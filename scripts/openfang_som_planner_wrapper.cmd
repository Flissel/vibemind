@echo off
REM OpenFang -> SoM-Planner bridge shim.
REM Reads the intent from stdin (OpenFang claude_code driver pipes it), delegates
REM to openfang_som_planner_wrapper.py which runs the full SoM pipeline
REM (som_core.run) and returns a spoken German summary. Uses voice/.venv312
REM (has autogen + pydantic that som_core needs).

setlocal

set "WRAPPER_PY=%~dp0openfang_som_planner_wrapper.py"

set "VENV_PY=%~dp0..\vibemind-os\voice\.venv312\Scripts\python.exe"
if exist "%VENV_PY%" (
    "%VENV_PY%" "%WRAPPER_PY%" %*
) else (
    python "%WRAPPER_PY%" %*
)

exit /b %ERRORLEVEL%
