"""Rede "br": CSVs da PRF 2017–2025 → acidentes, trechos, clima, trechos.geojson e pontos_via.parquet.

Uso (dentro de backend/):  python -m scripts.preparar_dados [--forcar]
Os CSVs da PRF são baixados do Google Drive para dados_externos/prf/ (se falhar, o erro explica como baixar à
mão). Overpass e Open-Meteo ficam em cache em artifacts/; --forcar baixa tudo de novo.
"""
import json
import sys

import pandas as pd

from app import clima, config, dados, osm, trafego


def main(forcar: bool = False):
    artefatos = config.REDES["br"]

    print(f"Lendo CSVs da PRF {config.ANOS_PRF[0]}–{config.ANOS_PRF[-1]}…")
    acidentes = dados.carregar_acidentes([dados.arquivo_prf(a, forcar) for a in config.ANOS_PRF])
    acidentes.to_parquet(artefatos.acidentes)
    por_ano = acidentes.groupby(acidentes["data"].dt.year).size().to_dict()
    print(f"  {len(acidentes):,} acidentes em {config.UF}; por ano: {por_ano}")

    print("Baixando geometria das BRs (Overpass/OSM)…")
    bruto = osm.baixar_osm(forcar)
    geojson, pontos = osm.construir_trechos(bruto, acidentes)
    artefatos.trechos_geojson.write_text(json.dumps(geojson))
    pontos.to_parquet(artefatos.pontos_via)

    # trechos com acidente + trechos que só existem pela geometria (zero acidentes no período)
    com_acidente = dados.resumo_trechos(acidentes)
    sem_acidente = osm.trechos_sem_acidente(pontos, acidentes)
    trechos = dados.adicionar_celula(pd.concat([com_acidente.drop(columns=["celula", "celula_lat", "celula_lon"]),
                                                sem_acidente], ignore_index=True))
    trechos["vmd"] = trafego.vmd_por_trecho(trechos, trafego.carregar_vmd(forcar))
    trechos.to_parquet(artefatos.trechos)
    print(f"  VMD do DNIT em {trechos['vmd'].notna().mean():.0%} dos trechos "
          f"(mediana {trechos['vmd'].median():,.0f} veículos/dia)")
    print(f"  {len(geojson['features'])} trechos com geometria, {len(pontos):,} pontos de via; "
          f"{len(com_acidente)} trechos com acidente + {len(sem_acidente)} sem nenhum")

    print("Baixando clima histórico (Open-Meteo)…")
    inicio = acidentes["data"].min().strftime("%Y-%m-%d")
    fim = acidentes["data"].max().strftime("%Y-%m-%d")
    hist = clima.baixar_historico(trechos[["celula", "celula_lat", "celula_lon"]], inicio, fim, artefatos, forcar)
    print(f"  {hist['celula'].nunique()} células, {len(hist):,} linhas célula×dia×período")


if __name__ == "__main__":
    main(forcar="--forcar" in sys.argv)
