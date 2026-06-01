@echo off
REM Wrapper de developpement local : definit SECRET_KEY puis lance Waitress.
REM Cette cle est UNIQUEMENT pour le poste de dev. Pas pour la production.
set SECRET_KEY=dev-local-secret-not-for-production-c0ffee
"%~dp0..\.venv\Scripts\python.exe" "%~dp0..\run_wsgi.py"
