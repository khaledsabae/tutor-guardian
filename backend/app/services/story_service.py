"""Pre-generated story cache — «توليد القصص مسبقًا» (growth plan §5.1).

Stories are the most expensive per-request generation in the app. The catalogue
of themes is fixed (STORY_THEMES) and the only personal element is the hero's
name, so almost every story can be generated once — offline, on the local
model — and served instantly from cache with the child's name substituted in.

Privacy rule: the cache is filled ONLY by the pre-generation batch
(ops/scripts/pregen_stories.py) using canonical hero names (سالم/سارة) — never
from live user requests — so one child's real name can never leak into a story
served to another family.

Gender matters: Arabic conjugates around the hero, so cached stories are keyed
by (theme, age_group, gender) and served only when the child's gender is known.
Unknown gender → caller falls back to live generation (previous behaviour).
"""
from __future__ import annotations

import logging
import random
import sqlite3

from app.db.init_db import get_conn

logger = logging.getLogger(__name__)

# Canonical hero names the batch generates with. Chosen to be unambiguous,
# common, and trivially replaceable (no diacritics, single token).
HERO_NAMES: dict[str, str] = {"male": "سالم", "female": "سارة"}

# How many distinct variants the batch aims to keep per (theme, age, gender) —
# enough that a repeat visitor doesn't get the exact same story twice in a row.
VARIANTS_PER_KEY = 2

_MIN_STORY_LENGTH = 200


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """CREATE TABLE IF NOT EXISTS story_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            theme TEXT NOT NULL,
            age_group TEXT NOT NULL,
            gender TEXT NOT NULL,
            hero_name TEXT NOT NULL,
            story TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now')),
            served_count INTEGER DEFAULT 0
        )"""
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_story_cache_key "
        "ON story_cache (theme, age_group, gender)"
    )


def personalize(story: str, hero_name: str, child_name: str) -> str:
    """Substitute the canonical hero name with the child's name."""
    child_name = child_name.strip()
    if not child_name or child_name == hero_name:
        return story
    return story.replace(hero_name, child_name)


def get_cached_story(theme: str, age_group: str, gender: str | None) -> dict | None:
    """Random cached variant for the key, or None (→ caller generates live)."""
    if gender not in HERO_NAMES:
        return None
    conn = get_conn()
    try:
        _ensure_schema(conn)
        rows = conn.execute(
            "SELECT id, hero_name, story FROM story_cache "
            "WHERE theme = ? AND age_group = ? AND gender = ?",
            (theme, age_group, gender),
        ).fetchall()
        if not rows:
            return None
        row = random.choice(rows)
        conn.execute(
            "UPDATE story_cache SET served_count = served_count + 1 WHERE id = ?",
            (row["id"],),
        )
        conn.commit()
        return {"id": row["id"], "hero_name": row["hero_name"], "story": row["story"]}
    except Exception as exc:  # noqa: BLE001 — cache must never break the endpoint
        logger.warning("story cache read failed: %s", exc)
        return None
    finally:
        conn.close()


def store_pregen_story(
    theme: str, age_group: str, gender: str, hero_name: str, story: str
) -> bool:
    """Store a batch-generated story. Returns False if it fails validation."""
    story = (story or "").strip()
    if len(story) < _MIN_STORY_LENGTH or hero_name not in story:
        return False
    conn = get_conn()
    try:
        _ensure_schema(conn)
        conn.execute(
            "INSERT INTO story_cache (theme, age_group, gender, hero_name, story) "
            "VALUES (?, ?, ?, ?, ?)",
            (theme, age_group, gender, hero_name, story),
        )
        conn.commit()
        return True
    finally:
        conn.close()


def variants_count(theme: str, age_group: str, gender: str) -> int:
    conn = get_conn()
    try:
        _ensure_schema(conn)
        row = conn.execute(
            "SELECT COUNT(*) FROM story_cache "
            "WHERE theme = ? AND age_group = ? AND gender = ?",
            (theme, age_group, gender),
        ).fetchone()
        return int(row[0] or 0)
    finally:
        conn.close()


def resolve_child_gender(device_id: str | None, child_id: int | None) -> str | None:
    """Gender of a child owned by this device, else None."""
    if not device_id or not child_id:
        return None
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT gender FROM child_profiles WHERE id = ? AND device_id = ?",
            (child_id, device_id),
        ).fetchone()
        gender = row["gender"] if row else None
        return gender if gender in HERO_NAMES else None
    except Exception:  # noqa: BLE001
        return None
    finally:
        conn.close()
