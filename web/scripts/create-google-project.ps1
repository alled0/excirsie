param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectId,

    [string]$ProjectName = "Taharrak",

    [string]$BillingAccount = ""
)

$ErrorActionPreference = "Stop"
$gcloud = if ($IsWindows -or $env:OS -eq "Windows_NT") { "gcloud.cmd" } else { "gcloud" }

if ($ProjectId -notmatch "^[a-z][a-z0-9-]{4,28}[a-z0-9]$") {
    throw "ProjectId must be 6-30 chars, lowercase letters/numbers/hyphens, start with a letter, and end with a letter or number."
}

Write-Host "Creating project $ProjectId..."
& $gcloud projects create $ProjectId --name=$ProjectName

if ([string]::IsNullOrWhiteSpace($BillingAccount)) {
    Write-Host "Available billing accounts:"
    & $gcloud billing accounts list
    Write-Host ""
    Write-Host "Project created, but billing was not linked."
    Write-Host "Run this after choosing a billing account:"
    Write-Host "gcloud billing projects link $ProjectId --billing-account BILLING_ACCOUNT_ID"
} else {
    & $gcloud billing projects link $ProjectId --billing-account=$BillingAccount
}

& $gcloud config set project $ProjectId

Write-Host "Project setup started for $ProjectId."
Write-Host "Next step: enable APIs after billing is linked."
