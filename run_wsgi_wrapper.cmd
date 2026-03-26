@echo off
setlocal
set "BASE=%~dp0"
cd /d "%BASE%"

if not exist "%BASE%logs" mkdir "%BASE%logs" 1>nul 2>nul
echo [%date% %time%] Wrapper started >> "%BASE%logs\started.txt" 2>&1

set "PY="
if exist "%BASE%.venv\Scripts\python.exe" set "PY=%BASE%.venv\Scripts\python.exe"
if not defined PY if exist "%BASE%venv\Scripts\python.exe" set "PY=%BASE%venv\Scripts\python.exe"

if not defined PY (
  echo [%date% %time%] ERROR: python.exe introuvable (.venv ou venv) >> "%BASE%logs\started.txt" 2>&1
  exit /b 1
)

"%PY%" "%BASE%run_wsgi.py"
