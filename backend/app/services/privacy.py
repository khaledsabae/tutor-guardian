"""Privacy redaction for the cloud quality tier.

Cloud payload contract (the ONLY things ever sent to the cloud provider):
  • the parent's question text — redacted by this module
  • recent conversation turns — redacted by this module
  • retrieved KB chunks (public-source curriculum content)
  • age_group + severity labels

NEVER sent: child profile records, device identifiers, session ids,
progress data, or any other stored personal data.

Redaction strategy: child names typed by the parent are the realistic
PII vector. We replace every known child name (from the local
`child_profiles` store) with the generic «طفلي». Best-effort and
fail-open: if the store is unreadable we return the text unchanged —
the cloud tier is an opt-in quality upgrade, not a data pipeline.
"""
from __future__ import annotations

import logging
import re
import sqlite3
from functools import lru_cache

from app.db.init_db import db_path

logger = logging.getLogger(__name__)

_REPLACEMENT = "طفلي"
# Arabic prefixes that attach directly to names (لـ/بـ/و/فـ/ال…).
_PREFIX = r"(?:ال|لل|و|ف|ب|ل|ك)?"


@lru_cache(maxsize=1)
def _known_names_cached(_epoch: int) -> tuple[str, ...]:
    try:
        conn = sqlite3.connect(db_path())
        rows = conn.execute("SELECT name FROM child_profiles").fetchall()
        conn.close()
        names = sorted(
            {(r[0] or "").strip() for r in rows if r[0] and len(r[0].strip()) >= 2},
            key=len,
            reverse=True,  # longest first so "عبد الرحمن" wins over "عبد"
        )
        return tuple(names)
    except Exception as exc:  # noqa: BLE001 — fail open, never break a request
        logger.debug("privacy: child names unavailable: %s", exc)
        return ()


def known_child_names() -> tuple[str, ...]:
    """Child names from the local store, cached ~per-process."""
    return _known_names_cached(0)


def redact_for_cloud(text: str) -> str:
    """Replace known child names with «طفلي» before any cloud call."""
    if not text:
        return text
    redacted = text
    for name in known_child_names():
        pattern = rf"{_PREFIX}{re.escape(name)}"
        redacted = re.sub(pattern, _REPLACEMENT, redacted)
    return redacted
