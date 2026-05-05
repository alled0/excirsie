# Copy this file to web/deploy.local.ps1 and fill in real values.
# web/deploy.local.ps1 is gitignored.

$env:PROJECT_ID = "your-gcp-project-id"
$env:REGION = "me-central2"
$env:ARTIFACT_REPO = "taharrak"

# Firebase Hosting can use the same project as Cloud Run, or a different one.
# FIREBASE_SITE_ID must be an existing Hosting site in that Firebase project.
$env:FIREBASE_PROJECT_ID = "your-firebase-project-id"
$env:FIREBASE_SITE_ID = "your-firebase-hosting-site-id"

# demo = no Cloud SQL, lowest-cost/free-first deploy. Data can reset.
# prod = PostgreSQL on Cloud SQL, durable production deploy.
$env:DEPLOY_MODE = "demo"

$env:MODEL_SERVICE_NAME = "taharrak-model-service"
$env:BACKEND_SERVICE_NAME = "taharrak-backend"

# These are filled automatically by web/scripts/deploy-cloud-run.ps1 after the
# first Cloud Run deployment. You may replace them later with custom domains.
$env:MODEL_SERVICE_URL = ""
$env:BACKEND_URL = ""

# Required only when DEPLOY_MODE = "prod".
$env:DB_URL = "jdbc:postgresql://<host>:5432/taharrak"
$env:DB_USER = "taharrak_app"
$env:DB_PASS_SECRET = "taharrak-db-pass:latest"

# For demo, "*" is okay. For production, set your Firebase/custom domain.
$env:APP_CORS_ALLOWED_ORIGINS = "*"

# Leave blank to let the deploy script write deployed Cloud Run URLs.
$env:FRONTEND_API_BASE = ""
$env:FRONTEND_MODEL_BASE = ""
$env:FRONTEND_WS_BASE = ""

# Cost/performance guards for demo mode.
# Set MIN_INSTANCES to 1 when you want the deployed app to feel responsive.
# Set MIN_INSTANCES back to 0 when you want the cheapest possible idle cost.
$env:MODEL_MIN_INSTANCES = "0"
$env:MODEL_MAX_INSTANCES = "1"
$env:MODEL_CONCURRENCY = "1"
$env:BACKEND_MIN_INSTANCES = "0"
$env:BACKEND_MAX_INSTANCES = "1"

# Uploaded-video speed knobs. Lower FPS/width is faster, but less precise.
$env:ANALYSIS_TARGET_FPS = "15"
$env:ANALYSIS_MAX_WIDTH = "720"
