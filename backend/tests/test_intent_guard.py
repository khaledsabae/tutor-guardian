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
