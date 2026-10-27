"""Clima por célula (~0,25°) e período do dia, via Open-Meteo.

- Histórico (archive-api): usado no treino, para o modelo ver o clima de TODOS os dias,
  não só dos dias com acidente.
- Previsão (api): usado na UI para pré-preencher o clima de datas próximas.
"""
import time

import httpx
import numpy as np
import pandas as pd

from . import config
from .dados import periodo_da_hora

URL_HISTORICO = "https://archive-api.open-meteo.com/v1/archive"
URL_PREVISAO = "https://api.open-meteo.com/v1/forecast"
VARIAVEIS = "precipitation,cloud_cover,temperature_2m"
LOTE = 10  # coordenadas por requisição


def _horario_para_periodos(hourly: dict) -> pd.DataFrame:
    df = pd.DataFrame(hourly)
    df["time"] = pd.to_datetime(df["time"])
    df["data"] = df["time"].dt.normalize()
    df["periodo"] = periodo_da_hora(df["time"].dt.hour)
    return (df.groupby(["data", "periodo"], observed=True)
            .agg(chuva_mm=("precipitation", "sum"), nebulosidade=("cloud_cover", "mean"),
                 temperatura=("temperature_2m", "mean"))
            .reset_index())


def _get_com_retentativa(url: str, params: dict, tentativas: int = 8) -> dict:
    for tentativa in range(tentativas):
        resp = httpx.get(url, params=params, timeout=120, headers={"User-Agent": config.USER_AGENT})
        if resp.status_code != 429:
            resp.raise_for_status()
            return resp.json()
        espera = 30 * (tentativa + 1)
        print(f"  Open-Meteo pediu para esperar (429); nova tentativa em {espera}s")
        time.sleep(espera)
    resp.raise_for_status()


def baixar_historico(celulas: pd.DataFrame, inicio: str, fim: str, forcar: bool = False) -> pd.DataFrame:
    """celulas: colunas celula, celula_lat, celula_lon."""
    if config.ARQ_CLIMA.exists() and not forcar:
        return pd.read_parquet(config.ARQ_CLIMA)
    # lotes já baixados ficam em artifacts/clima_lotes/, para retomar após um 429
    pasta_lotes = config.ARTIFACTS / "clima_lotes"
    pasta_lotes.mkdir(exist_ok=True)
    partes = []
    celulas = celulas.drop_duplicates("celula").reset_index(drop=True)
    for i in range(0, len(celulas), LOTE):
        arq_lote = pasta_lotes / f"lote_{i:04d}.parquet"
        if arq_lote.exists() and not forcar:
            partes.append(pd.read_parquet(arq_lote))
            continue
        lote = celulas.iloc[i:i + LOTE]
        params = {
            "latitude": ",".join(lote["celula_lat"].astype(str)),
            "longitude": ",".join(lote["celula_lon"].astype(str)),
            "start_date": inicio, "end_date": fim, "hourly": VARIAVEIS,
            "timezone": "America/Sao_Paulo",
        }
        dados = _get_com_retentativa(URL_HISTORICO, params)
        dados = dados if isinstance(dados, list) else [dados]
        lote_df = []
        for celula, item in zip(lote["celula"], dados):
            periodos = _horario_para_periodos(item["hourly"])
            periodos["celula"] = celula
            lote_df.append(periodos)
        lote_df = pd.concat(lote_df, ignore_index=True)
        lote_df.to_parquet(arq_lote)
        partes.append(lote_df)
        time.sleep(2)  # respeita o limite do serviço gratuito
    clima = pd.concat(partes, ignore_index=True)
    clima[["chuva_mm", "nebulosidade", "temperatura"]] = clima[["chuva_mm", "nebulosidade", "temperatura"]].fillna(0)
    clima.to_parquet(config.ARQ_CLIMA)
    return clima


def categoria_do_clima(chuva_mm: float, nebulosidade: float) -> str:
    if chuva_mm >= config.LIMIAR_CHUVA_FORTE_MM:
        return "chuva_forte"
    if chuva_mm >= config.LIMIAR_CHUVA_MM:
        return "chuva"
    if nebulosidade >= config.LIMIAR_NUBLADO:
        return "nublado"
    return "ceu_claro"


def presets_do_historico(clima: pd.DataFrame) -> dict:
    """Valores típicos de cada categoria, medidos no clima real de 2025."""
    presets = {k: dict(v) for k, v in config.CLIMA_CATEGORIAS.items()}
    cat = np.array([categoria_do_clima(c, n) for c, n in zip(clima["chuva_mm"], clima["nebulosidade"])])
    for nome in presets:
        grupo = clima[cat == nome]
        if len(grupo) >= 30:
            presets[nome]["chuva_mm"] = round(float(grupo["chuva_mm"].median()), 2)
            presets[nome]["nebulosidade"] = round(float(grupo["nebulosidade"].median()), 1)
        presets[nome]["frequencia"] = round(float((cat == nome).mean()), 4)
    return presets


def previsao(lat: float, lon: float, data: pd.Timestamp, periodo: str) -> dict:
    """Clima previsto para um ponto, dia e período (até 16 dias à frente)."""
    params = {"latitude": lat, "longitude": lon, "hourly": VARIAVEIS, "timezone": "America/Sao_Paulo",
              "start_date": data.strftime("%Y-%m-%d"), "end_date": data.strftime("%Y-%m-%d")}
    resp = httpx.get(URL_PREVISAO, params=params, timeout=20, headers={"User-Agent": config.USER_AGENT})
    resp.raise_for_status()
    periodos = _horario_para_periodos(resp.json()["hourly"])
    linha = periodos[periodos["periodo"] == periodo].iloc[0]
    valores = {"chuva_mm": round(float(linha["chuva_mm"]), 2),
               "nebulosidade": round(float(linha["nebulosidade"]), 1),
               "temperatura": round(float(linha["temperatura"]), 1)}
    valores["categoria"] = categoria_do_clima(valores["chuva_mm"], valores["nebulosidade"])
    return valores
