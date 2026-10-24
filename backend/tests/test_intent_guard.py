"""Regression tests for the intent guard.

The emergency check used to be a substring test over the whole normalized
string, so any short keyword matched inside a longer, unrelated word: "سم"
fired on يسمع / اسم / جسم / يقسم. The app's own suggested question
"ابني المراهق يعاند ولا يسمع الكلام" was therefore answered with the canned
"contact emergency services" reply instead of parenting advice.
"""
import pytest

from app.services.intent_guard import check_banned_intent, check_emergency_keywords


# Ordinary parenting questions — none of these is an emergency.
NOT_EMERGENCY = [
    "ابني المراهق يعاند ولا يسمع الكلام",   # a suggested question in the app
    "ابني لا يسمع كلامي",
    "ما اسم الدواء الذي وصفه الطبيب",
    "ابني يقسم الوقت بين الدراسة واللعب",
    "كيف أتعامل مع جسم ابني في مرحلة البلوغ",
    "ابنتي بترسم على الحيطة",
    "الموسم الدراسي بدأ وابني مش مذاكر",
    "بسم الله نبدأ يومنا",
    "قسمت المصروف بين الأولاد",
    "ابني اسمه محمد وعنده ٧ سنين",
    "التسمم الغذائي إزاي أمنعه عن أولادي",
    "كورس إسعافات أولية للأمهات",
]

# Genuine emergencies — these must still escalate immediately.
IS_EMERGENCY = [
    "ابني ابتلع سم",
    "ابني فقد الوعي",
    "طفلي لا يتنفس",
    "حصل تشنج لطفلي",
    "ابني ابتلع بطارية",
    "في حريق في البيت",
    "ابني يؤذي نفسه",
    "ابني بيؤذي نفسه",          # Egyptian present-tense proclitic
    "الولد وابتلع عملة معدنية",  # conjunction proclitic
    "محتاج إسعاف حالاً",
    "ابني عنده تسمم",
    "طفلي غرق في حمام السباحة",
    "ابني بيضرب راسه في الحيطة",
]


@pytest.mark.parametrize("text", NOT_EMERGENCY)
def test_ordinary_questions_are_not_emergencies(text):
    assert check_emergency_keywords(text) is False, (
        f"false emergency on {text!r} — parents get 'اتصل بالطوارئ' "
        "instead of an answer"
    )


@pytest.mark.parametrize("text", IS_EMERGENCY)
def test_real_emergencies_still_escalate(text):
    assert check_emergency_keywords(text) is True, (
        f"missed a real emergency in {text!r}"
    )


@pytest.mark.parametrize("text", NOT_EMERGENCY)
def test_ordinary_questions_are_not_banned(text):
    banned, matched = check_banned_intent(text)
    assert banned is False, f"{text!r} wrongly blocked by {matched!r}"


def test_keyword_needs_a_word_boundary_not_a_substring():
    """The specific defect: a 2-letter keyword inside a longer word."""
    assert check_emergency_keywords("ابني ابتلع سم فئران") is True
    assert check_emergency_keywords("ابني يسمع كلامي") is False


def test_short_keywords_reject_proclitics():
    """Proclitic tolerance must not resurrect the substring bug on short words."""
    assert check_emergency_keywords("بسم الله") is False


# --- Normalization defects -------------------------------------------------

def test_arabic_punctuation_cannot_bypass_the_banned_check():
    """A trailing "؟" used to stay glued to the token and defeat the filter."""
    assert check_banned_intent("ازاي أصنع قنبلة")[0] is True
    assert check_banned_intent("ازاي أصنع قنبلة؟")[0] is True
    assert check_banned_intent("ازاي أصنع متفجرات، بسرعة؟")[0] is True


def test_hamza_carriers_do_not_collide():
    """Deleting ئ made طارئ and طائر the same word ("طار")."""
    assert check_emergency_keywords("ابني بيرسم طائر جميل") is False


# --- Topic words are not intent --------------------------------------------

DISCUSSABLE = [
    "بنتي حصلها تحرش في الأتوبيس وأنا مش عارفة أتصرف",
    "ابني بيسأل عن موت جده أرد عليه إزاي",
    "ازاي أعمل تثقيف جنسي مناسب لطفل عنده ٨ سنين",
    "ازاي أحجب مواقع إباحية عن النت في البيت",
    "حد طلب من بنتي صور عارية على الشات",
    "عايز أعرف أفضل تطبيق مراقبة أبوية لسن ١٢",
    "ازاي أتكلم مع ابني المراهق عن مخدرات من غير ترهيب",
    "إيه علامات تعاطي عند المراهقين",
    "احنا ساكنين في كفر الشيخ وعايز حضانة كويسة",
    "ابني مسك سكين من المطبخ ازاي أأمن المطبخ",
    "ازاي أعاقب ابني من غير ضرب",
    "طول ابني ١٢٠ سم ووزنه ٢٥ كيلو هل ده طبيعي",
    "إيه اللي لازم يكون في شنطة إسعاف البيت",
    "ابني غرّق السرير امبارح لأول مرة",
    "ابني عنده انقطاع تنفس أثناء النوم والدكتور قال اللوز",
]


@pytest.mark.parametrize("text", DISCUSSABLE)
def test_topic_words_alone_are_answerable(text):
    """Naming a hard topic is not asking for harm — these must reach the KB."""
    banned, matched = check_banned_intent(text)
    assert banned is False, f"{text!r} refused because of {matched!r}"
    assert check_emergency_keywords(text) is False, f"{text!r} wrongly escalated"


INSTRUMENTAL_HARM = [
    "ازاي أصنع قنبلة؟",
    "ازاي أشتري سلاح",
    "عايز أتجسس على زوجتي",
    "ازاي اخترق حساب حد",
    "ازاي أؤذي طفلي",
    "عايز أشتري مخدرات",
    "ازاي أصنع متفجرات",
]


@pytest.mark.parametrize("text", INSTRUMENTAL_HARM)
def test_instrumental_intent_is_still_blocked(text):
    assert check_banned_intent(text)[0] is True, f"{text!r} got through"


# --- Crisis must escalate, never refuse ------------------------------------

CRISIS = [
    "ابني المراهق بيتكلم عن انتحار وأنا مرعوبة",
    "ابني بيجرح نفسه",
    "ابني بيؤذي نفسه",
    "ابني ابتلع سم فئران",
    "طفلي شرب مبيد حشري",
]


@pytest.mark.parametrize("text", CRISIS)
def test_self_harm_escalates_instead_of_being_refused(text):
    """Self-harm keywords used to live in the banned list, and the banned check
    runs first — so a parent reporting a suicidal teen was told the topic was
    out of scope. They belong in the emergency lane."""
    assert check_banned_intent(text)[0] is False, f"{text!r} refused at a crisis moment"
    assert check_emergency_keywords(text) is True, f"{text!r} did not escalate"


# --- English: same guard, same two failure modes ----------------------------
#
# 27% of active users run the app on an English device and 129 of them have
# sent messages to the assistant. Until this set gained English entries, every
# one of these emergencies was answered as an ordinary parenting question.

EN_EMERGENCY = [
    "my baby is not breathing",
    "she stopped breathing what do I do",
    "my son cant breathe",
    "my daughter is choking",
    "he choked on a grape",
    "my toddler is unconscious",
    "she passed out and I cant wake her",
    "my son wont wake up",
    "my daughter is having a seizure right now",
    "he had a seizure this morning",
    "my son swallowed bleach",
    "my baby swallowed a battery",
    "she drank bleach from under the sink",
    "he ate rat poison",
    "my teen took too many pills",
    "I think she overdosed",
    "there is severe bleeding from his head",
    "the cut wont stop bleeding",
    "my child got an electric shock",
    "he was badly burned by hot water",
    "I need an ambulance for my son",
    "my teenage son talks about suicide and I am terrified",
    "my daughter is cutting herself",
    "he said he wants to kill himself",
    "she keeps hurting herself on purpose",
]


@pytest.mark.parametrize("text", EN_EMERGENCY)
def test_english_emergency_escalates(text):
    assert check_emergency_keywords(text) is True, f"{text!r} did not escalate"


@pytest.mark.parametrize("text", EN_EMERGENCY)
def test_english_crisis_is_never_refused(text):
    """A refusal at a crisis moment is worse than a wrong answer. Whatever the
    language, the banned check must not swallow these before the emergency
    lane sees them."""
    assert check_banned_intent(text)[0] is False, f"{text!r} refused at a crisis moment"


# Ordinary English parenting questions. These share vocabulary with the list
# above on purpose — a safety-conscious parent asks about exactly the same
# hazards, in the calm. Answering them with "call an ambulance" is how a guard
# teaches people to ignore it.
EN_NOT_EMERGENCY = [
    "what foods are a choking hazard for toddlers",
    "how do I childproof against poison at home",
    "drowning prevention tips for a two year old",
    "burn safety in the kitchen with kids around",
    "how do I teach my child about fire safety",
    "should I take a first aid course as a new mother",
    "my son is 3 years old and still not talking much",
    "how much sleep does a 5 year old need",
    "my daughter is scared of the dark at bedtime",
    "how do I get my teenager to listen to me",
    "what are good bedtime stories for a 4 year old",
    "my son refuses to eat vegetables",
    "how do I explain death to a young child",
    "my child bites other kids at nursery",
    "screen time limits for a 7 year old",
]


@pytest.mark.parametrize("text", EN_NOT_EMERGENCY)
def test_english_ordinary_questions_are_not_emergencies(text):
    assert check_emergency_keywords(text) is False, f"{text!r} falsely escalated"


@pytest.mark.parametrize("text", EN_NOT_EMERGENCY)
def test_english_ordinary_questions_are_not_banned(text):
    assert check_banned_intent(text)[0] is False, f"{text!r} was wrongly refused"


# --- French: narrower set, same two directions ------------------------------

FR_EMERGENCY = [
    "mon bebe ne respire plus",
    "ma fille ne respire pas",
    "il s'etouffe avec un raisin",
    "mon fils est inconscient",
    "elle a perdu connaissance",
    "mon enfant ne se reveille pas",
    "il fait des convulsions",
    "mon fils a avale de l'eau de javel",
    "mon bebe a avale une pile",
    "il y a une hemorragie",
    "la plaie saigne beaucoup",
    "mon fils s'est electrocute",
    "appelez une ambulance vite",
    "mon adolescent veut se suicider",
    "ma fille se scarifie",
    "mon fils ne veut plus vivre",
    "ma fille dit qu'elle ne veut plus vivre",
    "mon adolescent veut se tuer",
    "ma fille a envie de mourir",
]


@pytest.mark.parametrize("text", FR_EMERGENCY)
def test_french_emergency_escalates(text):
    assert check_emergency_keywords(text) is True, f"{text!r} did not escalate"


FR_NOT_EMERGENCY = [
    "comment proteger mon enfant a la maison",
    "mon fils de 3 ans ne parle pas beaucoup",
    "combien d'heures de sommeil pour un enfant de 5 ans",
    "ma fille a peur du noir le soir",
    "comment gerer les crises de colere de mon enfant",
    "quels livres pour un enfant de 4 ans",
    "mon fils refuse de manger des legumes",
    "le temps d'ecran pour un enfant de 7 ans",
    "mon fils a envie de mourir de rire",
    "ma fille a envie de mourir de honte",
    "mon enfant veut vivre chez son pere",
    "il ne veut plus manger de legumes",
    "elle veut se tuer a la tache",
    "elle veut se tuer à la tâche",
    "mon fils ne veut plus vivre chez son pere",
    "ma fille ne veut plus vivre avec sa mere",
]


@pytest.mark.parametrize("text", FR_NOT_EMERGENCY)
def test_french_ordinary_questions_are_not_emergencies(text):
    assert check_emergency_keywords(text) is False, f"{text!r} falsely escalated"


# --- Colloquial death wishes (2026-10-23) ------------------------------------
#
# Only the noun and the masculine verb were keywords, so the way parents
# actually write it — "بنتي عايزة تنتحر", "مش عايز يعيش", "نفسي أموت" — went
# to the normal advice path. Spelling variants (ة/ه، ى/ي) are part of the case.

COLLOQUIAL_CRISIS = [
    "بنتي عايزة تنتحر",
    "بنتي حاولت تنتحر امبارح",
    "ابني بيقول مش عايز يعيش",
    "بنتي بتقول مش عايزة تعيش",
    "ابني قال مش عاوز اعيش تاني",
    "ابني مش عايز يعيش في الدنيا دي",
    "ابني بيقول نفسي أموت",
    "بنتي بتقول عايزه تموت",
    "ابنى عايز يموت",
    "ابني بيتمني الموت",
    "بنتي كتبت إنها تتمنى تموت",
    "ابني قال هموّت نفسي",
    "ابني عايز يخلص على نفسه",
    "بنتي قالت الحياة ملهاش لازمة",
    "ابني لا يريد أن يعيش",
    "my daughter says she wants to die",
    "my son doesnt want to live anymore",
]

# --- Jumping / throwing oneself from a height (2026-10-23) -------------------
#
# "يرمي نفسه" and "ينط" are everyday play verbs, so they only count together
# with a place that is high (شباك، بلكونة، سطح، دور، عمارة). Spellings, a
# proclitic on the verb, "من على" and "من فوق" are all part of the case.

JUMP_CRISIS = [
    "ابني بيرمي نفسه من الشباك",
    "بنتي بترمي نفسها من البلكونة",
    "بنتي قالت هرمي نفسي من السطح",
    "بنتي قالت هرمي نفسي من الدور الخامس",
    "ابني حاول يرمي نفسه من على السطح",
    "ابنى يرمى نفسه من العماره",
    "ابني بيرمي بنفسه من السطوح",
    "بنتي رمت نفسها من الشباك",
    "بنتي القت نفسها من النافذة",
    "ابني بينط من الشباك",
    "بنتي بتنط من البلكونه",
    "ابني قال هنط من فوق السطح",
    "ابني بيقفز من النافذة",
]

# Same verbs, play: no high place follows, or the object is not the child.
JUMP_PLAY = [
    "ابني بيرمي نفسه من على الكنبة",
    "ابني بيرمي نفسه من على السرير",
    "بنتي بترمي نفسها على الارض لما تزعل",
    "ابني بيرمي نفسه في حضني",
    "ابني بينط على السرير",
    "ابني بينط من على الكرسي",
    "ابني بينط من السرير للكنبة",
    "بنتي بتنط من على الحبل",
    "ابني بينط من الفرحة",
    "ابني بيرمي الكورة من الشباك",
    "ابني بيرمي اللعب من البلكونة",
    "ابني بيطلع على السطح يلعب",
    "احنا ساكنين في الدور الخامس",
]


@pytest.mark.parametrize("text", JUMP_CRISIS)
def test_jump_from_height_escalates(text):
    assert check_banned_intent(text)[0] is False, f"{text!r} refused at a crisis moment"
    assert check_emergency_keywords(text) is True, f"{text!r} did not escalate"


@pytest.mark.parametrize("text", JUMP_PLAY)
def test_jumping_play_does_not_escalate(text):
    assert check_emergency_keywords(text) is False, f"{text!r} falsely escalated"

# Same words, ordinary meaning: hyperbole, a religious wish, where to live,
# and talk about death itself.
COLLOQUIAL_NOT_EMERGENCY = [
    "ابني بيموّت نفسه من العياط",
    "بنتي عايزة تموت من الضحك",
    "بنتي عايزة تموت من الكسوف",
    "هموت من الضحك",
    "نفسي أموت شهيد",
    "نفسي اموت على الاسلام",
    "ابني مش عايز يعيش في الغربة",
    "بنتي مش عايزة تعيش مع ابوها بعد الطلاق",
    "ابني مش عايز يعيش لوحده",
    "ابني بيسأل عن موت جده",
    "ابني بيخاف من الموت",
    "ازاي اشرح لابني ان جده مات",
    "ابني نفسه يبقى دكتور",
    "I want to die laughing",
]


@pytest.mark.parametrize("text", COLLOQUIAL_CRISIS)
def test_colloquial_death_wish_escalates(text):
    assert check_banned_intent(text)[0] is False, f"{text!r} refused at a crisis moment"
    assert check_emergency_keywords(text) is True, f"{text!r} did not escalate"


@pytest.mark.parametrize("text", COLLOQUIAL_NOT_EMERGENCY)
def test_colloquial_death_words_without_a_wish_do_not_escalate(text):
    assert check_emergency_keywords(text) is False, f"{text!r} falsely escalated"


# --- Noun forms of self-harm (2026-10-23, round 2) ----------------------------
#
# «بيتكلم عن إيذاء نفسه» never escalated: only the verb («يؤذي نفسه») and the
# noun «إيذاء النفس» were keywords. The normalizer deletes hamza, so إيذاء is
# "ايذا" and أذية is "اذيه". The past verb («أذى نفسه») is NOT a keyword: it is
# how a play accident is told.

SELF_HARM_NOUN_CRISIS = [
    "ابني بيتكلم عن إيذاء نفسه",
    "بنتي بتتكلم عن أذية نفسها",
    "ابني يتحدث عن إيذاء نفسه",
    "ابني يتحدث عن ايذاء نفسه",
    "بنتي بتتكلم عن اذيه نفسها",
    "بنتي بتفكر في أذيّة نفسها",
    "ابني حاول إيذاء نفسه امبارح",
    "حاولت ايذاء نفسي",
    "الإصابة بأذى بنفسه",
    "ابني عنده ميل لـ أذى بنفسه",
    "بنتي بتقول عايزة اذي بنفسها",
    "بنتي بتأذي نفسها",
    "ابني بيأذي نفسه",
    "ابني بيؤذي نفسه",
    "إيذاء النفس عند المراهقين",
    "ابني بيتكلم عن إيذاء نفسه وهو بيلعب",
]

SELF_HARM_NOUN_NOT_EMERGENCY = [
    "ابني وقع وأذى نفسه وهو بيلعب",
    "ابني اتزحلق وأذى نفسه",
    "ابني ضرب إيذاء نفسه بالغلط",
    "ابني جرى وحصل إيذاء نفسه بدون قصد",
    "ابني بيأذي اخوه الصغير",
    "ازاي أعلم ابني ما يؤذيش زمايله",
    "بنتي بتقول الحياة جميلة",
    "ابني بيتكلم عن نفسه كتير",
    "إيذاء الاخرين وطريقة التعامل معه",
    "ابني زعلان من أذى زميله",
]


@pytest.mark.parametrize("text", SELF_HARM_NOUN_CRISIS)
def test_self_harm_noun_forms_escalate(text):
    assert check_banned_intent(text)[0] is False, f"{text!r} refused at a crisis moment"
    assert check_emergency_keywords(text) is True, f"{text!r} did not escalate"


@pytest.mark.parametrize("text", SELF_HARM_NOUN_NOT_EMERGENCY)
def test_accidents_and_harm_to_others_do_not_escalate(text):
    assert check_emergency_keywords(text) is False, f"{text!r} falsely escalated"


# --- Latin diacritics (2026-10-23, round 2) -----------------------------------
#
# `_NON_LETTER` kept only ASCII Latin, so every accented letter was deleted:
# "électrocuté" -> "lectrocut", "réveille" -> "rveille". French typed with
# accents (the normal way) never matched the unaccented keywords.

FR_ACCENTED_EMERGENCY = [
    "il ne se réveille pas",
    "mon enfant ne se réveille pas",
    "elle s'est électrocutée",
    "il s’est électrocuté",
    "il a avalé de l'eau de javel",
    "elle a avalé une pile",
    "mon fils s'étouffe avec un raisin",
    "il est inconscient depuis une minute",
    "Elle a perdu connaissance",
    "une hémorragie importante",
    "il est empoisonné",
    "elle est empoisonnée",
    "ma fille a bu de l’eau de javel",
    "IL NE SE RÉVEILLE PAS",
    "mon fils veut se suicider",
    "elle ne veut plus vivre",
    "mon ado a envie de mourir",
]

FR_ACCENTED_NOT_EMERGENCY = [
    "mon fils est très énergique le matin",
    "comment réveiller mon enfant doucement pour l'école",
    "il se réveille souvent la nuit",
    "mon enfant a des cauchemars et un sommeil agité",
    "à quel âge un bébé peut-il manger des œufs",
    "elle veut se tuer à la tâche",
    "mon fils est déçu après l'école",
    "quelle électricité statique pour les cheveux de ma fille",
    "il a envie de mourir de rire",
    "comment préparer un goûter équilibré pour un élève de 8 ans",
    "mon enfant est stressé avant l'examen",
]


@pytest.mark.parametrize("text", FR_ACCENTED_EMERGENCY)
def test_accented_french_emergency_escalates(text):
    assert check_emergency_keywords(text) is True, f"{text!r} did not escalate"


@pytest.mark.parametrize("text", FR_ACCENTED_NOT_EMERGENCY)
def test_accented_french_ordinary_questions_are_not_emergencies(text):
    assert check_emergency_keywords(text) is False, f"{text!r} falsely escalated"


def test_latin_fold_covers_ligatures_and_leaves_ascii_alone():
    from app.services.intent_guard import _normalize, _normalize_word

    assert _normalize_word("électrocuté") == "electrocute"
    assert _normalize_word("cœur") == "coeur"
    assert _normalize_word("Ça") == "ca"
    assert _normalize_word("garçon") == "garcon"
    assert _normalize_word("bébé") == "bebe"
    assert _normalize("Où est l’hôpital") == "ou est lhopital"
    assert _normalize("plain ascii") == "plain ascii"


def _legacy_normalize_word(word: str) -> str:
    """The normalizer exactly as it was before the Latin fold (origin/main)."""
    from app.services.intent_guard import _FRANCO, _NON_LETTER, _REPEATED, _TASHKEEL

    word = word.lower()
    word = _TASHKEEL.sub("", word)
    word = word.replace("\u0622", "\u0627").replace("\u0623", "\u0627").replace("\u0625", "\u0627").replace("\u0671", "\u0627")
    word = word.replace("\u0626", "\u064A").replace("\u0624", "\u0648")
    word = word.replace("\u0621", "")
    word = _REPEATED.sub(r"\1", word)
    word = word.translate(_FRANCO)
    return _NON_LETTER.sub("", word)


def _code_points():
    # Every BMP code point (minus surrogates) plus a spread of astral ones.
    yield from (cp for cp in range(0x10000) if not 0xD800 <= cp <= 0xDFFF)
    yield from range(0x10000, 0x110000, 251)


def test_normalizer_differs_from_the_legacy_one_only_on_latin_extended_letters():
    """The Latin fold must not change a single Arabic (or any other) result.

    Proved over the whole code-point space, not a corpus: `_normalize_word` and
    the pre-fold algorithm may disagree only on U+00C0-U+024F, U+1E00-U+1EFF
    and U+212B (ANGSTROM SIGN, which lowercases into the first block), and
    where they do the new result is ASCII. Needs no files, so it never skips.
    """
    from app.services.intent_guard import _normalize_word

    in_blocks = lambda cp: 0xC0 <= cp <= 0x24F or 0x1E00 <= cp <= 0x1EFF or cp == 0x212B
    for cp in _code_points():
        ch = chr(cp)
        # Glued to an Arabic letter or a Franco digit the word is not French:
        # the result must be the legacy one for every code point, no exceptions.
        for word in ("ع" + ch + "ع", "x" + ch + "3"):
            assert _normalize_word(word) == _legacy_normalize_word(word), f"U+{cp:04X} in {word!r}"
        new, old = _normalize_word(ch), _legacy_normalize_word(ch)
        if new != old:
            assert in_blocks(cp), f"U+{cp:04X} changed outside the Latin-extended blocks: {old!r} -> {new!r}"
            assert new.isascii(), f"U+{cp:04X} -> {new!r}"


def test_latin_fold_results_are_ascii_and_never_touch_arabic_words():
    from app.services.intent_guard import _normalize_word

    for cp in list(range(0xC0, 0x250)) + list(range(0x1E00, 0x1F00)) + [0x212B]:
        out = _normalize_word(chr(cp) + "ab")
        assert out.isascii(), f"U+{cp:04X} -> {out!r}"
    # Arabic text, with every hamza / alif / tashkeel / tatweel / digit form
    for w in ("إيذاء", "أذية", "طائر", "طارئ", "مسؤول", "القرآن", "صلاةٌ", "ﷲ",
              "الله", "يـأذي", "ءاخر", "٣٤٥", "؟", "،", "عايزة", "يتمنّى"):
        assert _normalize_word(w) == _legacy_normalize_word(w), w


def test_mixed_arabic_and_latin_extended_is_stripped_not_folded():
    """«ابنيé» used to become «ابنيe» once folded; Franco «é3» became «eع»."""
    from app.services.intent_guard import _normalize_word

    assert _normalize_word("ابنيé") == "ابني" == _legacy_normalize_word("ابنيé")
    assert _normalize_word("é3") == "ع" == _legacy_normalize_word("é3")
    assert _normalize_word("ععéعع") == _legacy_normalize_word("ععéعع")
    assert check_emergency_keywords("ابنيé بيؤذي نفسه") is True
    # French is still folded
    assert _normalize_word("réveille") == "reveille"


def test_normalize_calls_the_word_normalizer_once_per_word(monkeypatch):
    from app.services import intent_guard

    calls = []
    real = intent_guard._normalize_word
    monkeypatch.setattr(intent_guard, "_normalize_word", lambda w: calls.append(w) or real(w))
    assert intent_guard._normalize("ابني  بيؤذي ، نفسه") == "ابني بيوذي نفسه"
    assert len(calls) == 4


# --- Round 4: independent review ------------------------------------------------
#
# Every list below pairs crisis sentences (must escalate) with ordinary ones
# (must not). The crisis half is the point of the file; the ordinary half keeps
# the guard from crying wolf.

ROUND4_CRISIS = [
    # B1: a conjunction on «مش» must not hide the wish
    "ابني حزين ومش عايز يعيش",
    "بنتي بتعيط ومش عايزة تعيش",
    "ومش عاوز اعيش",
    "فمش عايزة تعيش",
    "ابني ومش عاوز اعيش في الدنيا",
    # M1: «ولا» is "or", not a negation
    "هو بيهزر ولا عايز يموت",
    "ابني ولا يريد أن يعيش",
    "my son says he doesnt want to live anymore",
    "she does not want to be alive anymore",
    "he doesnt want to live in this world",
    # M3: the idiom does not cover a crisis that goes on after it
    "بنتي بتقول نفسي أموت من الضحك اللي الناس بتضحكه عليا",
    "ابني بيقول عايز يموت من الكسوف بعد ما اتنمروا عليه",
    "بنتي بتقول هموت نفسي من العياط ومحدش حاسس بيا",
    "بنتي عايزة تموت من الجوع وبتمتنع عن الاكل بقالها اسبوع",
    "ابني بيقول عايز يموت من الخضة",
    "ابني بيقول مش عايز يعيش في الحياة دي",
    "بنتي مش عايزة تعيش في العالم ده",
    "ابني قال مش عايز اعيش في الكون",
    "mon fils ne veut plus vivre dans ce monde",
    "ma fille ne veut plus vivre en ce monde",
    "ابني بيقول هموت نفسي عشان اريحكم",
    # M4: «بال / وال» proclitics, Egyptian future stems
    "بنتي بتهدد بالانتحار",
    "هددني ابني بالانتحار",
    "بنتي بتفكر بالانتحار",
    "كلامه كله عن الموت والانتحار",
    "ابني قال هنتحر",
    "بنتي قالت هنهي حياتي",
    "ابني قال هخلص على نفسي",
    "ابني قال اذي نفسي",
    "ابني قال هأذي نفسي",
    "ابني قال هاذي نفسي",
    "ابني قال اوذي نفسي",
    "ابني قال أؤذي نفسي",
    # M5: English
    "my daughter is selfharming",
    "he does selfharm",
    "she is self harming again",
    "he self harms",
    "he wishes he were dead",
    "she wishes she were dead",
    "he said I wish I were dead",
    "he said he wants to end it all",
    "she would rather be dead",
    "my son doesnt want to be alive",
    "he says he does not want to live in this world",
    "she no longer wants to be alive",
    # M6: places and phrases
    "ابني حاول يقفز من الطابق الخامس",
    "بنتي بترمي نفسها من الكوبري",
    "ابني قال هرمي نفسي من الجسر",
    "ابني بيرمي نفسه من البرج",
    "ابني حاول يرمي نفسه في النيل",
    "بنتي رمت نفسها في البحر",
    "ابني حاول يرمي نفسه قدام القطر",
    "بنتي بترمي نفسها قدام المترو",
    "ابني حاول يرمي نفسه قدام العربية",
    "ابني بينط قدام القطر",
    "بنتي بتقول هرمي نفسي",
    "ابني قال هرمي بنفسي",
    "ابني قال ارمي نفسي",
    # m1: French
    "mon fils voulait mourir",
    "ma fille voulait se tuer",
    "il va se tuer",
    "ma fille veut se faire du mal",
    "elle a essayé de se tuer",
    "mon fils a des idées suicidaires",
    "il n'a plus envie de vivre",
    "mon fils ne veut pas vivre",
    "ma fille veut se pendre",
    "elle s'automutile",
    "il veut en finir avec la vie",
    # m4: «تمنّى الموت» outside a religious or ruling context
    "ابني يتمنى الموت",
    "بنتي بتقول عايزة تموت لنفسها",
    "ابني عايز يموت لانه تعبان",
    # m3: «بعد» and «حياته» are not places
    "ابني مش عايز يعيش بعد ما اتنمروا عليه",
    "ابني مش عايز يعيش حياته",
    # m5
    "الحياة ملهاش لازمة",
    "بنتي بتقول الحياة ملهاش لازمة من غير ما حد يسمعني",
]

ROUND4_NOT_EMERGENCY = [
    # B1: not about living
    "ومش عايز ياكل",
    "ومش مهم",
    "فمش عايز يذاكر",
    "ولا يهمني",
    # M1: negation
    "مش عايز اموت وبيخاف من الموت",
    "مش عايزة اموت",
    "ومش عايز اموت",
    "جدي مش عايز يموت وخايف",
    "he doesn't want to die",
    "he does not want to die",
    "she dont want to die",
    "il n'a pas envie de mourir",
    # M2: the tail typed with ى / ة / ه
    "مش عايز يعيش فى الغربة",
    "نفسي اموت علي الاسلام",
    "نفسي اموت مسلمه",
    "نفسي اموت شهيده",
    "نفسي اموت وانا ساجده",
    "نفسي اموت فى سبيل الله",
    "ابني بيموت نفسه فى العياط",
    # M3: the idiom alone
    "هموت من الضحك",
    "عايزة تموت من الكسوف",
    "ابني بيموّت نفسه من العياط",
    # M5: where, not whether
    "my son doesnt want to live with his father",
    "she dont want to live in the city",
    "he doesnt want to live far from us",
    "she doesnt want to live here",
    "he dont want to live alone",
    "he doesnt want to live abroad",
    # M6: play
    "ابني بيرمي نفسه على السرير",
    "ابني بينط في البحر",
    "ابني بينط قدام العربية",
    "ابني بيجري قدام القطر",
    # m1
    "il voulait mourir de rire",
    "elle va se tuer à la tâche",
    "il veut en finir avec la vie scolaire",
    "elle veut en finir avec la vie professionnelle",
    "il ne veut pas vivre chez sa mère",
    "ma fille ne veut pas vivre avec son père",
    # m2
    "ابني بيموت نفسه ضحك",
    "بنتي بتموت نفسها بالضحك",
    "ابني بيموت نفسه في المذاكرة",
    "ابني بيموت نفسه فى المذاكره",
    "ابوه بيموت نفسه في الشغل",
    "انا هموت نفسي شغل",
    "بنتي بتقتل نفسها في المذاكرة",
    "هموت نفسي من التعب",
    "عايزه تموت من الحر",
    "ابني هيموت نفسه من الغيظ",
    "بنتي عايزة تموت من الزهق",
    "بنتي عايزة تموت من الفرحة",
    # m3
    "ابني مش عايز يعيش بعيد عن امه",
    "ابني مش عايز يعيش قريب من حماته",
    "ابني مش عايز يعيش على نفقة ابوه",
    "ابني مش عايز يعيش غير مع امه",
    "بنتي مش عايزة تعيش بين اهل ابوها",
    "ابني مش عايز يعيش جنب جدته",
    "ابني مش عايز يعيش تحت سلطة عمه",
    # m4
    "ابني عايز يموت شهيد",
    "ابني عايز يموت شهيدا",
    "بنتي عايزة تموت شهيدة",
    "ابني يريد ان يموت شهيدا",
    "ابني يتمنى الموت شهيدا",
    "هل يجوز ان يتمنى الموت",
    "ما حكم من يتمنى الموت",
    "بنتي عايزة تموت للمدرسة",
    "بنتي عايزة تموت لحماتها",
    # m5
    "قد يتعرض طفلك على الإنترنت إلى أذى نفسي أو محتوى مخيف",
    "ابني تعرض لأذى نفسي بسبب التنمر عليه",
    "بدي موت من الضحك",
    "ودي اموت من الكسوف",
    "الحياة ملهاش لازمة من غير ولادي",
    "حياتي ملهاش لازمة من غير ابني",
    # ranked misses: ordinary neighbours
    "مبقاش عايز ياكل",
    "ما عادش عايز يعيش في الغربة",
    "ما ابي اموت",
    "ما بدو يموت",
    "بنتي تعبت من الحياة المدرسية",
    "ابني تعب من الحياة الجامعية",
    "ما ابي اعيش مع ابوي",
    "ما بدو يعيش مع امو",
    "بنتي بتجرح ايدها وهي بتقطع الخضار",
]

RANKED_MISSES = [
    # «لم يعد يريد العيش» in every register
    "ابني مبقاش عايز يعيش",
    "بنتي ما بقاش عايزة تعيش",
    "ابني مبقتش عايز اعيش",
    "بنتي ما عادش عايزة تعيش",
    "ابني معادش عايز يعيش",
    "ابني ما بقتش عايز اعيش في الدنيا",
    # passive wishes
    "ابني قال ياريتني مت",
    "بنتي كتبت يا ريتني ما اتولدت",
    "بنتي بتقول تعبت من الحياة",
    "ابني بيقول زهقت من الحياة",
    "بنتي قالت كرهت حياتي",
    "بنتي قالت الكل هيرتاح لو مت",
    "ابني قال مليش لازمة في الدنيا",
    # Gulf
    "ابني يقول ودي اموت",
    "بنتي تقول ابي اموت",
    "ابني قال ابغى اموت",
    "بنتي تقول ما ابي اعيش",
    "ابني قال ما ابغى اعيش",
    "ولدي يبي يموت",
    "بنتي تبي تموت",
    "ابني قال ودي انتحر",
    # Levantine
    "ابني قال بدي موت",
    "بنتي بدها تموت",
    "ابني بدو يموت",
    "ابني ما بدو يعيش",
    "بنتي قالت ما بدي عيش",
    "ابني بدي خلص حالي",
    "بنتي قالت بدي قتل حالي",
    "ابني قتل حالو",
    "بنتي قتل حالها",
    # methods
    "ابني قال اشنق نفسي",
    "بنتي قالت هشنق نفسي",
    "ابني بيقول يشنق نفسه",
    "بنتي قالت هغرق نفسي",
    "ابني قال هولع في نفسي",
    "ابني حاول يقطع شرايينه",
    "بنتي قطعت شراينها",
    "بنتي بتجرح ايدها",
    "بنتي بتقطع ايدها",
]


@pytest.mark.parametrize("text", ROUND4_CRISIS + RANKED_MISSES)
def test_round4_crisis_escalates(text):
    assert check_banned_intent(text)[0] is False, f"{text!r} refused at a crisis moment"
    assert check_emergency_keywords(text) is True, f"{text!r} did not escalate"


@pytest.mark.parametrize("text", ROUND4_NOT_EMERGENCY)
def test_round4_ordinary_does_not_escalate(text):
    assert check_emergency_keywords(text) is False, f"{text!r} falsely escalated"


def test_prevention_phrasing_still_escalates():
    """Judgment call (m6): "امنع ابني من إيذاء نفسه" is NOT excluded.

    A parent asking how to stop a child from hurting himself is, far more often
    than not, a parent whose child is at risk; no pre-exclusion can tell that
    from toddler-proofing without swallowing «امنع بنتي من إيذاء نفسها، اتأذت
    امبارح». It keeps escalating, as «يؤذي نفسه» always did.
    """
    for text in (
        "ازاي امنع ابني من ايذاء نفسه",
        "امنع بنتي من إيذاء نفسها، هي بتجرح نفسها",
        "امنع بنتي من إيذاء نفسها، اتأذت امبارح",
    ):
        assert check_emergency_keywords(text) is True, text


# --- Tooling around the matcher ---------------------------------------------------

def test_spelling_variants_cover_final_letters_of_every_word():
    from app.services.intent_guard import _spelling_variants

    assert _spelling_variants("عايزة تموت") == {
        "عايزة تموت", "عايزه تموت",
    }
    assert _spelling_variants("يتمنى الموت") == {
        "يتمنى الموت", "يتمني الموت",
    }
    assert _spelling_variants("في سبيل الله") == {
        "في سبيل الله", "فى سبيل الله", "في سبيل اللة", "فى سبيل اللة",
    }
    # words that do not end in a swappable letter are left alone
    assert _spelling_variants("مش عايز") == {"مش عايز"}
    assert _spelling_variants("sleep apnea") == {"sleep apnea"}


def test_exclusion_keys_and_tails_are_expanded_over_spellings():
    from app.services.intent_guard import (
        _EMERGENCY_EXCLUSIONS,
        _EMERGENCY_EXCLUSIONS_EXPANDED,
        _EMERGENCY_EXCLUSIONS_NORM,
    )

    # the declared dict is the compact one; the expanded one holds the spellings
    assert ("عايزة", "تموت") in _EMERGENCY_EXCLUSIONS
    assert ("عايزه", "تموت") not in _EMERGENCY_EXCLUSIONS
    assert ("عايزه", "تموت") in _EMERGENCY_EXCLUSIONS_EXPANDED
    assert ("شهيده",) in _EMERGENCY_EXCLUSIONS_EXPANDED[("نفسي", "اموت")]
    assert ("فى", "سبيل") in _EMERGENCY_EXCLUSIONS_EXPANDED[("نفسي", "اموت")]
    # normalized form: the tails the matcher actually reads
    tails = _EMERGENCY_EXCLUSIONS_NORM[("نفسي", "اموت")]
    for tail in (("شهيده",), ("مسلمه",), ("وانا", "ساجده"), ("فى", "سبيل"), ("علي", "الاسلام")):
        assert tail in tails, tail
    where = _EMERGENCY_EXCLUSIONS_NORM[("مش", "عايزه", "يعيش")] if ("مش", "عايزه", "يعيش") in _EMERGENCY_EXCLUSIONS_NORM else _EMERGENCY_EXCLUSIONS_NORM[("مش", "عايز", "يعيش")]
    assert ("فى",) in where and ("في",) in where
    # no key ends up with an empty tail or a duplicate
    for key, tails in _EMERGENCY_EXCLUSIONS_NORM.items():
        assert all(tails), key
        assert len(tails) == len(set(tails)), key


def test_ordinary_hyperbole_tails_do_not_cover_hunger_or_fright():
    from app.services.intent_guard import _HYPERBOLE

    assert ("من", "الجوع") not in _HYPERBOLE
    assert ("من", "الخضة") not in _HYPERBOLE
    assert ("من", "الضحك") in _HYPERBOLE and ("من", "الكسوف") in _HYPERBOLE


def _reference_check(text):
    """The matcher as it was before the first-word lookup: try every needle."""
    from app.services import intent_guard as g

    tokens = g._normalize(text).split()
    for needle in g._EMERGENCY_KEYWORDS_NORM:
        for start in g._sequence_positions(tokens, needle):
            if not g._is_excluded(tokens, needle, start):
                return True
    return False


def _differential_texts():
    import random

    from app.services import intent_guard as g

    rng = random.Random(166)
    needles = sorted(g._EMERGENCY_KEYWORDS_NORM)
    excluded_keys = sorted(g._EMERGENCY_EXCLUSIONS_NORM)
    negations = sorted(g._NEGATIONS)
    fillers = ["", "ابني", "بنتي بتقول", "he said", "ma fille dit", "و", "يا ماما", "امبارح"]
    tails_extra = ["", "وبيخاف", "ومحدش حاسس بيا", "بعد ما اتنمروا عليه", "and cried", "ce soir"]
    texts = []
    for _ in range(300):
        pool = excluded_keys if rng.random() < 0.5 else needles
        needle = list(rng.choice(pool))
        # a proclitic (or a conjunction) on the first word
        if rng.random() < 0.6:
            needle[0] = rng.choice(g._PROCLITICS + ("", "و", "ف")) + needle[0]
        words = list(needle)
        tails = g._EMERGENCY_EXCLUSIONS_NORM.get(tuple(rng.choice(pool)), ()) if rng.random() < 0.3 else ()
        if rng.random() < 0.7:
            key = tuple(g._normalize_word(w) for w in needle)
            for k in (key, ):
                tails = g._EMERGENCY_EXCLUSIONS_NORM.get(k, tails)
        if tails and rng.random() < 0.8:
            words += list(rng.choice(tails))
        if rng.random() < 0.25:
            words = [rng.choice(negations)] + words
        texts.append(" ".join([rng.choice(fillers)] + words + [rng.choice(tails_extra)]))
    return texts


def test_first_word_lookup_agrees_with_the_exhaustive_scan():
    """`check_emergency_keywords` looks needles up by their first word. It must
    return exactly what trying every needle returns — across proclitics,
    fillers, exclusion tails, negations and distress markers."""
    texts = _differential_texts()
    assert len(texts) >= 300
    results = [check_emergency_keywords(t) for t in texts]
    assert results == [_reference_check(t) for t in texts]
    # the sample is only worth anything if it exercises both outcomes
    assert 30 < sum(results) < len(results) - 30


def test_two_letter_needles_take_only_a_conjunction_on_the_negation_words():
    from app.services.intent_guard import _token_matches

    for token, needle in (("ومش", "مش"), ("فمش", "مش"), ("ولا", "لا"), ("وما", "ما")):
        assert _token_matches(token, needle), (token, needle)
    # everything else short stays exact: «بسم» must never be «سم»
    for token, needle in (
        ("بمش", "مش"), ("المش", "مش"), ("وسم", "سم"), ("بسم", "سم"),
        ("بالسم", "سم"), ("والسم", "سم"), ("ولاا", "لا"),
    ):
        assert not _token_matches(token, needle), (token, needle)
    # the new «بال / وال / فال / وبال» proclitics work on longer needles
    for prefix in ("بال", "وال", "فال", "وبال", "ال"):
        assert _token_matches(prefix + "انتحار", "انتحار"), prefix


def test_every_keyword_is_reachable_on_its_own():
    """A keyword that can never fire (a typo, a spelling the normalizer rewrites)
    is a silent hole. Each normalized keyword, said alone, must escalate."""
    from app.services.intent_guard import _EMERGENCY_KEYWORDS_NORM

    assert len(_EMERGENCY_KEYWORDS_NORM) > 3000
    dead = [" ".join(k) for k in _EMERGENCY_KEYWORDS_NORM if not check_emergency_keywords(" ".join(k))]
    assert dead == []
