"""Engenharia de features: ÚNICA fonte usada pelo treino e pela API.

Nada aqui usa colunas da PRF que só existem depois do acidente (clima/fase do dia/pista do CSV).
O clima vem do Open-Meteo, medido em todos os dias, com ou sem acidente.
"""
import pandas as pd

from . import config

FEATURES_CLIMA = ["chuva_mm", "nebulosidade", "temperatura"]
FEATURES_NUM = [
    "trecho_km", "lat", "lon", "periodo_idx",
    "dia_semana", "mes", "fim_de_semana", "feriado", "vespera_ou_pos_feriado", "temporada_verao",
    *FEATURES_CLIMA,
    "taxa_historica", "taxa_historica_periodo", "acid_ult_90d",
]
FEATURES_CAT = ["br", "delegacia"]
FEATURES = FEATURES_NUM + FEATURES_CAT
ALVO = "teve_acidente"


def adicionar_calendario(df: pd.DataFrame) -> pd.DataFrame:
    data = df["data"]
    df["dia_semana"] = data.dt.day_of_week
    df["mes"] = data.dt.month
    df["fim_de_semana"] = (df["dia_semana"] >= 5).astype(int)
    df["feriado"] = data.isin(config.FERIADOS).astype(int)
    vizinhos = config.FERIADOS - pd.Timedelta(days=1)
    vizinhos = vizinhos.append(config.FERIADOS + pd.Timedelta(days=1))
    df["vespera_ou_pos_feriado"] = (data.isin(vizinhos) & (df["feriado"] == 0)).astype(int)
    df["temporada_verao"] = df["mes"].isin([12, 1, 2]).astype(int)  # litoral catarinense
    df["periodo_idx"] = df["periodo"].map(config.PERIODO_IDX)
    return df


def adicionar_historico_treino(base: pd.DataFrame) -> pd.DataFrame:
    """Histórico do trecho até o dia ANTERIOR (sem vazamento). base: trecho_id, data, periodo, n_acidentes."""
    inicio = base["data"].min()
    dias = (base["data"] - inicio).dt.days.clip(lower=1)

    diario = (base.groupby(["trecho_id", "data"])["n_acidentes"].sum()
              .rename("n_dia").reset_index().sort_values(["trecho_id", "data"]))
    g = diario.groupby("trecho_id")["n_dia"]
    diario["acid_acumulado"] = g.transform(lambda s: s.shift(1).cumsum()).fillna(0)
    diario["acid_ult_90d"] = g.transform(lambda s: s.shift(1).rolling(90, min_periods=1).sum()).fillna(0)
    base = base.merge(diario[["trecho_id", "data", "acid_acumulado", "acid_ult_90d"]], on=["trecho_id", "data"])

    base = base.sort_values(["trecho_id", "periodo", "data"])
    acum_periodo = (base.groupby(["trecho_id", "periodo"])["n_acidentes"]
                    .transform(lambda s: s.shift(1).cumsum()).fillna(0))
    dias = (base["data"] - inicio).dt.days.clip(lower=1)
    base["taxa_historica"] = base["acid_acumulado"] / dias
    base["taxa_historica_periodo"] = acum_periodo / dias
    return base.drop(columns=["acid_acumulado"]).sort_index()


def estado_atual_trechos(acidentes: pd.DataFrame, trechos: pd.DataFrame) -> pd.DataFrame:
    """Histórico de cada trecho no fim da base: é o que a API usa para qualquer data escolhida."""
    fim = acidentes["data"].max()
    total_dias = (fim - acidentes["data"].min()).days + 1
    estado = trechos.copy().set_index("trecho_id")
    estado["taxa_historica"] = acidentes.groupby("trecho_id").size() / total_dias
    recentes = acidentes[acidentes["data"] > fim - pd.Timedelta(days=90)]
    estado["acid_ult_90d"] = recentes.groupby("trecho_id").size()
    por_periodo = acidentes.groupby(["trecho_id", "periodo"]).size().unstack(fill_value=0) / total_dias
    for periodo in config.PERIODOS:
        estado[f"taxa_{periodo}"] = por_periodo.get(periodo, 0)
    return estado.fillna(0).reset_index()


def montar_linhas(estado: pd.DataFrame, data: pd.Timestamp, periodo: str, clima: dict,
                  climatologia: pd.DataFrame) -> pd.DataFrame:
    """Uma linha de features por trecho de `estado`, para um cenário (data, período, clima).

    clima: chuva_mm, nebulosidade e (opcional) temperatura. Sem temperatura,
    usa a média de 2025 da célula naquele mês e período.
    """
    df = estado.copy()
    df["data"] = pd.Timestamp(data).normalize()
    df["periodo"] = periodo
    df = adicionar_calendario(df)
    df["taxa_historica_periodo"] = df[f"taxa_{periodo}"]
    for chave in ["chuva_mm", "nebulosidade"]:
        df[chave] = clima[chave]
    if clima.get("temperatura") is not None:
        df["temperatura"] = clima["temperatura"]
    else:
        temp = climatologia[(climatologia["mes"] == df["mes"].iat[0]) & (climatologia["periodo"] == periodo)]
        df = df.merge(temp[["celula", "temperatura"]], on="celula", how="left")
        df["temperatura"] = df["temperatura"].fillna(climatologia["temperatura"].mean())
    return df


def preparar_X(df: pd.DataFrame, categorias: dict, features=FEATURES) -> pd.DataFrame:
    X = df[features].copy()
    for col in FEATURES_CAT:
        if col in X:
            X[col] = pd.Categorical(X[col].astype(str), categories=categorias[col])
    return X
