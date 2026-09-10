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
# Each pattern: (rule_id, compiled regex). Normalized Arabic matching.
_RULES: list[tuple[str, "re.Pattern[str]"]] = [
    ("fiqh_malakat_yn", re.compile(r"ملك اليمين|مالك اليمين|ملكه يمين")),
    ("fiqh_talaq_khalaa", re.compile(r"الطلاق|أطلق زوجته|طلقتني|الخلع|كتابة خلع")),
    ("aqeedah_sifaat", re.compile(r"صفات الله|صفه الله|الرؤية|رؤية الله|الشفاعة|شفعاء يوم")),
    ("aqeedah_ghayb", re.compile(r"الغيب|علم الغيب|أرواح الأموات|الأرواح")),
    ("hadith_tahdith", re.compile(
        r"(حديث|حديث شريف)[^.]*(ضعيف|صحيح|قوي|منكر|موضوع|هل هو صحيح|هل صحيح)"
    )),
    ("hadith_tahdith2", re.compile(r"(ضعيف|صحيح|منكر|موضوع)[^.]*(حديث|رواية)")),
    ("fiqh_madhhab_tahara", re.compile(r"(المذهب|الحنفي|الشافعي|المالكي|الحنبلي)[^.]*(طهارة|صلاة|وضوء)")),
    ("fiqh_mahram_nikah", re.compile(r"من المحارم|المحارم والمحرمات|حلل لنا|حرم علينا|الزواج من")),
    ("halaal_haraam_music", re.compile(r"(الموسيق|الموسيقي|الغناء|آلات الموسيقى)[^.]{0,30}(حرام|حلال|حكم)")),
    ("halaal_haraam_images", re.compile(r"(الصور|التصوير|الرسم)[^.]{0,30}(حرام|حلال|حكم)")),
]


def _normalize(text: str) -> str:
    """Light Arabic normalization for matching (no tashkeel, unified alef)."""
    text = re.sub(r"[\u064B-\u065F\u0670\u0640]", "", text)
    for a in ("\u0622", "\u0623", "\u0625"):
        text = text.replace(a, "\u0627")
    return text


def check_fiqh_guard(text: str) -> tuple[bool, str]:
    """Return (blocked, rule_id) for explicit fiqh/aqeedah ruling questions."""
    norm = _normalize(text)
    for rule_id, pattern in _RULES:
        if pattern.search(norm):
            _log_block(text, rule_id)
            return True, rule_id
    return False, ""


# ── Telemetry: blocked_fiqh_log (FIQH_GUARD.md v3 — point ج) ────────────────
_LOG_DB = Path(__file__).resolve().parents[2] / "ops" / "sessions.db"


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
