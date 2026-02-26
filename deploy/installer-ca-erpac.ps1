# Installe le certificat de la CA ERPAC en racine de confiance pour https://conges.erpac.com
# Usage: .\deploy\installer-ca-erpac.ps1   ou   .\deploy\installer-ca-erpac.ps1 C:\chemin\vers\ca.cer
# Placez le fichier .cer de la CA dans deploy\erpac-ca.cer (ou passez le chemin en argument).

param([string]$CertPath = "$PSScriptRoot\erpac-ca.cer")
$ErrorActionPreference = "Stop"
if (-not (Test-Path -LiteralPath $CertPath)) {
    Write-Host "Fichier introuvable: $CertPath" -ForegroundColor Red
    Write-Host "Placez le certificat CA (.cer) dans deploy\erpac-ca.cer ou indiquez son chemin."
    exit 1
}
$store = New-Object System.Security.Cryptography.X509Certificates.X509Store("Root", "CurrentUser")
$store.Open("ReadWrite")
try {
    $cert = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2($CertPath)
    $store.Add($cert)
    Write-Host "Certificat CA installe (racine de confiance): $($cert.Subject)" -ForegroundColor Green
} finally { $store.Close() }
