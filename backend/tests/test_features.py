"""Histórico do trecho sem vazamento e coerência entre o treino e a API (dados sintéticos)."""
import numpy as np
import pandas as pd

from app import clima, config
from app.features import adicionar_historico_treino, estado_atual_trechos, nivel_notificacao

DATAS = pd.date_range("2024-01-01", "2024-12-31", freq="D")
DIAS_COM_ACIDENTE = pd.to_datetime(["2024-01-10", "2024-03-05", "2024-03-05", "2024-07-20", "2024-12-30"])


def _base():
    grade = pd.MultiIndex.from_product([["T1"], DATAS, list(config.PERIODOS)],
                                       names=["trecho_id", "data", "periodo"]).to_frame(index=False)
    acid = pd.DataFrame({"trecho_id": "T1", "data": DIAS_COM_ACIDENTE, "periodo": "tarde"})
    contagem = acid.groupby(["trecho_id", "data", "periodo"]).size().rename("n_acidentes")
    base = grade.merge(contagem, on=["trecho_id", "data", "periodo"], how="left").fillna({"n_acidentes": 0})
    return adicionar_historico_treino(base), acid


def test_historico_nao_inclui_o_proprio_dia():
    base, _ = _base()
    dia = base[(base["data"] == "2024-03-05") & (base["periodo"] == "tarde")].iloc[0]
    assert dia["n_acidentes"] == 2
    assert dia["acid_ult_365d"] == 1  # só o de 10/01
    seguinte = base[(base["data"] == "2024-03-06") & (base["periodo"] == "tarde")].iloc[0]
    assert seguinte["acid_ult_365d"] == 3


def test_acid_ult_365d_bate_com_contagem_manual():
    base, _ = _base()
    for data in ["2024-01-10", "2024-01-11", "2024-08-01", "2024-12-31"]:
        esperado = int(((DIAS_COM_ACIDENTE < pd.Timestamp(data))
                        & (DIAS_COM_ACIDENTE >= pd.Timestamp(data) - pd.Timedelta(days=365))).sum())
        assert base.loc[base["data"] == data, "acid_ult_365d"].iat[0] == esperado


def test_estado_da_api_continua_o_treino():
    """O estado usado pela API equivale ao histórico do treino no dia seguinte ao fim da base."""
    _, acid = _base()
    trechos = pd.DataFrame({"trecho_id": ["T1"]})
    estado = estado_atual_trechos(acid, trechos).iloc[0]
    assert estado["acid_ult_365d"] == len(DIAS_COM_ACIDENTE)
    # taxa: acidentes ÷ dias do período (aqui, do 1º ao último acidente)
    total_dias = (DIAS_COM_ACIDENTE.max() - DIAS_COM_ACIDENTE.min()).days + 1
    assert np.isclose(estado["taxa_historica"], len(DIAS_COM_ACIDENTE) / total_dias)


def test_nivel_notificacao_defasado_e_normalizado():
    inicio, fim = pd.Timestamp("2024-01-01"), pd.Timestamp("2024-12-31")
    datas = pd.Series(pd.date_range(inicio - pd.Timedelta(days=200), fim, freq="D"))  # 1 acidente por dia
    nivel = nivel_notificacao(datas, inicio, fim).set_index("data")["nivel_notificacao"]
    assert np.allclose(nivel, 1.0)
    assert nivel.index.max() == fim + pd.Timedelta(days=1)  # valor usado pela API


def test_clima_ausente_preenchido_pela_climatologia():
    hist = pd.DataFrame({"celula": "c", "data": pd.to_datetime(["2024-01-01", "2024-01-02", "2024-02-01"]),
                         "periodo": "tarde", "chuva_mm": [2.0, 4.0, 10.0], "nebulosidade": [50.0, 70.0, 90.0],
                         "temperatura": [25.0, 27.0, 20.0]})
    df = pd.DataFrame({"celula": ["c"], "data": [pd.Timestamp("2025-01-15")], "periodo": ["tarde"],
                       "chuva_mm": [np.nan], "nebulosidade": [np.nan], "temperatura": [np.nan]})
    cheio = clima.preencher_com_climatologia(df, hist).iloc[0]
    assert (cheio["chuva_mm"], cheio["nebulosidade"], cheio["temperatura"]) == (3.0, 60.0, 26.0)
