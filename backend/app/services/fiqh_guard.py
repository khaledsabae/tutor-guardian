"""FIQH Guard — hard block for fatwa/aqeedah ruling questions.

Per ops/FIQH_GUARD.md v3 (approved 2026-09-10):
- Hard Block on explicit fiqh/aqeedah categories, regardless of retrieval score.
- Tarbawi-intent questions (guiding a child) are NOT blocked — they are the product.
- Every block is logged to blocked_fiqh_log (text, rule, timestamp) for weekly
  false-positive review and future classifier training — with the family's
  child names, emails and phone numbers masked, and kept for
  FIQH_LOG_RETENTION_DAYS (default 90).
- A narrow deterministic parenting-after-divorce exception is enabled under
  the approved parenting/ruling distinction. General model classification
  remains opt-in shadow only; it cannot change live decisions.
"""
from __future__ import annotations

import logging
import hashlib
import os
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

# Full-question grammar, not a bag of parenting words. Additional clauses,
# legal details, quoted rulings, unknown intent and every overlapping hard
# category retain the block. Canonical privacy placeholders are allowed.
_PARENT_CHILD = (
    r"(?:طفلي|ابني|ابنتي|بنتي|اطفالي|اولادي|الطفل\s+[ا-ي]"
    r"|(?:ابني|ابنتي|بنتي)\s+(?:طفلي|الطفل\s+[ا-ي]))"
)
_PARENTING_AFTER_DIVORCE = _compile(
    rf"\s*(?:كيف|ازاي)\s+(?:اساعد|ادعم|اطمئن)\s+{_PARENT_CHILD}\s+"
    r"(?:(?:على\s+)?(?:التاقلم|التكيف)\s+)?بعد\s+الطلاق\s*[؟?!.]*\s*"
)


def _match_fiqh_guard(text: str) -> tuple[bool, str]:
    """Pure legacy decision, shared with the opt-in semantic shadow protocol."""
    norm = _normalize(text)
    for rule_id, pattern in _RULES:
        if pattern.search(norm):
            return True, rule_id
    return False, ""


def _matching_fiqh_rules(text: str) -> tuple[str, ...]:
    """Inspect every category: an early divorce topic must not hide a ruling."""
    norm = _normalize(text)
    return tuple(rule_id for rule_id, pattern in _RULES if pattern.search(norm))


def _effective_fiqh_guard(text: str, device_id: str | None = None) -> tuple[bool, str]:
    """Live deterministic policy; semantic labels never decide an exemption."""
    rules = _matching_fiqh_rules(text)
    if not rules:
        return False, ""
    hard = next((rule for rule in rules if rule != "fiqh_talaq_khalaa"), None)
    if hard:
        return True, hard
    if len(text) <= 2000:
        if _PARENTING_AFTER_DIVORCE.fullmatch(_normalize(text)):
            return False, ""
    return True, rules[0]


def check_fiqh_guard(text: str, device_id: str | None = None) -> tuple[bool, str]:
    """Apply narrow deterministic parenting policy, then optional shadow.

    Unknown modes (including enforce/active) cannot activate classification.
    Existing router emergency checks still precede this function.
    """
    blocked, rule = _effective_fiqh_guard(text, device_id)
    if os.environ.get("FIQH_INTENT_MODE") == "shadow":
        try:
            from app.services.fiqh_intent import evaluate
            decision = evaluate(text, device_id, mode="shadow")
            blocked = decision.effective_blocked
            if not blocked:
                rule = ""
        except Exception:
            pass  # Shadow failures never alter the deterministic decision.
    if blocked:
        _log_block(text, rule, device_id)
    return blocked, rule


# ── Telemetry: blocked_fiqh_log (FIQH_GUARD.md v3 — point ج) ────────────────
_LOG_DB = Path(__file__).resolve().parents[3] / "ops" / "sessions.db"


# An email, or a run of 7+ digits allowing spaces/dashes/+ (Arabic-Indic
# digits included): contact details a parent typed into a question.
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_PHONE = re.compile(r"\+?[\d\u0660-\u0669](?:[\s-]?[\d\u0660-\u0669]){6,}")


def _retention_days() -> int:
    try:
        return max(1, int(os.environ.get("FIQH_LOG_RETENTION_DAYS", "90")))
    except ValueError:
        return 90


def _scrub(text: str, device_id: str | None) -> str | None:
    """What the review needs is the phrasing that tripped a rule, not who asked.

    The questions are verbatim parent text and used to be stored as typed,
    forever: children's names, and whatever contact details came with them.
    """
    from app.services import privacy  # lazy: avoids an import cycle

    try:
        text = privacy.redact_for_cloud(text, device_id)
        if not isinstance(text, str):
            raise ValueError("invalid redaction result")
        # Shared privacy helpers deliberately fail open for other callers.
        # Fiqh logs/model prompts must not interpret an unavailable name store
        # as proof there are no names. Read strictly and apply this snapshot
        # even if the shared helper silently returned the original question.
        uri = Path(privacy.db_path()).resolve().as_uri() + "?mode=ro"
        with sqlite3.connect(uri, uri=True, timeout=0.2) as conn:
            if device_id:
                family = privacy.family_from_conn(conn, device_id)
                text = privacy.redact_family(text, family)
            else:
                names = tuple(row[0] for row in conn.execute(
                    "SELECT name FROM child_profiles") if row[0])
                text = privacy.redact_with_names(text, names)
    except Exception:
        logger.warning("fiqh_guard: redaction unavailable; metadata only")
        return None
    text = _EMAIL.sub("[email]", text)
    return _PHONE.sub("[phone]", text)


def _log_block(text: str, rule_id: str, device_id: str | None = None) -> None:
    try:
        import sqlite3
        conn = sqlite3.connect(str(_LOG_DB))
        conn.execute(
            """CREATE TABLE IF NOT EXISTS blocked_fiqh_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question TEXT NOT NULL,
                rule_id TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now')),
                redacted INTEGER
            )"""
        )
        from app.services.retention import ensure_marker
        ensure_marker(conn, "blocked_fiqh_log")
        scrubbed = _scrub(text, device_id)
        stored = scrubbed[:500] if scrubbed is not None else (
            "sha256:" + hashlib.sha256(text.encode()).hexdigest())
        conn.execute(
            "INSERT INTO blocked_fiqh_log (question, rule_id, redacted) VALUES (?, ?, ?)",
            (stored, rule_id, 1 if scrubbed is not None else 0),
        )
        conn.execute(
            "DELETE FROM blocked_fiqh_log WHERE created_at < datetime('now', ?)",
            (f"-{_retention_days()} days",),
        )
        conn.commit()
        conn.close()
    except Exception:
        logger.warning("fiqh_guard: failed to log block metadata")
