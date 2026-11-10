"""Engenharia de features: ÚNICA fonte usada pelo treino e pela API.

Nada aqui usa colunas da PRF que só existem depois do acidente (clima/fase do dia/pista do CSV).
O clima vem do Open-Meteo, medido em todos os dias, com ou sem acidente.
"""
import pandas as pd

from . import config

FEATURES_CLIMA = ["chuva_mm", "nebulosidade", "temperatura"]
FEATURES_COMUNS = [
    "lat", "lon", "periodo_idx",
    "dia_semana", "mes", "fim_de_semana", "feriado", "vespera_ou_pos_feriado", "temporada_verao", "pandemia",
    *FEATURES_CLIMA,
    "taxa_historica", "taxa_historica_periodo", "acid_ult_365d",
]
# O que muda entre as redes é só como o trecho é descrito:
# br: km do trecho de 10 km, BR e delegacia da PRF · sc: comprimento da rodovia dentro do município e a rodovia.
# (o município não entra como categoria: são 295, acima do limite de 255 categorias do HistGradientBoosting)
FEATURES_CAT = {"br": ["br", "delegacia"], "sc": ["rodovia"]}
FEATURES = {
    # vmd: volume médio diário do DNIT (fixo por trecho; NaN onde não há segmento SNV)
    "br": ["trecho_km", *FEATURES_COMUNS, "vmd", *FEATURES_CAT["br"]],
    # nivel_notificacao: quanto o Detran está registrando no RENAEST (varia entre anos, ex.: queda em 2024)
    "sc": ["comprimento_km", *FEATURES_COMUNS, "nivel_notificacao", *FEATURES_CAT["sc"]],
}
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
    df["pandemia"] = data.between(*config.PANDEMIA).astype(int)    # menos tráfego em 2020–2021
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
    # janela de 1 ano: muda pouco entre o fim da base e uma data futura, que é como a API a usa
    diario["acid_ult_365d"] = g.transform(lambda s: s.shift(1).rolling(365, min_periods=1).sum()).fillna(0)
    base = base.merge(diario[["trecho_id", "data", "acid_acumulado", "acid_ult_365d"]], on=["trecho_id", "data"])

    base = base.sort_values(["trecho_id", "periodo", "data"])
    acum_periodo = (base.groupby(["trecho_id", "periodo"])["n_acidentes"]
                    .transform(lambda s: s.shift(1).cumsum()).fillna(0))
    dias = (base["data"] - inicio).dt.days.clip(lower=1)
    base["taxa_historica"] = base["acid_acumulado"] / dias
    base["taxa_historica_periodo"] = acum_periodo / dias
    return base.drop(columns=["acid_acumulado"]).sort_index()


def nivel_notificacao(datas_acidentes: pd.Series, inicio: pd.Timestamp, fim: pd.Timestamp) -> pd.DataFrame:
    """Acidentes registrados em SC (todas as vias) nos N dias ANTERIORES a cada data, ÷ a média do período.

    ~1 = notificação normal; 0,8 = o Detran registrou 20% menos que o habitual. Defasado: sem vazamento.
    """
    janela = config.JANELA_NOTIFICACAO_DIAS
    dias = pd.date_range(inicio - pd.Timedelta(days=janela), fim, freq="D")
    diario = datas_acidentes.dt.normalize().value_counts().reindex(dias, fill_value=0).sort_index()
    media = diario[inicio:fim].mean() * janela
    nivel = diario.shift(1).rolling(janela, min_periods=janela).sum() / media
    # o dia seguinte ao fim é o valor que a API usa para qualquer data futura
    nivel.loc[fim + pd.Timedelta(days=1)] = diario.iloc[-janela:].sum() / media
    return nivel[inicio:].rename("nivel_notificacao").rename_axis("data").reset_index()


def estado_atual_trechos(acidentes: pd.DataFrame, trechos: pd.DataFrame) -> pd.DataFrame:
    """Histórico de cada trecho no fim da base: é o que a API usa para qualquer data escolhida."""
    fim = acidentes["data"].max()
    total_dias = (fim - acidentes["data"].min()).days + 1
    estado = trechos.copy().set_index("trecho_id")
    estado["taxa_historica"] = acidentes.groupby("trecho_id").size() / total_dias
    recentes = acidentes[acidentes["data"] > fim - pd.Timedelta(days=365)]
    estado["acid_ult_365d"] = recentes.groupby("trecho_id").size()
    por_periodo = acidentes.groupby(["trecho_id", "periodo"]).size().unstack(fill_value=0) / total_dias
    for periodo in config.PERIODOS:
        estado[f"taxa_{periodo}"] = por_periodo.get(periodo, 0)
    return estado.fillna(0).reset_index()


def montar_linhas(estado: pd.DataFrame, data: pd.Timestamp, periodo: str, clima: dict,
                  climatologia: pd.DataFrame) -> pd.DataFrame:
    """Uma linha de features por trecho de `estado`, para um cenário (data, período, clima).

    clima: chuva_mm, nebulosidade e (opcional) temperatura. Sem temperatura,
    usa a média histórica da célula naquele mês e período.
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


def preparar_X(df: pd.DataFrame, categorias: dict, features: list) -> pd.DataFrame:
    """categorias: coluna categórica → lista de valores vistos no treino."""
    X = df[features].copy()
    for col in categorias:
        if col in X:
            X[col] = pd.Categorical(X[col].astype(str), categories=categorias[col])
    return X
