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
