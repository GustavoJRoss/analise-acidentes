"""Configuração, estado do ciclo e MLflow: compartilhados pelos notebooks 01–05."""
import json
import os
import sys
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parents[1]
# o código do modelo (features, clima, avaliação) vive em backend/ e é reaproveitado sem cópia
if str(RAIZ / "backend") not in sys.path:
    sys.path.insert(0, str(RAIZ / "backend"))

os.environ.setdefault("MLFLOW_DISABLE_AGENT_HINT", "1")


def carregar_config(caminho: Path = RAIZ / "config" / "config.yaml") -> dict:
    return yaml.safe_load(Path(caminho).read_text())


def caminho(rel: str) -> Path:
    """Caminho relativo à raiz do repositório (os notebooks rodam dentro de notebooks/)."""
    return RAIZ / rel


def estado(cfg, chave: str) -> Path:
    """Caminho de estado do pipeline (estado do ciclo, modelos, MLflow, evidências, dados processados).

    No GitHub Actions é a própria raiz, e o estado é commitado. Localmente, `mlops.sh` define MLOPS_SAIDA
    (ex.: .mlops-local/) para que testes locais nunca misturem histórico com o do workflow agendado.
    """
    base = Path(os.environ["MLOPS_SAIDA"]) if os.environ.get("MLOPS_SAIDA") else RAIZ
    if not base.is_absolute():
        base = RAIZ / base
    return base / cfg["caminhos"][chave]


def _arq_ciclo(cfg) -> Path:
    return estado(cfg, "estado") / "ciclo_atual.json"


def ler_ciclo(cfg) -> dict:
    return json.loads(_arq_ciclo(cfg).read_text())


def salvar_ciclo(cfg, ciclo: dict) -> None:
    arq = _arq_ciclo(cfg)
    arq.parent.mkdir(parents=True, exist_ok=True)
    arq.write_text(json.dumps(ciclo, ensure_ascii=False, indent=2))


def atualizar_ciclo(cfg, **campos) -> dict:
    ciclo = ler_ciclo(cfg) | campos
    salvar_ciclo(cfg, ciclo)
    return ciclo


def gatilho() -> str:
    """schedule | workflow_dispatch | local: vai como tag em todo run (prova da execução agendada)."""
    return os.environ.get("GITHUB_EVENT_NAME", "local")


def configurar_mlflow(cfg):
    import mlflow
    db = estado(cfg, "mlflow_db")
    db.parent.mkdir(parents=True, exist_ok=True)
    mlflow.set_tracking_uri(f"sqlite:///{db}")
    nome = cfg["projeto"]["experimento_mlflow"]
    if mlflow.get_experiment_by_name(nome) is None:
        # artefatos ao lado do banco, dentro do repositório (versionados junto com ele pelo workflow)
        mlflow.create_experiment(nome, artifact_location=estado(cfg, "mlflow_artefatos").as_uri())
    mlflow.set_experiment(nome)
    return mlflow


def tags_ciclo(ciclo: dict, **extra) -> dict:
    return {"cycle_id": ciclo["cycle_id"], "data_version": ciclo["data_version"], "gatilho": gatilho(),
            "git_sha": os.environ.get("GITHUB_SHA", "local"), **extra}


def pasta_evidencias(cfg, ciclo: dict) -> Path:
    pasta = estado(cfg, "evidencias") / ciclo["cycle_id"]
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta
