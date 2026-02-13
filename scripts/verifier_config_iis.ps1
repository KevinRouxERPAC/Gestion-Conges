# Verifie la configuration du site Gestion Conges pour IIS
# Executer depuis la racine du projet : .\scripts\verifier_config_iis.ps1

$base = "C:\Sites\Gestion-Conges"
Write-Host "=== Verification config IIS - $base ===" -ForegroundColor Cyan

@("app.py", "run_wsgi.py", "web.config") | ForEach-Object {
    $p = Join-Path $base $_
    if (Test-Path $p) { Write-Host "  OK  $_" } else { Write-Host "  MANQUE  $_" -ForegroundColor Red }
}

$py = Join-Path $base ".venv\Scripts\python.exe"
if (Test-Path $py) { Write-Host "  OK  .venv\Scripts\python.exe" } else { Write-Host "  MANQUE  .venv\Scripts\python.exe" -ForegroundColor Red }

if (Test-Path (Join-Path $base "logs")) { Write-Host "  OK  logs\" } else { Write-Host "  MANQUE  logs\" -ForegroundColor Red }

Push-Location $base
try {
    $r = & $py -c "from app import create_app; create_app(); print('OK')" 2>&1
    if ($r -match "OK") { Write-Host "  OK  create_app()" } else { Write-Host "  ERREUR  $r" -ForegroundColor Red }
} finally { Pop-Location }

$mod = & C:\Windows\System32\inetsrv\appcmd.exe list module 2>$null
if ($mod -match "httpPlatformHandler") { Write-Host "  OK  HttpPlatformHandler" } else { Write-Host "  MANQUE  HttpPlatformHandler" -ForegroundColor Red }
Write-Host "=== Fin ===" -ForegroundColor Cyan
