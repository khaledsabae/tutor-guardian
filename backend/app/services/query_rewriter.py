"""Colloquial-to-search query rewriting.

Parents write in dialect («ابني بيعيط وبيعمل دماغه») while the KB is
fuṣḥā — embeddings partially bridge that, BM25 doesn't. A single
local-fast LLM call turns the question into 3-5 fuṣḥā search keywords
used as an EXTRA retrieval query (the raw question is always kept).

Skipped when the domain classifier already matched via its keyword
fast-path (the question is clearly KB-aligned — latency not worth it).
Results cached in ops/sessions.db so repeated questions are free.

The call goes through the gateway's auxiliary helpers, so it follows the
configured primary provider (with its telemetry and monthly ceiling) and
shares the classifier's circuit breaker — once one of them has found the
host dead, the other doesn't pay the timeout to rediscover it.
"""
from __future__ import annotations

import hashlib
import logging
import sqlite3
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)

_CACHE_DB = Path(__file__).resolve().parents[3] / "ops" / "sessions.db"
_REWRITE_TIMEOUT_S = 6

_PROMPT = (
    "حوّل سؤال الوالد التالي إلى كلمات بحث بالعربية الفصحى (3 إلى 5 كلمات "
    "فقط، بدون شرح، مفصولة بمسافات):\n{question}"
)


_schema_initialized = False


def _get_conn() -> sqlite3.Connection:
    """Open a WAL-mode connection with a busy timeout to prevent lock errors."""
    global _schema_initialized
    conn = sqlite3.connect(_CACHE_DB, timeout=5.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    if not _schema_initialized:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS query_rewrites (
                question_hash TEXT PRIMARY KEY, rewritten TEXT,
                ts TEXT DEFAULT (datetime('now')))"""
        )
        conn.commit()
        _schema_initialized = True
    return conn


def _cache_get(qhash: str) -> str | None:
    try:
        conn = _get_conn()
        row = conn.execute(
            "SELECT rewritten FROM query_rewrites WHERE question_hash=?", (qhash,)
        ).fetchone()
        conn.close()
        return row[0] if row else None
    except Exception:  # noqa: BLE001
        return None


def _cache_put(qhash: str, rewritten: str) -> None:
    try:
        conn = _get_conn()
        conn.execute(
            "INSERT OR REPLACE INTO query_rewrites (question_hash, rewritten) VALUES (?,?)",
            (qhash, rewritten),
        )
        conn.commit()
        conn.close()
    except Exception:  # noqa: BLE001
        pass



class _RewriteUnavailable(Exception):
    """The provider call itself failed — as opposed to succeeding with an
    unusable answer. Kept as an exception so neither cache layer memoises it:
    lru_cache doesn't store exceptions, and the sqlite write is skipped, so a
    transient outage doesn't permanently disable rewriting for a question.
    """


@lru_cache(maxsize=256)
def _rewrite_cached(question: str) -> str:
    qhash = hashlib.sha256(question.encode()).hexdigest()[:24]
    cached = _cache_get(qhash)
    if cached is not None:
        return cached

    from app.config.llm_config import LLM
    from app.services.ai_gateway import (
        OllamaProvider, aux_breaker, aux_cloud_provider, aux_generate,
    )

    if aux_breaker.is_open():
        raise _RewriteUnavailable("auxiliary circuit open")

    provider = aux_cloud_provider(timeout=_REWRITE_TIMEOUT_S) or OllamaProvider(
        base_url=LLM.local_base_url, model=LLM.local_fast_model,
        timeout=_REWRITE_TIMEOUT_S,
    )
    raw = aux_generate(
        provider, _PROMPT.format(question=question[:400]),
        options={"temperature": 0.1, "num_predict": 40},
        tier="query_rewrite",
    )
    if raw is None:
        raise _RewriteUnavailable("provider call failed")

    # sanity: keep it short and single-line, else discard. The call worked, so
    # an unusable answer IS cacheable — asking again would waste the same call.
    rewritten = raw.splitlines()[0].strip() if raw else ""
    if not (2 <= len(rewritten.split()) <= 8):
        rewritten = ""
    logger.debug("query rewrite: %r → %r", question[:40], rewritten)

    _cache_put(qhash, rewritten)
    return rewritten


def rewrite_query(question: str, *, classifier_fast_path: bool) -> str:
    """Return fuṣḥā search keywords for `question`, or "" to skip.

    `classifier_fast_path=True` means the domain classifier matched via
    keywords — the question already speaks the KB's language.
    """
    if classifier_fast_path or not question or len(question) < 12:
        return ""
    try:
        return _rewrite_cached(question.strip())
    except _RewriteUnavailable as exc:
        logger.debug("query rewrite skipped: %s", exc)
        return ""  # best-effort: the raw question is always searched anyway
