"""Testes da API (usam os artefatos gerados pelos scripts de preparação e treino).

Rodar (dentro de backend/):  pytest
Os testes de rota/busca chamam serviços públicos do OSM e são pulados com  pytest -m "not externo".
Os testes da rede estadual são pulados se ela não foi preparada (scripts.preparar_estaduais + treinar --rede sc).
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def cliente():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def trechos(cliente):
    return [f["properties"] for f in cliente.get("/api/trechos").json()["features"]]


def _mais_movimentado(trechos, rede):
    da_rede = [t for t in trechos if t["rede"] == rede]
    if not da_rede:
        pytest.skip(f"rede {rede} não preparada")
    return max(da_rede, key=lambda t: t["acidentes"])["trecho_id"]


@pytest.fixture(scope="module")
def trecho_br(trechos):
    return _mais_movimentado(trechos, "br")


@pytest.fixture(scope="module")
def trecho_sc(trechos):
    return _mais_movimentado(trechos, "sc")


def _prever(cliente, trecho_ids, **kw):
    corpo = {"trecho_ids": trecho_ids, "data": "2026-01-10", "periodo": "tarde", "clima": "ceu_claro", **kw}
    resp = cliente.post("/api/prever", json=corpo)
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_trechos_geojson(cliente, trechos):
    dados = cliente.get("/api/trechos").json()
    assert dados["type"] == "FeatureCollection"
    assert len([t for t in trechos if t["rede"] == "br"]) > 200
    chaves = {"trecho_id", "rede", "rodovia", "rotulo", "municipio", "acidentes", "acidentes_ano", "densidade"}
    assert all(chaves <= t.keys() for t in trechos)


def test_previsao_um_trecho(cliente, trecho_br):
    r = _prever(cliente, [trecho_br])
    assert 0 < r["probabilidade"] < 1
    assert len(r["trechos"]) == 1 and r["fatores"]
    assert r["trechos"][0]["rotulo"].startswith("BR-")
    assert r["cenario"]["temporada_verao"] is True


def test_rota_combina_probabilidades(cliente, trechos):
    ids = [t["trecho_id"] for t in trechos[:5]]
    r = _prever(cliente, ids)
    individuais = [t["probabilidade"] for t in r["trechos"]]
    assert [t["trecho_id"] for t in r["trechos"]] == ids
    assert max(individuais) <= r["probabilidade"] <= min(1, sum(individuais)) + 1e-6


def test_entradas_mudam_a_previsao(cliente, trecho_br):
    base = _prever(cliente, [trecho_br])["probabilidade"]
    outras = [
        _prever(cliente, [trecho_br], periodo="madrugada")["probabilidade"],
        _prever(cliente, [trecho_br], clima="chuva_forte")["probabilidade"],
        _prever(cliente, [trecho_br], data="2026-02-17")["probabilidade"],  # Carnaval
    ]
    assert all(p != base for p in outras)


def test_feriado_detectado(cliente, trecho_br):
    assert _prever(cliente, [trecho_br], data="2026-12-25")["cenario"]["feriado"] is True


def test_validacao(cliente, trecho_br):
    for desconhecido in ["999-0", "SC-999|4205407"]:
        assert cliente.post("/api/prever", json={"trecho_ids": [desconhecido], "data": "2026-01-10",
                                                 "periodo": "tarde"}).status_code == 404
    assert cliente.post("/api/prever", json={"trecho_ids": [trecho_br], "data": "2026-01-10",
                                             "periodo": "almoco"}).status_code == 422


def test_modelo_metricas(cliente):
    m = cliente.get("/api/modelo").json()
    assert m["br"]["modelos"]["com_clima"]["roc_auc"] > 0.7


# ---- rede estadual (RENAEST) -------------------------------------------------------------------
def test_previsao_trecho_estadual(cliente, trecho_sc):
    r = _prever(cliente, [trecho_sc])
    assert 0 < r["probabilidade"] < 1 and r["fatores"]
    assert r["trechos"][0]["rede"] == "sc" and r["trechos"][0]["rodovia"].startswith("SC-")


def test_rota_mista_br_e_estadual(cliente, trecho_br, trecho_sc):
    r = _prever(cliente, [trecho_br, trecho_sc])
    individuais = {t["trecho_id"]: t["probabilidade"] for t in r["trechos"]}
    esperado = 1 - (1 - individuais[trecho_br]) * (1 - individuais[trecho_sc])
    assert r["probabilidade"] == pytest.approx(esperado, abs=1e-4)
    assert {t["rede"] for t in r["trechos"]} == {"br", "sc"}
    assert all(f["efeito_relativo"] > -1 for f in r["fatores"])


def test_metricas_estaduais(cliente, trecho_sc):
    assert "sc" in cliente.get("/api/modelo").json()


@pytest.mark.externo
def test_rota_joinville_florianopolis(cliente):
    r = cliente.post("/api/rota", json={"origem": {"lat": -26.304, "lon": -48.846},
                                        "destino": {"lat": -27.595, "lon": -48.548}})
    assert r.status_code == 200, r.text
    dados = r.json()
    assert dados["distancia_km"] > 100
    assert any(t["trecho_id"].startswith("101-") for t in dados["trechos"])


@pytest.mark.externo
def test_rota_pela_sc401(cliente, trecho_sc):
    # centro de Florianópolis → Jurerê: a maior parte do caminho é pela SC-401
    r = cliente.post("/api/rota", json={"origem": {"lat": -27.5954, "lon": -48.5480},
                                        "destino": {"lat": -27.4390, "lon": -48.4966}})
    assert r.status_code == 200, r.text
    assert any(t["trecho_id"].startswith("SC-401|") for t in r.json()["trechos"])


@pytest.mark.externo
def test_busca(cliente):
    r = cliente.get("/api/busca", params={"q": "Blumenau"})
    assert r.status_code == 200 and r.json()


def test_media_de_referencia_e_probabilidade(cliente, trecho_sc):
    """A taxa histórica passa de 1 acidente por período em trechos movimentados; a referência não pode virar 100%."""
    r = _prever(cliente, [trecho_sc])
    assert 0 < r["media_referencia"] < 1
    assert 0 < r["trechos"][0]["media_periodo"] < 1
