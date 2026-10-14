"""A weekly plan you can tick (نور والقناديل, Phase 3) — schema v36's
`weekly_plan_marks` behind PUT/DELETE /api/children/{id}/weekly-plan/marks
and the additive `marks` list on GET /api/children/{id}/weekly-plan.

A mark is a positive step taken: there is no "missed" state, un-marking is a
DELETE of the row, and every privacy path that forgets the plan forgets its
marks too (memory erase, child deletion, account deletion).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app import curriculum_loader as cl
from app.db.init_db import get_conn
from app.services import weekly_plan as wp
from tests.device_proof_support import prove


@pytest.fixture(scope="module", autouse=True)
def _curriculum():
    cl.load_curriculum()
    wp._load.cache_clear()


@pytest.fixture
def client():
    from app.main import app
    with TestClient(app) as c:
        yield c


def _auth(client, device: str) -> dict:
    tok = client.post("/api/chat/sessions", json={"device_id": device}).json()["token"]
    return {"Authorization": f"Bearer {tok}"}


def _child(client, h, name: str = "سالم", age: str = "7-9") -> int:
    return client.post("/api/children", json={"name": name, "age_group": age},
                       headers=h).json()["id"]


def _plan(client, h, cid) -> dict:
    r = client.get(f"/api/children/{cid}/weekly-plan?tz_offset_minutes=0", headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def _url(cid) -> str:
    return f"/api/children/{cid}/weekly-plan/marks"


def _mark(client, h, cid, week_start, item_key):
    return client.put(_url(cid), headers=h, json={"week_start": week_start, "item_key": item_key})


def _unmark(client, h, cid, week_start, item_key):
    return client.request("DELETE", _url(cid), headers=h,
                          json={"week_start": week_start, "item_key": item_key})


def _rows(device: str) -> int:
    conn = get_conn()
    try:
        return conn.execute("SELECT COUNT(*) FROM weekly_plan_marks WHERE device_id = ?",
                            (device,)).fetchone()[0]
    finally:
        conn.close()


def _ticked(client, device: str):
    """A family with one child and one ticked plan action."""
    h = _auth(client, device)
    cid = _child(client, h)
    plan = _plan(client, h, cid)
    assert _mark(client, h, cid, plan["week_start"], plan["actions"][0]["key"]).status_code == 200
    assert _rows(device) == 1
    return h, cid, plan


# ── Marking ───────────────────────────────────────────────────────────────


def test_get_carries_an_empty_marks_list_and_every_old_key(client):
    h = _auth(client, "dev-marks-shape")
    cid = _child(client, h)
    plan = _plan(client, h, cid)
    assert plan["marks"] == []
    # Additive: an older build reads the same plan it always did.
    for key in ("child_id", "week", "week_start", "lang", "band", "focus", "actions",
                "adapted_from_outcomes", "worship", "lesson", "source", "generated_at"):
        assert key in plan, key


def test_mark_is_idempotent_and_shows_on_the_plan(client):
    h = _auth(client, "dev-marks-put")
    cid = _child(client, h)
    plan = _plan(client, h, cid)
    key = plan["actions"][1]["key"]
    r = _mark(client, h, cid, plan["week_start"], key)
    assert r.status_code == 200, r.text
    assert r.json() == {"child_id": cid, "week_start": plan["week_start"], "item_key": key,
                        "marked": True, "marks": [key]}
    again = _mark(client, h, cid, plan["week_start"], key)
    assert again.status_code == 200 and again.json()["marks"] == [key]
    assert _rows("dev-marks-put") == 1
    assert _plan(client, h, cid)["marks"] == [key]

    worship = plan["worship"]["key"]
    assert _mark(client, h, cid, plan["week_start"], worship).json()["marks"] == [key, worship]


def test_unmark_deletes_the_row_and_is_idempotent(client):
    h, cid, plan = _ticked(client, "dev-marks-del")
    key = plan["actions"][0]["key"]
    r = _unmark(client, h, cid, plan["week_start"], key)
    assert r.status_code == 200, r.text
    assert r.json() == {"child_id": cid, "week_start": plan["week_start"], "item_key": key,
                        "marked": False, "marks": []}
    assert _rows("dev-marks-del") == 0                      # nothing records an "unmarked"
    assert _unmark(client, h, cid, plan["week_start"], key).status_code == 200
    assert _plan(client, h, cid)["marks"] == []


def test_marks_belong_to_their_week(client):
    h = _auth(client, "dev-marks-week")
    cid = _child(client, h)
    plan = _plan(client, h, cid)
    last_week = (date.fromisoformat(plan["week_start"]) - timedelta(days=7)).isoformat()
    key = plan["actions"][0]["key"]
    assert _mark(client, h, cid, last_week, key).status_code == 200
    assert _plan(client, h, cid)["marks"] == []


def test_marks_belong_to_their_child(client):
    h = _auth(client, "dev-marks-two")
    first, second = _child(client, h), _child(client, h, name="سارة")
    plan = _plan(client, h, first)
    key = plan["actions"][0]["key"]
    assert _mark(client, h, first, plan["week_start"], key).status_code == 200
    assert _plan(client, h, second)["marks"] == []


def test_needs_a_session_and_the_childs_own_device(client):
    h, cid, plan = _ticked(client, "dev-marks-owner")
    body = {"week_start": plan["week_start"], "item_key": plan["actions"][0]["key"]}
    assert client.put(_url(cid), json=body).status_code == 401
    stranger = _auth(client, "dev-marks-stranger")
    assert client.put(_url(cid), json=body, headers=stranger).status_code == 404
    assert client.request("DELETE", _url(cid), json=body, headers=stranger).status_code == 404
    assert client.put(_url(999999), json=body, headers=h).status_code == 404
    assert _rows("dev-marks-owner") == 1                    # the stranger changed nothing


@pytest.mark.parametrize("item_key", ["", "nonsense", "x" * 200, "sleep_school_99",
                                      "lesson_7-9_medical_emotional_health_02"])
def test_only_a_plan_item_can_be_marked(client, item_key):
    h = _auth(client, "dev-marks-key")
    cid = _child(client, h)
    plan = _plan(client, h, cid)
    r = _mark(client, h, cid, plan["week_start"], item_key)
    assert r.status_code == 422, r.text
    assert _rows("dev-marks-key") == 0


def test_week_start_must_be_a_recent_monday(client):
    h = _auth(client, "dev-marks-when")
    cid = _child(client, h)
    plan = _plan(client, h, cid)
    key = plan["actions"][0]["key"]
    monday = date.fromisoformat(plan["week_start"])
    for bad in ((monday + timedelta(days=1)).isoformat(),        # a Tuesday
                (monday + timedelta(days=14)).isoformat(),       # two weeks ahead
                (monday - timedelta(days=21)).isoformat(),       # three weeks back
                "2026-13-01", "soon"):
        r = _mark(client, h, cid, bad, key)
        assert r.status_code == 422, (bad, r.text)
        assert r.json()["detail"]["code"] == "week_start", bad
    assert _rows("dev-marks-when") == 0


def test_mark_service_accepts_the_current_and_previous_week_only():
    today = date(2026, 10, 14)                                # a Wednesday
    now = datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc)
    assert wp.valid_mark_week(date(2026, 10, 12), now=now)
    assert wp.valid_mark_week(date(2026, 10, 5), now=now)
    assert not wp.valid_mark_week(date(2026, 9, 28), now=now)
    assert not wp.valid_mark_week(date(2026, 10, 19), now=now)
    assert not wp.valid_mark_week(today, now=now)            # not a Monday
    # A family at +14:00 is already in Monday while UTC is still Sunday.
    sunday = datetime(2026, 10, 18, 11, 0, tzinfo=timezone.utc)
    assert wp.valid_mark_week(date(2026, 10, 19), now=sunday)


# ── Forgetting ────────────────────────────────────────────────────────────


def test_forgetting_a_childs_memory_forgets_its_marks(client):
    h, cid, _plan_ = _ticked(client, "dev-marks-forget-child")
    prove(client, h, push_token="fcm-marks-forget-child")
    r = client.delete(f"/api/children/{cid}/memory", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["deleted"]["weekly_plan_marks"] == 1
    assert _rows("dev-marks-forget-child") == 0


def test_privacy_delete_all_forgets_the_marks_of_this_device_only(client):
    h, _cid, _p = _ticked(client, "dev-marks-wipe")
    _ticked(client, "dev-marks-keep")
    prove(client, h, push_token="fcm-marks-wipe")
    r = client.delete("/api/privacy/memory", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["deleted"]["weekly_plan_marks"] == 1
    assert _rows("dev-marks-wipe") == 0
    assert _rows("dev-marks-keep") == 1


def test_deleting_the_child_deletes_its_marks(client):
    h, cid, _p = _ticked(client, "dev-marks-child-gone")
    prove(client, h, push_token="fcm-marks-child-gone")
    assert client.delete(f"/api/children/{cid}", headers=h).status_code == 200
    assert _rows("dev-marks-child-gone") == 0


def test_a_deleted_account_loses_its_marks(client):
    h, _cid, _p = _ticked(client, "dev-marks-account")
    _ticked(client, "dev-marks-bystander")
    prove(client, h, push_token="fcm-marks-account")
    r = client.delete("/api/privacy/account?confirm=true", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["deleted"].get("weekly_plan_marks") == 1
    assert _rows("dev-marks-account") == 0
    assert _rows("dev-marks-bystander") == 1


def test_a_twin_fold_carries_the_marks_to_the_family():
    """The identity merge that moves rows between device ids (device twins,
    PR #29) finds tables by introspection — the marks ride along, and the
    fold's log puts them back on revert."""
    from app.services import device_twins
    conn = get_conn()
    try:
        cid = conn.execute("INSERT INTO child_profiles (device_id, name, age_group) "
                           "VALUES ('dev-marks-family', 'سالم', '7-9')").lastrowid
        conn.execute("INSERT INTO weekly_plan_marks (device_id, child_id, item_id, marked_on) "
                     "VALUES ('dev-marks-twin', ?, 'sleep_school_1', '2026-10-12')", (cid,))
        conn.commit()
        assert ("weekly_plan_marks", "device_id") in device_twins.device_columns(conn)
        counts = device_twins._fold_rows(conn, "dev-marks-twin", "dev-marks-family")
        conn.commit()
        assert counts.get("weekly_plan_marks.device_id") == 1
    finally:
        conn.close()
    assert _rows("dev-marks-family") == 1 and _rows("dev-marks-twin") == 0
