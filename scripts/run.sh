#!/usr/bin/env bash
# Setup + run ARGUS on macOS/Linux. Prereqs: Python 3.11+, Node 18+, MySQL.
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="$ROOT/backend/.venv/bin/python"

if [ ! -x "$PY" ]; then
  echo "== Backend venv =="
  python3 -m venv "$ROOT/backend/.venv"
  "$PY" -m pip install --upgrade pip
  "$PY" -m pip install -r "$ROOT/backend/requirements.txt"
fi

if [ ! -d "$ROOT/frontend/dist" ]; then
  echo "== Frontend build =="
  (cd "$ROOT/frontend" && npm install && npm run build)
fi

[ -f "$ROOT/backend/.env" ] || cp "$ROOT/backend/.env.example" "$ROOT/backend/.env"

cd "$ROOT/backend"
"$PY" -m alembic upgrade head
"$PY" -c "from sqlalchemy import select,func; from app.core.database import SessionLocal; from app.models import Customer; s=SessionLocal(); n=s.scalar(select(func.count()).select_from(Customer)) or 0; s.close(); exit(1) if n==0 else exit(0)" \
  || { "$PY" -m app.synthetic.seed; "$PY" -c "from app.core.database import SessionLocal; from app.modules.pipeline import run_detection; s=SessionLocal(); run_detection(s, reset=True, enrich=True); s.close()"; }

echo "ARGUS -> http://localhost:8000"
exec "$PY" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
