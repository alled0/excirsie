# Web App Setup

Three separate services — each lives in its own folder.

```
web/
├── model-service/   Python (FastAPI) — runs the pose pipeline
├── backend/         Java (Spring Boot) — REST gateway + feedback DB
└── frontend/        TypeScript (Angular) — the browser app
```

For the short daily run commands, see `RUN_EACH_TIME.md`.
For the production deployment plan, see `DEPLOYMENT.md`.
For the remaining cloud values and secrets, see `CREDENTIALS_TODO.md`.

---

## Local development (no Docker)

### 1. Python model service

```bash
cd web/model-service
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8081 --reload
```

The first start downloads the pose model (~5 MB). After that it stays on disk.

---

### 2. Spring Boot backend

Requirements: Java 17+, Maven 3.9+

```bash
cd web/backend
mvn spring-boot:run
```

Runs on **port 8080**. Local backend data is stored in `web/backend/data/workout-dev.mv.db`.

To point at a remote model service, set the env var:
```bash
MODEL_SERVICE_URL=http://<host>:8081 mvn spring-boot:run
```

---

### 3. Angular frontend

Requirements: Node 20+, npm

```bash
cd web/frontend
npm install
npm start          # proxies /api → localhost:8080
```

Runs on **http://localhost:4200**.

---

## Production build (Docker Compose)

```bash
# Build the Angular bundle first
cd web/frontend
npm install
npm run build:prod

# Then start everything
cd web
docker compose up --build
```

- Frontend → http://localhost:4200  (nginx)
- Backend  → http://localhost:8080  (Spring Boot)
- Model    → http://localhost:8081  (FastAPI, internal only)

For a cloud deployment, use the production plan in `DEPLOYMENT.md`.

---

## Reviewing collected feedback

Spring Boot exposes a read-only admin endpoint:

```
GET http://localhost:8080/api/feedback
GET http://localhost:8080/api/feedback?exerciseKey=1
```

The embedded H2 console (for quick inspection during dev) is at:
`http://localhost:8080/h2-console`  — JDBC URL: `jdbc:h2:file:./data/workout-dev`
