# Self-signed TLS for local docker compose (deploy/certs/)
$ErrorActionPreference = "Stop"
$Dir = Join-Path (Split-Path $PSScriptRoot -Parent) "deploy\certs"
New-Item -ItemType Directory -Force -Path $Dir | Out-Null
$Key = Join-Path $Dir "privkey.pem"
$Crt = Join-Path $Dir "fullchain.pem"
openssl req -x509 -nodes -days 365 -newkey rsa:2048 `
  -keyout $Key -out $Crt -subj "/CN=localhost"
Write-Host "Created $Crt and $Key"
