# Diagnostic 502 Bad Gateway - Gestion Conges sous IIS
# Executer depuis la racine du projet : .\scripts\diagnostic_502.ps1

param([string]$BasePath = "C:\Sites\Gestion-Conges")

$logFile = Join-Path $BasePath "logs\stdout.log"
$py = Join-Path $BasePath ".venv\Scripts\python.exe"

Write-Host "=== Diagnostic 502 - $BasePath ===" -ForegroundColor Cyan

if (-not (Test-Path $py)) {
    Write-Host "ERREUR: Python introuvable: $py" -ForegroundColor Red
} else {
    Write-Host "  OK  Python: $py" -ForegroundColor Green
}

if (Test-Path $logFile) {
    Write-Host "`n--- Dernieres lignes logs\stdout.log ---" -ForegroundColor Cyan
    Get-Content $logFile -Tail 40 -ErrorAction SilentlyContinue
    Write-Host "--- Fin ---`n" -ForegroundColor Cyan
} else {
    Write-Host "  Aucun logs\stdout.log" -ForegroundColor Yellow
}

Write-Host "=== 502.3 / 0x8007000d ===" -ForegroundColor Cyan
Write-Host "1. Consulter logs\stdout.log (et fichiers stdout.log_*.log) pour [run_wsgi] et Waitress"
Write-Host "2. Recycler le pool IIS puis refaire une requete"
Write-Host "3. web.config : processPath, arguments (chemin complet), workingDirectory = ce dossier"
Write-Host "4. Droits : compte du pool doit pouvoir ECRIRE dans logs\ et LIRE tout le site"
Write-Host "5. Pool IIS : ""Activer les applications 32 bits"" = False (Python 64 bits)"
Write-Host "6. Si le log reste vide : le processus ne demarre pas (chemin Python ou droits)"
