# ARGUS one-time setup (Windows / PowerShell).
# Prereqs: Python 3.11+, Node 18+, a running MySQL with MYSQL_PASSWORD set in backend\.env
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$py = "$root\backend\.venv\Scripts\python.exe"

Write-Host "== [1/4] Backend virtual environment ==" -ForegroundColor Cyan
python -m venv "$root\backend\.venv"
& $py -m pip install --upgrade pip
& $py -m pip install -r "$root\backend\requirements.txt"

Write-Host "== [2/4] Frontend build ==" -ForegroundColor Cyan
Push-Location "$root\frontend"
npm install
npm run build
Pop-Location

Write-Host "== [3/4] Database migrate ==" -ForegroundColor Cyan
if (-not (Test-Path "$root\backend\.env")) {
  Copy-Item "$root\backend\.env.example" "$root\backend\.env"
  Write-Host "  Created backend\.env — set MYSQL_PASSWORD before continuing." -ForegroundColor Yellow
}
Push-Location "$root\backend"
& $py -m alembic upgrade head

Write-Host "== [4/4] Seed ecosystem + run engines ==" -ForegroundColor Cyan
& $py -m app.synthetic.seed
& $py -c "from app.core.database import SessionLocal; from app.modules.pipeline import run_detection; s=SessionLocal(); run_detection(s, reset=True, enrich=True); s.close(); print('detection complete')"
Pop-Location

Write-Host "`nSetup complete. Start ARGUS with:  .\scripts\run.ps1" -ForegroundColor Green
