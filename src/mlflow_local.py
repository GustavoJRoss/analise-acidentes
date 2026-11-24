"""Abre a interface do MLflow sobre o histórico do pipeline.

O banco gravado no GitHub Actions guarda os artefatos com o caminho absoluto do runner
(/home/runner/work/...). Este script copia o banco, troca esse prefixo pelo caminho desta máquina e abre o
`mlflow ui` na cópia, sem alterar o histórico versionado.

  bash mlops.sh --ui            # histórico local (.mlops-local/)
  MLOPS_SAIDA= bash mlops.sh --ui   # histórico do workflow agendado (mlops/ na raiz)
"""
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

from .comum import carregar_config, estado

MARCA = "/mlops/mlartifacts"


def copia_com_caminhos_locais(db: Path) -> Path:
    destino = Path(tempfile.mkdtemp(prefix="mlflow-ui-")) / "mlflow.db"
    shutil.copy(db, destino)
    prefixo_local = "file://" + str(db.parent.parent.resolve())  # pasta que contém mlops/
    con = sqlite3.connect(destino)
    tabelas = [r[0] for r in con.execute("select name from sqlite_master where type='table'")]
    for t in tabelas:
        for _, col, *_ in con.execute(f"pragma table_info('{t}')").fetchall():
            if "artifact" in col.lower():  # experiments.artifact_location, runs.artifact_uri, logged_models…
                con.execute(f"update '{t}' set {col} = ? || substr({col}, instr({col}, ?)) "
                            f"where {col} like 'file://%' || ? || '%'", (prefixo_local, MARCA, MARCA))
    con.commit()
    con.close()
    return destino


def main(porta: str = ""):
    cfg = carregar_config()
    db = estado(cfg, "mlflow_db")
    if not db.exists():
        sys.exit(f"Não há histórico em {db}. Rode um ciclo antes (bash mlops.sh).")
    copia = copia_com_caminhos_locais(db)
    print(f"MLflow sobre {db} (cópia com caminhos locais: {copia})")
    subprocess.run([sys.executable, "-m", "mlflow", "ui", "--backend-store-uri", f"sqlite:///{copia}",
                    "--port", porta or "5000"], check=False)


if __name__ == "__main__":
    main(*(a for a in sys.argv[1:2] if a))
