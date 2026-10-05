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
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.core.taxonomy import CANONICAL_DOMAINS, canonical_domain
from app.services.domain_classifier import KEYWORD_RULES, _keyword_fast_path

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
    "كيف أضيف طفلي الثاني في التطبيق؟",
    "ازاي اضيف ابني التاني على التطبيق",
    "كيف أغير اسم طفلي في التطبيق؟",
    "هل التطبيق مجاني؟",
    "هل في التطبيق إعلانات؟",
    "هل المربي مجاني",
    "كيف أحذف حسابي؟",
    "أريد حذف بياناتي",
    "عايزة امسح بياناتي من التطبيق",
    "كيف أخرج من وضع الطفل؟",
    "كيف أفعّل وضع الطفل لابني؟",
    "نسيت رمز PIN الخاص بوضع الطفل",
    "كيف اسلم الجهاز لابني في وضع الطفل",
    "ما هو ما يعرفه المربي عن طفلي؟",
    "كيف أوقف الذاكرة في التطبيق؟",
    "كيف أبدأ رحلة الصلاة مع ابني؟",
    "متى يبدأ رمضان العائلة؟",
    "أين أجد مساراتي؟",
    "ما هي مهمة اليوم لابني؟",
    "ما هي خطوة اليوم؟",
    "كيف أغير لغة التطبيق إلى الإنجليزية؟",
    "التطبيق لا يعمل عندي",
    "كيف أستخدم التطبيق؟",
    "هل التطبيق يحفظ بيانات أطفالي؟",
    "هل التطبيق يرسل اسم طفلي للذكاء الاصطناعي؟",
    "كيف أحفظ تقدمي إذا غيرت الهاتف؟",
    "كيف تعمل العملات في التطبيق؟",
    "هل يمكن استخدام التطبيق بالفرنسية؟",
    "كيف أراسلكم؟",
    "ما هو تطبيق المربي؟",
    # Over several lines, as parents do write them.
    "السلام عليكم\nكيف أضيف طفلي الثاني\nفي التطبيق؟",
])
def test_app_questions_route_to_app_help(question):
    assert _routes_to_app_help(question)


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
])
def test_parenting_questions_do_not_route_to_app_help(question):
    assert not _routes_to_app_help(question)


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
