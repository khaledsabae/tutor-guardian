"""The English-content gate: what it parses, what it stamps, and when a stamp dies.

`ops/tools/review_en_parity.py` replaced a signature nobody was ever going to
write. The schema had said from day one that `approved_by: null` means "not
reviewed, not published in English", and 424 published files carried null —
because the field waited for a human reviewer this solo project does not have.

The stamp it writes is only worth anything if three properties hold, and each
test below pins one of them:

* **A stamp names exactly what was reviewed.** `content_sha256` covers the
  Arabic *and* the English. Edit either afterwards — the translation, or the
  source it was checked against — and the stamp is stale, and `check` refuses
  the commit. Without that, the record describes a text that no longer exists:
  in August 19% of 362 stored review notes quoted English that had already been
  fixed, and the counter described the past.
* **A reviewer that says nothing has not said "clean".** glm-5.2 answered a
  batch with `{"items": []}` during calibration. Read as "no defects", that is
  five files approved by a model that looked at none of them.
* **Nothing touches the Qur'an.** A model "correcting" the orthography of an
  ayah is precisely the corruption `check_quran_citations` exists to stop.
"""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

_TOOL = Path(__file__).resolve().parents[2] / "ops" / "tools" / "review_en_parity.py"


@pytest.fixture(scope="module")
def rp():
    spec = importlib.util.spec_from_file_location("review_en_parity", _TOOL)
    module = importlib.util.module_from_spec(spec)
    # dataclasses resolve string annotations through sys.modules[cls.__module__].
    sys.modules[spec.name] = module
    argv, sys.argv = sys.argv, [sys.argv[0]]
    try:
        spec.loader.exec_module(module)
    finally:
        sys.argv = argv
    return module


@pytest.fixture()
def tree(rp, tmp_path, monkeypatch):
    """A miniature repo: one lesson in Arabic and English, one knowledge unit."""
    cur = tmp_path / "knowledge_base" / "curriculum"
    (cur / "lessons").mkdir(parents=True)
    (cur / "i18n" / "en" / "lessons").mkdir(parents=True)
    units = tmp_path / "knowledge_base" / "units"
    units.mkdir(parents=True)
    ar = {"id": "lesson_x", "title": "الصدق", "summary": "اجعل الصدق آمنًا.",
          "try_this": "امدح صدقه.", "reflection_prompts": ["متى يكذب؟"],
          "is_published": True, "approved_by": None}
    en = {**ar, "title": "Truthfulness", "summary": "Make truthfulness safe.",
          "try_this": "Praise his honesty.", "reflection_prompts": ["When does he lie?"],
          "language": "en", "translation": {"review_defects": [{"why": "stale"}],
                                            "approved_by": None}}
    (cur / "lessons" / "lesson_x.json").write_text(json.dumps(ar, ensure_ascii=False))
    (cur / "i18n" / "en" / "lessons" / "lesson_x.json").write_text(
        json.dumps(en, ensure_ascii=False))
    monkeypatch.setattr(rp, "ROOT", tmp_path)
    monkeypatch.setattr(rp, "CURRICULUM", cur)
    monkeypatch.setattr(rp, "I18N_EN", cur / "i18n" / "en")
    monkeypatch.setattr(rp, "UNITS", units)
    monkeypatch.setattr(rp, "STORIES_EN", tmp_path / "absent.json")
    return tmp_path


def _lesson(rp):
    (item,) = rp.collect_curriculum("lessons")
    return item


def _stamp(rp, item):
    rec = rp.build_record(item, ("deepseek-v4-pro", "glm-5.2"), 1, False,
                          [{"model": "glm-5.2", "field": "title", "type": "tone",
                            "why": "nuance"}], [], "2026-10-04")
    rp.write_stamp(item, rec)


# ── leaf paths ───────────────────────────────────────────────────────────

def test_paths_parse_and_round_trip(rp):
    assert rp.parse_path("pages[2].text") == ["pages", 2, "text"]
    assert rp.parse_path("bands.2-3.activities[0].title_ar") == [
        "bands", "2-3", "activities", 0, "title_ar"]
    doc = {"pages": [{"text": "a"}, {"text": "b"}]}
    rp.set_leaf(doc, "pages[1].text", "c")
    assert rp.get_leaf(doc, "pages[1].text") == "c"
    assert rp.get_leaf(doc, "pages[9].text") is None


@pytest.mark.parametrize("bad", ["", ".a", "a.", "a..b", "a[x]"])
def test_malformed_path_is_refused_not_guessed(rp, bad):
    with pytest.raises(ValueError):
        rp.parse_path(bad)


def test_set_leaf_never_invents_structure(rp):
    with pytest.raises(KeyError):
        rp.set_leaf({"a": {}}, "b.c", 1)


def test_missing_story_fields_get_their_parent_built(rp):
    # The English stories predate discussionQuestions; the fixer fills them in.
    story = {"id": "s", "pages": []}
    rp._ensure_parent(story, "discussionQuestions[2]")
    rp.set_leaf(story, "discussionQuestions[2]", "Why?")
    assert story["discussionQuestions"] == [None, None, "Why?"]


def test_walk_skips_structural_keys_and_reports_missing_english(rp):
    ar = {"id": "x", "image": "a.png", "title": "عنوان", "pages": [{"text": "نص"}],
          "discussionQuestions": ["لماذا؟"]}
    en = {"id": "x", "image": "a.png", "title": "Title", "pages": [{"text": "Text"}]}
    pairs = {p: e for p, _a, e in rp.walk_text_pairs(ar, en)}
    assert pairs == {"title": "Title", "pages[0].text": "Text",
                     "discussionQuestions[0]": None}


# ── the fingerprint ──────────────────────────────────────────────────────

def test_sha_ignores_key_order_and_sees_either_language(rp):
    f1 = {"t": {"ar": "سكينة", "en": "tranquility"}, "s": {"ar": "أ", "en": "A"}}
    f2 = {"s": {"ar": "أ", "en": "A"}, "t": {"ar": "سكينة", "en": "tranquility"}}
    assert rp.content_sha(f1) == rp.content_sha(f2)
    # The case that motivated binding the stamp to the Arabic too: «سفينة»
    # for «سكينة» left the English fluent and the source corrupt.
    f3 = {"t": {"ar": "سفينة", "en": "tranquility"}, "s": {"ar": "أ", "en": "A"}}
    f4 = {"t": {"ar": "سكينة", "en": "tranquility."}, "s": {"ar": "أ", "en": "A"}}
    assert rp.content_sha(f1) != rp.content_sha(f3)
    assert rp.content_sha(f1) != rp.content_sha(f4)


# ── the stamp ────────────────────────────────────────────────────────────

def test_stamp_round_trips_including_tagged_model_names(rp):
    s = rp.stamp_value(("deepseek-v4-pro", "glm-5.2"), "2026-10-04")
    assert s == "auto-review:deepseek-v4-pro+glm-5.2:2026-10-04"
    assert rp.parse_stamp(s) == {"reviewers": ["deepseek-v4-pro", "glm-5.2"],
                                 "date": "2026-10-04"}
    tagged = rp.stamp_value(("mistral-large-3:675b", "glm-5.2"), "2026-10-04")
    assert rp.parse_stamp(tagged)["reviewers"] == ["mistral-large-3:675b", "glm-5.2"]


@pytest.mark.parametrize("bad", [None, "", "Sheikh Ahmad", "auto-review:a:2026-10-04",
                                 "auto-review:a+b:2026-13-40", "auto-review:a+b"])
def test_non_stamps_do_not_parse(rp, bad):
    assert rp.parse_stamp(bad) is None


def test_unstamped_published_english_fails_the_gate(rp, tree):
    assert "approved_by: null" in rp.check_item(_lesson(rp))


def test_stamp_passes_the_gate_and_replaces_stale_review_notes(rp, tree):
    _stamp(rp, _lesson(rp))
    item = _lesson(rp)
    assert rp.check_item(item) is None
    doc = json.loads(item.en_file.read_text())
    stamp = "auto-review:deepseek-v4-pro+glm-5.2:2026-10-04"
    # Curriculum overlays carry approved_by twice (root copy + translation record).
    assert doc["approved_by"] == stamp
    assert doc["translation"]["approved_by"] == stamp
    assert doc["translation"]["auto_review"]["content_sha256"] == item.sha
    # The August notes described text that no longer exists; they go.
    assert doc["translation"]["review_defects"] == [
        {"model": "glm-5.2", "field": "title", "type": "tone", "why": "nuance"}]
    assert doc["translation"]["review_verdict"] == "low_only"


@pytest.mark.parametrize("side,value", [
    ("en", "Make honesty safe."),     # translation edited after review
    ("ar", "اجعل الصدق آمنا جدًا."),   # the SOURCE edited after review
])
def test_any_edit_after_review_makes_the_stamp_stale(rp, tree, side, value):
    _stamp(rp, _lesson(rp))
    sub = "i18n/en/lessons" if side == "en" else "lessons"
    f = tree / "knowledge_base" / "curriculum" / sub / "lesson_x.json"
    doc = json.loads(f.read_text())
    doc["summary"] = value
    f.write_text(json.dumps(doc, ensure_ascii=False))
    assert "stale" in rp.check_item(_lesson(rp))


def test_a_human_signature_is_accepted_as_written(rp, tree):
    f = tree / "knowledge_base" / "curriculum" / "i18n/en/lessons/lesson_x.json"
    doc = json.loads(f.read_text())
    doc["translation"]["approved_by"] = "Sheikh Ahmad"
    f.write_text(json.dumps(doc, ensure_ascii=False))
    assert rp.check_item(_lesson(rp)) is None


def test_unpublished_and_untranslated_need_no_stamp(rp, tree):
    item = _lesson(rp)
    item.published = False
    assert rp.check_item(item) is None
    copy = _lesson(rp)
    for v in copy.fields.values():
        v["en"] = v["ar"]          # an English file that is the Arabic verbatim
    assert rp.check_item(copy) is None


def test_unpublish_moves_the_file_and_records_why(rp, tree, monkeypatch):
    monkeypatch.setattr(rp, "UNPUBLISHED", tree / "ops" / "data" / "en_unpublished")
    with pytest.raises(SystemExit):
        rp.cmd_unpublish([_lesson(rp)], "")      # no reason, no move
    rp.cmd_unpublish([_lesson(rp)], "meaning reversed in summary")
    assert not (tree / "knowledge_base/curriculum/i18n/en/lessons/lesson_x.json").exists()
    manifest = json.loads((tree / "ops/data/en_unpublished/MANIFEST.json").read_text())
    assert manifest[0]["reason"] == "meaning reversed in summary"


# ── reading the reviewers ────────────────────────────────────────────────

def _chunks(rp, tree):
    return rp.chunks_of(_lesson(rp), 7000)


def test_an_empty_answer_is_not_a_clean_answer(rp, tree):
    batch = _chunks(rp, tree)
    assert rp.parse_review('```json\n{"items": []}\n```', batch) == {}
    assert rp.parse_review("not json", batch) is None


def test_review_parsing_normalises_severity_conservatively(rp, tree):
    batch = _chunks(rp, tree)
    raw = json.dumps({"items": [{"id": "lesson_x", "defects": [
        {"field": "summary", "side": "Arabic", "type": "source_corruption",
         "severity": "CRITICAL!!", "why": "x"},
        {"field": "title", "side": "english", "severity": "low", "why": "y"}]}]})
    (d1, d2) = rp.parse_review(raw, batch)["lesson_x"]
    assert d1["severity"] == "medium" and d1["side"] == "arabic"   # unknown → blocking
    assert d2["severity"] == "low" and d2["side"] == "english"


def test_large_units_are_split_and_batches_respect_the_budget(rp):
    item = rp.Item("adhkar", "adhkar:x", Path("en"), Path("ar"),
                   {f"items[{i}].text": {"ar": "أ" * 100, "en": "a" * 100} for i in range(10)})
    chunks = rp.chunks_of(item, 450)
    assert len(chunks) == 5 and chunks[0].cid == "adhkar:x#0"
    assert all(len(b) <= 2 for b in rp.batches_of(chunks, 900, 12))


def test_blocking_honours_only_adjudications_bound_to_this_text(rp, tree):
    item = _lesson(rp)
    v = rp.Verdict(item, defects={"glm-5.2": [
        {"field": "summary", "type": "hadith", "severity": "medium", "side": "arabic",
         "why": "w"}]})
    good = {"lesson_x": {"content_sha256": item.sha, "overrides": [
        {"field": "summary", "type": "hadith", "reason": "source honestly named"}]}}
    stale = {"lesson_x": {"content_sha256": "0" * 64, "overrides": [
        {"field": "summary", "type": "hadith", "reason": "source honestly named"}]}}
    unreasoned = {"lesson_x": {"content_sha256": item.sha, "overrides": [
        {"field": "summary", "type": "hadith", "reason": ""}]}}
    assert v.blocking(rp.adjudicated_for(item, good)) == []
    assert len(v.blocking(rp.adjudicated_for(item, stale))) == 1
    assert len(v.blocking(rp.adjudicated_for(item, unreasoned))) == 1


# ── deterministic gates ──────────────────────────────────────────────────

def test_arabic_left_in_english_is_leakage_except_where_it_belongs(rp):
    assert rp.leaked_arabic("Be gentle ﷺ ﴿وَقُل رَّبِّ﴾ «خيركم»") == ""
    assert rp.leaked_arabic("تربية الأولاد في الإسلام") != ""


def test_deterministic_layer_catches_what_actually_shipped(rp):
    def item(ar, en):
        return rp.Item("kb_units", "k", Path("en"), Path("ar"), {"text": {"ar": ar, "en": en}})
    types = lambda it: {d["type"] for d in rp.deterministic_defects(it)}  # noqa: E731
    # aqe-b1e103fc, 2026-08-15: an isnad the Arabic never carried.
    assert "hadith" in types(item(
        "وقال النبي ﷺ: «من مات وهو يعلم أن لا إله إلا الله دخل الجنة».",
        "The Prophet said: 'Whoever dies knowing there is no god but Allah will "
        "enter Paradise.' (Narrated by al-Bukhari)"))
    # رحمة rendered as rifq — the injection that happened 34 times.
    assert "term_injection" in types(item("عامل طفلك برحمة", "Treat your child with rifq"))
    assert "leakage" in types(item("نص", "Text \u6587\u5b57"))  # CJK, escaped: guards scan source
    assert "omission" in types(item("نص", None))
    assert types(item("عامل طفلك برحمة", "Treat your child with mercy")) == set()


@pytest.mark.parametrize("old,new,ok", [
    ("ما القصة التي أثرت בו أكثر؟", "ما القصة التي أثرت فيه أكثر؟", True),
    ("قال تعالى ﴿وَقُل رَّبِّ ارْحَمْهُمَا﴾", "قال تعالى ﴿وقل رب ارحمهما﴾", False),
    (["أ", "ب"], ["أ"], False),
])
def test_arabic_fixes_never_touch_an_ayah(rp, old, new, ok):
    assert (rp.arabic_change_problem(old, new) is None) is ok


def test_self_tests_pass(rp):
    assert rp._self_test()


# ── writing without collateral damage ────────────────────────────────────
# Other agents edit these files in parallel. A fix to one Arabic word must be a
# one-line diff, not a re-serialised file that conflicts with everything.

def test_arabic_fix_is_a_literal_edit_that_keeps_the_file_format(rp, tmp_path):
    ar = tmp_path / "unit.json"
    ar.write_text('{"id": "u", "keywords": ["أ","ب"], "text": "أثرت בו أكثر"}',
                  encoding="utf-8")                      # compact, no final newline
    item = rp.Item("kb_units", "u__en", tmp_path / "u__en.json", ar,
                   {"text": {"ar": "أثرت בו أكثر", "en": "affected him most"}})
    rp.apply_arabic(item, {"text": "أثرت فيه أكثر"})
    assert ar.read_text(encoding="utf-8") == \
        '{"id": "u", "keywords": ["أ","ب"], "text": "أثرت فيه أكثر"}'
    assert item.fields["text"]["ar"] == "أثرت فيه أكثر"


def test_arabic_fix_refuses_an_ambiguous_target(rp, tmp_path):
    ar = tmp_path / "unit.json"
    ar.write_text('{"a": "نص", "b": "نص"}', encoding="utf-8")
    item = rp.Item("kb_units", "u__en", tmp_path / "x.json", ar,
                   {"a": {"ar": "نص", "en": "text"}})
    with pytest.raises(ValueError):
        rp.apply_arabic(item, {"a": "نصّ"})
    assert ar.read_text(encoding="utf-8") == '{"a": "نص", "b": "نص"}'


@pytest.mark.parametrize("ending", ["\n", ""])
def test_rewrites_keep_the_final_newline_as_it_was(rp, tmp_path, ending):
    f = tmp_path / "pack.json"
    f.write_text('{\n  "a": 1\n}' + ending, encoding="utf-8")
    rp._dump(f, {"a": 2})
    assert f.read_text(encoding="utf-8") == '{\n  "a": 2\n}' + ending


def test_the_commit_answers_for_what_it_touches_source_included(rp, tree):
    item = _lesson(rp)
    assert rp.touched_by(item, {"knowledge_base/curriculum/i18n/en/lessons/lesson_x.json"})
    # Editing only the Arabic still invalidates the English stamp.
    assert rp.touched_by(item, {"knowledge_base/curriculum/lessons/lesson_x.json"})
    assert not rp.touched_by(item, {"knowledge_base/curriculum/lessons/other.json"})


def test_a_prefixed_field_path_still_reaches_the_fixer(rp):
    # glm-5.2 writes "fields.text"; left as is, the defect blocks the stamp but
    # never reaches the fixer, and the unit hangs with neither.
    valid = {"text", "pages[0].text"}
    assert rp.canon_field("fields.text", valid) == "text"
    assert rp.canon_field("fields[pages[0].text]", valid) == "pages[0].text"
    assert rp.canon_field("text", valid) == "text"
    assert rp.canon_field("summary", valid) == "summary"   # unknown stays visible


def test_an_account_cap_is_told_apart_from_a_burst_limit(rp):
    # The body Ollama Cloud actually returned on 2026-10-04, mid-run.
    cap = ('{"error":{"message":"You reached your Pro 5-hour limit. Max is $100/month '
           'for $300 of usage, with no 5-hour or weekly caps"}}')
    assert rp._is_usage_cap(cap)
    assert not rp._is_usage_cap('{"error": "Too Many Requests"}')
