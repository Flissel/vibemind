@echo off
REM openfang_watchdog — keep OpenFang daemon alive.
REM
REM Usage:
REM   openfang_watchdog              # default: poll every 60s in foreground
REM   openfang_watchdog --once       # single check + exit
REM
REM Start in background (detached) from PowerShell:
REM   Start-Process -FilePath "scripts\openfang_watchdog.cmd" -WindowStyle Hidden
REM
REM Stop a running background watchdog:
REM   tasklist | findstr python.exe   # find the watchdog pid
REM   taskkill /PID <pid> /F

setlocal

set "VENV_PY=%~dp0..\.venv\Scripts\python.exe"
set "WATCHDOG=%~dp0openfang_watchdog.py"

if exist "%VENV_PY%" (
    "%VENV_PY%" "%WATCHDOG%" %*
) else (
    python "%WATCHDOG%" %*
)

exit /b %ERRORLEVEL%
