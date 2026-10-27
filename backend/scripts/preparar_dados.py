"""CSV da PRF → acidentes.parquet, clima.parquet, trechos.geojson e pontos_via.parquet.

Uso (dentro de backend/):  python -m scripts.preparar_dados [--forcar]
Downloads externos (Overpass, Open-Meteo) ficam em cache em artifacts/; --forcar baixa de novo.
"""
import json
import sys

from app import clima, config, dados, osm


def main(forcar: bool = False):
    config.ARTIFACTS.mkdir(exist_ok=True)

    print("Lendo CSV da PRF…")
    acidentes = dados.carregar_acidentes()
    acidentes.to_parquet(config.ARQ_ACIDENTES)
    trechos = dados.resumo_trechos(acidentes)
    print(f"  {len(acidentes):,} acidentes em {config.UF}, {len(trechos)} trechos")

    print("Baixando geometria das BRs (Overpass/OSM)…")
    bruto = osm.baixar_osm(forcar)
    geojson, pontos = osm.construir_trechos(bruto, acidentes, set(trechos["trecho_id"]))
    config.ARQ_TRECHOS_GEOJSON.write_text(json.dumps(geojson))
    pontos.to_parquet(config.ARQ_PONTOS_VIA)
    print(f"  {len(geojson['features'])} trechos com geometria, {len(pontos):,} pontos de via")

    print("Baixando clima histórico (Open-Meteo)…")
    inicio = acidentes["data"].min().strftime("%Y-%m-%d")
    fim = acidentes["data"].max().strftime("%Y-%m-%d")
    hist = clima.baixar_historico(trechos[["celula", "celula_lat", "celula_lon"]], inicio, fim, forcar)
    print(f"  {hist['celula'].nunique()} células, {len(hist):,} linhas célula×dia×período")


if __name__ == "__main__":
    main(forcar="--forcar" in sys.argv)
