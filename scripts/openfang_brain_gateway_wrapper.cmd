@echo off
REM OpenFang -> Brain capability-pipeline bridge shim.
REM Calls openfang_brain_gateway_wrapper.py; it reads the channel message
REM from stdin (the patched OpenFang claude_code driver pipes it there) and
REM POSTs it to Brain's /api/multihop/execute, returning final_text. This is
REM what makes the Telegram bot flow through Brain capability routing
REM (browser_automation / coding_task / desktop_skill / ...).

setlocal

REM Uncomment to dump intent/reply to %TEMP%\openfang_brain_gateway.log
REM set "OPENFANG_BRAIN_GATEWAY_DEBUG=1"

set "WRAPPER_PY=%~dp0openfang_brain_gateway_wrapper.py"

set "VENV_PY=%~dp0..\.venv\Scripts\python.exe"
if exist "%VENV_PY%" (
    "%VENV_PY%" "%WRAPPER_PY%" %*
) else (
    python "%WRAPPER_PY%" %*
)

exit /b %ERRORLEVEL%
