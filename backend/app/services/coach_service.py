"""
Proactive parenting coach service — المرشد التربوي الاستباقي
=============================================================

v3.2: Graceful degradation.
  * Personalized card is shown ONLY when we are confident it matches the
    parent's actual recent question and the child's gender/age.
  * Otherwise we silently fall back to the plain daily tip (DailyTipCard).
  * This guarantees zero lying frames — the differentiator is trust.

Response contract:
  - If tip["text"] starts with "{child_name} في عمر" → personalized card.
  - Otherwise → plain deterministic daily tip (use the existing DailyTipCard).
"""
from __future__ import annotations

import datetime as dt
import hashlib
import logging
import os
import re
import sqlite3
from typing import Optional

from app import curriculum_loader as cl
from app.core.taxonomy import canonical_age_group, canonical_domain
from app.db.init_db import get_conn
from app.services import conversation_store as store
from app.services import llm_service
from app.services.ai_gateway import get_gateway

logger = logging.getLogger(__name__)

COACH_TIP_ENABLED = os.environ.get("COACH_TIP_ENABLED", "false").lower() in ("1", "true", "yes")

_MIN_TIP_LENGTH = 60
_MAX_TIP_LENGTH = 500
_CJK_RE = re.compile(r"[　-〿぀-ヿㇰ-ㇿ㐀-䶿一-鿿가-힯＀-￯]+")

# Common topics → hand-curated warm seeds. Used only when the model fails.
_TOPIC_SEEDS: dict[str, str] = {
    "شاشة": "1. حدّد وقتاً ثابتاً للشاشة (مثلاً نصف ساعة بعد الظهر). 2. جهّز بديلاً جاهزاً: ألعاب، كتب، أو نشاط خارجي. 3. قلّله تدريجياً وامدحه كلما استغنى عنها.",
    "تلفزيون": "1. اختر معه برنامجاً واحداً محدداً. 2. شغّله بعد أن ينتهي من مهمة بسيطة. 3. بعده اسأله: 'أعجبك؟ شو تعلمت؟' ليصبح المشاهدة حواراً.",
    "تابلت": "1. احفظ الجهاز في مكان مشترك، لا في غرفته. 2. لا ألعاب عنيفة قبل النوم بساعة. 3. اقترح بديلاً ممتعاً تلعبه معه أنت.",
    "تلفون": "1. اتفقوا على وقت يستخدم فيه الجهاز. 2. ضع الهاتف خارج غرفة النوم ليلاً. 3. افتحوا معاً تطبيقاً واحداً وتكلّموا عنه.",
    "تيك توك": "1. حدّدي سقفاً يومياً واضحاً. 2. شاركيها في فيديو واحد لتفهمي ما يشاهده. 3. جهّزي نشاطاً بديلاً تحبه مع صديقاتها.",
    "سوشيال": "1. اجلسي معها واسأليها: من الشخص اللي بتقارني نفسك بيه؟ 2. ذكّريها بصفاتها الحقيقية التي تحبّها. 3. حدّدي يوماً خالياً من المقارنات.",
    "ألفاظ": "1. اسأله بهدوء: من وين سمعت الكلمة؟ 2. اشرح أن في كلاماً لا نستخدمه. 3. علّمه عبارة بديلة مهذبة يقولها بدلاً منها.",
    "كذب": "1. اجلسي معها في مكان هادئ: 'أنا أعرف إنك كنتِ عايزة تبقي محبوبة'. 2. قوليها: الصدق أمان، وحتى لو الحقيقة صعبة أنا هساعدك. 3. امتدحيها كلما قالت الحقيقة.",
    "خوف": "1. اجلسي بجانبها قبل النوم واقرأي دعاءين قصيرين. 2. اتركي إضاءة خافتة وباباً مفتوحاً قليلاً. 3. صباحاً سجّلي أي شيء خافت منه لتحلّيه سوياً.",
    "نوم": "1. ثبّتي روتين نوم بنفس الأوقات. 2. ساعة قبل النوم: لا شاشات، حمام دافئ، قصة قصيرة. 3. إذا استمرّت الاستيقاظات استشيري طبيباً.",
    "عناد": "1. قدّمي خيارين محدودين (مثلاً: 'تريد الطعام بالملعقة أو الشوكة؟'). 2. لا تدخلي في جدال طويل. 3. امتدحي التعاون فوراً حين يحدث.",
    "أكل": "1. لا تضغطي ولا تُجبرّي. 2. ضعي الطبق واتركيها تختار منه. 3. قلّلي الحلويات بين الوجبات ليحمّسها على الأكل.",
    "ضرب": "1. افصليهما بهدوء بدون صراخ. 2. اسأل المعتدي: 'شو حسيت لما ضربت؟' 3. علّمه عبارة يقولها بدلاً من الضرب: 'أنا زعلان، ممكن ألعب لوحدي شوي.'",
    "ألعاب عنيفة": "1. احفظ الجهاز في مكان مشترك بعد وقت محدّد. 2. لا تترك الألعاب العنيفة تبقى الخيار الوحيد؛ جهّز بديلاً من الألعاب التفاعلية أو الإبداعية. 3. احكِ معاه عن الفرق بين اللعب والعنف الحقيقي.",
    "عنف": "1. احفظ الجهاز في مكان مشترك بعد وقت محدّد. 2. لا تترك الألعاب العنيفة تبقى الخيار الوحيد؛ جهّز بديلاً من الألعاب التفاعلية أو الإبداعية. 3. احكِ معاه عن الفرق بين اللعب والعنف الحقيقي.",
    "قراءة": "1. اختار كتاباً قصيراً بصور جذابة. 2. اقرأ صوتاً مسرّعاً وتوقّف اسأله: 'توقع إيه هيحصل؟' 3. خصّص 10 دقائق يومياً في نفس المكان.",
    "صلاة": "1. صلِّ أمامه وأظهر السكينة. 2. ابدأ بسورة قصيرة وسبّح معه. 3. امتدحه ولو ركع ركعة واحدة.",
    "مذاكرة": "1. زوّده مكاناً هادئاً ووقتاً ثابتاً. 2. اقسم المذاكرة لقطع صغيرة بفواصل. 3. امتدح المجهود مش النتيجة بس.",
    "جامعة": "1. اسأله: أي مادة بتضغط عليك؟ 2. ساعده يضع خطة أسبوعية واقعية. 3. شجّعه يتواصل مع مرشد أكاديمي.",
    "سفر": "1. اسمعي مخاوفها دون مقاطعة. 2. ناقشي معاً قواعد السلامة والتواصل اليومي. 3. ابدئي بتجربة قصيرة قبل السفر الطويل.",
    "تكلم": "1. اقرأ له وصِف الأشياء بالكلمات البسيطة. 2. شجّعه يطلب بكلمة بدل الإشارة. 3. لو تأخر أكثر من ستة أشهر استشر أخصائي نطق.",
    "قافلة": "1. اسمعيها بهدوء دون مقاطعة. 2. قوليها: مش ذنبك، واللي بيضايقك غلط. 3. اتصلي بالمدرسة واطلبي لقاء لحل الموضوع.",
    "باص": "1. اسمعيها بهدوء دون مقاطعة. 2. قوليها: مش ذنبك، واللي بيضايقك غلط. 3. اتصلي بالمدرسة واطلبي لقاء لحل الموضوع.",
}


# «رحلة الطفل» — the parent-settable "current challenge" catalogue.
# Each key maps to (topic_phrase, domain). The topic phrase deliberately
# embeds a keyword that `_TOPIC_SEEDS` / the daily-tip matcher recognize,
# so a challenge flows through the exact same grounded pipeline as a real
# parent question. Domains stay non-medical so the safety gates behave the
# same (generation still blocked for toddlers / medical).
CHALLENGE_TOPICS: dict[str, tuple[str, str]] = {
    "sleep": ("نوم الطفل ورفض النوم", "development"),
    "lying": ("كذب الطفل", "development"),
    "screens": ("شاشة الطفل والتابلت", "cyber"),
    "tantrums": ("عناد الطفل ونوبات الغضب", "development"),
    "eating": ("أكل الطفل ورفض الطعام", "development"),
    "hitting": ("ضرب الطفل", "development"),
    "fear": ("خوف الطفل", "development"),
    "study": ("مذاكرة الطفل", "development"),
}


def _today_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")


def _active_challenge(
    conn: sqlite3.Connection, device_id: str, child_id: int
) -> Optional[sqlite3.Row]:
    """The most recent active «current challenge» for this child, if any."""
    try:
        return conn.execute(
            "SELECT topic, domain FROM child_challenges "
            "WHERE device_id = ? AND child_id = ? AND status = 'active' "
            "ORDER BY id DESC LIMIT 1",
            (device_id, child_id),
        ).fetchone()
    except sqlite3.Error as exc:  # table may not exist on very old DBs
        logger.warning("active_challenge lookup failed: %s", exc)
        return None


def _get_owned_child(conn: sqlite3.Connection, child_id: int, device_id: str) -> Optional[sqlite3.Row]:
    row = conn.execute("SELECT * FROM child_profiles WHERE id = ?", (child_id,)).fetchone()
    if row is None or row["device_id"] != device_id:
        return None
    return row


def _recent_parent_topic(
    device_id: str,
    *,
    child_id: int | None = None,
    lookback_messages: int = 8,
) -> tuple[Optional[str], Optional[str]]:
    """Return (exact_question, domain) of the most recent user message for this child."""
    conn = get_conn()
    try:
        sessions = store.list_sessions(device_id, limit=20)
        user_messages: list[tuple[str, str]] = []
        for sess in sessions:
            sid = sess["id"]
            metadata = sess.get("metadata") or {}
            if child_id is not None:
                sess_child = metadata.get("child_id")
                if sess_child is not None and int(sess_child) != child_id:
                    continue
            rows = conn.execute(
                "SELECT content, domain FROM chat_messages "
                "WHERE session_id = ? AND role = 'user' AND domain IS NOT NULL "
                "ORDER BY id DESC LIMIT ?",
                (sid, lookback_messages),
            ).fetchall()
            for r in rows:
                user_messages.append((r["content"], r["domain"]))
        if not user_messages:
            return None, None
        return user_messages[0]
    except Exception as exc:  # noqa: BLE001
        logger.warning("recent_parent_topic failed: %s", exc)
        return None, None
    finally:
        conn.close()


def _gender_word(gender: Optional[str]) -> str:
    if gender and gender.lower() in ("female", "f", "girl", "بنت"):
        return "بنت"
    if gender and gender.lower() in ("male", "m", "boy", "ولد"):
        return "ولد"
    return "طفل"


def _build_coach_prompt(
    child_name: str,
    child_gender: Optional[str],
    age_group: str,
    exact_question: str,
) -> str:
    """Simple, grounded prompt for tg-tutor:v3 (3B)."""
    gender = _gender_word(child_gender)
    return (
        f"اسم الطفل: {child_name}، {gender}، عمره {age_group}.\n"
        f"سؤال الأب: {exact_question}\n"
        "اكتب نصيحة تربوية عملية قصيرة (٣ خطوات مرقّمة) تردّ على سؤال الأب بالظبط. "
        "استخدم اسم الطفل أو ضمير واحد فقط. بدون مقدمات وبدون ذكر مصادر."
    )


def _clean_generation(raw: str) -> str:
    """Post-process model output: strip fine-tune artifacts and clean whitespace."""
    if not raw:
        return ""
    leading_patterns = [
        r"(?:\ufeff|\s)*نعم[،,.]?\s*[،:.-]*\s*",
        r"(?:\ufeff|\s)*بالتأكيد[،,.]?\s*[،:.-]*\s*",
        r"(?:\ufeff|\s)*أجل[،,.]?\s*[،:.-]*\s*",
        r"(?:\ufeff|\s)*صحيح[،,.]?\s*[،:.-]*\s*",
        r"(?:\ufeff|\s)*\"[^\"]*\"\s*[،,.-]?\s*",
        r"(?:\ufeff|\s)*النصيحة التالية[،,.:]?\s*",
        r"(?:\ufeff|\s)*إليك[^\n]*الخطوات[،,.:]?\s*",
    ]
    for pat in leading_patterns:
        raw = re.sub(pat, "", raw, flags=re.IGNORECASE | re.DOTALL)
    markers = (
        "متوافقة مع", "بناءً على", "إليك النصيحة",
        "إليك بعض النصائح", "النصيحة:", "النصيحة :", "النصيحة/",
        "غير مضمونة", "غير مضمون", "غير مؤكدة", "غير مؤكد",
        "للأسف", "ليس هناك حل", "لا يوجد علاج",
    )
    for marker in markers:
        idx = raw.find(marker)
        if idx != -1 and idx < 200:
            raw = raw[idx + len(marker):]
    lines = raw.splitlines()
    cleaned_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if re.search(r"^\s*(?:[-—]?\s*)?(?:المصادر?|📚|المصدر|source)", stripped, re.IGNORECASE):
            continue
        if re.match(r"^\d+[\.\-)\]]?\s*$", stripped):
            continue
        cleaned_lines.append(stripped)
    text = "\n".join(cleaned_lines).strip()
    # Unify mixed Arabic/European numbering to clean line-broken steps.
    text = re.sub(r"(?:^|\n)\s*(?:خطوة\s+)?[٠١٢٣٤٥٦٧٨٩0-9]+[\.\-)\]\:\-]\s*", "\n", text)
    text = re.sub(r"\n\s*\n+", "\n", text).strip()
    return text


def _wrap_tip(
    core: str,
    child_name: str,
    age_group: str,
    recent_topic: str,
    *,
    is_challenge: bool = False,
) -> str:
    """Wrap a matching core with the warm, personalized frame."""
    # Normalize age labels so parents never see internal strings like 'prenatal-1'.
    age_display = age_group.replace("-", "–")
    if age_display.startswith("prenatal"):
        age_display = "0–3"
    if is_challenge:
        # Honest framing: the parent flagged this as their current focus.
        opener = f"{child_name} في عمر {age_display}، وأنت بتتابع تحدّي «{recent_topic}»:"
    else:
        opener = f"{child_name} في عمر {age_display}، ولاحظت إنك سألت عن «{recent_topic}»:"
    closer = " اللهم بارك فيه واجعله من الصالحين."
    return f"{opener}\n\n{core.strip()}{closer}"


def _looks_personal(text: str) -> bool:
    return "في عمر" in text and "اللهم بارك" in text


def _is_core_ok(core: str, recent_topic: str, age_group: str, domain: Optional[str]) -> bool:
    """Substance + Arabic-only + reasonable length + topic overlap + age/medical safety."""
    if not core:
        return False
    core = core.strip()
    if len(core) < _MIN_TIP_LENGTH or len(core) > _MAX_TIP_LENGTH:
        return False
    if _CJK_RE.search(core):
        return False
    if not re.search(r"[\u0600-\u06FF]", core):
        return False
    latin_chars = len(re.findall(r"[a-zA-Z]", core))
    if latin_chars > 0 and latin_chars / len(core) > 0.03:
        return False

    # Reject corrupted/generated markers that slip through.
    lowered_core = core.lower()
    if any(m in lowered_core for m in ["غير مضمونة", "غير مضمون", "غير مؤكدة", "غير مؤكد", "للأسف", "ليس هناك حل", "لا يوجد علاج"]):
        logger.info("coach quality: meta/dislaimer text")
        return False

    # Medical safety: never generate medical advice outside medical domain.
    medical_terms = ["طبيب نفسي", "علاج", "تشخيص", "تدخل", "أعراض", "طبيب الأطفال", "صيدلي", "دواء", "حبوب", "جرعة"]
    if domain != "medical" and any(m in lowered_core for m in medical_terms):
        logger.info("coach quality: medical term in non-medical domain")
        return False

    # Reject broken/incomprehensible fragments.
    if re.search(r"[\u0600-\u06FF]\s+[بتثجحخدذرزسشصضطظعغفقكلمنهوي]\.?$", core):
        logger.info("coach quality: sentence ends with isolated single letter fragment")
        return False
    if re.search(r"\b(وبكسرت|وبكسر|بكسرت|بكسر)\b", core):
        logger.info("coach quality: broken conjunction fragment")
        return False

    # Medical safety: we never generate medical advice; seeds/curriculum only.
    if domain == "medical" or age_group in ("0-3", "2-3"):
        logger.info("coach quality: medical/toddler content — generation forbidden")
        return False

    # Topic relevance by content-word overlap.
    topic_words = {w for w in re.findall(r"[\u0600-\u06FF]{3,}", recent_topic)}
    core_words = {w for w in re.findall(r"[\u0600-\u06FF]{3,}", core)}
    overlap = topic_words & core_words
    if len(overlap) < 1:
        return False

    # Reject phrasing that normalizes violent games by scheduling them.
    lowered_topic = recent_topic.lower()
    if any(m in lowered_topic for m in ["عنيف", "ألعاب عنيفة", "عنف", "violent"]):
        if any(m in lowered_core for m in ["حدد وقتاً", "حدد وقت", "وقت معين", "وقت محدد", "للألعاب العنيفة"]):
            logger.info("coach quality: schedules violent games")
            return False
    confrontation_topic = any(m in lowered_topic for m in ["قافلة", " bully", "بيتنمر", "بتتخانق", "بيتخانق", "تنمر", "بيتنمروا", "بيتنمّر"])
    if confrontation_topic:
        avoidance_markers = ["لا ترسل", "لا تذهب", "تجنّب", "ابعد", "اخفي", "انسحب", "في البيت", "ذاتي", "من المدرسة"]
        if any(m in lowered_core for m in avoidance_markers):
            logger.info("coach quality: avoidance advice for confrontation topic")
            return False
    return True


def _pronoun_consistent(core: str, child_gender: Optional[str]) -> bool:
    """Check that the core uses roughly one gender set of pronouns."""
    lowered = core.lower()
    male_count = sum(lowered.count(w) for w in ("ابن", "ولد", "هو", "له", "ب", "ابنك"))
    female_count = sum(lowered.count(w) for w in ("بنت", "هي", "لها", "بنتك"))
    if child_gender and child_gender.lower() in ("female", "f", "girl", "بنت"):
        return female_count >= male_count or female_count > 0
    if child_gender and child_gender.lower() in ("male", "m", "boy", "ولد"):
        return male_count >= female_count or male_count > 0
    return True


def _is_seed_safe(core: str, recent_topic: str, age_group: str, domain: Optional[str]) -> bool:
    """Lightweight safety gate for hand-curated seeds: length/CJK/latin/medical/toddler."""
    if not core:
        return False
    core = core.strip()
    if len(core) < _MIN_TIP_LENGTH or len(core) > _MAX_TIP_LENGTH:
        return False
    if _CJK_RE.search(core):
        return False
    latin_chars = len(re.findall(r"[a-zA-Z]", core))
    if latin_chars > 0 and latin_chars / len(core) > 0.03:
        return False
    if domain == "medical" or age_group in ("0-3", "2-3"):
        return False
    return bool(re.search(r"[\u0600-\u06FF]", core))


def _manual_seed_for_topic(recent_topic: str) -> Optional[str]:
    """Return a hand-curated seed if the topic matches a known keyword."""
    lowered = recent_topic.lower()
    for keyword, seed in _TOPIC_SEEDS.items():
        if keyword in lowered:
            return seed
    return None


def _find_topic_matching_fallback(
    age_group: str,
    recent_topic: str,
    domain: Optional[str],
    used_texts: Optional[set[str]] = None,
) -> Optional[dict]:
    """Find a daily-tip seed whose text actually addresses the recent topic."""
    topic_words = {w for w in re.findall(r"[\u0600-\u06FF]{3,}", recent_topic) if len(w) >= 3}
    if not topic_words:
        return None

    def score(tip: dict) -> int:
        text = tip.get("text", "")
        text_words = set(re.findall(r"[\u0600-\u06FF]{3,}", text))
        overlap = len(topic_words & text_words)
        same_age = tip.get("age_group") == age_group
        same_domain = tip.get("domain") == domain
        return overlap * 10 + (5 if same_age else 0) + (3 if same_domain else 0)

    candidates: list[dict] = []
    for t in cl.get_daily_tips(age_group):
        candidates.append(t)
    if len([c for c in candidates if score(c) > 0]) < 3:
        for ag in ["0-3", "2-3", "4-6", "7-9", "10-12", "13-15", "16-18"]:
            if ag == age_group:
                continue
            for t in cl.get_daily_tips(ag):
                candidates.append(t)

    scored = [(t, score(t)) for t in candidates if score(t) > 0]
    if not scored:
        return None
    scored.sort(key=lambda x: x[1], reverse=True)
    for tip, _ in scored:
        text = tip.get("text", "")
        if used_texts and text in used_texts:
            continue
        return tip
    return None


def _pick_plain_fallback(age_group: str, child_id: int, used_texts: Optional[set[str]] = None) -> dict:
    """Return the deterministic daily tip for the age group (DailyTipCard equivalent).

    In production the daily tip is per (date, age_group). The child_id argument is
    only exposed for batch sampling scripts so different children in the same age
    group get different plain tips for review.
    """
    pool = cl.get_daily_tips(age_group)
    if not pool:
        return {
            "id": "fallback_none",
            "text": "ابدأ اليوم بنصيحة واحدة: خصّص دقائق حقيقية مع طفلك بلا شاشات، واسأله عن يومه.",
            "domain": "development",
        }
    today = _today_utc()
    seed_input = f"{today}:{age_group}:{child_id}"
    h = hashlib.sha256(seed_input.encode("utf-8")).hexdigest()
    idx = int(h, 16) % len(pool)
    if used_texts:
        for offset in range(len(pool)):
            candidate = pool[(idx + offset) % len(pool)]
            text = candidate.get("text", "")
            if text not in used_texts:
                return candidate
    return pool[idx]


def _ensure_coach_tips_table() -> None:
    conn = get_conn()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS coach_tips (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id    TEXT NOT NULL,
                child_id     INTEGER NOT NULL,
                date         TEXT NOT NULL,
                domain       TEXT,
                text         TEXT NOT NULL,
                source       TEXT NOT NULL DEFAULT 'fallback',
                shown_at     TEXT,
                tapped_at    TEXT,
                created_at   TEXT NOT NULL DEFAULT (datetime('now')),
                UNIQUE (device_id, child_id, date)
            );
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS ix_coach_tips_device_date "
            "ON coach_tips (device_id, child_id, date)"
        )
        conn.commit()
    finally:
        conn.close()


def _load_or_create_tip(
    conn: sqlite3.Connection,
    device_id: str,
    child_id: int,
    date: str,
) -> Optional[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM coach_tips WHERE device_id = ? AND child_id = ? AND date = ?",
        (device_id, child_id, date),
    ).fetchone()


def _store_tip(
    conn: sqlite3.Connection,
    device_id: str,
    child_id: int,
    date: str,
    domain: Optional[str],
    text: str,
    source: str,
) -> int:
    cur = conn.execute(
        """
        INSERT INTO coach_tips (device_id, child_id, date, domain, text, source)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(device_id, child_id, date) DO UPDATE SET
            domain = excluded.domain,
            text = excluded.text,
            source = excluded.source,
            shown_at = COALESCE(coach_tips.shown_at, excluded.created_at)
        RETURNING id
        """,
        (device_id, child_id, date, domain, text, source),
    )
    row = cur.fetchone()
    conn.commit()
    return row["id"]


def _mark_shown_once(conn: sqlite3.Connection, tip_id: int) -> None:
    conn.execute(
        "UPDATE coach_tips SET shown_at = COALESCE(shown_at, datetime('now')) WHERE id = ?",
        (tip_id,),
    )
    conn.commit()


async def get_proactive_tip(
    device_id: str,
    child_id: int,
    *,
    mark_shown: bool = True,
    used_texts: Optional[set[str]] = None,
) -> dict:
    """Return today's tip. If text does not start with child name → plain daily tip."""
    _ensure_coach_tips_table()
    date = _today_utc()

    conn = get_conn()
    try:
        child = _get_owned_child(conn, child_id, device_id)
        if child is None:
            raise ValueError("طفل غير موجود أو لا ينتمي لهذا الجهاز.")

        age_group = canonical_age_group(child["age_group"])
        child_name = child["name"]
        child_gender = child["gender"]

        cached = _load_or_create_tip(conn, device_id, child_id, date)
        if cached is not None:
            if mark_shown:
                _mark_shown_once(conn, cached["id"])
            return {
                "id": cached["id"],
                "text": cached["text"],
                "domain": cached["domain"] or "development",
                "source": cached["source"],
                "child_id": child_id,
                "date": cached["date"],
            }

        # «رحلة الطفل»: an active current-challenge outranks the most recent
        # chat question — the parent explicitly flagged it as what they're
        # working on right now.
        challenge = _active_challenge(conn, device_id, child_id)
        if challenge is not None:
            recent_topic = challenge["topic"]
            domain = canonical_domain(challenge["domain"]) if challenge["domain"] else None
            signal_is_challenge = True
        else:
            recent_topic, domain_raw = _recent_parent_topic(device_id, child_id=child_id)
            domain = canonical_domain(domain_raw) if domain_raw else None
            signal_is_challenge = False

        # No signal → plain deterministic tip.
        if not recent_topic or not domain:
            fallback = _pick_plain_fallback(age_group, child_id, used_texts=used_texts)
            text = fallback["text"]
            chosen_domain: str = fallback.get("domain", "development") or "development"
            source = "fallback"
            tip_id = _store_tip(conn, device_id, child_id, date, chosen_domain, text, source)
            if mark_shown:
                _mark_shown_once(conn, tip_id)
            return {
                "id": tip_id,
                "text": text,
                "domain": chosen_domain,
                "source": source,
                "child_id": child_id,
                "date": date,
            }

        # Attempt 1: model generation with grounding.
        generated_text: Optional[str] = None
        if COACH_TIP_ENABLED:
            prompt = _build_coach_prompt(child_name, child_gender, age_group, recent_topic)
            try:
                result = await get_gateway().generate(
                    prompt,
                    options={"temperature": 0.45, "num_predict": 240},
                    tier="local_fast",
                    route_reason="proactive_coach_tip",
                )
                generated_text = llm_service.clean_model_output(result.text or "")
                generated_text = _clean_generation(generated_text)
            except Exception as exc:  # noqa: BLE001
                logger.warning("proactive tip generation failed: %s", exc)

        core_text: Optional[str] = None
        source = "fallback"

        if generated_text and _is_core_ok(generated_text, recent_topic, age_group, domain) and _pronoun_consistent(generated_text, child_gender):
            core_text = generated_text.strip()
            source = "generated"

        # Attempt 2: hand-curated topic seed.
        if core_text is None:
            seed = _manual_seed_for_topic(recent_topic)
            # Manual seeds are pre-approved; only check length/CJK.
            if seed and _is_seed_safe(seed, recent_topic, age_group, domain):
                core_text = seed.strip()
                source = "fallback"

        # For toddlers, do not trust generated output at all.
        if age_group in ("0-3", "2-3") and source == "generated":
            core_text = None
            source = "fallback"

        # Attempt 3: search daily tips for a matching seed.
        if core_text is None:
            matched = _find_topic_matching_fallback(age_group, recent_topic, domain, used_texts=used_texts)
            if matched and _is_core_ok(matched.get("text", ""), recent_topic, age_group, domain):
                core_text = matched["text"].strip()
                source = "fallback"

        # Graceful degradation: if no trustworthy matching core, return plain daily tip.
        if core_text is None:
            plain = _pick_plain_fallback(age_group, child_id, used_texts=used_texts)
            text = plain["text"]
            chosen_domain = plain.get("domain", "development") or "development"
            source = "fallback"
            tip_id = _store_tip(conn, device_id, child_id, date, chosen_domain, text, source)
            if mark_shown:
                _mark_shown_once(conn, tip_id)
            return {
                "id": tip_id,
                "text": text,
                "domain": chosen_domain,
                "source": source,
                "child_id": child_id,
                "date": date,
            }

        text = _wrap_tip(
            core_text, child_name, age_group, recent_topic,
            is_challenge=signal_is_challenge,
        )
        chosen_domain = domain if domain else "development"
        tip_id = _store_tip(conn, device_id, child_id, date, chosen_domain, text, source)
        if mark_shown:
            _mark_shown_once(conn, tip_id)
        return {
            "id": tip_id,
            "text": text,
            "domain": chosen_domain,
            "source": source,
            "child_id": child_id,
            "date": date,
        }
    finally:
        conn.close()


def record_tap(device_id: str, tip_id: int) -> None:
    _ensure_coach_tips_table()
    conn = get_conn()
    try:
        row = conn.execute("SELECT device_id FROM coach_tips WHERE id = ?", (tip_id,)).fetchone()
        if row is None or row["device_id"] != device_id:
            raise ValueError("نصيحة غير موجودة أو لا تنتمي لهذا الجهاز.")
        conn.execute(
            "UPDATE coach_tips SET tapped_at = datetime('now') WHERE id = ?",
            (tip_id,),
        )
        conn.commit()
    finally:
        conn.close()
