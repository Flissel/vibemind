@echo off
REM OpenFang -> SoM-Team bridge shim (Phase B, insane handler).
REM Reads the intent from stdin (OpenFang claude_code driver pipes it), delegates
REM to openfang_som_team_wrapper.py which builds a dynamic capability SelectorGroupChat
REM (som_team_runner.run) and returns a spoken result. Uses voice/.venv312.

setlocal

set "WRAPPER_PY=%~dp0openfang_som_team_wrapper.py"

set "VENV_PY=%~dp0..\vibemind-os\voice\.venv312\Scripts\python.exe"
if exist "%VENV_PY%" (
    "%VENV_PY%" "%WRAPPER_PY%" %*
) else (
    python "%WRAPPER_PY%" %*
)

exit /b %ERRORLEVEL%
