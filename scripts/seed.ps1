# Rebuild the demo: reseed ecosystem + re-run every engine.
$root = Split-Path -Parent $PSScriptRoot
$py = "$root\backend\.venv\Scripts\python.exe"
Set-Location "$root\backend"
& $py -m app.synthetic.seed
& $py -c "from app.core.database import SessionLocal; from app.modules.pipeline import run_detection; s=SessionLocal(); run_detection(s, reset=True, enrich=True); s.close(); print('rebuild complete')"
