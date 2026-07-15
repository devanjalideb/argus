#!/usr/bin/env bash
# Container startup: wait for MySQL, migrate, seed on first run, then serve.
set -e
cd /app/backend

echo "[argus] waiting for database…"
for i in $(seq 1 30); do
  if python -c "from app.core.database import check_connection,ensure_database_exists; ensure_database_exists(); exit(0 if check_connection() else 1)" 2>/dev/null; then
    echo "[argus] database ready."; break
  fi
  sleep 2
done

echo "[argus] running migrations…"
alembic upgrade head

echo "[argus] seeding on first run…"
python - <<'PY'
from sqlalchemy import select, func
from app.core.database import SessionLocal
from app.models import Customer
from app.synthetic.seed import run_seed
from app.modules.pipeline import run_detection
with SessionLocal() as s:
    n = s.scalar(select(func.count()).select_from(Customer)) or 0
if n == 0:
    print("[argus] generating synthetic ecosystem + investigations…")
    run_seed(reset=True)
    with SessionLocal() as s:
        run_detection(s, reset=True, enrich=True)
else:
    print(f"[argus] existing data found ({n} customers) — skipping seed.")
PY

echo "[argus] starting API on :8000"
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
