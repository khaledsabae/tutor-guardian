# Tutor Guardian backend — FastAPI + ChromaDB (ONNX, CPU). Build context = repo root.
FROM python:3.11-slim

# Create a non-root user — running as root in production is a security risk.
RUN groupadd -g 10001 appgroup && \
    useradd -u 10001 -g appgroup -m -s /bin/bash appuser

WORKDIR /app

# onnxruntime needs libgomp1; curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgomp1 curl \
    && rm -rf /var/lib/apt/lists/*

# Point HF model cache to a path inside /app so appuser can write to it.
ENV HF_HOME=/app/.cache/huggingface

COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# Pre-download the embedding + reranker models into the image so cold
# start needs no Hugging Face network access (e5 ~250MB, reranker ~470MB).
RUN python -c "from sentence_transformers import SentenceTransformer, CrossEncoder; \
    SentenceTransformer('intfloat/multilingual-e5-small'); \
    CrossEncoder('cross-encoder/mmarco-mMiniLMv2-L12-H384-v1', max_length=256)"

# App code + knowledge base + tools (units are needed to build the vector index)
COPY backend/ ./backend/
COPY knowledge_base/ ./knowledge_base/
COPY ops/tools/ ./ops/tools/
COPY frontend/ ./frontend/
COPY docs/ ./docs/
COPY .well-known/ ./.well-known/

# Transfer ownership before switching user
RUN chown -R appuser:appgroup /app

ENV PROJECT_ROOT=/app \
    PYTHONPATH=/app/backend \
    PYTHONUNBUFFERED=1 \
    CONVERSATIONS_DB=/app/ops/conversations.db

# Drop to non-root user for security
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--app-dir", "backend", "--host", "0.0.0.0", "--port", "8000"]
