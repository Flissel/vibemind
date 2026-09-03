@echo off
REM OpenFang -> openclaw wrapper shim.
REM Calls openfang_openclaw_wrapper.py; it reads the prompt from stdin (the
REM patched OpenFang claude_code driver pipes it there) and invokes the
REM openclaw embedded agent inside the vibemind-openclaw container.

setlocal

REM Uncomment to dump argv/msg to %TEMP%\openfang_openclaw_wrapper.log
REM set "OPENFANG_OPENCLAW_DEBUG=1"

set "WRAPPER_PY=%~dp0openfang_openclaw_wrapper.py"

set "VENV_PY=%~dp0..\.venv\Scripts\python.exe"
if exist "%VENV_PY%" (
    "%VENV_PY%" "%WRAPPER_PY%" %*
) else (
    python "%WRAPPER_PY%" %*
)

exit /b %ERRORLEVEL%
