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
import os
import re
import sqlite3
from functools import lru_cache

from app.db.init_db import db_path

logger = logging.getLogger(__name__)

_REPLACEMENT = "طفلي"
# Arabic prefixes that attach directly to names (لـ/بـ/و/فـ/ال…).
_PREFIX = r"(?:ال|لل|و|ف|ب|ل|ك)?"
# Word boundaries for Arabic script. Without them a name matched INSIDE other
# words: a child named «نور» rewrote «منورة» and «النور», and a name that is
# also a word ("أمل", "هدى") corrupted ordinary sentences (audit M4).
_AR_LETTER = r"[\u0621-\u064A\u066E-\u06D3]"
# Attached particles can stack — a conjunction then a preposition/article:
# «وبأحمد», «ولأحمد», «فالنور». One optional prefix was enough while there
# was no word boundary; with one, the chain has to be spelled out.
_PREFIX_CHAIN = r"(?:و|ف)?(?:ال|لل|ب|ل|ك)?"


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


def names_for_device(device_id: str | None) -> tuple[str, ...]:
    """The CALLER's children's names (longest first), or () on any error.

    Redaction used to replace every child name in the whole database — so a
    family asking about «يوسف عليه السلام» got «طفلي عليه السلام» sent to the
    cloud because some other family has a son named Yusuf, and the fiqh
    domain is exactly what routes to the cloud tier (audit M4). The PII a
    parent types is their own child's name; that is the set to remove.
    One indexed read per call, from a worker thread.
    """
    if not device_id:
        return ()
    try:
        conn = sqlite3.connect(db_path())
        try:
            rows = conn.execute(
                "SELECT name FROM child_profiles WHERE device_id = ?", (device_id,)
            ).fetchall()
        finally:
            conn.close()
    except Exception as exc:  # noqa: BLE001 — fail open, never break a request
        logger.debug("privacy: names for device unavailable: %s", exc)
        return ()
    return tuple(sorted(
        {(r[0] or "").strip() for r in rows if r[0] and len(r[0].strip()) >= 2},
        key=len, reverse=True,
    ))


def mentions_any(text: str, names: tuple[str, ...]) -> bool:
    """True when `text` contains one of `names` as a word (prefixes allowed)."""
    return any(_name_pattern(n).search(text or "") for n in names)


@lru_cache(maxsize=4096)
def _name_pattern(name: str) -> "re.Pattern[str]":
    return re.compile(
        rf"(?<!{_AR_LETTER}){_PREFIX_CHAIN}{re.escape(name)}(?!{_AR_LETTER})"
    )


def known_child_names() -> tuple[str, ...]:
    """Child names from the local store, cached ~per-process."""
    try:
        epoch = int(os.path.getmtime(db_path()))
    except Exception:
        epoch = 0
    return _known_names_cached(epoch)


def redact_for_cloud(text: str, device_id: str | None = None) -> str:
    """Replace child names with «طفلي» before any cloud call.

    With `device_id` (the normal path) only that family's children are
    redacted; without one, every known name is — the old behaviour, now
    word-bounded, kept for callers that have no identity.
    """
    if not text:
        return text
    names = names_for_device(device_id) if device_id else known_child_names()
    redacted = text
    for name in names:
        redacted = _name_pattern(name).sub(_REPLACEMENT, redacted)
    return redacted
