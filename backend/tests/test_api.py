"""Testes da API (usam os artefatos gerados por preparar_dados + treinar).

Rodar (dentro de backend/):  pytest
Os testes de rota/busca chamam serviços públicos do OSM e são pulados com  pytest -m "not externo".
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def cliente():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def trecho_movimentado(cliente):
    trechos = cliente.get("/api/trechos").json()["features"]
    return max(trechos, key=lambda f: f["properties"]["acidentes"])["properties"]["trecho_id"]


def _prever(cliente, trecho_ids, **kw):
    corpo = {"trecho_ids": trecho_ids, "data": "2026-01-10", "periodo": "tarde", "clima": "ceu_claro", **kw}
    resp = cliente.post("/api/prever", json=corpo)
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_trechos_geojson(cliente):
    dados = cliente.get("/api/trechos").json()
    assert dados["type"] == "FeatureCollection"
    assert len(dados["features"]) > 200
    props = dados["features"][0]["properties"]
    assert {"trecho_id", "br", "trecho_km", "acidentes", "prob_dia"} <= props.keys()


def test_previsao_um_trecho(cliente, trecho_movimentado):
    r = _prever(cliente, [trecho_movimentado])
    assert 0 < r["probabilidade"] < 1
    assert len(r["trechos"]) == 1 and r["fatores"]
    assert r["cenario"]["temporada_verao"] is True


def test_rota_combina_probabilidades(cliente, trecho_movimentado):
    trechos = [f["properties"]["trecho_id"] for f in cliente.get("/api/trechos").json()["features"][:5]]
    r = _prever(cliente, trechos)
    individuais = [t["probabilidade"] for t in r["trechos"]]
    assert max(individuais) <= r["probabilidade"] <= min(1, sum(individuais)) + 1e-6


def test_entradas_mudam_a_previsao(cliente, trecho_movimentado):
    base = _prever(cliente, [trecho_movimentado])["probabilidade"]
    outras = [
        _prever(cliente, [trecho_movimentado], periodo="madrugada")["probabilidade"],
        _prever(cliente, [trecho_movimentado], clima="chuva_forte")["probabilidade"],
        _prever(cliente, [trecho_movimentado], data="2026-02-17")["probabilidade"],  # Carnaval
    ]
    assert all(p != base for p in outras)


def test_feriado_detectado(cliente, trecho_movimentado):
    assert _prever(cliente, [trecho_movimentado], data="2026-12-25")["cenario"]["feriado"] is True


def test_validacao(cliente, trecho_movimentado):
    assert cliente.post("/api/prever", json={"trecho_ids": ["999-0"], "data": "2026-01-10",
                                             "periodo": "tarde"}).status_code == 404
    assert cliente.post("/api/prever", json={"trecho_ids": [trecho_movimentado], "data": "2026-01-10",
                                             "periodo": "almoco"}).status_code == 422


def test_modelo_metricas(cliente):
    m = cliente.get("/api/modelo").json()
    assert m["modelos"]["com_clima"]["roc_auc"] > 0.7


@pytest.mark.externo
def test_rota_joinville_florianopolis(cliente):
    r = cliente.post("/api/rota", json={"origem": {"lat": -26.304, "lon": -48.846},
                                        "destino": {"lat": -27.595, "lon": -48.548}})
    assert r.status_code == 200, r.text
    dados = r.json()
    assert dados["distancia_km"] > 100
    assert any(t["trecho_id"].startswith("101-") for t in dados["trechos"])


@pytest.mark.externo
def test_busca(cliente):
    r = cliente.get("/api/busca", params={"q": "Blumenau"})
    assert r.status_code == 200 and r.json()
