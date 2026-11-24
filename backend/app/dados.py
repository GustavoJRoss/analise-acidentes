"""Carga dos CSVs da PRF (2017–2025): filtra SC e passa de uma linha por pessoa para uma linha por acidente."""
from pathlib import Path

import pandas as pd

from . import config

COLUNAS = [
    "id", "pesid", "data_inversa", "horario", "uf", "br", "km", "municipio", "ordem_tipo_acidente",
    "tipo_acidente", "classificacao_acidente", "latitude", "longitude", "delegacia",
    "ilesos", "feridos_leves", "feridos_graves", "mortos",
]


def periodo_da_hora(hora: pd.Series) -> pd.Series:
    rotulos = list(config.PERIODOS)
    limites = [inicio for inicio, _ in config.PERIODOS.values()] + [24]
    return pd.cut(hora, bins=limites, right=False, labels=rotulos).astype(str)


def id_trecho(br, trecho_km) -> str:
    return f"{int(br)}-{int(trecho_km)}"


def arquivo_prf(ano: int, forcar: bool = False) -> Path:
    """Caminho do CSV (ou ZIP) da PRF de um ano. Baixa do Google Drive (gdown) se ainda não existe."""
    if ano == 2025 and config.CSV_PATH.exists() and not forcar:
        return config.CSV_PATH
    for nome in (f"prf_{ano}.zip", f"acidentes{ano}_todas_causas_tipos.csv", f"acidentes{ano}_todas_causas_tipos.zip"):
        if (config.PASTA_PRF / nome).exists() and not forcar:
            return config.PASTA_PRF / nome
    destino = config.PASTA_PRF / f"prf_{ano}.zip"
    destino.parent.mkdir(parents=True, exist_ok=True)
    try:
        import gdown
        gdown.download(id=config.IDS_DRIVE_PRF[ano], output=str(destino), quiet=True)
    except Exception as exc:  # o Google Drive às vezes bloqueia downloads automáticos
        destino.unlink(missing_ok=True)
        raise RuntimeError(
            f"Não consegui baixar a base da PRF de {ano} ({exc}). Baixe em {config.URL_PORTAL_PRF} "
            f"(Acidentes → Agrupados por pessoa – Todas as causas e tipos de acidentes, {ano}) e coloque o ZIP "
            f"ou o CSV em {config.PASTA_PRF}/") from exc
    return destino


def _pessoas_sc(caminho: Path) -> pd.DataFrame:
    """Lê um CSV da PRF (o pandas abre o ZIP direto) e devolve só as linhas de SC."""
    blocos = pd.read_csv(caminho, sep=";", encoding="latin1", decimal=",", low_memory=False, dtype=str,
                         usecols=lambda c: c in COLUNAS, chunksize=500_000)
    pessoas = pd.concat([b[b["uf"] == config.UF] for b in blocos], ignore_index=True)
    for col in set(COLUNAS) - set(pessoas.columns):
        pessoas[col] = pd.NA
    return pessoas


def _numero(serie: pd.Series) -> pd.Series:
    """'303,5' ou '303.5' → 303.5."""
    return pd.to_numeric(serie.astype(str).str.replace(",", ".", regex=False), errors="coerce")


def _data(serie: pd.Series) -> pd.Series:
    """Os arquivos usam AAAA-MM-DD; alguns anos antigos da PRF usaram DD/MM/AAAA."""
    data = pd.to_datetime(serie, format="%Y-%m-%d", errors="coerce")
    falhas = data.isna()
    data[falhas] = pd.to_datetime(serie[falhas], format="%d/%m/%Y", errors="coerce")
    if data.isna().any():
        raise ValueError(f"{data.isna().sum()} datas inválidas na base da PRF: {serie[data.isna()].head().tolist()}")
    return data


def carregar_acidentes(arquivos=None) -> pd.DataFrame:
    """arquivos: lista de CSV/ZIP da PRF; por padrão, os de config.ANOS_PRF (baixados se faltarem)."""
    arquivos = arquivos if arquivos is not None else [arquivo_prf(a) for a in config.ANOS_PRF]
    return limpar_pessoas(pd.concat([_pessoas_sc(Path(a)) for a in arquivos], ignore_index=True))


def limpar_pessoas(pessoas: pd.DataFrame) -> pd.DataFrame:
    """Linhas brutas da PRF (uma por pessoa, colunas como texto) → uma linha por acidente, validada.

    Também usada pelo pipeline MLOps (src/), que recebe os lotes brutos e refaz esta limpeza a cada ciclo.
    """
    pessoas = pessoas.copy()
    for col in ["id", "pesid", "br", "ordem_tipo_acidente", "ilesos", "feridos_leves", "feridos_graves", "mortos"]:
        pessoas[col] = _numero(pessoas[col])
    for col in ["km", "latitude", "longitude"]:
        pessoas[col] = _numero(pessoas[col])

    vitimas = (pessoas.drop_duplicates(["id", "pesid"])
               .groupby("id")[["ilesos", "feridos_leves", "feridos_graves", "mortos"]].sum())

    # ordem_tipo_acidente == 1 é o tipo principal do acidente
    acidentes = (pessoas.sort_values(["id", "ordem_tipo_acidente"], kind="stable")  # determinístico em empates
                 .drop_duplicates("id")
                 .drop(columns=["pesid", "ilesos", "feridos_leves", "feridos_graves", "mortos", "uf"])
                 .merge(vitimas, on="id")
                 .dropna(subset=["br", "km", "latitude", "longitude"]))
    lat, lon = config.BBOX_SC["lat"], config.BBOX_SC["lon"]
    dentro = acidentes["latitude"].between(*lat) & acidentes["longitude"].between(*lon)
    if (~dentro).any():
        print(f"  {(~dentro).sum()} acidentes com coordenada fora de SC descartados")
    acidentes = acidentes[dentro].copy()

    acidentes["id"] = acidentes["id"].astype(int)
    acidentes["data"] = _data(acidentes["data_inversa"])
    acidentes["hora"] = pd.to_datetime(acidentes["horario"], format="%H:%M:%S").dt.hour
    acidentes["periodo"] = periodo_da_hora(acidentes["hora"])
    acidentes["br"] = acidentes["br"].astype(int)
    acidentes["trecho_km"] = (acidentes["km"] // config.TAMANHO_TRECHO_KM * config.TAMANHO_TRECHO_KM).astype(int)
    acidentes["trecho_id"] = [id_trecho(b, k) for b, k in zip(acidentes["br"], acidentes["trecho_km"])]
    return acidentes.drop(columns=["data_inversa", "horario", "ordem_tipo_acidente"]).reset_index(drop=True)


def resumo_trechos(acidentes: pd.DataFrame) -> pd.DataFrame:
    """Uma linha por trecho: localização representativa e totais do período (e a média por ano)."""
    def moda(s):
        return s.mode().iat[0]

    trechos = (acidentes.groupby("trecho_id")
               .agg(br=("br", "first"), trecho_km=("trecho_km", "first"),
                    lat=("latitude", "median"), lon=("longitude", "median"),
                    delegacia=("delegacia", moda), municipio=("municipio", moda),
                    acidentes=("id", "size"), mortos=("mortos", "sum"),
                    feridos_graves=("feridos_graves", "sum"))
               .reset_index())
    trechos["acidentes_ano"] = (trechos["acidentes"] / config.ANOS_COBERTOS_PRF).round(1)
    return adicionar_celula(trechos)


def adicionar_celula(trechos: pd.DataFrame) -> pd.DataFrame:
    """Célula da grade de clima (~0,25°) mais próxima do ponto representativo de cada trecho."""
    celula = config.TAMANHO_CELULA_CLIMA
    trechos["celula_lat"] = (trechos["lat"] / celula).round() * celula
    trechos["celula_lon"] = (trechos["lon"] / celula).round() * celula
    trechos["celula"] = trechos["celula_lat"].round(2).astype(str) + "," + trechos["celula_lon"].round(2).astype(str)
    return trechos
