"""
Media file naming, one source of truth for the API and the generators.
======================================================================

Why this module exists
----------------------
Two separate bugs came out of naming living in whichever file needed it:

1. `curriculum_loader` inferred a media file's language from its name with
   `if "_ar" in fname ... else "en"`, so the one indexed podcast carrying no
   `language` key — 37.8 MB of Arabic — was served to English users as English.
2. Every podcast generator builds its own skip-predicate from its own copy of
   the output path, with four different size thresholds (500 KB, 2 MB, 10 KB,
   10 MB). An English run against an Arabic-shaped predicate inspects the
   Arabic file, finds it large, and skips every lesson — exiting 0 having
   produced nothing.

Both disappear when there is exactly one place that answers "what is this file
called" and "what language is it".

Stdlib only, and no imports from `app` — `ops/tools/*` and `scripts/*` add
`backend/` to `sys.path` and import this directly, so it must not drag in
FastAPI or settings.

The frozen Arabic names
-----------------------
Arabic podcasts are `<lesson_id>_podcast.mp3` with no tag, and Arabic path
videos are `<path_id>_ar_eg.mp4`. The asymmetry is history, not design: the 214
podcasts predate any language convention and the videos do not. Renaming the
podcasts for symmetry would cost a 7.35 GB re-rsync and a rewrite of every
index entry, and buy nothing — so absence of a tag is defined as Arabic
instead, which is true of every file that exists and enforceable for every file
that follows.
"""

from typing import Optional

SOURCE_LANG = "ar"

# Value passed to the NotebookLM CLI's `--language`. Audio and video use
# different codes because the Arabic runs did: `ar_001` (Arabic-World) for
# audio, `ar_eg` (Arabic-Egypt) for video.
AUDIO_CLI_LANG = {"ar": "ar_001", "en": "en"}
VIDEO_CLI_LANG = {"ar": "ar_eg", "en": "en_us"}

# Filename tag written for each language. Mirrors the CLI argument above so a
# file can be checked against the command that produced it.
PODCAST_TAG = {"ar": "", "en": "_en"}
VIDEO_WRITE_TAG = {"ar": "ar_eg", "en": "en_us"}

# Tags *accepted* when resolving, in preference order, with the Arabic
# fallback last for non-Arabic languages.
#
# English lists both `en_us` and `en`: the exact code NotebookLM honours for a
# video is not confirmed until a real generation runs, and a resolver that only
# knows one of them would strand a directory full of correctly-generated files
# while reporting "no English video". Writing stays single-tag; only reading is
# permissive.
VIDEO_READ_TAGS = {
    "ar": ("ar_eg",),
    "en": ("en_us", "en", "ar_eg"),  # Arabic never falls forward to English
}

# One threshold per medium, replacing the four that disagreed. 2 MB is the
# strictest already in use (`regen_podcasts.REAL_MIN`); the looser ones existed
# to let edge-tts clips through and that backlog is drained.
MIN_PODCAST_BYTES = 2 * 1024 * 1024
MIN_VIDEO_BYTES = 5 * 1024 * 1024


def norm_lang(lang: Optional[str], known: tuple = ("ar", "en")) -> str:
    """'en-US,en;q=0.9' → 'en'. Anything unknown → the source language."""
    head = (lang or "").split(",")[0].split(";")[0].strip().lower()
    base = head.split("-")[0].split("_")[0]
    return base if base in known else SOURCE_LANG


def podcast_rel(lesson_id: str, lang: str = SOURCE_LANG) -> str:
    """Repo-relative path of a lesson podcast."""
    return f"docs/{lesson_id}_podcast{PODCAST_TAG[norm_lang(lang)]}.mp3"


def path_video_rel(path_id: str, lang: str = SOURCE_LANG) -> str:
    """Repo-relative path a path video is *written* to."""
    return f"docs/path_videos/{path_id}_{VIDEO_WRITE_TAG[norm_lang(lang)]}.mp4"


def path_video_candidates(path_id: str, lang: str = SOURCE_LANG) -> tuple:
    """Paths to try when *reading*, best match first, Arabic fallback last."""
    code = norm_lang(lang)
    return tuple(f"docs/path_videos/{path_id}_{tag}.mp4"
                 for tag in VIDEO_READ_TAGS[code])


def language_of_filename(rel_path: str) -> str:
    """Language a filename claims. Untagged means Arabic — never guessed.

    The only place a filename becomes a language. `language` declared in
    `lesson_index.json` always wins over this; see `check_served_assets.py`,
    which fails when the two disagree.
    """
    stem = rel_path.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    for lang, tags in VIDEO_READ_TAGS.items():
        for tag in tags:
            if stem.endswith(f"_{tag}"):
                # `ar_eg` is in English's read list as its fallback; the tag
                # still names Arabic.
                return "ar" if tag.startswith("ar") else lang
    for lang, tag in PODCAST_TAG.items():
        if tag and stem.endswith(tag):
            return lang
    return SOURCE_LANG
