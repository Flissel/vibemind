@echo off
REM OpenFang -> SoM-Resume bridge shim.
REM Telegram-Antwort auf eine SoM-Rueckfrage laeuft via brain-gateway -> Brain
REM (som_resume capability) -> openfang:som-resume -> dieser Shim. Liest die
REM Antwort vom stdin, findet den juengsten wartenden Run, resumed detached.
REM Uses voice/.venv312 (fuer den detached som_resume.py, der autogen braucht).

setlocal

set "WRAPPER_PY=%~dp0openfang_som_resume_wrapper.py"

set "VENV_PY=%~dp0..\vibemind-os\voice\.venv312\Scripts\python.exe"
if exist "%VENV_PY%" (
    "%VENV_PY%" "%WRAPPER_PY%" %*
) else (
    python "%WRAPPER_PY%" %*
)

exit /b %ERRORLEVEL%
