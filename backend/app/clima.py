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
        espera = 60 * (tentativa + 1)  # o limite por hora do plano gratuito pode exigir alguns minutos
        print(f"  Open-Meteo pediu para esperar (429); nova tentativa em {espera}s")
        time.sleep(espera)
    resp.raise_for_status()


def _intervalos_anuais(inicio: str, fim: str) -> list:
    """Quebra o período em anos: cada pedaço vira um lote em cache, e um 429 no meio não perde o resto."""
    inicio, fim = pd.Timestamp(inicio), pd.Timestamp(fim)
    return [(max(inicio, pd.Timestamp(ano, 1, 1)), min(fim, pd.Timestamp(ano, 12, 31)))
            for ano in range(inicio.year, fim.year + 1)]


def _lote_baixado(lote: pd.DataFrame, ini: pd.Timestamp, fim: pd.Timestamp) -> pd.DataFrame:
    params = {
        "latitude": ",".join(lote["celula_lat"].astype(str)),
        "longitude": ",".join(lote["celula_lon"].astype(str)),
        "start_date": ini.strftime("%Y-%m-%d"), "end_date": fim.strftime("%Y-%m-%d"),
        "hourly": VARIAVEIS, "timezone": "America/Sao_Paulo",
    }
    dados = _get_com_retentativa(URL_HISTORICO, params)
    dados = dados if isinstance(dados, list) else [dados]
    partes = []
    for celula, item in zip(lote["celula"], dados):
        periodos = _horario_para_periodos(item["hourly"])
        periodos["celula"] = celula
        partes.append(periodos)
    return pd.concat(partes, ignore_index=True)


def _cobre(clima: pd.DataFrame, celulas: set, inicio: pd.Timestamp, fim: pd.Timestamp) -> bool:
    if clima.empty or not celulas <= set(clima["celula"]):
        return False
    por_celula = clima[clima["celula"].isin(celulas)].groupby("celula")["data"].agg(["min", "max"])
    return bool((por_celula["min"] <= inicio).all() and (por_celula["max"] >= fim).all())


def baixar_historico(celulas: pd.DataFrame, inicio: str, fim: str, artefatos: config.Artefatos,
                     forcar: bool = False) -> pd.DataFrame:
    """celulas: colunas celula, celula_lat, celula_lon. Resultado salvo em artefatos.clima.

    O cache é por ano e por célula (clima_lotes/lote_{ano}_*.parquet): se as células ou o período mudarem,
    só o que falta é baixado. Um 429 no meio não perde nada: é só rodar de novo.
    """
    inicio_ts, fim_ts = pd.Timestamp(inicio), pd.Timestamp(fim)
    celulas = celulas.drop_duplicates("celula").sort_values("celula").reset_index(drop=True)
    pedidas = set(celulas["celula"])
    if artefatos.clima.exists() and not forcar:
        clima = pd.read_parquet(artefatos.clima)
        if _cobre(clima, pedidas, inicio_ts, fim_ts):
            return clima
    artefatos.clima_lotes.mkdir(exist_ok=True)
    partes = []
    for ini, fim_ano in _intervalos_anuais(inicio, fim):
        # o cache é compartilhado entre as redes: uma célula baixada para as estaduais serve para as BRs
        pastas = {artefatos.clima_lotes, *(a.clima_lotes for a in config.REDES.values())}
        arquivos = [] if forcar else sorted(a for p in pastas if p.exists() for a in p.glob(f"lote_{ini.year}_*.parquet"))
        existentes = pd.concat([pd.read_parquet(a) for a in arquivos], ignore_index=True) if arquivos else pd.DataFrame()
        prontas = set()
        if not existentes.empty:
            cobertura = existentes.groupby("celula")["data"].agg(["min", "max"])
            prontas = set(cobertura[(cobertura["min"] <= ini) & (cobertura["max"] >= fim_ano)].index)
            partes.append(existentes[existentes["celula"].isin(pedidas & prontas)])
        faltam = celulas[~celulas["celula"].isin(prontas)].reset_index(drop=True)
        for i in range(0, len(faltam), LOTE):
            lote = faltam.iloc[i:i + LOTE]
            lote_df = _lote_baixado(lote, ini, fim_ano)
            nome = f"lote_{ini.year}_{fim_ano:%m%d}_{lote['celula'].iat[0]}.parquet".replace(",", "_")
            lote_df.to_parquet(artefatos.clima_lotes / nome)
            partes.append(lote_df)
            print(f"  clima {ini.year}: {i + len(lote)} de {len(faltam)} células que faltavam")
            time.sleep(2)  # respeita o limite do serviço gratuito
    clima = pd.concat(partes, ignore_index=True)
    clima = (clima[clima["celula"].isin(pedidas) & clima["data"].between(inicio_ts, fim_ts)]
             .drop_duplicates(["celula", "data", "periodo"]).reset_index(drop=True))
    faltando = clima[["chuva_mm", "nebulosidade", "temperatura"]].isna().mean().max()
    if faltando > 0.01:
        print(f"  AVISO: {faltando:.1%} das linhas de clima sem valor; serão preenchidas pela climatologia")
    clima.to_parquet(artefatos.clima)
    return clima


def climatologia(clima: pd.DataFrame) -> pd.DataFrame:
    """Média de cada variável por célula × mês × período (para preencher buracos e temperatura na API)."""
    return (clima.assign(mes=clima["data"].dt.month)
            .groupby(["celula", "mes", "periodo"])[["chuva_mm", "nebulosidade", "temperatura"]].mean()
            .reset_index())


def preencher_com_climatologia(df: pd.DataFrame, clima: pd.DataFrame) -> pd.DataFrame:
    """Preenche clima ausente em df (colunas celula, data, periodo) com a média da célula no mês e período."""
    variaveis = ["chuva_mm", "nebulosidade", "temperatura"]
    if not df[variaveis].isna().any().any():
        return df
    media = climatologia(clima).rename(columns={v: f"{v}_media" for v in variaveis})
    df = df.assign(mes_clima=df["data"].dt.month).merge(
        media.rename(columns={"mes": "mes_clima"}), on=["celula", "mes_clima", "periodo"], how="left")
    for v in variaveis:
        df[v] = df[v].fillna(df[f"{v}_media"]).fillna(clima[v].mean())
    return df.drop(columns=["mes_clima", *[f"{v}_media" for v in variaveis]])


def categoria_do_clima(chuva_mm: float, nebulosidade: float) -> str:
    if chuva_mm >= config.LIMIAR_CHUVA_FORTE_MM:
        return "chuva_forte"
    if chuva_mm >= config.LIMIAR_CHUVA_MM:
        return "chuva"
    if nebulosidade >= config.LIMIAR_NUBLADO:
        return "nublado"
    return "ceu_claro"


def presets_do_historico(clima: pd.DataFrame) -> dict:
    """Valores típicos de cada categoria, medidos no clima histórico da rede."""
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
