"""Regras de limpeza dos endereços do RENAEST e casamento com nomes do OSM (exemplos reais de SC)."""
import pytest

import pandas as pd

from app.renaest import casar, resumir
from app.vias import codigo_rodovia, esfera, km_do_texto, normalizar, nucleo, ref_principal


@pytest.mark.parametrize("texto, esperado", [
    ("RUA AV. GOV. CELSO RAMOS", "AVENIDA GOVERNADOR CELSO RAMOS"),
    ("ROD  SC 405", "RODOVIA SC 405"),
    ("RODOVIA SC-413 - PROXIMIDADES DO TREVO D", "RODOVIA SC 413"),
    ("Rodovia José Carlos Daux", "RODOVIA JOSE CARLOS DAUX"),
    ("LINHA RODOVIA ESTADUAL SC 150", "ESTADUAL SC 150"),
    ("", ""),
    (None, ""),
])
def test_normalizar(texto, esperado):
    assert normalizar(texto) == esperado


def test_nucleo_ignora_tipo_e_preposicoes():
    assert nucleo(normalizar("RUA AV. D  PEDRO II")) == "PEDRO II"
    assert nucleo("AVENIDA BEIRA MAR NORTE") == nucleo("RUA BEIRA MAR NORTE") == "BEIRA MAR NORTE"


@pytest.mark.parametrize("texto, esperado", [
    ("SC355 KM 73.800", "SC-355"), ("RUA RODOVIA BR 470", "BR-470"), ("SC-163  SC-163  KM 99 200", "SC-163"),
    ("ROD  SC A101A", None), ("RUA DAS FLORES", None),
])
def test_codigo_rodovia(texto, esperado):
    assert codigo_rodovia(texto) == esperado


@pytest.mark.parametrize("texto, esperado", [
    ("SC355 KM 73.800", 73.8), ("SC-163 KM 99 200", 99.2), ("RODOVIA SC 350 KM 215", 215.0),
    ("RODOVIA SC 135 KM 1 5", 1.5), ("SC-401", None),
])
def test_km_do_texto(texto, esperado):
    assert km_do_texto(texto) == esperado


def test_ref_e_esfera():
    assert ref_principal("SC-401;SC-402") == "SC-401"
    assert esfera("SC-401") == "estadual" and esfera("BR-101") == "federal"
    assert esfera(None) == esfera(float("nan")) == "municipal"


def test_casar_por_ordem_de_regras():
    floripa = "4205407"
    por_nome = {floripa: {"RODOVIA JOSE CARLOS DAUX": ("Rodovia José Carlos Daux", "SC-401", 1.0)}}
    por_nucleo = {floripa: {
        "JOSE CARLOS DAUX": ("Rodovia José Carlos Daux", "SC-401", 1.0),
        "GOVERNADOR ADERBAL RAMOS SILVA": ("Rodovia Governador Aderbal Ramos da Silva", "SC-401", 1.0),
        "PROFESSOR ABELARDO SOUSA": ("Rua Professor Abelardo Sousa", None, 0.0),
    }}
    assert casar(floripa, "SC 401", por_nome, por_nucleo)[1:4:2] == ("SC-401", "codigo")
    assert casar(floripa, "RODOVIA JOSE CARLOS DAUX", por_nome, por_nucleo)[1:4:2] == ("SC-401", "nome")
    assert casar(floripa, "RUA JOSE CARLOS DAUX", por_nome, por_nucleo)[1:4:2] == ("SC-401", "nucleo")
    # texto cortado em 40 caracteres pelo RENAEST
    assert casar(floripa, "RODOVIA GOVERNADOR ADERBAL RAMOS DA SILV", por_nome, por_nucleo)[1:4:2] == ("SC-401", "prefixo")
    nome, ref, _, metodo, nota = casar(floripa, "RUA PROFESSOR ABELARDO SOUZA", por_nome, por_nucleo)
    assert (nome, ref, metodo) == ("Rua Professor Abelardo Sousa", None, "aproximado") and nota >= 90
    # nada parecido: fica sem via, sem chutar uma rodovia
    assert casar(floripa, "AREA RURAL", por_nome, por_nucleo)[3] == "sem_casamento"
    assert casar(floripa, "AREA RURAL", por_nome, por_nucleo)[:2] == (None, None)
    assert casar("4202404", "RODOVIA JOSE CARLOS DAUX", por_nome, por_nucleo)[3] == "sem_casamento"


def _vias(nome_norm, nome_osm, refs):
    """Uma linha por via do OSM com o mesmo nome; refs: lista com a ref (ou None) de cada via."""
    return pd.DataFrame({"osm_id": range(len(refs)), "nome_norm": nome_norm, "nome_osm": nome_osm, "ref": refs})


def test_rua_com_um_segmento_de_rodovia_nao_vira_rodovia():
    nome, ref, fracao = resumir(_vias("RUA MIRADOR", "Rua Mirador", ["SC-340"] + [None] * 9))
    assert (nome, ref, fracao) == ("Rua Mirador", None, 0.1)


def test_rua_que_e_maioria_rodovia_herda_ref():
    assert resumir(_vias("AVENIDA GETULIO VARGAS", "Avenida Getúlio Vargas", ["SC-114"] * 6 + [None] * 4))[1] == "SC-114"


def test_nome_de_rodovia_herda_ref_mesmo_em_minoria():
    assert resumir(_vias("RODOVIA JOSE CARLOS DAUX", "Rodovia José Carlos Daux", ["SC-401"] + [None] * 5))[1] == "SC-401"
