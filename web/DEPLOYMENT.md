# Taharrak Deployment Plan

This is the recommended path for deploying Taharrak while keeping the product easy to grow.

The remaining values you need to provide are listed in `CREDENTIALS_TODO.md`.

## Target Architecture

Keep the current three-service split:

```text
Angular frontend
  -> Spring Boot backend API
      -> PostgreSQL
      -> Python model service for analysis requests

Angular live camera
  -> Python model service WebSocket
```

Recommended first production stack:

- Frontend: Firebase Hosting or another static host/CDN.
- Backend: Spring Boot container on Cloud Run.
- Model service: FastAPI/MediaPipe container on Cloud Run.
- Database: PostgreSQL on Cloud SQL.
- Container images: Artifact Registry.
- Uploaded files later: Cloud Storage.
- Async processing later: Cloud Tasks plus a model-worker endpoint or Cloud Run Job.

Lowest-cost demo stack while no users are expected:

- Frontend: Firebase Hosting.
- Backend: Spring Boot container on Cloud Run with `SPRING_PROFILES_ACTIVE=demo`.
- Model service: FastAPI/MediaPipe container on Cloud Run.
- Database: in-memory H2 inside the backend container.
- Cloud SQL: not created.

The demo stack avoids the always-on Cloud SQL monthly cost. It is not durable:
users, sessions, and history can reset whenever Cloud Run scales down, restarts,
or replaces the backend container.

## Service Boundaries

### Frontend

Location: `web/frontend`

Responsibilities:

- Browser UI.
- Camera capture.
- Calls `/api` for REST work.
- Opens the live WebSocket through `wsBase`.
- Does not store secrets.

Runtime config:

```json
{
  "apiBase": "/api",
  "modelBase": "/api",
  "wsBase": "wss://taharrak-model-service.example.com/ws"
}
```

Use `/api` when your static host rewrites `/api` to the backend service.
If there is no rewrite, use the full backend URL instead:

```json
{
  "apiBase": "https://taharrak-backend.example.com/api",
  "modelBase": "https://taharrak-backend.example.com/api",
  "wsBase": "wss://taharrak-model-service.example.com/ws"
}
```

This file lives at:

```text
web/frontend/src/assets/runtime-config.json
```

For local dev, `wsBase` can stay as `ws://localhost:8081/ws`.
For Docker Compose, `runtime-config.docker.json` overrides this file so nginx can route WebSockets through `/ws`.

### Backend

Location: `web/backend`

Responsibilities:

- Users, sessions, feedback, events, and client errors.
- REST gateway to the model service for upload analysis.
- Database migrations through Flyway.
- Production system of record.

Production environment:

```text
SPRING_PROFILES_ACTIVE=prod
MODEL_SERVICE_URL=https://<model-service-url>
DB_URL=jdbc:postgresql://<host>:5432/taharrak
DB_USER=<db-user>
DB_PASS=<db-password>
```

Free-first demo environment:

```text
SPRING_PROFILES_ACTIVE=demo
MODEL_SERVICE_URL=https://<model-service-url>
```

Do not use the demo profile for real production data.

### Model Service

Location: `web/model-service`

Responsibilities:

- MediaPipe pose inference.
- Video analysis.
- Live WebSocket feedback.
- No database ownership.
- No long-term user data storage.

Keep it stateless. Any future model artifacts should be bundled in the image or downloaded at startup from controlled storage.

## Phase 1: Deploy The Current Product

### Option A: Free-First Demo Deploy

1. Do not create Cloud SQL yet.
2. Copy `web/deploy.local.example.ps1` to `web/deploy.local.ps1`.
3. Keep `DEPLOY_MODE=demo`.
4. If you want a brand-new Firebase project and Hosting site, create them:

```powershell
.\web\scripts\create-firebase-project.ps1 `
  -ProjectId "taharrak-yourname-001" `
  -DisplayName "Taharrak"
```

Project IDs are global, so choose a unique lowercase ID with letters, numbers,
and hyphens.

5. Deploy Cloud Run services:

```powershell
.\web\scripts\deploy-cloud-run.ps1
```

The script writes deployed service URLs to `web/deploy.generated.ps1` and updates
`web/frontend/src/assets/runtime-config.json`.

6. Deploy the frontend:

```powershell
.\web\scripts\deploy-frontend-firebase.ps1
```

7. Smoke test:

```powershell
.\web\scripts\smoke-test.ps1
```

Expected checks:

```text
GET /api/exercises
POST /api/users/resolve
GET model-service /health
live camera WebSocket connects
video upload returns an analysis result
session history saves
```

In demo mode, session history only needs to work within the current backend
container lifetime. It is allowed to reset after idle scale-down or redeploy.

### Option B: Durable Production Deploy

1. Create a managed PostgreSQL database.
2. Set `DEPLOY_MODE=prod` in `web/deploy.local.ps1`.
3. Fill in the Cloud SQL and Secret Manager values from `CREDENTIALS_TODO.md`.
4. Deploy Cloud Run, Firebase Hosting, and smoke tests using the same commands
   from Option A.

## Phase 2: Make Uploads Scalable

Move uploaded videos out of request/response processing.

Target flow:

```text
Frontend asks backend for an upload URL
Frontend uploads video directly to object storage
Backend creates a processing job row
Cloud Tasks starts model processing
Model worker reads video from storage
Model worker writes result JSON to storage or backend
Frontend polls backend for job status
```

Add these backend concepts when ready:

- `analysis_jobs` table.
- signed upload URL endpoint.
- job status endpoint.
- retry-safe processing callback.
- storage object cleanup policy.

Do this before you expect large videos or many simultaneous users.

## Phase 3: Split Live And Batch Model Work

When traffic grows, separate the model service into two deployables:

```text
model-live
  WebSocket sessions
  low latency
  smaller concurrency

model-worker
  uploaded videos
  queue driven
  retryable
  larger CPU/memory
```

This keeps a heavy upload from hurting a live workout session.

## Phase 4: Operational Baseline

Add before public launch:

- staging environment
- CI checks for Python tests, Angular build, and Maven package
- Cloud Run health checks
- structured logs
- error reporting
- database backups
- budget alerts
- request latency dashboard
- active live sessions dashboard
- model-service CPU and memory dashboard
- queue depth dashboard after async jobs exist

## Phase 5: Later Scale Options

Stay on Cloud Run while the workload is mostly CPU-bound and request based.

Consider GKE Autopilot or dedicated compute only if:

- model service needs GPU scheduling
- live WebSocket sessions require more control
- batch processing needs custom workers
- Cloud Run cold starts or timeouts become product issues

Move only the model workload first. Keep the frontend, backend, database, and storage architecture stable.

## Build Commands

Full local production build:

```powershell
.\web\scripts\build-production.ps1
```

Backend:

```powershell
cd web/backend
mvn clean package
docker build -t taharrak-backend .
```

Model service:

```powershell
docker build -f web/model-service/Dockerfile -t taharrak-model-service .
```

Frontend:

```powershell
cd web/frontend
npm install
npm run build:prod
```

CI already has the same baseline checks in:

```text
.github/workflows/ci.yml
```

## Cloud Run Example Commands

Set these locally first:

```powershell
$PROJECT_ID = "your-gcp-project"
$REGION = "me-central2"
$REPO = "taharrak"
```

Create an Artifact Registry repository once:

```powershell
gcloud artifacts repositories create $REPO `
  --repository-format=docker `
  --location=$REGION `
  --project=$PROJECT_ID
```

Build and push the model service:

```powershell
gcloud auth configure-docker "$REGION-docker.pkg.dev"

cd C:\Users\wlaeed\Desktop\projects\excirsie
docker build -f web/model-service/Dockerfile `
  -t "$REGION-docker.pkg.dev/$PROJECT_ID/$REPO/model-service:latest" .
docker push "$REGION-docker.pkg.dev/$PROJECT_ID/$REPO/model-service:latest"
```

Deploy the model service:

```powershell
gcloud run deploy taharrak-model-service `
  --image "$REGION-docker.pkg.dev/$PROJECT_ID/$REPO/model-service:latest" `
  --region $REGION `
  --project $PROJECT_ID `
  --allow-unauthenticated `
  --memory 2Gi `
  --cpu 2 `
  --timeout 3600
```

Build and push the backend after `mvn clean package`:

```powershell
cd web/backend
docker build -t "$REGION-docker.pkg.dev/$PROJECT_ID/$REPO/backend:latest" .
docker push "$REGION-docker.pkg.dev/$PROJECT_ID/$REPO/backend:latest"
```

Deploy the backend:

```powershell
gcloud run deploy taharrak-backend `
  --image "$REGION-docker.pkg.dev/$PROJECT_ID/$REPO/backend:latest" `
  --region $REGION `
  --project $PROJECT_ID `
  --allow-unauthenticated `
  --memory 1Gi `
  --cpu 1 `
  --set-env-vars "SPRING_PROFILES_ACTIVE=prod,MODEL_SERVICE_URL=https://<model-service-url>,DB_URL=jdbc:postgresql://<host>:5432/taharrak,DB_USER=<db-user>" `
  --set-secrets "DB_PASS=taharrak-db-pass:latest"
```

For the frontend, update `runtime-config.json`, run `npm run build:prod`, then deploy the generated `dist/formcheck` folder to your static host.

## Local Docker Check

```powershell
cd web
docker compose up --build
```

Open:

```text
http://localhost:4200
```

## Production Rules

- Do not use H2 in production.
- Do not store uploaded videos on container disk.
- Do not put secrets in Angular files.
- Do not make the model service the owner of user/session data.
- Do not add Kubernetes until the model workload has clearly outgrown Cloud Run.
