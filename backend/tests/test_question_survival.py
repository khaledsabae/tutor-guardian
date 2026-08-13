"""كل سؤال يجب أن يخرج بأثر — الطبقة التي كانت تُسقط 10.9% من الأسئلة صامتةً.

قياس على الإنتاج يوم 2026-08-13: 176 من 1,617 سؤالًا (10.9%) بلا أي صف إجابة.
تبيّن أن التوليد كان ينجح (88% منها له نداء نموذج بزمن طبيعي في نافذته) لكن
الحفظ يعيش داخل المولّد غير المتزامن، وانقطاع العميل يُغلقه بـCancelledError —
وهي BaseException لا يلتقطها `except Exception`. فلا صف، ولا سجل، ولا أثر.

هذه الاختبارات تثبّت الأمرين معًا: أن التصنيف يُحفظ على صف السؤال، وأن
انقطاع البث يترك أثرًا بدل الصمت.
"""
import asyncio

import pytest

from app.config.guardrails_loader import load_guardrails_config
from app.services import conversation_store as store
from app.services.guardrails import evaluate_guardrails


# ── حفظ التصنيف على صف السؤال ───────────────────────────────────────

def test_add_message_returns_rowid():
    """بلا المعرّف لا سبيل لتحديث الصف بعد التصنيف — كان يُرجع None."""
    sid = store.create_session("device-test")
    mid = store.add_message(sid, "user", "ابني يرفض النوم")
    assert isinstance(mid, int) and mid > 0


def test_classification_backfills_onto_the_question_row():
    sid = store.create_session("device-test")
    mid = store.add_message(sid, "user", "ابني يرفض النوم")

    conn = store.get_conn()
    before = conn.execute(
        "SELECT domain, severity FROM chat_messages WHERE id = ?", (mid,)
    ).fetchone()
    conn.close()
    assert before["domain"] is None  # يُكتب قبل التصنيف، عمدًا

    store.update_classification(mid, domain="tarbiyah", severity="متوسط")

    conn = store.get_conn()
    after = conn.execute(
        "SELECT domain, severity FROM chat_messages WHERE id = ?", (mid,)
    ).fetchone()
    conn.close()
    assert after["domain"] == "tarbiyah"
    assert after["severity"] == "متوسط"


def test_update_classification_does_not_disturb_other_rows():
    sid = store.create_session("device-test")
    first = store.add_message(sid, "user", "سؤال أول")
    second = store.add_message(sid, "user", "سؤال ثانٍ")
    store.update_classification(first, domain="cyber", severity="خفيف")

    conn = store.get_conn()
    row = conn.execute(
        "SELECT domain FROM chat_messages WHERE id = ?", (second,)
    ).fetchone()
    conn.close()
    assert row["domain"] is None


def test_update_classification_with_nothing_to_set_is_a_noop():
    sid = store.create_session("device-test")
    mid = store.add_message(sid, "user", "س", domain="fiqh")
    store.update_classification(mid)  # كل الحقول None

    conn = store.get_conn()
    row = conn.execute(
        "SELECT domain FROM chat_messages WHERE id = ?", (mid,)
    ).fetchone()
    conn.close()
    assert row["domain"] == "fiqh"  # لم يُمحَ


def test_coach_query_shape_now_matches_rows():
    """`coach_service.recent_parent_topic` يستعلم عن role='user' AND domain
    IS NOT NULL — استعلام لم يكن يُرجع صفًا واحدًا قط قبل هذا الإصلاح."""
    sid = store.create_session("device-test")
    mid = store.add_message(sid, "user", "ابني عصبي")
    store.update_classification(mid, domain="tarbiyah", severity="خفيف")

    conn = store.get_conn()
    rows = conn.execute(
        "SELECT content, domain FROM chat_messages "
        "WHERE role='user' AND domain IS NOT NULL"
    ).fetchall()
    conn.close()
    assert len(rows) == 1
    assert rows[0]["domain"] == "tarbiyah"


# ── نجاة الإجابة عند انقطاع البث ─────────────────────────────────────

async def _drain(gen, stop_after: int | None = None) -> list[str]:
    """يستهلك المولّد، ويقطعه بعد n حدثًا كما يفعل عميل يغادر الشاشة."""
    out: list[str] = []
    try:
        async for item in gen:
            out.append(item)
            if stop_after is not None and len(out) >= stop_after:
                break
    finally:
        await gen.aclose()
    return out


# لا نعتمد pytest-asyncio: ليس في requirements (الموجود pytest-anyio وهو لا
# يشغّل `async def` تلقائيًا)، ونجاح هذين محليًا كان بفضل نسخة مثبّتة عالميًا
# على جهاز واحد. asyncio.run تكفي ولا تضيف اعتمادية.
def test_interrupted_stream_persists_what_the_parent_saw():
    """المحاكاة الدنيا لبنية event_stream: حفظ داخل finally لا داخل except.

    هذا هو جوهر العطب: `except Exception` لا يرى CancelledError ولا
    GeneratorExit، فكان الانقطاع يمر بلا أي أثر.
    """
    sid = store.create_session("device-test")
    store.add_message(sid, "user", "سؤال طويل عن التربية")
    persisted: list[tuple[str, str]] = []

    async def event_stream():
        sent: list[str] = []
        done = False
        try:
            for delta in ("جزء ", "أول ", "ثم ", "بقية"):
                sent.append(delta)
                yield delta
            done = True
        except Exception:  # noqa: BLE001 — لا يلتقط CancelledError عمدًا
            pass
        finally:
            if not done:
                text = "".join(sent).strip()
                if text:
                    persisted.append((text, "interrupted"))
                    store.add_message(sid, "assistant", text, mode="interrupted")

    got = asyncio.run(_drain(event_stream(), stop_after=2))
    assert got == ["جزء ", "أول "]
    assert persisted == [("جزء أول", "interrupted")]

    conn = store.get_conn()
    rows = conn.execute(
        "SELECT role, mode FROM chat_messages WHERE session_id = ? ORDER BY id",
        (sid,),
    ).fetchall()
    conn.close()
    assert [r["role"] for r in rows] == ["user", "assistant"]
    assert rows[1]["mode"] == "interrupted"


def test_completed_stream_persists_once_not_twice():
    """المسار السليم يحفظ مرة واحدة — حارس `persisted` يمنع صفًا مكررًا."""
    sid = store.create_session("device-test")
    writes: list[str] = []

    async def event_stream():
        persisted = False

        def _persist(text, mode):
            nonlocal persisted
            if persisted:
                return
            persisted = True
            writes.append(mode)

        try:
            for delta in ("أ", "ب"):
                yield delta
            _persist("أب", "llm_generated")
            yield "done"
        finally:
            if not persisted:
                _persist("أب", "interrupted")

    asyncio.run(_drain(event_stream()))
    assert writes == ["llm_generated"]


# ── طابور المراجعة البشرية ───────────────────────────────────────────

@pytest.fixture(scope="module")
def shipped_policies():
    return load_guardrails_config()


@pytest.mark.parametrize("domain", ["aqeedah", "fiqh", "islamic_parenting"])
def test_ordinary_question_no_longer_floods_the_review_queue(domain, shipped_policies):
    """«خفيف» هي الخطورة الافتراضية لكل سؤال لا تلتقطه كلمات الطوارئ، فكان
    كل سؤال في هذه المجالات يُعلَّم — 983 رسالة (61%) لم يقرأها أحد."""
    decision = evaluate_guardrails(domain, "خفيف", shipped_policies)
    assert decision["needs_human_review"] is False


@pytest.mark.parametrize("domain", [
    "aqeedah", "fiqh", "islamic_parenting", "medical", "development", "cyber",
])
@pytest.mark.parametrize("severity", ["شديد", "طارئ"])
def test_escalation_is_untouched(domain, severity, shipped_policies):
    """تضييق العلامة يجب ألا يضيّق التصعيد: الشديد والطارئ يظلّان مراجَعين."""
    decision = evaluate_guardrails(domain, severity, shipped_policies)
    assert decision["needs_human_review"] is True
    assert decision["escalate_to"]


def test_emergency_still_escalates_to_emergency_services(shipped_policies):
    for domain in ("aqeedah", "fiqh", "islamic_parenting"):
        assert evaluate_guardrails(domain, "طارئ", shipped_policies)["escalate_to"] \
            == "emergency_services"
