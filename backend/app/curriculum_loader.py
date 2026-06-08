"""
Curriculum loader — يقرأ JSON files للمنهج من knowledge_base/curriculum/.

Three data types:
- paths/      : 3-30 day journeys
- lessons/    : 5-min lessons within a path
- daily_tips/ : short rotating tips (≤ 280 chars)

Loads at startup (eager) and exposes:
- get_paths(age_group, domain)            -> list of paths
- get_path(path_id)                       -> path or None
- get_lessons_for_path(path_id)           -> ordered list of lessons
- get_lesson(lesson_id)                   -> lesson or None
- get_daily_tips(age_group)               -> list of tips (rotating pool)

Filters by `is_published` so draft content is not exposed to the API.
"""
import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parents[2] / "knowledge_base" / "curriculum"

PATHS_DIR = BASE_DIR / "paths"
LESSONS_DIR = BASE_DIR / "lessons"
TIPS_DIR = BASE_DIR / "daily_tips"

# Module-level cache. Loaded once at startup via load_curriculum().
_paths_cache: dict[str, dict] = {}
_lessons_cache: dict[str, dict] = {}
_tips_cache: list[dict] = []


def _load_json(path: Path) -> Optional[dict]:
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning("[curriculum] failed to read %s: %s", path.name, e)
        return None


def _is_published(obj: dict) -> bool:
    """Treat missing `is_published` as published (tips default to true)."""
    return bool(obj.get("is_published", True))


def load_curriculum() -> None:
    """Eager-load all curriculum JSON. Call once at app startup."""
    global _paths_cache, _lessons_cache, _tips_cache

    # ── Paths ──
    paths: dict[str, dict] = {}
    for f in sorted(PATHS_DIR.glob("*.json")):
        d = _load_json(f)
        if d and d.get("id") and _is_published(d):
            paths[d["id"]] = d
    _paths_cache = paths

    # ── Lessons ──
    lessons: dict[str, dict] = {}
    for f in sorted(LESSONS_DIR.glob("*.json")):
        d = _load_json(f)
        if d and d.get("id") and _is_published(d):
            lessons[d["id"]] = d
    _lessons_cache = lessons

    # ── Daily Tips ──
    tips: list[dict] = []
    for f in sorted(TIPS_DIR.glob("*.json")):
        d = _load_json(f)
        if d and d.get("id") and _is_published(d):
            tips.append(d)
    _tips_cache = tips

    logger.info(
        "[curriculum] loaded %d paths, %d lessons, %d tips",
        len(_paths_cache), len(_lessons_cache), len(_tips_cache),
    )


def curriculum_stats() -> dict:
    """For /healthz or debug endpoints."""
    return {
        "paths": len(_paths_cache),
        "lessons": len(_lessons_cache),
        "tips": len(_tips_cache),
    }


# ── Accessors ─────────────────────────────────────────────────────────────

def get_paths(age_group: Optional[str] = None, domain: Optional[str] = None) -> list[dict]:
    """Return published paths, optionally filtered by age_group and/or domain."""
    out = list(_paths_cache.values())
    if age_group:
        out = [p for p in out if p.get("age_group") == age_group]
    if domain:
        out = [p for p in out if p.get("domain") == domain]
    # Stable order: by age_group, then domain, then id
    out.sort(key=lambda p: (p.get("age_group", ""), p.get("domain", ""), p.get("id", "")))
    return out


def get_path(path_id: str) -> Optional[dict]:
    return _paths_cache.get(path_id)


def get_lessons_for_path(path_id: str) -> list[dict]:
    """Return published lessons for a path, ordered by `order` ascending."""
    out = [l for l in _lessons_cache.values() if l.get("path_id") == path_id]
    out.sort(key=lambda l: l.get("order", 999))
    return out


def get_lesson(lesson_id: str) -> Optional[dict]:
    return _lessons_cache.get(lesson_id)


def get_daily_tips(age_group: str, time_of_day: Optional[str] = None) -> list[dict]:
    """Return published tips for an age_group, optionally filtered by time_of_day."""
    out = [t for t in _tips_cache if t.get("age_group") == age_group]
    if time_of_day:
        # "anytime" matches everything; otherwise exact match
        if time_of_day != "anytime":
            out = [t for t in out if t.get("time_of_day") in (time_of_day, "anytime", None)]
    return out


def get_daily_tip_by_id(tip_id: str) -> Optional[dict]:
    for t in _tips_cache:
        if t.get("id") == tip_id:
            return t
    return None
