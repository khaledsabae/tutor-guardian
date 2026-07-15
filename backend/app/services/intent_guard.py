"""Intent guard — blocks obviously harmful user prompts before they reach
any LLM or retrieval layer.

Two lines of defense:
1. Normalization to catch Franco-Arabic / repeated-letter / alif-variant
   / hamza-variant evasions.
2. Curated keyword and phrase lists (suicide/self-harm, medical dosing,
   sexual content, drugs/alcohol, child abuse, weapons, radicalization,
   privacy invasion).
"""
import re


# ---------------------------------------------------------------------------
# Normalization helpers.
# ---------------------------------------------------------------------------

_TASHKEEL = re.compile(r"[\u064B-\u065F\u0670\u0640]")
_REPEATED = re.compile(r"(.)\1{2,}")

_FRANCO = str.maketrans({
    "2": "أ",
    "3": "ع",
    "4": "غ",
    "5": "خ",
    "6": "ط",
    "7": "ح",
    "8": "ق",
    "9": "ص",
})


def _normalize_word(word: str) -> str:
    """Apply all char-level normalization to a single token."""
    word = word.lower()
    word = _TASHKEEL.sub("", word)
    # Alif variants and hamza-bearing letters collapse to bare alif/noise.
    word = word.replace("\u0622", "\u0627").replace("\u0623", "\u0627").replace("\u0625", "\u0627").replace("\u0671", "\u0627")
    # Strip standalone hamza forms so أؤذي becomes اذي (matches "أذى" variants).
    word = word.replace("\u0621", "").replace("\u0624", "").replace("\u0626", "")
    word = _REPEATED.sub(r"\1", word)
    word = word.translate(_FRANCO)
    # Keep only Arabic letters, ASCII letters and digits.
    word = re.sub(r"[^\u0600-\u06FF\u0750-\u077Fa-zA-Z0-9]", "", word)
    return word


def _normalize(text: str) -> str:
    """
    Lowercase, strip tashkeel/diacritics, collapse alif/hamza variants,
    remove repeated-char padding, and map common Franco-Arabic digits to
    Arabic letters. This is intentionally lossy: we only care about detecting
    banned intent, not preserving meaning.
    """
    return " ".join(
        _normalize_word(w) for w in text.split() if _normalize_word(w)
    )


# ---------------------------------------------------------------------------
# Banned keywords (single token) and phrases (2-3 tokens).
# Applied to the normalized, whitespace-split text.
# ---------------------------------------------------------------------------

_BANNED_KEYWORDS = {
    "انتحار",
    "انتحاري",
    "انتحر",
    "أقتل",
    "اقتل",
    "إيذاء",
    "أذية",
    "موت",
    "جنس",
    "جنسي",
    "إباحي",
    "إباحية",
    "تحرش",
    "مخدر",
    "مخدرات",
    "حشيش",
    "كحول",
    "خمر",
    "فودو",
    "بانجو",
    "هيروين",
    "كوكايين",
    "تعاطي",
    "سلاح",
    "مسدس",
    "بندقية",
    "قنبلة",
    "متفجرات",
    "سكين",
    "خنجر",
    "أجرم",
    "جريمة",
    "كفر",
    "كافر",
    "أكره",
    "أبغض",
    "فتنة",
    "طائفية",
    "اخترق",
    "اختراق",
    "تجسس",
    "جاسوس",
    "هاكر",
    "مراقبة",
}

_BANNED_KEYWORDS_NORM = {_normalize_word(w) for w in _BANNED_KEYWORDS}

_BANNED_PHRASES = {
    # Self-harm / suicide
    ("أقتل", "نفسي"),
    ("اقتل", "نفسي"),
    ("أذية", "النفس"),
    ("إيذاء", "نفس"),
    ("أنهي", "حياتي"),
    ("موت", "نفسي"),
    ("أموت", "نفسي"),
    ("اموت", "نفسي"),
    # Medical dosing
    ("جرعة", "زائدة"),
    ("جرعة", "كبيرة"),
    ("جرعة", "الدواء"),
    ("جرعة", "دواء"),
    ("كم", "حبة"),
    ("كم", "ملغ"),
    ("كم", "قرص"),
    ("جرعة", "دواء", "لطفلي"),
    ("أعطي", "طفلي", "دواء"),
    ("كمية", "الدواء"),
    # Sexual / inappropriate
    ("ممارسات", "جنسية"),
    ("مواقع", "إباحية"),
    ("صور", "عارية"),
    ("جنس", "مع"),
    # Child abuse
    ("كيف", "أؤذي"),
    ("أؤذي", "طفلي"),
    ("أذى", "طفلي"),
    ("أعرض", "طفلي"),
    ("أعرّض", "طفلي"),
    ("أوقع", "الأذى"),
    ("أضرب", "طفلي"),
    ("أعذب", "طفلي"),
    ("أهمل", "طفلي"),
    ("أضرب", "ابني"),
    ("اضرب", "ابني"),
    ("أعاقب", "ابني"),
    ("اعاقب", "ابني"),
    ("أضرب", "بنتي"),
    ("أعاقب", "بنتي"),
    ("سوء", "معاملة", "الطفل"),
    ("إساءة", "للطفل"),
    ("عنف", "ضد", "الطفل"),
    ("ضرب", "الأطفال"),
    ("تعذيب", "طفل"),
    ("إهمال", "طفل"),
    # Weapons / crime
    ("أصنع", "متفجرات"),
    ("أشتري", "سلاح"),
    ("أقتل", "شخص"),
    # Radicalization / hate
    ("قتل", "المشركين"),
    ("تطهير", "عرقي"),
    ("مسلمين", "كفار"),
    ("حرب", "أهلية"),
    ("فتنة", "طائفية"),
    # Privacy invasion
    ("كاميرا", "خفية"),
}

# Normalize the phrase vocabulary the same way incoming tokens are normalized.
_BANNED_PHRASES_NORM = {
    tuple(_normalize_word(t) for t in phrase): phrase
    for phrase in _BANNED_PHRASES
}


def check_banned_intent(text: str) -> tuple[bool, str]:
    """
    Returns (is_banned, matched_pattern).
    True = الطلب ممنوع ويجب إيقافه فوراً.
    """
    normalized = _normalize(text)
    tokens = normalized.split()

    # Single-token keywords.
    for token in tokens:
        if token in _BANNED_KEYWORDS_NORM:
            return True, token

    # Multi-token phrases.
    for i in range(len(tokens)):
        if i + 1 < len(tokens):
            phrase = (tokens[i], tokens[i + 1])
            if phrase in _BANNED_PHRASES_NORM:
                return True, " ".join(_BANNED_PHRASES_NORM[phrase])
        if i + 2 < len(tokens):
            phrase = (tokens[i], tokens[i + 1], tokens[i + 2])
            if phrase in _BANNED_PHRASES_NORM:
                return True, " ".join(_BANNED_PHRASES_NORM[phrase])

    return False, ""


# ---------------------------------------------------------------------------
# Emergency keywords — same normalization, checked as substring presence.
# ---------------------------------------------------------------------------

_EMERGENCY_KEYWORDS = {
    "يؤذي نفسه",
    "يضرب رأسه",
    "فقد الوعي",
    "حدث تشنج",
    "تشنج",
    "لا يتنفس",
    "سم",
    "ابتلع",
    "طارئ",
    "إسعاف",
    "انقطاع تنفس",
    "صعق كهربائي",
    "حريق",
    "غرق",
}

# Normalize once so alif/hamza variants in the input still match.
_EMERGENCY_KEYWORDS_NORM = {_normalize(kw) for kw in _EMERGENCY_KEYWORDS}


def check_emergency_keywords(text: str) -> bool:
    """True = يحتمل طارئ طبي → escalate فوراً."""
    normalized = _normalize(text)
    return any(kw in normalized for kw in _EMERGENCY_KEYWORDS_NORM)
