"""The glossary guard is a programmatic constraint, not a prompt instruction.

It exists because 34 real term injections shipped across four consecutive
"fix" passes on 2026-08-11 — رحمة rendered as *rifq*, أمان as *amanah* — each
pass correcting the one before it and adding its own. A model asked politely
not to do this does it anyway; a substring check does not.

Both directions matter equally. A guard that misses an injection lets a
religious category change slip through. A guard that fires on correct text gets
switched off, and switching it off brings all 34 back.
"""
import importlib.util
import sys
from pathlib import Path

import pytest

_TOOL = (Path(__file__).resolve().parents[2]
         / "ops" / "tools" / "translate_curriculum.py")


@pytest.fixture(scope="module")
def tc():
    spec = importlib.util.spec_from_file_location("translate_curriculum", _TOOL)
    module = importlib.util.module_from_spec(spec)
    argv, sys.argv = sys.argv, [sys.argv[0]]
    try:
        spec.loader.exec_module(module)
    finally:
        sys.argv = argv
    return module


# ── Must fire: the injections that actually shipped ──────────────────────

@pytest.mark.parametrize("arabic,english,term", [
    ("عامل طفلك برحمة", "Treat your child with rifq", "rifq"),
    ("امنح طفلك أماناً في بيته", "Give your child amanah at home", "amanah"),
    ("تحدث معه بلطف", "Speak to him with rifq", "rifq"),
    ("اعطه نصيحة", "Give him tarbiyah", "tarbiyah"),
])
def test_injection_is_rejected(tc, arabic, english, term):
    issues = tc._validate_glossary({"text": arabic}, {"text": english})
    assert issues, f"{term!r} injected with no Arabic root and was not caught"
    assert term in issues[0]


# ── Must not fire: correct usage, and near-misses ────────────────────────

@pytest.mark.parametrize("arabic,english", [
    ("عامل طفلك برفق", "Treat your child with rifq"),
    ("علّمه الأمانة", "Teach him amanah"),
    ("التربية مسؤولية", "Tarbiyah is a responsibility"),
    ("الحياء من الإيمان", "Haya is part of iman"),
])
def test_correct_usage_passes(tc, arabic, english):
    assert tc._validate_glossary({"text": arabic}, {"text": english}) == []


def test_haya_does_not_match_inside_al_hayah(tc):
    """The false positive that rejected a correct translation twice.

    «الحياة» (life) transliterates to *al-Hayah*, which contains the letters of
    *haya* (modesty, from «حياء»). A substring check flagged
    lesson_10-12_islamic_parenting_identity_02 — whose Arabic title is
    «القرآن: دستور الحياة وبوصلة المراهق» — as an injection, so the fixer's
    output was thrown away at the gate on two separate runs.
    """
    issues = tc._validate_glossary(
        {"title": "القرآن: دستور الحياة وبوصلة المراهق"},
        {"title": "Al-Qur'an: Dustur al-Hayah wa Busulah al-Murahiqa"},
    )
    assert issues == [], f"false positive on al-Hayah: {issues}"


@pytest.mark.parametrize("english", [
    "The seerahs of the companions",   # plural suffix
    "a rifq-first approach",           # hyphenated
    "(rifq)",                          # parenthesised gloss
])
def test_word_boundaries_still_catch_affixed_forms(tc, english):
    """Boundaries must not become an escape hatch: an injected term is still an
    injection when it is pluralised, hyphenated or bracketed."""
    issues = tc._validate_glossary({"text": "كلام لا جذر فيه"}, {"text": english})
    assert issues, f"boundary check let {english!r} through"


def test_multiword_glossary_terms_are_matched(tc):
    issues = tc._validate_glossary(
        {"text": "كلام عام بلا جذر"},
        {"text": "Practise birr al-walidayn daily"},
    )
    assert issues and "birr al-walidayn" in issues[0]


def test_every_glossary_term_has_roots(tc):
    """A term with no root entry can never be rejected — it would be a silent
    hole in the guard rather than a permitted term."""
    missing = set(tc.GLOSSARY.values()) - set(tc.GLOSSARY_ROOTS)
    assert not missing, f"glossary terms with no root list: {sorted(missing)}"
