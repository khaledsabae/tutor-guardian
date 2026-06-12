"""Cross-encoder reranking of hybrid-retrieval candidates.

Default model: cross-encoder/mmarco-mMiniLMv2-L12-H384-v1 — multilingual
(mMARCO includes Arabic), ~118M params, scores ~8 query-passage pairs in
well under a second on CPU. RERANKER_MODEL env can opt into the stronger
BAAI/bge-reranker-v2-m3 on hosts with CPU headroom.

Hard latency budget: if a rerank call exceeds RERANK_BUDGET_S the module
disables itself for the process lifetime and callers fall back to the
fusion (RRF) ordering — quality degrades gracefully, UX never stalls.
"""
from __future__ import annotations

import logging
import os
import threading
import time

logger = logging.getLogger(__name__)

RERANKER_MODEL = os.environ.get(
    "RERANKER_MODEL", "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"
)
# Calibrated on the golden set: relevant Arabic passages score ≈ -0.8…-5
# with mmarco-MiniLM logits; below ≈ -6 is reliably off-topic.
RERANK_MIN_SCORE = float(os.environ.get("RERANK_MIN_SCORE", "-6.0"))
RERANK_BUDGET_S = float(os.environ.get("RERANK_BUDGET_S", "2.0"))
RERANK_ENABLED = os.environ.get("RERANK_ENABLED", "true").lower() in ("1", "true", "yes")

_model = None
_lock = threading.Lock()
_disabled = False


def _get_model():
    global _model
    if _model is None:
        with _lock:
            if _model is None:
                from sentence_transformers import CrossEncoder

                t0 = time.monotonic()
                _model = CrossEncoder(RERANKER_MODEL, max_length=256)
                logger.info("reranker %s loaded in %.1fs",
                            RERANKER_MODEL, time.monotonic() - t0)
    return _model


def rerank(query: str, candidates: list[dict], top_n: int = 4) -> list[dict]:
    """Score candidates against the query; return the best `top_n`.

    On any failure (or after a budget blowout) returns the input order
    trimmed to top_n — never raises.
    """
    global _disabled
    if not candidates:
        return []
    if not RERANK_ENABLED or _disabled:
        return candidates[:top_n]
    try:
        model = _get_model()
        pairs = [
            (query, (c.get("document") or "").removeprefix("passage: ")[:1500])
            for c in candidates
        ]
        t0 = time.monotonic()
        scores = model.predict(pairs, show_progress_bar=False)
        elapsed = time.monotonic() - t0
        for c, s in zip(candidates, scores):
            c["rerank_score"] = float(s)
        if elapsed > RERANK_BUDGET_S:
            logger.warning(
                "reranker exceeded budget (%.2fs > %.1fs) — disabling for this process",
                elapsed, RERANK_BUDGET_S,
            )
            _disabled = True
        kept = sorted(candidates, key=lambda c: -c["rerank_score"])[:top_n]
        filtered = [c for c in kept if c["rerank_score"] >= RERANK_MIN_SCORE]
        # never return nothing because of an over-aggressive threshold
        return filtered or kept[:1]
    except Exception as exc:  # noqa: BLE001 — degrade, don't break retrieval
        logger.warning("rerank failed (%s) — falling back to fusion order", exc)
        return candidates[:top_n]
