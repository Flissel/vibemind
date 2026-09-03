@echo off
REM OpenFang -> Buergergeld-Pipeline bridge shim.
REM Calls openfang_buergergeld_wrapper.py; it reads the intent from stdin
REM (the patched OpenFang claude_code driver pipes it there), routes it to
REM the right skills/buergergeld pipeline (status / vorbereiten / parse) and
REM returns a spoken German reply. Stops at the approval gate — sends nothing.

setlocal

set "WRAPPER_PY=%~dp0openfang_buergergeld_wrapper.py"

set "VENV_PY=%~dp0..\.venv\Scripts\python.exe"
if exist "%VENV_PY%" (
    "%VENV_PY%" "%WRAPPER_PY%" %*
) else (
    python "%WRAPPER_PY%" %*
)

exit /b %ERRORLEVEL%
