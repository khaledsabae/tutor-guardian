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


@pytest.fixture(scope="module")
def parity():
    spec = importlib.util.spec_from_file_location(
        "deepen_paths_parity", ROOT / "ops/tools/review_en_parity.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


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
    """Every lesson the tool wrote — with its English twin, published or held back
    by `review_en_parity.py unpublish` (an unpublished twin is still checked)."""
    out = []
    twins = [*(CURRICULUM / "i18n" / "en" / "lessons").glob("*.json"),
             *(ROOT / "ops" / "data" / "en_unpublished" / "lessons").glob("*.json")]
    for f in sorted(twins):
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


def _lesson_parity_item(parity, ar, en, en_file):
    return parity.Item(
        kind="lessons", key=en["id"], en_file=en_file,
        ar_file=CURRICULUM / "lessons" / en_file.name,
        fields=parity._field_pairs(ar, en, parity.CURRICULUM_FIELDS["lessons"]),
        age_band=str(ar.get("age_group", "")),
    )


def _assert_lesson_approval(parity, item):
    translation = parity.read_translation(item)
    if translation["approved_by"] is None:
        return  # Generator drafts may still await independent review.
    problem = parity._approval_problem(item, translation)
    assert problem is None, (item.key, problem)
    stamp = parity.parse_stamp(translation["approved_by"])
    assert stamp is not None, (item.key, "not an automatic review stamp")
    reviewers = stamp["reviewers"]
    families = {parity.model_family(model) for model in reviewers}
    assert len(reviewers) == len(families) == 2 and None not in families, (
        item.key, "two independent reviewer families required")
    assert translation["auto_review"].get("reviewers") == reviewers, (
        item.key, "stamp and review record disagree")
    conflict = parity.family_conflict(item, reviewers)
    assert conflict is None, (item.key, conflict)
    defects = parity.deterministic_defects(item)
    assert not defects, (item.key, [defect["why"] for defect in defects])


def test_written_lessons_are_well_formed_pairs(dp, parity):
    for ar, en in _generated_lessons():
        assert en["id"] == ar["id"] and en["path_id"] == ar["path_id"]
        assert ar["try_this"].startswith("اليوم:"), ar["id"]
        assert en["try_this"].startswith("Today:"), en["id"]
        assert en["warning_flags"] == ar["warning_flags"], ar["id"]
        en_file = CURRICULUM / "i18n/en/lessons" / f"{en['id']}.json"
        if not en_file.exists():
            en_file = ROOT / "ops/data/en_unpublished/lessons" / en_file.name
        _assert_lesson_approval(parity, _lesson_parity_item(parity, ar, en, en_file))
        path = json.loads((CURRICULUM / "paths" / f"{ar['path_id']}.json")
                          .read_text(encoding="utf-8"))
        assert ar["id"] in path["lesson_ids"], ar["id"]


@pytest.fixture
def reviewed_pair(tmp_path):
    """Copy the recovered, genuinely reviewed lesson; never stamp repo content."""
    name = "lesson_7-9_aqeedah_fundamentals_11.json"
    # Preserve the actual db07c35f reviewed text: current production lesson 11
    # is now a source-corrected draft and must not retain that old approval.
    fixture = ROOT / "backend/tests/fixtures/lesson11_reviewed_db07c35f"
    ar = json.loads((fixture / "ar.json").read_text())
    en = json.loads((fixture / "en.json").read_text())
    return ar, en, tmp_path / name


def _check_reviewed_pair(parity, pair):
    ar, en, en_file = pair
    en_file.write_text(json.dumps(en, ensure_ascii=False))
    _assert_lesson_approval(parity, _lesson_parity_item(parity, ar, en, en_file))


def test_current_independent_review_is_allowed(parity, reviewed_pair):
    _check_reviewed_pair(parity, reviewed_pair)


def test_unapproved_generator_draft_is_still_allowed(parity, reviewed_pair):
    reviewed_pair[1]["translation"]["approved_by"] = None
    _check_reviewed_pair(parity, reviewed_pair)


@pytest.mark.parametrize("side", [0, 1], ids=["source", "english"])
def test_reviewed_lesson_rejects_text_changed_after_review(parity, reviewed_pair, side):
    reviewed_pair[side]["summary"] += " Additional text."
    with pytest.raises(AssertionError, match="stale"):
        _check_reviewed_pair(parity, reviewed_pair)


@pytest.mark.parametrize("stamp", ["auto-review::2026-10-07", "Unverified signer"])
def test_reviewed_lesson_rejects_invalid_approval(parity, reviewed_pair, stamp):
    reviewed_pair[1]["translation"]["approved_by"] = stamp
    with pytest.raises(AssertionError, match="malformed|no content fingerprint"):
        _check_reviewed_pair(parity, reviewed_pair)


@pytest.mark.parametrize("reviewers,reason", [
    (["deepseek-v4-pro"], "two independent"),
    (["deepseek-v4-pro", "deepseek-v3.2"], "two independent"),
    (["claude-opus-5.5", "glm-5.2"], "same family"),
])
def test_reviewed_lesson_requires_reviewers_independent_of_each_other_and_author(
        parity, reviewed_pair, reviewers, reason):
    translation = reviewed_pair[1]["translation"]
    translation["approved_by"] = parity.stamp_value(reviewers, "2026-10-07")
    translation["auto_review"]["reviewers"] = reviewers
    with pytest.raises(AssertionError, match=reason):
        _check_reviewed_pair(parity, reviewed_pair)


def test_reviewed_lesson_rejects_mismatched_reviewer_record(parity, reviewed_pair):
    reviewed_pair[1]["translation"]["auto_review"]["reviewers"] = ["glm-5.2"]
    with pytest.raises(AssertionError, match="disagree"):
        _check_reviewed_pair(parity, reviewed_pair)


def test_current_hash_does_not_bypass_deterministic_guards(parity, reviewed_pair):
    ar, en, en_file = reviewed_pair
    en["summary"] += " 中文"
    item = _lesson_parity_item(parity, ar, en, en_file)
    en["translation"]["auto_review"]["content_sha256"] = item.sha
    with pytest.raises(AssertionError, match="CJK/Cyrillic"):
        _check_reviewed_pair(parity, reviewed_pair)


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


# ── writing: ids fixed by spec position, only the cleared prefix ───────────

_SUMMARY = "قراءةٌ قصيرة للوالدين عن الصلاة في يوم الطفل. " * 12


class _Shelf:
    """A throw-away curriculum with one existing two-lesson path, a four-lesson
    spec for it, drafts for all four, and a switch for which ones are cleared."""

    def __init__(self, dp, tmp, monkeypatch):
        self.dp, self.tmp = dp, tmp
        cur = tmp / "knowledge_base" / "curriculum"
        for sub in ("paths", "lessons", "i18n/en/paths", "i18n/en/lessons"):
            (cur / sub).mkdir(parents=True)
        self.cur, self.pid = cur, "path_7-9_test_worship"
        base = [{"id": f"lesson_7-9_test_worship_0{i}", "path_id": self.pid,
                 "title": f"درسٌ قديم {i}", "order": i} for i in (1, 2)]
        for b in base:
            self._put(cur / "lessons" / f"{b['id']}.json", b)
        path = {"id": self.pid, "title": "مسار", "age_group": "7-9", "domain": "islamic_parenting",
                "description": "وصف", "lesson_ids": [b["id"] for b in base], "estimated_days": 2}
        self._put(cur / "paths" / f"{self.pid}.json", path)
        self._put(cur / "i18n" / "en" / "paths" / f"{self.pid}.json",
                  dict(path, title="Path", description="Description"))
        self.spec_path = tmp / "ops" / "data" / "deepen_paths" / "t.json"
        self.spec_path.parent.mkdir(parents=True)
        self.briefs = [f"درسٌ جديد {i}" for i in range(1, 5)]
        self.work = dp.Work(tmp / "work" / "t")
        self._put(self.work.root / f"{self.pid}.drafts.json", {
            f"s{i:02d}": {
                "ar": {"title": b, "summary": _SUMMARY, "try_this": "اليوم: صلِّ مع طفلك.",
                       "reflection_prompts": ["كيف كان؟"], "unit_ids": [], "warning_flags": [],
                       "needs_professional_followup": False},
                "en": {"title": f"New lesson {i}", "summary": "A short read. " * 30,
                       "try_this": "Today: pray with your child.",
                       "reflection_prompts": ["How was it?"], "warning_flags": []}}
            for i, b in enumerate(self.briefs, 1)})
        self.cleared = set()
        monkeypatch.setattr(dp, "ROOT", tmp)
        monkeypatch.setattr(dp, "CURRICULUM", cur)
        monkeypatch.setattr(dp, "LESSON_INDEX", tmp / "docs" / "lesson_index.json")
        monkeypatch.setattr(dp, "lesson_state", self._state)

    @staticmethod
    def _put(f, doc):
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")

    def _state(self, job, draft, work, grams):
        ok = job["key"] in self.cleared
        rec = {"reviewer": "deepseek-v4-pro", "at": "t", "defects": [],
               "contains_religious_text": False}
        return {"key": job["key"], "brief": job["brief"], "accepted": ok,
                "blockers": [] if ok else ["not reviewed"], "ar_review": rec, "en_review": rec}

    def write(self, briefs=None):
        spec = {"paths": [{"path_id": self.pid, "unit_bands": ["7-9"], "lessons": [
            {"title": b, "focus": "", "keywords": []} for b in (briefs or self.briefs)]}]}
        self._put(self.spec_path, spec)
        return self.dp.write_outputs(spec, self.spec_path, self.work, {}, set())

    def path(self):
        return json.loads((self.cur / "paths" / f"{self.pid}.json").read_text(encoding="utf-8"))

    def served(self):
        out = {}
        for lid in self.path()["lesson_ids"]:
            doc = json.loads((self.cur / "lessons" / f"{lid}.json").read_text(encoding="utf-8"))
            out[doc["title"]] = (lid, doc["order"])
        return out


@pytest.fixture
def shelf(dp, tmp_path, monkeypatch):
    return _Shelf(dp, tmp_path, monkeypatch)


def test_writing_later_lessons_never_renumbers_the_ones_already_served(shelf):
    shelf.cleared = {"s01", "s02"}
    shelf.write()
    first = shelf.served()
    assert first["درسٌ جديد 1"] == ("lesson_7-9_test_worship_03", 3)
    assert first["درسٌ جديد 2"] == ("lesson_7-9_test_worship_04", 4)
    # The media index now links the first new lesson's id — a fresh allocation would
    # have moved it to the `d` fallback. A served id is reused, never re-allocated.
    shelf._put(shelf.tmp / "docs" / "lesson_index.json",
               {"lessons": [{"lesson_id": "lesson_7-9_test_worship_03"}]})
    shelf.cleared = {"s01", "s02", "s03", "s04"}
    shelf.write()
    later = shelf.served()
    for title, served in first.items():
        assert later[title] == served, title
    assert later["درسٌ جديد 4"] == ("lesson_7-9_test_worship_06", 6)
    assert shelf.path()["estimated_days"] == len(shelf.path()["lesson_ids"]) == 6


def test_only_the_contiguous_prefix_of_cleared_lessons_is_written(shelf):
    shelf.cleared = {"s01", "s03", "s04"}
    report = shelf.write()
    assert [t for t in shelf.served() if t.startswith("درسٌ جديد")] == ["درسٌ جديد 1"]
    held = {e["key"]: e.get("held_behind") for e in report["lessons"]}
    assert held == {"s01": None, "s02": None, "s03": "s02", "s04": "s02"}
    assert shelf.path()["estimated_days"] == 3
    orders = sorted(order for _, order in shelf.served().values())
    assert orders == list(range(1, 4))


def test_a_rewrite_never_withdraws_a_served_lesson(shelf):
    shelf.cleared = {"s01", "s02"}
    shelf.write()
    shelf.cleared = {"s01"}     # s02's text changed after it was served, not re-reviewed
    with pytest.raises(ValueError, match="never withdraws a served lesson"):
        shelf.write()


def test_inserting_a_lesson_before_a_served_one_is_refused(shelf):
    shelf.cleared = {"s01", "s02"}
    shelf.write()
    with pytest.raises(ValueError, match="never inserted or reordered"):
        shelf.write(briefs=["درسٌ أُدرج قبل غيره"] + shelf.briefs)


def test_an_unpublished_english_twin_stays_unpublished_and_keeps_its_place(shelf):
    """`review_en_parity.py unpublish` moves an unstamped English twin out of what the
    app loads. To _generated() the lesson must stay ours — counted as an original it
    would join the path's base and shift every later order — and a rewrite must not
    publish its English again before a review stamps it."""
    shelf.cleared = {"s01", "s02"}
    shelf.write()
    lid = shelf.served()["درسٌ جديد 1"][0]
    held = shelf.tmp / "ops" / "data" / "en_unpublished" / "lessons" / f"{lid}.json"
    held.parent.mkdir(parents=True)
    (shelf.cur / "i18n" / "en" / "lessons" / f"{lid}.json").rename(held)
    shelf.cleared = {"s01", "s02", "s03"}
    shelf.write()
    assert shelf.served()["درسٌ جديد 1"] == (lid, 3)
    assert shelf.served()["درسٌ جديد 3"] == ("lesson_7-9_test_worship_05", 5)
    assert held.exists()
    assert not (shelf.cur / "i18n" / "en" / "lessons" / f"{lid}.json").exists()
