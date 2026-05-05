$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $repoRoot
$firebase = if ($IsWindows -or $env:OS -eq "Windows_NT") { "firebase.cmd" } else { "firebase" }

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

$localConfig = "web/deploy.local.ps1"
if (Test-Path $localConfig) {
    . $localConfig
}

$generatedConfig = "web/deploy.generated.ps1"
if (Test-Path $generatedConfig) {
    . $generatedConfig
}

if ([string]::IsNullOrWhiteSpace($env:PROJECT_ID)) {
    throw "Missing PROJECT_ID. Copy web/deploy.local.example.ps1 to web/deploy.local.ps1 and fill it in."
}

$firebaseProjectId = if ($env:FIREBASE_PROJECT_ID) { $env:FIREBASE_PROJECT_ID } else { $env:PROJECT_ID }
$firebaseSiteId = if ($env:FIREBASE_SITE_ID) { $env:FIREBASE_SITE_ID } else { $firebaseProjectId }

$projectsJson = & $firebase "projects:list" "--json"
$projectsExitCode = $LASTEXITCODE
if ($projectsExitCode -ne 0) {
    throw "Firebase CLI authentication is not valid. Run: firebase logout  then: firebase login --reauth"
}
$projects = $projectsJson | ConvertFrom-Json
$matchingProject = @($projects.result | Where-Object { $_.projectId -eq $firebaseProjectId })
if ($matchingProject.Count -eq 0) {
    $availableProjects = ($projects.result | ForEach-Object { $_.projectId }) -join ", "
    throw "Firebase project '$firebaseProjectId' was not found. Set FIREBASE_PROJECT_ID to one of: $availableProjects"
}

if (
    $matchingProject[0].resources -and
    $matchingProject[0].resources.hostingSite -and
    $firebaseSiteId -ne $matchingProject[0].resources.hostingSite
) {
    Write-Host "Firebase project default Hosting site is '$($matchingProject[0].resources.hostingSite)'. Using configured site '$firebaseSiteId'."
}

Invoke-CommandChecked `
    -FilePath $firebase `
    -Arguments @("hosting:sites:get", $firebaseSiteId, "--project", $firebaseProjectId) `
    -FailureMessage "Firebase Hosting site '$firebaseSiteId' was not found in project '$firebaseProjectId'. Set FIREBASE_SITE_ID to an existing site."

& "web/scripts/write-runtime-config.ps1"

Push-Location "web/frontend"
npm ci
npm run build:prod
Pop-Location

$firebaseConfigPath = "firebase.generated.json"
$firebaseConfig = [ordered]@{
    hosting = [ordered]@{
        site = $firebaseSiteId
        public = "web/frontend/dist/formcheck/browser"
        ignore = @("firebase.json", "**/.*", "**/node_modules/**")
        rewrites = @(
            [ordered]@{
                source = "**"
                destination = "/index.html"
            }
        )
    }
}
$firebaseConfig | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 $firebaseConfigPath

Invoke-CommandChecked `
    -FilePath $firebase `
    -Arguments @("deploy", "--only", "hosting:$firebaseSiteId", "--project", $firebaseProjectId, "--config", $firebaseConfigPath) `
    -FailureMessage "Firebase Hosting deploy failed."
