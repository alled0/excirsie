# Dev startup script — launches all three services in separate windows.
# Run from any terminal: .\web\start-dev.ps1

$root     = Split-Path $PSScriptRoot -Parent
$webRoot  = "$root\web"
$mvn      = "$env:USERPROFILE\tools\apache-maven-3.9.6\bin\mvn.cmd"
$uvicorn  = "$env:APPDATA\Python\Python314\Scripts\uvicorn.exe"

if (-not (Test-Path $mvn)) {
    Write-Error "Maven not found at $mvn — re-run the setup steps in SETUP.md"
    exit 1
}
if (-not (Test-Path $uvicorn)) {
    Write-Error "uvicorn not found at $uvicorn — run: pip install uvicorn"
    exit 1
}

Write-Host "Starting model service  (port 8081)..."
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$webRoot\model-service'; & '$uvicorn' main:app --port 8081 --reload"

Write-Host "Starting Spring Boot    (port 8080)..."
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$webRoot\backend'; & '$mvn' spring-boot:run"

Write-Host "Starting Angular        (port 4200)..."
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$webRoot\frontend'; npm start"

Write-Host ""
Write-Host "All three services launching in separate windows."
Write-Host "Open http://localhost:4200 once Angular finishes compiling."
