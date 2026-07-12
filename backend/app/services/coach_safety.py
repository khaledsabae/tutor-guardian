"""
Deterministic safety checker for proactive parenting tips.
Ensures generated tips conform to length, domain-safety, and age policies.
"""
import re

_MIN_TIP_LENGTH = 60
_MAX_TIP_LENGTH = 500
_CJK_RE = re.compile(r"[　-〿぀-ヿㇰ-ㇿ㐀-䶿一-鿿가-힯＀-￯]+")

# Disallowed boilerplate/metadata strings in LLM generation
_BOILERPLATES = [
    "نصيحتي لك هي",
    "بناء على المعلومات",
    "المصادر:",
    "📚 المصدر",
    "إليك النصيحة",
    "إليك بعض النصائح",
    "النصيحة:",
    "النصيحة :",
    "النصيحة/"
]

# Disallowed disclaimers or phrases expressing failure
_DISCLAIMERS = [
    "غير مضمونة",
    "غير مضمون",
    "غير مؤكدة",
    "غير مؤكد",
    "للأسف",
    "ليس هناك حل",
    "لا يوجد علاج"
]

# Medical terminology that shouldn't appear in non-medical tips
_MEDICAL_TERMS = [
    "طبيب نفسي",
    "علاج",
    "تشخيص",
    "تدخل",
    "أعراض",
    "طبيب الأطفال",
    "صيدلي",
    "دواء",
    "حبوب",
    "جرعة",
    "عيادة"
]

def verify_tip_safety(tip_text: str, age_group: str, domain: str) -> tuple[bool, str]:
    """
    Verify generated tips against safety policy boundaries.
    
    Returns: (is_safe: bool, reason_or_cleaned_text: str)
    """
    if not tip_text:
        return False, "نص فارغ"

    cleaned = tip_text.strip()

    # 1. Clean LLM boilerplate first to assess true content length
    for marker in _BOILERPLATES:
        cleaned = cleaned.replace(marker, "")
    cleaned = cleaned.strip()

    # 2. Age group check: forbid automatic generation for toddlers
    if age_group in ("0-3", "2-3", "prenatal-1"):
        return False, "تراجع تلقائي: ممنوع استخدام التوليد التلقائي للأطفال الرضع دون 3 سنوات."

    # 3. Medical domain restriction: we never generate medical advice
    if domain == "medical":
        return False, "تراجع تلقائي: ممنوع استخدام التوليد التلقائي للاستشارات الطبية."

    # 4. Length checks
    if len(cleaned) < _MIN_TIP_LENGTH or len(cleaned) > _MAX_TIP_LENGTH:
        return False, f"تراجع تلقائي: النصيحة خارج نطاق الطول المسموح به (60-500 حرف). الطول الحالي: {len(cleaned)}"

    # 5. Language purity (No CJK, must contain Arabic letters)
    if _CJK_RE.search(cleaned):
        return False, "تراجع تلقائي: تم كشف أحرف غير عربية (صينية/يابانية)."
    if not re.search(r"[\u0600-\u06FF]", cleaned):
        return False, "تراجع تلقائي: النص لا يحتوي على أي أحرف عربية."

    latin_chars = len(re.findall(r"[a-zA-Z]", cleaned))
    if latin_chars > 0 and (latin_chars / len(cleaned)) > 0.03:
        return False, "تراجع تلقائي: نسبة الحروف اللاتينية مرتفعة جداً."

    # 6. Reject disclaimers or warning phrases
    cleaned_lower = cleaned.lower()
    for dec in _DISCLAIMERS:
        if dec in cleaned_lower:
            return False, f"تراجع تلقائي: تم كشف عبارة إخلاء مسؤولية أو نبرة عجز ({dec})."

    # 7. Non-medical domain term check
    if domain != "medical":
        for term in _MEDICAL_TERMS:
            if re.search(rf"\b{term}\w*\b", cleaned_lower):
                return False, f"تراجع تلقائي: تم كشف مصطلح طبي ({term}) في مجال غير طبي."

    # 8. Check for broken sentence fragments or conjunction ends
    if re.search(r"[\u0600-\u06FF]\s+[بتثجحخدذرزسشصضطظعغفقكلمنهوي]\.?$", cleaned):
        return False, "تراجع تلقائي: الجملة تنتهي بحرف منفصل مبهم."
    if re.search(r"\b(وبكسرت|وبكسر|بكسرت|بكسر)\b", cleaned_lower):
        return False, "تراجع تلقائي: تم كشف خطأ صياغة لغوية شائعة في التوليد."

    return True, cleaned
