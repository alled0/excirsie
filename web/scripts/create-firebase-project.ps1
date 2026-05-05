param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectId,

    [string]$DisplayName = "Taharrak",

    [string]$SiteId = ""
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $repoRoot

$firebase = if ($IsWindows -or $env:OS -eq "Windows_NT") { "firebase.cmd" } else { "firebase" }
$site = if ([string]::IsNullOrWhiteSpace($SiteId)) { $ProjectId } else { $SiteId }

function Invoke-Checked {
    param(
        [string]$FilePath,
        [string[]]$Arguments,
        [string]$FailureMessage
    )

    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw $FailureMessage
    }
}

function Invoke-FirebaseJson {
    param(
        [string[]]$Arguments
    )

    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $output = & $firebase @Arguments 2>&1
        $exitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }
    $raw = ($output | ForEach-Object { $_.ToString() }) -join "`n"

    if ($exitCode -ne 0) {
        return [pscustomobject]@{
            Success = $false
            Json = $null
            Raw = $raw
        }
    }

    $jsonStart = $raw.IndexOf("{")
    if ($jsonStart -lt 0) {
        return [pscustomobject]@{
            Success = $false
            Json = $null
            Raw = $raw
        }
    }

    try {
        return [pscustomobject]@{
            Success = $true
            Json = ($raw.Substring($jsonStart) | ConvertFrom-Json)
            Raw = $raw
        }
    } catch {
        return [pscustomobject]@{
            Success = $false
            Json = $null
            Raw = $raw
        }
    }
}

$projectList = Invoke-FirebaseJson -Arguments @("projects:list", "--json")
$projectExists = $false
if ($projectList.Success -and $projectList.Json.result) {
    $projectExists = @($projectList.Json.result | Where-Object { $_.projectId -eq $ProjectId }).Count -gt 0
}

if ($projectExists) {
    Write-Host "Firebase project '$ProjectId' already exists. Reusing it."
} else {
    Invoke-Checked `
        -FilePath $firebase `
        -Arguments @("projects:create", $ProjectId, "--display-name", $DisplayName) `
        -FailureMessage "Could not create Firebase project '$ProjectId'. The ID may already be taken, billing/API permissions may be missing, or your account may not have permission."
}

Invoke-Checked `
    -FilePath $firebase `
    -Arguments @("use", "--add", $ProjectId, "--alias", "default") `
    -FailureMessage "Could not set Firebase project alias for '$ProjectId'."

$siteLookup = Invoke-FirebaseJson -Arguments @("hosting:sites:get", $site, "--project", $ProjectId, "--json")
if ($siteLookup.Success) {
    Write-Host "Firebase Hosting site '$site' already exists. Reusing it."
} else {
    Invoke-Checked `
        -FilePath $firebase `
        -Arguments @("hosting:sites:create", $site, "--project", $ProjectId, "--non-interactive") `
        -FailureMessage "Could not create Hosting site '$site'. It may already exist globally or may not be available."
}

$localConfig = "web/deploy.local.ps1"
if (!(Test-Path $localConfig)) {
    Copy-Item "web/deploy.local.example.ps1" $localConfig
}

$content = Get-Content $localConfig -Raw
$content = $content -replace '\$env:PROJECT_ID\s*=\s*"[^"]*"', "`$env:PROJECT_ID = `"$ProjectId`""
$content = $content -replace '\$env:FIREBASE_PROJECT_ID\s*=\s*"[^"]*"', "`$env:FIREBASE_PROJECT_ID = `"$ProjectId`""
$content = $content -replace '\$env:FIREBASE_SITE_ID\s*=\s*"[^"]*"', "`$env:FIREBASE_SITE_ID = `"$site`""
if ($content -notmatch '\$env:FIREBASE_PROJECT_ID') {
    $content += "`r`n`$env:FIREBASE_PROJECT_ID = `"$ProjectId`"`r`n"
}
if ($content -notmatch '\$env:FIREBASE_SITE_ID') {
    $content += "`$env:FIREBASE_SITE_ID = `"$site`"`r`n"
}
Set-Content -Encoding UTF8 $localConfig $content

$generatedConfig = "web/deploy.generated.ps1"
if (Test-Path $generatedConfig) {
    Remove-Item $generatedConfig -Force
    Write-Host "Removed stale $generatedConfig. It will be regenerated after Cloud Run deploy."
}

$runtimeConfig = "web/frontend/src/assets/runtime-config.json"
if (Test-Path $runtimeConfig) {
    Remove-Item $runtimeConfig -Force
    Write-Host "Removed stale $runtimeConfig. It will be regenerated before the next frontend deploy."
}

Write-Host "Firebase project ready."
Write-Host "Project: $ProjectId"
Write-Host "Hosting site: $site"
Write-Host "Updated $localConfig"
