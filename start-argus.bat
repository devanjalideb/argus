@echo off
title ARGUS launcher
echo ================================================
echo    ARGUS - AI Cyber Decision Intelligence
echo ================================================
echo.

echo [1/3] Ensuring MySQL is running...
REM Best-effort start of whichever MySQL service exists (harmless if already running).
net start MySQL80 >nul 2>&1
net start MySQL8  >nul 2>&1
net start MySQL   >nul 2>&1
echo       done (if it was already running, that is fine).
echo.

echo [2/3] Starting the ARGUS server...
start "ARGUS server" "C:\Users\ravin\OneDrive\Desktop\Claude Code\ARGUS\backend\.venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --app-dir "C:\Users\ravin\OneDrive\Desktop\Claude Code\ARGUS\backend"
echo.

echo [3/3] Opening http://localhost:8000 ...
timeout /t 5 /nobreak >nul
start "" http://localhost:8000
echo.

echo ================================================
echo   ARGUS is running at http://localhost:8000
echo   Keep the "ARGUS server" window OPEN.
echo   Close that window to stop ARGUS.
echo   If the app shows "DB offline", start MySQL
echo   via services.msc (MySQL80) and refresh.
echo ================================================
timeout /t 5 /nobreak >nul
exit
