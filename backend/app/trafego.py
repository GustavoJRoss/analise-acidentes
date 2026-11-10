"""Volume de tráfego (VMD) das BRs, da planilha "Fatores VMD e UPE por trecho" do DNIT.

O DNIT publica, em PDF, o VMD (volume médio diário) de cada segmento do SNV, com UF, BR e km inicial/final na
mesma quilometragem usada pela PRF. Aqui o PDF é lido, filtrado para SC e o VMD é levado para os trechos de
10 km do modelo como média ponderada pela extensão de cada segmento dentro do trecho.

Os valores são de uma única data de atualização (não há série histórica): o VMD entra como característica fixa
do trecho, não varia com o dia.
"""
import re

import httpx
import numpy as np
import pandas as pd

from . import config

URL_VMD_DNIT = ("https://www.gov.br/dnit/pt-br/rodovias/operacoes-rodoviarias/faixa-de-dominio/"
                "planilha_f_upe_snv_20-08-2026.pdf")
ARQ_PDF = config.DADOS_EXTERNOS / "dnit" / "fatores_vmd_upe.pdf"
ARQ_VMD = config.DADOS_EXTERNOS / "dnit" / "vmd_snv.parquet"

# "SC 101 101BSC0010 0 0 2,4 2,40 19101,65 1,48 1,50": UF, BR, código SNV, coincidentes, km i, km f, extensão, VMD…
_NUM = r"(\d+(?:,\d+)?)"
RE_LINHA = re.compile(rf"^([A-Z]{{2}}) (\d+) (\S+) (\S+) {_NUM} {_NUM} {_NUM} {_NUM} {_NUM} {_NUM}$")


def _numero(texto: str) -> float:
    return float(texto.replace(".", "").replace(",", ".")) if "," in texto else float(texto)


def ler_pdf(caminho) -> pd.DataFrame:
    import pdfplumber  # só necessário para (re)gerar o parquet

    linhas = []
    with pdfplumber.open(caminho) as pdf:
        for pagina in pdf.pages:
            for linha in (pagina.extract_text() or "").splitlines():
                m = RE_LINHA.match(linha.strip())
                if m:
                    uf, br, snv, _, km_i, km_f, _, vmd, _, _ = m.groups()
                    linhas.append((uf, int(br), snv, _numero(km_i), _numero(km_f), _numero(vmd)))
    return pd.DataFrame(linhas, columns=["uf", "br", "snv", "km_inicial", "km_final", "vmd"])


def carregar_vmd(forcar: bool = False) -> pd.DataFrame:
    """Segmentos SNV de SC com VMD (baixa e lê o PDF na primeira vez)."""
    if ARQ_VMD.exists() and not forcar:
        return pd.read_parquet(ARQ_VMD)
    ARQ_PDF.parent.mkdir(parents=True, exist_ok=True)
    if forcar or not ARQ_PDF.exists():
        resp = httpx.get(URL_VMD_DNIT, timeout=120, follow_redirects=True, headers={"User-Agent": config.USER_AGENT})
        resp.raise_for_status()
        ARQ_PDF.write_bytes(resp.content)
    vmd = ler_pdf(ARQ_PDF)
    vmd = vmd[(vmd["uf"] == config.UF) & (vmd["vmd"] > 0)].reset_index(drop=True)
    vmd.to_parquet(ARQ_VMD)
    return vmd


def vmd_por_trecho(trechos: pd.DataFrame, vmd: pd.DataFrame) -> pd.Series:
    """VMD médio de cada trecho (br, trecho_km), ponderado pela sobreposição em km. NaN se não há segmento."""
    tam = config.TAMANHO_TRECHO_KM
    resultado = np.full(len(trechos), np.nan)
    por_br = {br: g for br, g in vmd.groupby("br")}
    for i, (br, km0) in enumerate(zip(trechos["br"], trechos["trecho_km"])):
        g = por_br.get(int(br))
        if g is None:
            continue
        sobreposicao = (np.minimum(g["km_final"], km0 + tam) - np.maximum(g["km_inicial"], km0)).clip(lower=0)
        if sobreposicao.sum() > 0:
            resultado[i] = float((g["vmd"] * sobreposicao).sum() / sobreposicao.sum())
    return pd.Series(resultado, index=trechos.index, name="vmd")
