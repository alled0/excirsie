param(
    [string]$OutputPath = "web/frontend/src/assets/runtime-config.json"
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $repoRoot

$apiBase = if ($env:FRONTEND_API_BASE) { $env:FRONTEND_API_BASE } else { "/api" }
$modelBase = if ($env:FRONTEND_MODEL_BASE) { $env:FRONTEND_MODEL_BASE } else { $apiBase }
$wsBase = if ($env:FRONTEND_WS_BASE) { $env:FRONTEND_WS_BASE } else { "ws://localhost:8081/ws" }

$config = [ordered]@{
    apiBase = $apiBase
    modelBase = $modelBase
    wsBase = $wsBase
}

$resolvedOutput = Join-Path $repoRoot $OutputPath
$outputDir = Split-Path $resolvedOutput -Parent
New-Item -ItemType Directory -Force $outputDir | Out-Null
$config | ConvertTo-Json -Depth 4 | Set-Content -Encoding UTF8 $resolvedOutput

Write-Host "Wrote runtime config to $resolvedOutput"
