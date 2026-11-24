"""Entrada e versionamento dos dados de cada ciclo.

Os acidentes chegam por replay cronológico: uma base inicial (2017 → dez/2023) e um lote por mês de 2024, consumido
um por ciclo agendado. 2025 fica reservado para a avaliação final. Os arquivos guardam as linhas BRUTAS da PRF
(uma por pessoa envolvida, colunas como texto, só SC): a limpeza é refeita no notebook 01 a cada ciclo. Um arquivo
real novo da PRF pode entrar como lote (`data/raw/lotes/AAAA-MM.parquet`) sem mudar o código.
"""
import hashlib
import json
import os
import shutil
from datetime import datetime, timezone

import pandas as pd

from .comum import RAIZ, caminho, estado, salvar_ciclo

ORIGEM_ARTEFATOS = RAIZ / "backend" / "artifacts"


def preparar_raw(cfg) -> dict:
    """Uma vez, localmente: lê os CSV/ZIP originais da PRF (2017–2025), guarda só as linhas de SC, sem limpeza, e
    corta em base inicial, lotes mensais e teste reservado. Requer as bases baixadas por backend/scripts/preparar_dados.
    """
    from app import dados
    d = cfg["dados"]
    pessoas = pd.concat([dados._pessoas_sc(dados.arquivo_prf(a)) for a in range(2017, 2026)], ignore_index=True)
    data = dados._data(pessoas["data_inversa"])
    inicio_lotes, inicio_teste = pd.Timestamp(d["inicio_lotes"]), pd.Timestamp(d["inicio_teste"])

    pasta_lotes = caminho(d["lotes"])
    pasta_lotes.mkdir(parents=True, exist_ok=True)
    pessoas[data < inicio_lotes].to_parquet(caminho(d["base_inicial"]), index=False)
    pessoas[data >= inicio_teste].to_parquet(caminho(d["teste_reservado"]), index=False)
    replay = (data >= inicio_lotes) & (data < inicio_teste)
    contagem = {}
    for mes, lote in pessoas[replay].groupby(data[replay].dt.strftime("%Y-%m")):
        lote.to_parquet(pasta_lotes / f"{mes}.parquet", index=False)
        contagem[mes] = len(lote)
    # trechos (geometria OSM + VMD) e clima diário (Open-Meteo) são insumos fixos, já preparados pelo backend
    shutil.copy(ORIGEM_ARTEFATOS / "trechos.parquet", caminho(d["trechos"]))
    shutil.copy(ORIGEM_ARTEFATOS / "clima.parquet", caminho(d["clima"]))
    return {"base_inicial": int((data < inicio_lotes).sum()), "lotes": contagem,
            "teste_reservado": int((data >= inicio_teste).sum())}


def lotes_disponiveis(cfg) -> list[str]:
    return sorted(p.stem for p in caminho(cfg["dados"]["lotes"]).glob("*.parquet"))


def _arq_consumidos(cfg):
    return estado(cfg, "estado") / "lotes_consumidos.json"


def lotes_consumidos(cfg) -> list[str]:
    arq = _arq_consumidos(cfg)
    return json.loads(arq.read_text())["lotes"] if arq.exists() else []


def proximos_lotes(disponiveis: list[str], consumidos: list[str], primeiro_ciclo: bool, n: int) -> list[str]:
    """O 1º ciclo usa só a base inicial; os seguintes consomem os n próximos lotes ainda não usados."""
    if primeiro_ciclo:
        return []
    return [l for l in disponiveis if l not in consumidos][:n]


CHAVE = ["id", "pesid"]  # uma linha bruta da PRF = um acidente × uma pessoa


def unir_sem_duplicar(partes: list[pd.DataFrame], chave=CHAVE) -> tuple[pd.DataFrame, int]:
    """Concatena base + lotes e remove linhas repetidas (mesmo acidente e pessoa), por exemplo um lote reenviado.
    Devolve (dados, linhas duplicadas removidas)."""
    todos = pd.concat(partes, ignore_index=True)
    unicos = todos.drop_duplicates(chave, keep="first").reset_index(drop=True)
    return unicos, len(todos) - len(unicos)


def versao_dos_dados(ids: pd.Series, ultimo_lote: str | None) -> str:
    """Identificador determinístico: o mesmo conjunto de acidentes gera sempre a mesma data_version."""
    unicos = pd.to_numeric(pd.Series(ids), errors="coerce").dropna().astype("int64").drop_duplicates().sort_values()
    h = hashlib.sha256(unicos.to_numpy().tobytes()).hexdigest()[:8]
    return f"v{ultimo_lote or 'base'}-{h}"


def fim_dos_dados(cfg, lotes: list[str]) -> pd.Timestamp:
    """Último dia coberto pelos dados do ciclo (fim do mês do último lote, ou véspera do 1º lote)."""
    if lotes:
        return pd.Timestamp(lotes[-1]) + pd.offsets.MonthEnd(0)
    return pd.Timestamp(cfg["dados"]["inicio_lotes"]) - pd.Timedelta(days=1)


def carregar_brutos(cfg, lotes: list[str], incluir_teste: bool = False) -> tuple[pd.DataFrame, int]:
    """Linhas brutas (por pessoa) da base inicial + lotes [+ teste reservado], sem duplicatas."""
    partes = [pd.read_parquet(caminho(cfg["dados"]["base_inicial"]))]
    partes += [pd.read_parquet(caminho(cfg["dados"]["lotes"]) / f"{l}.parquet") for l in lotes]
    if incluir_teste:
        partes.append(pd.read_parquet(caminho(cfg["dados"]["teste_reservado"])))
    return unir_sem_duplicar(partes)


def acidentes_limpos(cfg, lotes: list[str], incluir_teste: bool = False) -> pd.DataFrame:
    """Atalho do notebook 05: brutos → limpeza da PRF (uma linha por acidente)."""
    from app import dados
    return dados.limpar_pessoas(carregar_brutos(cfg, lotes, incluir_teste)[0])


def iniciar_ciclo(cfg) -> tuple[dict, pd.DataFrame]:
    """Define os lotes do ciclo, carrega as linhas brutas, gera cycle_id e data_version e grava o estado do ciclo."""
    consumidos = lotes_consumidos(cfg)
    primeiro = not _arq_consumidos(cfg).exists()
    novos = proximos_lotes(lotes_disponiveis(cfg), consumidos, primeiro, cfg["dados"]["lotes_por_ciclo"])
    lotes = consumidos + novos
    brutos, duplicatas = carregar_brutos(cfg, lotes)
    from app import dados
    mes_bruto = dados._data(brutos["data_inversa"]).dt.strftime("%Y-%m")

    agora = datetime.now(timezone.utc)
    cycle_id = os.environ.get("CYCLE_ID") or f"local-{agora:%Y%m%d-%H%M%S}"
    ciclo = {
        "cycle_id": cycle_id,
        "data_version": versao_dos_dados(brutos["id"], lotes[-1] if lotes else None),
        "iniciado_em": agora.isoformat(timespec="seconds"),
        "lotes": lotes,
        "lotes_novos": novos,
        "fim_dos_dados": str(fim_dos_dados(cfg, lotes).date()),
        "linhas_brutas": len(brutos),
        "linhas_brutas_novas": int(mes_bruto.isin(novos).sum()),
        "duplicatas_removidas": duplicatas,
        "primeiro_ciclo": primeiro,
    }
    salvar_ciclo(cfg, ciclo)
    _arq_consumidos(cfg).write_text(json.dumps({"lotes": lotes, "atualizado_em": ciclo["iniciado_em"]}, indent=2))
    return ciclo, brutos
