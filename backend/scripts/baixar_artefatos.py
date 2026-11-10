"""Baixa os artefatos treinados da última GitHub Release e extrai em backend/artifacts/.

Uso (dentro de backend/):  python -m scripts.baixar_artefatos [--forcar]

É o caminho rápido para rodar a API, a interface, o script de demonstração e o notebook final sem refazer a
preparação dos dados (que baixa ~700 MB de bases públicas e leva bastante tempo).
"""
import io
import sys
import zipfile

import httpx

from app import config

URL = "https://github.com/GustavoJRoss/analise-acidentes/releases/latest/download/artefatos.zip"


def main():
    if config.REDES["br"].modelo.exists() and "--forcar" not in sys.argv:
        print(f"Os artefatos já existem em {config.ARTIFACTS} (use --forcar para baixar de novo).")
        return
    print(f"Baixando {URL} …")
    resp = httpx.get(URL, timeout=300, follow_redirects=True)
    resp.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
        for nome in z.namelist():  # só caminhos relativos dentro de artifacts/
            if nome.startswith("/") or ".." in nome.split("/"):
                raise RuntimeError(f"Caminho inválido no pacote: {nome}")
        z.extractall(config.ARTIFACTS)
        print(f"{len(z.namelist())} arquivos extraídos em {config.ARTIFACTS}")


if __name__ == "__main__":
    main()
