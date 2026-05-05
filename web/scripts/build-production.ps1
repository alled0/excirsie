$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $repoRoot

if (Test-Path "web/deploy.local.ps1") {
    . "web/deploy.local.ps1"
}

& "web/scripts/write-runtime-config.ps1"

Push-Location "web/backend"
mvn -B clean package
Pop-Location

Push-Location "web/frontend"
npm ci
npm run build:prod
Pop-Location

docker build -f "web/model-service/Dockerfile" -t "taharrak-model-service:local" .
docker build -f "web/backend/Dockerfile" -t "taharrak-backend:local" "web/backend"

Write-Host "Production build complete."
