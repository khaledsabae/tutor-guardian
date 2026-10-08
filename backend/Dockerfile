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

# Production's frozen package set, hash-locked: every file pip may install is
# named by its sha256, so a republished or compromised wheel fails the build
# instead of entering the image. Versions are .github/ci/constraints-prod.txt's
# (production's own freeze — without it every deploy re-resolved
# requirements.txt's ranges: 2026-10-04 fastapi 0.141→0.142, oauthlib 3→4, +22
# more); regenerate with .github/ci/lock-backend-deps.py, never by hand.
# The hosted CI installs the same file (.github/actions/backend-env).
# torch is in it as a direct URL to the CPU-only wheel on
# download.pytorch.org/whl/cpu: the PyPI torch wheel for Linux is the CUDA build
# and drags in ~4 GB of nvidia-* libraries; this host has no GPU. Everything
# else comes from PyPI. --no-deps: the lock is the whole closure (pip check
# proves it); --only-binary: no package's build code runs here.
COPY .github/ci/requirements-prod.lock ./backend/requirements-prod.lock
RUN pip install --no-cache-dir --require-hashes --no-deps --only-binary=:all: \
        -r backend/requirements-prod.lock \
    && pip check \
    && ! pip list 2>/dev/null | grep -qi '^nvidia-'

# Pre-download the embedding + reranker models into the image so cold
# start needs no Hugging Face network access (e5 ~250MB, reranker ~470MB).
# Owned by appuser in the same layer: a later `chown -R` would copy every
# file into a new layer and double the size.
RUN python -c "from sentence_transformers import SentenceTransformer, CrossEncoder; \
    SentenceTransformer('intfloat/multilingual-e5-small'); \
    CrossEncoder('cross-encoder/mmarco-mMiniLMv2-L12-H384-v1', max_length=256)" \
    && chown -R appuser:appgroup "$HF_HOME"

# App code + knowledge base first: the baked index below depends on these two
# and nothing else, so a change to tools, scripts, frontend or docs reuses it.
# --chown at copy time for the same reason as above: the old trailing
# `RUN chown -R appuser:appgroup /app` duplicated all of /app, models included.
COPY --chown=appuser:appgroup backend/ ./backend/
COPY --chown=appuser:appgroup knowledge_base/ ./knowledge_base/

# The directories the app writes into (volumes in production, plain dirs in
# a container started from the image alone). Directories only — no -R.
RUN mkdir -p /app/ops /app/knowledge_base/chroma_db \
    && chown appuser:appgroup /app /app/ops /app/knowledge_base /app/knowledge_base/chroma_db

# Offline Hugging Face from here on: both models are in the image (above) and
# the knowledge index is baked with them (below), so the container must load
# exactly these files — never a newer revision that would no longer match the
# index — and must not wait on huggingface.co to start. Measured 2026-10-04
# with the hub unreachable: 146 s to healthy online, 11 s offline.
ENV PROJECT_ROOT=/app \
    PYTHONPATH=/app/backend \
    PYTHONUNBUFFERED=1 \
    CONVERSATIONS_DB=/app/ops/conversations.db \
    HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1

# Drop to non-root user for security
USER appuser

# Bake the knowledge index: the container's own startup call
# (retrieval._ensure_index — same units, same offline model, same fingerprint)
# run here, on the build machine, then parked at knowledge_base/chroma_seed.
# Production mounts the tg_chroma volume over chroma_db, so startup copies the
# seed into it when the volume's index is for other units — seconds, instead of
# re-embedding every unit on the production host. chroma_db is left empty.
RUN ANONYMIZED_TELEMETRY=False python -m app.services.index_seed \
    && rm -rf knowledge_base/chroma_seed \
    && mv knowledge_base/chroma_db knowledge_base/chroma_seed \
    && mkdir knowledge_base/chroma_db

COPY --chown=appuser:appgroup ops/tools/ ./ops/tools/
COPY --chown=appuser:appgroup ops/scripts/ ./ops/scripts/
COPY --chown=appuser:appgroup frontend/ ./frontend/
COPY --chown=appuser:appgroup docs/ ./docs/
COPY --chown=appuser:appgroup .well-known/ ./.well-known/

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--app-dir", "backend", "--host", "0.0.0.0", "--port", "8000"]
