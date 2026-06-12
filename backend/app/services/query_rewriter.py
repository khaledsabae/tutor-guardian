"""Colloquial-to-search query rewriting.

Parents write in dialect («ابني بيعيط وبيعمل دماغه») while the KB is
fuṣḥā — embeddings partially bridge that, BM25 doesn't. A single
local-fast LLM call turns the question into 3-5 fuṣḥā search keywords
used as an EXTRA retrieval query (the raw question is always kept).

Skipped when the domain classifier already matched via its keyword
fast-path (the question is clearly KB-aligned — latency not worth it).
Results cached in ops/sessions.db so repeated questions are free.
"""
from __future__ import annotations

import hashlib
import logging
import sqlite3
import time
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)

_CACHE_DB = Path(__file__).resolve().parents[3] / "ops" / "sessions.db"
_REWRITE_TIMEOUT_S = 6

_PROMPT = (
    "حوّل سؤال الوالد التالي إلى كلمات بحث بالعربية الفصحى (3 إلى 5 كلمات "
    "فقط، بدون شرح، مفصولة بمسافات):\n{question}"
)


def _cache_get(qhash: str) -> str | None:
    try:
        conn = sqlite3.connect(_CACHE_DB)
        conn.execute(
            """CREATE TABLE IF NOT EXISTS query_rewrites (
                question_hash TEXT PRIMARY KEY, rewritten TEXT,
                ts TEXT DEFAULT (datetime('now')))"""
        )
        row = conn.execute(
            "SELECT rewritten FROM query_rewrites WHERE question_hash=?", (qhash,)
        ).fetchone()
        conn.close()
        return row[0] if row else None
    except Exception:  # noqa: BLE001
        return None


def _cache_put(qhash: str, rewritten: str) -> None:
    try:
        conn = sqlite3.connect(_CACHE_DB)
        conn.execute(
            "INSERT OR REPLACE INTO query_rewrites (question_hash, rewritten) VALUES (?,?)",
            (qhash, rewritten),
        )
        conn.commit()
        conn.close()
    except Exception:  # noqa: BLE001
        pass


@lru_cache(maxsize=256)
def _rewrite_cached(question: str) -> str:
    qhash = hashlib.sha256(question.encode()).hexdigest()[:24]
    cached = _cache_get(qhash)
    if cached is not None:
        return cached

    try:
        import requests
        from app.config.llm_config import LLM

        t0 = time.monotonic()
        resp = requests.post(
            f"{LLM.local_base_url}/api/generate",
            json={
                "model": LLM.local_fast_model,
                "prompt": _PROMPT.format(question=question[:400]),
                "stream": False,
                "options": {"temperature": 0.1, "num_predict": 40},
            },
            timeout=_REWRITE_TIMEOUT_S,
        )
        resp.raise_for_status()
        rewritten = (resp.json().get("response") or "").strip()
        # sanity: keep it short and single-line, else discard
        rewritten = rewritten.splitlines()[0].strip() if rewritten else ""
        if not (2 <= len(rewritten.split()) <= 8):
            rewritten = ""
        logger.debug("query rewrite %.2fs: %r → %r",
                     time.monotonic() - t0, question[:40], rewritten)
    except Exception as exc:  # noqa: BLE001 — best-effort
        logger.debug("query rewrite skipped: %s", exc)
        rewritten = ""

    _cache_put(qhash, rewritten)
    return rewritten


def rewrite_query(question: str, *, classifier_fast_path: bool) -> str:
    """Return fuṣḥā search keywords for `question`, or "" to skip.

    `classifier_fast_path=True` means the domain classifier matched via
    keywords — the question already speaks the KB's language.
    """
    if classifier_fast_path or not question or len(question) < 12:
        return ""
    return _rewrite_cached(question.strip())
