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
from app.media_naming import language_of_filename, path_video_candidates

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parents[2] / "knowledge_base" / "curriculum"

PATHS_DIR = BASE_DIR / "paths"
LESSONS_DIR = BASE_DIR / "lessons"
TIPS_DIR = BASE_DIR / "daily_tips"
I18N_DIR = BASE_DIR / "i18n"

# Languages we have full translations for. Arabic is the source, so it is not
# an overlay — everything falls back to it.
TRANSLATED_LANGS = ("en",)

# Module-level cache. Loaded once at startup via load_curriculum().
_paths_cache: dict[str, dict] = {}
_lessons_cache: dict[str, dict] = {}
_tips_cache: list[dict] = []
_assets_cache: dict[str, dict] = {}

# Translation overlays, keyed by language then id. A miss falls through to the
# Arabic cache above rather than 404ing: a lesson with no translation yet must
# still open, in Arabic, instead of disappearing for English users.
_i18n_paths_cache: dict[str, dict[str, dict]] = {}
_i18n_lessons_cache: dict[str, dict[str, dict]] = {}
# Tips are cached as a *list* (the daily pick indexes into it), so the overlay
# is keyed by id and applied per item on read — the list itself is never
# rebuilt per language. See get_daily_tips() for why that ordering matters.
_i18n_tips_cache: dict[str, dict[str, dict]] = {}


def _norm_lang(lang: Optional[str]) -> Optional[str]:
    """'en-US,en;q=0.9' → 'en'. Anything we have no overlay for → None (Arabic)."""
    if not lang:
        return None
    head = lang.split(",")[0].split(";")[0].strip().lower()
    base = head.split("-")[0]
    return base if base in TRANSLATED_LANGS else None


def _media_lang(declared: Optional[str], filename: str) -> str:
    """Language of a media entry. Untagged means Arabic — never guessed.

    This replaced an inference that read "no `_ar` in the filename" as English:

        if "_ar" in fname or "lesson_0-3" in fname: lang = "ar"
        else:                                       lang = "en"

    Exactly one indexed podcast carries no `language` — `lesson_10-12_cyber_01`
    → `docs/lesson_01_podcast.mp3`, 37.8 MB of Arabic. It matches neither
    branch, so it was served to English users as though it were English, and
    the fallback that exists for precisely this case never ran.
    """
    code = (declared or "").strip().lower().split("-")[0]
    return code if code else language_of_filename(filename)


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
                        
                        normalized_podcasts = [
                            {**p, "language": _media_lang(p.get("language"),
                                                          p.get("file", ""))}
                            for p in podcasts
                        ]
                        normalized_videos = [
                            {**v, "language": _media_lang(v.get("language"),
                                                          v.get("file", ""))}
                            for v in videos
                        ]
                        
                        asset_data = {
                            "podcasts": normalized_podcasts,
                            "videos": normalized_videos,
                            "flashcards": raw_assets.get("flashcards", []),
                            "quizzes": raw_assets.get("quizzes", []),
                            "infographics": raw_assets.get("infographics", []),
                            "reports": raw_assets.get("reports", []),
                            "data_tables": raw_assets.get("data_tables", []),
                        }
                        # Cache by both short and long IDs
                        assets[short_id] = asset_data
                        assets[long_id] = asset_data
        except Exception as e:
            logger.warning("[curriculum] failed to load index file: %s", e)
    else:
        logger.warning("[curriculum] docs/lesson_index.json not found")
    _assets_cache = assets

    # ── Translation overlays ──
    # Only ids that already exist in Arabic are overlaid: a stray translation
    # file must not conjure a lesson that the source curriculum does not have.
    global _i18n_paths_cache, _i18n_lessons_cache, _i18n_tips_cache
    _i18n_paths_cache, _i18n_lessons_cache, _i18n_tips_cache = {}, {}, {}
    # `_tips_cache` is a list; the other two are dicts. Index tips by id here so
    # all three present the same {id: doc} shape to the overlay loop.
    tips_by_id = {t["id"]: t for t in _tips_cache if t.get("id")}
    for lang in TRANSLATED_LANGS:
        for sub, source, target in (
            ("lessons", _lessons_cache, _i18n_lessons_cache),
            ("paths", _paths_cache, _i18n_paths_cache),
            ("daily_tips", tips_by_id, _i18n_tips_cache),
        ):
            overlay: dict[str, dict] = {}
            for f in sorted((I18N_DIR / lang / sub).glob("*.json")):
                d = _load_json(f)
                if d and d.get("id") in source:
                    overlay[d["id"]] = d
            target[lang] = overlay

    logger.info(
        "[curriculum] loaded %d paths, %d lessons, %d tips, %d assets"
        " · translations: %s",
        len(_paths_cache), len(_lessons_cache), len(_tips_cache), len(_assets_cache),
        ", ".join(
            f"{lang} {len(_i18n_lessons_cache.get(lang, {}))} lessons"
            f"/{len(_i18n_paths_cache.get(lang, {}))} paths"
            f"/{len(_i18n_tips_cache.get(lang, {}))} tips"
            for lang in TRANSLATED_LANGS
        ) or "none",
    )


def curriculum_stats() -> dict:
    """For /healthz or debug endpoints."""
    return {
        "paths": len(_paths_cache),
        "lessons": len(_lessons_cache),
        "tips": len(_tips_cache),
        "assets": len(_assets_cache),
    }


def media_exists(relative_path: Optional[str]) -> bool:
    """True if a repo-relative media path resolves to a real file.

    Media is gitignored and reaches production by rsync, so a rename on one side
    leaves lesson_index.json naming a file that is not there. Callers use this to
    drop the reference instead of handing the app a URL that 404s silently.
    """
    if not relative_path:
        return False
    return (Path(__file__).resolve().parents[2] / relative_path).is_file()


def _add_path_video(path: dict, lang: Optional[str] = None) -> dict:
    """Attach the best available path video for `lang`, Arabic as fallback.

    `video_language` ships alongside `video_mp4` because `_translate()` stamps
    `language: "en"` on the path text unconditionally. Without it, a path badged
    English can hand the app an Egyptian-dialect video and the only person who
    finds out is the parent who pressed play.
    """
    path_id = path.get("id")
    if not path_id:
        return path
    out = dict(path)
    for rel in path_video_candidates(path_id, _norm_lang(lang) or "ar"):
        if media_exists(rel):
            out["video_mp4"] = rel
            out["video_language"] = language_of_filename(rel)
            break
    return out


def _translate(item: dict, overlay: dict[str, dict[str, dict]],
               lang: Optional[str]) -> dict:
    """Overlay the translated fields onto the Arabic entry.

    Merged rather than swapped, so a translation that omits a field (or a newly
    added field it does not know about yet) keeps the Arabic value instead of
    dropping it. Structural fields the app routes on — id, path_id, order —
    always win from the source.
    """
    code = _norm_lang(lang)
    if not code:
        return item
    tr = overlay.get(code, {}).get(item.get("id", ""))
    if not tr:
        return item
    merged = {**item, **{k: v for k, v in tr.items() if v not in (None, "", [])}}
    for key in ("id", "path_id", "order", "age_group", "domain", "unit_ids"):
        if key in item:
            merged[key] = item[key]
    merged["language"] = code
    return merged


def get_paths(age_group: Optional[str] = None, domain: Optional[str] = None,
              lang: Optional[str] = None) -> list[dict]:
    """Return published paths, optionally filtered by age_group and/or domain."""
    out = list(_paths_cache.values())
    if age_group:
        ages = set(age_equivalents(age_group))  # 0-3 ≡ prenatal-1
        out = [p for p in out if p.get("age_group") in ages]
    if domain:
        out = [p for p in out if p.get("domain") == domain]
    # Stable order: by age_group, then domain, then id
    out.sort(key=lambda p: (p.get("age_group", ""), p.get("domain", ""), p.get("id", "")))
    return [_add_path_video(_translate(p, _i18n_paths_cache, lang), lang) for p in out]


def get_path(path_id: str, lang: Optional[str] = None) -> Optional[dict]:
    path = _paths_cache.get(path_id)
    if path:
        return _add_path_video(_translate(path, _i18n_paths_cache, lang), lang)
    return None


def get_lessons_for_path(path_id: str, lang: Optional[str] = None) -> list[dict]:
    """Return published lessons for a path, ordered by `order` ascending."""
    out = [l for l in _lessons_cache.values() if l.get("path_id") == path_id]
    out.sort(key=lambda l: l.get("order", 999))
    return [_translate(l, _i18n_lessons_cache, lang) for l in out]


def get_lesson(lesson_id: str, lang: Optional[str] = None) -> Optional[dict]:
    lesson = _lessons_cache.get(lesson_id)
    if lesson is None:
        return None
    return _translate(lesson, _i18n_lessons_cache, lang)


def search(query: str, limit: int = 20, lang: Optional[str] = None) -> list[dict]:
    """Substring search across published lessons, daily tips, and paths.

    Returns a flat list of lightweight result dicts:
      {type: lesson|tip|path, id, title, snippet, age_group, domain, path_id?}
    Title matches rank above body-only matches; results are capped at `limit`.

    Matching runs over the source *and* the translation, while rendering uses
    the requested language. An English user searching "sleep" has no Arabic
    string to hit, so before this the search returned nothing for them and the
    English curriculum was unreachable except by browsing; an Arabic query from
    an English-locale user still matches, and comes back in English.
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

    def _hit(*values: str) -> bool:
        return any(q in (v or "").lower() for v in values)

    for lesson in _lessons_cache.values():
        view = _translate(lesson, _i18n_lessons_cache, lang)
        title, summary = view.get("title", ""), view.get("summary", "")
        in_title = _hit(title, lesson.get("title", ""))
        if in_title or _hit(summary, lesson.get("summary", "")):
            scored.append((0 if in_title else 1, {
                "type": "lesson", "id": lesson["id"], "title": title,
                "snippet": _snippet(summary), "age_group": lesson.get("age_group"),
                "domain": lesson.get("domain"), "path_id": lesson.get("path_id"),
            }))

    for path in _paths_cache.values():
        view = _translate(path, _i18n_paths_cache, lang)
        title, desc = view.get("title", ""), view.get("description", "")
        in_title = _hit(title, path.get("title", ""))
        if in_title or _hit(desc, path.get("description", "")):
            scored.append((0 if in_title else 1, {
                "type": "path", "id": path["id"], "title": title,
                "snippet": _snippet(desc), "age_group": path.get("age_group"),
                "domain": path.get("domain"),
            }))

    for tip in _tips_cache:
        view = _translate(tip, _i18n_tips_cache, lang)
        text = view.get("text", "")
        if _hit(text, tip.get("text", "")):
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


def get_daily_tips(age_group: str, time_of_day: Optional[str] = None,
                   lang: Optional[str] = None) -> list[dict]:
    """Return published tips for an age_group, optionally filtered by time_of_day.

    🚨 The pool is built from the Arabic cache and only then translated item by
    item. `_pick_tip_for_today` chooses with `sha256(date:age:time) % len(pool)`,
    so pool *length and order* are load-bearing: building a separate English
    pool — even one that happens to be the same size today — makes the index
    mean something different the first time a tip is added in one language and
    not the other. Two parents in one household would get different tips on the
    same day, which is the one property that hash exists to guarantee.
    """
    ages = set(age_equivalents(age_group))  # 0-3 ≡ prenatal-1
    out = [t for t in _tips_cache if t.get("age_group") in ages]
    if time_of_day:
        # "anytime" matches everything; otherwise exact match
        if time_of_day != "anytime":
            out = [t for t in out if t.get("time_of_day") in (time_of_day, "anytime", None)]
    return [_translate(t, _i18n_tips_cache, lang) for t in out]


def get_daily_tip_by_id(tip_id: str, lang: Optional[str] = None) -> Optional[dict]:
    for t in _tips_cache:
        if t.get("id") == tip_id:
            return _translate(t, _i18n_tips_cache, lang)
    return None
