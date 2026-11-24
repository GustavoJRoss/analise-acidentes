"""Critério 10 · Monitor de drift com alerta.

Problema real do projeto: trechos mudam de patamar de um ano para outro, e eventos como a pandemia mudam o
tráfego. O monitor compara o mês mais recente do ciclo com o MESMO mês dos anos de treino (referência sazonal,
para que mês/verão/temperatura não acusem drift só pela estação) e mede:
  * PSI (Population Stability Index) de cada feature;
  * razão entre a taxa de acidentes do mês e a da referência (mudança no próprio alvo).
Passando do limite, o workflow escreve no resumo da execução e abre uma issue no GitHub.
"""
import os
import subprocess

import numpy as np
import pandas as pd

from .preprocessamento import ALVO, CATEGORICAS

EPS = 1e-4
# constantes num mesmo mês do ano ou iguais por construção: não informam drift
IGNORAR = {"mes", "temporada_verao", "pandemia"}


def psi_numerica(ref: pd.Series, atual: pd.Series, bins: int = 10) -> float:
    ref, atual = ref.dropna(), atual.dropna()
    if ref.empty or atual.empty:
        return 0.0
    cortes = np.unique(np.quantile(ref, np.linspace(0, 1, bins + 1)))
    if len(cortes) < 3:  # quase constante: compara a fração em cada valor distinto
        return psi_categorica(ref.astype(str), atual.astype(str))
    cortes[0], cortes[-1] = -np.inf, np.inf
    e = np.histogram(ref, cortes)[0] / len(ref)
    a = np.histogram(atual, cortes)[0] / len(atual)
    return _psi(e, a)


def psi_categorica(ref: pd.Series, atual: pd.Series) -> float:
    cats = sorted(set(ref.astype(str)) | set(atual.astype(str)))
    e = ref.astype(str).value_counts(normalize=True).reindex(cats, fill_value=0).to_numpy()
    a = atual.astype(str).value_counts(normalize=True).reindex(cats, fill_value=0).to_numpy()
    return _psi(e, a)


def _psi(e, a) -> float:
    e, a = np.clip(e, EPS, None), np.clip(a, EPS, None)
    return float(np.sum((a - e) * np.log(a / e)))


def monitorar(referencia: pd.DataFrame, atual: pd.DataFrame, features: list[str], cfg: dict) -> dict:
    psi = {}
    for f in features:
        if f in IGNORAR:
            continue
        psi[f] = round(psi_categorica(referencia[f], atual[f]) if f in CATEGORICAS
                       else psi_numerica(referencia[f], atual[f]), 4)
    taxa_ref, taxa_atual = float(referencia[ALVO].mean()), float(atual[ALVO].mean())
    razao = taxa_atual / taxa_ref if taxa_ref > 0 else float("nan")
    lim = cfg["drift"]
    # clima e calendário de um mês variam naturalmente entre anos: são reportados, mas não disparam alerta
    sem_alerta = set(lim.get("ignorar_no_alerta", []))
    motivos = [f"PSI de {f} = {v:.3f} > {lim['psi_alerta']}" for f, v in psi.items()
               if v > lim["psi_alerta"] and f not in sem_alerta]
    if not (lim["razao_taxa_min"] <= razao <= lim["razao_taxa_max"]):
        motivos.append(f"taxa de acidentes {razao:.2f}× a do mesmo mês nos anos anteriores "
                       f"(fora de [{lim['razao_taxa_min']}, {lim['razao_taxa_max']}])")
    return {"psi": dict(sorted(psi.items(), key=lambda kv: -kv[1])), "psi_max": max(psi.values(), default=0.0),
            "taxa_referencia": round(taxa_ref, 5), "taxa_atual": round(taxa_atual, 5),
            "razao_taxa": round(razao, 3), "alerta": bool(motivos), "motivos": motivos,
            "linhas_referencia": len(referencia), "linhas_atual": len(atual)}


def recorte_mensal(base: pd.DataFrame, mes: pd.Timestamp, anos_ref: int = 3) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(referência, atual): o mês `mes` e o mesmo mês nos `anos_ref` anos anteriores."""
    atual = base[base["data"].dt.to_period("M") == mes.to_period("M")]
    meses_ref = [(mes - pd.DateOffset(years=i)).to_period("M") for i in range(1, anos_ref + 1)]
    referencia = base[base["data"].dt.to_period("M").isin(meses_ref)]
    return referencia, atual


def alertar(relatorio: dict, ciclo: dict, mes: str) -> str:
    """Resumo em Markdown; no GitHub Actions, vai para o resumo da execução e, se houver alerta, vira issue."""
    linhas = [f"## Monitor de drift · ciclo `{ciclo['cycle_id']}` · {mes}",
              f"- data_version: `{ciclo['data_version']}`",
              f"- PSI máximo: **{relatorio['psi_max']:.3f}**; taxa de acidentes {relatorio['razao_taxa']}× a referência",
              f"- Alerta: **{'SIM' if relatorio['alerta'] else 'não'}**"]
    linhas += [f"  - {m}" for m in relatorio["motivos"]]
    texto = "\n".join(linhas) + "\n"
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as f:
            f.write(texto)
    if relatorio["alerta"] and os.environ.get("GITHUB_ACTIONS") == "true":
        subprocess.run(["gh", "issue", "create", "--title", f"Drift detectado no ciclo {ciclo['cycle_id']} ({mes})",
                        "--body", texto], check=False)
    return texto
