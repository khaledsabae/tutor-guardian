import pytest
from app.services.coach_safety import verify_tip_safety

def test_verify_tip_safety_valid():
    text = "يجب على المربي تقديم بدائل إيجابية عند محاولة تقليل وقت الشاشة للطفل، مثل تشجيعه على ممارسة الرياضة أو القراءة التفاعلية لبناء مهاراته."
    is_safe, res = verify_tip_safety(text, "7-9", "development")
    assert is_safe is True
    assert "وقت الشاشة" in res

def test_verify_tip_safety_too_short():
    is_safe, reason = verify_tip_safety("نصيحة قصيرة جداً", "7-9", "development")
    assert is_safe is False
    assert "خارج نطاق الطول" in reason

def test_verify_tip_safety_too_long():
    text = "يجب على المربي تقديم بدائل إيجابية " * 20
    is_safe, reason = verify_tip_safety(text, "7-9", "development")
    assert is_safe is False
    assert "خارج نطاق الطول" in reason

def test_verify_tip_safety_toddler_blocked():
    text = "يجب على المربي تقديم بدائل إيجابية عند محاولة تقليل وقت الشاشة للطفل، مثل تشجيعه على ممارسة الرياضة أو القراءة التفاعلية لبناء مهاراته."
    # Age group 2-3 (toddler) must be blocked
    is_safe, reason = verify_tip_safety(text, "2-3", "development")
    assert is_safe is False
    assert "دون 3 سنوات" in reason

def test_verify_tip_safety_medical_domain_blocked():
    text = "يجب على المربي تقديم بدائل إيجابية عند محاولة تقليل وقت الشاشة للطفل، مثل تشجيعه على ممارسة الرياضة أو القراءة التفاعلية لبناء مهاراته."
    # Domain medical must be blocked for auto-generation
    is_safe, reason = verify_tip_safety(text, "7-9", "medical")
    assert is_safe is False
    assert "للاستشارات الطبية" in reason

def test_verify_tip_safety_medical_terms_in_non_medical():
    # term "دواء" (medicine)
    text = "هذه نصيحة تربوية طويلة ومفصلة لتقليل العناد بدون إعطاء أي دواء أو حبوب علاجية للطفل في المنزل."
    is_safe, reason = verify_tip_safety(text, "7-9", "development")
    assert is_safe is False
    assert "تم كشف مصطلح طبي" in reason

def test_verify_tip_safety_cjk_characters():
    text = "هذه نصيحة تربوية طويلة ومفصلة لتقليل العناد 日本語 للطفل في المنزل."
    is_safe, reason = verify_tip_safety(text, "7-9", "development")
    assert is_safe is False
    assert "أحرف غير عربية" in reason

def test_verify_tip_safety_boilerplate_stripped():
    text = "نصيحتي لك هي يجب على المربي تقديم بدائل إيجابية عند محاولة تقليل وقت الشاشة للطفل، مثل تشجيعه على ممارسة الرياضة أو القراءة التفاعلية."
    is_safe, res = verify_tip_safety(text, "7-9", "development")
    assert is_safe is True
    assert "نصيحتي لك هي" not in res
