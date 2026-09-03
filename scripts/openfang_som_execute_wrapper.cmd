@echo off
REM OpenFang -> SoM-Execute bridge shim.
REM "fuehre den Plan aus" -> Brain (som_execute capability) -> openfang:som-execute
REM -> dieser Shim. Liest den Befehl vom stdin, nimmt den juengsten ready-Plan,
REM startet die Ausfuehrung detached (Schritte dauern Minuten). Uses voice/.venv312.

setlocal

set "WRAPPER_PY=%~dp0openfang_som_execute_wrapper.py"

set "VENV_PY=%~dp0..\vibemind-os\voice\.venv312\Scripts\python.exe"
if exist "%VENV_PY%" (
    "%VENV_PY%" "%WRAPPER_PY%" %*
) else (
    python "%WRAPPER_PY%" %*
)

exit /b %ERRORLEVEL%
