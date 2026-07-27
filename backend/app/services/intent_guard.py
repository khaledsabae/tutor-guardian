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
# Arabic-script letters plus ASCII alphanumerics. Everything else — including
# Arabic punctuation, which shares the U+0600 block with the letters — is dropped.
_NON_LETTER = re.compile(
    r"[^\u0620-\u064A\u0660-\u0669\u066E-\u06D3\u06D5\u06E5-\u06FF"
    r"\u0750-\u077Fa-zA-Z0-9]"
)

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
    # Alif variants collapse to bare alif.
    word = word.replace("\u0622", "\u0627").replace("\u0623", "\u0627").replace("\u0625", "\u0627").replace("\u0671", "\u0627")
    # Hamza carriers map to their carrier letter instead of being deleted.
    # Deleting them collapsed distinct words onto each other: طارئ and طائر
    # both became "طار", so "ابني بيرسم طائر" read as a medical emergency.
    # Mapping ئ->ي and ؤ->و keeps them apart and still matches spelling variants.
    word = word.replace("\u0626", "\u064A").replace("\u0624", "\u0648")
    word = word.replace("\u0621", "")
    word = _REPEATED.sub(r"\1", word)
    word = word.translate(_FRANCO)
    # Keep only Arabic letters, ASCII letters and digits. Arabic punctuation
    # (، ؛ ؟ ٪ ۔) lives inside U+0600-U+06FF, so it has to be excluded
    # explicitly — otherwise a trailing "؟" stayed glued to the token and
    # "ازاي أصنع قنبلة؟" sailed straight past the banned-keyword check.
    word = _NON_LETTER.sub("", word)
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

# Only words that carry harmful intent on their own belong here. A bare topic
# noun does not: this list previously refused "بنتي حصلها تحرش في الأتوبيس"
# (تحرش), "ابني بيسأل عن موت جده" (موت), "تثقيف جنسي" (جنسي),
# "ابني بيقول أنا أكره المدرسة" (أكره), "تطبيق مراقبة أبوية" (مراقبة) and
# even "ساكنين في كفر الشيخ" (كفر). Topic words moved to _BANNED_PHRASES,
# where they must co-occur with an instrumental verb; self-harm words moved to
# the emergency lane so a frightened parent gets help instead of a refusal.
_BANNED_KEYWORDS = {
    "فودو",
    "بانجو",
    "هيروين",
    "كوكايين",
    "متفجرات",
}

_BANNED_KEYWORDS_NORM = {_normalize_word(w) for w in _BANNED_KEYWORDS}

# Every entry pairs a topic with an instrumental verb or an unambiguous target.
# Reporting, protecting and asking-about are NOT banned — a parent describing
# abuse, grooming or drug worries needs an answer, not a closed door.
_BANNED_PHRASES = {
    # Medical dosing — asking us to set a dose. ("كم","حبة") and friends were
    # removed: they fired on questions about a dose the doctor already gave.
    ("جرعة", "زائدة"),
    ("جرعة", "كبيرة"),
    ("جرعة", "الدواء"),
    ("جرعة", "دواء"),
    ("جرعة", "دواء", "لطفلي"),
    ("كمية", "الدواء"),
    # Sexual — soliciting the content, not discussing it. ("مواقع","إباحية")
    # and ("صور","عارية") were removed: they blocked "ازاي أحجب مواقع إباحية"
    # and a live grooming report ("حد طلب من بنتي صور عارية").
    ("ممارسات", "جنسية"),
    ("جنس", "مع"),
    # Child abuse — first-person intent to harm. The descriptive phrases
    # (سوء معاملة الطفل / إساءة للطفل / عنف ضد الطفل / تعذيب طفل / إهمال طفل)
    # were removed: every one of them blocked a protective or reporting
    # question. ("أعاقب","ابني") was removed outright — عقاب is neutral, and it
    # blocked "ازاي أعاقب ابني من غير ضرب", which is exactly what this app is for.
    ("كيف", "أؤذي"),
    ("أؤذي", "طفلي"),
    ("أذى", "طفلي"),
    ("أعرض", "طفلي"),
    ("أعرّض", "طفلي"),
    ("أوقع", "الأذى"),
    ("أعذب", "طفلي"),
    ("أعذب", "ابني"),
    # Drugs / alcohol — acquiring or using, not discussing with a teen.
    ("أشتري", "مخدرات"),
    ("أبيع", "مخدرات"),
    ("أجيب", "مخدرات"),
    ("أتعاطى", "مخدرات"),
    ("أشتري", "حشيش"),
    ("أشرب", "خمر"),
    ("أشتري", "خمر"),
    # Weapons / crime
    ("أصنع", "متفجرات"),
    ("أصنع", "قنبلة"),
    ("أشتري", "سلاح"),
    ("أقتل", "شخص"),
    ("أقتل", "حد"),
    ("أطعن", "بسكين"),
    ("أهدد", "بسكين"),
    # Radicalization / hate
    ("قتل", "المشركين"),
    ("تطهير", "عرقي"),
    ("مسلمين", "كفار"),
    ("فتنة", "طائفية"),
    # Privacy invasion — spying on an adult. Parental monitoring and baby
    # monitors are legitimate, so ("كاميرا","خفية") alone is no longer banned.
    ("أتجسس", "على", "زوجتي"),
    ("أتجسس", "على", "جوزي"),
    ("أتجسس", "على", "مراتي"),
    ("اخترق", "حساب"),
    ("أخترق", "حساب"),
    ("اخترق", "موبايل"),
    ("اخترق", "تليفون"),
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
    # Acute medical
    "يؤذي نفسه",
    "تؤذي نفسها",
    "يضرب رأسه",
    "فقد الوعي",
    "تشنج",           # "حدث تشنج" was redundant with this
    "لا يتنفس",
    "صعق كهربائي",
    "حريق",
    "غرق",
    "ابتلع",
    "بلعت",
    # Poisoning. Bare "سم" is gone: as a two-letter token it is centimetres,
    # and this app asks about height and growth constantly
    # ("طول ابني 120 سم"). Bare "تسمم" is gone too — it matched the topic
    # phrase "التسمم الغذائي إزاي أمنعه". The real signal needs a second word.
    "شرب سم",
    "بلع سم",
    "سم فئران",
    "مبيد حشري",
    "عنده تسمم",
    "حصله تسمم",
    "اتسمم",
    # Calling for an ambulance. Bare "إسعاف" would match "شنطة إسعاف البيت"
    # and first-aid-training questions, so it needs the request verb.
    "محتاج إسعاف",
    "عايز إسعاف",
    "اطلب إسعاف",
    "اتصل بالإسعاف",
    # Self-harm and suicide. These used to sit in _BANNED_KEYWORDS, and since
    # the banned check runs first (assistant.py:87), a parent reporting a
    # suicidal teen was answered with "هذا الموضوع خارج نطاق ما يمكنني
    # مساعدتك فيه" — a refusal, at the worst possible moment. They escalate now.
    "انتحار",
    "ينتحر",
    "انتحر",
    "إيذاء النفس",
    "يجرح نفسه",
    "تجرح نفسها",
    "ينهي حياته",
    "يقتل نفسه",
}

# Emergency keywords whose meaning flips when a specific word follows.
# Checked after a keyword hits: a match here cancels the escalation.
_EMERGENCY_EXCLUSIONS: dict[tuple[str, ...], tuple[tuple[str, ...], ...]] = {
    # Egyptian "غرّق السرير" is bedwetting, not drowning.
    ("غرق",): (("السرير",), ("الفرش",), ("المرتبة",), ("سريره",)),
    # Sleep apnea is chronic and belongs in a normal consultation.
    ("انقطاع", "تنفس"): (("النوم",), ("نومه",), ("نومها",)),
}

# Normalize once so alif/hamza variants in the input still match. Stored as
# token tuples, not strings: matching must respect word boundaries.
#
# This used to be a plain substring test over the whole normalized string, so
# every short keyword matched inside longer words — "سم" fired on يسمع, اسم,
# جسم, يقسم. "ابني المراهق يعاند ولا يسمع الكلام" (one of the app's own
# suggested questions) was classified as a medical emergency and answered with
# "اتصل بالطوارئ" instead of parenting advice.
_EMERGENCY_KEYWORDS_NORM = {
    tuple(_normalize(kw).split()) for kw in _EMERGENCY_KEYWORDS
}


# Proclitics a parent's phrasing bolts onto the front of a word — Egyptian
# present tense (بيؤذي), conjunctions (وابتلع), the definite article (الحريق).
_PROCLITICS = ("ب", "بي", "و", "وب", "ف", "ال", "لل", "ل", "ك", "ه", "ها")

# Below this length a keyword must match the token exactly. "سم" is two
# letters; allowing a proclitic there would let "بسم" (بسم الله) match again.
_MIN_LEN_FOR_PROCLITIC = 3


def _token_matches(token: str, needle: str) -> bool:
    """True when `token` is `needle`, optionally carrying a proclitic."""
    if token == needle:
        return True
    if len(needle) < _MIN_LEN_FOR_PROCLITIC:
        return False
    return any(token == p + needle for p in _PROCLITICS)


def _contains_token_sequence(tokens: list[str], needle: tuple[str, ...]) -> bool:
    """True when `needle` appears as consecutive whole tokens in `tokens`."""
    if not needle or len(needle) > len(tokens):
        return False
    span = len(needle)
    return any(
        all(_token_matches(tokens[i + j], needle[j]) for j in range(span))
        for i in range(len(tokens) - span + 1)
    )


_EMERGENCY_EXCLUSIONS_NORM = {
    tuple(_normalize_word(t) for t in kw): tuple(
        tuple(_normalize_word(t) for t in ex) for ex in exclusions
    )
    for kw, exclusions in _EMERGENCY_EXCLUSIONS.items()
}


def _sequence_positions(tokens: list[str], needle: tuple[str, ...]) -> list[int]:
    """Start indices where `needle` matches consecutive whole tokens."""
    span = len(needle)
    if not needle or span > len(tokens):
        return []
    return [
        i for i in range(len(tokens) - span + 1)
        if all(_token_matches(tokens[i + j], needle[j]) for j in range(span))
    ]


def _is_excluded(tokens: list[str], needle: tuple[str, ...], start: int) -> bool:
    """True when the words right after a hit reveal a benign meaning."""
    exclusions = _EMERGENCY_EXCLUSIONS_NORM.get(needle)
    if not exclusions:
        return False
    tail = tokens[start + len(needle):]
    return any(_sequence_positions(tail[:len(ex)], ex) for ex in exclusions)


def check_emergency_keywords(text: str) -> bool:
    """True = يحتمل طارئ طبي → escalate فوراً.

    Matches on whole-token boundaries so a keyword never fires from inside an
    unrelated word, and honours `_EMERGENCY_EXCLUSIONS` for keywords whose
    meaning flips with the following word (غرق السرير = bedwetting).
    """
    tokens = _normalize(text).split()
    for needle in _EMERGENCY_KEYWORDS_NORM:
        for start in _sequence_positions(tokens, needle):
            if not _is_excluded(tokens, needle, start):
                return True
    return False
