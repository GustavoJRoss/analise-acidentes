#!/usr/bin/env bash
# Sobe o backend (FastAPI, porta 8000) e o frontend (Next, porta 3000) juntos.
# Uso: bash rodar.sh   (Ctrl+C derruba os dois)
set -e
cd "$(dirname "$0")"

backend/.venv/bin/uvicorn app.main:app --app-dir backend --reload --reload-dir backend/app --port 8000 &
BACKEND_PID=$!
trap 'kill $BACKEND_PID 2>/dev/null' EXIT INT TERM

pnpm --dir frontend dev
