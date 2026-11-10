"""Constantes compartilhadas entre preparação, treino e API."""
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

BACKEND_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = BACKEND_DIR.parent
CSV_PATH = ROOT_DIR / "acidentes2025_todas_causas_tipos.csv"
ARTIFACTS = BACKEND_DIR / "artifacts"


@dataclass(frozen=True)
class Artefatos:
    """Arquivos gerados para uma rede de rodovias. As duas redes usam os mesmos nomes, em pastas diferentes."""
    pasta: Path

    def __post_init__(self):
        self.pasta.mkdir(parents=True, exist_ok=True)

    trechos_geojson = property(lambda self: self.pasta / "trechos.geojson")
    pontos_via = property(lambda self: self.pasta / "pontos_via.parquet")
    clima = property(lambda self: self.pasta / "clima.parquet")
    clima_lotes = property(lambda self: self.pasta / "clima_lotes")
    modelo = property(lambda self: self.pasta / "modelo.joblib")
    estado = property(lambda self: self.pasta / "estado_trechos.parquet")
    climatologia = property(lambda self: self.pasta / "climatologia.parquet")
    metricas = property(lambda self: self.pasta / "metricas.json")
    presets_clima = property(lambda self: self.pasta / "clima_presets.json")
    acidentes = property(lambda self: self.pasta / "acidentes.parquet")
    trechos = property(lambda self: self.pasta / "trechos.parquet")
    notificacao = property(lambda self: self.pasta / "notificacao.parquet")
    previsoes_teste = property(lambda self: self.pasta / "teste_previsoes.parquet")


# "br": rodovias federais (PRF, trechos de 10 km) · "sc": rodovias estaduais (RENAEST, rodovia × município)
REDES = {"br": Artefatos(ARTIFACTS), "sc": Artefatos(ARTIFACTS / "estaduais")}
ARQ_OSM_BRUTO = ARTIFACTS / "osm_brs.json"

# bases externas grandes, baixadas pelos scripts e mantidas fora do git
DADOS_EXTERNOS = ROOT_DIR / "dados_externos"
PASTA_RENAEST = DADOS_EXTERNOS / "renaest"
ARQ_RENAEST_SC = PASTA_RENAEST / "acidentes_sc.parquet"
ARQ_RENAEST_VIAS = PASTA_RENAEST / "acidentes_sc_vias.parquet"
ARQ_OSM_VIAS = DADOS_EXTERNOS / "osm" / "vias_sc.json"
ARQ_OSM_ESTADUAIS = DADOS_EXTERNOS / "osm" / "rodovias_estaduais_sc.json"
ARQ_MUNICIPIOS_GEO = DADOS_EXTERNOS / "ibge" / "municipios_sc.geojson"
ARQ_MUNICIPIOS_NOMES = DADOS_EXTERNOS / "ibge" / "municipios_sc_nomes.json"

# PRF: um arquivo por ano, "Agrupados por pessoa – Todas as causas e tipos de acidentes" (IDs do Google Drive
# conferidos no portal em 09/11/2026). O CSV de 2025 na raiz do projeto continua aceito.
URL_PORTAL_PRF = "https://www.gov.br/prf/pt-br/acesso-a-informacao/dados-abertos/dados-abertos-da-prf"
PASTA_PRF = DADOS_EXTERNOS / "prf"
ANOS_PRF = range(2017, 2026)
ANOS_COBERTOS_PRF = len(ANOS_PRF)
IDS_DRIVE_PRF = {
    2017: "1Kv5mNgZvxtl0xwqsmDrxcaLY2KELxR-3", 2018: "1J-012nSnIafOASNFvIYY_vDKKpM51w5_",
    2019: "1DAJYKVfkTcPhQodSmHp9rsG1Q8XJW-m3", 2020: "1yQtVOsAlupPHQVVTmbJo0NR3XMzgHANO",
    2021: "1Gk3U6cMOZIevsDZHLi6J503xoCRS_lnI", 2022: "1wskEgRC3ame7rncSDQ7qWhKsoKw1lohY",
    2023: "1-caam_dahYOf2eorq4mez04Om6DD5d_3", 2024: "14qBOhrE1gioVtuXgxkCJ9kCA8YtUGXKA",
    2025: "1-PJGRbfSe7PVjU37A3wTCls_NRXyVGRD",
}
BBOX_SC = {"lat": (-29.45, -25.9), "lon": (-53.9, -48.3)}
PANDEMIA = (pd.Timestamp("2020-03-15"), pd.Timestamp("2021-12-31"))

UF = "SC"
CODIGO_IBGE_UF = 42
TAMANHO_TRECHO_KM = 10
TAMANHO_CELULA_CLIMA = 0.25  # graus; agrupa trechos próximos para buscar clima
CORTE_TESTE = {"br": pd.Timestamp("2025-01-01"), "sc": pd.Timestamp("2025-06-01")}  # teste: os 12 meses finais

# 2018 está incompleto no RENAEST; jan–mai/2026 tem volume mensal igual ao de 2025 (base de 12/09/2026)
INICIO_RENAEST, FIM_RENAEST = pd.Timestamp("2019-01-01"), pd.Timestamp("2026-05-31")
ANOS_COBERTOS_RENAEST = ((FIM_RENAEST - INICIO_RENAEST).days + 1) / 365.25
JANELA_NOTIFICACAO_DIAS = 180           # nível de notificação do RENAEST: acidentes em SC nos 180 dias anteriores
DIAS_AQUECIMENTO = 180                  # início da base: histórico do trecho curto demais, fica fora do treino
FRACAO_MIN_REF = 0.5                    # via casada por nome só vira rodovia se a maioria das vias com o nome tem ref

USER_AGENT = "analise-acidentes-sc/0.1 (projeto de estudo)"

# periodo -> (hora inicial, hora final exclusiva)
PERIODOS = {
    "madrugada": (0, 6),
    "manha": (6, 12),
    "tarde": (12, 18),
    "noite": (18, 24),
}
PERIODO_IDX = {nome: i for i, nome in enumerate(PERIODOS)}


def _pascoa(ano: int) -> pd.Timestamp:
    """Domingo de Páscoa (algoritmo de Meeus/Jones/Butcher)."""
    a, b, c = ano % 19, ano // 100, ano % 100
    d, e = b // 4, b % 4
    g = (8 * b + 13) // 25
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 19 * l) // 433
    mes = (h + l - 7 * m + 90) // 25
    return pd.Timestamp(ano, mes, (h + l - 7 * m + 33 * mes + 19) % 32)


def _feriados(anos) -> pd.DatetimeIndex:
    """Feriados nacionais, com Carnaval (segunda e terça), Sexta-feira Santa e Corpus Christi."""
    datas = []
    for ano in anos:
        pascoa = _pascoa(ano)
        fixos = ["01-01", "04-21", "05-01", "09-07", "10-12", "11-02", "11-15", "12-25"]
        if ano >= 2024:
            fixos.append("11-20")  # Consciência Negra virou feriado nacional em 2024
        datas += [pd.Timestamp(f"{ano}-{md}") for md in fixos]
        datas += [pascoa - pd.Timedelta(days=d) for d in (48, 47, 2)] + [pascoa + pd.Timedelta(days=60)]
    return pd.DatetimeIndex(sorted(datas))


# do início do RENAEST até datas que o usuário pode escolher
FERIADOS = _feriados(range(2019, 2028))

# Categorias de clima mostradas na UI. Não há "neblina": o histórico do Open-Meteo (ERA5)
# praticamente não registra códigos de neblina, então o modelo não teria como aprender o efeito.
# Os valores numéricos são recalculados a partir do clima real em treinar.py
# (clima_presets.json); estes são o fallback.
CLIMA_CATEGORIAS = {
    "ceu_claro": {"rotulo": "Céu claro", "chuva_mm": 0.0, "nebulosidade": 10.0},
    "nublado": {"rotulo": "Nublado", "chuva_mm": 0.0, "nebulosidade": 85.0},
    "chuva": {"rotulo": "Chuva", "chuva_mm": 3.0, "nebulosidade": 95.0},
    "chuva_forte": {"rotulo": "Chuva forte", "chuva_mm": 20.0, "nebulosidade": 100.0},
}
LIMIAR_CHUVA_MM = 1.0
LIMIAR_CHUVA_FORTE_MM = 10.0
LIMIAR_NUBLADO = 60.0
