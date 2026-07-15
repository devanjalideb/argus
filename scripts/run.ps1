# Start ARGUS (serves the API + compiled UI at http://localhost:8000).
$root = Split-Path -Parent $PSScriptRoot
$py = "$root\backend\.venv\Scripts\python.exe"
Set-Location "$root\backend"
Write-Host "ARGUS -> http://localhost:8000  (Ctrl+C to stop)" -ForegroundColor Green
& $py -m uvicorn app.main:app --host 127.0.0.1 --port 8000
