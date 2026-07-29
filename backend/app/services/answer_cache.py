"""Semantic answer cache — «كاش الأسئلة المتكررة» (growth plan §5.1).

Parents' questions repeat heavily («ابني لا يصلي», «التبول اللاإرادي»…). The
chat prompt contains NO child-personal data (only age_group/domain/severity +
KB units + session history), so an answer generated for one parent's cold
question is exactly as correct for the next parent asking the same thing.

Safety envelope — an answer is served from / stored into the cache ONLY when:
  * the flag is on (ANSWER_CACHE_ENABLED)
  * it is the session's FIRST question (no assistant turns in history), so the
    answer cannot depend on earlier conversation
  * the reply was locally generated, grounded, and not flagged for review
Everything else falls through to live generation, unchanged.

Lookup = exact normalized-hash match first, then cosine similarity over the
stored e5 embeddings (same model RAG already uses). Hits are logged into the
existing llm_calls telemetry as provider='answer_cache', so the hit rate the
plan wants to measure is simply: answer_cache calls / assistant calls.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import sqlite3
import time
from pathlib import Path

logger = logging.getLogger(__name__)

ANSWER_CACHE_ENABLED = os.environ.get(
    "ANSWER_CACHE_ENABLED", "false"
).lower() in ("1", "true", "yes")
_TTL_DAYS = int(os.environ.get("ANSWER_CACHE_TTL_DAYS", "45"))
_MIN_SIM = float(os.environ.get("ANSWER_CACHE_MIN_SIM", "0.92"))
_MIN_ANSWER_LEN = 80
_MAX_CANDIDATES = 500  # brute-force cosine scan cap per lookup

_DB = Path(os.environ.get(
    "ANSWER_CACHE_DB",
    str(Path(__file__).resolve().parents[3] / "ops" / "sessions.db"),
))

# Arabic normalization: strip tashkeel/tatweel, unify alef/yaa/taa-marbuta,
# drop punctuation, collapse whitespace.
_TASHKEEL_RE = re.compile(r"[ً-ْـ]")
# Arabic punctuation lives inside the Arabic Unicode block, so strip it
# explicitly before the generic non-word sweep.
_AR_PUNCT_RE = re.compile(r"[؟،؛«»٬٫٪]")
_PUNCT_RE = re.compile(r"[^\w\s؀-ۿ]")
_WS_RE = re.compile(r"\s+")


def normalize(text: str) -> str:
    text = (text or "").strip()
    text = _TASHKEEL_RE.sub("", text)
    text = text.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    text = text.replace("ى", "ي").replace("ة", "ه")
    text = _AR_PUNCT_RE.sub(" ", text)
    text = _PUNCT_RE.sub(" ", text)
    return _WS_RE.sub(" ", text).strip().lower()


def _key(question: str, age_group: str, domain: str, severity: str) -> str:
    payload = f"{normalize(question)}|{age_group}|{domain}|{severity}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _conn() -> sqlite3.Connection:
    _DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_DB)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute(
        """CREATE TABLE IF NOT EXISTS answer_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            qhash TEXT UNIQUE,
            question_norm TEXT NOT NULL,
            age_group TEXT NOT NULL,
            domain TEXT NOT NULL,
            severity TEXT NOT NULL,
            answer TEXT NOT NULL,
            embedding TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            hit_count INTEGER DEFAULT 0
        )"""
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_answer_cache_scope "
        "ON answer_cache (age_group, domain)"
    )
    return conn


def _embed(text: str) -> list[float] | None:
    """Embed via the RAG embedder (lazy import — heavy model)."""
    try:
        from app.services.retrieval import embed_query
        vec = embed_query(normalize(text))
        if vec is None:
            return None
        # chromadb may wrap the embedder and hand back a numpy array — force
        # a plain float list so truthiness/json behave.
        return [float(x) for x in vec]
    except Exception as exc:  # noqa: BLE001 — cache degrades to exact-match only
        logger.debug("answer-cache embedding unavailable: %s", exc)
        return None


def _cosine(a: list[float], b: list[float]) -> float:
    # Embeddings are L2-normalized → dot product == cosine similarity.
    if len(a) != len(b):
        return -1.0
    return sum(x * y for x, y in zip(a, b))


def lookup(question: str, age_group: str, domain: str, severity: str) -> str | None:
    """Cached answer for an equivalent question, or None."""
    if not ANSWER_CACHE_ENABLED:
        return None
    start = time.monotonic()
    try:
        conn = _conn()
        try:
            fresh = f"-{_TTL_DAYS} days"
            row = conn.execute(
                "SELECT id, answer FROM answer_cache "
                "WHERE qhash = ? AND created_at >= datetime('now', ?)",
                (_key(question, age_group, domain, severity), fresh),
            ).fetchone()
            match_kind = "exact"
            if row is None:
                vec = _embed(question)
                if vec is None:
                    return None
                candidates = conn.execute(
                    "SELECT id, answer, embedding FROM answer_cache "
                    "WHERE age_group = ? AND domain = ? AND severity = ? "
                    "AND embedding IS NOT NULL "
                    "AND created_at >= datetime('now', ?) "
                    "ORDER BY hit_count DESC LIMIT ?",
                    (age_group, domain, severity, fresh, _MAX_CANDIDATES),
                ).fetchall()
                best, best_sim = None, _MIN_SIM
                for cand in candidates:
                    try:
                        sim = _cosine(vec, json.loads(cand["embedding"]))
                    except Exception:  # noqa: BLE001
                        continue
                    if sim >= best_sim:
                        best, best_sim = cand, sim
                if best is None:
                    return None
                row, match_kind = best, "semantic"
            conn.execute(
                "UPDATE answer_cache SET hit_count = hit_count + 1 WHERE id = ?",
                (row["id"],),
            )
            conn.commit()
        finally:
            conn.close()
        latency = int((time.monotonic() - start) * 1000)
        try:
            from app.services.ai_gateway import _log_call
            _log_call("answer_cache", match_kind, latency, None, None,
                      streamed=False, ok=True, tier="cache",
                      route_reason="answer_cache_hit")
        except Exception:  # noqa: BLE001
            pass
        return row["answer"]
    except Exception as exc:  # noqa: BLE001 — cache must never break chat
        logger.warning("answer-cache lookup failed: %s", exc)
        return None


def purge(reason: str = "") -> int:
    """Drop every cached answer. Returns how many were removed.

    A cached answer is a frozen copy of what the knowledge base said at the
    moment it was generated — including the «📚 المصادر» line. When the units
    change underneath it, the cache keeps serving the old text: after the
    citation repairs on 2026-07-29 a parent asking about ADHD was still shown
    the pre-fix source line, and would have been for the 45-day TTL.

    So the cache is dropped whenever the index is actually rebuilt. A miss
    costs one generation (~$0.0005 and a couple of seconds); a stale hit costs
    a wrong citation, which is the thing this app promises not to do.
    """
    if not ANSWER_CACHE_ENABLED:
        return 0
    try:
        conn = _conn()
        try:
            removed = conn.execute("SELECT COUNT(*) FROM answer_cache").fetchone()[0]
            conn.execute("DELETE FROM answer_cache")
            conn.commit()
        finally:
            conn.close()
        if removed:
            logger.info("answer cache purged (%d entries)%s",
                        removed, f" — {reason}" if reason else "")
        return int(removed)
    except Exception as exc:  # noqa: BLE001 — the cache must never break chat
        logger.warning("answer-cache purge failed: %s", exc)
        return 0


def store(question: str, age_group: str, domain: str, severity: str, answer: str) -> bool:
    """Store a freshly generated first-question answer. Best-effort."""
    if not ANSWER_CACHE_ENABLED:
        return False
    answer = (answer or "").strip()
    if len(answer) < _MIN_ANSWER_LEN:
        return False
    try:
        vec = _embed(question)
        conn = _conn()
        try:
            conn.execute(
                "INSERT INTO answer_cache "
                "(qhash, question_norm, age_group, domain, severity, answer, embedding) "
                "VALUES (?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(qhash) DO UPDATE SET "
                "answer = excluded.answer, created_at = datetime('now')",
                (
                    _key(question, age_group, domain, severity),
                    normalize(question)[:500],
                    age_group, domain, severity, answer,
                    json.dumps(vec) if vec else None,
                ),
            )
            conn.commit()
            return True
        finally:
            conn.close()
    except Exception as exc:  # noqa: BLE001
        logger.warning("answer-cache store failed: %s", exc)
        return False
