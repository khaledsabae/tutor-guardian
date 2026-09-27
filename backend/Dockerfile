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
# torch from the CPU-only index first. The default PyPI wheel for Linux is the
# CUDA build and drags in ~4 GB of nvidia-* libraries; this host has no GPU and
# the models run on CPU. The version comes from requirements.txt (the pin stays
# in one place); `2.13.0+cpu` satisfies `torch==2.13.0`, so the second install
# keeps it instead of pulling the CUDA build.
RUN TORCH_VERSION="$(sed -n 's/^torch==\([^ #]*\).*/\1/p' backend/requirements.txt)" \
    && test -n "$TORCH_VERSION" \
    && pip install --no-cache-dir "torch==${TORCH_VERSION}" \
        --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r backend/requirements.txt \
    && ! pip list 2>/dev/null | grep -qi '^nvidia-'

# Pre-download the embedding + reranker models into the image so cold
# start needs no Hugging Face network access (e5 ~250MB, reranker ~470MB).
# Owned by appuser in the same layer: a later `chown -R` would copy every
# file into a new layer and double the size.
RUN python -c "from sentence_transformers import SentenceTransformer, CrossEncoder; \
    SentenceTransformer('intfloat/multilingual-e5-small'); \
    CrossEncoder('cross-encoder/mmarco-mMiniLMv2-L12-H384-v1', max_length=256)" \
    && chown -R appuser:appgroup "$HF_HOME"

# App code + knowledge base + tools (units are needed to build the vector index).
# --chown at copy time for the same reason: the old trailing
# `RUN chown -R appuser:appgroup /app` duplicated all of /app, models included.
COPY --chown=appuser:appgroup backend/ ./backend/
COPY --chown=appuser:appgroup knowledge_base/ ./knowledge_base/
COPY --chown=appuser:appgroup ops/tools/ ./ops/tools/
COPY --chown=appuser:appgroup ops/scripts/ ./ops/scripts/
COPY --chown=appuser:appgroup frontend/ ./frontend/
COPY --chown=appuser:appgroup docs/ ./docs/
COPY --chown=appuser:appgroup .well-known/ ./.well-known/

# The directories the app writes into (volumes in production, plain dirs in
# the candidate image the deploy tests run in). Directories only — no -R.
RUN mkdir -p /app/ops /app/knowledge_base/chroma_db \
    && chown appuser:appgroup /app /app/ops /app/knowledge_base /app/knowledge_base/chroma_db

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
