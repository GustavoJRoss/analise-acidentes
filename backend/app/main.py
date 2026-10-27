"""API de risco de acidentes nas BRs de SC.

Rodar (dentro de backend/):  uvicorn app.main:app --reload --port 8000
"""
from contextlib import asynccontextmanager
from datetime import date, timedelta

import httpx
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.concurrency import run_in_threadpool

from . import clima, config, rotas
from .modelo import ServicoPrevisao
from .schemas import PedidoPrevisao, PedidoRota, Periodo

estado = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    estado["servico"] = ServicoPrevisao()
    estado["casador"] = rotas.CasadorDeRota()
    yield
    estado.clear()


app = FastAPI(title="Risco de acidentes — BRs de SC", lifespan=lifespan)


def _erro_externo(servico: str, exc: Exception):
    raise HTTPException(502, f"{servico} indisponível no momento. Tente novamente em instantes.") from exc


@app.get("/api/saude")
def saude():
    return {"ok": True}


@app.get("/api/trechos")
def trechos():
    return estado["servico"].trechos_geojson()


@app.get("/api/opcoes")
def opcoes():
    servico = estado["servico"]
    return {
        "clima": [{"id": k, "rotulo": v["rotulo"], "chuva_mm": v["chuva_mm"], "frequencia": v.get("frequencia")}
                  for k, v in servico.presets.items()],
        "periodos": [{"id": "madrugada", "rotulo": "Madrugada", "faixa": "0h–6h"},
                     {"id": "manha", "rotulo": "Manhã", "faixa": "6h–12h"},
                     {"id": "tarde", "rotulo": "Tarde", "faixa": "12h–18h"},
                     {"id": "noite", "rotulo": "Noite", "faixa": "18h–24h"}],
        "feriados": [str(d.date()) for d in config.FERIADOS],
    }


@app.post("/api/prever")
def prever(pedido: PedidoPrevisao):
    servico = estado["servico"]
    desconhecidos = [t for t in pedido.trecho_ids if t not in servico.estado.index]
    if desconhecidos:
        raise HTTPException(404, f"Trechos desconhecidos: {', '.join(desconhecidos[:5])}")
    personalizado = pedido.clima_personalizado.model_dump() if pedido.clima_personalizado else None
    return servico.prever(pedido.trecho_ids, pd.Timestamp(pedido.data), pedido.periodo, pedido.clima, personalizado)


@app.post("/api/rota")
async def rota(pedido: PedidoRota):
    try:
        resultado = await run_in_threadpool(rotas.calcular_rota, (pedido.origem.lat, pedido.origem.lon),
                                            (pedido.destino.lat, pedido.destino.lon))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except httpx.HTTPError as exc:
        _erro_externo("Serviço de rotas (OSRM)", exc)
    resultado["trechos"] = estado["casador"].trechos_da_rota(resultado["geometria"]["coordinates"])
    return resultado


@app.get("/api/busca")
async def busca(q: str = Query(min_length=3, max_length=120)):
    try:
        return await run_in_threadpool(rotas.buscar_endereco, q.strip().lower())
    except httpx.HTTPError as exc:
        _erro_externo("Busca de endereços (Nominatim)", exc)


@app.get("/api/clima-previsto")
async def clima_previsto(trecho_id: str, data: date, periodo: Periodo):
    servico = estado["servico"]
    if trecho_id not in servico.estado.index:
        raise HTTPException(404, "Trecho desconhecido")
    hoje = date.today()
    if not hoje <= data <= hoje + timedelta(days=15):
        raise HTTPException(422, "A previsão do tempo só cobre os próximos 16 dias.")
    lat, lon = servico.centro(trecho_id)
    try:
        return await run_in_threadpool(clima.previsao, lat, lon, pd.Timestamp(data), periodo)
    except httpx.HTTPError as exc:
        _erro_externo("Previsão do tempo (Open-Meteo)", exc)


@app.get("/api/modelo")
def modelo():
    return estado["servico"].metricas
