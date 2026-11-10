"""Treina o modelo trecho × dia × período de uma rede e salva os artefatos usados pela API.

Uso (dentro de backend/):
  python -m scripts.treinar             # rede "br" (PRF). Requer: python -m scripts.preparar_dados
  python -m scripts.treinar --rede sc   # rede "sc" (RENAEST). Requer: python -m scripts.preparar_estaduais
"""
import argparse
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

# Mais acidentes no passado do trecho => mais risco. O clima fica livre: nos dados da PRF a chuva
# forte coincide com MENOS acidentes (menos tráfego), e forçar o sinal esconderia isso.
MONOTONICAS = {"taxa_historica": 1, "taxa_historica_periodo": 1}


def montar_base(acidentes, trechos, clima_hist, notificacao=None):
    datas = pd.date_range(acidentes["data"].min().normalize(), acidentes["data"].max().normalize(), freq="D")
    grade = pd.MultiIndex.from_product([trechos["trecho_id"], datas, list(config.PERIODOS)],
                                       names=["trecho_id", "data", "periodo"]).to_frame(index=False)
    contagem = acidentes.groupby(["trecho_id", "data", "periodo"]).size().rename("n_acidentes")
    base = grade.merge(contagem, on=["trecho_id", "data", "periodo"], how="left").fillna({"n_acidentes": 0})
    base[ALVO] = (base["n_acidentes"] > 0).astype(int)
    base = adicionar_historico_treino(base)
    # no começo da base a taxa histórica tem denominador de poucos dias e é só ruído
    base = base[base["data"] >= datas[0] + pd.Timedelta(days=config.DIAS_AQUECIMENTO)]
    base = base.merge(trechos, on="trecho_id")
    base = base.merge(clima_hist, on=["celula", "data", "periodo"], how="left")
    base = clima.preencher_com_climatologia(base, clima_hist)
    if notificacao is not None:
        base = base.merge(notificacao, on="data", how="left")
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


def main(rede: str):
    artefatos = config.REDES[rede]
    features, corte = FEATURES[rede], config.CORTE_TESTE[rede]
    acidentes = pd.read_parquet(artefatos.acidentes)
    clima_hist = pd.read_parquet(artefatos.clima)
    # trechos.parquet inclui os trechos sem acidente; sem ele (preparação antiga), só os que tiveram acidente
    trechos = pd.read_parquet(artefatos.trechos) if artefatos.trechos.exists() else dados.resumo_trechos(acidentes)
    categorias = {c: sorted(trechos[c].astype(str).unique()) for c in FEATURES_CAT[rede]}
    notificacao = pd.read_parquet(artefatos.notificacao) if "nivel_notificacao" in features else None

    print(f"[{rede}] Montando base trecho × dia × período…")
    base = montar_base(acidentes, trechos, clima_hist, notificacao)
    treino, teste = base[base["data"] < corte], base[base["data"] >= corte]
    print(f"  {len(base):,} linhas | treino {len(treino):,} ({treino[ALVO].mean():.2%} positivos)"
          f" | teste {len(teste):,} ({teste[ALVO].mean():.2%})")

    variantes = {"com_clima": features, "sem_clima": [f for f in features if f not in FEATURES_CLIMA]}
    metricas = {"taxa_base_teste": round(float(teste[ALVO].mean()), 4), "modelos": {}}
    modelos_teste, probs_teste = {}, {}
    for nome, feats in variantes.items():
        m = novo_modelo(feats).fit(preparar_X(treino, categorias, feats), treino[ALVO])
        p = m.predict_proba(preparar_X(teste, categorias, feats))[:, 1]
        metricas["modelos"][nome] = avaliar(teste[ALVO], p)
        modelos_teste[nome], probs_teste[nome] = m, p
    metricas["modelos"]["ingenuo_taxa_periodo"] = avaliar(teste[ALVO], teste["taxa_historica_periodo"].clip(0, 1))
    for nome, m in metricas["modelos"].items():
        print(f"  {nome:22s} {m}")

    # o clima ajuda em alguma situação específica? (PR-AUC com × sem clima em subconjuntos do teste)
    subconjuntos = {"noite": teste["periodo"] == "noite", "verao": teste["temporada_verao"] == 1,
                    "chuva": teste["chuva_mm"] >= config.LIMIAR_CHUVA_MM,
                    "chuva_forte": teste["chuva_mm"] >= config.LIMIAR_CHUVA_FORTE_MM}
    metricas["clima_por_subconjunto"] = {}
    for nome, filtro in subconjuntos.items():
        filtro = filtro.to_numpy()
        y = teste[ALVO].to_numpy()[filtro]
        if y.sum() < 30:
            continue
        metricas["clima_por_subconjunto"][nome] = {
            "linhas": int(filtro.sum()), "taxa_base": round(float(y.mean()), 4),
            **{f"pr_auc_{v}": round(average_precision_score(y, probs_teste[v][filtro]), 4) for v in variantes}}
    print("  clima por subconjunto:", metricas["clima_por_subconjunto"])

    print("Importância por permutação (teste)…")
    amostra = teste.sample(60_000, random_state=42)
    imp = permutation_importance(modelos_teste["com_clima"], preparar_X(amostra, categorias, features), amostra[ALVO],
                                 scoring="average_precision", n_repeats=5, random_state=42, n_jobs=-1)
    metricas["importancia"] = (pd.Series(imp.importances_mean, index=features)
                               .sort_values(ascending=False).round(5).to_dict())

    presets = clima.presets_do_historico(clima_hist)

    # efeito médio de cada categoria de clima no teste (mesmos trechos/dias, só o clima muda)
    efeito = {}
    for nome, valores in presets.items():
        cenario = amostra.copy()
        for chave in ["chuva_mm", "nebulosidade"]:
            cenario[chave] = valores[chave]
        prob = modelos_teste["com_clima"].predict_proba(preparar_X(cenario, categorias, features))[:, 1]
        efeito[nome] = round(float(prob.mean()), 5)
    metricas["efeito_clima_prob_media"] = efeito
    print("  efeito do clima:", efeito)

    print("Retreinando com todo o período para a API…")
    final = novo_modelo(features).fit(preparar_X(base, categorias, features), base[ALVO])
    joblib.dump({"modelo": final, "features": features, "categorias": categorias, "rede": rede}, artefatos.modelo)

    estado = estado_atual_trechos(acidentes, trechos)
    if notificacao is not None:
        estado["nivel_notificacao"] = float(notificacao["nivel_notificacao"].iat[-1])
    estado.to_parquet(artefatos.estado)
    clima.climatologia(clima_hist)[["celula", "mes", "periodo", "temperatura"]].to_parquet(artefatos.climatologia)
    artefatos.presets_clima.write_text(json.dumps(presets, ensure_ascii=False, indent=2))

    metricas.update({"rede": rede, "linhas_base": len(base), "trechos": len(trechos),
                     "periodo_dados": [str(acidentes["data"].min().date()), str(acidentes["data"].max().date())],
                     "inicio_treino": str(base["data"].min().date()),
                     "corte_teste": str(corte.date())})
    artefatos.metricas.write_text(json.dumps(metricas, ensure_ascii=False, indent=2))
    print("Artefatos salvos em", artefatos.pasta)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--rede", choices=list(config.REDES), default="br")
    np.random.seed(42)
    main(parser.parse_args().rede)
