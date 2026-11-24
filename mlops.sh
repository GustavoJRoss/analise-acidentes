#!/usr/bin/env bash
# Roda um ciclo do pipeline MLOps (notebooks 01→05) localmente, na mesma ordem do workflow agendado.
#
#   bash mlops.sh              # estado em .mlops-local/ (não mistura com o histórico do GitHub Actions)
#   MLOPS_SAIDA= bash mlops.sh # grava na raiz, como o workflow (models/, mlops/, data/estado/, evidencias/)
#   bash mlops.sh --limpar     # apaga .mlops-local/ e recomeça do primeiro ciclo
#   bash mlops.sh 01_etl       # só os notebooks indicados (o workflow roda um por passo, com o mesmo CYCLE_ID)
#   bash mlops.sh --ui         # abre o MLflow (também o histórico vindo do GitHub Actions, com caminhos ajustados)
set -euo pipefail
cd "$(dirname "$0")"
export MLOPS_SAIDA="${MLOPS_SAIDA-.mlops-local}"
export MLFLOW_DISABLE_AGENT_HINT=1
PY="${PYTHON:-.venv/bin/python3.12}"
command -v "$PY" >/dev/null || PY=python3

if [ "${1:-}" = "--limpar" ]; then rm -rf .mlops-local; echo "estado local apagado"; exit 0; fi
if [ "${1:-}" = "--ui" ]; then exec "$PY" -m src.mlflow_local "${2:-}"; fi

CICLO="${CYCLE_ID:-local-$(date -u +%Y%m%d-%H%M%S)}"
export CYCLE_ID="$CICLO"
SAIDA_NB="${MLOPS_SAIDA:-.}/evidencias/$CICLO/notebooks"
mkdir -p "$SAIDA_NB"
if [ $# -gt 0 ]; then NOTEBOOKS=("$@")
else NOTEBOOKS=(01_etl 02_votacao_features 03_treino_competicao 04_selecao_promocao 05_previsoes); fi
for nb in "${NOTEBOOKS[@]}"; do
  echo "== $nb"
  "$PY" -m jupyter nbconvert --to notebook --execute "notebooks/$nb.ipynb" \
    --output-dir "$SAIDA_NB" --ExecutePreprocessor.timeout=1800
done
echo "ciclo $CICLO: ${NOTEBOOKS[*]} concluído(s). Para ver no MLflow: bash mlops.sh --ui"
