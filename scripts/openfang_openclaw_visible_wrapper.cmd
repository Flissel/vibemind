@echo off
REM OpenFang -> openclaw VISIBLE-browser wrapper shim.
REM Sibling of openfang_openclaw_wrapper.cmd. Calls
REM openfang_openclaw_visible_wrapper.py; it reads the prompt from stdin (the
REM patched OpenFang claude_code driver pipes it there) and routes the agent
REM turn through the NATIVE openclaw Gateway (ws://127.0.0.1:18793) so the
REM agent's browser tool drives a VISIBLE Chrome window on the host PC.

setlocal

REM Uncomment to dump argv/msg to %TEMP%\openfang_openclaw_visible.log
REM set "OPENFANG_OPENCLAW_DEBUG=1"

set "WRAPPER_PY=%~dp0openfang_openclaw_visible_wrapper.py"

set "VENV_PY=%~dp0..\.venv\Scripts\python.exe"
if exist "%VENV_PY%" (
    "%VENV_PY%" "%WRAPPER_PY%" %*
) else (
    python "%WRAPPER_PY%" %*
)

exit /b %ERRORLEVEL%
