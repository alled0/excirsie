# Web App Setup

Three separate services — each lives in its own folder.

```
web/
├── model-service/   Python (FastAPI) — runs the pose pipeline
├── backend/         Java (Spring Boot) — REST gateway + feedback DB
└── frontend/        TypeScript (Angular) — the browser app
```

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

Runs on **port 8080**. Feedback is stored in `web/backend/data/feedback-db.mv.db`.

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

For a cloud deployment, push all three images to a registry and update
`docker-compose.yml` to use them, or deploy each service to its preferred
runtime (e.g. Cloud Run for Python, App Engine / ECS for Java, Vercel/Netlify
for the static Angular build).

---

## Reviewing collected feedback

Spring Boot exposes a read-only admin endpoint:

```
GET http://localhost:8080/api/feedback
GET http://localhost:8080/api/feedback?exerciseKey=1
```

The embedded H2 console (for quick inspection during dev) is at:
`http://localhost:8080/h2-console`  — JDBC URL: `jdbc:h2:file:./data/feedback-db`
