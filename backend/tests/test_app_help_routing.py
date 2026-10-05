"""App-help questions reach the app-help units — and parenting questions never do.

Before 2026-10-05 nothing in the knowledge base described the app itself, and a
question like «كيف أحذف حسابي؟» went to the model classifier, came back
"general", and was answered with no retrieval at all: the model was left to
guess at menus. Twelve `app_help` units now describe the app as it ships, and
one keyword rule routes app questions to them.

The rule is the risky half. «التطبيق العملي» is how parents say "putting advice
into practice", «وضع الطفل» is also "the child's situation", and «نصيحة اليوم»
opens 28% of all questions — parenting questions about a tip. A rule that
caught those would answer a parenting question from the app manual. So the
negative side is asserted over every parenting-question corpus in the repo,
not only over a hand-picked list.

Only strong signals decide alone (names only the app uses, child mode with an
enter/exit verb or a PIN, deleting «حسابي» with no other platform named).
«التطبيق» next to an app action is weak — «بعد التطبيق لمدة أسبوع…» is a
parenting question — so the keywords hand it to the model classifier: a
parenting domain from the model is kept, and when the model finds none
(«general», nothing, or no answer) the question goes to app_help. Beside a
parenting domain the keywords found, the weak signal adds app_help to the search.
"""
from __future__ import annotations

import asyncio
import json
import threading
import time
from pathlib import Path

import pytest

import app.services.domain_classifier as dc
from app.core.taxonomy import CANONICAL_DOMAINS, canonical_domain
from app.services.domain_classifier import (
    KEYWORD_RULES, UNCERTAIN_DOMAINS, _keyword_fast_path, _parse_domains, classify_domains,
)

# Captured at import, before conftest's autouse stub replaces it per test.
_REAL_CALL_LLM = dc._call_llm

ROOT = Path(__file__).resolve().parents[2]
UNITS = ROOT / "knowledge_base" / "units"

APP_UNITS = {
    "app-dd32e745": "البداية وإضافة الأطفال",
    "app-8a81df34": "شاشة «اليوم»",
    "app-f59d4579": "المسارات والدروس",
    "app-b1730301": "المساعد",
    "app-c269bf7e": "وضع الطفل",
    "app-088ecfc5": "المهام والعملات والعهد",
    "app-6e3efa4b": "الذاكرة",
    "app-06bb2e07": "المتابعة وخطة الأسبوع",
    "app-615f0eea": "برامج الأسرة",
    "app-2e094883": "الخصوصية وحذف الحساب",
    "app-7e3f1ed7": "المجانية",
    "app-7f8739f7": "اللغات",
}


def _routes_to_app_help(question: str) -> bool:
    return "app_help" in (_keyword_fast_path(question) or [])


# ── the domain exists end to end ───────────────────────────────────────────

def test_app_help_is_a_canonical_storage_domain():
    assert "app_help" in CANONICAL_DOMAINS
    assert canonical_domain("app_help") == "app_help"
    schema = json.loads((ROOT / "knowledge_base/schema/knowledge_unit.schema.json").read_text(encoding="utf-8"))
    assert "app_help" in schema["properties"]["domain"]["enum"]


def test_app_help_has_a_guardrail_policy():
    """A reachable domain with no policy answers with no review and no escalation."""
    from app.config.guardrails_loader import load_guardrails_config

    policy = load_guardrails_config()["domains"].get("app_help")
    assert policy, "app_help is reachable but has no guardrail policy"
    assert policy["default_policy"]["require_human_review"] is False
    assert policy["severity_overrides"]["طارئ"]["escalate_to"] == "emergency_services"


def test_the_rule_comes_last_so_a_parenting_domain_keeps_the_label():
    assert KEYWORD_RULES[-1][1] == "app_help"
    assert _keyword_fast_path("كيف أبدأ رحلة الصلاة في التطبيق؟") == ["fiqh", "app_help"]


# ── app questions route ────────────────────────────────────────────────────

@pytest.mark.parametrize("question", [
    "هل المربي مجاني",
    "كيف أحذف حسابي؟",
    "أريد حذف بياناتي",
    "عايزة امسح بياناتي من التطبيق",
    "هل يمكن إلغاء حسابي في المربي؟",
    # The app's own delete screen talks about the linked Google account.
    "كيف أحذف حسابي المرتبط بحساب Google؟",
    "كيف أخرج من وضع الطفل؟",
    "كيف أفعّل وضع الطفل لابني؟",
    "نسيت رمز PIN الخاص بوضع الطفل",
    "نسيت الـpin لوضع الطفل",
    "كيف اسلم الجهاز لابني في وضع الطفل",
    "وضع الطفل في التطبيق لا يعمل",
    "ما هو ما يعرفه المربي عن طفلي؟",
    "كيف أوقف ذاكرة المربي؟",
    "أين أجد مساراتي؟",
    "كيف أحفظ تقدمي إذا غيرت الهاتف؟",
    "كيف أراسلكم؟",
    "ما هو تطبيق المربي؟",
    # Over several lines, as parents do write them — the anchored lookaheads
    # must still see past the first line.
    "السلام عليكم\nكيف أحذف حسابي؟",
    "السلام عليكم\nوضع الطفل عندي مقفول\nونسيت رمز PIN",
])
def test_app_questions_route_to_app_help(question):
    assert _routes_to_app_help(question)


@pytest.mark.parametrize("question", [
    "كيف أضيف طفلي الثاني في التطبيق؟",
    "ازاي اضيف ابني التاني على التطبيق",
    "هل التطبيق مجاني؟",
    "كيف أغير لغة التطبيق إلى الإنجليزية؟",
    "التطبيق لا يعمل عندي",
    "كيف أستخدم التطبيق؟",
    "السلام عليكم\nكيف أضيف طفلي الثاني\nفي التطبيق؟",
    # Card names are quoted to ask about a topic; they are not triggers.
    "ما هي مهمة اليوم لابني؟",
    "ما هي خطوة اليوم؟",
    "متى يبدأ رمضان العائلة؟",
])
def test_the_weak_app_signal_alone_leaves_the_question_to_the_model(question):
    """«التطبيق» + an app action is also how parents describe practice, so on its
    own it decides nothing: the fast path returns None and the model classifies."""
    assert _keyword_fast_path(question) is None


def test_the_weak_app_signal_beside_a_parenting_domain_adds_app_help():
    assert _keyword_fast_path("كيف أستخدم التطبيق لمتابعة صلاة ابني؟") == ["fiqh", "app_help"]


# ── the model decides what the weak signal alone cannot ────────────────────

_GENERAL = '{"domains": ["general"]}'


@pytest.fixture
def model_answers(monkeypatch):
    """Make the classifier model answer `raw` (None = the model is unreachable),
    through the real call and parse path — only the network is replaced."""
    def _answer(raw):
        monkeypatch.setattr(dc, "_call_llm", _REAL_CALL_LLM)
        if raw is None:
            monkeypatch.setattr(dc, "_classifier_provider", lambda: None)
        else:
            monkeypatch.setattr(dc, "_classifier_provider", lambda: object())
            monkeypatch.setattr(dc, "aux_generate", lambda *a, **k: raw)
        dc._classify_cached.cache_clear()

    yield _answer
    dc._classify_cached.cache_clear()


_WEAK_ONLY_APP_QUESTIONS = [
    "هل التطبيق مجاني؟",
    "كيف أضيف طفلي الثاني في التطبيق؟",
    "ازاي اضيف ابني التاني على التطبيق",
    "كيف أغير لغة التطبيق إلى الإنجليزية؟",
    "التطبيق لا يعمل عندي",
    "كيف أستخدم التطبيق؟",
    "السلام عليكم\nكيف أضيف طفلي الثاني\nفي التطبيق؟",
]


@pytest.mark.parametrize("question", _WEAK_ONLY_APP_QUESTIONS)
def test_a_weak_only_question_the_model_calls_general_goes_to_app_help(model_answers, question):
    """«طفلي» would normally veto «general» into the broad search; beside the
    weak app signal it does not — «كيف أضيف طفلي الثاني في التطبيق؟» is about
    the app."""
    assert _keyword_fast_path(question) is None
    model_answers(_GENERAL)
    assert classify_domains(question) == ["app_help"]


@pytest.mark.parametrize("raw", [None, '{"domains": []}', "لا أعرف"])
def test_a_weak_only_question_the_model_names_no_domain_for_goes_to_app_help(model_answers, raw):
    """Unreachable, naming nothing, or not JSON: no parenting domain was found."""
    model_answers(raw)
    assert classify_domains("هل التطبيق مجاني؟") == ["app_help"]


def test_an_outage_verdict_is_not_kept_once_the_model_is_back(model_answers):
    question = "ابني أنشأ حساب على التطبيق بدون علمي"
    model_answers(None)
    assert classify_domains(question) == ["app_help"]
    model_answers('{"domains": ["cyber"]}')
    assert classify_domains(question) == ["cyber"]


@pytest.mark.parametrize("question,model_domain", [
    # The review's eight (PR #47, 03ffba8b), each with the domain a working
    # model gives. Four reach the model through the weak signal; two reach it
    # with no keyword at all; two never reach it (a parenting rule matches).
    ("بعد التطبيق لمدة أسبوع لم تنجح الطريقة… هل أغير الأسلوب؟", "medical"),
    ("ابني يفهم قاعدة الحساب لكنه يخطئ في التطبيق", "medical"),
    ("المعلمة قالت إن ابني لا يحسن التطبيق في الدروس", "medical"),
    ("ابني أنشأ حساب على التطبيق بدون علمي", "cyber"),
    ("مهمة اليوم: كيف أعلم ابني الصدق؟", "medical"),
    ("رمضان عائلتنا… بعد وفاة الجد", "aqeedah"),
    ("أحذف حسابي على فيسبوك…", "cyber"),
    ("وضع الطفل أمام التطبيقات", "cyber"),
])
def test_the_models_parenting_domain_is_kept_for_the_review_cases(model_answers, question, model_domain):
    model_answers('{"domains": ["%s", "general"]}' % model_domain)
    domains = classify_domains(question)
    assert domains == [model_domain]
    assert "app_help" not in domains


def test_the_own_child_veto_still_guards_questions_without_the_app_signal():
    assert _parse_domains(_GENERAL, "ابني مابيحبش يروح المدرسة وبيعيط") == list(UNCERTAIN_DOMAINS)
    assert _parse_domains(_GENERAL, "كيف أضيف طفلي الثاني في التطبيق؟") == ["general"]


def test_a_question_without_the_app_signal_keeps_the_broad_fallback(model_answers):
    model_answers(None)
    assert classify_domains("بنتي عمرها 5 سنوات تصرفاتها غريبة") == list(UNCERTAIN_DOMAINS)


@pytest.mark.parametrize("question,expected", [
    ("هل التطبيق مجاني؟", ["app_help"]),
    ("بنتي عمرها 5 سنوات تصرفاتها غريبة", list(UNCERTAIN_DOMAINS)),
    # Keywords that matched keep their verdict, weak signal included.
    ("كيف أستخدم التطبيق لمتابعة صلاة ابني؟", ["fiqh", "app_help"]),
])
def test_a_classifier_past_its_deadline_falls_back_the_same_way(monkeypatch, question, expected):
    """The router's deadline (_classify_and_rewrite) is the other way the model
    can give no verdict; it uses the same fallback."""
    from app.routers import assistant

    release = threading.Event()

    def _slow_classify(q):
        release.wait(5.0)
        return ["medical"]

    monkeypatch.setattr(assistant, "classify_domains", _slow_classify)
    monkeypatch.setattr(assistant, "rewrite_query", lambda *a, **k: "")
    monkeypatch.setattr(assistant, "_AUX_WAIT_S", 0.2, raising=False)
    try:
        domains, _ = asyncio.run(assistant._classify_and_rewrite(question))
    finally:
        release.set()
    assert domains == expected


# ── parenting questions do not ─────────────────────────────────────────────

@pytest.mark.parametrize("question", [
    # «التطبيق» meaning "putting it into practice"
    "ما التطبيق العملي لتعديل سلوك ابني العنيد؟",
    "كيف يكون التطبيق العملي لهذه النصيحة؟",
    "بخصوص نصيحة اليوم: كيف أطبقها مع ابني؟",
    # «وضع الطفل» as the child's situation, or putting the child somewhere
    "ما وضع الطفل النفسي بعد الطلاق؟",
    "وضع الطفل في الحضانة مبكرا هل يضره؟",
    "وضع الطفل أمام الهاتف لساعات",
    "ما وضع الطفل عند الدخول للمدرسة",
    # Other apps and accounts, and words the app shares with everyday Arabic
    "ابني يستخدم التطبيقات كثيرا",
    "ابني يريد حذف حسابه على الفيسبوك",
    "ابني فتح حساب جوجل بدون إذني",
    "ابني يعرف رمز القفل للهاتف",
    "ابني يعاني من ضعف الذاكرة في المذاكرة",
    "كيف أعلم ابني قيمة العملات والمال؟",
    "اعمل لي خطة الأسبوع للمذاكرة",
    "ما المراحل المهمة في نمو الطفل؟",
    "اقترح برنامج رمضان لأطفالي",
    "ما برامج الأسرة المناسبة على التلفاز",
    "ابني حذف الألعاب من الهاتف وغضب",
    "دور المربي في تعديل السلوك",
    "كيف يتعامل المربي مع عناد الطفل",
    "ابني يتعلم اللغة الإنجليزية ببطء",
    "ما وضع الطفل في التطبيق العملي للخطة؟",
])
def test_parenting_questions_do_not_route_to_app_help(question):
    assert not _routes_to_app_help(question)


@pytest.mark.parametrize("question", [
    # «التطبيق» as practice, beside an app action
    "بعد التطبيق لمدة أسبوع لم تنجح الطريقة… هل أغير الأسلوب؟",
    "ابني يفهم قاعدة الحساب لكنه يخطئ في التطبيق",
    "المعلمة قالت إن ابني لا يحسن التطبيق في الدروس",
    # another app's account
    "ابني أنشأ حساب على التطبيق بدون علمي",
    # a card quoted to ask about its topic
    "مهمة اليوم: كيف أعلم ابني الصدق؟",
    "رمضان عائلتنا… بعد وفاة الجد",
    # another platform's account
    "أحذف حسابي على فيسبوك…",
    "أريد حذف حسابي على انستغرام",
    "حذف بياناتي من واتساب",
    # apps in general
    "وضع الطفل أمام التطبيقات",
])
def test_parenting_questions_are_never_answered_from_the_app_manual_alone(question):
    """Found in review (PR #47): each of these was app_help-only. A question may
    still search app_help beside a parenting domain, never instead of one."""
    assert _keyword_fast_path(question) != ["app_help"]


def _parenting_corpus() -> list[str]:
    out: list[str] = []
    for name in ("collected_questions_all.json", "collected_questions.json", "collected_questions_r3.json"):
        out += [d["question"] for d in json.loads((ROOT / "ops/data" / name).read_text(encoding="utf-8"))]
    for name in ("golden_set.jsonl", "memory_set.jsonl"):
        for line in (ROOT / "ops/eval" / name).read_text(encoding="utf-8").splitlines():
            if line.strip() and json.loads(line).get("question"):
                out.append(json.loads(line)["question"])
    arb = json.loads((ROOT / "mobile/lib/l10n/app_ar.arb").read_text(encoding="utf-8"))
    out += [v for k, v in arb.items() if k.startswith("chatQ_") and isinstance(v, str)]
    return out


_FILLER = "ابني عمره تسع سنوات ويرفض الذهاب إلى المدرسة كل صباح ويبكي. "


@pytest.mark.parametrize("name,head,filler,tail", [
    ("plain", "", _FILLER, ""),
    ("app noun first", "التطبيق ", _FILLER, ""),
    ("child mode first", "وضع الطفل ", _FILLER, ""),
    ("delete phrase last", "", _FILLER, " حذف حسابي"),
    ("one letter", "", "ا", ""),
    ("lines", "التطبيق\n", "سطر قصير بلا شيء\n", ""),
])
def test_a_question_of_the_maximum_length_classifies_fast(name, head, filler, tail):
    """The fast path runs on the event loop (routers/assistant.py). Unanchored,
    the paired lookaheads were quadratic: ~160 ms here and 1–2 s in review for a
    4,000-character question. Anchored with `^` it is a few milliseconds."""
    from app.models.api import MAX_MESSAGE_CHARS

    body = head + filler * (MAX_MESSAGE_CHARS // len(filler) + 1)
    text = body[:MAX_MESSAGE_CHARS - len(tail)] + tail
    assert len(text) == MAX_MESSAGE_CHARS
    best = min(_elapsed(_keyword_fast_path, text) for _ in range(3))
    assert best < 0.050, f"{name}: {best * 1000:.0f} ms for {len(text)} characters"


def _elapsed(fn, arg) -> float:
    start = time.perf_counter()
    fn(arg)
    return time.perf_counter() - start


def test_no_parenting_question_in_the_repo_routes_to_app_help():
    corpus = _parenting_corpus()
    assert len(corpus) > 500, "the corpora moved — this test must not pass vacuously"
    hits = [q[:80] for q in corpus if _routes_to_app_help(q)]
    assert not hits, f"{len(hits)} parenting questions routed to app_help: {hits[:5]}"


# ── the units ──────────────────────────────────────────────────────────────

def _app_units() -> dict[str, dict]:
    out = {}
    for f in sorted(UNITS.glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        if d.get("domain") == "app_help":
            out[d["id"]] = d
    return out


def test_every_topic_has_its_unit_and_every_unit_is_authored_app_guidance():
    units = _app_units()
    assert set(APP_UNITS) <= set(units), sorted(set(APP_UNITS) - set(units))
    for uid, d in units.items():
        assert d["source_kind"] == "authored_guidance", uid
        assert d["authored_references"] and d["source_note"], uid
        assert d["age_group"] == "unspecified", uid   # an app question has no age
        assert d["language"] == "ar", uid


def test_no_unit_offers_a_support_purchase_the_app_does_not_show():
    """«ادعم المربّي» renders only when the server's DONATIONS_ENABLED is on — off by
    default, and never switched on in production (no OPERATIONS_LOG entry). A unit
    that told parents where to find it would send them to a screen they cannot see."""
    for uid, d in _app_units().items():
        for word in ("ادعم المربّي", "ادعم المربي", "تبرع", "تبرّع"):
            assert word not in d["text_simplified"], (uid, word)


@pytest.mark.parametrize("question,expected", [
    ("كيف أحذف حسابي وبياناتي؟", "app-2e094883"),
    ("كيف أضيف طفلًا آخر وأغيّر اسمه؟", "app-dd32e745"),
    ("كيف أخرج من وضع الطفل؟ نسيت رمز PIN", "app-c269bf7e"),
    ("هل التطبيق مجاني وهل فيه إعلانات؟", "app-7e3f1ed7"),
    ("كيف أوقف ذاكرة المربي أو أمسحها؟", "app-6e3efa4b"),
])
def test_the_lexical_leg_finds_the_right_app_unit(question, expected):
    """BM25 over the real corpus, filtered to app_help as retrieval filters it."""
    top = [r["unit_id"] for r in _bm25().search(question, domain="app_help", top_k=3)]
    assert expected in top, (question, top)


_INDEX = None


def _bm25():
    global _INDEX
    if _INDEX is None:
        from app.services.bm25_index import _Bm25Index
        _INDEX = _Bm25Index()
    return _INDEX
