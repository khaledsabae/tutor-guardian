# Tutor Guardian backend — FastAPI + ChromaDB (ONNX, CPU). Build context = repo root.
FROM python:3.11-slim

WORKDIR /app

# onnxruntime needs libgomp1; curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgomp1 curl \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# App code + knowledge base + tools (units are needed to build the vector index)
COPY backend/ ./backend/
COPY knowledge_base/ ./knowledge_base/
COPY ops/tools/ ./ops/tools/
COPY frontend/ ./frontend/
COPY docs/ ./docs/

ENV PROJECT_ROOT=/app \
    PYTHONPATH=/app/backend \
    PYTHONUNBUFFERED=1 \
    CONVERSATIONS_DB=/app/ops/conversations.db

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--app-dir", "backend", "--host", "0.0.0.0", "--port", "8000"]
