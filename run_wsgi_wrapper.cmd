@echo off
setlocal
set "BASE=%~dp0"
cd /d "%BASE%"

if not exist "%BASE%logs" mkdir "%BASE%logs" 1>nul 2>nul
echo [%date% %time%] Wrapper started >> "%BASE%logs\started.txt" 2>&1
:: #region agent log (debug-a810eb)
echo {"sessionId":"a810eb","runId":"pre-fix","hypothesisId":"H5","location":"run_wsgi_wrapper.cmd:start","message":"wrapper started","data":{"base":"%BASE%"},"timestamp":"%date% %time%"}>> "%BASE%logs\debug-a810eb.log" 2>nul
:: #endregion agent log (debug-a810eb)

set "PY="
if exist "%BASE%.venv\Scripts\python.exe" set "PY=%BASE%.venv\Scripts\python.exe"
if not defined PY if exist "%BASE%venv\Scripts\python.exe" set "PY=%BASE%venv\Scripts\python.exe"
if not defined PY if defined PYTHON_EXE set "PY=%PYTHON_EXE%"
if not defined PY (
  for /f "usebackq delims=" %%P in (`where python 2^>nul`) do (
    if not defined PY set "PY=%%P"
  )
)

if not defined PY (
  echo [%date% %time%] ERROR: python.exe introuvable (.venv ou venv) >> "%BASE%logs\started.txt" 2>&1
  :: #region agent log (debug-a810eb)
  echo {"sessionId":"a810eb","runId":"pre-fix","hypothesisId":"H5","location":"run_wsgi_wrapper.cmd:python","message":"python not found","data":{"base":"%BASE%"},"timestamp":"%date% %time%"}>> "%BASE%logs\debug-a810eb.log" 2>nul
  :: #endregion agent log (debug-a810eb)
  exit /b 1
)

:: #region agent log (debug-a810eb)
echo {"sessionId":"a810eb","runId":"post-fix","hypothesisId":"H5","location":"run_wsgi_wrapper.cmd:python","message":"python resolved","data":{"python":"%PY%"},"timestamp":"%date% %time%"}>> "%BASE%logs\debug-a810eb.log" 2>nul
:: #endregion agent log (debug-a810eb)

"%PY%" "%BASE%run_wsgi.py"
