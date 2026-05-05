$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $repoRoot

if (Test-Path "web/deploy.local.ps1") {
    . "web/deploy.local.ps1"
}

if (Test-Path "web/deploy.generated.ps1") {
    . "web/deploy.generated.ps1"
}

$backendUrl = if ($env:BACKEND_URL) { $env:BACKEND_URL.TrimEnd("/") } else { "http://localhost:8080" }
$modelUrl = if ($env:MODEL_SERVICE_URL) { $env:MODEL_SERVICE_URL.TrimEnd("/") } else { "http://localhost:8081" }

function Test-JsonEndpoint {
    param(
        [string]$Name,
        [string]$Url
    )
    Write-Host "Checking $Name -> $Url"
    $response = Invoke-WebRequest -Uri $Url -UseBasicParsing
    if ($response.StatusCode -lt 200 -or $response.StatusCode -ge 300) {
        throw "$Name failed with status $($response.StatusCode)"
    }
}

Test-JsonEndpoint "model health" "$modelUrl/health"
Test-JsonEndpoint "backend health" "$backendUrl/health"
Test-JsonEndpoint "backend exercises gateway" "$backendUrl/api/exercises"

Write-Host "Smoke test passed."
