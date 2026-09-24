import pytest
from app.models.api import UserMessage
from app.services.intent_guard import (
    check_abusive_language,
    check_conversational_shortcut,
)
from app.services.guardrails import (
    emergency_reply,
    _build_fallback_message,
)
from app.services.llm_service import (
    build_pivot_prompt,
    _compose_system_prompt,
)


def test_emergency_fallback_contains_hotlines():
    policies = {
        "global": {
            "emergency_fallback_message": (
                "هذا المساعد لا يقدّم تشخيصًا طبيًا أو تدخلاً في الأزمات الطارئة. "
                "يُرجى الاتصال فورًا بأرقام الطوارئ: مصر: 123 / 16000، السعودية: 997 / 911 / 116111، أو 112."
            )
        }
    }
    user_msg = UserMessage(
        message_text="ابني ابتلع منظف سام وفاقد الوعي",
        age_group="4-6",
        severity="طارئ",
    )
    reply = emergency_reply(user_msg, policies)
    assert reply.severity == "طارئ"
    assert reply.escalation_target == "emergency_services"
    assert "123" in reply.reply_text
    assert "997" in reply.reply_text
    assert "112" in reply.reply_text


def test_emergency_default_fallback_without_policy_dict():
    msg = _build_fallback_message("medical", "تسمم", "4-6", {}, is_emergency_case=True)
    assert "123" in msg
    assert "997" in msg
    assert "112" in msg


@pytest.mark.parametrize(
    "text",
    [
        "انيك امك",
        "يا عرص",
        "يا منيوك",
        "يا شرموطة",
        "كس امك",
        "يلعن امك",
        "يلعن ابوك",
        "يا ابن الكلب",
    ],
)
def test_abusive_language_detected(text):
    is_abusive, matched = check_abusive_language(text)
    assert is_abusive is True
    assert len(matched) > 0


@pytest.mark.parametrize(
    "text",
    [
        "كيف أتعامل مع ابني العنيد؟",
        "ابني يضرب أخته الصغيره",
        "هل مسموح للطفل اللعب في الشارع؟",
    ],
)
def test_normal_queries_not_abusive(text):
    is_abusive, _ = check_abusive_language(text)
    assert is_abusive is False


@pytest.mark.parametrize(
    "text,expected_sub",
    [
        ("شكرا", "عفوًا"),
        ("شكراً جزيلاً", "عفوًا"),
        ("جزاك الله خيرا", "عفوًا"),
        ("السلام عليكم", "وعليكم السلام"),
        ("أهلاً", "وعليكم السلام"),
        ("مرحبا", "وعليكم السلام"),
        ("لا شكر على واجب", "بارك الله فيك"),
    ],
)
def test_conversational_shortcuts(text, expected_sub):
    is_conv, reply_text = check_conversational_shortcut(text)
    assert is_conv is True
    assert expected_sub in reply_text
    # Must NOT mention or force any parenting activity
    assert "نشاط" not in reply_text
    assert "صندوق الأمانة" not in reply_text


def test_conversational_shortcut_does_not_fire_on_real_question():
    # If the user says thanks but asks a real question, it must not shortcut
    is_conv, _ = check_conversational_shortcut("شكرا، بس ابني عمره 5 سنوات ومش بينام")
    assert is_conv is False

    is_conv, _ = check_conversational_shortcut("السلام عليكم، عندي استفسار عن بكاء طفلي الرضيع")
    assert is_conv is False


def test_pivot_prompt_has_exemptions():
    prompt = build_pivot_prompt("كيف أضيف طفل في التطبيق", "4-6")
    assert "استثناء" in prompt or "تحية أو شكر" in prompt
    assert "طريقة استخدامه الفنية" in prompt


def test_compose_system_prompt_has_exemptions():
    prompt = _compose_system_prompt("tarbiyah", "شكرا")
    assert "استثناءات هامة" in prompt
    assert "تحية أو شكر" in prompt
    assert "التطبيق نفسه" in prompt
    assert "نصيحة اليوم" in prompt
