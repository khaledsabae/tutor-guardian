"""The answer comes back in the language the parent wrote in.

Measured, not assumed: 40% of the people who use the assistant are on
non-Arabic devices — 881 English and 353 French against 1,940 Arabic over 28
days on GA4 — and 331 of the assistant's messages in that window came from
English-device users. Asked in English, production answered in Arabic. Probed
on 2026-08-21 against the live container: "My 8 year old son refuses to pray.
What should I do?" came back as «أولاً، لا تقلقي فهذا السلوك طبيعي جداً…».

Nothing was broken. The system prompt opens with «أنت مساعد تربوي ذكي للأهل
العرب المسلمين» and never mentions the language of the reply, so an Arabic
prompt answered in Arabic — exactly as written, and wrong for two users in
five.

Retrieval had already been fixed for this: `detect_query_language` picks
sources in the language of the question. Only the generation step was still
answering in the language of its own instructions.
"""
import pytest

from app.services.llm_service import _compose_system_prompt

_EN = "My 8 year old son refuses to pray. What should I do?"
_AR = "ابني عمره ثماني سنوات ويرفض الصلاة، فماذا أفعل معه؟"
_FR = "Mon fils de huit ans refuse de prier, que dois-je faire?"

_DOMAINS = ["islamic_parenting", "fiqh", "aqeedah", "medical", "tarbiyah"]


@pytest.mark.parametrize("domain", _DOMAINS)
def test_a_non_arabic_question_gets_the_language_directive(domain):
    prompt = _compose_system_prompt(domain, _EN)
    assert prompt.startswith("🔴 LANGUAGE"), (
        "the rule has to lead: the local 3B follows the head of a prompt far "
        "more reliably than its tail, and several hundred words of Arabic "
        "follow this line"
    )


@pytest.mark.parametrize("domain", _DOMAINS)
def test_an_arabic_question_is_left_alone(domain):
    assert not _compose_system_prompt(domain, _AR).startswith("🔴 LANGUAGE")


def test_french_is_covered_without_being_named():
    """Script detection cannot tell French from English, so the directive names
    no language — it says "the language they used", which the model can see and
    this code cannot. A French parent must not be answered in English any more
    than in Arabic."""
    prompt = _compose_system_prompt("islamic_parenting", _FR)
    assert prompt.startswith("🔴 LANGUAGE")
    assert "same language they used" in prompt
    assert "in English" not in prompt.split("Two exceptions")[0]


def test_the_rule_is_stated_in_arabic_too():
    """An Arabic system prompt that never mentions language is itself an
    instruction to answer in Arabic. The rule belongs in both languages: the
    English block can be absent (Arabic question, short question) and the
    contract must still hold."""
    for question in (_AR, "ok", ""):
        assert "أجب بلغة الوالد نفسها" in _compose_system_prompt("fiqh", question)


@pytest.mark.parametrize("question", [_EN, _FR])
def test_scripture_is_not_translated_into_the_answer(question):
    """The one thing answering in English must not sweep along with it.

    A model told "write everything in English" will render an ayah in English
    and leave the reader with no way to know they are not reading the Qur'an.
    Both exceptions are carried in the same block as the instruction they
    qualify, so no prompt can arrive with one and not the other.
    """
    prompt = _compose_system_prompt("aqeedah", question)
    head = prompt.split("\n\n")[0]
    assert "Qur'an is quoted in Arabic script" in head
    assert "explanation of the meaning" in head
    assert "Hadith wording is quoted in Arabic" in head
    assert "never as the Qur'an itself" in head


def test_the_arabic_rule_carries_the_same_exception():
    prompt = _compose_system_prompt("aqeedah", _AR)
    assert "ويبقى القرآن مقتبساً" in prompt
    assert "بيان للمعنى" in prompt


@pytest.mark.parametrize("domain", _DOMAINS)
def test_the_domain_rules_survive_the_directive(domain):
    """The language block is prepended, not substituted. Everything the prompt
    said before — no corporal punishment, sharia takes precedence, address the
    parent directly — has to still be in there."""
    prompt = _compose_system_prompt(domain, _EN)
    assert "لا تنصح بالضرب أو العقاب البدني" in prompt
    if domain in {"fiqh", "islamic_parenting", "aqeedah"}:
        assert "يُقدَّم الحكم الشرعي دون استثناء" in prompt
    else:
        assert "إذا تعارضت أي معلومة مع الثوابت الإسلامية" in prompt
