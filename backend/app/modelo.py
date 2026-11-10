"""Carrega os artefatos de cada rede uma vez e responde às previsões da API.

- ServicoPrevisao: um modelo, o de uma rede ("br" = BRs/PRF, "sc" = rodovias estaduais/RENAEST).
- PrevisaoCombinada: o que a API usa. Separa os trechos pedidos por rede, consulta cada modelo e combina
  as probabilidades — uma rota pode passar por BRs e por rodovias estaduais.
"""
import json

import joblib
import numpy as np
import pandas as pd

from . import config
from .features import montar_linhas, preparar_X

DESCRICAO_PERIODO_DADOS = {"br": "média 2017–2025 (PRF)", "sc": "média jan/2019–mai/2026 (RENAEST)"}


def combinar(p) -> float:
    """Probabilidade de ao menos um acidente em algum dos trechos."""
    return float(1 - np.prod(1 - np.asarray(p)))


def prob_pela_taxa(taxa: float) -> float:
    """Taxa histórica (acidentes por dia-período, pode passar de 1) → chance de ao menos um acidente (Poisson)."""
    return float(1 - np.exp(-max(taxa, 0.0)))


def rede_do_trecho(trecho_id: str) -> str:
    """'101-200' → 'br'; 'SC-401|4205407' → 'sc'."""
    return "sc" if trecho_id.startswith("SC") else "br"


class ServicoPrevisao:
    def __init__(self, rede: str):
        artefatos = config.REDES[rede]
        pacote = joblib.load(artefatos.modelo)
        self.rede = rede
        self.modelo = pacote["modelo"]
        self.features = pacote["features"]
        self.categorias = pacote["categorias"]
        self.estado = pd.read_parquet(artefatos.estado).set_index("trecho_id", drop=False)
        self.climatologia = pd.read_parquet(artefatos.climatologia)
        self.presets = json.loads(artefatos.presets_clima.read_text())
        self.metricas = json.loads(artefatos.metricas.read_text())
        self.geojson = json.loads(artefatos.trechos_geojson.read_text())

    # ---- previsão -------------------------------------------------------------------------
    def linhas(self, trecho_ids, data, periodo, clima):
        return montar_linhas(self.estado.loc[trecho_ids].reset_index(drop=True), data, periodo, clima,
                             self.climatologia)

    def prob(self, linhas: pd.DataFrame) -> np.ndarray:
        return self.modelo.predict_proba(preparar_X(linhas, self.categorias, self.features))[:, 1]

    def valores_clima(self, categoria: str, personalizado: dict = None) -> dict:
        if personalizado:
            return personalizado
        return {k: self.presets[categoria][k] for k in ("chuva_mm", "nebulosidade")}

    def cenarios_fatores(self, linhas, periodo, categoria, clima_personalizado) -> dict:
        """Cenários de referência para explicar o resultado: nome do fator → lista de variantes das linhas.

        A estrutura (nomes e número de variantes) depende só da data, período e clima, nunca dos trechos:
        assim as duas redes produzem cenários que podem ser combinados variante a variante.
        """
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
        return cenarios

    def prob_cenarios(self, cenarios: dict) -> dict:
        """Uma única chamada ao modelo para todos os cenários: (fator, variante) → probabilidades por trecho."""
        blocos, chaves = [], []
        for nome, variantes in cenarios.items():
            for i, v in enumerate(variantes):
                blocos.append(v)
                chaves.extend([(nome, i)] * len(v))
        p = self.prob(pd.concat(blocos, ignore_index=True))
        resultado = pd.DataFrame(chaves, columns=["fator", "variante"]).assign(p=p)
        return {chave: g["p"].to_numpy() for chave, g in resultado.groupby(["fator", "variante"], sort=False)}

    # ---- descrição dos trechos ------------------------------------------------------------------
    def descricao(self, e) -> dict:
        if self.rede == "br":
            br, km = int(e["br"]), int(e["trecho_km"])
            rodovia, rotulo, comprimento = f"BR-{br}", f"BR-{br} · km {km}–{km + config.TAMANHO_TRECHO_KM}", config.TAMANHO_TRECHO_KM
            acidentes_ano = float(e["acidentes_ano"])
        else:
            rodovia, comprimento = e["rodovia"], float(e["comprimento_km"])
            rotulo, acidentes_ano = f"{rodovia} · {e['municipio']}", float(e["acidentes_ano"])
        return {"trecho_id": e["trecho_id"], "rede": self.rede, "rodovia": rodovia, "rotulo": rotulo,
                "municipio": e["municipio"], "comprimento_km": round(comprimento, 1),
                "acidentes_ano": round(acidentes_ano, 1),
                # acidentes por 10 km por ano: deixa trechos de tamanhos diferentes na mesma escala do mapa
                "densidade": round(acidentes_ano / max(comprimento, 1.0) * 10, 1)}

    def trechos_geojson(self) -> list:
        features = []
        for feat in self.geojson["features"]:
            tid = feat["properties"]["trecho_id"]
            if tid not in self.estado.index:
                continue
            e = self.estado.loc[tid]
            props = {
                **self.descricao(e),
                "acidentes": int(e["acidentes"]), "mortos": int(e["mortos"]),
                "periodo_dados": DESCRICAO_PERIODO_DADOS[self.rede],
                "centro": [round(float(e["lat"]), 5), round(float(e["lon"]), 5)],
            }
            features.append({**feat, "properties": props})
        return features

    def centro(self, trecho_id: str):
        e = self.estado.loc[trecho_id]
        return float(e["lat"]), float(e["lon"])


class PrevisaoCombinada:
    def __init__(self):
        # a rede estadual é opcional: sem os artefatos dela, o app segue só com as BRs
        self.servicos = {rede: ServicoPrevisao(rede) for rede, a in config.REDES.items() if a.modelo.exists()}
        self.presets = self.servicos["br"].presets

    def conhece(self, trecho_id: str) -> bool:
        servico = self.servicos.get(rede_do_trecho(trecho_id))
        return servico is not None and trecho_id in servico.estado.index

    def servico_do_trecho(self, trecho_id: str) -> ServicoPrevisao:
        return self.servicos[rede_do_trecho(trecho_id)]

    def prever(self, trecho_ids: list, data: pd.Timestamp, periodo: str, categoria: str,
               clima_personalizado: dict = None) -> dict:
        por_rede = {}
        for tid in trecho_ids:
            por_rede.setdefault(rede_do_trecho(tid), []).append(tid)

        probs, medias, descricoes, cenarios_p, primeiras = {}, [], {}, [], None
        for rede, ids in por_rede.items():
            servico = self.servicos[rede]
            clima = servico.valores_clima(categoria, clima_personalizado)
            linhas = servico.linhas(ids, data, periodo, clima)
            primeiras = linhas if primeiras is None else primeiras
            for tid, p, (_, e) in zip(ids, servico.prob(linhas), servico.estado.loc[ids].iterrows()):
                probs[tid] = float(p)
                media = prob_pela_taxa(float(e[f"taxa_{periodo}"]))
                medias.append(media)
                descricoes[tid] = {**servico.descricao(e), "media_periodo": round(media, 5)}
            cenarios = servico.cenarios_fatores(linhas, periodo, categoria, clima_personalizado is not None)
            cenarios_p.append(servico.prob_cenarios(cenarios))

        p_total = combinar(list(probs.values()))
        p_media = combinar(medias)
        trechos = [{**descricoes[t], "probabilidade": round(probs[t], 5)} for t in trecho_ids]
        return {
            "probabilidade": round(p_total, 5),
            "media_referencia": round(p_media, 5),
            "razao_media": round(p_total / p_media, 2) if p_media > 0 else None,
            "trechos": trechos,
            "fatores": self._fatores(cenarios_p, p_total),
            "cenario": {
                "data": str(pd.Timestamp(data).date()), "periodo": periodo, "clima": categoria,
                "feriado": bool(primeiras["feriado"].iat[0]),
                "vespera_ou_pos_feriado": bool(primeiras["vespera_ou_pos_feriado"].iat[0]),
                "fim_de_semana": bool(primeiras["fim_de_semana"].iat[0]),
                "temporada_verao": bool(primeiras["temporada_verao"].iat[0]),
                "chuva_mm": float(primeiras["chuva_mm"].iat[0]),
                "temperatura": round(float(primeiras["temperatura"].mean()), 1),
            },
        }

    @staticmethod
    def _fatores(cenarios_por_rede: list, p_total: float) -> list:
        """Quanto cada escolha muda o risco em relação a uma referência neutra, juntando as redes."""
        juntos = {}
        for cenarios in cenarios_por_rede:
            for chave, p in cenarios.items():
                juntos.setdefault(chave, []).append(p)
        por_fator = {}
        for (fator, variante), partes in juntos.items():
            por_fator.setdefault(fator, []).append(combinar(np.concatenate(partes)))
        fatores = []
        for nome, refs in por_fator.items():
            p_ref = float(np.mean(refs))
            fatores.append({"fator": nome, "efeito": round(p_total - p_ref, 5),
                            "efeito_relativo": round(p_total / p_ref - 1, 3) if p_ref > 0 else 0.0})
        return sorted(fatores, key=lambda f: -abs(f["efeito_relativo"]))

    def trechos_geojson(self) -> dict:
        return {"type": "FeatureCollection",
                "features": [f for s in self.servicos.values() for f in s.trechos_geojson()]}

    def centro(self, trecho_id: str):
        return self.servico_do_trecho(trecho_id).centro(trecho_id)

    @property
    def metricas(self) -> dict:
        return {rede: s.metricas for rede, s in self.servicos.items()}
