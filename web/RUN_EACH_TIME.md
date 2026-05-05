# Run Each Time

Start the 3 services in 3 terminals from the repo root.

## 1. Model service

```powershell
cd C:\Users\wlaeed\Desktop\projects\excirsie\web\model-service
uvicorn main:app --host 0.0.0.0 --port 8081 --reload
```

Health check:

```powershell
Invoke-WebRequest http://localhost:8081/health
```

## 2. Backend

```powershell
cd C:\Users\wlaeed\Desktop\projects\excirsie\web\backend
mvn spring-boot:run
```

Runs on:

```text
http://localhost:8080
```

If you see `Database may be already in use`, another backend is already running.
Do not start a second one.

If you want to restart it:

```powershell
Get-NetTCPConnection -LocalPort 8080 -State Listen |
  Select-Object -ExpandProperty OwningProcess -Unique |
  ForEach-Object { Stop-Process -Id $_ }
```

Then run:

```powershell
mvn spring-boot:run
```

## 3. Frontend

```powershell
cd C:\Users\wlaeed\Desktop\projects\excirsie\web\frontend
npm start
```

Open:

```text
http://localhost:4200
```

## If the backend DB gets corrupted

Delete the local dev DB, then restart the backend:

```powershell
Remove-Item .\data\workout-dev.mv.db, .\data\workout-dev.trace.db -Force -ErrorAction SilentlyContinue
mvn spring-boot:run
```

## Live camera + skeleton

1. Open `http://localhost:4200`
2. Go to the camera page
3. Start a session
4. Enable `Show joints and skeleton`
## Google Free-First Deploy

Use this while you are not expecting real users and want to avoid Cloud SQL cost.

```powershell
cd C:\Users\wlaeed\Desktop\projects\excirsie
.\web\scripts\deploy-cloud-run.ps1
.\web\scripts\deploy-frontend-firebase.ps1
.\web\scripts\smoke-test.ps1
```

`web/deploy.local.ps1` should have:

```powershell
$env:DEPLOY_MODE = "demo"
```

Demo mode uses an in-memory backend database. It is cheap, but history can reset
after restart, redeploy, or Cloud Run scale-down.

## If The Deployed Site Feels Slow

The faster deployed profile keeps one backend and one model-service instance
warm, and samples uploaded videos at 15 FPS / 720px:

```powershell
$env:MODEL_MIN_INSTANCES = "1"
$env:MODEL_MAX_INSTANCES = "3"
$env:MODEL_CONCURRENCY = "1"
$env:BACKEND_MIN_INSTANCES = "1"
$env:BACKEND_MAX_INSTANCES = "2"
$env:ANALYSIS_TARGET_FPS = "15"
$env:ANALYSIS_MAX_WIDTH = "720"
```

Set `MODEL_MIN_INSTANCES` and `BACKEND_MIN_INSTANCES` back to `0` only when
you want the cheapest idle cost and can accept slower first requests.
