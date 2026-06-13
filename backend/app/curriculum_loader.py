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

from app.core.taxonomy import age_equivalents

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parents[2] / "knowledge_base" / "curriculum"

PATHS_DIR = BASE_DIR / "paths"
LESSONS_DIR = BASE_DIR / "lessons"
TIPS_DIR = BASE_DIR / "daily_tips"

# Module-level cache. Loaded once at startup via load_curriculum().
_paths_cache: dict[str, dict] = {}
_lessons_cache: dict[str, dict] = {}
_tips_cache: list[dict] = []
_assets_cache: dict[str, dict] = {}


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
    global _paths_cache, _lessons_cache, _tips_cache, _assets_cache

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

    # ── Lesson Assets ──
    assets: dict[str, dict] = {}
    index_file = Path(__file__).resolve().parents[2] / "docs" / "lesson_index.json"
    if index_file.exists():
        try:
            with index_file.open("r", encoding="utf-8") as f:
                index_data = json.load(f)
                for lesson_entry in index_data.get("lessons", []):
                    short_id = lesson_entry.get("lesson_id")
                    age = lesson_entry.get("age_group")
                    topic = lesson_entry.get("topic_path")
                    if short_id and age and topic:
                        # Extract order, e.g., lesson_10-12_cyber_01 -> 01
                        order = short_id.split("_")[-1]
                        long_id = f"lesson_{age}_{topic}_{order}"
                        raw_assets = lesson_entry.get("assets", {})
                        
                        podcasts = raw_assets.get("podcasts", [])
                        videos = raw_assets.get("videos", [])
                        
                        normalized_podcasts = []
                        for p in podcasts:
                            lang = p.get("language")
                            if not lang:
                                fname = p.get("file", "")
                                if "_ar" in fname or "lesson_0-3" in fname:
                                    lang = "ar"
                                else:
                                    lang = "en"
                            normalized_podcasts.append({**p, "language": lang})

                        normalized_videos = []
                        for v in videos:
                            lang = v.get("language")
                            if not lang:
                                fname = v.get("file", "")
                                if "_ar" in fname:
                                    lang = "ar"
                                else:
                                    lang = "en"
                            normalized_videos.append({**v, "language": lang})
                        
                        asset_data = {
                            "podcasts": normalized_podcasts,
                            "videos": normalized_videos,
                            "flashcards": raw_assets.get("flashcards", []),
                            "quizzes": raw_assets.get("quizzes", [])
                        }
                        # Cache by both short and long IDs
                        assets[short_id] = asset_data
                        assets[long_id] = asset_data
        except Exception as e:
            logger.warning("[curriculum] failed to load index file: %s", e)
    else:
        logger.warning("[curriculum] docs/lesson_index.json not found")
    _assets_cache = assets

    logger.info(
        "[curriculum] loaded %d paths, %d lessons, %d tips, %d assets",
        len(_paths_cache), len(_lessons_cache), len(_tips_cache), len(_assets_cache),
    )


def curriculum_stats() -> dict:
    """For /healthz or debug endpoints."""
    return {
        "paths": len(_paths_cache),
        "lessons": len(_lessons_cache),
        "tips": len(_tips_cache),
        "assets": len(_assets_cache),
    }


def _add_path_video(path: dict) -> dict:
    path_id = path.get("id")
    if not path_id:
        return path
    out = dict(path)
    video_relative_path = f"docs/path_videos/{path_id}_ar_eg.mp4"
    video_file = Path(__file__).resolve().parents[2] / video_relative_path
    if video_file.exists():
        out["video_mp4"] = video_relative_path
    return out


def get_paths(age_group: Optional[str] = None, domain: Optional[str] = None) -> list[dict]:
    """Return published paths, optionally filtered by age_group and/or domain."""
    out = list(_paths_cache.values())
    if age_group:
        ages = set(age_equivalents(age_group))  # 0-3 ≡ prenatal-1
        out = [p for p in out if p.get("age_group") in ages]
    if domain:
        out = [p for p in out if p.get("domain") == domain]
    # Stable order: by age_group, then domain, then id
    out.sort(key=lambda p: (p.get("age_group", ""), p.get("domain", ""), p.get("id", "")))
    return [_add_path_video(p) for p in out]


def get_path(path_id: str) -> Optional[dict]:
    path = _paths_cache.get(path_id)
    if path:
        return _add_path_video(path)
    return None


def get_lessons_for_path(path_id: str) -> list[dict]:
    """Return published lessons for a path, ordered by `order` ascending."""
    out = [l for l in _lessons_cache.values() if l.get("path_id") == path_id]
    out.sort(key=lambda l: l.get("order", 999))
    return out


def get_lesson(lesson_id: str) -> Optional[dict]:
    return _lessons_cache.get(lesson_id)


def search(query: str, limit: int = 20) -> list[dict]:
    """Substring search across published lessons, daily tips, and paths.

    Returns a flat list of lightweight result dicts:
      {type: lesson|tip|path, id, title, snippet, age_group, domain, path_id?}
    Title matches rank above body-only matches; results are capped at `limit`.
    """
    q = (query or "").strip().lower()
    if len(q) < 2:
        return []

    scored: list[tuple[int, dict]] = []

    def _snippet(text: str) -> str:
        text = " ".join((text or "").split())
        idx = text.lower().find(q)
        if idx < 0:
            return text[:120]
        start = max(0, idx - 40)
        return ("…" if start else "") + text[start:start + 120]

    for lesson in _lessons_cache.values():
        title = lesson.get("title", "")
        summary = lesson.get("summary", "")
        in_title = q in title.lower()
        if in_title or q in summary.lower():
            scored.append((0 if in_title else 1, {
                "type": "lesson", "id": lesson["id"], "title": title,
                "snippet": _snippet(summary), "age_group": lesson.get("age_group"),
                "domain": lesson.get("domain"), "path_id": lesson.get("path_id"),
            }))

    for path in _paths_cache.values():
        title = path.get("title", "")
        desc = path.get("description", "")
        in_title = q in title.lower()
        if in_title or q in desc.lower():
            scored.append((0 if in_title else 1, {
                "type": "path", "id": path["id"], "title": title,
                "snippet": _snippet(desc), "age_group": path.get("age_group"),
                "domain": path.get("domain"),
            }))

    for tip in _tips_cache:
        text = tip.get("text", "")
        if q in text.lower():
            scored.append((2, {
                "type": "tip", "id": tip["id"], "title": _snippet(text),
                "snippet": "", "age_group": tip.get("age_group"),
                "domain": tip.get("domain"),
            }))

    scored.sort(key=lambda s: (s[0], s[1]["title"]))
    return [r for _, r in scored[:limit]]


def get_lesson_assets(lesson_id: str) -> Optional[dict]:
    return _assets_cache.get(lesson_id)


_ASSETS_ROOT = Path(__file__).resolve().parents[2] / "docs" / "lesson_assets"
_asset_content_cache: dict[str, dict] = {}


def get_asset_content(asset_id: str) -> Optional[dict]:
    """Resolve an asset id (flashcards/quizzes entry) to its JSON content.

    Looks up the id across all lessons' asset lists, reads the referenced
    file from docs/lesson_assets/ only (path-traversal safe), and caches it.
    """
    if asset_id in _asset_content_cache:
        return _asset_content_cache[asset_id]

    repo_root = Path(__file__).resolve().parents[2]
    for bundle in _assets_cache.values():
        for kind in ("flashcards", "quizzes"):
            for entry in bundle.get(kind, []) or []:
                if entry.get("id") != asset_id:
                    continue
                rel = entry.get("file") or ""
                fp = (repo_root / rel).resolve()
                if not fp.is_relative_to(_ASSETS_ROOT) or fp.suffix != ".json":
                    logger.warning("[curriculum] asset %s path rejected: %s", asset_id, rel)
                    return None
                content = _load_json(fp)
                if content is None:
                    return None
                result = {"id": asset_id, "kind": kind, **content}
                _asset_content_cache[asset_id] = result
                return result
    return None


def get_daily_tips(age_group: str, time_of_day: Optional[str] = None) -> list[dict]:
    """Return published tips for an age_group, optionally filtered by time_of_day."""
    ages = set(age_equivalents(age_group))  # 0-3 ≡ prenatal-1
    out = [t for t in _tips_cache if t.get("age_group") in ages]
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
