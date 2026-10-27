"""Constantes compartilhadas entre preparação, treino e API."""
from pathlib import Path

import pandas as pd

BACKEND_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = BACKEND_DIR.parent
CSV_PATH = ROOT_DIR / "acidentes2025_todas_causas_tipos.csv"
ARTIFACTS = BACKEND_DIR / "artifacts"

ARQ_ACIDENTES = ARTIFACTS / "acidentes.parquet"
ARQ_OSM_BRUTO = ARTIFACTS / "osm_brs.json"
ARQ_TRECHOS_GEOJSON = ARTIFACTS / "trechos.geojson"
ARQ_PONTOS_VIA = ARTIFACTS / "pontos_via.parquet"
ARQ_CLIMA = ARTIFACTS / "clima.parquet"
ARQ_MODELO = ARTIFACTS / "modelo.joblib"
ARQ_ESTADO = ARTIFACTS / "estado_trechos.parquet"
ARQ_CLIMATOLOGIA = ARTIFACTS / "climatologia.parquet"
ARQ_METRICAS = ARTIFACTS / "metricas.json"
ARQ_PRESETS_CLIMA = ARTIFACTS / "clima_presets.json"

UF = "SC"
TAMANHO_TRECHO_KM = 10
TAMANHO_CELULA_CLIMA = 0.25  # graus; agrupa trechos próximos para buscar clima
CORTE_TESTE = pd.Timestamp("2025-10-01")

USER_AGENT = "analise-acidentes-sc/0.1 (projeto de estudo)"

# periodo -> (hora inicial, hora final exclusiva)
PERIODOS = {
    "madrugada": (0, 6),
    "manha": (6, 12),
    "tarde": (12, 18),
    "noite": (18, 24),
}
PERIODO_IDX = {nome: i for i, nome in enumerate(PERIODOS)}

# Feriados nacionais (inclui Carnaval). 2026–2027 para datas escolhidas pelo usuário.
FERIADOS = pd.to_datetime([
    "2025-01-01", "2025-03-03", "2025-03-04", "2025-04-18", "2025-04-21", "2025-05-01",
    "2025-06-19", "2025-09-07", "2025-10-12", "2025-11-02", "2025-11-15", "2025-11-20", "2025-12-25",
    "2026-01-01", "2026-02-16", "2026-02-17", "2026-04-03", "2026-04-21", "2026-05-01",
    "2026-06-04", "2026-09-07", "2026-10-12", "2026-11-02", "2026-11-15", "2026-11-20", "2026-12-25",
    "2027-01-01", "2027-02-08", "2027-02-09", "2027-03-26", "2027-04-21", "2027-05-01",
    "2027-05-27", "2027-09-07", "2027-10-12", "2027-11-02", "2027-11-15", "2027-11-20", "2027-12-25",
])

# Categorias de clima mostradas na UI. Não há "neblina": o histórico do Open-Meteo (ERA5)
# praticamente não registra códigos de neblina, então o modelo não teria como aprender o efeito.
# Os valores numéricos são recalculados a partir do clima real de 2025 em treinar.py
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
