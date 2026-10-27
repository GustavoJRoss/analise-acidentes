"""Treina o modelo trecho × dia × período e salva os artefatos usados pela API.

Uso (dentro de backend/):  python -m scripts.treinar
Requer ter rodado antes: python -m scripts.preparar_dados
"""
import json

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.inspection import permutation_importance
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score

from app import clima, config, dados
from app.features import (ALVO, FEATURES, FEATURES_CAT, FEATURES_CLIMA, adicionar_calendario,
                          adicionar_historico_treino, estado_atual_trechos, preparar_X)

# Mais acidentes no passado do trecho => mais risco. O clima fica livre: nos dados de 2025 a chuva
# forte coincide com MENOS acidentes (menos tráfego), e forçar o sinal esconderia isso.
MONOTONICAS = {"taxa_historica": 1, "taxa_historica_periodo": 1}


def montar_base(acidentes, trechos, clima_hist):
    datas = pd.date_range(acidentes["data"].min(), acidentes["data"].max(), freq="D")
    grade = pd.MultiIndex.from_product([trechos["trecho_id"], datas, list(config.PERIODOS)],
                                       names=["trecho_id", "data", "periodo"]).to_frame(index=False)
    contagem = acidentes.groupby(["trecho_id", "data", "periodo"]).size().rename("n_acidentes")
    base = grade.merge(contagem, on=["trecho_id", "data", "periodo"], how="left").fillna({"n_acidentes": 0})
    base[ALVO] = (base["n_acidentes"] > 0).astype(int)
    base = adicionar_historico_treino(base)
    base = base.merge(trechos, on="trecho_id")
    base = base.merge(clima_hist, on=["celula", "data", "periodo"], how="left")
    base[FEATURES_CLIMA] = base[FEATURES_CLIMA].fillna(0)
    return adicionar_calendario(base)


def novo_modelo(features):
    return HistGradientBoostingClassifier(
        learning_rate=0.05, max_iter=500, max_leaf_nodes=31, min_samples_leaf=200,
        l2_regularization=1.0, categorical_features="from_dtype",
        monotonic_cst={f: s for f, s in MONOTONICAS.items() if f in features},
        early_stopping=True, validation_fraction=0.15, random_state=42)


def avaliar(y, p):
    return {"roc_auc": round(roc_auc_score(y, p), 4), "pr_auc": round(average_precision_score(y, p), 4),
            "brier": round(brier_score_loss(y, p), 5)}


def main():
    acidentes = pd.read_parquet(config.ARQ_ACIDENTES)
    clima_hist = pd.read_parquet(config.ARQ_CLIMA)
    trechos = dados.resumo_trechos(acidentes)
    categorias = {c: sorted(trechos[c].astype(str).unique()) for c in FEATURES_CAT}

    print("Montando base trecho × dia × período…")
    base = montar_base(acidentes, trechos, clima_hist)
    treino, teste = base[base["data"] < config.CORTE_TESTE], base[base["data"] >= config.CORTE_TESTE]
    print(f"  {len(base):,} linhas | treino {len(treino):,} ({treino[ALVO].mean():.2%} positivos)"
          f" | teste {len(teste):,} ({teste[ALVO].mean():.2%})")

    variantes = {"com_clima": FEATURES, "sem_clima": [f for f in FEATURES if f not in FEATURES_CLIMA]}
    metricas = {"taxa_base_teste": round(float(teste[ALVO].mean()), 4), "modelos": {}}
    modelos_teste = {}
    for nome, feats in variantes.items():
        m = novo_modelo(feats).fit(preparar_X(treino, categorias, feats), treino[ALVO])
        p = m.predict_proba(preparar_X(teste, categorias, feats))[:, 1]
        metricas["modelos"][nome] = avaliar(teste[ALVO], p)
        modelos_teste[nome] = m
    metricas["modelos"]["ingenuo_taxa_periodo"] = avaliar(teste[ALVO], teste["taxa_historica_periodo"].clip(0, 1))
    for nome, m in metricas["modelos"].items():
        print(f"  {nome:22s} {m}")

    print("Importância por permutação (teste)…")
    amostra = teste.sample(60_000, random_state=42)
    imp = permutation_importance(modelos_teste["com_clima"], preparar_X(amostra, categorias), amostra[ALVO],
                                 scoring="average_precision", n_repeats=5, random_state=42, n_jobs=-1)
    metricas["importancia"] = (pd.Series(imp.importances_mean, index=FEATURES)
                               .sort_values(ascending=False).round(5).to_dict())

    presets = clima.presets_do_historico(clima_hist)

    # efeito médio de cada categoria de clima no teste (mesmos trechos/dias, só o clima muda)
    efeito = {}
    for nome, valores in presets.items():
        cenario = amostra.copy()
        for chave in ["chuva_mm", "nebulosidade"]:
            cenario[chave] = valores[chave]
        efeito[nome] = round(float(modelos_teste["com_clima"].predict_proba(preparar_X(cenario, categorias))[:, 1].mean()), 5)
    metricas["efeito_clima_prob_media"] = efeito
    print("  efeito do clima:", efeito)

    print("Retreinando com o ano completo para a API…")
    final = novo_modelo(FEATURES).fit(preparar_X(base, categorias), base[ALVO])
    joblib.dump({"modelo": final, "features": FEATURES, "categorias": categorias}, config.ARQ_MODELO)

    estado_atual_trechos(acidentes, trechos).to_parquet(config.ARQ_ESTADO)
    climatologia = (clima_hist.assign(mes=clima_hist["data"].dt.month)
                    .groupby(["celula", "mes", "periodo"])["temperatura"].mean().reset_index())
    climatologia.to_parquet(config.ARQ_CLIMATOLOGIA)
    config.ARQ_PRESETS_CLIMA.write_text(json.dumps(presets, ensure_ascii=False, indent=2))

    metricas.update({"linhas_base": len(base), "trechos": len(trechos),
                     "periodo_dados": [str(base["data"].min().date()), str(base["data"].max().date())],
                     "corte_teste": str(config.CORTE_TESTE.date())})
    config.ARQ_METRICAS.write_text(json.dumps(metricas, ensure_ascii=False, indent=2))
    print("Artefatos salvos em", config.ARTIFACTS)


if __name__ == "__main__":
    np.random.seed(42)
    main()
