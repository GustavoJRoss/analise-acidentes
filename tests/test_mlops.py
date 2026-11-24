"""Regras do pipeline MLOps: são as decisões automáticas que o professor precisa poder auditar.

Rodar da raiz:  .venv/bin/python3.12 -m pytest tests -q
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import drift, ingestao, promocao  # noqa: E402
from src.comum import carregar_config  # noqa: E402
from src.features import votar  # noqa: E402

CFG = carregar_config()


# --- votação ------------------------------------------------------------------------------------------------

def _tabela(rankings: dict, k: int) -> pd.DataFrame:
    t = pd.DataFrame({"ranking": rankings}).rename_axis("feature")
    t["voto"] = (t["ranking"] <= k).astype(int)
    return t


def test_votacao_elege_quem_tem_dois_votos():
    tabs = {"m1": _tabela({"a": 1, "b": 2, "c": 3, "d": 4}, k=2),
            "m2": _tabela({"a": 1, "c": 2, "b": 3, "d": 4}, k=2),
            "m3": _tabela({"b": 1, "d": 2, "a": 3, "c": 4}, k=2)}
    v = votar(tabs, min_votos=2, min_features=1)
    assert set(v.index[v["eleita"]]) == {"a", "b"}          # a: m1+m2, b: m1+m3; c e d só um voto
    assert v.loc["a", "votos"] == 2 and v.loc["d", "votos"] == 1


def test_votacao_completa_pela_media_de_ranking():
    tabs = {"m1": _tabela({"a": 1, "b": 2, "c": 3}, k=1),
            "m2": _tabela({"b": 1, "c": 2, "a": 3}, k=1),
            "m3": _tabela({"c": 1, "a": 2, "b": 3}, k=1)}
    v = votar(tabs, min_votos=2, min_features=2)            # ninguém tem 2 votos
    eleitas = v[v["eleita"]]
    assert len(eleitas) == 2
    assert (eleitas["motivo"] == "completada pela média de ranking").all()


# --- promoção ------------------------------------------------------------------------------------------------

def _m(pr, roc=0.8, cal=1.0):
    return {"pr_auc": pr, "roc_auc": roc, "razao_prevista_observada": cal}


def test_primeiro_ciclo_promove_o_melhor_candidato():
    d = promocao.decidir({"a": _m(0.10), "b": _m(0.12)}, None, CFG)
    assert d["decisao"] == "promovido" and d["vencedor_ciclo"] == "b"


def test_promove_so_acima_do_limiar():
    limiar = CFG["promocao"]["limiar_melhoria"]
    vigente = _m(0.130)
    assert promocao.decidir({"b": _m(0.130 + limiar / 2)}, vigente, CFG)["decisao"] == "mantido"
    assert promocao.decidir({"b": _m(0.130 + limiar * 1.5)}, vigente, CFG)["decisao"] == "promovido"


def test_mantem_vigente_se_vencedor_reprovado_na_qualidade():
    d = promocao.decidir({"b": _m(0.20, cal=3.0)}, _m(0.13), CFG)   # muito melhor, mas descalibrado
    assert d["decisao"] == "mantido" and d["falhas_qualidade"]


# --- ingestão ------------------------------------------------------------------------------------------------

def test_lotes_um_por_ciclo_e_primeiro_ciclo_so_base():
    disp = ["2024-01", "2024-02", "2024-03"]
    assert ingestao.proximos_lotes(disp, [], primeiro_ciclo=True, n=1) == []
    assert ingestao.proximos_lotes(disp, [], primeiro_ciclo=False, n=1) == ["2024-01"]
    assert ingestao.proximos_lotes(disp, ["2024-01"], primeiro_ciclo=False, n=1) == ["2024-02"]
    assert ingestao.proximos_lotes(disp, disp, primeiro_ciclo=False, n=1) == []      # acabou: reusa os dados


def test_uniao_sem_duplicar_e_versao_deterministica():
    # linhas brutas: uma por pessoa; a mesma pessoa do mesmo acidente reenviada num lote é duplicata
    a = pd.DataFrame({"id": ["1", "1", "2", "3"], "pesid": ["10", "11", "20", "30"]})
    b = pd.DataFrame({"id": ["3", "4"], "pesid": ["30", "40"]})
    dados, dup = ingestao.unir_sem_duplicar([a, b])
    assert dup == 1 and len(dados) == 5 and sorted(dados["id"].unique()) == ["1", "2", "3", "4"]
    v1 = ingestao.versao_dos_dados(dados["id"], "2024-01")
    v2 = ingestao.versao_dos_dados(dados["id"].sample(frac=1, random_state=0), "2024-01")
    assert v1 == v2 and v1.startswith("v2024-01-")
    assert ingestao.versao_dos_dados(dados["id"].iloc[:3], "2024-01") != v1


# --- drift ---------------------------------------------------------------------------------------------------

def test_psi_zero_para_mesma_distribuicao_e_alto_para_deslocada():
    rng = np.random.default_rng(0)
    ref = pd.Series(rng.normal(0, 1, 5000))
    assert drift.psi_numerica(ref, pd.Series(rng.normal(0, 1, 5000))) < 0.05
    assert drift.psi_numerica(ref, pd.Series(rng.normal(1.5, 1, 5000))) > 0.5


@pytest.mark.parametrize("taxa_atual, alerta", [(0.02, False), (0.012, True), (0.03, True)])
def test_alerta_pela_taxa_de_acidentes(taxa_atual, alerta):
    rng = np.random.default_rng(1)
    n = 20000
    ref = pd.DataFrame({"x": rng.normal(size=n), "teve_acidente": np.arange(n) < n * 0.02})        # taxas exatas
    atual = pd.DataFrame({"x": rng.normal(size=n), "teve_acidente": np.arange(n) < n * taxa_atual})
    assert drift.monitorar(ref, atual, ["x"], CFG)["alerta"] is alerta
