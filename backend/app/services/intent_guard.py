import re

BANNED_PATTERNS = [
    # أذى النفس
    r"(انتحار|أذية النفس|إيذاء نفس|اقتل نفس|أقتل نفسي)",
    # جرعات دواء
    r"(جرعة|كمية الدواء|كم حبة|كم ملغ|ملليغرام)",
    # محتوى غير لائق
    r"(إباحي|جنسي|تحرش)",
    # نشاط غير قانوني
    r"(مخدر|حشيش|كحول)",
    # إيذاء الطفل / إساءة معاملة
    r"(كيف أؤذي|أؤذي طفلي|أذى طفلي|أعرّض طفلي|أعرض طفلي|أوقع الأذى|أضرب طفلي|أعذب طفلي|أهمل طفلي|سوء معاملة الطفل|إساءة للطفل|عنف ضد الطفل|كيف أضرب|اضرب ابني|أضرب ابني|اعاقب ابني|كيف اعاقب)",
]

COMPILED = [re.compile(p, re.UNICODE | re.IGNORECASE) for p in BANNED_PATTERNS]

def check_banned_intent(text: str) -> tuple[bool, str]:
    """
    Returns (is_banned, matched_pattern).
    True = الطلب ممنوع ويجب إيقافه فوراً.
    """
    for pattern in COMPILED:
        match = pattern.search(text)
        if match:
            return True, match.group()
    return False, ""

EMERGENCY_KEYWORDS = [
    "يؤذي نفسه", "يضرب رأسه", "لا يتنفس", "فقد الوعي",
    "تشنج", "سم", "ابتلع", "طارئ", "إسعاف"
]

def check_emergency_keywords(text: str) -> bool:
    """True = يحتمل طارئ طبي → escalate فوراً."""
    return any(kw in text for kw in EMERGENCY_KEYWORDS)
