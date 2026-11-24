"""Três métodos de seleção de features e a votação que elege o conjunto do ciclo.

Tudo é ajustado SÓ com o treino do ciclo (uma amostra estratificada, para caber no runner do GitHub). Cada método
produz um ranking completo (1 = melhor) e vota nas suas k melhores features.
"""
from functools import partial

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_selection import RFE, SelectKBest, mutual_info_classif
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import OrdinalEncoder, StandardScaler, TargetEncoder

from .preprocessamento import ALVO, CATEGORICAS

# features naturalmente discretas: o estimador de informação mútua as trata como categorias
DISCRETAS = {"periodo_idx", "dia_semana", "mes", "fim_de_semana", "feriado", "vespera_ou_pos_feriado",
             "temporada_verao", "pandemia", "trecho_km", *CATEGORICAS}


def amostrar(treino: pd.DataFrame, n: int, seed: int) -> pd.DataFrame:
    if len(treino) <= n:
        return treino
    amostra, _ = train_test_split(treino, train_size=n, stratify=treino[ALVO], random_state=seed)
    return amostra


def _matriz_ordinal(df: pd.DataFrame, candidatas: list[str]) -> pd.DataFrame:
    """Categóricas → códigos inteiros; ausentes numéricos → mediana. Só para os métodos 1 e 2."""
    X = df[candidatas].copy()
    cats = [c for c in candidatas if c in CATEGORICAS]
    if cats:
        X[cats] = OrdinalEncoder().fit_transform(X[cats].astype(str))
    return X.fillna(X.median(numeric_only=True))


def _tabela(features, score, ranking, k) -> pd.DataFrame:
    t = pd.DataFrame({"score": score, "ranking": ranking}, index=pd.Index(features, name="feature"))
    t["voto"] = (t["ranking"] <= k).astype(int)
    return t.sort_values("ranking")


def metodo_selectkbest(df, candidatas, k, seed) -> pd.DataFrame:
    """SelectKBest com informação mútua: mede dependência (inclusive não linear) entre a feature e o alvo."""
    X = _matriz_ordinal(df, candidatas)
    discretas = np.array([c in DISCRETAS for c in candidatas])
    score_fn = partial(mutual_info_classif, discrete_features=discretas, random_state=seed)
    sel = SelectKBest(score_fn, k=min(k, len(candidatas))).fit(X, df[ALVO])
    ranking = pd.Series(sel.scores_).rank(ascending=False, method="first").astype(int).to_numpy()
    return _tabela(candidatas, sel.scores_, ranking, k)


def metodo_random_forest(df, candidatas, k, seed) -> pd.DataFrame:
    """Importância por redução de impureza de uma Random Forest (com classes balanceadas)."""
    X = _matriz_ordinal(df, candidatas)
    rf = RandomForestClassifier(n_estimators=200, max_depth=12, min_samples_leaf=50, class_weight="balanced",
                                n_jobs=-1, random_state=seed).fit(X, df[ALVO])
    ranking = pd.Series(rf.feature_importances_).rank(ascending=False, method="first").astype(int).to_numpy()
    return _tabela(candidatas, rf.feature_importances_, ranking, k)


def metodo_rfe(df, candidatas, k, seed) -> pd.DataFrame:
    """RFE com Regressão Logística: elimina, uma a uma, a feature de menor |coeficiente| até sobrar uma.

    A ordem de eliminação dá o ranking completo. Categóricas viram UMA coluna cada (TargetEncoder com validação
    cruzada interna, sem vazamento), para o ranking continuar sendo por feature original.
    """
    X = df[candidatas].copy()
    cats = [c for c in candidatas if c in CATEGORICAS]
    if cats:
        X[cats] = TargetEncoder(random_state=seed).fit_transform(X[cats].astype(str), df[ALVO])
    X = StandardScaler().fit_transform(X.fillna(X.median(numeric_only=True)))
    rfe = RFE(LogisticRegression(class_weight="balanced", max_iter=1000), n_features_to_select=1, step=1)
    rfe.fit(X, df[ALVO])
    # score: em que rodada a feature saiu (maior = sobreviveu mais tempo)
    return _tabela(candidatas, len(candidatas) + 1 - rfe.ranking_, rfe.ranking_, k)


METODOS = {"selectkbest_mi": metodo_selectkbest, "random_forest": metodo_random_forest, "rfe_logistica": metodo_rfe}


def votar(tabelas: dict[str, pd.DataFrame], min_votos: int, min_features: int) -> pd.DataFrame:
    """Regra fixada antes: eleita com ≥ min_votos; se faltarem features, completa pela menor média de ranking
    (que também é o critério de desempate e de ordenação)."""
    votos = pd.DataFrame({f"voto_{m}": t["voto"] for m, t in tabelas.items()})
    rankings = pd.DataFrame({f"rank_{m}": t["ranking"] for m, t in tabelas.items()})
    tab = votos.join(rankings)
    tab["votos"] = votos.sum(axis=1)
    tab["media_ranking"] = rankings.mean(axis=1).round(2)
    tab = tab.sort_values(["votos", "media_ranking"], ascending=[False, True])
    tab["eleita"] = tab["votos"] >= min_votos
    tab["motivo"] = np.where(tab["eleita"], f"≥ {min_votos} votos", "")
    faltam = min_features - int(tab["eleita"].sum())
    if faltam > 0:
        completar = tab[~tab["eleita"]].sort_values("media_ranking").index[:faltam]
        tab.loc[completar, "eleita"] = True
        tab.loc[completar, "motivo"] = "completada pela média de ranking"
    return tab.rename_axis("feature")
