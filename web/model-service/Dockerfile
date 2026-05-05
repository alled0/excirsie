FROM python:3.11-slim

WORKDIR /app

# System deps required by OpenCV / MediaPipe
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 libsm6 libxext6 libxrender1 libgl1 libegl1 libgles2 libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY web/model-service/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the shared taharrak package and the service entrypoint
COPY taharrak/ taharrak/
COPY config.json config.json
COPY web/model-service/main.py main.py

# Pre-download the pose model so the first request is fast
RUN python -c "from taharrak.eval import _ensure_model; _ensure_model()"

EXPOSE 8080
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8081}"]
