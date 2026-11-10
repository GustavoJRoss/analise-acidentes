"""Trechos de BR a partir da geometria: km interpolado nos vãos sem acidente."""
import numpy as np
import pandas as pd
from sklearn.neighbors import BallTree

from app.osm import _km_dos_pontos, trechos_sem_acidente

KM_POR_GRAU = 111.32


def _arvores(acidentes):
    return {br: (BallTree(np.radians(g[["latitude", "longitude"]].values), metric="haversine"), g["km"].values)
            for br, g in acidentes.groupby("br")}


def test_km_interpolado_no_vao_entre_acidentes():
    # via reta de 40 km para o norte; acidentes só nas pontas (km 100 e km 140)
    coords = np.array([[-28.0 + k / KM_POR_GRAU, -49.0] for k in range(0, 41)])
    acid = pd.DataFrame({"br": 101, "latitude": [-28.0, -28.0 + 40 / KM_POR_GRAU], "longitude": -49.0,
                         "km": [100.0, 140.0]})
    brs, kms = _km_dos_pontos(coords, [101], _arvores(acid))
    assert (brs == 101).all()
    assert np.isclose(kms[0], 100) and np.isclose(kms[-1], 140)
    assert np.allclose(kms[10:31], np.arange(110, 131), atol=0.2)  # meio do vão: > 5 km de qualquer acidente


def test_ponta_sem_acidente_fica_sem_km():
    coords = np.array([[-28.0 + k / KM_POR_GRAU, -49.0] for k in range(0, 21)])
    acid = pd.DataFrame({"br": 101, "latitude": [-28.0], "longitude": -49.0, "km": [100.0]})
    _, kms = _km_dos_pontos(coords, [101], _arvores(acid))
    assert not np.isnan(kms[:5]).any() and np.isnan(kms[-1])


def test_resumo_dos_trechos_sem_acidente():
    pontos = pd.DataFrame({"lat": [-28.0, -28.01, -27.5], "lon": [-49.0, -49.0, -49.0],
                           "trecho_id": ["101-110", "101-110", "101-100"]})
    acid = pd.DataFrame({"trecho_id": ["101-100"], "latitude": [-27.5], "longitude": [-49.0],
                         "delegacia": ["DEL01-SC"], "municipio": ["PALHOCA"]})
    resumo = trechos_sem_acidente(pontos, acid)
    assert resumo["trecho_id"].tolist() == ["101-110"]
    linha = resumo.iloc[0]
    assert (linha["br"], linha["trecho_km"], linha["acidentes"], linha["delegacia"]) == (101, 110, 0, "DEL01-SC")
