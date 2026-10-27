"""Geometria das BRs em SC a partir do OpenStreetMap (Overpass), cortada nos trechos de 10 km do modelo.

O OSM não tem a quilometragem da PRF, então cada ponto da via herda o km do acidente mais
próximo da mesma BR. Pontos longe de qualquer acidente ficam sem trecho (o modelo não os cobre).
"""
import json
import re

import httpx
import numpy as np
import pandas as pd
from sklearn.neighbors import BallTree

from . import config
from .dados import id_trecho

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
CONSULTA = """
[out:json][timeout:180];
area["ISO3166-2"="BR-SC"]->.sc;
way(area.sc)["highway"~"^(motorway|trunk|primary|secondary|tertiary)$"]["ref"~"BR-"];
out geom;
"""
RAIO_TERRA_M = 6_371_000
ESPACAMENTO_M = 100        # densificação das linhas para casar rotas
DIST_MAX_ACIDENTE_M = 5_000


def baixar_osm(forcar: bool = False) -> dict:
    if config.ARQ_OSM_BRUTO.exists() and not forcar:
        return json.loads(config.ARQ_OSM_BRUTO.read_text())
    resp = httpx.post(OVERPASS_URL, data={"data": CONSULTA}, timeout=240,
                      headers={"User-Agent": config.USER_AGENT})
    resp.raise_for_status()
    config.ARQ_OSM_BRUTO.write_text(resp.text)
    return resp.json()


def _brs_da_ref(ref: str) -> list:
    return sorted({int(n) for n in re.findall(r"BR-?\s?(\d{3})", ref or "")})


def _densificar(coords: np.ndarray) -> np.ndarray:
    """coords em (lat, lon). Insere pontos para que o espaçamento fique <= ESPACAMENTO_M."""
    saida = [coords[0]]
    for a, b in zip(coords[:-1], coords[1:]):
        dist = _haversine_m(a, b)
        n = max(int(dist // ESPACAMENTO_M), 0)
        for t in np.linspace(0, 1, n + 2)[1:]:
            saida.append(a + (b - a) * t)
    return np.array(saida)


def _haversine_m(a, b) -> float:
    lat1, lon1, lat2, lon2 = map(np.radians, (a[0], a[1], b[0], b[1]))
    h = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 2 * RAIO_TERRA_M * np.arcsin(np.sqrt(h))


def construir_trechos(osm: dict, acidentes: pd.DataFrame, trechos_validos: set):
    """Retorna (geojson dos trechos, DataFrame de pontos densificados com trecho_id)."""
    arvores = {}
    for br, grupo in acidentes.groupby("br"):
        arvores[br] = (BallTree(np.radians(grupo[["latitude", "longitude"]].values), metric="haversine"),
                       grupo["km"].values)

    linhas_por_trecho = {}
    pontos = []
    for elem in osm["elements"]:
        if elem.get("type") != "way" or "geometry" not in elem:
            continue
        brs = [b for b in _brs_da_ref(elem.get("tags", {}).get("ref")) if b in arvores]
        if not brs:
            continue
        coords = _densificar(np.array([[g["lat"], g["lon"]] for g in elem["geometry"]]))

        # para cada ponto, a BR cujo acidente mais próximo está mais perto
        melhor_dist = np.full(len(coords), np.inf)
        melhor_trecho = np.full(len(coords), None, dtype=object)
        for br in brs:
            arvore, kms = arvores[br]
            dist, idx = arvore.query(np.radians(coords), k=1)
            dist = dist[:, 0] * RAIO_TERRA_M
            km = kms[idx[:, 0]]
            melhor = dist < melhor_dist
            melhor_dist[melhor] = dist[melhor]
            for i in np.where(melhor)[0]:
                melhor_trecho[i] = id_trecho(br, km[i] // config.TAMANHO_TRECHO_KM * config.TAMANHO_TRECHO_KM)
        melhor_trecho[melhor_dist > DIST_MAX_ACIDENTE_M] = None
        melhor_trecho = np.array([t if t in trechos_validos else None for t in melhor_trecho], dtype=object)

        # quebra a via em sequências contínuas do mesmo trecho
        inicio = 0
        for i in range(1, len(coords) + 1):
            if i == len(coords) or melhor_trecho[i] != melhor_trecho[inicio]:
                trecho = melhor_trecho[inicio]
                if trecho is not None:
                    fim = min(i + 1, len(coords))  # inclui o próximo ponto para não deixar buracos
                    linha = [[round(lon, 5), round(lat, 5)] for lat, lon in coords[inicio:fim]]
                    if len(linha) >= 2:
                        linhas_por_trecho.setdefault(trecho, []).append(linha)
                inicio = i
        for (lat, lon), trecho in zip(coords, melhor_trecho):
            if trecho is not None:
                pontos.append((lat, lon, trecho))

    features = [{"type": "Feature", "properties": {"trecho_id": t},
                 "geometry": {"type": "MultiLineString", "coordinates": linhas}}
                for t, linhas in linhas_por_trecho.items()]
    geojson = {"type": "FeatureCollection", "features": features}
    pontos_df = pd.DataFrame(pontos, columns=["lat", "lon", "trecho_id"])
    return geojson, pontos_df
