"""Units awaiting a scholar's review are not indexed or served (167-F).

The seven parent-doubts units carry `translation.draft_status == "awaiting-review"`.
Merging them must not put unapproved text in front of a parent: the loader — the
one door to the index, BM25, the answer-cache fingerprint and retrieval — skips
them unless TG_ALLOW_DRAFT_UNITS is set. Legacy units (no field, or the older
"draft" value) are unaffected. Publishing = flipping the status after sign-off.
"""
import json

import pytest

from app.services import knowledge_loader as kl

_BASE = {
    "domain": "aqeedah", "language": "ar", "age_group": "7-9",
    "behavior_type": "x", "intervention_type": "إرشادي", "severity": "خفيف",
    "reference_type": "حديث", "reference_info": "القرآن الكريم: فصلت ٤٦",
    "text_original": "t", "text_simplified": "نص", "title": "عنوان",
}


def _write(dir_path, uid, **extra):
    (dir_path / f"{uid}.json").write_text(
        json.dumps({**_BASE, "id": uid, **extra}, ensure_ascii=False), encoding="utf-8")


@pytest.fixture
def units_dir(tmp_path, monkeypatch):
    monkeypatch.delenv(kl.ALLOW_DRAFTS_ENV, raising=False)
    _write(tmp_path, "legacy-1")                                   # no field at all
    _write(tmp_path, "legacy-draft-1", translation={"draft_status": "draft"})
    _write(tmp_path, "approved-1", translation={"draft_status": "approved"})
    _write(tmp_path, "pending-1", translation={"draft_status": "awaiting-review"})
    _write(tmp_path, "pending-top-1", draft_status="awaiting-review")
    served = next(iter(kl.SERVED_BEFORE_GATE))
    _write(tmp_path, served, translation={"draft_status": "awaiting-review"})
    return tmp_path, served


def _ids(path):
    return {u.id for u in kl.load_knowledge_units_from_dir(path)}


def test_legacy_units_load(units_dir):
    path, _ = units_dir
    ids = _ids(path)
    assert {"legacy-1", "legacy-draft-1", "approved-1"} <= ids


def test_draft_unit_is_skipped_by_default(units_dir):
    path, _ = units_dir
    ids = _ids(path)
    assert "pending-1" not in ids
    assert "pending-top-1" not in ids  # top-level field is honoured too


def test_flag_lets_drafts_load(units_dir, monkeypatch):
    path, _ = units_dir
    for value in ("1", "true", "YES"):
        monkeypatch.setenv(kl.ALLOW_DRAFTS_ENV, value)
        assert {"pending-1", "pending-top-1"} <= _ids(path)
    monkeypatch.setenv(kl.ALLOW_DRAFTS_ENV, "0")
    assert "pending-1" not in _ids(path)


def test_unit_already_served_before_the_gate_is_not_withdrawn(units_dir):
    path, served = units_dir
    assert served in _ids(path)


def test_flipping_the_status_publishes(units_dir):
    path, _ = units_dir
    assert "pending-1" not in _ids(path)
    _write(path, "pending-1", translation={"draft_status": "approved"})
    assert "pending-1" in _ids(path)


def test_the_real_corpus_gates_exactly_the_parent_doubts_drafts(monkeypatch):
    """Every awaiting-review unit on disk is held back, except the grandfathered
    one; nothing else (no legacy unit) disappears because of the gate."""
    monkeypatch.delenv(kl.ALLOW_DRAFTS_ENV, raising=False)
    disk = {}
    for f in sorted((kl.BASE_DIR / "units").glob("*.json")):
        disk[f.stem] = json.loads(f.read_text(encoding="utf-8"))
    gated = {i for i, d in disk.items() if kl._is_unpublished_draft(d)}
    assert gated, "no draft unit found — the gate matches nothing"
    assert all((disk[i].get("translation") or {}).get("draft_status") == "awaiting-review"
               for i in gated)

    default = {u.id for u in kl.load_default_knowledge_units()}
    assert not gated & default, "an unapproved draft is being served"
    monkeypatch.setenv(kl.ALLOW_DRAFTS_ENV, "1")
    with_drafts = {u.id for u in kl.load_default_knowledge_units()}
    assert gated <= with_drafts, "the flag does not bring the drafts back"
    assert with_drafts - default == gated, "the gate removed something besides the drafts"


def test_no_unit_shows_draft_status_in_reference_info():
    """167-E: reference_info is shown to parents verbatim (reply_sources) — it
    carries the citation list only. Draft status lives in translation/source_note."""
    bad = []
    for f in sorted((kl.BASE_DIR / "units").glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        for field in ("reference_info", "authored_references"):
            text = json.dumps(d.get(field), ensure_ascii=False)
            if "مسودة" in text or "draft" in text.lower():
                bad.append(f"{f.stem}:{field}")
    for f in sorted((kl.BASE_DIR.parent / "ops/data/en_parity_pending/parent-doubts-units").glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        for field in ("reference_info", "authored_references"):
            text = json.dumps(d.get(field), ensure_ascii=False)
            if "مسودة" in text or "draft" in text.lower():
                bad.append(f"{f.stem}:{field}")
    assert not bad, f"draft-status text in a served citation field: {bad}"
