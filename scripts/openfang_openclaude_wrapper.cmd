@echo off
REM OpenFang -> OpenClaude wrapper shim.
REM Calls openfang_openclaude_wrapper.py with all forwarded args.
REM The Python script re-execs into node + openclaude so stdin stays attached
REM (the patched OpenFang claude_code driver pipes the prompt via stdin).

setlocal

REM Uncomment to dump argv/env to %TEMP%\openfang_openclaude_wrapper.log
REM set "OPENFANG_OPENCLAUDE_DEBUG=1"

set "WRAPPER_PY=%~dp0openfang_openclaude_wrapper.py"

REM Prefer the project venv if it exists, else fall back to system python.
set "VENV_PY=%~dp0..\.venv\Scripts\python.exe"
if exist "%VENV_PY%" (
    "%VENV_PY%" "%WRAPPER_PY%" %*
) else (
    python "%WRAPPER_PY%" %*
)

exit /b %ERRORLEVEL%
