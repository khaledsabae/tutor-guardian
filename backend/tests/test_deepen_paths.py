"""The gates in ops/tools/deepen_paths.py are what stand between a draft and a parent.

The deepened paths (prayer and religion, anger and stubbornness, sleep) are
written by an author and attacked by a reviewer from another model family —
but the reviewer is a model, and «a gate that trusts a model's verdict can be
passed by a model». So everything that can be checked mechanically is checked
mechanically, before any review: no religious text typed by the author, no
dialect, no stray script, and every verse or hadith inserted verbatim from the
guarded adhkar bank. These tests pin that the gates bite where they must and
stay quiet where they must.
"""
import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
_TOOL = ROOT / "ops" / "tools" / "deepen_paths.py"
CURRICULUM = ROOT / "knowledge_base" / "curriculum"


@pytest.fixture(scope="module")
def dp():
    spec = importlib.util.spec_from_file_location("deepen_paths", _TOOL)
    module = importlib.util.module_from_spec(spec)
    argv, sys.argv = sys.argv, [sys.argv[0]]
    try:
        spec.loader.exec_module(module)
    finally:
        sys.argv = argv
    return module


@pytest.fixture(scope="module")
def bank(dp):
    return dp.load_bank()


GOOD_SUMMARY = " ".join(["الطفل يتعلّم بالقدوة قبل الكلام، فكن هادئًا معه."] * 22)


def _lesson(**over):
    doc = {
        "title": "درسٌ تجريبي",
        "summary": GOOD_SUMMARY,
        "try_this": "اليوم: اجلس مع طفلك عشر دقائق واسأله عن يومه.",
        "reflection_prompts": ["كيف استجاب طفلك حين سألته عن يومه؟"],
        "unit_ids": ["seed-sleep-46"],
        "warning_flags": [],
        "needs_professional_followup": False,
    }
    doc.update(over)
    return doc


def _gates(dp, doc, allowed=()):
    return dp.arabic_gates(doc, set(allowed), dp._bank_ngrams(dp.load_bank()),
                           set(dp.units()))


def test_a_clean_draft_passes(dp):
    assert _gates(dp, _lesson()) == []


@pytest.mark.parametrize("snippet", [
    "قال النبي ﷺ: «الدين النصيحة»",
    "رواه البخاري",
    "قال تعالى: ﴿وَاصْبِرْ﴾",
    "كما في الحديث الشريف",
    "أخرجه الترمذي",
])
def test_religious_text_typed_by_the_author_is_rejected(dp, snippet):
    doc = _lesson(summary=GOOD_SUMMARY + " " + snippet)
    assert any("نصٌّ شرعي" in p for p in _gates(dp, doc)), snippet


def test_copying_four_words_of_a_bank_verse_is_rejected(dp, bank):
    verse = bank["v_020_132"]["text"]          # وَأْمُرْ أَهْلَكَ بِالصَّلَاةِ وَاصْطَبِرْ …
    stripped = dp._strip_marks(verse)
    doc = _lesson(summary=GOOD_SUMMARY + " " + " ".join(stripped.split()[:5]))
    assert any("منقولة" in p for p in _gates(dp, doc))


def test_conversation_is_not_mistaken_for_hadith(dp):
    """«الحديث مع طفلك» is a conversation; the gate must not fire on it."""
    doc = _lesson(summary=GOOD_SUMMARY + " الحديث مع طفلك قبل النوم من أجمل اللحظات.")
    assert _gates(dp, doc) == []


@pytest.mark.parametrize("word", ["عشان", "اللي", "دلوقتي", "مش", "بيحب"])
def test_egyptian_dialect_is_rejected(dp, word):
    doc = _lesson(summary=GOOD_SUMMARY + f" هذا {word} مهم.")
    assert any("عامية" in p for p in _gates(dp, doc)), word


@pytest.mark.parametrize("word", ["دول عربية", "عملٌ خالص لله", "حاجة الطفل"])
def test_msa_words_that_look_colloquial_pass(dp, word):
    doc = _lesson(summary=GOOD_SUMMARY + f" {word}.")
    assert _gates(dp, doc) == [], word


@pytest.mark.parametrize("leak", ["בו", "而不是", "hello", "привет"])
def test_any_non_arabic_script_is_rejected(dp, leak):
    doc = _lesson(summary=GOOD_SUMMARY + f" {leak}")
    assert any("محارف" in p for p in _gates(dp, doc)), leak


def test_placeholder_is_allowed_only_when_listed(dp):
    doc = _lesson(summary=GOOD_SUMMARY + " [[h_009]]")
    assert _gates(dp, doc, allowed={"h_009"}) == []
    assert any("غير مسموح" in p for p in _gates(dp, doc))


def test_try_this_must_be_an_action_for_today(dp):
    doc = _lesson(try_this="هذا الأسبوع: اجلس مع طفلك وتحدّث معه عن يومه.")
    assert any("اليوم:" in p for p in _gates(dp, doc))


def test_free_text_warning_flags_are_rejected(dp):
    """The app shows only the `needs_professional_followup` token (models.dart);
    free text in warning_flags is invisible to parents."""
    doc = _lesson(warning_flags=["حزنٌ يطول أسابيع"])
    assert any("warning_flags" in p for p in _gates(dp, doc))
    doc = _lesson(warning_flags=["needs_professional_followup"],
                  needs_professional_followup=True)
    assert _gates(dp, doc) == []


def test_unknown_unit_is_rejected(dp):
    doc = _lesson(unit_ids=["not-a-real-unit"])
    assert any("unit_ids" in p for p in _gates(dp, doc))


@pytest.fixture(scope="module")
def scan():
    """The scripture guard's own scanner — the tests ask it, not a copy of its rules."""
    sys.path.insert(0, str(ROOT / "ops" / "tools"))
    import scripture_scan
    return scripture_scan


def test_bank_hadith_numbers_hold_their_text_in_the_guards_corpus(bank, scan):
    """Muslim was held back until the hadith guard moved to Abd al-Baqi's numbering
    (#27): a number that changes under a published lesson is worse than no hadith.
    It has moved, so both Sahihayn are offered — and every number the tool can
    insert must hold its exact text in the corpus the guard itself reads."""
    hadith = [i for i in bank.values() if i["kind"] == "hadith"]
    assert {i["provenance"]["book"] for i in hadith} == {"البخاري", "مسلم"}
    for item in hadith:
        prov = item["provenance"]
        assert scan.sahihayn_holds(prov["book"], int(prov["number"]),
                                   scan._fragments(item["text"])), item["id"]


def test_expansion_inserts_the_bank_text_verbatim_in_both_languages(dp, bank):
    ar = dp.expand("قبل [[v_020_132]] بعد", bank, "ar")
    en = dp.expand("before [[v_020_132]] after", bank, "en")
    text = bank["v_020_132"]["text"]
    assert f"﴿{text}﴾" in ar and f"﴿{text}﴾" in en
    assert "Allah says: ﴿" in en and "Surah Ta-Ha, 20:132" in en
    h = dp.expand("[[h_009]]", bank, "en")
    assert f"«{bank['h_009']['text']}»" in h and "(Sahih al-Bukhari 6116)" in h


def test_every_expanded_hadith_is_sound_to_the_scripture_guard(dp, bank, scan):
    """«(Sahih al-Bukhari, hadith 6927)» read to the guard as no citation at all, so
    the English twin of a lesson showed a hadith «بلا إسناد». The guard is what
    stands between the text and the parent: ask it about every hadith, both
    languages, and require the same book and number on each side."""
    for hid, item in bank.items():
        if item["kind"] != "hadith":
            continue
        ar, en = (dp.expand(f"[[{hid}]]", bank, lang) for lang in ("ar", "en"))
        for text in (ar, en):
            assert [f for f in scan.scan_text(text) if f.verdict != "ok"] == [], (hid, text)
        want = {(item["provenance"]["book"], int(item["provenance"]["number"]))}
        assert scan.ar_citations(ar) == scan.en_citations(en) == want, hid


def test_english_gate_rejects_arabic_not_taken_from_the_source(dp):
    ar = _lesson()
    en = {"title": "A lesson", "summary": "Text with Arabic: بسم الله",
          "try_this": "Today: sit with your child.",
          "reflection_prompts": ["How did it go?"], "warning_flags": []}
    assert any("verbatim" in p for p in dp.english_gates(en, ar))


def test_english_gate_rejects_a_placeholder_the_arabic_does_not_have(dp):
    """Seen live: a model 'fixing' an English draft inserted [[h_009]] where the
    Arabic had a dhikr, which would have put «Do not become angry» into a
    lesson about doubts."""
    ar = _lesson()
    en = {"title": "A lesson", "summary": "Say: [[h_009]]",
          "try_this": "Today: sit with your child.",
          "reflection_prompts": ["How did it go?"], "warning_flags": []}
    assert any("placeholders" in p for p in dp.english_gates(en, ar))


# ── what was actually written ────────────────────────────────────────────

def _generated_lessons():
    out = []
    for f in sorted((CURRICULUM / "i18n" / "en" / "lessons").glob("*.json")):
        en = json.loads(f.read_text(encoding="utf-8"))
        if (en.get("translation") or {}).get("generated_by") == "ops/tools/deepen_paths.py":
            ar = json.loads((CURRICULUM / "lessons" / f.name).read_text(encoding="utf-8"))
            out.append((ar, en))
    return out


def test_every_verse_and_hadith_in_a_written_lesson_is_verbatim_from_the_bank(dp, bank):
    texts = {i["text"] for i in bank.values()}
    for ar, en in _generated_lessons():
        for doc in (ar, en):
            for m in re.finditer(r"﴿([^﴾]+)﴾", doc["summary"]):
                assert m.group(1) in texts, (doc["id"], m.group(1)[:40])
            for m in re.finditer(r"ﷺ[^«]{0,12}«([^»]+)»", doc["summary"]):
                assert m.group(1) in texts, (doc["id"], m.group(1)[:40])


def test_written_lessons_are_well_formed_pairs(dp):
    for ar, en in _generated_lessons():
        assert en["id"] == ar["id"] and en["path_id"] == ar["path_id"]
        assert ar["try_this"].startswith("اليوم:"), ar["id"]
        assert en["try_this"].startswith("Today:"), en["id"]
        assert en["warning_flags"] == ar["warning_flags"], ar["id"]
        assert en["translation"]["approved_by"] is None
        path = json.loads((CURRICULUM / "paths" / f"{ar['path_id']}.json")
                          .read_text(encoding="utf-8"))
        assert ar["id"] in path["lesson_ids"], ar["id"]


# ── the reviewer call: one try per family, then wait ──────────────────────

class _FakeOllama:
    """Stands in for urlopen: a script of outcomes per model, and a call log."""

    def __init__(self, outcomes):
        self.outcomes, self.calls = outcomes, []

    def __call__(self, req, timeout=None):
        import io
        import urllib.error
        model = json.loads(req.data)["model"]
        self.calls.append(model)
        out = self.outcomes[model]
        if isinstance(out, int):
            raise urllib.error.HTTPError(req.full_url, out, "x", {}, None)
        if isinstance(out, BaseException):
            raise out
        body = {"choices": [{"message": {"content": json.dumps(out)}}]}
        return io.BytesIO(json.dumps(body).encode())


@pytest.fixture
def ollama(dp, monkeypatch):
    monkeypatch.setenv("OLLAMA_API_KEY", "test-not-a-key")
    monkeypatch.setattr(dp, "REVIEW_PATIENCE_S", 0)

    def install(outcomes):
        fake = _FakeOllama(outcomes)
        monkeypatch.setattr(dp.urllib.request, "urlopen", fake)
        return fake
    return install


def test_a_timeout_goes_to_the_other_family_without_retrying_the_same_model(dp, ollama):
    """tc._post retries a timeout three times; on a crowded shared key that spent
    15 minutes per lesson — and quota — before the fallback was ever asked."""
    fake = ollama({dp.REVIEW_MODEL: TimeoutError("read timed out"),
                   dp.REVIEW_FALLBACK: {"verdict": "clean", "defects": []}})
    verdict, model = dp.review("system", {"lesson": "x"})
    assert (verdict["verdict"], model) == ("clean", dp.REVIEW_FALLBACK)
    assert fake.calls == [dp.REVIEW_MODEL, dp.REVIEW_FALLBACK]


def test_an_account_refusal_is_raised_not_waited_on(dp, ollama):
    fake = ollama({dp.REVIEW_MODEL: 401, dp.REVIEW_FALLBACK: {"verdict": "clean"}})
    with pytest.raises(RuntimeError, match="غير متاح"):
        dp.review("system", {"lesson": "x"})
    assert fake.calls == [dp.REVIEW_MODEL]


def test_both_families_busy_ends_in_an_error_not_a_verdict(dp, ollama):
    fake = ollama({dp.REVIEW_MODEL: 429, dp.REVIEW_FALLBACK: 429})
    with pytest.raises(RuntimeError, match="both reviewers unavailable"):
        dp.review("system", {"lesson": "x"})
    assert fake.calls == [dp.REVIEW_MODEL, dp.REVIEW_FALLBACK]
