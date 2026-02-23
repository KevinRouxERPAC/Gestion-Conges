@echo off
cd /d "C:\Sites\Gestion-Conges"
echo [%date% %time%] Wrapper started >> "C:\Sites\Gestion-Conges\logs\started.txt" 2>&1
"C:\Sites\Gestion-Conges\.venv\Scripts\python.exe" "C:\Sites\Gestion-Conges\run_wsgi.py"
