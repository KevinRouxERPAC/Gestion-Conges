# Diagnostic IIS - executer sur le serveur
$base = "C:\Sites\Gestion-Conges"
$log = "$base\logs\diagnostic.txt"
if (-not (Test-Path "$base\logs")) { New-Item -ItemType Directory -Path "$base\logs" -Force | Out-Null }
"Diagnostic $(Get-Date)" | Out-File $log
"Python existe: $(Test-Path $base\.venv\Scripts\python.exe)" | Out-File $log -Append
"run_wsgi existe: $(Test-Path $base\run_wsgi.py)" | Out-File $log -Append
Write-Host "Ecrit dans $log"; Get-Content $log
