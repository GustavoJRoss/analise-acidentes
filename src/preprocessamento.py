"""ETL do ciclo: diagnóstico e tratamento dos acidentes, base trecho × dia × período e divisão temporal.

A montagem da base e as features vêm de backend/ (as mesmas usadas pela API), sem cópia.
"""
import pandas as pd

from . import comum  # noqa: F401  (coloca backend/ no sys.path)
from app import config  # noqa: E402
from app.features import ALVO, FEATURES, FEATURES_CAT  # noqa: E402
from scripts.treinar import montar_base  # noqa: E402

REDE = "br"
CANDIDATAS = FEATURES[REDE]
CATEGORICAS = FEATURES_CAT[REDE]
NUMERICAS = [f for f in CANDIDATAS if f not in CATEGORICAS]


def diagnostico_bruto(pessoas: pd.DataFrame) -> dict:
    """Problemas nas linhas brutas da PRF (uma por pessoa, como vêm do CSV), antes da limpeza."""
    num = lambda c: pd.to_numeric(pessoas[c].astype(str).str.replace(",", ".", regex=False), errors="coerce")
    lat_, lon_ = num("latitude"), num("longitude")
    lat, lon = config.BBOX_SC["lat"], config.BBOX_SC["lon"]
    data = pd.to_datetime(pessoas["data_inversa"], format="%Y-%m-%d", errors="coerce")
    data = data.fillna(pd.to_datetime(pessoas["data_inversa"], format="%d/%m/%Y", errors="coerce"))
    sem_local = lat_.isna() | lon_.isna() | num("br").isna() | num("km").isna()
    fora = ~sem_local & ~(lat_.between(*lat) & lon_.between(*lon))
    return {
        "linhas (pessoas)": int(len(pessoas)),
        "acidentes distintos": int(pessoas["id"].nunique()),
        "pessoas por acidente (média)": round(len(pessoas) / max(pessoas["id"].nunique(), 1), 2),
        "linhas repetidas (id + pesid)": int(pessoas.duplicated(["id", "pesid"]).sum()),
        "acidentes sem br/km/coordenada": int(pessoas.loc[sem_local, "id"].nunique()),
        "acidentes com coordenada fora de SC": int(pessoas.loc[fora, "id"].nunique()),
        "datas em formato inválido": int(data.isna().sum()),
        "horário ausente": int(pessoas["horario"].isna().sum()),
        "tipo de acidente ausente": int(pessoas["tipo_acidente"].isna().sum()),
    }


def diagnostico(acidentes: pd.DataFrame, trechos: pd.DataFrame) -> dict:
    """Problemas de qualidade nos acidentes: ausentes, duplicatas, inconsistências e outliers."""
    lat, lon = config.BBOX_SC["lat"], config.BBOX_SC["lon"]
    vitimas = acidentes[["ilesos", "feridos_leves", "feridos_graves", "mortos"]]
    return {
        "linhas": int(len(acidentes)),
        "ausentes": {c: int(n) for c, n in acidentes.isna().sum().items() if n > 0},
        "ids_duplicados": int(acidentes["id"].duplicated().sum()),
        "coordenada_fora_de_sc": int((~acidentes["latitude"].between(*lat) | ~acidentes["longitude"].between(*lon)).sum()),
        "km_negativo": int((acidentes["km"] < 0).sum()),
        "trecho_desconhecido": int((~acidentes["trecho_id"].isin(trechos["trecho_id"])).sum()),
        "periodo_invalido": int((~acidentes["periodo"].isin(list(config.PERIODOS))).sum()),
        "vitimas_negativas": int((vitimas < 0).any(axis=1).sum()),
        # outlier: mais de 10 mortos num acidente (possível, mas raro; só sinalizado, não removido)
        "outlier_mortos_gt_10": int((acidentes["mortos"] > 10).sum()),
        "periodo_dados": [str(acidentes["data"].min().date()), str(acidentes["data"].max().date())],
    }


def tratar(acidentes: pd.DataFrame, trechos: pd.DataFrame, fim: pd.Timestamp) -> pd.DataFrame:
    """Remove o que não pode entrar na base: duplicatas, coordenadas fora de SC, trecho desconhecido, datas além
    do fim do ciclo. Ausentes nas colunas de vítimas viram 0 (a PRF deixa vazio quando não há)."""
    lat, lon = config.BBOX_SC["lat"], config.BBOX_SC["lon"]
    ok = (acidentes["latitude"].between(*lat) & acidentes["longitude"].between(*lon)
          & acidentes["trecho_id"].isin(trechos["trecho_id"]) & (acidentes["km"] >= 0)
          & acidentes["periodo"].isin(list(config.PERIODOS)) & (acidentes["data"] <= fim))
    limpo = acidentes[ok].drop_duplicates("id").copy()
    colunas_vitimas = ["ilesos", "feridos_leves", "feridos_graves", "mortos"]
    limpo[colunas_vitimas] = limpo[colunas_vitimas].fillna(0)
    return limpo.reset_index(drop=True)


def montar(acidentes: pd.DataFrame, trechos: pd.DataFrame, clima: pd.DataFrame) -> pd.DataFrame:
    """Base trecho × dia × período com alvo e features (histórico do trecho só até o dia anterior)."""
    base = montar_base(acidentes, trechos, clima)
    return base[["trecho_id", "data", "periodo", ALVO, *CANDIDATAS]].reset_index(drop=True)


def dividir(base: pd.DataFrame, fim: pd.Timestamp, meses_validacao: int) -> tuple[pd.DataFrame, pd.DataFrame, pd.Timestamp]:
    """Divisão temporal: validação = últimos `meses_validacao` meses até `fim`; treino = tudo antes."""
    inicio_val = (fim + pd.Timedelta(days=1)) - pd.DateOffset(months=meses_validacao)
    treino = base[base["data"] < inicio_val]
    validacao = base[(base["data"] >= inicio_val) & (base["data"] <= fim)]
    return treino, validacao, inicio_val
