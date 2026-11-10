"""Rede "sc": RENAEST → acidentes nas rodovias estaduais, trechos rodovia × município, geometria e clima.

Uso (dentro de backend/):  python -m scripts.preparar_estaduais [--forcar]
Baixa (com cache em dados_externos/ e artifacts/estaduais/): RENAEST (~530 MB), malha municipal do IBGE,
vias do OSM com nome, rodovias estaduais do OSM e clima histórico do Open-Meteo. Se o Open-Meteo pedir para
esperar no meio do clima, é só rodar de novo: os lotes já baixados ficam guardados.
"""
import json
import sys

import pandas as pd

from app import clima, config, dados, osm, renaest
from app.features import nivel_notificacao


def main(forcar: bool = False):
    artefatos = config.REDES["sc"]

    print("Baixando bases (RENAEST, IBGE, OSM)…")
    renaest.baixar_municipios(forcar)
    poligonos, nomes_mun = renaest.carregar_municipios()
    zip_renaest = renaest.baixar_renaest(forcar)
    acid = renaest.extrair_uf(zip_renaest, forcar)
    print(f"  {len(acid):,} acidentes de {config.UF} no RENAEST ({zip_renaest.name})")

    print("Limpando endereços e casando com as vias do OSM…")
    casados = renaest.limpar_e_casar(acid, osm.baixar_vias_nomeadas(forcar), poligonos, nomes_mun)
    casados.to_parquet(config.ARQ_RENAEST_VIAS, index=False)
    casou = ~casados["metodo"].isin(["vazio", "sem_casamento"])
    print(f"  {casou.mean():.1%} dos acidentes casados com uma via; esferas: "
          f"{casados['esfera'].value_counts(normalize=True).round(3).to_dict()}")

    datas = pd.to_datetime(casados["data_acidente"])
    nivel_notificacao(datas, config.INICIO_RENAEST, config.FIM_RENAEST).to_parquet(artefatos.notificacao)
    no_periodo = datas.between(config.INICIO_RENAEST, config.FIM_RENAEST)
    est = casados[(casados["esfera"] == "estadual") & no_periodo].copy()
    est["data"] = pd.to_datetime(est["data_acidente"])
    est["periodo"] = dados.periodo_da_hora(est["hora_acidente"].str[:2].astype(int))
    est["mortos"] = pd.to_numeric(est["qtde_obitos"], errors="coerce").fillna(0).astype(int)

    # todo par rodovia × município do OSM entra, com ou sem acidente (o modelo precisa ver trechos seguros)
    pares_com_acidente = set(est.groupby(["rodovia", "codigo_ibge"]).size().index)

    print("Cortando as rodovias estaduais pelos municípios…")
    geojson, pontos, trechos = osm.construir_trechos_estaduais(
        osm.baixar_rodovias_estaduais(forcar), poligonos, pares_com_acidente)
    est["trecho_id"] = [osm.id_trecho_estadual(r, c) for r, c in zip(est["rodovia"], est["codigo_ibge"])]
    acidentes = est[est["trecho_id"].isin(trechos["trecho_id"])][["trecho_id", "data", "periodo", "mortos"]]
    print(f"  {len(trechos)} trechos com geometria; {len(acidentes):,} de {len(est):,} acidentes estaduais "
          f"({len(acidentes) / len(est):.1%}) ficam no modelo")

    n_anos = config.ANOS_COBERTOS_RENAEST
    totais = acidentes.groupby("trecho_id").agg(acidentes=("data", "size"), mortos=("mortos", "sum"))
    trechos = trechos.merge(totais, on="trecho_id", how="left").fillna({"acidentes": 0, "mortos": 0})
    trechos[["acidentes", "mortos"]] = trechos[["acidentes", "mortos"]].astype(int)
    print(f"  {(trechos['acidentes'] == 0).sum()} trechos sem nenhum acidente casado no período")
    trechos["municipio"] = trechos["codigo_ibge"].map(nomes_mun)
    trechos["acidentes_ano"] = (trechos["acidentes"] / n_anos).round(1)
    trechos = dados.adicionar_celula(trechos)

    acidentes.reset_index(drop=True).to_parquet(artefatos.acidentes)
    trechos.to_parquet(artefatos.trechos)
    artefatos.trechos_geojson.write_text(json.dumps(geojson))
    pontos.to_parquet(artefatos.pontos_via)
    print(f"  {len(pontos):,} pontos de via; maiores trechos: "
          f"{trechos.nlargest(5, 'acidentes')[['trecho_id', 'municipio', 'acidentes']].values.tolist()}")

    inicio, fim = f"{config.INICIO_RENAEST:%Y-%m-%d}", f"{config.FIM_RENAEST:%Y-%m-%d}"
    celulas = trechos[["celula", "celula_lat", "celula_lon"]].drop_duplicates("celula")
    print(f"Baixando clima histórico {inicio} a {fim} para {len(celulas)} células (Open-Meteo)…")
    hist = clima.baixar_historico(celulas, inicio, fim, artefatos, forcar)
    print(f"  {hist['celula'].nunique()} células, {len(hist):,} linhas célula×dia×período")


if __name__ == "__main__":
    main(forcar="--forcar" in sys.argv)
