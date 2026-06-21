"""
Feedback analyzer — تحليل ذكي لفيدباك المستخدمين
==================================================
يسحب مصدرَي الفيدباك (تقييمات 👍/👎 على المحادثة + الفيدباك الحر من زرّ
الفيدباك) ويمرّرهما على بوّابة الذكاء (DeepSeek) عشان:
  • يصنّف كل عنصر (wrong_answer / kb_gap / bug / content_error /
    praise / feature_request / noise)
  • يقدّر الخطورة 1-5 وهل العنصر «حقيقي» يستحق قرارًا فعليًا
  • للـ👎 يسحب السؤال+الإجابة الحقيقية من الجلسة ويشخّص لماذا فشل الرد
  • يجمّع كل ده في ملخّص قرارات مرتّب بالأولوية

ده حلقة التحسين الواقعية: الداتاسِت الصناعي يبدأ المساعد باردًا، وهذا
يحوّل ردود فعل المستخدمين الحقيقية إلى قرارات ملموسة.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from app.db.init_db import get_conn
from app.services import conversation_store
from app.services.ai_gateway import get_gateway

logger = logging.getLogger(__name__)

_BATCH = 12          # عناصر الفيدباك لكل نداء للموديل
_HISTORY_TURNS = 6   # عدد أدوار المحادثة المسحوبة لكل 👎

CATEGORIES = (
    "wrong_answer", "kb_gap", "bug", "content_error",
    "feature_request", "praise", "noise",
)

_ANALYZE_PROMPT = """أنت محلّل منتج خبير لتطبيق «المربّي» (مرشد تربوي ذكي بالعربية).
أمامك دفعة من فيدباك مستخدمين حقيقيين. صنّف كل عنصر بدقّة وقرّر إن كان فيه
مشكلة حقيقية تستحق قرارًا.

التصنيفات المسموحة (category):
- wrong_answer: المساعد أعطى إجابة خاطئة/غير مفيدة (يظهر من 👎 + المحادثة)
- kb_gap: سؤال لا تغطّيه قاعدة المعرفة (نحتاج محتوى جديد)
- bug: عُطل تقني (تعطّل، بطء، شاشة فاضية، خطأ)
- content_error: خطأ في محتوى موجود (معلومة غلط، لغة، ترجمة)
- feature_request: طلب ميزة أو تحسين
- praise: مدح/شكر (لا إجراء)
- noise: فارغ/غير مفهوم/سبام (لا إجراء)

لكل عنصر أعِد كائن JSON بالحقول:
  "index": رقم العنصر كما هو بين القوسين،
  "category": واحدة من التصنيفات أعلاه،
  "severity": رقم 1 (تافه) إلى 5 (حرج)،
  "actionable": true/false (هل يستحق قرارًا فعليًا؟)،
  "issue": جملة عربية تلخّص المشكلة الحقيقية (أو "" للمدح/الضجيج)،
  "recommended_action": إجراء عملي مقترح (أو "")

أعِد **مصفوفة JSON فقط** بدون أي نص قبلها أو بعدها.

الفيدباك:
{items}
"""


def _q_and_a(session_id: str | None) -> dict | None:
    """للجلسة المُقيّمة: أرجِع آخر سؤال للمستخدم + رد المساعد."""
    if not session_id:
        return None
    try:
        turns = conversation_store.get_history(session_id, limit=_HISTORY_TURNS)
    except Exception as exc:  # noqa: BLE001 — جلسة محذوفة/خطأ DB → نتخطّى السياق
        logger.warning("history fetch failed for %s: %s", session_id, exc)
        return None
    question = answer = None
    for t in reversed(turns):
        if t.role == "assistant" and answer is None:
            answer = t.content
        elif t.role == "user" and question is None:
            question = t.content
        if question and answer:
            break
    if not (question or answer):
        return None
    return {"question": question, "answer": answer}


def _query(con, sql: str, params: tuple) -> list:
    """SELECT مع تجاهل الجداول الناقصة (app_feedback يُنشأ بكسل)."""
    try:
        return con.execute(sql, params).fetchall()
    except Exception as exc:  # noqa: BLE001
        logger.warning("feedback query skipped: %s", exc)
        return []


def collect_feedback(limit: int = 500) -> list[dict]:
    """اسحب المصدرين في قائمة موحّدة (الأحدث أولًا)."""
    con = get_conn()
    items: list[dict] = []
    try:
        for r in _query(
            con,
            "SELECT session_id, rating, comment, created_at FROM user_feedback "
            "ORDER BY created_at DESC LIMIT ?", (limit,),
        ):
            items.append({
                "source": "rating",
                "rating": r["rating"],
                "comment": r["comment"] or "",
                "created_at": r["created_at"],
                "context": _q_and_a(r["session_id"]) if r["rating"] == "down" else None,
            })
        for r in _query(
            con,
            "SELECT message, contact, app_version, created_at, "
            "(audio_b64 IS NOT NULL) AS has_audio FROM app_feedback "
            "ORDER BY created_at DESC LIMIT ?", (limit,),
        ):
            items.append({
                "source": "app",
                "message": r["message"] or "",
                "contact": r["contact"],
                "app_version": r["app_version"],
                "created_at": r["created_at"],
                "has_audio": bool(r["has_audio"]),
            })
    finally:
        con.close()
    return items


def _render_items(batch: list[dict], offset: int) -> str:
    """حوّل دفعة فيدباك إلى نص مرقّم للـprompt."""
    lines: list[str] = []
    for i, item in enumerate(batch):
        idx = offset + i
        if item["source"] == "rating":
            head = f"[{idx}] تقييم محادثة: {'👎' if item['rating'] == 'down' else '👍'}"
            if item.get("comment"):
                head += f" | تعليق: {item['comment']}"
            ctx = item.get("context")
            if ctx:
                q = (ctx.get("question") or "")[:400]
                a = (ctx.get("answer") or "")[:600]
                head += f"\n   سؤال المستخدم: {q}\n   رد المساعد: {a}"
        else:
            head = f"[{idx}] فيدباك تطبيق: {item.get('message', '')[:600]}"
            if item.get("has_audio"):
                head += " (يحتوي نوت صوتي — للمراجعة اليدوية)"
            if item.get("app_version"):
                head += f" | إصدار {item['app_version']}"
        lines.append(head)
    return "\n".join(lines)


def _parse_json_array(text: str) -> list:
    """استخرج مصفوفة JSON بصمود من رد الموديل (مع/بدون أسوار ```)."""
    text = (text or "").strip()
    start, end = text.find("["), text.rfind("]")
    if start == -1 or end == -1 or end < start:
        return []
    try:
        data = json.loads(text[start:end + 1])
        return data if isinstance(data, list) else []
    except Exception:  # noqa: BLE001
        return []


def _fallback_verdict(item: dict) -> dict:
    """تصنيف احتياطي لو الموديل لم يُصنّف العنصر."""
    if item["source"] == "rating":
        down = item.get("rating") == "down"
        return {
            "category": "wrong_answer" if down else "praise",
            "severity": 3 if down else 1, "actionable": down,
            "issue": item.get("comment", "") if down else "",
            "recommended_action": "مراجعة يدوية" if down else "",
        }
    return {"category": "noise", "severity": 1, "actionable": False,
            "issue": "", "recommended_action": "مراجعة يدوية"}


async def _analyze_batch(gateway, batch: list[dict], offset: int) -> list[dict]:
    """صنّف دفعة عبر الموديل، مع سدّ أي عنصر ناقص بالتصنيف الاحتياطي."""
    prompt = _ANALYZE_PROMPT.format(items=_render_items(batch, offset))
    verdicts: list = []
    try:
        res = await gateway.generate(prompt, options={"temperature": 0.1})
        verdicts = _parse_json_array(res.text)
    except Exception as exc:  # noqa: BLE001
        logger.warning("feedback batch analysis failed: %s", exc)
    by_index = {v.get("index"): v for v in verdicts if isinstance(v, dict)}
    out: list[dict] = []
    for i, item in enumerate(batch):
        idx = offset + i
        v = by_index.get(idx) or _fallback_verdict(item)
        v["index"] = idx
        out.append(v)
    return out


def _short(item: dict) -> str:
    """مقتطف مرجعي قصير للعنصر الخام."""
    if item["source"] == "rating":
        ctx = item.get("context") or {}
        base = item.get("comment") or (ctx.get("question") or "تقييم بلا تعليق")
        return f"👎 {base}"[:200] if item.get("rating") == "down" else f"👍 {base}"[:200]
    return (item.get("message") or "(نوت صوتي)")[:200]


def _build_digest(items: list[dict], analyzed: list[dict]) -> dict:
    """جمّع التصنيفات في ملخّص قرارات مرتّب."""
    by_cat: dict[str, int] = {}
    actionable: list[dict] = []
    for item, v in zip(items, analyzed):
        cat = v.get("category", "noise")
        by_cat[cat] = by_cat.get(cat, 0) + 1
        if v.get("actionable"):
            actionable.append({
                "category": cat,
                "severity": v.get("severity", 0),
                "issue": v.get("issue", ""),
                "recommended_action": v.get("recommended_action", ""),
                "raw": _short(item),
                "created_at": item.get("created_at"),
            })
    actionable.sort(key=lambda x: x.get("severity", 0), reverse=True)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total": len(items),
        "by_category": by_cat,
        "actionable_count": len(actionable),
        "voice_notes_pending": sum(1 for i in items if i.get("has_audio")),
        "actionable": actionable,
    }


async def analyze(limit: int = 500) -> dict:
    """نقطة الدخول: اسحب → صنّف بالـAI → ملخّص قرارات."""
    items = collect_feedback(limit)
    if not items:
        return _build_digest([], [])
    gateway = get_gateway()
    analyzed: list[dict] = []
    for start in range(0, len(items), _BATCH):
        batch = items[start:start + _BATCH]
        analyzed.extend(await _analyze_batch(gateway, batch, start))
    return _build_digest(items, analyzed)
