@echo off
setlocal

set "WRAPPER_PY=%~dp0openfang_claude_subscription_wrapper.py"
set "VENV_PY=%~dp0..\.venv\Scripts\python.exe"
if exist "%VENV_PY%" (
    "%VENV_PY%" "%WRAPPER_PY%" %*
) else (
    python "%WRAPPER_PY%" %*
)

exit /b %ERRORLEVEL%
