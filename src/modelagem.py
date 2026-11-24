"""Os dois algoritmos que disputam o ciclo, com o MESMO pré-processamento de entrada e as MESMAS features eleitas.

Cada modelo é um Pipeline completo (pré-processamento + estimador): o objeto serializado já carrega as
transformações e a lista de features, e prevê a partir das colunas brutas da base.
"""
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline, make_pipeline
from sklearn.preprocessing import OneHotEncoder, OrdinalEncoder, StandardScaler

from .preprocessamento import ALVO, CATEGORICAS
from scripts.treinar import MONOTONICAS, avaliar, calibracao, captura_top_k  # noqa: E402

NOMES = {"logistica": "Regressão Logística", "hist_gradient_boosting": "HistGradientBoosting"}


def _separar(features):
    return [f for f in features if f in CATEGORICAS], [f for f in features if f not in CATEGORICAS]


def modelo_logistica(features: list[str], seed: int) -> Pipeline:
    """Sem class_weight="balanced": ele infla as probabilidades (~18× a taxa real) e o modelo nunca passaria na
    checagem de calibração. A ordenação (PR-AUC) praticamente não muda."""
    cats, nums = _separar(features)
    prep = ColumnTransformer([
        ("num", make_pipeline(SimpleImputer(strategy="median"), StandardScaler()), nums),
        ("cat", OneHotEncoder(handle_unknown="ignore"), cats),
    ])
    return Pipeline([("prep", prep),
                     ("modelo", LogisticRegression(max_iter=1000, random_state=seed))])


def modelo_hgb(features: list[str], seed: int) -> Pipeline:
    """Mesmos hiperparâmetros do modelo em produção (backend/scripts/treinar.py), restrição monotônica incluída."""
    cats, nums = _separar(features)
    prep = ColumnTransformer([
        ("cat", OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=np.nan,
                               encoded_missing_value=np.nan), cats),
        ("num", "passthrough", nums),
    ], verbose_feature_names_out=False).set_output(transform="pandas")
    hgb = HistGradientBoostingClassifier(
        learning_rate=0.05, max_iter=500, max_leaf_nodes=31, min_samples_leaf=200, l2_regularization=1.0,
        categorical_features=cats or None,
        monotonic_cst={f: s for f, s in MONOTONICAS.items() if f in nums} or None,
        early_stopping=True, validation_fraction=0.15, random_state=seed)
    return Pipeline([("prep", prep), ("modelo", hgb)])


CONSTRUTORES = {"logistica": modelo_logistica, "hist_gradient_boosting": modelo_hgb}


def preparar_entrada(df: pd.DataFrame, features: list[str]) -> pd.DataFrame:
    X = df[features].copy()
    for c in X.columns.intersection(CATEGORICAS):
        X[c] = X[c].astype(str)
    return X


def treinar(algoritmo: str, treino: pd.DataFrame, features: list[str], seed: int) -> Pipeline:
    return CONSTRUTORES[algoritmo](features, seed).fit(preparar_entrada(treino, features), treino[ALVO])


def prever(modelo: Pipeline, df: pd.DataFrame, features: list[str]) -> np.ndarray:
    return modelo.predict_proba(preparar_entrada(df, features))[:, 1]


def metricas(y, p) -> dict:
    """Métrica principal (pr_auc) + ROC-AUC, Brier, calibração e captura top-k. Mesmo protocolo para todos."""
    cal = calibracao(y, p)
    top = captura_top_k(y, p)
    return {**avaliar(y, p), "razao_prevista_observada": cal["razao_prevista_observada"],
            "captura_top_10pct": top["top_10pct"], "captura_top_5pct": top["top_5pct"]}
