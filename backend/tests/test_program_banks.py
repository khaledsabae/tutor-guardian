"""Family programs (Ramadan · prayer journey · milestones) are content banks with a
validator that must have teeth in the right place.

Two halves, both necessary:

* the real files pass every gate (schema, references, language parity, sacred
  texts, program constraints, hadith cards against the Sahihayn) — so a broken
  file cannot reach a family;
* every rule rejects a crafted violation of exactly that rule — so a gate that
  silently stopped looking (the way the hadith guard once never read the
  translated units) shows up here as a failing test, not as a green check.

The mutations start from copies of the shipped files rather than hand-written
fixtures: a fixture written to match the schema tests the schema, not the data.
"""
from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "ops" / "tools"
CURRICULUM = ROOT / "knowledge_base" / "curriculum"
PROGRAMS = CURRICULUM / "programs"
PROGRAMS_EN = CURRICULUM / "i18n" / "en" / "programs"


def _load_tool(name: str):
    sys.path.insert(0, str(TOOLS))
    spec = importlib.util.spec_from_file_location(name, TOOLS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def cp():
    return _load_tool("check_programs")


@pytest.fixture(scope="module")
def src(cp):
    return cp.load_sources()


def _pair(name: str):
    fname = f"{name}.json"
    if not (PROGRAMS / fname).exists():
        pytest.skip(f"{fname} not shipped yet")
    ar = json.loads((PROGRAMS / fname).read_text(encoding="utf-8"))
    en = json.loads((PROGRAMS_EN / fname).read_text(encoding="utf-8"))
    return ar, en


@pytest.fixture(scope="module")
def ramadan():
    return _pair("ramadan_family")


def _problems(cp, src, name, ar, en):
    return cp.check_pair(name, ar, en, src)


def _expect(problems, needle):
    assert any(needle in p for p in problems), (
        f"expected a problem containing {needle!r}, got:\n" + "\n".join(problems[:15]))


# ── the real files pass every gate ─────────────────────────────────────────

@pytest.mark.parametrize("tool,marker", [
    ("check_programs.py", "PROGRAMS OK"),
    ("check_curriculum_schema.py", "CURRICULUM SCHEMA OK"),
    ("check_hadith_citations.py", "HADITH OK"),
])
def test_shipped_programs_pass_the_gate(tool, marker):
    result = subprocess.run([sys.executable, str(TOOLS / tool)], cwd=ROOT,
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stdout[-3000:] + result.stderr[-2000:]
    assert marker in result.stdout


def test_every_shipped_program_has_an_english_twin():
    for f in PROGRAMS.glob("*.json"):
        assert (PROGRAMS_EN / f.name).exists(), f"{f.name} ships without English"


def test_self_tests_hold_on_the_real_sources(cp, src):
    assert cp._self_test(src) == []


def test_hadith_scan_reads_program_cards():
    hc = _load_tool("check_hadith_citations")
    books = hc._load_index()["books"]
    cards, errors = hc.scan_programs(books)
    if any(PROGRAMS.glob("*.json")):
        assert cards > 0, "the hadith guard is not reading program evidence cards"
    assert errors == []
    bad = {"text_ar": "خيركم من تعلم القرآن وعلمه", "source": "صحيح البخاري — حديث ٥٠٢٧",
           "provenance": {"book": "البخاري", "number": 5028}}
    assert hc.check_program_card(books, bad) is not None


def test_loader_resolves_the_english_twin_and_falls_back_to_arabic():
    sys.path.insert(0, str(ROOT / "backend"))
    from app.services import content_lang
    if not (PROGRAMS_EN / "ramadan_family.json").exists():
        pytest.skip("ramadan_family not shipped yet")
    assert content_lang.localised(PROGRAMS, "ramadan_family.json", "en") == PROGRAMS_EN / "ramadan_family.json"
    assert content_lang.localised(PROGRAMS, "ramadan_family.json", "fr") == PROGRAMS / "ramadan_family.json"


# ── every rule bites (Ramadan) ─────────────────────────────────────────────

def _mutated(pair, fn):
    ar, en = copy.deepcopy(pair[0]), copy.deepcopy(pair[1])
    fn(ar, en)
    return ar, en


@pytest.mark.parametrize("label,mutate,needle", [
    ("unknown knowledge unit",
     lambda ar, en: [d["parent_note"]["unit_ids"].append("isl-does-not-exist") for d in (ar["days"][0], en["days"][0])],
     "ليست وحدة"),
    ("story with no English version",
     lambda ar, en: [d.__setitem__("story_id", "badr_broken_toy") for d in (ar["days"][0], en["days"][0])],
     "بلا ترجمة"),
    ("ayah outside its surah",
     lambda ar, en: [d["quran"]["together"].__setitem__("to", 99) for d in (ar["days"][0], en["days"][0])],
     "خارج حدود السورة"),
    ("English drops a step",
     lambda ar, en: en["days"][0]["family_challenge"]["steps"].pop(),
     "طول القائمة"),
    ("English changes an invariant",
     lambda ar, en: en["days"][2].__setitem__("story_id", "layla_star"),
     "يجب أن يتطابق"),
    ("Arabic letters in English",
     lambda ar, en: en["days"][0]["parent_note"].__setitem__("text", en["days"][0]["parent_note"]["text"] + " رمضان"),
     "حروف عربية في الإنجليزي"),
    ("Egyptian dialect",
     lambda ar, en: ar["days"][0]["variants"]["7-9"].__setitem__("text", "مش لازم تكتب النية النهارده عشان تعبان."),
     "عامية"),
    ("Prophet mentioned without a source",
     lambda ar, en: ar["days"][1]["variants"]["7-9"].__setitem__("text", "كان النبي ﷺ يحب الزينة في رمضان، فزيّن الركن."),
     "بلا حديث مرفق"),
    ("hadith quoted in free text",
     lambda ar, en: ar["days"][0]["parent_note"].__setitem__("text", "قال النبي ﷺ: إنما الأعمال بالنيات."),
     "اقتباس/إسناد"),
    ("attached hadith copied outside its card",
     lambda ar, en: ar["days"][3]["parent_note"].__setitem__("text", "تذكّروا: تسحروا فإن في السحور بركة، ولا توقظوا الصغار."),
     "مقتبس خارج بطاقته"),
    ("weak saying about Ramadan's thirds",
     lambda ar, en: ar["days"][20]["parent_note"].__setitem__("text", "العشر الأواخر عتق من النار، فاجتهدوا مع أطفالكم."),
     "قول لا يثبت"),
    ("fasting under seven",
     lambda ar, en: [d["fasting_ladder"]["bands"]["4-6"]["steps"][0].update(until="dhuhr", approx_hours=6) for d in (ar, en)],
     "لا إمساك تحت السابعة"),
    ("a full fasting day for 7-9",
     lambda ar, en: [d["fasting_ladder"]["bands"]["7-9"]["steps"][-1].update(until="maghrib", approx_hours=13) for d in (ar, en)],
     "لا يوم كامل"),
    ("odd night placed on the even evening",
     lambda ar, en: [d["days"][20].__setitem__("odd_night", True) for d in (ar, en)],
     "odd_night"),
    ("family word left to a day that may not come",
     lambda ar, en: [d["days"][29]["tracks"].append("family_word") for d in (ar, en)],
     "family_word"),
    ("recap template with an unknown field",
     lambda ar, en: [d["recap"]["templates"]["lines"].append("x {nonexistent}") for d in (ar, en)],
     "ليس مقياسًا"),
    ("template fields differ between languages",
     lambda ar, en: en["recap"]["templates"].__setitem__("closing", "{app_link}"),
     "حقول القالب"),
    ("orphan evidence card",
     lambda ar, en: [d["days"][0]["parent_note"]["evidence_ids"].remove("h_ramadan_faith") for d in (ar, en)],
     "بطاقة يتيمة"),
    ("band map missing a band",
     lambda ar, en: [d["bands"]["band_map"].pop("16-18") for d in (ar, en)],
     "band_map"),
    ("variant addressed to the wrong reader",
     lambda ar, en: [d["days"][0]["variants"]["4-6"].__setitem__("addressed_to", "child") for d in (ar, en)],
     "موجّه إلى"),
    ("challenge track without a story",
     lambda ar, en: [d["days"][0]["tracks"].append("story_heard") for d in (ar, en)],
     "story_heard"),
])
def test_ramadan_rule_bites(cp, src, ramadan, label, mutate, needle):
    ar, en = _mutated(ramadan, mutate)
    _expect(_problems(cp, src, "ramadan_family", ar, en), needle)


def test_pasted_verse_is_caught_even_without_brackets(cp, src, ramadan):
    verse = src["quran"][2][182]["text"]       # al-Baqarah 183
    ar, en = _mutated(ramadan, lambda a, e: a["days"][0]["parent_note"].__setitem__(
        "text", a["days"][0]["parent_note"]["text"] + " " + verse))
    _expect(_problems(cp, src, "ramadan_family", ar, en), "نصّ قرآني")


def test_real_ramadan_has_no_problems(cp, src, ramadan):
    assert _problems(cp, src, "ramadan_family", *copy.deepcopy(ramadan)) == []


def test_odd_nights_are_the_evenings_before_odd_days(ramadan):
    """The 21st night is the evening of day 20 — the Hijri night precedes its day."""
    odd = [d["day"] for d in ramadan[0]["days"] if d["odd_night"]]
    assert odd == [20, 22, 24, 26, 28]


def test_fasting_ladder_is_conservative(ramadan):
    bands = ramadan[0]["fasting_ladder"]["bands"]
    assert bands["0-3"]["fasts"] == bands["4-6"]["fasts"] == "no"
    assert all(s["until"] != "maghrib" for s in bands["7-9"]["steps"])
    assert max(s["approx_hours"] for s in bands["7-9"]["steps"]) <= 9
    ladder = ramadan[0]["fasting_ladder"]
    assert ladder["doctor_first"] and ladder["stop_signs"] and ladder["urgent_signs"]


def test_recap_card_carries_nothing_personal(ramadan):
    privacy = ramadan[0]["recap"]["privacy"]
    assert not any(privacy[k] for k in ("child_names", "child_ages", "photos", "free_text"))


def test_challenges_fit_a_fasting_home(ramadan):
    for d in ramadan[0]["days"]:
        ch = d["family_challenge"]
        assert ch["minutes"] <= 15 and ch["at_home"] and ch["cost"] in ("free", "low"), d["day"]


# ── every rule bites (Prayer Journey) ──────────────────────────────────────

@pytest.fixture(scope="module")
def prayer():
    return _pair("prayer_journey")


@pytest.mark.parametrize("label,mutate,needle", [
    ("coins grow instead of tapering",
     lambda ar, en: [d["stages"][4]["child_tasks"][0].__setitem__("coins", 15) for d in (ar, en)],
     "المكافأة تزيد"),
    ("a day's coins exceed the app's cap",
     lambda ar, en: [d["stages"][0]["child_tasks"][0].update(per_week=70, coins=10) for d in (ar, en)],
     "سقف التطبيق"),
    ("weeks with a gap",
     lambda ar, en: [d["stages"][2].__setitem__("week_from", 6) for d in (ar, en)],
     "غير متصلة"),
    ("no stage suggests recording the first prayer",
     lambda ar, en: [d["stages"][2].__setitem__("journey_milestone_key", None) for d in (ar, en)],
     "أول صلاة"),
    ("a seven-year-old routed to preparation",
     lambda ar, en: [d["entry_rules"][0].__setitem__("max_age_years", 7) or d["entry_rules"][1].__setitem__("min_age_years", 8)
                     for d in (ar, en)],
     "عمر 7"),
    ("duplicate task id",
     lambda ar, en: [d["stages"][1]["child_tasks"][0].__setitem__("id", "prayer_s1_pray_beside") for d in (ar, en)],
     "مكرّر"),
    ("prophet mentioned in an unsourced principle",
     lambda ar, en: ar["principles"].__setitem__(0, "كان النبي ﷺ يعلّم الأطفال الصلاة كل يوم."),
     "بلا حديث مرفق"),
])
def test_prayer_rule_bites(cp, src, prayer, label, mutate, needle):
    ar, en = _mutated(prayer, mutate)
    _expect(_problems(cp, src, "prayer_journey", ar, en), needle)


def test_real_prayer_journey_has_no_problems(cp, src, prayer):
    assert _problems(cp, src, "prayer_journey", *copy.deepcopy(prayer)) == []


def test_prayer_journey_never_grounds_in_units_that_endorse_hitting(prayer):
    """The app's stance is no physical discipline. Two KB units (isl-c4d83813,
    isl-d54fd8e8) endorse hitting at ten; a program that cites them as its source
    hands the parent that advice one tap away."""
    used = set()
    for node in [prayer[0]["basis"], prayer[0]["preparation"], prayer[0]["ownership"],
                 prayer[0]["reward_policy"], *prayer[0]["stages"]]:
        used.update(node.get("unit_ids", []))
    assert not used & {"isl-c4d83813", "isl-d54fd8e8"}


def test_the_seven_hadith_is_described_not_quoted(prayer):
    """«مروهم بالصلاة لسبع» is outside the two Sahihs: no card may carry it."""
    for card in prayer[0]["evidence"]:
        assert "مروا" not in card["text_ar"] and "لسبع" not in card["text_ar"]
    assert "isl-f2bef952" in prayer[0]["basis"]["unit_ids"]


# ── every rule bites (Milestones) ──────────────────────────────────────────

@pytest.fixture(scope="module")
def milestones():
    return _pair("milestones")


def _ms(doc, key):
    return next(m for m in doc["milestones"] if m["key"] == key)


@pytest.mark.parametrize("label,mutate,needle", [
    ("feature with no bank for the child's band",
     lambda ar, en: [_ms(d, "puberty_boys")["links"]["features"].append("license") for d in (ar, en)],
     "لا بنك لها"),
    ("medical milestone without red flags",
     lambda ar, en: [_ms(d, "school_entry").pop("red_flags") for d in (ar, en)],
     "بلا red_flags"),
    ("gendered milestone sent before gender is known",
     lambda ar, en: [_ms(d, "puberty_girls")["audience"].__setitem__("if_gender_unknown", "show") for d in (ar, en)],
     "if_gender_unknown"),
    ("a required milestone missing",
     lambda ar, en: [d["milestones"].remove(_ms(d, "first_phone")) for d in (ar, en)],
     "ناقص"),
    ("alert timing off-policy",
     lambda ar, en: [_ms(d, "age_ten")["trigger"].__setitem__("alert_days_before", 10) for d in (ar, en)],
     "السياسة"),
    ("short hadith copied into a card (caught by a reviewer, missed by a 12-char floor)",
     lambda ar, en: _ms(ar, "puberty_boys")["cards"][4].__setitem__(
         "body", "والحياء من الإيمان كما في الحديث المرفق؛ فعلّموه إياه باحترام."),
     "مقتبس خارج بطاقته"),
    ("season trigger with inverted ages",
     lambda ar, en: [_ms(d, "first_fasting")["trigger"].update(min_age_months=160, max_age_months=100) for d in (ar, en)],
     "min_age_months"),
])
def test_milestone_rule_bites(cp, src, milestones, label, mutate, needle):
    ar, en = _mutated(milestones, mutate)
    _expect(_problems(cp, src, "milestones", ar, en), needle)


def test_real_milestones_have_no_problems(cp, src, milestones):
    assert _problems(cp, src, "milestones", *copy.deepcopy(milestones)) == []


def test_puberty_is_covered_for_both_girls_and_boys_with_red_flags(milestones):
    girls, boys = _ms(milestones[0], "puberty_girls"), _ms(milestones[0], "puberty_boys")
    assert girls["audience"]["gender"] == "female" and boys["audience"]["gender"] == "male"
    assert girls["medical"] and boys["medical"] and girls["red_flags"] and boys["red_flags"]
    # girls are prepared before the earliest normal onset (8), boys before theirs (9)
    assert girls["trigger"]["age_months"] - 1 < 8 * 12 + 12
    assert boys["trigger"]["age_months"] - 1 < 9 * 12 + 12


def test_milestone_alerts_fit_a_notification(milestones):
    for lang_doc in milestones:
        for m in lang_doc["milestones"]:
            assert len(m["alert"]["title"]) <= 50 and len(m["alert"]["body"]) <= 160, m["key"]
