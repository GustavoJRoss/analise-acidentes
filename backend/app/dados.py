"""Carga do CSV da PRF: filtra SC e passa de uma linha por pessoa para uma linha por acidente."""
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


def carregar_acidentes(csv_path=config.CSV_PATH) -> pd.DataFrame:
    raw = pd.read_csv(csv_path, sep=";", encoding="latin1", decimal=",", usecols=COLUNAS, low_memory=False)
    pessoas = raw[raw["uf"] == config.UF]

    vitimas = (pessoas.drop_duplicates(["id", "pesid"])
               .groupby("id")[["ilesos", "feridos_leves", "feridos_graves", "mortos"]].sum())

    # ordem_tipo_acidente == 1 é o tipo principal do acidente
    acidentes = (pessoas.sort_values(["id", "ordem_tipo_acidente"])
                 .drop_duplicates("id")
                 .drop(columns=["pesid", "ilesos", "feridos_leves", "feridos_graves", "mortos", "uf"])
                 .merge(vitimas, on="id")
                 .dropna(subset=["br", "km", "latitude", "longitude"]))

    acidentes["data"] = pd.to_datetime(acidentes["data_inversa"])
    acidentes["hora"] = pd.to_datetime(acidentes["horario"], format="%H:%M:%S").dt.hour
    acidentes["periodo"] = periodo_da_hora(acidentes["hora"])
    acidentes["br"] = acidentes["br"].astype(int)
    acidentes["trecho_km"] = (acidentes["km"] // config.TAMANHO_TRECHO_KM * config.TAMANHO_TRECHO_KM).astype(int)
    acidentes["trecho_id"] = [id_trecho(b, k) for b, k in zip(acidentes["br"], acidentes["trecho_km"])]
    return acidentes.drop(columns=["data_inversa", "horario", "ordem_tipo_acidente"]).reset_index(drop=True)


def resumo_trechos(acidentes: pd.DataFrame) -> pd.DataFrame:
    """Uma linha por trecho: localização representativa e totais de 2025."""
    def moda(s):
        return s.mode().iat[0]

    trechos = (acidentes.groupby("trecho_id")
               .agg(br=("br", "first"), trecho_km=("trecho_km", "first"),
                    lat=("latitude", "median"), lon=("longitude", "median"),
                    delegacia=("delegacia", moda), municipio=("municipio", moda),
                    acidentes=("id", "size"), mortos=("mortos", "sum"),
                    feridos_graves=("feridos_graves", "sum"))
               .reset_index())
    celula = config.TAMANHO_CELULA_CLIMA
    trechos["celula_lat"] = (trechos["lat"] / celula).round() * celula
    trechos["celula_lon"] = (trechos["lon"] / celula).round() * celula
    trechos["celula"] = trechos["celula_lat"].round(2).astype(str) + "," + trechos["celula_lon"].round(2).astype(str)
    return trechos
