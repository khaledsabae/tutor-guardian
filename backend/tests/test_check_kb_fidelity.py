"""KB fidelity guard (ops/tools/check_kb_fidelity.py).

The assistant cites a unit's `text_simplified` as evidence; nobody compared it
with the unit's own `text_original` until 2026-10-04, when 210 units were
withdrawn for summaries written over reversed-letter PDF text. These tests pin
the two things that must keep holding:

  * the detector still sees the extraction failures and invented claims it was
    built on (its self-tests, plus real shapes here), and
  * the guard refuses a withdrawn unit coming back (by path, by id under another
    file name, by translation — the b1100ae2 regression) and a flagged unit that
    nobody judged on its current text — run end to end on a scratch tree.
"""
import importlib.util
import json
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _load():
    spec = importlib.util.spec_from_file_location("check_kb_fidelity", ROOT / "ops" / "tools" / "check_kb_fidelity.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["check_kb_fidelity"] = mod
    spec.loader.exec_module(mod)
    return mod


fid = _load()

FWD = fid._FWD_SAMPLE
LOADER = 'EXCLUDED_SOURCES = (\n    "gov.pdf",\n)\n'


def test_self_tests_pass():
    assert fid.self_test() == []


def test_repository_guard_is_green():
    """The committed state: quarantine holds, every flagged live unit has a verdict."""
    assert fid.cmd_check() == 0


def test_extraction_shapes():
    assert fid.source_flags(FWD)[0] == []
    assert "reversed" in fid.source_flags(fid._visual_order(FWD))[0]
    assert "glyph_substituted" in fid.source_flags(fid._visual_order(fid._mylotus(FWD)))[0]
    # The reversed source still *contains* the Prophet ﷺ — de-reversed, it is evidence.
    src = fid._visual_order("وكان النبي صلى الله عليه وسلم يمازح الصغار ويعلمهم الصدق. " * 3)
    assert "introduces_prophet" not in fid.claim_flags("كان النبي ﷺ يمازح الصغار.", src)


def test_invented_claims_are_flagged():
    src = "ينبغي للوالدين أن يعلما الطفل الصدق بالقدوة والحوار، وأن يكافئا السلوك الحسن. " * 3
    flags = fid.claim_flags("قال النبي ﷺ لابن عمر رضي الله عنهما: ينام الطفل 14 ساعة.", src)
    assert {"introduces_prophet", "introduces_companion", "introduces_number"} <= set(flags)
    assert "meta_framing" in fid.meta_flags("النص يتحدث عن أهمية الصلاة.")


# ── the guard end to end, on a scratch repository ──────────────────────────


def _unit(uid: str, **kw) -> dict:
    return {"id": uid, "title": "عنوان", "text_simplified": "شجّع طفلك على الحوار.", "text_original": FWD, **kw}


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    units = tmp_path / "knowledge_base" / "units"
    units.mkdir(parents=True)
    (tmp_path / "backend" / "app" / "services").mkdir(parents=True)
    (tmp_path / "backend" / "app" / "services" / "knowledge_loader.py").write_text(LOADER, encoding="utf-8")
    archive = tmp_path / "ops" / "data" / "en_unpublished" / "kb_units_source"
    archive.mkdir(parents=True)
    (tmp_path / "ops" / "data" / "kb_fidelity").mkdir(parents=True)

    (units / "dev-good.json").write_text(json.dumps(_unit("dev-good")), encoding="utf-8")
    bad = _unit("isl-bad", text_simplified="قصة مخترعة.", text_original=fid._visual_order(FWD))
    (archive / "isl-bad.json").write_text(json.dumps(bad, ensure_ascii=False), encoding="utf-8")
    (tmp_path / "ops" / "data" / "en_unpublished" / "MANIFEST.json").write_text(json.dumps([
        {"key": "isl-bad", "kind": "kb_units", "from": "knowledge_base/units/isl-bad.json",
         "to": "ops/data/en_unpublished/kb_units_source/isl-bad.json", "reason": "t", "on": "2026-10-04"}]),
        encoding="utf-8")
    _write(tmp_path, "quarantined.json", {"units": [
        {"id": "isl-bad", "category": "unfaithful", "on": "2026-10-04",
         "files": [{"from": "knowledge_base/units/isl-bad.json",
                    "to": "ops/data/en_unpublished/kb_units_source/isl-bad.json"}]}]})
    _write(tmp_path, "judged_faithful.json", {"units": {}})
    (tmp_path / "knowledge_base" / "units_index.json").write_text(
        json.dumps({"total_units": 1, "units": [{"id": "dev-good"}]}), encoding="utf-8")
    return tmp_path


def _write(root: Path, name: str, doc) -> None:
    (root / "ops" / "data" / "kb_fidelity" / name).write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")


def test_clean_scratch_repo_passes(repo):
    assert fid.cmd_check(repo) == 0


def test_withdrawn_unit_back_at_its_path_fails(repo):
    shutil.copy(repo / "ops/data/en_unpublished/kb_units_source/isl-bad.json", repo / "knowledge_base/units/isl-bad.json")
    assert fid.cmd_check(repo) == 1


def test_withdrawn_unit_back_under_another_name_or_as_translation_fails(repo):
    (repo / "knowledge_base/units/isl-bad-v2.json").write_text(json.dumps(_unit("isl-bad")), encoding="utf-8")
    assert fid.cmd_check(repo) == 1
    (repo / "knowledge_base/units/isl-bad-v2.json").unlink()
    (repo / "knowledge_base/units/isl-bad__en.json").write_text(
        json.dumps({"id": "isl-bad__en", "title": "t", "text_simplified": "An invented story."}), encoding="utf-8")
    assert fid.cmd_check(repo) == 1


def test_withdrawn_id_left_in_units_index_fails(repo):
    (repo / "knowledge_base/units_index.json").write_text(
        json.dumps({"total_units": 2, "units": [{"id": "dev-good"}, {"id": "isl-bad"}]}), encoding="utf-8")
    assert fid.cmd_check(repo) == 1


def test_flagged_unit_needs_a_verdict_bound_to_its_text(repo):
    unit = _unit("isl-rev", text_original=fid._visual_order(FWD))
    path = repo / "knowledge_base/units/isl-rev.json"
    path.write_text(json.dumps(unit, ensure_ascii=False), encoding="utf-8")
    assert fid.cmd_check(repo) == 1                       # flagged, never judged

    _write(repo, "judged_faithful.json", {"units": {"isl-rev": {"fingerprint": fid.unit_fingerprint(unit)}}})
    assert fid.cmd_check(repo) == 0                       # judged on this exact text

    unit["text_simplified"] = "شجّع طفلك على الحوار كل يوم."
    path.write_text(json.dumps(unit, ensure_ascii=False), encoding="utf-8")
    assert fid.cmd_check(repo) == 1                       # edited → verdict no longer holds


def test_excluded_source_is_out_of_scope(repo):
    unit = _unit("med-gov", source_file="gov.pdf", text_original=fid._visual_order(FWD))
    (repo / "knowledge_base/units/med-gov.json").write_text(json.dumps(unit, ensure_ascii=False), encoding="utf-8")
    assert fid.cmd_check(repo) == 0


def test_is_published_false_does_not_hide_a_unit(repo):
    """The loader reads only EXCLUDED_SOURCES: a «hidden» unit would still be cited."""
    (repo / "knowledge_base/units/dev-hidden.json").write_text(
        json.dumps(_unit("dev-hidden", is_published=False)), encoding="utf-8")
    assert fid.cmd_check(repo) == 1


def test_missing_records_break_the_check_not_pass_it(repo):
    (repo / "ops/data/kb_fidelity/judged_faithful.json").unlink()
    assert fid.cmd_check(repo) == 2


# ── the committed records ──────────────────────────────────────────────────


def _record() -> list[dict]:
    return json.loads((ROOT / "ops/data/kb_fidelity/quarantined.json").read_text(encoding="utf-8"))["units"]


def test_quarantine_record_is_ordered_by_production_retrieval():
    rec = _record()
    assert rec, "the quarantine record is empty"
    counts = [e["retrieved"] for e in rec]
    assert counts == sorted(counts, reverse=True)
    assert all(e["reason"] and e["category"] in {"unfaithful", "meta_note"} for e in rec)


def _cited_ids(node):
    if isinstance(node, dict):
        for k, v in node.items():
            if k == "unit_ids" and isinstance(v, list):
                yield from v
            elif k in ("unit_id", "source_unit_id") and isinstance(v, str):
                yield v
            else:
                yield from _cited_ids(v)
    elif isinstance(node, list):
        for v in node:
            yield from _cited_ids(v)


def test_no_surface_cites_a_withdrawn_unit():
    """Programmes, lessons, tips (AR and EN) and the eval set ground on knowledge units;
    none may rest on a withdrawn one — a dangling reference is a claim with no basis."""
    withdrawn = {e["id"] for e in _record()}
    for f in sorted((ROOT / "knowledge_base" / "curriculum").rglob("*.json")):
        if "schema" in f.parts:
            continue
        cited = set(_cited_ids(json.loads(f.read_text(encoding="utf-8"))))
        assert not cited & withdrawn, f"{f.relative_to(ROOT)} cites withdrawn units {sorted(cited & withdrawn)}"
    for line in (ROOT / "ops" / "eval" / "golden_set.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            item = json.loads(line)
            assert not set(item.get("expected_unit_ids") or []) & withdrawn, item["id"]


# Rewritten on purpose in PR #27 (70f2df67, 3ab8dae1, 2224ade1) and reviewed there:
# the app's own guidance, not summaries of their PDF chunks. The discipline guard
# hands everything it does not claim to the model, which must be able to retrieve
# the app's stated position on hitting and the 7/10 narration — so these stay served.
AUTHORED = ("isl-c4d83813", "isl-af807518", "isl-602bfb05", "isl-901bde3f", "isl-24dda124")


@pytest.mark.parametrize("uid", AUTHORED)
def test_trust_content_rewrites_stay_served_with_honest_provenance(uid):
    path = ROOT / "knowledge_base" / "units" / f"{uid}.json"
    assert path.exists(), f"{uid} must stay served"
    assert uid not in {e["id"] for e in _record()}
    unit = json.loads(path.read_text(encoding="utf-8"))
    assert unit.get("source_kind") == "authored_guidance"
    assert unit.get("authored_references") and unit.get("source_note")
    assert "الألوكة" not in unit.get("reference_info", "") and "كيف تربي ولدك" != unit.get("reference_info")
    ledger = json.loads((ROOT / "ops/data/kb_fidelity/judged_faithful.json").read_text(encoding="utf-8"))["units"]
    assert ledger[uid]["fingerprint"] == fid.unit_fingerprint(unit)
