@echo off
REM ============================================================
REM  ARGUS portable launcher  (Windows)
REM  Runs from ANY folder. Uses a local SQLite database, so the
REM  recipient needs ONLY Python 3.11+ (no MySQL, no Node).
REM ============================================================
setlocal
cd /d "%~dp0"
set "ROOT=%~dp0"
set "PY=%ROOT%backend\.venv\Scripts\python.exe"

echo ================================================
echo    ARGUS - portable launcher (SQLite mode)
echo ================================================
echo.

REM --- locate Python even if python.exe was not added to PATH ---
set "PYCMD="
python --version >nul 2>&1 && set "PYCMD=python"
if not defined PYCMD py --version >nul 2>&1 && set "PYCMD=py"
if not defined PYCMD if exist "%LocalAppData%\Programs\Python\Python313\python.exe" set "PYCMD=%LocalAppData%\Programs\Python\Python313\python.exe"
if not defined PYCMD if exist "%LocalAppData%\Programs\Python\Python312\python.exe" set "PYCMD=%LocalAppData%\Programs\Python\Python312\python.exe"
if not defined PYCMD if exist "%LocalAppData%\Programs\Python\Python311\python.exe" set "PYCMD=%LocalAppData%\Programs\Python\Python311\python.exe"
if not defined PYCMD if exist "%ProgramFiles%\Python313\python.exe" set "PYCMD=%ProgramFiles%\Python313\python.exe"
if not defined PYCMD (
  echo [ERROR] Python 3.11+ was not found.
  echo   - If it IS installed, re-run the python.org installer, choose "Modify",
  echo     and tick "Add Python to environment variables".
  echo   - Otherwise install it from https://www.python.org/downloads/
  echo     ^(tick "Add python.exe to PATH"^).
  echo.
  pause
  exit /b 1
)
echo Using Python: %PYCMD%

if not exist "%PY%" (
  echo [1/4] Creating Python environment ^(first run only, ~2 min, needs internet^)...
  "%PYCMD%" -m venv "%ROOT%backend\.venv"
  "%PY%" -m pip install --upgrade pip
  "%PY%" -m pip install -r "%ROOT%backend\requirements.txt"
) else (
  echo [1/4] Python environment ready.
)

REM Portable SQLite DB (absolute path, forward slashes for the URL).
set "ROOTS=%ROOT:\=/%"
set "DATABASE_URL=sqlite:///%ROOTS%backend/argus_portable.db"

cd /d "%ROOT%backend"
echo [2/4] Building database schema...
"%PY%" -c "from app.core.database import create_all; create_all()"

echo [3/4] Seeding demo data ^(first run only^)...
"%PY%" -c "from sqlalchemy import select,func; from app.core.database import SessionLocal; from app.models import Customer; s=SessionLocal(); n=s.scalar(select(func.count()).select_from(Customer)) or 0; s.close(); exit(0 if n else 7)"
if errorlevel 7 (
  "%PY%" -m app.synthetic.seed
  "%PY%" -c "from app.core.database import SessionLocal; from app.modules.pipeline import run_detection; s=SessionLocal(); run_detection(s, reset=True, enrich=True); s.close()"
)

echo [4/4] Starting ARGUS...
start "ARGUS server" cmd /c ""%PY%" -m uvicorn app.main:app --host 127.0.0.1 --port 8000"
timeout /t 6 /nobreak >nul
start "" http://localhost:8000
echo.
echo ================================================
echo   ARGUS is running at http://localhost:8000
echo   Keep the "ARGUS server" window open.
echo   Close it to stop ARGUS.
echo ================================================
timeout /t 5 /nobreak >nul
exit /b 0
