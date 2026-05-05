# Credentials To Fill In

Everything in the repo is prepared so deployment should mostly be filling these values.

## Local Deploy File

1. Copy:

```powershell
Copy-Item web\deploy.local.example.ps1 web\deploy.local.ps1
```

2. Fill in:

```text
PROJECT_ID
REGION
ARTIFACT_REPO
FIREBASE_PROJECT_ID
FIREBASE_SITE_ID
DEPLOY_MODE
MODEL_SERVICE_URL
BACKEND_URL
DB_URL
DB_USER
DB_PASS_SECRET
APP_CORS_ALLOWED_ORIGINS
FRONTEND_API_BASE
FRONTEND_MODEL_BASE
FRONTEND_WS_BASE
```

`web/deploy.local.ps1` is ignored by Git.

For the lowest-cost demo path, set:

```text
DEPLOY_MODE=demo
```

In demo mode you do not need `DB_URL`, `DB_USER`, or `DB_PASS_SECRET`.
The backend uses an in-memory H2 database, so data can reset when Cloud Run
scales to zero or starts a new container. This avoids the always-on Cloud SQL
monthly cost while you are not expecting users.

For a durable production deployment later, set:

```text
DEPLOY_MODE=prod
```

Then fill in the Cloud SQL and Secret Manager values.

## Google Cloud

Create or confirm:

```text
Artifact Registry repository
Cloud SQL PostgreSQL instance, only for DEPLOY_MODE=prod
Secret Manager secret for DB_PASS, only for DEPLOY_MODE=prod
Cloud Run service account permissions
Firebase Hosting project, if using Firebase
```

`FIREBASE_PROJECT_ID` must be one of the IDs shown by:

```powershell
firebase projects:list
```

`FIREBASE_SITE_ID` is usually the default Hosting site shown in that project,
for example `gyms-51c55` for project `gyms-51c55`.

To create a fresh Firebase project and Hosting site:

```powershell
.\web\scripts\create-firebase-project.ps1 `
  -ProjectId "taharrak-yourname-001" `
  -DisplayName "Taharrak"
```

Project IDs are global, so choose a unique lowercase ID with letters, numbers,
and hyphens.

## GitHub Secrets

Add these if you want to deploy Cloud Run from GitHub Actions:

```text
GCP_PROJECT_ID
GCP_REGION
GCP_ARTIFACT_REPO
GCP_WORKLOAD_IDENTITY_PROVIDER
GCP_SERVICE_ACCOUNT
MODEL_SERVICE_NAME
BACKEND_SERVICE_NAME
MODEL_SERVICE_URL
DB_URL
DB_USER
DB_PASS_SECRET
APP_CORS_ALLOWED_ORIGINS
```

## Commands After Values Are Filled

Cloud Run:

```powershell
.\web\scripts\deploy-cloud-run.ps1
```

Frontend on Firebase:

```powershell
.\web\scripts\deploy-frontend-firebase.ps1
```

Smoke test:

```powershell
.\web\scripts\smoke-test.ps1
```
