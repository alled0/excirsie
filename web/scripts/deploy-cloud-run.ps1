$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $repoRoot

$localConfig = "web/deploy.local.ps1"
if (!(Test-Path $localConfig)) {
    throw "Missing $localConfig. Copy web/deploy.local.example.ps1 to web/deploy.local.ps1 and fill it in."
}

. $localConfig

$gcloud = if ($IsWindows -or $env:OS -eq "Windows_NT") { "gcloud.cmd" } else { "gcloud" }

$deployMode = if ($env:DEPLOY_MODE) { $env:DEPLOY_MODE.Trim().ToLowerInvariant() } else { "prod" }
if ($deployMode -notin @("demo", "prod")) {
    throw "DEPLOY_MODE must be either 'demo' or 'prod'."
}

$required = @(
    "PROJECT_ID",
    "REGION",
    "ARTIFACT_REPO",
    "MODEL_SERVICE_NAME",
    "BACKEND_SERVICE_NAME"
)

if ($deployMode -eq "prod") {
    $required += @(
        "DB_URL",
        "DB_USER",
        "DB_PASS_SECRET"
    )
}

foreach ($name in $required) {
    if ([string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable($name))) {
        throw "Missing required environment variable: $name"
    }
}

$registry = "$($env:REGION)-docker.pkg.dev"
$modelImage = "$registry/$($env:PROJECT_ID)/$($env:ARTIFACT_REPO)/model-service:latest"
$backendImage = "$registry/$($env:PROJECT_ID)/$($env:ARTIFACT_REPO)/backend:latest"

function Invoke-Gcloud {
    param(
        [string[]]$Arguments,
        [switch]$Quiet
    )

    $previousPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        if ($Quiet) {
            & $gcloud @Arguments *> $null
        } else {
            & $gcloud @Arguments
        }
        return $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previousPreference
    }
}

function Invoke-GcloudOutput {
    param(
        [string[]]$Arguments
    )

    $previousPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $output = & $gcloud @Arguments 2>&1
        $exitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previousPreference
    }

    if ($exitCode -ne 0) {
        throw "gcloud failed: $($Arguments -join ' ')`n$($output -join [Environment]::NewLine)"
    }

    return $output | ForEach-Object { $_.ToString() }
}

function Invoke-CommandChecked {
    param(
        [string]$FilePath,
        [string[]]$Arguments,
        [string]$FailureMessage
    )

    $previousPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & $FilePath @Arguments
        $exitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previousPreference
    }

    if ($exitCode -ne 0) {
        throw $FailureMessage
    }
}

function Get-CloudRunServiceUrl {
    param(
        [string]$ServiceName
    )

    $lines = Invoke-GcloudOutput -Arguments @(
        "run", "services", "describe", $ServiceName,
        "--region", $env:REGION,
        "--project", $env:PROJECT_ID,
        "--format", "value(status.url)"
    )

    $url = $lines | Where-Object { $_ -match "^https?://" } | Select-Object -First 1
    if ([string]::IsNullOrWhiteSpace($url)) {
        throw "Could not resolve deployed URL for Cloud Run service: $ServiceName"
    }
    return $url.Trim()
}

$exitCode = Invoke-Gcloud -Arguments @("config", "set", "project", $env:PROJECT_ID)
if ($exitCode -ne 0) {
    throw "Failed to set gcloud project."
}

$requiredServices = @(
    "run.googleapis.com",
    "artifactregistry.googleapis.com"
)
if ($deployMode -eq "prod") {
    $requiredServices += "secretmanager.googleapis.com"
}

foreach ($service in $requiredServices) {
    $exitCode = Invoke-Gcloud -Arguments @("services", "enable", $service, "--project", $env:PROJECT_ID)
    if ($exitCode -ne 0) {
        throw "Failed to enable Google Cloud API '$service'. Confirm billing is linked for project '$($env:PROJECT_ID)' and rerun."
    }
}

$exitCode = Invoke-Gcloud -Arguments @("auth", "configure-docker", $registry, "--quiet")
if ($exitCode -ne 0) {
    throw "Failed to configure Docker auth for Artifact Registry."
}

Invoke-CommandChecked `
    -FilePath "docker" `
    -Arguments @("info") `
    -FailureMessage "Docker Desktop is not running or Docker cannot reach its Linux engine. Start Docker Desktop, wait until it says it is running, then rerun web/scripts/deploy-cloud-run.ps1."

$exitCode = Invoke-Gcloud -Quiet -Arguments @(
    "artifacts", "repositories", "describe", $env:ARTIFACT_REPO,
    "--location", $env:REGION,
    "--project", $env:PROJECT_ID
)

if ($exitCode -ne 0) {
    $exitCode = Invoke-Gcloud -Arguments @(
        "artifacts", "repositories", "create", $env:ARTIFACT_REPO,
        "--repository-format=docker",
        "--location=$($env:REGION)",
        "--project=$($env:PROJECT_ID)"
    )
    if ($exitCode -ne 0) {
        throw "Failed to create Artifact Registry repository."
    }
}

Push-Location "web/backend"
Invoke-CommandChecked `
    -FilePath "mvn" `
    -Arguments @("-B", "clean", "package") `
    -FailureMessage "Backend Maven package failed."
Pop-Location

Invoke-CommandChecked `
    -FilePath "docker" `
    -Arguments @("build", "-f", "web/model-service/Dockerfile", "-t", $modelImage, ".") `
    -FailureMessage "Model service Docker build failed."
Invoke-CommandChecked `
    -FilePath "docker" `
    -Arguments @("push", $modelImage) `
    -FailureMessage "Model service Docker push failed."

Invoke-CommandChecked `
    -FilePath "docker" `
    -Arguments @("build", "-f", "web/backend/Dockerfile", "-t", $backendImage, "web/backend") `
    -FailureMessage "Backend Docker build failed."
Invoke-CommandChecked `
    -FilePath "docker" `
    -Arguments @("push", $backendImage) `
    -FailureMessage "Backend Docker push failed."

$modelMinInstances = if ($env:MODEL_MIN_INSTANCES) { $env:MODEL_MIN_INSTANCES } else { "0" }
$modelConcurrency = if ($env:MODEL_CONCURRENCY) { $env:MODEL_CONCURRENCY } else { "1" }
$analysisTargetFps = if ($env:ANALYSIS_TARGET_FPS) { $env:ANALYSIS_TARGET_FPS } else { "15" }
$analysisMaxWidth = if ($env:ANALYSIS_MAX_WIDTH) { $env:ANALYSIS_MAX_WIDTH } else { "720" }
$modelEnvVars = "TAHARRAK_ANALYSIS_TARGET_FPS=$analysisTargetFps,TAHARRAK_ANALYSIS_MAX_WIDTH=$analysisMaxWidth"

$modelDeployArgs = @(
    "run", "deploy", $env:MODEL_SERVICE_NAME,
    "--image", $modelImage,
    "--region", $env:REGION,
    "--project", $env:PROJECT_ID,
    "--allow-unauthenticated",
    "--memory", "2Gi",
    "--cpu", "2",
    "--timeout", "3600",
    "--min-instances", $modelMinInstances,
    "--concurrency", $modelConcurrency,
    "--set-env-vars", $modelEnvVars
)

if ($env:MODEL_MAX_INSTANCES) {
    $modelDeployArgs += @("--max-instances", $env:MODEL_MAX_INSTANCES)
} elseif ($deployMode -eq "demo") {
    $modelDeployArgs += @("--max-instances", "1")
}

$exitCode = Invoke-Gcloud -Arguments $modelDeployArgs
if ($exitCode -ne 0) {
    throw "Model service deploy failed."
}

$modelServiceUrl = Get-CloudRunServiceUrl $env:MODEL_SERVICE_NAME
$env:MODEL_SERVICE_URL = $modelServiceUrl

$corsOrigins = if ($env:APP_CORS_ALLOWED_ORIGINS) { $env:APP_CORS_ALLOWED_ORIGINS } else { "*" }

$backendProfile = if ($deployMode -eq "demo") { "demo" } else { "prod" }
$backendEnvVars = "SPRING_PROFILES_ACTIVE=$backendProfile,MODEL_SERVICE_URL=$modelServiceUrl,APP_CORS_ALLOWED_ORIGINS=$corsOrigins"
if ($deployMode -eq "prod") {
    $backendEnvVars = "$backendEnvVars,DB_URL=$($env:DB_URL),DB_USER=$($env:DB_USER)"
}

$backendMinInstances = if ($env:BACKEND_MIN_INSTANCES) { $env:BACKEND_MIN_INSTANCES } else { "0" }

$backendDeployArgs = @(
    "run", "deploy", $env:BACKEND_SERVICE_NAME,
    "--image", $backendImage,
    "--region", $env:REGION,
    "--project", $env:PROJECT_ID,
    "--allow-unauthenticated",
    "--memory", "1Gi",
    "--cpu", "1",
    "--timeout", "600",
    "--min-instances", $backendMinInstances,
    "--set-env-vars", $backendEnvVars
)

if ($env:BACKEND_MAX_INSTANCES) {
    $backendDeployArgs += @("--max-instances", $env:BACKEND_MAX_INSTANCES)
} elseif ($deployMode -eq "demo") {
    # Keep the in-memory demo database from splitting across instances.
    $backendDeployArgs += @("--max-instances", "1")
}

if ($deployMode -eq "prod") {
    $backendDeployArgs += @("--set-secrets", "DB_PASS=$($env:DB_PASS_SECRET)")
}

$exitCode = Invoke-Gcloud -Arguments $backendDeployArgs
if ($exitCode -ne 0) {
    throw "Backend deploy failed."
}

$backendServiceUrl = Get-CloudRunServiceUrl $env:BACKEND_SERVICE_NAME
$env:BACKEND_URL = $backendServiceUrl

function Use-DeployedValue {
    param(
        [string]$CurrentValue,
        [string]$DeployedValue
    )

    if ([string]::IsNullOrWhiteSpace($CurrentValue)) {
        return $DeployedValue
    }
    if ($CurrentValue -match "xxxxx|your-frontend-domain|example\.com|localhost") {
        return $DeployedValue
    }
    return $CurrentValue
}

$wsBase = $modelServiceUrl -replace "^https://", "wss://"
$wsBase = $wsBase -replace "^http://", "ws://"
$wsBase = "$($wsBase.TrimEnd('/'))/ws"

$env:FRONTEND_API_BASE = Use-DeployedValue $env:FRONTEND_API_BASE "$backendServiceUrl/api"
$env:FRONTEND_MODEL_BASE = Use-DeployedValue $env:FRONTEND_MODEL_BASE "$backendServiceUrl/api"
$env:FRONTEND_WS_BASE = Use-DeployedValue $env:FRONTEND_WS_BASE $wsBase

$generatedConfig = "web/deploy.generated.ps1"
@"
# Generated by web/scripts/deploy-cloud-run.ps1. Safe to delete.
`$env:GENERATED_PROJECT_ID = "$($env:PROJECT_ID)"
`$env:MODEL_SERVICE_URL = "$modelServiceUrl"
`$env:BACKEND_URL = "$backendServiceUrl"
`$env:FRONTEND_API_BASE = "$($env:FRONTEND_API_BASE)"
`$env:FRONTEND_MODEL_BASE = "$($env:FRONTEND_MODEL_BASE)"
`$env:FRONTEND_WS_BASE = "$($env:FRONTEND_WS_BASE)"
"@ | Set-Content -Encoding UTF8 $generatedConfig

& "web/scripts/write-runtime-config.ps1"

Write-Host "Cloud Run deployment complete."
Write-Host "Mode: $deployMode"
Write-Host "Model service: $modelServiceUrl"
Write-Host "Backend: $backendServiceUrl"
Write-Host "Generated frontend config: $generatedConfig"
