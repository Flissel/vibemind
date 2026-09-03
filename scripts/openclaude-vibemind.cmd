@echo off
REM openclaude-vibemind — drop-in `claude` replacement using OpenAI/gpt-4o-mini.
REM
REM Usage examples:
REM   openclaude-vibemind                              # interactive, default 'code' mcp profile
REM   openclaude-vibemind --mcp bare                   # zero MCPs, fastest
REM   openclaude-vibemind --mcp full -p "hi"           # all .mcp.json servers
REM   openclaude-vibemind --mcp desktop                # desktop-automation only
REM
REM All arg-handling lives in openclaude-vibemind.py — this .cmd is just a thin shim
REM that forwards stdin/stdout/stderr.

setlocal

set "VENV_PY=%~dp0..\.venv\Scripts\python.exe"
set "LAUNCHER=%~dp0openclaude-vibemind.py"

if exist "%VENV_PY%" (
    "%VENV_PY%" "%LAUNCHER%" %*
) else (
    python "%LAUNCHER%" %*
)

exit /b %ERRORLEVEL%
