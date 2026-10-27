"""Carrega os artefatos uma vez e responde às previsões da API."""
import json

import joblib
import numpy as np
import pandas as pd

from . import config
from .features import montar_linhas, preparar_X


class ServicoPrevisao:
    def __init__(self):
        pacote = joblib.load(config.ARQ_MODELO)
        self.modelo = pacote["modelo"]
        self.features = pacote["features"]
        self.categorias = pacote["categorias"]
        self.estado = pd.read_parquet(config.ARQ_ESTADO).set_index("trecho_id", drop=False)
        self.climatologia = pd.read_parquet(config.ARQ_CLIMATOLOGIA)
        self.presets = json.loads(config.ARQ_PRESETS_CLIMA.read_text())
        self.metricas = json.loads(config.ARQ_METRICAS.read_text())
        self.geojson = json.loads(config.ARQ_TRECHOS_GEOJSON.read_text())

    # ---- previsão -------------------------------------------------------------------------
    def _linhas(self, trecho_ids, data, periodo, clima):
        return montar_linhas(self.estado.loc[trecho_ids].reset_index(drop=True), data, periodo, clima,
                             self.climatologia)

    def _prob(self, linhas: pd.DataFrame) -> np.ndarray:
        return self.modelo.predict_proba(preparar_X(linhas, self.categorias, self.features))[:, 1]

    @staticmethod
    def _combinar(p: np.ndarray) -> float:
        """Probabilidade de ao menos um acidente em algum dos trechos."""
        return float(1 - np.prod(1 - p))

    def valores_clima(self, categoria: str, personalizado: dict = None) -> dict:
        if personalizado:
            return personalizado
        return {k: self.presets[categoria][k] for k in ("chuva_mm", "nebulosidade")}

    def prever(self, trecho_ids: list, data: pd.Timestamp, periodo: str, categoria: str,
               clima_personalizado: dict = None) -> dict:
        clima = self.valores_clima(categoria, clima_personalizado)
        linhas = self._linhas(trecho_ids, data, periodo, clima)
        p = self._prob(linhas)
        p_total = self._combinar(p)

        # referência: frequência observada em 2025 no mesmo trecho e período
        taxa = self.estado.loc[trecho_ids, f"taxa_{periodo}"].values
        p_media = self._combinar(np.clip(taxa, 0, 1))

        trechos = []
        for (_, linha), prob, media in zip(linhas.iterrows(), p, taxa):
            trechos.append({
                "trecho_id": linha["trecho_id"], "br": int(linha["br"]), "trecho_km": int(linha["trecho_km"]),
                "municipio": linha["municipio"], "probabilidade": round(float(prob), 5),
                "media_periodo": round(float(media), 5),
            })
        return {
            "probabilidade": round(p_total, 5),
            "media_referencia": round(p_media, 5),
            "razao_media": round(p_total / p_media, 2) if p_media > 0 else None,
            "trechos": trechos,
            "fatores": self._fatores(linhas, p_total, periodo, categoria, clima_personalizado is not None),
            "cenario": {
                "data": str(pd.Timestamp(data).date()), "periodo": periodo, "clima": categoria,
                "feriado": bool(linhas["feriado"].iat[0]), "vespera_ou_pos_feriado": bool(linhas["vespera_ou_pos_feriado"].iat[0]),
                "fim_de_semana": bool(linhas["fim_de_semana"].iat[0]), "temporada_verao": bool(linhas["temporada_verao"].iat[0]),
                "chuva_mm": float(linhas["chuva_mm"].iat[0]), "temperatura": round(float(linhas["temperatura"].mean()), 1),
            },
        }

    # ---- explicação: quanto cada escolha muda o risco em relação a uma referência neutra --------
    def _fatores(self, linhas, p_total, periodo, categoria, clima_personalizado):
        cenarios = {}

        if categoria != "ceu_claro" or clima_personalizado:
            ref = linhas.copy()
            for k, v in self.valores_clima("ceu_claro").items():
                ref[k] = v
            rotulo = "Clima previsto" if clima_personalizado else self.presets[categoria]["rotulo"]
            cenarios[f"{rotulo} (vs. céu claro)"] = [ref]

        outros_periodos = []
        for outro in config.PERIODOS:
            ref = linhas.copy()
            ref["periodo_idx"] = config.PERIODO_IDX[outro]
            ref["taxa_historica_periodo"] = ref[f"taxa_{outro}"]
            outros_periodos.append(ref)
        cenarios[f"Período: {periodo} (vs. média do dia)"] = outros_periodos

        dia = linhas.iloc[0]
        if dia["feriado"] or dia["vespera_ou_pos_feriado"] or dia["fim_de_semana"]:
            ref = linhas.copy()
            ref[["dia_semana", "fim_de_semana", "feriado", "vespera_ou_pos_feriado"]] = [2, 0, 0, 0]
            if dia["feriado"]:
                rotulo = "Feriado"
            elif dia["vespera_ou_pos_feriado"]:
                rotulo = "Véspera/dia seguinte a feriado"
            else:
                rotulo = "Fim de semana"
            cenarios[f"{rotulo} (vs. quarta-feira comum)"] = [ref]

        meses = []
        for mes in range(1, 13):
            ref = linhas.copy()
            ref["mes"] = mes
            ref["temporada_verao"] = int(mes in (12, 1, 2))
            meses.append(ref)
        cenarios["Época do ano (vs. média dos meses)"] = meses

        # uma única chamada ao modelo para todos os cenários
        blocos, chaves = [], []
        for nome, variantes in cenarios.items():
            for i, v in enumerate(variantes):
                blocos.append(v)
                chaves.extend([(nome, i)] * len(v))
        p = self._prob(pd.concat(blocos, ignore_index=True))
        resultado = pd.DataFrame(chaves, columns=["fator", "variante"]).assign(p=p)

        fatores = []
        for nome, grupo in resultado.groupby("fator", sort=False):
            p_ref = np.mean([self._combinar(g["p"].values) for _, g in grupo.groupby("variante")])
            fatores.append({"fator": nome, "efeito": round(p_total - p_ref, 5),
                            "efeito_relativo": round(p_total / p_ref - 1, 3) if p_ref > 0 else 0.0})
        return sorted(fatores, key=lambda f: -abs(f["efeito_relativo"]))

    # ---- dados para o mapa ------------------------------------------------------------------------
    def trechos_geojson(self) -> dict:
        features = []
        for feat in self.geojson["features"]:
            tid = feat["properties"]["trecho_id"]
            if tid not in self.estado.index:
                continue
            e = self.estado.loc[tid]
            props = {
                "trecho_id": tid, "br": int(e["br"]), "trecho_km": int(e["trecho_km"]), "municipio": e["municipio"],
                "acidentes": int(e["acidentes"]), "mortos": int(e["mortos"]), "feridos_graves": int(e["feridos_graves"]),
                "prob_dia": round(float(1 - np.exp(-e["taxa_historica"])), 4),
                "centro": [round(float(e["lat"]), 5), round(float(e["lon"]), 5)],
            }
            features.append({**feat, "properties": props})
        return {"type": "FeatureCollection", "features": features}

    def centro(self, trecho_id: str):
        e = self.estado.loc[trecho_id]
        return float(e["lat"]), float(e["lon"])
