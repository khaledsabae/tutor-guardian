"""Short Arabic keyword regressions: lexical routing only, no provider calls."""
import json
from pathlib import Path

import pytest

from app.services import domain_classifier as classifier

ROOT = Path(__file__).resolve().parents[2]


def golden_question(ident):
    return next(json.loads(line)["question"] for line in
                (ROOT / "ops/eval/golden_set.jsonl").read_text().splitlines()
                if json.loads(line)["id"] == ident)


@pytest.mark.parametrize("ident", ["g-011", "g-012"])
def test_golden_embedded_keywords_defer_to_classifier(ident, monkeypatch):
    question = golden_question(ident)
    assert classifier._keyword_fast_path(question) is None
    seen = []
    monkeypatch.setattr(classifier, "_call_llm",
                        lambda text: seen.append(text) or ["fiqh"])
    classifier._classify_cached.cache_clear()
    assert classifier.classify_domains(question) == ["fiqh"]
    assert seen == [question]
    classifier._classify_cached.cache_clear()


@pytest.mark.parametrize("question", [
    "بعض الأطفال مختلفون", "ماذا أقرأ لعبدالله علوان؟",
    "هل يتعلم من بعضهم؟", "ماذا تقترح لعبدالرحمن؟",
    "بَعْضُ النصائح مفيدة", "ماذا أقرأ لِعَبْدِالله؟",
])
def test_embedded_bite_play_tokens_do_not_invent_a_domain(question):
    assert classifier._keyword_fast_path(question) is None
    assert classifier.fallback_domains(question) == list(classifier.UNCERTAIN_DOMAINS)


@pytest.mark.parametrize("form", [
    "عض", "العض", "بالعض", "للعض", "وعضني", "يعض", "تعضني",
    "بيعضني", "بتعضه", "عضني", "عضّني", "يَعُضُّني", "وعَضَّني",
])
def test_real_biting_forms_remain_medical(form):
    assert "medical" in classifier._keyword_fast_path(f"طفلي {form} ماذا أفعل؟")


@pytest.mark.parametrize("form", [
    "لعب", "اللعب", "باللعب", "للعب", "ولعبه", "يلعب", "تلعب",
    "بيلعب", "بتلعب", "بلعب", "هيلعب", "وبيلعب", "يَلْعَبُ",
])
def test_real_playing_forms_remain_development(form):
    assert "development" in classifier._keyword_fast_path(f"طفلي {form} ماذا أفعل؟")


@pytest.mark.parametrize("form", ["السمع", "بالسمع", "يسمع", "بيسمع", "يَسْمَعُ"])
def test_real_hearing_forms_remain_development(form):
    assert "development" in classifier._keyword_fast_path(f"طفلي {form} ماذا أفعل؟")


@pytest.mark.parametrize("form,domain", [
    ("يعضونني", "medical"),
    ("يعضونه", "medical"),
    ("يعضونها", "medical"),
    ("تعضونني", "medical"),
    ("ويعضونني", "medical"),
    ("فَيَعُضُّونَني", "medical"),
    ("بيلعبوا", "development"),
    ("بيلعبوه", "development"),
    ("بيلعبوها", "development"),
    ("بتلعبوا", "development"),
    ("وبيلعبوا", "development"),
    ("فَبِيَلْعَبُوا", "development"),
    ("بيسمعوا", "development"),
    ("بيسمعوني", "development"),
    ("بيسمعوه", "development"),
    ("بيسمعوها", "development"),
    ("بتسمعوا", "development"),
    ("وبيسمعوا", "development"),
    ("فَبِيَسْمَعُوا", "development"),
    ("يسمعونني", "development"),
])
def test_plural_verbs_and_object_suffixes_keep_their_domain(form, domain):
    assert domain in (classifier._keyword_fast_path(f"أطفالي {form}") or [])


@pytest.mark.parametrize("question", [
    "ماذا تنصح لبعضهم؟", "فبعضهن مختلفات", "ماذا أقرأ ولعبدالله علوان؟",
    "ماذا أقرأ لِعَبْدِالله علوان؟", "فسمعت عن عبدالله علوان",
    "وسَمِعْتُ عن عبدالله علوان",
])
def test_plural_expansion_does_not_restore_embedded_roots_or_adult_reports(question):
    assert classifier._keyword_fast_path(question) is None


@pytest.mark.parametrize("question", [
    "بنتي ما سمعت الجرس لما رن جنبها",
    "طفلتي ما سمعته لما رن الجرس جنبها",
    "ابنتي ما سمعتها لما رنت الصفارة جنبها",
    "بِنْتِي ما سَمِعَتْ الجَرَسَ لما رن جنبها",
    "وبنتي هي ما سمعت صوت الباب",
    "ابنتنا سمعت ندائي مرة فقط",
    "بنتي سمعتها تقول إنها لا تلتقط أي صوت",
    "أنا قلقة لأن بنتي ما سمعت الجرس",
    "ناديتها، بنتي هي ما سمعت صوت الباب",
])
def test_child_subject_past_hearing_keeps_development(question):
    assert "development" in (classifier._keyword_fast_path(question) or [])


def test_child_hearing_remains_additive_beside_parent_anxiety():
    assert classifier._keyword_fast_path(
        "بنتي ما سمعت الجرس لما رن جنبها وأنا قلقة"
    ) == ["medical", "development"]


@pytest.mark.parametrize("question", [
    "سمعت عن عبدالله علوان من صديقي",
    "سمعته يحكي عن عبدالله علوان",
    "سمعتها تحكي عن عبدالله علوان",
    "سَمِعْتُ عن عبدالله علوان",
    "أنا ما سمعت الجرس",
    "زوجتي ما سمعت الجرس",
    "هي ما سمعت الجرس",
    "بنتي أنا ما سمعت الجرس جنبها",
    "بنتي سمعت عن عبدالله علوان",
    "بنتي سمعتها تحكي عن عبدالله علوان",
    "بنتي ما سمعته عن عبدالله علوان",
    "بنتي سمعت عن الجرس الجديد",
    "أم بنتي ما سمعت الجرس",
    "ابني أنا ما سمعته لما رن الجرس",
])
def test_adult_or_reported_topic_is_not_child_hearing(question):
    assert "development" not in (classifier._keyword_fast_path(question) or [])


_ADULT_REPORTED_HEARING = [
    "سمعنا عن عبدالله علوان",
    "وسَمِعْنَا عن عبدالله علوان من صديقي",
    "زوجي سمعه عن عبدالله علوان",
    "هل سمعك أحد عن الكتاب",
    "سمعها في الإذاعة",
    "زوجي سمع عن عبدالله علوان",
    "سمعنا كثيرًا عن هذا الكتاب",
    "سمعنا من الشيخ في المحاضرة",
    "أبي سمعهم في الراديو",
    "سمعنا أن هذا الكتاب مفيد",
]


@pytest.mark.parametrize("question", _ADULT_REPORTED_HEARING)
def test_adult_reported_hearing_suffix_forms_are_not_development(question):
    assert "development" not in (classifier._keyword_fast_path(question) or [])


@pytest.mark.parametrize("question", _ADULT_REPORTED_HEARING)
def test_adult_reported_hearing_beside_app_help_stays_app_help(question):
    assert classifier._keyword_fast_path(f"{question}، كيف أحذف حسابي؟") == ["app_help"]


@pytest.mark.parametrize("question", [
    "ابني ما بيسمعنا لما نناديه",
    "بنتي ما سمعتها تستجيب لاسمها",
    "ابني لا يسمعه حين أكلمه من الخلف",
    "طفلي عمره سنة ولا يلتفت لما نسمّعه صوت",
    "ابني عنده ضعف في سمعه من الولادة",
    "طفلي سمعه ضعيف عن باقي إخوته",
    "بنتي سمعها ضعيف في الأذن اليسرى",
    "ابني لا يسمع، سمعنا عن طبيب ممتاز",
    "ابني سمعه إن شاء الله سليم؟",
    "طفلي سمعه عن بعد ضعيف",
])
def test_child_hearing_with_suffix_forms_keeps_development(question):
    assert "development" in (classifier._keyword_fast_path(question) or [])


def test_explicit_fiqh_remains_additive_to_real_biting():
    domains = classifier._keyword_fast_path("طفلي يعضني وقت الصلاة")
    assert "fiqh" in domains and "medical" in domains


def test_educational_games_still_route_to_development():
    assert "development" in classifier._keyword_fast_path("أريد ألعاب تعليمية لابنتي")


def test_ambiguous_golden_keeps_uncertain_fallback_when_model_unavailable(monkeypatch):
    question = golden_question("g-012")
    monkeypatch.setattr(classifier, "_call_llm", lambda _: None)
    classifier._classify_cached.cache_clear()
    assert classifier.classify_domains(question) == list(classifier.UNCERTAIN_DOMAINS)
    classifier._classify_cached.cache_clear()


# ── P2: contextual child hearing beside a strong app-help signal ────────────
# The contextual hearing check ran after the keyword rules, so it appended
# development AFTER app_help. A worried parent who also asks about the app must
# keep the parenting domain as the label (domains[0]); app_help stays searched.

@pytest.mark.parametrize("question", [
    "بنتي ما سمعت الجرس، كيف أحذف حسابي؟",
    "بِنْتِي ما سَمِعَتْ الجَرَسَ، كيف أحذف حسابي؟",
    "ابنتي ما سمعته لما رن الجرس جنبها، احذف حسابي",
    "بنتي سمعتها تقول إنها لا تلتقط أي صوت، كيف أخرج من وضع الطفل؟",
    "أولادي ما بيسمعوا الجرس، كيف أحذف حسابي؟",
])
def test_child_hearing_outranks_strong_app_help(question):
    assert classifier._keyword_fast_path(question) == ["development", "app_help"]


def test_child_hearing_p2_label_is_parenting_first(monkeypatch):
    question = "بنتي ما سمعت الجرس، كيف أحذف حسابي؟"
    monkeypatch.setattr(classifier, "_call_llm", lambda _: pytest.fail("LLM called"))
    classifier._classify_cached.cache_clear()
    assert classifier.classify_domains(question) == ["development", "app_help"]
    assert classifier.classify_single_domain(question) == "development"
    classifier._classify_cached.cache_clear()


@pytest.mark.parametrize("question", ["كيف أحذف حسابي؟", "كيف أخرج من وضع الطفل؟"])
def test_standalone_app_help_stays_app_help_only(question):
    assert classifier._keyword_fast_path(question) == ["app_help"]


@pytest.mark.parametrize("question,expected", [
    ("بنتي ما سمعت الجرس وعندها حرارة وألم في أذنها، هل أذهب للطبيب؟ وكيف أحذف حسابي؟",
     ["medical", "development", "app_help"]),
    ("بنتي ما سمعت الجرس وقت الصلاة، كيف أحذف حسابي؟",
     ["fiqh", "development", "app_help"]),
])
def test_medical_and_fiqh_keep_priority_over_child_hearing(question, expected):
    assert classifier._keyword_fast_path(question) == expected


def test_emergency_phrase_with_child_hearing_still_takes_the_emergency_lane():
    from app.services.intent_guard import check_emergency_keywords
    question = "بنتي ما سمعت الجرس وعندها تشنج، كيف أحذف حسابي؟"
    # The router checks emergencies before it ever classifies a domain.
    assert check_emergency_keywords(question) is True
    assert classifier._keyword_fast_path(question)[0] != "app_help"


def test_adult_hearing_report_beside_app_help_is_not_child_hearing():
    assert classifier._keyword_fast_path(
        "سمعت عن عبدالله علوان، كيف أحذف حسابي؟"
    ) == ["app_help"]


# ── Review oct7: dialect negation/suffix forms the explicit lists dropped ───
# The base classifier matched bare «عض/لعب/سمع» anywhere, so these routed; the
# explicit forms must keep them without bringing «بعض/لعبدالله/سمعة» back.

@pytest.mark.parametrize("question,domain", [
    ("ابني مايسمع زين لما أناديه", "development"),
    ("ابني مابيسمعش لما بنده عليه", "development"),
    ("عيالي ما يسمعوا الجرس", "development"),
    ("عيالي ما يسمعو الجرس", "development"),
    ("ابني ما بيلعبش مع الأطفال التانيين", "development"),
    ("ولادي مابيلعبوش", "development"),
    ("ابني مايلعب مع أحد", "development"),
    ("عيالي مايلعبون", "development"),
    ("ابني ما يلعبو مع حد", "development"),
    ("ابني مايعض إلا أخوه", "medical"),
    ("ولادي بيعضوا بعض", "medical"),
    ("ومش بيسمعلنا خالص", "development"),
    ("ابني ميسمعش لما أناديه", "development"),
    ("بنتي مبتلعبش مع حد", "development"),
])
def test_dialect_negation_and_suffix_forms_keep_their_domain(question, domain):
    assert domain in (classifier._keyword_fast_path(question) or [])


@pytest.mark.parametrize("question,domain", [
    ("ابني يريد أن يكون عضو في النادي", "medical"),
    ("ابني يريد أن يكون عضوًا في النادي", "medical"),
    ("ابني يريد أن يكون عضواً في النادي", "medical"),
    ("ابني عنده عضلات قوية", "medical"),
    ("هل يتعلمون من بعض؟", "medical"),
    ("الأشياء داخل بعض", "medical"),
    ("يقوم بعض الأطفال بالرسم", "medical"),
    ("ابني يحب بعضهم", "medical"),
    ("هل أقرأ لعبدالله علوان؟", "development"),
    ("سمعة العائلة مهمة", "development"),
    ("ابني يهتم بسمعته", "development"),
    ("سمعته بين الناس سيئة", "development"),
    ("العبادة عند الأطفال", "development"),
    ("ابني يحب الملعب الكبير", "development"),
])
def test_broadened_forms_keep_embedded_and_lookalike_exclusions(question, domain):
    assert domain not in (classifier._keyword_fast_path(question) or [])


@pytest.mark.parametrize("question", [
    "طفلي يقوم بعض يده وجرح نفسه",
    "طفلي عمره سنتين يعاني من عصبية شديدة ويقوم بعض يده وجرح نفسه عندما ترفض أمه طلبه.",
    "بنتي بتقوم بعض صوابعها لما تتعصب",
    "ابني يقوم بعض نفسه",
])
def test_self_biting_is_medical(question):
    assert "medical" in (classifier._keyword_fast_path(question) or [])


@pytest.mark.parametrize("question", [
    "ابني عنده ضعف سمعي",
    "ابنتي تعاني من إعاقة سمعية",
    "هل الفحص السمعي ضروري للمولود؟",
    "متى نجري فحص القدرة السمعية؟",
    "طفلي يحتاج سماعة أذن",
    "بنتي تلبس سماعات من سنة",
])
def test_hearing_adjectives_and_devices_are_development(question):
    assert "development" in (classifier._keyword_fast_path(question) or [])


@pytest.mark.parametrize("question", [
    "نسمع عن التربية الإيجابية",
    "نسمع كثيرًا عن التربية الإيجابية",
    "بنسمع عن التنمر كتير",
    "تسمع عن طريقة مونتيسوري؟",
    "بتسمع عن طريقة مونتيسوري؟",
    "سمعنا على اليوتيوب عن العناد",
    "سمعنا من الدكتور أن هذه مرحلة",
    "سمعنا من الطبيب أن هذه مرحلة",
    "سمعنا من الأستاذ أن هذه مرحلة",
    "سمعنا من المعلم أن هذه مرحلة",
])
def test_present_and_new_channel_reported_hearing_is_not_development(question):
    assert "development" not in (classifier._keyword_fast_path(question) or [])


@pytest.mark.parametrize("question", [
    "ابني ما بيسمع عن بعد",
    "بنتي تسمع عن قرب فقط",
    "بنتي تسمع عن طريق الأذن اليسرى فقط",
    "هل ضعف سمعه أن يكون من الالتهاب؟",
])
def test_child_hearing_with_reported_lookalikes_keeps_development(question):
    assert "development" in (classifier._keyword_fast_path(question) or [])


@pytest.mark.parametrize("question", ["عضة الطفل لأمه", "عضته تركت أثرًا على يد أخيه"])
def test_bite_noun_is_medical(question):
    assert "medical" in (classifier._keyword_fast_path(question) or [])


@pytest.mark.parametrize("question,domain", [
    ("ابني یسمع بصعوبة", "development"),   # Persian yeh U+06CC
    ("طفلي یلعب وحده", "development"),
    ("ابني يکذب كثيرًا", "fiqh"),          # Persian keheh U+06A9
])
def test_persian_keyboard_letters_are_normalised(question, domain):
    assert domain in (classifier._keyword_fast_path(question) or [])


@pytest.mark.parametrize("question", [
    "ابني مابيسمعش، كيف أحذف حسابي؟",
    "عيالي ما يسمعو الجرس، كيف أحذف حسابي؟",
])
def test_dialect_child_hearing_outranks_strong_app_help(question):
    assert classifier._keyword_fast_path(question) == ["development", "app_help"]


@pytest.mark.parametrize("question", [
    "سمع " * 12500, "مابيسمعش " * 5000, "ما" * 25000, "بيعضوا " * 7000,
    "نسمع" + " كثير" * 10000, "سمعنا" + " مرة" * 12500 + " x",
    "بعض " * 12500, "ي" * 50000,
])
def test_keyword_rules_stay_linear_on_50k_inputs(question):
    import time
    start = time.perf_counter()
    classifier._keyword_fast_path(question)
    assert time.perf_counter() - start < 1.0
