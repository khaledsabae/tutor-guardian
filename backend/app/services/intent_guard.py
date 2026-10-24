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
import unicodedata


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

# Latin letters that NFKD does not decompose into base + combining mark.
_LATIN_LIGATURES = str.maketrans({
    "\u0153": "oe", "\u0152": "oe", "\u00e6": "ae", "\u00c6": "ae",
    "\u00df": "ss", "\u00f8": "o", "\u00d8": "o", "\u0142": "l",
    "\u0141": "l", "\u0111": "d", "\u0110": "d",
})


_ARABIC_SCRIPT = re.compile(r"[\u0600-\u06FF\u0750-\u077F]")
# Franco-Arabic digits that stand for an Arabic letter (see `_FRANCO`).
_FRANCO_DIGITS = frozenset("23456789")


def _is_latin_extended(cp: int) -> bool:
    return 0x00C0 <= cp <= 0x024F or 0x1E00 <= cp <= 0x1EFF


def _fold_latin(word: str) -> str:
    """Drop accents from Latin-script letters: électrocuté -> electrocute.

    Only characters in the Latin-1 Supplement / Latin Extended blocks are
    touched (U+00C0-U+024F, U+1E00-U+1EFF). Arabic is never decomposed: its
    hamza and alif handling below depends on the code points staying as typed.
    Without this the `_NON_LETTER` filter below deleted every accented letter
    ("réveille" -> "rveille"), so French emergencies typed correctly never
    matched the unaccented keywords.

    A token that mixes in Arabic letters (or Franco digits, which become Arabic
    letters later) is not French, so it is returned untouched: the stray
    Latin-extended characters are then deleted by `_NON_LETTER` exactly as they
    always were, instead of being folded into a Latin letter that would glue
    itself to the Arabic ("ابنيé" -> "ابني", "é3" -> "ع"). Deleting them *after*
    the repeated-letter collapse, not before, is what keeps this identical to
    the old behaviour for such tokens.
    """
    if word.isascii():
        return word
    if _ARABIC_SCRIPT.search(word) or not _FRANCO_DIGITS.isdisjoint(word):
        return word
    out = []
    for ch in word:
        if _is_latin_extended(ord(ch)):
            ch = ch.translate(_LATIN_LIGATURES)
            ch = "".join(
                c for c in unicodedata.normalize("NFKD", ch)
                if not unicodedata.combining(c)
            )
        out.append(ch)
    return "".join(out)


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
    word = _fold_latin(word.lower())
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
    return " ".join(n for w in text.split() if (n := _normalize_word(w)))


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
# Abusive / vulgar language check — blocks explicit insults directed at the assistant
# ---------------------------------------------------------------------------

_ABUSIVE_KEYWORDS = {
    "انيك",
    "منيوك",
    "متناك",
    "شرموط",
    "شرموطة",
    "شرموطه",
    "عرص",
    "خول",
    "قحبة",
    "قحبه",
    "طيز",
}

_ABUSIVE_KEYWORDS_NORM = {_normalize_word(w) for w in _ABUSIVE_KEYWORDS}

_ABUSIVE_PHRASES = {
    ("كس", "امك"),
    ("يلعن", "امك"),
    ("يلعن", "ابوك"),
    ("يلعن", "دينك"),
    ("ابن", "الوسخة"),
    ("ابن", "الوسخه"),
    ("ابن", "الكلب"),
    ("يا", "عرص"),
    ("يا", "خول"),
    ("يا", "شرموط"),
    ("يا", "شرموطة"),
}

_ABUSIVE_PHRASES_NORM = {
    tuple(_normalize_word(t) for t in phrase): phrase
    for phrase in _ABUSIVE_PHRASES
}


def check_abusive_language(text: str) -> tuple[bool, str]:
    """Check if the text contains vulgar insults or profanity."""
    normalized = _normalize(text)
    tokens = normalized.split()

    for token in tokens:
        if token in _ABUSIVE_KEYWORDS_NORM:
            return True, token

    for i in range(len(tokens)):
        if i + 1 < len(tokens):
            phrase = (tokens[i], tokens[i + 1])
            if phrase in _ABUSIVE_PHRASES_NORM:
                return True, " ".join(_ABUSIVE_PHRASES_NORM[phrase])
        if i + 2 < len(tokens):
            phrase = (tokens[i], tokens[i + 1], tokens[i + 2])
            if phrase in _ABUSIVE_PHRASES_NORM:
                return True, " ".join(_ABUSIVE_PHRASES_NORM[phrase])

    return False, ""


# ---------------------------------------------------------------------------
# Conversational shortcut — immediate, deterministic replies for pleasantries
# ---------------------------------------------------------------------------

_THANKS_PHRASES = {
    "شكرا", "شكرا لك", "شكرا جزيلا", "شكرا جزيلا لك", "شكرا كتير", "شكرا يا غالي",
    "جزاك الله خيرا", "جزاك الله خير", "جزاكم الله خيرا", "جزاكم الله خير",
    "مشكور", "مشكورين", "تسلم", "تسلم ايدك", "يعطيك العافيه", "يعطيك الف عافيه",
    "الله يجزيك خير", "بارك الله فيك",
}

_GREETING_PHRASES = {
    "السلام عليكم", "السلام عليكم ورحمة الله", "السلام عليكم ورحمة الله وبركاته",
    "سلام", "سلام عليكم",
    "صباح الخير", "مساء الخير", "صباح النور", "مساء النور",
    "اهلا", "اهلا بك", "اهلا وسهلا", "مرحبا", "مرحبا بك", "هاي", "هلو",
}

# «كيف الحال» and friends reached the off-topic pivot, which answered a
# question nobody asked (👎 triage, 2026-10-04).
_HOW_ARE_YOU_PHRASES = {
    "كيف الحال", "كيف حالك", "كيف حالكم", "كيفك", "ازيك", "ازيكم",
    "عامل ايه", "عاملة ايه", "اخبارك ايه", "شلونك",
}

_CLOSING_PHRASES = {
    "لا شكر على واجب", "العفو", "على الرحب والسعة",
}

# Latin-script pleasantries got the Arabic pivot. Replies follow the parent's
# language: English unless the message itself is French.
_EN_THANKS_PHRASES = {
    "thanks", "thank you", "thanks a lot", "thank you so much", "thank you very much",
    "thx", "jazakallah khair", "jazak allah khair",
}
_EN_GREETING_PHRASES = {
    "hi", "hello", "hey", "hi there", "hello there", "good morning", "good evening",
}
# A salam is returned as a salam, whatever language the parent reads — and
# it is spelled a dozen ways (T8): "Salam", "Salaam alaikum", "salamualaikum",
# "As-salamu alaykum", "Assalam o alaikum", "Salam alaykoum", "Assalamou
# alaykoum", "Salamalekoum", "... wa rahmatullahi wa barakatuh". Matched on
# the normalized text with its spaces taken out; anchored, so a salam with a
# question after it still goes to the model.
_LATIN_SALAM_RE = re.compile(
    r"^(?:[ae]s?)?sala+m"                     # salam, salaam, assalam, asalam, essalam
    r"(?:u|ou|o)?"                            # salamu, salamou, salam o
    r"(?:a?l[ae]?[iy]?[kc](?:u|ou|o)m)?"      # alaikum, aleykum, alikoum, alaykoum, alekoum
    r"(?:wa?rahmat(?:u|ou|o)?l+ah[iy]?)?"     # wa rahmatullah(i), warahmatoullah
    r"(?:wa?barakat(?:u|ou|o)h?)?"            # wa barakatuh, wabarakatou
    r"(?:wrwb|wr)?$"
)
_FR_THANKS_PHRASES = {"merci", "merci beaucoup", "merci bien", "merci infiniment"}
_FR_GREETING_PHRASES = {"bonjour", "bonsoir", "salut", "coucou"}

_LATIN_REPLIES = {
    # Returned in full whatever the parent wrote — "with one better than it"
    # — as the Arabic reply above does.
    "salam": {
        "en": "Wa alaikum assalam wa rahmatullahi wa barakatuh! How can I help you today with your child's care and upbringing?",
        "fr": "Wa alaykoum assalam wa rahmatoullahi wa barakatouh ! Comment puis-je vous aider aujourd'hui pour l'éducation de votre enfant ?",
    },
    "thanks": {
        "en": "You're welcome! I'm always glad to help with anything about raising your child.",
        "fr": "Avec plaisir ! Je suis toujours là pour vous aider dans l'éducation de votre enfant.",
    },
    "greeting": {
        "en": "Hello, and welcome! How can I help you today with your child's care and upbringing?",
        "fr": "Bonjour et bienvenue ! Comment puis-je vous aider aujourd'hui pour l'éducation de votre enfant ?",
    },
}

_ARABIC_LETTER = re.compile(r"[\u0600-\u06FF]")
_LATIN_LETTER = re.compile(r"[A-Za-zÀ-ÿŒœ]")
_FR_ACCENTS = re.compile(r"[àâçéèêëîïôûùüÿœæ]", re.IGNORECASE)
# Words English does not share — "son", "on", "plus", "par" are left out.
_FR_WORDS = frozenset({
    "je", "j", "tu", "il", "elle", "nous", "vous", "mon", "ma", "mes", "ton", "ta",
    "est", "pas", "comment", "pourquoi", "quoi", "avec", "dans", "pour", "que",
    "qui", "une", "des", "les", "du", "au", "aux", "mais", "et", "enfant", "fils",
    "fille", "bonjour", "merci", "salut", "bonsoir", "coucou", "aider", "faire",
    "de", "le", "la", "un", "ne", "ce", "cette", "sa", "ses", "sur", "en", "très",
    "quand", "enfants", "bébé", "dort", "mange", "veut",
})
# How French speakers (Maghreb, West Africa) transliterate Arabic phrases:
# "alaykoum", "salamou", "rahmatoullah", "inchallah", "hamdoulillah".
_FR_TRANSLITERATION = re.compile(
    r"(?:koum|salamou|rahmatou|barakatou|inch'?\s?allah|hamdou|machallah)",
    re.IGNORECASE,
)


def detect_reply_language(text: str) -> str:
    """'ar', 'en' or 'fr' — the language to answer a short system message in.

    Arabic script wins. Latin text is French on two French words, on one
    French word in a short message or next to a French accent, or on a
    French-style transliteration («Salam alaykoum»); English otherwise. An
    accent alone is not enough (T8): "José" and "Chloé" are names in English
    sentences too. Deliberately coarse: it picks the language of an apology
    or a greeting, not of a whole answer (the model is told to mirror the
    parent for that).
    """
    t = text or ""
    ar = len(_ARABIC_LETTER.findall(t))
    la = len(_LATIN_LETTER.findall(t))
    if ar >= la:
        return "ar"
    if _FR_TRANSLITERATION.search(t):
        return "fr"
    words = re.findall(r"[a-zà-ÿœ]+", t.lower())
    french = sum(1 for w in words if w in _FR_WORDS)
    if french >= 2 or (french and (len(words) <= 3 or _FR_ACCENTS.search(t))):
        return "fr"
    return "en"

_THANKS_NORM = {_normalize(p) for p in _THANKS_PHRASES}
_GREETING_NORM = {_normalize(p) for p in _GREETING_PHRASES}
_HOW_ARE_YOU_NORM = {_normalize(p) for p in _HOW_ARE_YOU_PHRASES}
_CLOSING_NORM = {_normalize(p) for p in _CLOSING_PHRASES}
_EN_THANKS_NORM = {_normalize(p) for p in _EN_THANKS_PHRASES}
_EN_GREETING_NORM = {_normalize(p) for p in _EN_GREETING_PHRASES}
_FR_THANKS_NORM = {_normalize(p) for p in _FR_THANKS_PHRASES}
_FR_GREETING_NORM = {_normalize(p) for p in _FR_GREETING_PHRASES}


def check_conversational_shortcut(text: str, lang: str | None = None) -> tuple[bool, str]:
    """If the text is strictly a greeting, thanks, or pleasantry with no actual
    question, return (True, predefined_response) to bypass LLM and avoid
    unprompted activity generation.

    `lang` ('en'/'fr') picks the language of a Latin-script reply; by default
    it is detected from the text.
    """
    norm = _normalize(text).strip()
    if not norm:
        return False, ""

    if norm in _THANKS_NORM:
        return True, "عفوًا، وجزاك الله خيرًا! يسعدني دائمًا مساعدتك في كل ما يخص طفلك وتربيته. أتمنى لك ولأسرتك دوام التوفيق والبركة."

    if norm in _GREETING_NORM:
        return True, "وعليكم السلام ورحمة الله وبركاته، أهلاً بك! كيف يمكنني مساعدتك اليوم في رعاية طفلك وتربيته؟"

    if norm in _HOW_ARE_YOU_NORM:
        return True, "الحمد لله، أهلاً بك! كيف يمكنني مساعدتك اليوم في رعاية طفلك وتربيته؟"

    if norm in _CLOSING_NORM:
        return True, "بارك الله فيك ويسّر أمرك! أنا في خدمتك دائمًا لأي استشارة أو تساؤل تربوي."

    latin = lang if lang in ("en", "fr") else detect_reply_language(text)
    if latin not in ("en", "fr"):
        latin = "en"
    if _LATIN_SALAM_RE.match(norm.replace(" ", "")):
        return True, _LATIN_REPLIES["salam"][latin]
    if norm in _FR_THANKS_NORM:
        return True, _LATIN_REPLIES["thanks"]["fr"]
    if norm in _FR_GREETING_NORM:
        return True, _LATIN_REPLIES["greeting"]["fr"]
    if norm in _EN_THANKS_NORM:
        return True, _LATIN_REPLIES["thanks"][latin]
    if norm in _EN_GREETING_NORM:
        return True, _LATIN_REPLIES["greeting"][latin]

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
    # Colloquial phrasings. Until 2026-10-23 only the noun and the masculine
    # verb were here, so the way parents actually write it never escalated:
    # "بنتي عايزة تنتحر", "مش عايز يعيش", "نفسي أموت", "هموّت نفسي" all went
    # to the normal advice path. Every entry below needs a second word that
    # makes the wish explicit — bare "يموت"/"أموت" is everyday hyperbole
    # ("هموت من الضحك") and talk about a grandparent's death. Spelling
    # variants (ة/ه، ى/ي) are generated by `_spelling_variants` below.
    "تنتحر",
    "انتحرت",
    "يحاول ينتحر",
    "مش عايز يعيش",
    "مش عايزة تعيش",
    "مش عاوز يعيش",
    "مش عاوزة تعيش",
    "مش عايز اعيش",
    "مش عايزة اعيش",
    "مش عاوز اعيش",
    "مش عاوزة اعيش",
    "مش عايز يعيش في الدنيا",
    "مش عايزة تعيش في الدنيا",
    "مش عايز اعيش في الدنيا",
    "مش عايزة اعيش في الدنيا",
    "عايز يموت",
    "عايزة تموت",
    "عاوز يموت",
    "عاوزة تموت",
    "عايز اموت",
    "عايزة اموت",
    "عاوز اموت",
    "عاوزة اموت",
    "نفسي اموت",
    "نفسه يموت",
    "نفسها تموت",
    "يتمنى الموت",
    "تتمنى الموت",
    "يتمنى يموت",
    "تتمنى تموت",
    "هموت نفسي",
    "يموت نفسه",
    "تموت نفسها",
    "اموت نفسي",
    "اقتل نفسي",
    "هقتل نفسي",
    "تقتل نفسها",
    "يخلص على نفسه",
    "تخلص على نفسها",
    "اخلص على نفسي",
    "تنهي حياتها",
    "انهي حياتي",
    "يأذي نفسه",
    "تأذي نفسها",
    # Noun forms: «بيتكلم عن إيذاء نفسه», «بتتكلم عن أذية نفسها». The
    # normalizer deletes hamza, so إيذاء -> "ايذا" and أذية -> "اذيه" (the
    # existing "إيذاء النفس" is "ايذا النفس"). The reflexive pronoun is
    # required: "إيذاء" alone is also "hurting others". The PAST verb
    # («أذى نفسه وهو بيلعب») is deliberately not here — that is a play
    # accident, not intent; the noun carries the wish or the plan.
    "إيذاء نفسه",
    "إيذاء نفسها",
    "إيذاء نفسي",
    "أذية نفسه",
    "أذية نفسها",
    "أذية نفسي",
    "أذى بنفسه",
    "أذى بنفسها",
    "أذى بنفسي",
    "الحياة ملهاش لازمة",
    "الحياة مالهاش لازمة",
    "حياتي ملهاش لازمة",
    # Round 4: stems the Egyptian future / first person drops the alif from
    # ("هنتحر", "هنهي حياتي", "هخلص على نفسي"); «هأذي/هاذي نفسي» normalize to
    # هاذي and match «اذي نفسي» through the ه proclitic; «أؤذي» is «اوذي».
    "هنتحر",
    "هنهي حياتي",
    "هخلص على نفسي",
    "اذي نفسي",
    "اوذي نفسي",
    # Passive wishes and "tired of life". «تعبت من الحياة» can be plain venting;
    # for a message about a child the cost of asking is lower than the cost of
    # missing it, so it escalates (school / work / marriage life is excluded).
    "ياريتني مت",
    "يا ريتني مت",
    "ياريتني كنت مت",
    "يا ريتني كنت مت",
    "ياريتني اموت",
    "يا ريتني اموت",
    "ياريتني ما اتولدت",
    "يا ريتني ما اتولدت",
    "ياريتني ما اتولدتش",
    "يا ريتني ما اتولدتش",
    "تعبت من الحياة",
    "زهقت من الحياة",
    "تعب من الحياة",
    "زهق من الحياة",
    "كرهت حياتي",
    "كرهت حياتها",
    "كره حياته",
    "يكره حياته",
    "تكره حياتها",
    "اكره حياتي",
    "هيرتاح لو مت",
    "هيرتاحوا لو مت",
    "هترتاح لو مت",
    "هترتاحوا لو مت",
    "هرتاح لو مت",
    # Methods and their first-person / reflexive forms
    "اشنق نفسي",
    "هشنق نفسي",
    "يشنق نفسه",
    "تشنق نفسها",
    "شنق نفسه",
    "شنقت نفسها",
    "هغرق نفسي",
    "اغرق نفسي",
    "هولع في نفسي",
    "اولع في نفسي",
    "يولع في نفسه",
    "تولع في نفسها",
    "هحرق نفسي",
    "احرق نفسي",
    "تجرح ايدها",
    "تجرح ايديها",
    "يجرح ايده",
    "يجرح ايديه",
    "تقطع ايدها",
    "تقطع ايديها",
    "يقطع ايده",
    "يقطع ايديه",
    # Gulf and Levantine
    "ودي انتحر",
    "ابي انتحر",
    "ابغى انتحر",
    "بدي انتحر",
    "بدي خلص حالي",
    "بدي قتل حالي",
    "قتل حالو",
    "قتل حالها",
    "بدو يقتل حالو",
    "بدها تقتل حالها",
    # First-person throwing oneself needs no place: a threat in the first
    # person is not play language. Third person («بيرمي نفسه») still does.
    "هرمي نفسي",
    "هرمي بنفسي",
    "ارمي نفسي",
    "ارمي بنفسي",
    # MSA
    "لا يريد أن يعيش",
    "لا تريد أن تعيش",
    "يريد أن يموت",
    "تريد أن تموت",
    # ── English ──────────────────────────────────────────────────────────
    #
    # 🚨 Not hypothetical. GA4, 28 days: 881 users (27%) run the app on an
    # English device and 129 of them sent 331 messages to the assistant;
    # another 71 on French devices sent 145. The UI already ships in English
    # to any `locale=en` device. Until now this whole set was Arabic, so an
    # English "she is not breathing" never escalated — it went to the normal
    # parenting path and came back as advice.
    #
    # Same discipline as the Arabic entries above: multi-word where a single
    # word is ambiguous, because the failure this file already survived once
    # was over-matching, not under-matching. "choking hazard", "poison
    # prevention", "drowning prevention" and "burn safety" are ordinary
    # questions a careful parent asks, and answering them with "call an
    # ambulance" teaches parents the assistant is broken.
    #
    # No digits: `_FRANCO` maps 9→ص and 3→ع, so "call 911" normalizes to
    # "call ص11" and a digit keyword can never match.
    #
    # Airway / breathing
    "not breathing",
    "stopped breathing",
    "cant breathe",
    "cannot breathe",
    "is choking",
    "choked on",
    # Consciousness
    "unconscious",
    "passed out",
    "lost consciousness",
    "wont wake up",
    "will not wake up",
    "not waking up",
    # Seizure
    "having a seizure",
    "had a seizure",
    "is convulsing",
    # Ingestion — the verb is what separates an incident from a safety question
    "swallowed bleach",
    "swallowed poison",
    "swallowed a battery",
    "swallowed batteries",
    "swallowed detergent",
    "swallowed pills",
    "drank bleach",
    "drank poison",
    "ate rat poison",
    "took too many pills",
    "overdosed",
    "overdose",
    # Trauma
    "severe bleeding",
    "bleeding heavily",
    "wont stop bleeding",
    "is drowning",
    "electric shock",
    "electrocuted",
    "badly burned",
    "third degree burn",
    # Summoning help
    "call an ambulance",
    "need an ambulance",
    "call emergency services",
    # Self-harm and suicide. Deliberately including the bare nouns, matching
    # the Arabic side (انتحار/ينتحر): a false escalation here costs a parent
    # one unhelpful reply, and the alternative cost is not symmetric.
    "suicide",
    "suicidal",
    "kill himself",
    "kill herself",
    "kill myself",
    "hurt himself",
    "hurt herself",
    "hurting himself",
    "hurting herself",
    "harm himself",
    "harm herself",
    "self harm",
    "cutting herself",
    "cutting himself",
    "end his life",
    "end her life",
    "wants to die",
    "want to die",
    "doesnt want to live",
    "dont want to live",
    "wishes he was dead",
    "wishes she was dead",
    "wish i was dead",
    "wishes he were dead",
    "wishes she were dead",
    "wish i were dead",
    "selfharm",
    "selfharming",
    "self harming",
    "self harms",
    "end it all",
    "rather be dead",
    "doesnt want to be alive",
    "dont want to be alive",
    "does not want to be alive",
    "do not want to be alive",
    "no longer want to be alive",
    "no longer wants to be alive",
    "does not want to live",
    "do not want to live",
    # "in" is excluded after the bare phrase (custody / relocation), so the
    # existential reading needs its own entries.
    "doesnt want to live in this world",
    "dont want to live in this world",
    "does not want to live in this world",
    "do not want to live in this world",
    # ── French ───────────────────────────────────────────────────────────
    #
    # 353 users (11%) on French devices; 71 of them sent 145 messages to the
    # assistant. Deliberately narrower than the English set: only phrasings
    # where the emergency is unambiguous, because I can verify English parent
    # idiom against the app's own data and cannot do the same here.
    # ⚠️ Wants a native-speaker pass before it is treated as complete —
    # what is here should not fire wrongly, but it certainly misses cases.
    "ne respire plus",
    "ne respire pas",
    # s'étouffe → "setouffe": the normalizer strips the apostrophe *inside* the
    # whitespace token, so the elided pronoun stays glued to the verb. One
    # token covers every subject. (My first guess here was "stouffe", which
    # would never have matched anything — the test caught it, not review.)
    "setouffe",
    "inconscient",
    "inconsciente",
    "perdu connaissance",
    "ne se reveille pas",
    "crise convulsive",
    "convulsions",
    "a avale de leau de javel",
    "a avale une pile",
    "a bu de leau de javel",
    "a avale du poison",
    "empoisonne",
    "empoisonnee",
    "hemorragie",
    "saigne beaucoup",
    "electrocute",
    "electrocutee",      # feminine: «elle s'est électrocutée»
    "appelez une ambulance",
    "appeler une ambulance",
    "se suicider",
    "suicide",           # مشترك مع الإنجليزية، والتطبيع يوحّدهما
    "se fait du mal",
    "se scarifie",
    "veut mourir",
    # Added 2026-10-23 with the Arabic colloquial set. Still only phrasings
    # that are unambiguous; "mourir de rire / de honte / de faim" is excluded
    # for "envie de mourir" in `_EMERGENCY_EXCLUSIONS`.
    "ne veut plus vivre",
    "ne veux plus vivre",
    "ne veulent plus vivre",
    "veut se tuer",
    "veux me tuer",
    "veut en finir avec la vie",
    "envie de mourir",
    "envie de se tuer",
    # Round 4
    "voulait mourir",
    "voulait se tuer",
    "va se tuer",
    "veut se faire du mal",
    "a essayé de se tuer",
    "idées suicidaires",
    "n'a plus envie de vivre",
    "n'ont plus envie de vivre",
    "ne veut pas vivre",
    "veut se pendre",
    "s'automutile",
    "s'automutilent",
    "ne veut plus vivre dans ce monde",
    "ne veut plus vivre en ce monde",
    "ne veux plus vivre dans ce monde",
    "ne veux plus vivre en ce monde",
}



def _spelling_variants(phrase: str) -> set[str]:
    """Every combination of final ة/ه and ى/ي across the phrase's words.

    `_normalize_word` keeps these letters distinct on purpose (they separate
    real words elsewhere), but parents type both: "عايزة"/"عايزه",
    "يتمنى"/"يتمني". Generating the variants here keeps the normalizer intact.
    """
    swaps = {"ة": "ه", "ه": "ة", "ى": "ي", "ي": "ى"}
    options = []
    for word in phrase.split():
        forms = {word}
        if word[-1] in swaps:
            forms.add(word[:-1] + swaps[word[-1]])
        options.append(sorted(forms))
    results = {""}
    for forms in options:
        results = {f"{r} {f}".strip() for r in results for f in forms}
    return results


# Jumping or throwing oneself from a height. "يرمي نفسه" and "ينط" alone are
# play ("بيرمي نفسه من على الكنبة", "بينط على السرير", "بيرمي نفسه في حضني"),
# so no verb is a keyword by itself: every entry is verb + "من" (+ "على" /
# "فوق") + a place that is actually high. A sofa, bed or chair is not in the
# list, so those sentences never match and need no exclusion. Final-letter
# spellings (ة/ه، ى/ي) come from `_spelling_variants` like every other entry.
# "نفسه" is required for the throwing verbs: "يرمي الكورة من الشباك" is a ball.
_THROW_VERBS = (
    "يرمي نفسه", "ترمي نفسها", "ارمي نفسي", "هرمي نفسي",
    "رمي نفسه", "رمت نفسها", "رميت نفسي",
    "يلقي نفسه", "تلقي نفسها", "القي نفسي", "القى نفسه", "القت نفسها",
)
# Egyptian "نط" = jump, MSA "قفز"; the place carries the meaning
_LEAP_VERBS = (
    "ينط", "تنط", "انط", "هنط", "نط", "نطت",
    "يقفز", "تقفز", "اقفز", "هقفز", "قفز", "قفزت",
)
_JUMP_VERBS = _THROW_VERBS + _LEAP_VERBS
_JUMP_FROM = ("من", "من على", "من فوق")
_HEIGHT_PLACES = (
    "شباك", "نافذة", "بلكونة", "شرفة", "سطح", "سطوح", "دور", "عمارة",
    "طابق", "كوبري", "جسر", "برج",
)
# Not "from a height" but just as final. Only the throwing verbs: «بينط في
# البحر» is a child at the beach. «يرمي نفسه في البحر» can still be a beach
# sentence; that cost is accepted, the other side of it is not.
_THROW_INTO = ("في النيل", "في البحر")
_IN_FRONT_OF = ("قدام القطر", "قدام المترو", "قدام العربية")
_LEAP_IN_FRONT_OF = ("قدام القطر", "قدام المترو")
_JUMP_SELF_HARM = (
    {
        f"{verb} {frm} {place}"
        for verb in _JUMP_VERBS
        for frm in _JUMP_FROM
        for place in _HEIGHT_PLACES
    }
    | {f"{verb} {place}" for verb in _THROW_VERBS for place in _THROW_INTO + _IN_FRONT_OF}
    | {f"{verb} {place}" for verb in _LEAP_VERBS for place in _LEAP_IN_FRONT_OF}
)

# ── Gulf, Levantine and "no longer" forms of «لا يريد أن يعيش» ──────────────
#
# The Egyptian «مش عايز يعيش» family was written out by hand; the same wish in
# the other registers is generated: negation word x wanting word x "live".
_NOT_WANT_LIVE_NEG = ("مش", "مبقاش", "ما بقاش", "مبقتش", "ما بقتش", "ما عادش", "معادش")
_WANTING = (
    (("عايز", "عاوز"), ("يعيش", "اعيش")),
    (("عايزة", "عاوزة"), ("تعيش", "اعيش")),
)
_NOT_WANT_LIVE_EG = {
    f"{neg} {want} {verb}"
    for neg in _NOT_WANT_LIVE_NEG
    for wants, verbs in _WANTING
    for want in wants
    for verb in verbs
}
# Gulf «ما ابي اعيش», Levantine «ما بدو يعيش / ما بدي عيش».
_NOT_WANT_LIVE_OTHER = {
    "ما ابي اعيش", "ما ابغى اعيش", "ما بدو يعيش", "ما بدها تعيش",
    "ما بدي عيش", "ما بدي اعيش",
}
_NOT_WANT_LIVE = _NOT_WANT_LIVE_EG | _NOT_WANT_LIVE_OTHER
# "…في الدنيا / الحياة / العالم / الكون" says it is the world, not a place.
_NOT_WANT_LIVE_WORLD = {
    f"{kw} في {world}"
    for kw in _NOT_WANT_LIVE_EG
    for world in ("الدنيا", "الحياة", "العالم", "الكون")
}
_NOT_VALUED = {
    f"{neg} لازمة في {where}"
    for neg in ("مليش", "ماليش")
    for where in ("الدنيا", "الحياة")
}
_ARTERIES = {
    f"{verb} {obj}"
    for verb in ("قطع", "قطعت", "يقطع", "تقطع", "اقطع", "هقطع")
    for obj in ("شرايينه", "شراينه", "شرايينها", "شراينها", "شرايني", "شراييني")
}

# Keywords that say "I / he wants to die". A negation right before one flips
# the sentence ("مش عايز اموت", "he doesnt want to die"), so these — and only
# these — are cancelled by a preceding negation word. «مش عايز يعيش» is NOT
# here: it is the crisis itself.
_WISH_TO_DIE = (
    {
        f"{want} {verb}"
        for wants, verbs in (
            (("عايز", "عاوز"), ("يموت", "اموت")),
            (("عايزة", "عاوزة"), ("تموت", "اموت")),
        )
        for want in wants
        for verb in verbs
    }
    | {
        "نفسي اموت", "نفسه يموت", "نفسها تموت",
        "يتمنى الموت", "تتمنى الموت", "يتمنى يموت", "تتمنى تموت",
        "يريد أن يموت", "تريد أن تموت",
        # Gulf, Levantine
        "ودي اموت", "ابي اموت", "ابغى اموت", "يبي يموت", "تبي تموت",
        "يبغى يموت", "تبغى تموت", "بدي اموت", "بدي موت", "بدها تموت", "بدو يموت",
        # English, French
        "want to die", "wants to die",
        "veut mourir", "voulait mourir", "envie de mourir",
    }
)

# Keywords typed with ي (the Egyptian verb, «اذي نفسي» = I harm myself) whose ى
# spelling is a different, ordinary word: «أذى نفسي» is "psychological harm"
# (a phrase straight out of the app's own knowledge base). No spelling variants.
_EXACT_SPELLING = frozenset({"اذي نفسي", "اوذي نفسي"})

_EMERGENCY_KEYWORDS = {
    variant
    for kw in (
        _EMERGENCY_KEYWORDS | _JUMP_SELF_HARM | _NOT_WANT_LIVE | _NOT_WANT_LIVE_WORLD
        | _NOT_VALUED | _ARTERIES | _WISH_TO_DIE
    )
    for variant in ({kw} if kw in _EXACT_SPELLING else _spelling_variants(kw))
}

# Emergency keywords whose meaning flips when a specific word follows.
# Checked after a keyword hits: a match here cancels the escalation.
#
# Idioms of exaggeration. Each tail is cancelled again when the text also holds
# a distress marker (`_DISTRESS_MARKERS`): «هموت نفسي من العياط ومحدش حاسس بيا»
# is the sentence, not the idiom. «من الجوع» and «من الخضة» are not listed at
# all: a child who wants to die "of hunger" and has stopped eating is exactly
# the case an exclusion must not hide.
_HYPERBOLE: tuple[tuple[str, ...], ...] = (
    ("من", "العياط"), ("في", "العياط"), ("من", "الضحك"), ("من", "الكسوف"),
    ("من", "التعب"), ("من", "الحر"), ("من", "الزهق"), ("من", "الغيظ"),
    ("من", "الفرحة"),
)
# "يموّت نفسه ضحك / في المذاكرة / في الشغل" = works / laughs himself to death.
# Not «عشان / علشان»: «هموت نفسي عشان أريحكم» is a crisis.
_OVERWORK: tuple[tuple[str, ...], ...] = (
    ("ضحك",), ("بالضحك",), ("مذاكره",), ("في", "المذاكره"), ("في", "الشغل"),
    ("شغل",),
)
_ACCIDENTAL: tuple[tuple[str, ...], ...] = (
    ("بالغلط",), ("بالصدفه",), ("بالصدفة",), ("بدون", "قصد"), ("من", "غير", "قصد"),
)
_WHERE_TO_LIVE: tuple[tuple[str, ...], ...] = (
    ("في",), ("مع",), ("عند",), ("هنا",), ("هناك",), ("بره",), ("برا",),
    ("لوحده",), ("لوحدها",), ("لوحدي",), ("معانا",), ("معاهم",), ("معاها",),
    ("معاه",), ("بعيد",), ("قريب",), ("على",), ("غير",), ("بين",), ("جنب",),
    ("تحت",),
)
_EN_WHERE_TO_LIVE: tuple[tuple[str, ...], ...] = tuple(
    (w,) for w in ("with", "in", "at", "near", "far", "here", "there", "alone", "abroad")
)
_FR_WHERE_TO_LIVE: tuple[tuple[str, ...], ...] = (
    ("chez",), ("avec",), ("ici",), ("dans",), ("en",),
)
# A religious wish, not a death wish: "نفسي أموت شهيد",
# "نفسي أموت على الإسلام", "نفسي أموت وأنا ساجد".
_MARTYR: tuple[tuple[str, ...], ...] = (("شهيد",), ("شهيدا",), ("شهيدة",))
_RELIGIOUS_WISH = _MARTYR + (
    ("على", "الاسلام"), ("مسلم",), ("مسلمة",),
    ("وانا", "ساجد"), ("وانا", "ساجدة"), ("في", "سبيل"),
)
# Egyptian "تموت على / لـ X" = adores X: «عايزة تموت للمدرسة» is a girl who
# cannot wait for school. A listed object only: any «ل…» word would also take
# «لانه», «لاني», «لحد» and, worst, «لنفسها».
_ADORES: tuple[tuple[str, ...], ...] = tuple(
    (w,) for w in ("للمدرسة", "للجامعة", "للاكل", "للكورة", "لحماتها", "لحماته")
)
# «تعبت من الحياة المدرسية / العملية» is a tired student or employee.
_LIFE_QUALIFIED: tuple[tuple[str, ...], ...] = tuple(
    (w,) for w in ("المدرسية", "الجامعية", "العملية", "الزوجية", "الوظيفية")
)
# Prevention / cooking tails for «بتجرح ايدها / بتقطع ايدها».
_KITCHEN_ACCIDENT: tuple[tuple[str, ...], ...] = _ACCIDENTAL + (
    ("وهي", "بتطبخ"), ("وهي", "بتقطع"), ("وهو", "بيطبخ"), ("وهو", "بيقطع"),
    ("وهي", "بتعمل"), ("وهو", "بيعمل"),
)

_NOT_WANT_LIVE_KEYS = tuple(tuple(kw.split()) for kw in sorted(_NOT_WANT_LIVE)) + (
    ("لا", "يريد", "أن", "يعيش"), ("لا", "تريد", "أن", "تعيش"),
)

# (keys, tails) rules, merged into `_EMERGENCY_EXCLUSIONS`. A key may appear in
# several rules; its tails are the union.
_EXCLUSION_RULES: tuple[tuple[tuple[tuple[str, ...], ...], tuple[tuple[str, ...], ...]], ...] = (
    # Egyptian "غرّق السرير" is bedwetting, not drowning.
    ((("غرق",),), (("السرير",), ("الفرش",), ("المرتبة",), ("سريره",))),
    # Sleep apnea is chronic and belongs in a normal consultation.
    ((("انقطاع", "تنفس"),), (("النوم",), ("نومه",), ("نومها",))),
    # Egyptian hyperbole: "بيموّت نفسه من العياط" = cries a lot,
    # "عايزة تموت من الكسوف" = embarrassed. The wish is literal otherwise.
    # Keys and tails are expanded over ة/ه and ى/ي by `_spelling_variants`.
    (
        (
            ("يموت", "نفسه"), ("تموت", "نفسها"), ("هموت", "نفسي"), ("اموت", "نفسي"),
            ("عايز", "يموت"), ("عايزة", "تموت"), ("عاوز", "يموت"), ("عاوزة", "تموت"),
            ("عايز", "اموت"), ("عايزة", "اموت"), ("عاوز", "اموت"), ("عاوزة", "اموت"),
            ("نفسي", "اموت"), ("نفسه", "يموت"), ("نفسها", "تموت"),
        ),
        _HYPERBOLE,
    ),
    # Working or laughing oneself to death.
    (
        (
            ("يموت", "نفسه"), ("تموت", "نفسها"), ("هموت", "نفسي"), ("اموت", "نفسي"),
            ("يخلص", "على", "نفسه"), ("تخلص", "على", "نفسها"), ("اخلص", "على", "نفسي"),
            ("يقتل", "نفسه"), ("تقتل", "نفسها"), ("اقتل", "نفسي"), ("هقتل", "نفسي"),
        ),
        _OVERWORK,
    ),
    # The same idioms in Gulf and Levantine: «بدي موت من الضحك».
    (
        (
            ("ودي", "اموت"), ("ابي", "اموت"), ("ابغى", "اموت"), ("يبي", "يموت"),
            ("تبي", "تموت"), ("يبغى", "يموت"), ("تبغى", "تموت"), ("بدي", "اموت"),
            ("بدي", "موت"), ("بدها", "تموت"), ("بدو", "يموت"),
        ),
        _HYPERBOLE + _MARTYR,
    ),
    # "نفسي أموت شهيد / على الإسلام / وأنا ساجد".
    ((("نفسي", "اموت"), ("نفسه", "يموت"), ("نفسها", "تموت")), _RELIGIOUS_WISH),
    # Wishing for martyrdom, or adoring something.
    (
        (
            ("عايز", "يموت"), ("عايزة", "تموت"), ("عاوز", "يموت"), ("عاوزة", "تموت"),
            ("عايز", "اموت"), ("عايزة", "اموت"), ("عاوز", "اموت"), ("عاوزة", "اموت"),
        ),
        _MARTYR + _ADORES,
    ),
    (
        (
            ("يريد", "أن", "يموت"), ("تريد", "أن", "تموت"),
            ("يتمنى", "الموت"), ("تتمنى", "الموت"), ("يتمنى", "يموت"), ("تتمنى", "تموت"),
        ),
        _MARTYR,
    ),
    # "مش عايز يعيش" is also where a child refuses to live: "مش عايز يعيش في
    # الغربة / مع جدته / لوحده". A place or person right after cancels it;
    # "مش عايز يعيش في الدنيا" is its own keyword, so the wish still escalates.
    (_NOT_WANT_LIVE_KEYS, _WHERE_TO_LIVE),
    # The noun phrase is not a wish to self-harm when the incident was
    # explicitly accidental: «ايذاء نفسه بالغلط / بالصدفة / بدون قصد». Play
    # tails («وهو بيلعب») are NOT excluded: a child who talks about hurting
    # himself while playing is still a child talking about hurting himself.
    (
        (
            ("ايذا", "نفسه"), ("ايذا", "نفسها"), ("ايذا", "نفسي"),
            ("اذيه", "نفسه"), ("اذيه", "نفسها"), ("اذيه", "نفسي"),
            ("اذى", "بنفسه"), ("اذى", "بنفسها"), ("اذى", "بنفسي"),
        ),
        _ACCIDENTAL,
    ),
    ((("تجرح", "ايدها"), ("تجرح", "ايديها"), ("يجرح", "ايده"), ("يجرح", "ايديه"),
      ("تقطع", "ايدها"), ("تقطع", "ايديها"), ("يقطع", "ايده"), ("يقطع", "ايديه")),
     _KITCHEN_ACCIDENT),
    # "الحياة ملهاش لازمة من غير ولادي" is love, not despair.
    (
        (
            ("الحياة", "ملهاش", "لازمة"), ("الحياة", "مالهاش", "لازمة"),
            ("حياتي", "ملهاش", "لازمة"),
        ),
        (("من", "غير"),),
    ),
    (
        (("تعبت", "من", "الحياة"), ("زهقت", "من", "الحياة"),
         ("تعب", "من", "الحياة"), ("زهق", "من", "الحياة")),
        _LIFE_QUALIFIED,
    ),
    # French
    (
        (("envie", "de", "mourir"), ("veut", "mourir"), ("voulait", "mourir")),
        (("de", "rire"), ("de", "honte"), ("de", "faim")),
    ),
    # "se tuer à la tâche" = to work oneself to the bone. Accents are folded
    # ("à la tâche" -> "a la tache"); the "la tache" / "tche" tails are kept
    # for text that reached the normalizer already stripped.
    (
        (("veut", "se", "tuer"), ("voulait", "se", "tuer"), ("va", "se", "tuer")),
        (
            ("a", "la", "tache"), ("la", "tache"), ("a", "la", "tche"), ("la", "tche"),
            ("au", "travail"),
        ),
    ),
    # "ne veut plus vivre chez son père" is where, not whether.
    (
        (
            ("ne", "veut", "plus", "vivre"), ("ne", "veux", "plus", "vivre"),
            ("ne", "veulent", "plus", "vivre"), ("ne", "veut", "pas", "vivre"),
            ("ne", "veux", "pas", "vivre"), ("ne", "veulent", "pas", "vivre"),
        ),
        _FR_WHERE_TO_LIVE,
    ),
    # "en finir avec la vie scolaire / professionnelle / de quartier".
    (
        (("veut", "en", "finir", "avec", "la", "vie"),),
        (("scolaire",), ("professionnelle",), ("de", "quartier")),
    ),
    # English
    (
        (("want", "to", "die"), ("wants", "to", "die")),
        (("laughing",), ("of", "embarrassment")),
    ),
    # "doesn't want to live with his father" is where, not whether.
    (
        (
            ("doesnt", "want", "to", "live"), ("dont", "want", "to", "live"),
            ("does", "not", "want", "to", "live"), ("do", "not", "want", "to", "live"),
        ),
        _EN_WHERE_TO_LIVE,
    ),
)

# Phrasing that precedes a keyword and turns it into a question about a ruling,
# not a report: «هل يجوز أن يتمنى الموت», «حكم من يتمنى الموت». Looked for in
# the four words before the hit.
_PRE_WINDOW = 4
_PRE_EXCLUSIONS: dict[tuple[str, ...], tuple[tuple[str, ...], ...]] = {
    key: (("يجوز",), ("حكم",))
    for key in (
        ("يتمنى", "الموت"), ("تتمنى", "الموت"), ("يتمنى", "يموت"), ("تتمنى", "تموت"),
    )
}

# A tail followed by one of these words is not that tail any more:
# «من غير ولادي» is love, «من غير ما حد يسمعني» is despair.
_TAIL_VETO = {("من", "غير"): frozenset({"ما"})}

# Words before a «wish to die» keyword that negate it.
_NEGATIONS = frozenset({
    "مش", "ما", "لا", "ومش", "فمش",   # never "ولا": «ولا عايز يموت» is "or wants to die"
    "not", "pas", "doesnt", "dont", "didnt", "never",
})

# Words anywhere in the text that mean the exaggeration idiom is not the
# whole story: bullying, refusing food, nobody listening, an attempt.
_DISTRESS_MARKERS: tuple[tuple[str, ...], ...] = (
    ("اتنمر",), ("اتنمروا",), ("اتنمرو",), ("تنمر",), ("تنمروا",), ("تنمرو",),
    ("مش", "قادر"), ("مش", "قادرة"), ("محدش",), ("بتمتنع",), ("بيمتنع",),
    ("حاول",), ("حاولت",), ("حاولوا",),
    ("بيضحكوا", "عليا"), ("بيضحكو", "عليا"),
    ("بيتريقوا",), ("بيتريقو",), ("بيتريق",), ("بتتريق",), ("اتريقوا",), ("اتريقو",),
)
# «الناس بتضحكه عليا»: any "laugh" word followed closely by "at me".
_LAUGHED_AT = frozenset({"عليا", "عليه", "عليها"})


def _expand_words(words: tuple[str, ...]) -> list[tuple[str, ...]]:
    """Every ة/ه and ى/ي spelling of a word sequence, normalized, de-duplicated."""
    seen: dict[tuple[str, ...], None] = {}
    for variant in sorted(_spelling_variants(" ".join(words))):
        seen[tuple(_normalize_word(w) for w in variant.split())] = None
    return list(seen)


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
# present tense (بيؤذي), conjunctions (وابتلع), the definite article (الحريق),
# "with the" (بالانتحار, والانتحار).
_PROCLITICS = (
    "ب", "بي", "و", "وب", "ف", "ال", "لل", "ل", "ك", "ه", "ها",
    "بال", "وال", "فال", "وبال",
)

# Below this length a keyword must match the token exactly. "سم" is two
# letters; allowing a proclitic there would let "بسم" (بسم الله) match again.
_MIN_LEN_FOR_PROCLITIC = 3

# The one exception: the negation words that open «مش عايز يعيش». «ومش عايز
# يعيش» / «فمش عايزة تعيش» is how a parent writes it mid-sentence, and a
# conjunction on these two-letter words does not turn them into another word.
_SHORT_WITH_CONJUNCTION = frozenset({"مش", "لا", "ما"})


def _token_matches(token: str, needle: str) -> bool:
    """True when `token` is `needle`, optionally carrying a proclitic."""
    if token == needle:
        return True
    if len(needle) < _MIN_LEN_FOR_PROCLITIC:
        return (
            needle in _SHORT_WITH_CONJUNCTION
            and len(token) == len(needle) + 1
            and token[0] in "وف"
            and token.endswith(needle)
        )
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


# Exclusions, three stages. `_EMERGENCY_EXCLUSIONS` merges the rules above;
# `_EMERGENCY_EXCLUSIONS_EXPANDED` spreads keys *and tails* over their ة/ه and
# ى/ي spellings (a tail typed «شهيده» or «فى سبيل» must cancel just like the
# spelling written here); `_EMERGENCY_EXCLUSIONS_NORM` is the normalized form
# the matcher reads.
_EMERGENCY_EXCLUSIONS: dict[tuple[str, ...], tuple[tuple[str, ...], ...]] = {}
for _keys, _tails in _EXCLUSION_RULES:
    for _key in _keys:
        _EMERGENCY_EXCLUSIONS[_key] = _EMERGENCY_EXCLUSIONS.get(_key, ()) + _tails


def _expand_raw(words: tuple[str, ...]) -> list[tuple[str, ...]]:
    return [tuple(v.split()) for v in sorted(_spelling_variants(" ".join(words)))]


_EMERGENCY_EXCLUSIONS_EXPANDED: dict[tuple[str, ...], tuple[tuple[str, ...], ...]] = {}
for _kw, _exclusions in _EMERGENCY_EXCLUSIONS.items():
    _tails = tuple(dict.fromkeys(v for ex in _exclusions for v in _expand_raw(ex)))
    for _variant in _expand_raw(_kw):
        _EMERGENCY_EXCLUSIONS_EXPANDED[_variant] = tuple(dict.fromkeys(
            _EMERGENCY_EXCLUSIONS_EXPANDED.get(_variant, ()) + _tails
        ))

_EMERGENCY_EXCLUSIONS_NORM: dict[tuple[str, ...], tuple[tuple[str, ...], ...]] = {}
for _kw, _exclusions in _EMERGENCY_EXCLUSIONS_EXPANDED.items():
    _nk = tuple(_normalize_word(t) for t in _kw)
    _nt = tuple(tuple(_normalize_word(t) for t in ex) for ex in _exclusions)
    _EMERGENCY_EXCLUSIONS_NORM[_nk] = tuple(dict.fromkeys(
        _EMERGENCY_EXCLUSIONS_NORM.get(_nk, ()) + _nt
    ))

# Tails that are idioms and give way to a distress marker.
_GUARDED_TAILS_NORM = frozenset(
    tail for ex in _HYPERBOLE + _OVERWORK for tail in _expand_words(ex)
)
_DISTRESS_MARKERS_NORM = tuple(
    marker for m in _DISTRESS_MARKERS for marker in _expand_words(m)
)
_NEGATABLE_NORM = frozenset(
    tuple(_normalize(variant).split())
    for kw in _WISH_TO_DIE
    for variant in _spelling_variants(kw)
)
_PRE_EXCLUSIONS_NORM = {
    nk: tuple(m for ex in markers for m in _expand_words(ex))
    for key, markers in _PRE_EXCLUSIONS.items()
    for nk in _expand_words(key)
}

# First word -> needles starting with it, for the lookup in
# `check_emergency_keywords`.
_EMERGENCY_BY_FIRST: dict[str, list[tuple[str, ...]]] = {}
for _needle in _EMERGENCY_KEYWORDS_NORM:
    _EMERGENCY_BY_FIRST.setdefault(_needle[0], []).append(_needle)


def _sequence_positions(tokens: list[str], needle: tuple[str, ...]) -> list[int]:
    """Start indices where `needle` matches consecutive whole tokens."""
    span = len(needle)
    if not needle or span > len(tokens):
        return []
    return [
        i for i in range(len(tokens) - span + 1)
        if all(_token_matches(tokens[i + j], needle[j]) for j in range(span))
    ]


def _has_distress_marker(tokens: list[str]) -> bool:
    """True when the whole text carries a sign that an idiom is not just an idiom."""
    if any(_sequence_positions(tokens, m) for m in _DISTRESS_MARKERS_NORM):
        return True
    return any(
        "ضحك" in tok and not _LAUGHED_AT.isdisjoint(tokens[i + 1:i + 4])
        for i, tok in enumerate(tokens)
    )


def _is_excluded(tokens: list[str], needle: tuple[str, ...], start: int) -> bool:
    """True when the words around a hit reveal a benign meaning."""
    if needle in _NEGATABLE_NORM and start > 0 and tokens[start - 1] in _NEGATIONS:
        return True
    markers = _PRE_EXCLUSIONS_NORM.get(needle)
    if markers:
        window = tokens[max(0, start - _PRE_WINDOW):start]
        if any(_sequence_positions(window, m) for m in markers):
            return True
    exclusions = _EMERGENCY_EXCLUSIONS_NORM.get(needle)
    if not exclusions:
        return False
    tail = tokens[start + len(needle):]
    distressed: bool | None = None
    for ex in exclusions:
        if not _sequence_positions(tail[:len(ex)], ex):
            continue
        if _TAIL_VETO.get(ex, frozenset()).intersection(tail[len(ex):len(ex) + 1]):
            continue
        if ex in _GUARDED_TAILS_NORM:
            if distressed is None:
                distressed = _has_distress_marker(tokens)
            if distressed:
                continue
        return True
    return False


def check_emergency_keywords(text: str) -> bool:
    """True = يحتمل طارئ طبي → escalate فوراً.

    Matches on whole-token boundaries so a keyword never fires from inside an
    unrelated word, and honours `_EMERGENCY_EXCLUSIONS` for keywords whose
    meaning flips with the following word (غرق السرير = bedwetting).
    """
    tokens = _normalize(text).split()
    for start, token in enumerate(tokens):
        # Look up only the needles whose first word this token could be, with
        # or without a proclitic, instead of scanning every needle. The jump
        # phrases made the list ~2.5k entries; the full scan cost ~17ms.
        bases = {token}
        bases.update(token[len(p):] for p in _PROCLITICS if token.startswith(p))
        for base in bases:
            for needle in _EMERGENCY_BY_FIRST.get(base, ()):
                if (
                    start + len(needle) <= len(tokens)
                    and all(
                        _token_matches(tokens[start + j], needle[j])
                        for j in range(len(needle))
                    )
                    and not _is_excluded(tokens, needle, start)
                ):
                    return True
    return False
