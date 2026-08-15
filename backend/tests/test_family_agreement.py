"""The agreement is two-sided or it is not an agreement.

Most of these assert that half-formed agreements are refused: one that binds
only the child, one signed by a child who has not read it, one that never got
a second signature. The gate downstream keys on `has_active_agreement`, so
every way of accidentally producing a true there is a way of opening the child
surface on nothing.
"""
import json

import pytest

from app.db.init_db import get_conn
from app.services import family_agreement as fa

DEVICE = "dev-agreement-1"


@pytest.fixture
def child():
    def make(age_group: str = "7-9") -> int:
        conn = get_conn()
        try:
            cur = conn.execute(
                "INSERT INTO child_profiles (device_id, name, age_group) VALUES (?, ?, ?)",
                (DEVICE, "أحمد", age_group),
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()
    return make


def _two_sided():
    return [
        {"applies_to": "child", "text_ar": "مافيش جهاز على السفرة", "clause_key": "t"},
        {"applies_to": "parent", "text_ar": "مافيش جهاز على السفرة — عليّ أنا كمان",
         "clause_key": "t"},
    ]


# ── The clause bank ────────────────────────────────────────────────────────

def test_the_shipped_bank_pairs_every_child_clause_with_a_parent_one():
    """The rule the whole feature rests on. A bank that drifts into one-sided
    clauses would produce one-sided agreements by default."""
    pairs = fa.load_clause_bank("7-9")
    assert pairs, "no clause bank for 7-9"
    for pair in pairs:
        assert pair.get("child"), f"{pair.get('key')} has no child clause"
        assert pair.get("parent"), f"{pair.get('key')} has no parent clause"


def test_the_bank_includes_the_clause_that_makes_reporting_possible():
    """«أسمع من غير ما أزعّق» is the price that makes «أقول لبابا» real. A
    child who expects the device confiscated does not report."""
    keys = {p["key"] for p in fa.load_clause_bank("7-9")}
    assert "tell_when_uncomfortable" in keys


def test_suggestions_keep_each_pair_adjacent():
    rows = fa.suggested_clauses("7-9")
    assert rows
    for i in range(0, len(rows) - 1, 2):
        assert rows[i]["applies_to"] == "child"
        assert rows[i + 1]["applies_to"] == "parent"
        assert rows[i]["clause_key"] == rows[i + 1]["clause_key"]


def test_an_unknown_band_yields_nothing_rather_than_raising():
    assert fa.load_clause_bank("99-100") == []
    assert fa.suggested_clauses("99-100") == []


def test_the_bank_file_is_valid_and_published():
    path = fa.CLAUSES_DIR / "clauses_7-9.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["is_published"] is True
    assert data["age_band"] == "7-9"


# ── Drafting refuses one-sided agreements ──────────────────────────────────

def test_a_draft_with_nothing_on_the_parent_is_refused(child):
    cid = child()
    result = fa.save_draft(DEVICE, cid, [
        {"applies_to": "child", "text_ar": "مافيش جهاز على السفرة"},
        {"applies_to": "child", "text_ar": "الجهاز يبات برّه"},
    ])
    assert result["ok"] is False
    assert result["reason"] == "nothing_on_the_parent"


def test_a_draft_with_nothing_on_the_child_is_refused(child):
    cid = child()
    result = fa.save_draft(DEVICE, cid, [
        {"applies_to": "parent", "text_ar": "مافيش جهاز على السفرة"},
    ])
    assert result["ok"] is False
    assert result["reason"] == "nothing_on_the_child"


def test_a_both_clause_satisfies_both_sides(child):
    cid = child()
    result = fa.save_draft(DEVICE, cid, [
        {"applies_to": "both", "text_ar": "مافيش جهاز على السفرة"},
    ])
    assert result["ok"] is True


def test_empty_and_malformed_clauses_are_dropped(child):
    cid = child()
    result = fa.save_draft(DEVICE, cid, [
        {"applies_to": "child", "text_ar": "   "},
        {"applies_to": "nobody", "text_ar": "بند غامض"},
        *_two_sided(),
    ])
    assert result["ok"] is True
    assert len(result["agreement"]["clauses"]) == 2


def test_redrafting_replaces_rather_than_appends(child):
    cid = child()
    fa.save_draft(DEVICE, cid, _two_sided())
    again = fa.save_draft(DEVICE, cid, _two_sided())
    assert len(again["agreement"]["clauses"]) == 2


# ── Signing ────────────────────────────────────────────────────────────────

def _draft_and_ack(cid):
    draft = fa.save_draft(DEVICE, cid, _two_sided())
    for c in draft["agreement"]["clauses"]:
        if c["applies_to"] in ("child", "both"):
            fa.acknowledge_clause(DEVICE, cid, c["id"])
    return draft


def test_a_child_cannot_sign_what_they_have_not_read(child):
    cid = child()
    fa.save_draft(DEVICE, cid, _two_sided())
    result = fa.sign(DEVICE, cid, "child")
    assert result["ok"] is False
    assert result["reason"] == "clauses_not_acknowledged"
    assert result["remaining"] == 1


def test_one_signature_is_not_an_agreement(child):
    cid = child()
    _draft_and_ack(cid)
    assert fa.sign(DEVICE, cid, "parent")["activated"] is False
    assert fa.has_active_agreement(DEVICE, cid) is False


def test_both_signatures_activate_it(child):
    cid = child()
    _draft_and_ack(cid)
    fa.sign(DEVICE, cid, "parent")
    result = fa.sign(DEVICE, cid, "child")
    assert result["activated"] is True
    assert result["agreement"]["status"] == "active"
    assert result["agreement"]["next_review_date"]
    assert fa.has_active_agreement(DEVICE, cid) is True


def test_redrafting_an_agreement_clears_both_signatures(child):
    """Changing the terms after signing must not inherit consent to the old
    ones."""
    cid = child()
    _draft_and_ack(cid)
    fa.sign(DEVICE, cid, "parent")
    fa.save_draft(DEVICE, cid, _two_sided())
    current = fa.get_current(DEVICE, cid)
    assert current["signed_by_parent_at"] is None
    assert current["signed_by_child_at"] is None


def test_a_new_agreement_archives_the_old_one(child):
    cid = child()
    _draft_and_ack(cid)
    fa.sign(DEVICE, cid, "parent")
    fa.sign(DEVICE, cid, "child")

    _draft_and_ack(cid)
    fa.sign(DEVICE, cid, "parent")
    second = fa.sign(DEVICE, cid, "child")

    conn = get_conn()
    try:
        active = conn.execute(
            "SELECT COUNT(*) AS n FROM family_agreements WHERE child_id = ? "
            "AND status = 'active'", (cid,),
        ).fetchone()["n"]
        archived = conn.execute(
            "SELECT COUNT(*) AS n FROM family_agreements WHERE child_id = ? "
            "AND status = 'archived'", (cid,),
        ).fetchone()["n"]
    finally:
        conn.close()
    assert active == 1
    assert archived == 1
    assert second["agreement"]["version"] == 2


def test_signing_without_a_draft_is_refused(child):
    cid = child()
    assert fa.sign(DEVICE, cid, "parent")["reason"] == "no_draft"


def test_an_unknown_signer_is_refused(child):
    cid = child()
    _draft_and_ack(cid)
    assert fa.sign(DEVICE, cid, "teacher")["reason"] == "unknown_signer"


def test_another_devices_clause_cannot_be_acknowledged(child):
    cid = child()
    draft = fa.save_draft(DEVICE, cid, _two_sided())
    clause_id = draft["agreement"]["clauses"][0]["id"]
    assert fa.acknowledge_clause("someone-else", cid, clause_id)["ok"] is False


def test_no_agreement_means_no_active_agreement(child):
    assert fa.has_active_agreement(DEVICE, child()) is False
