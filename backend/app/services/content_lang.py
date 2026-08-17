"""Picking the right language file for a content bank.

`curriculum_loader` already solved this for lessons, paths and daily tips, and
the comment above its overlay caches says exactly why:

    A miss falls through to the Arabic cache above rather than 404ing: a lesson
    with no translation yet must still open, in Arabic, instead of disappearing
    for English users.

The three child-surface banks — agreements, missions, licence scenarios — were
written outside that mechanism, each loading `<dir>/<name>_<band>.json` with no
notion of language at all. This is the shared piece so they do not each grow
their own half of it.

**The fallback is the whole point, not a courtesy.** An empty bank is not a
neutral state in this product: the agreement screen renders "the agreement is
only available for ages 7-9" when its bank comes back empty, and the mission
card renders "no mission today". Returning empty for an English user with an
untranslated band would tell them a feature does not exist for their child's
age, which is false. Arabic they cannot read is a worse experience than English
they can; a claim that the feature is unavailable is a wrong one.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

# One entry, and it is deliberate: adding "fr" here without the files behind it
# silently routes French users through the fallback below, which is correct
# behaviour but hides that nothing was translated.
TRANSLATED_LANGS = ("en",)


def normalise(lang: Optional[str]) -> Optional[str]:
    """'en-US,en;q=0.9' → 'en'. Anything with no overlay → None (Arabic).

    Accepts a bare code or a full Accept-Language header, because callers get
    it from a query parameter in some places and a header in others.
    """
    if not lang:
        return None
    head = lang.split(",")[0].split(";")[0].strip().lower()
    base = head.split("-")[0]
    return base if base in TRANSLATED_LANGS else None


def localised(base_dir: Path, filename: str, lang: Optional[str]) -> Path:
    """The translated file if it exists, else the Arabic one.

    **The overlay root is the curriculum directory, not the bank directory.**
    A bank at `curriculum/license/scenarios_x.json` has its translation at
    `curriculum/i18n/en/license/scenarios_x.json` — one `i18n/` tree beside
    `lessons`, `paths` and `daily_tips`, not an `i18n/` inside every bank
    folder.

    This is not a preference. `ops/tools/check_curriculum_schema.py` scans
    `CURRICULUM / "i18n" / <lang> / <sub>`, and `check_quran_rendering.py`
    globs `curriculum/i18n/en/**`. A file placed under `license/i18n/en/`
    would be validated by nothing — no schema check, no Qur'an-rendering
    check — and my first version of this function looked for it exactly
    there. Translated banks that no guard reads and no loader finds are worse
    than no translation: they look done.

    Existence is checked per call rather than cached — these are read once per
    session open, not per request, and a stale cache after a content deploy is
    a worse trade than a stat().
    """
    code = normalise(lang)
    if code:
        # base_dir is `<curriculum>/<sub>`; the overlay is `<curriculum>/i18n/<lang>/<sub>`.
        candidate = base_dir.parent / "i18n" / code / base_dir.name / filename
        if candidate.exists():
            return candidate
    return base_dir / filename
