"""FIQH Guard — hard block for fatwa/aqeedah ruling questions.

Per ops/FIQH_GUARD.md v3 (approved 2026-09-10):
- Hard Block on explicit fiqh/aqeedah categories, regardless of retrieval score.
- Tarbawi-intent questions (guiding a child) are NOT blocked — they are the product.
- Every block is logged to blocked_fiqh_log (text, rule, timestamp) for weekly
  false-positive review and future classifier training.
- Regex phase only (v3 plan step 3); the intent classifier comes after a week
  of real samples.
"""
from __future__ import annotations

import logging
import re
import sqlite3
import time
from pathlib import Path

logger = logging.getLogger(__name__)

# ── Safe reply (approved wording, FIQH_GUARD.md v3) ─────────────────────────
SAFE_REPLY = (
    "سؤالك مهم وله جوانب شرعية دقيقة نفضل أن تؤخذ من مصادر الفتوى والجهات "
    "الشرعية المعتمدة. تخصصنا في «المربّي» يتركز في التطبيقات التربوية والعملية؛ "
    "فإذا كان سؤالك مرتبطاً بكيفية توضيح هذا المفهوم لأولادك أو التعامل معه "
    "تربوياً داخل الأسرة، يسعدنا تقديم الدعم في هذا الجانب."
)

# ── Regex rules (explicit cases only — v3 plan step 3) ──────────────────────
# Matched against `_normalize(text)`, so every pattern is normalized the same
# way when it is compiled (see _compile). Before that, any alternative written
# with أ/إ/آ ("أطلق زوجته", "الأرواح", "آلات الموسيقى") could never match: the
# text had already lost its hamza, the pattern had not.
#
# Precision fixes (2026-09 audit). The categories are unchanged; only
# collisions with *different words* were removed. Each of these was blocked
# with the fiqh reply before:
#   «ابني حديث الولادة ووزنه ضعيف»      — newborn (حديث الولادة), a medical question
#   «كيف أعلم ابني ترك الغيبة»          — backbiting (الغيبة ⊃ الغيب)
#   «ابني عنده ضعف في الرؤية»          — eyesight (الرؤية)
#   «أمنع الصور… التحكم الأبوي»          — parental controls (التحكم ⊃ حكم)
#   «ما موضوع الحديث المناسب مع ابني»   — "topic of conversation"
#   «ابني ضعيف في القراءة… رواية»        — a weak reader and a novel
# and «ما حكم الموسيقى» — the plainest fatwa phrasing — was *not* blocked,
# because the ruling word came before the topic. Regression-tested in
# backend/tests/test_fiqh_guard_precision.py.
_AR = r"[\u0621-\u064A]"
_WORD_START = rf"(?<!{_AR})"
# «حديث» as a word (optionally الـ/بالـ/و/ف), but not تحديث (update) and not
# حديث/حديثي الولادة·العهد·السن (newborn, recent, young).
_HADITH = (
    rf"{_WORD_START}(?:ال|بال|وال|فال|و|ف|ب)?حديث"
    rf"(?!ي?\s*(?:ال)?(?:ولاد|عهد|سن(?!{_AR})))"
)
# A ruling word as a word of its own: الحكم/بحكم/حكمه yes; التحكم, يتحكم,
# محكمة, الحكمة (wisdom) and حرامي (thief) no.
_RULING = rf"{_WORD_START}(?:ال|و|ف|ب)?(?:حرام(?!ي)|حلال|حكم(?!ة))"
_MUSIC = r"(?:الموسيق|الغناء|الاغاني|المعازف|الات الموسيق)"
_IMAGES = r"(?:الصور|التصوير|الرسم)"
_GAP = r"[^.؟?!]"

_RULE_SOURCES: list[tuple[str, str]] = [
    ("fiqh_malakat_yn", r"ملك اليمين|مالك اليمين|ملكه يمين"),
    ("fiqh_talaq_khalaa", r"الطلاق|أطلق زوجته|طلقتني|الخلع|كتابة خلع"),
    ("aqeedah_sifaat", (
        r"صفات الله|صفه الله|رؤية الله|رؤيه الله|رؤية المؤمنين"
        r"|الرؤية (?:في|يوم) (?:الآخرة|الاخره|القيامة|القيامه|الجنة|الجنه)"
        r"|الشفاعة|شفعاء يوم"
    )),
    ("aqeedah_ghayb", rf"الغيب(?!{_AR})|علم الغيب|أرواح الأموات|الأرواح"),
    # «موضوع» (fabricated) only right next to the hadith — anywhere else in
    # the sentence it is the everyday word for "topic".
    ("hadith_tahdith", (
        rf"{_HADITH}(?:\s+شريف)?{_GAP}{{0,30}}?{_WORD_START}(?:ال|وال|و)?(?:ضعيف|صحيح|قوي|منكر)"
        rf"|{_HADITH}\s+(?:ال)?موضوع"
    )),
    ("hadith_tahdith2", rf"{_WORD_START}(?:ال|و)?(?:ضعيف|صحيح|منكر){_GAP}{{0,15}}{_HADITH}"),
    ("fiqh_madhhab_tahara", (
        r"(?:المذهب|الحنفي|الشافعي|المالكي|الحنبلي)[^.]{0,40}(?:طهارة|صلاة|وضوء)"
    )),
    ("fiqh_mahram_nikah", r"من المحارم|المحارم والمحرمات|حلل لنا|حرم علينا|الزواج من"),
    ("halaal_haraam_music", (
        rf"{_MUSIC}{_GAP}{{0,30}}{_RULING}|{_RULING}{_GAP}{{0,20}}{_MUSIC}"
    )),
    ("halaal_haraam_images", (
        rf"{_IMAGES}{_GAP}{{0,30}}{_RULING}|{_RULING}{_GAP}{{0,20}}{_IMAGES}"
    )),
]


def _normalize(text: str) -> str:
    """Light Arabic normalization for matching (no tashkeel, unified alef)."""
    text = re.sub(r"[\u064B-\u065F\u0670\u0640]", "", text)
    for a in ("\u0622", "\u0623", "\u0625"):
        text = text.replace(a, "\u0627")
    return text


def _compile(source: str) -> "re.Pattern[str]":
    # Normalize the pattern exactly as the text is normalized. Escapes such as
    # \u0621 are still backslash sequences here, so ranges are untouched.
    return re.compile(_normalize(source))


_RULES: list[tuple[str, "re.Pattern[str]"]] = [
    (rule_id, _compile(src)) for rule_id, src in _RULE_SOURCES
]


def check_fiqh_guard(text: str) -> tuple[bool, str]:
    """Return (blocked, rule_id) for explicit fiqh/aqeedah ruling questions."""
    norm = _normalize(text)
    for rule_id, pattern in _RULES:
        if pattern.search(norm):
            _log_block(text, rule_id)
            return True, rule_id
    return False, ""


# ── Telemetry: blocked_fiqh_log (FIQH_GUARD.md v3 — point ج) ────────────────
_LOG_DB = Path(__file__).resolve().parents[3] / "ops" / "sessions.db"


def _log_block(text: str, rule_id: str) -> None:
    try:
        import sqlite3
        conn = sqlite3.connect(str(_LOG_DB))
        conn.execute(
            """CREATE TABLE IF NOT EXISTS blocked_fiqh_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question TEXT NOT NULL,
                rule_id TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now'))
            )"""
        )
        conn.execute(
            "INSERT INTO blocked_fiqh_log (question, rule_id) VALUES (?, ?)",
            (text[:500], rule_id),
        )
        conn.commit()
        conn.close()
    except Exception:
        logger.warning("fiqh_guard: failed to log blocked question", exc_info=True)
