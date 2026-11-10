"""Geometria das rodovias de SC a partir do OpenStreetMap (Overpass).

- BRs: cortadas nos trechos de 10 km do modelo. O OSM não tem a quilometragem da PRF, então cada ponto
  da via herda o km do acidente mais próximo da mesma BR. Pontos longe de qualquer acidente ficam sem trecho.
- Rodovias estaduais: cortadas pelos limites municipais (trecho = rodovia × município), porque os
  acidentes do RENAEST em SC só trazem o município e o nome da via.
- Vias com nome (todas as categorias): usadas para casar o endereço digitado no RENAEST.
"""
import json
import re

import httpx
import numpy as np
import pandas as pd
import shapely
from sklearn.neighbors import BallTree

from . import config
from .dados import id_trecho
from .vias import ref_principal

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
CONSULTA_BRS = """
[out:json][timeout:180];
area["ISO3166-2"="BR-SC"]->.sc;
way(area.sc)["highway"~"^(motorway|trunk|primary|secondary|tertiary)$"]["ref"~"BR-"];
out geom;
"""
RAIO_TERRA_M = 6_371_000
ESPACAMENTO_M = 100        # densificação das linhas para casar rotas
DIST_MAX_ACIDENTE_M = 5_000
DIST_ANCORA_M = 300          # ponto da via tão perto de um acidente herda o km dele
MIN_EXTENSAO_SEM_ACIDENTE_M = 2_000   # trecho de BR sem acidente precisa de ao menos 2 km de via
MIN_KM_SEM_ACIDENTE_SC = 1.0          # idem para rodovia estadual × município


CONSULTA_ESTADUAIS = """
[out:json][timeout:300];
area["ISO3166-2"="BR-SC"]->.sc;
way(area.sc)["highway"]["ref"~"^SC[A-Z]?-?[0-9]"];
out geom;
"""
TIPOS_COM_NOME = ("motorway|trunk|primary|secondary|tertiary|unclassified|residential|living_street|service|"
                  "track|road|motorway_link|trunk_link|primary_link|secondary_link|tertiary_link|pedestrian|cycleway")
CONSULTA_VIAS_NOMEADAS = f"""
[out:json][timeout:600];
area["ISO3166-2"="BR-SC"]->.sc;
(way(area.sc)["highway"~"^({TIPOS_COM_NOME})$"]["name"];
 way(area.sc)["highway"]["ref"~"^(SC|BR|SCT|SCA|SCL|SCI)"];);
out tags center;
"""


def _overpass(consulta: str, arquivo, forcar: bool, timeout: int = 660) -> dict:
    """Executa a consulta e guarda a resposta em `arquivo` (cache)."""
    if arquivo.exists() and not forcar:
        return json.loads(arquivo.read_text())
    resp = httpx.post(OVERPASS_URL, data={"data": consulta}, timeout=timeout,
                      headers={"User-Agent": config.USER_AGENT})
    resp.raise_for_status()
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    arquivo.write_text(resp.text)
    return resp.json()


def baixar_osm(forcar: bool = False) -> dict:
    return _overpass(CONSULTA_BRS, config.ARQ_OSM_BRUTO, forcar, timeout=240)


def baixar_rodovias_estaduais(forcar: bool = False) -> dict:
    return _overpass(CONSULTA_ESTADUAIS, config.ARQ_OSM_ESTADUAIS, forcar)


def baixar_vias_nomeadas(forcar: bool = False) -> dict:
    """Todas as vias com nome ou código em SC, só com as tags e o ponto central (~40 MB)."""
    return _overpass(CONSULTA_VIAS_NOMEADAS, config.ARQ_OSM_VIAS, forcar)


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


def _km_dos_pontos(coords: np.ndarray, brs: list, arvores: dict):
    """Para cada ponto da via: (BR, km).

    Âncoras: pontos a até DIST_ANCORA_M de um acidente da mesma BR recebem o km desse acidente. Entre duas
    âncoras da mesma BR, o km é interpolado pela distância percorrida (assim um vão sem acidente também ganha
    km). Nas pontas da via, sem âncora dos dois lados, vale o km do acidente mais próximo até DIST_MAX_ACIDENTE_M.
    """
    melhor_dist = np.full(len(coords), np.inf)
    melhor_br = np.zeros(len(coords), dtype=int)
    km_vizinho = np.full(len(coords), np.nan)
    for br in brs:
        arvore, kms = arvores[br]
        dist, idx = arvore.query(np.radians(coords), k=1)
        dist = dist[:, 0] * RAIO_TERRA_M
        melhor = dist < melhor_dist
        melhor_dist[melhor], melhor_br[melhor], km_vizinho[melhor] = dist[melhor], br, kms[idx[melhor, 0]]

    km = np.where(melhor_dist <= DIST_MAX_ACIDENTE_M, km_vizinho, np.nan)
    ancoras = np.where(melhor_dist <= DIST_ANCORA_M)[0]
    if len(ancoras) >= 2:
        percorrido = np.concatenate([[0], np.cumsum([_haversine_m(a, b) for a, b in zip(coords[:-1], coords[1:])])])
        meio = np.setdiff1d(np.arange(ancoras[0] + 1, ancoras[-1]), ancoras)
        antes = ancoras[np.searchsorted(ancoras, meio) - 1]
        depois = ancoras[np.searchsorted(ancoras, meio)]
        mesma_br = melhor_br[antes] == melhor_br[depois]
        meio, antes, depois = meio[mesma_br], antes[mesma_br], depois[mesma_br]
        frac = (percorrido[meio] - percorrido[antes]) / np.maximum(percorrido[depois] - percorrido[antes], 1)
        km[meio] = km_vizinho[antes] + frac * (km_vizinho[depois] - km_vizinho[antes])
        melhor_br[meio] = melhor_br[antes]
    return melhor_br, km


def construir_trechos(osm: dict, acidentes: pd.DataFrame):
    """Retorna (geojson dos trechos, DataFrame de pontos densificados com trecho_id).

    Um trecho existe se há geometria do OSM com km atribuído, mesmo sem nenhum acidente: é assim que o modelo
    vê trechos seguros. (Antes, só os trechos com acidente entravam.)
    """
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
        brs_pt, kms_pt = _km_dos_pontos(coords, brs, arvores)
        melhor_trecho = np.array([None if np.isnan(k) else id_trecho(b, k // config.TAMANHO_TRECHO_KM
                                                                        * config.TAMANHO_TRECHO_KM)
                                  for b, k in zip(brs_pt, kms_pt)], dtype=object)

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

    pontos_df = pd.DataFrame(pontos, columns=["lat", "lon", "trecho_id"])
    # trecho sem acidente só conta se tem extensão de verdade (evita restos de interpolação em trevos)
    com_acidente = set(acidentes["trecho_id"])
    n_pontos = pontos_df["trecho_id"].value_counts()
    validos = {t for t, n in n_pontos.items() if t in com_acidente or n * ESPACAMENTO_M >= MIN_EXTENSAO_SEM_ACIDENTE_M}
    pontos_df = pontos_df[pontos_df["trecho_id"].isin(validos)].reset_index(drop=True)
    features = [{"type": "Feature", "properties": {"trecho_id": t},
                 "geometry": {"type": "MultiLineString", "coordinates": linhas}}
                for t, linhas in linhas_por_trecho.items() if t in validos]
    return {"type": "FeatureCollection", "features": features}, pontos_df


def trechos_sem_acidente(pontos: pd.DataFrame, acidentes: pd.DataFrame) -> pd.DataFrame:
    """Resumo (mesmas colunas de dados.resumo_trechos) dos trechos que só existem pela geometria.

    Local: mediana dos pontos da via. Delegacia e município: os do acidente mais próximo (de qualquer BR).
    """
    novos = pontos[~pontos["trecho_id"].isin(set(acidentes["trecho_id"]))]
    if novos.empty:
        return pd.DataFrame()
    resumo = novos.groupby("trecho_id")[["lat", "lon"]].median().reset_index()
    arvore = BallTree(np.radians(acidentes[["latitude", "longitude"]].values), metric="haversine")
    _, idx = arvore.query(np.radians(resumo[["lat", "lon"]].values), k=1)
    vizinho = acidentes.iloc[idx[:, 0]].reset_index(drop=True)
    partes = resumo["trecho_id"].str.split("-", expand=True).astype(int)
    return resumo.assign(br=partes[0], trecho_km=partes[1], delegacia=vizinho["delegacia"],
                         municipio=vizinho["municipio"], acidentes=0, mortos=0, feridos_graves=0, acidentes_ano=0.0)


# ---- rodovias estaduais: rodovia × município ------------------------------------------------------
def id_trecho_estadual(rodovia: str, codigo_ibge: str) -> str:
    return f"{rodovia}|{codigo_ibge}"


def _comprimento_km(coords_latlon: np.ndarray) -> float:
    a, b = coords_latlon[:-1], coords_latlon[1:]
    lat = np.radians((a[:, 0] + b[:, 0]) / 2)
    return float(np.hypot((b[:, 0] - a[:, 0]) * 111.32, (b[:, 1] - a[:, 1]) * 111.32 * np.cos(lat)).sum())


def construir_trechos_estaduais(osm: dict, municipios: dict, pares_com_acidente: set):
    """Corta cada rodovia estadual pelos limites municipais.

    municipios: código IBGE → polígono (shapely). pares_com_acidente: {(rodovia, código IBGE)} com algum acidente.
    Todo par entra; os sem acidente só se a rodovia tem ao menos MIN_KM_SEM_ACIDENTE_SC km no município
    (zero acidentes casados pode ser falha do casamento de endereços, mas um trecho curto é quase sempre isso).
    Retorna (geojson, DataFrame de pontos densificados com trecho_id, DataFrame com um resumo por trecho).
    """
    linhas_por_ref = {}
    for elem in osm["elements"]:
        if elem.get("type") != "way" or "geometry" not in elem:
            continue
        ref = ref_principal(elem.get("tags", {}).get("ref"))
        if ref and ref.startswith("SC"):
            linhas_por_ref.setdefault(ref, []).append(
                shapely.LineString([(g["lon"], g["lat"]) for g in elem["geometry"]]))

    codigos = list(municipios)
    arvore = shapely.STRtree([municipios[c] for c in codigos])
    features, pontos, resumo = [], [], []
    for ref, linhas in linhas_por_ref.items():
        rodovia = shapely.line_merge(shapely.union_all(linhas))
        for i in arvore.query(rodovia, predicate="intersects"):
            cod = codigos[i]
            parte = shapely.intersection(rodovia, municipios[cod])
            partes = [g for g in shapely.get_parts(parte) if g.geom_type == "LineString" and g.length > 0]
            if not partes:
                continue
            tid = id_trecho_estadual(ref, cod)
            coords = [np.array(g.coords)[:, ::-1] for g in partes]  # (lat, lon)
            comprimento = sum(_comprimento_km(c) for c in coords if len(c) >= 2)
            minimo = 0.2 if (ref, cod) in pares_com_acidente else MIN_KM_SEM_ACIDENTE_SC
            if comprimento < minimo:  # só encosta no município
                continue
            maior = max(partes, key=lambda g: g.length)
            centro = maior.interpolate(0.5, normalized=True)
            resumo.append((tid, ref, cod, round(comprimento, 2), centro.y, centro.x))
            features.append({
                "type": "Feature", "properties": {"trecho_id": tid},
                "geometry": {"type": "MultiLineString",
                             "coordinates": [[[round(lon, 5), round(lat, 5)] for lat, lon in c] for c in coords]},
            })
            for c in coords:
                for lat, lon in _densificar(c):
                    pontos.append((lat, lon, tid))

    geojson = {"type": "FeatureCollection", "features": features}
    pontos_df = pd.DataFrame(pontos, columns=["lat", "lon", "trecho_id"])
    resumo_df = pd.DataFrame(resumo, columns=["trecho_id", "rodovia", "codigo_ibge", "comprimento_km", "lat", "lon"])
    return geojson, pontos_df, resumo_df
