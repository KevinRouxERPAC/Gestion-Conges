# Diagnostic IIS - executer sur le serveur
param([string]$BasePath = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path)

$base = $BasePath
$log = Join-Path $base "logs\diagnostic.txt"
if (-not (Test-Path (Join-Path $base "logs"))) { New-Item -ItemType Directory -Path (Join-Path $base "logs") -Force | Out-Null }

$pyVenv = Join-Path $base ".venv\Scripts\python.exe"
if (-not (Test-Path $pyVenv)) { $pyVenv = Join-Path $base "venv\Scripts\python.exe" }

"Diagnostic $(Get-Date)" | Out-File $log
"Base: $base" | Out-File $log -Append
"Python existe: $(Test-Path $pyVenv) ($pyVenv)" | Out-File $log -Append
"run_wsgi existe: $(Test-Path (Join-Path $base "run_wsgi.py"))" | Out-File $log -Append
Write-Host "Ecrit dans $log"
Get-Content $log
