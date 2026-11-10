"""Empacota os artefatos treinados para publicar como anexo de uma GitHub Release.

Uso (dentro de backend/):  python -m scripts.empacotar_artefatos   →  ../dist/artefatos.zip

Inclui o que a API, o script de demonstração, o notebook final e um novo treino (scripts.treinar) precisam.
Ficam de fora os caches de download (clima_lotes/, osm_brs.json), que só servem para preparar os dados do zero.
"""
import zipfile

from app import config

ARQUIVOS_POR_REDE = ["modelo.joblib", "estado_trechos.parquet", "trechos.geojson", "pontos_via.parquet",
                     "climatologia.parquet", "clima_presets.json", "metricas.json", "trechos.parquet",
                     "acidentes.parquet", "clima.parquet", "notificacao.parquet", "teste_previsoes.parquet"]
DESTINO = config.ROOT_DIR / "dist" / "artefatos.zip"


def main():
    DESTINO.parent.mkdir(exist_ok=True)
    arquivos = [a.pasta / nome for a in config.REDES.values() for nome in ARQUIVOS_POR_REDE]
    arquivos = [p for p in arquivos if p.exists()]
    arquivos += sorted((config.ARTIFACTS / "historico_metricas").glob("*.json"))
    extra = config.ARTIFACTS / "relatorio_dados.json"
    if extra.exists():
        arquivos.append(extra)
    with zipfile.ZipFile(DESTINO, "w", zipfile.ZIP_DEFLATED) as z:
        for p in arquivos:
            z.write(p, p.relative_to(config.ARTIFACTS))
    print(f"{len(arquivos)} arquivos → {DESTINO} ({DESTINO.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
