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

from pathlib import Path

_FINETUNED_RERANKER_DIR = Path(
    os.environ.get(
        "TG_RERANKER_V2_DIR",
        str(Path(__file__).resolve().parents[3] / "ops" / "models" / "tg-reranker-v2"),
    )
)
RERANKER_MODEL = os.environ.get(
    "RERANKER_MODEL",
    str(_FINETUNED_RERANKER_DIR)
    if (_FINETUNED_RERANKER_DIR / "config.json").exists()
    else "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1",
)
# Calibrated on the golden set: relevant Arabic passages score ≈ -0.8…-5
# with mmarco-MiniLM logits; below ≈ -6 is reliably off-topic.
# It is also the ABSOLUTE floor: when even the best candidate is below it,
# rerank() returns an empty NoConfidentMatch (see below), not the nearest unit.
# Re-measured on 126 golden questions: no floor between -6 and -5 loses an
# expected unit, but each step up also turns away in-scope questions (10/100 at
# -5, 20/100 at -4.25) for one more abstention, so -6 stays. Scores are logits
# of the default mmarco model; a different RERANKER_MODEL (e.g. the fine-tuned
# tg-reranker-v2) needs its own value — this is why it is env-configurable.
RERANK_MIN_SCORE = float(os.environ.get("RERANK_MIN_SCORE", "-6.0"))
# The production VPS scores a 4-candidate batch in 2–3s. At the old 2.0s the
# reranker disabled itself within the first few requests of every process, which
# also silently killed off-topic detection (assistant._off_topic reads
# rerank_score). 6.0s leaves headroom without hiding a genuinely overloaded box.
RERANK_BUDGET_S = float(os.environ.get("RERANK_BUDGET_S", "6.0"))
# Consecutive over-budget calls before giving up. One slow call is normal
# (cold caches, a loaded box); a sustained streak means the box can't keep up.
RERANK_MAX_STRIKES = int(os.environ.get("RERANK_MAX_STRIKES", "3"))
RERANK_ENABLED = os.environ.get("RERANK_ENABLED", "true").lower() in ("1", "true", "yes")

class NoConfidentMatch(list):
    """The empty result of a rerank where nothing cleared the relevance floor.

    An ordinary empty list to every caller (`not x`, `len(x) == 0`, iteration),
    so nothing that already handles "no units" changes. It additionally carries
    the best score seen, which is how assistant._off_topic can tell "the
    reranker looked and found nothing relevant" (-> the off-topic pivot, exactly
    what a lone below-floor unit used to trigger) from "retrieval produced
    nothing / the reranker was off" (-> "no information, see a specialist").
    Slicing returns a plain list and drops the marker: return it as is.
    """

    def __init__(self, best_rerank_score: float | None = None):
        super().__init__()
        self.best_rerank_score = best_rerank_score


_model = None
_lock = threading.Lock()
_disabled = False
_slow_calls = 0


def _get_model():
    global _model
    if _model is None:
        with _lock:
            if _model is None:
                import torch
                from sentence_transformers import CrossEncoder

                t0 = time.monotonic()
                model_path = (
                    str(_FINETUNED_RERANKER_DIR)
                    if not os.environ.get("RERANKER_MODEL")
                    and (_FINETUNED_RERANKER_DIR / "config.json").exists()
                    else RERANKER_MODEL
                )
                _model = CrossEncoder(
                    model_path,
                    max_length=256,
                    activation_fn=torch.nn.Identity(),
                )
                logger.info("reranker %s loaded in %.1fs",
                            model_path, time.monotonic() - t0)
    return _model


def eager_load_model():
    """Trigger model loading on startup."""
    try:
        if RERANK_ENABLED and not _disabled:
            _get_model()
    except Exception as e:
        logger.warning("Failed to eager-load reranker: %s", e)


def is_disabled() -> bool:
    """Has this process switched the reranker off after repeated slow calls?

    Worth asking from outside because the switch takes the off-topic detector
    down with it (`assistant._off_topic` reads `rerank_score`), and the only
    trace it left was a single log line. The app kept answering, with raw
    retrieval order and no topic filter, while every health surface stayed green.
    """
    return _disabled


def rerank(query: str, candidates: list[dict], top_n: int = 4) -> list[dict]:
    """Score candidates against the query; return the best `top_n` that clear
    RERANK_MIN_SCORE.

    If even the best candidate is below the floor the result is an empty
    `NoConfidentMatch` — "nothing relevant", which is not the same as "no
    candidates" (an ordinary empty list). On any failure (or after a budget
    blowout) returns the input order trimmed to top_n — never raises.
    """
    global _disabled
    if not candidates:
        return []
    if not RERANK_ENABLED or _disabled:
        return candidates[:top_n]
    global _slow_calls
    try:
        # Model load must not be charged to the latency budget — the first
        # scoring call after a cold start pays ~3s of weight loading, which
        # used to trip the one-strike disable and silently kill reranking (and
        # with it off-topic detection) for the whole process lifetime.
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
            _slow_calls += 1
            logger.warning(
                "reranker exceeded budget (%.2fs > %.1fs) — strike %d/%d",
                elapsed, RERANK_BUDGET_S, _slow_calls, RERANK_MAX_STRIKES,
            )
            if _slow_calls >= RERANK_MAX_STRIKES:
                logger.warning("reranker disabled for this process after %d strikes",
                               _slow_calls)
                _disabled = True
        else:
            _slow_calls = 0
        ranked = sorted(candidates, key=lambda c: -c["rerank_score"])
        best = ranked[0]["rerank_score"]
        # Absolute floor. This replaces the old "never return nothing" rule
        # (`filtered or kept[:1]`), which handed the parent the nearest unit
        # however irrelevant it was: a teen-doubt unit as the ONLY result for
        # a router-configuration question (-6.7) or a TikTok follow-up (-7.2).
        # An empty result is safe to hand back: assistant._off_topic routes it
        # to the pivot exactly as it routed the lone sub-floor unit, a plain
        # empty list still gets the "no sufficient information" reply, and
        # emergency escalation (keywords/severity) runs before retrieval.
        if best < RERANK_MIN_SCORE:
            return NoConfidentMatch(best)
        return [c for c in ranked[:top_n] if c["rerank_score"] >= RERANK_MIN_SCORE]
    except Exception as exc:  # noqa: BLE001 — degrade, don't break retrieval
        logger.warning("rerank failed (%s) — falling back to fusion order", exc)
        return candidates[:top_n]
