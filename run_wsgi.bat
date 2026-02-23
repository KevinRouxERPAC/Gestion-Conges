@echo off
REM Lanceur IIS : force le repertoire du site comme CWD.
cd /d "%~dp0"
"%~dp0.venv\Scripts\python.exe" "%~dp0run_wsgi.py"
