"""Rotas (OSRM) e busca de endereços (Nominatim), ambos sobre dados do OpenStreetMap."""
import threading
import time
from functools import lru_cache

import httpx
import numpy as np
import pandas as pd
from sklearn.neighbors import BallTree

from . import config

OSRM_URL = "https://router.project-osrm.org/route/v1/driving"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
SC_VIEWBOX = "-53.9,-25.9,-48.3,-29.45"  # lon_min, lat_max, lon_max, lat_min
RAIO_TERRA_M = 6_371_000
DIST_MAX_VIA_M = 50       # ponto da rota a até 50 m de uma BR conta como "na BR"
MIN_PONTOS_TRECHO = 3     # ignora cruzamentos rápidos (viadutos, passagens sobre a BR)
ESPACAMENTO_M = 100

_trava_nominatim = threading.Lock()
_ultima_chamada = [0.0]


class CasadorDeRota:
    def __init__(self):
        pontos = pd.read_parquet(config.ARQ_PONTOS_VIA)
        self.trecho_ids = pontos["trecho_id"].values
        self.arvore = BallTree(np.radians(pontos[["lat", "lon"]].values), metric="haversine")

    def trechos_da_rota(self, coords_lonlat: list) -> list:
        pontos = _densificar(np.array([[lat, lon] for lon, lat in coords_lonlat]))
        dist, idx = self.arvore.query(np.radians(pontos), k=1)
        perto = dist[:, 0] * RAIO_TERRA_M <= DIST_MAX_VIA_M
        passo_m = np.append(_distancias_m(pontos), 0)  # distância até o próximo ponto

        contagem, metros, ordem = {}, {}, []
        for t, m in zip(self.trecho_ids[idx[perto, 0]], passo_m[perto]):
            if t not in contagem:
                ordem.append(t)
            contagem[t] = contagem.get(t, 0) + 1
            metros[t] = metros.get(t, 0) + m
        return [{"trecho_id": t, "km_na_rota": round(metros[t] / 1000, 1)}
                for t in ordem if contagem[t] >= MIN_PONTOS_TRECHO]


def _distancias_m(pontos: np.ndarray) -> np.ndarray:
    """Distância (aproximação plana, suficiente em poucos km) entre pontos consecutivos (lat, lon)."""
    a, b = pontos[:-1], pontos[1:]
    lat = np.radians((a[:, 0] + b[:, 0]) / 2)
    return np.hypot((b[:, 0] - a[:, 0]) * 111_320, (b[:, 1] - a[:, 1]) * 111_320 * np.cos(lat))


def _densificar(pontos: np.ndarray) -> np.ndarray:
    saida = [pontos[0]]
    for a, b, dist in zip(pontos[:-1], pontos[1:], _distancias_m(pontos)):
        n = int(dist // ESPACAMENTO_M)
        for t in np.linspace(0, 1, n + 2)[1:]:
            saida.append(a + (b - a) * t)
    return np.array(saida)


def calcular_rota(origem: tuple, destino: tuple) -> dict:
    """origem/destino em (lat, lon). Retorna geometria GeoJSON, distância e duração."""
    coords = f"{origem[1]},{origem[0]};{destino[1]},{destino[0]}"
    resp = httpx.get(f"{OSRM_URL}/{coords}", params={"overview": "full", "geometries": "geojson"},
                     timeout=30, headers={"User-Agent": config.USER_AGENT})
    resp.raise_for_status()
    dados = resp.json()
    if dados.get("code") != "Ok" or not dados.get("routes"):
        raise ValueError("Não foi possível traçar uma rota entre esses pontos.")
    rota = dados["routes"][0]
    return {"geometria": rota["geometry"], "distancia_km": round(rota["distance"] / 1000, 1),
            "duracao_min": round(rota["duration"] / 60)}


@lru_cache(maxsize=512)
def buscar_endereco(q: str) -> list:
    # política do Nominatim: no máximo 1 requisição por segundo e User-Agent identificável
    with _trava_nominatim:
        espera = 1.0 - (time.time() - _ultima_chamada[0])
        if espera > 0:
            time.sleep(espera)
        resp = httpx.get(NOMINATIM_URL, timeout=15, headers={"User-Agent": config.USER_AGENT},
                         params={"q": q, "format": "jsonv2", "countrycodes": "br", "viewbox": SC_VIEWBOX,
                                 "bounded": 1, "limit": 6, "accept-language": "pt-BR"})
        _ultima_chamada[0] = time.time()
    resp.raise_for_status()
    return [{"nome": r["display_name"], "lat": float(r["lat"]), "lon": float(r["lon"])} for r in resp.json()]
