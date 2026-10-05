"""The four medical units PR #23 found missing stay sourced, safe and reachable.

PR #23 shipped red flags for puberty, periods and children's fasting in the
family programs with no knowledge unit behind them. These units fill that gap
from public-health pages (NHS, the AAP's HealthyChildren.org, the Saudi Ministry
of Health), so what they promise is pinned here: every claim has a cited page,
every unit ends by saying when to see a doctor, no medicine is named (the medical
policy forbids it), the fasting unit keeps the program's order — urgent signs
first — and retrieval finds each unit for the question a parent would ask.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
UNITS = ROOT / "knowledge_base" / "units"

GAP_UNITS = {
    "dev-7562f817": "development",   # boys' puberty
    "med-360b9041": "medical",       # early or delayed puberty
    "med-f8cc198a": "medical",       # a girl's first years of periods
    "med-80a3871c": "medical",       # fasting children: dehydration, when to stop
}


def _unit(uid: str) -> dict:
    return json.loads((UNITS / f"{uid}.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("uid,domain", sorted(GAP_UNITS.items()))
def test_each_unit_cites_the_pages_it_rests_on(uid, domain):
    d = _unit(uid)
    assert d["domain"] == domain and d["language"] == "ar"
    assert d["source_kind"] == "authored_guidance" and d["source_note"]
    web = [r for r in d["authored_references"] if re.search(r"https://www\.(nhs\.uk|healthychildren\.org|moh\.gov\.sa)/", r)]
    assert web, f"{uid}: no public-health page cited"
    for r in web:
        assert "اطُّلع عليها 2026-10-05" in r, f"{uid}: a cited page has no access date: {r[:80]}"
    assert "اطّلعنا عليها" in d["reference_info"]


@pytest.mark.parametrize("uid", sorted(GAP_UNITS))
def test_each_unit_ends_by_saying_when_to_see_a_doctor(uid):
    sections = [s for s in _unit(uid)["text_simplified"].split("\n\n") if s.strip()]
    assert sections[-1].startswith("متى تراجعون"), sections[-1][:60]


_MEDICINE_NAMES = re.compile(
    r"باراسيتامول|أسيتامينوفين|ايبوبروفين|إيبوبروفين|بروفين|نابروكسين|ميفيناميك|ترانيكساميك|تستوستيرون|"
    r"استروجين|إستروجين|حبوب منع الحمل|(?i:paracetamol|ibuprofen|naproxen|testosterone|tranexamic)"
)


@pytest.mark.parametrize("uid", sorted(GAP_UNITS))
def test_no_unit_names_a_medicine(uid):
    """policies.v1.yaml: medical → allow_medication_names: false."""
    d = _unit(uid)
    assert not _MEDICINE_NAMES.search(d["title"] + " " + d["text_simplified"])


def test_the_fasting_unit_keeps_the_ladders_order_and_actions():
    """ramadan_family.json «سلّم الصيام» puts urgent signs before stop signs; a
    unit that led with the milder list would teach the wrong reflex."""
    ladder = json.loads((ROOT / "knowledge_base/curriculum/programs/ramadan_family.json")
                        .read_text(encoding="utf-8"))["fasting_ladder"]
    text = _unit("med-80a3871c")["text_simplified"]
    urgent, stop = text.index("الإسعاف فورًا"), text.index("أن يُفطر الآن")
    assert urgent < stop
    # The ladder's actions, as the unit must carry them.
    assert "ماء وتمرة أو عصير" in ladder["stop_action"] and "ماء وتمرة أو عصير" in text
    assert "لا تعطوه شيئًا بالفم حتى يستعيد وعيه تمامًا" in text
    assert "خلال ساعة" in ladder["stop_action"] and "خلال ساعة" in text
    for sign in ("إغماء", "تشنّج", "قيء متكرر", "هبوط السكر"):
        assert sign in text, sign


@pytest.mark.parametrize("question,domain,expected", [
    ("متى يبدأ البلوغ عند الأولاد وما علاماته؟", "development", "dev-7562f817"),
    ("كيف أشرح لابني الاحتلام؟", "development", "dev-7562f817"),
    ("ابني عمره 14 ولم تظهر عليه علامات البلوغ متى نراجع الطبيب؟", "medical", "med-360b9041"),
    ("الدورة عند بنتي غير منتظمة من سنة هل هذا طبيعي؟", "medical", "med-f8cc198a"),
    ("بنتي الدورة عندها غزيرة وتغير الفوطة كل ساعة", "medical", "med-f8cc198a"),
    ("متى يفطر الطفل الصائم فورا؟", "medical", "med-80a3871c"),
])
def test_the_lexical_leg_finds_each_unit(question, domain, expected):
    top = [r["unit_id"] for r in _bm25().search(question, domain=domain, top_k=3)]
    assert expected in top, (question, top)


_INDEX = None


def _bm25():
    global _INDEX
    if _INDEX is None:
        from app.services.bm25_index import _Bm25Index
        _INDEX = _Bm25Index()
    return _INDEX
