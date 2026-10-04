"""Every row the family programs keep is reachable by the delete paths.

Two paths (PR #26): deleting one child (DELETE /api/children/{id} —
privacy.erase_child from a session proven to hold the phone, the profile row
alone otherwise) and deleting the whole account (privacy.erase_account). Both
discover tables at run time — by child_id and by device_id — so these tests
hold the v34 tables to that shape: each carries device_id, each per-child one
carries child_id, and a child's deletion removes exactly that child's rows —
not the family's, not a sibling's.
"""
from app.db.init_db import get_conn
from app.services import programs_common as pc
from tests.programs_support import DEVICE, OTHER, add_child, child_headers, client, freeze, rows

V34_TABLES = ("program_settings", "program_children", "ramadan_fasting", "ramadan_marks",
              "prayer_journeys", "milestone_alerts")


def _columns(table: str) -> set[str]:
    conn = get_conn()
    try:
        return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
    finally:
        conn.close()


def test_every_new_table_carries_the_device_and_per_child_ones_the_child():
    for table in V34_TABLES:
        assert "device_id" in _columns(table), table
    for table in pc.PER_CHILD_TABLES:
        assert "child_id" in _columns(table), table
    assert set(pc.PER_CHILD_TABLES) == set(V34_TABLES) - {"program_settings"}


def _populate(monkeypatch, c):
    """One family, two children, a row in every program table."""
    freeze(monkeypatch, "2027-02-12T17:00:00")                 # day 5
    gone = add_child(c, birth_month="2019-06", gender="female")
    kept = add_child(c, name="سارة", birth_month="2018-01")
    p = {"tz_offset_minutes": 180, "lang": "en"}
    assert c.post("/api/programs/ramadan/marks", params=p,
                  json={"mark": "challenge_done"}).status_code == 200
    for cid in (gone, kept):
        r = c.put(f"/api/children/{cid}/ramadan/fasting", params=p,
                  json={"step_key": "morning_hours", "reached_puberty": False})
        assert r.status_code == 200
        assert c.put(f"/api/children/{cid}/ramadan/fasting", params=p,
                     json={"step_key": "until_dhuhr"}).status_code == 200      # a climb
        assert c.post(f"/api/children/{cid}/ramadan/fasting/practice", params=p,
                      json={}).status_code == 200
        assert c.post(f"/api/children/{cid}/prayer-journey/enrol", params=p,
                      json={}).status_code == 200
        assert c.post("/api/value-tracking/child-mode/prayer/claim",
                      params={"task_id": "prayer_s1_pray_beside", "tz_offset_minutes": 180},
                      headers=child_headers(cid)).status_code == 200
        conn = get_conn()
        conn.execute("INSERT INTO milestone_alerts (device_id, child_id, alert_key, "
                     "milestone_key, status) VALUES (?, ?, 'k', 'k', 'sent')", (DEVICE, cid))
        conn.commit()
        conn.close()
    return gone, kept


def _proven(monkeypatch):
    """A session that proved it holds the phone (core/proof.py) — the case in
    which a child's deletion takes everything tied to the child."""
    from app.routers import children
    monkeypatch.setattr(children, "confirmed_session", lambda request: True)


def test_deleting_a_child_deletes_its_program_rows_and_nothing_else(monkeypatch):
    c = client()
    gone, kept = _populate(monkeypatch, c)
    _proven(monkeypatch)
    for table in pc.PER_CHILD_TABLES:
        assert rows(table, "child_id = ?", (gone,)), table           # populated first
    assert c.delete(f"/api/children/{gone}").status_code == 200
    for table in pc.PER_CHILD_TABLES:
        assert rows(table, "child_id = ?", (gone,)) == [], table
        assert rows(table, "child_id = ?", (kept,)), table           # the sibling's stay
    assert rows("child_missions", "child_id = ?", (gone,)) == []
    assert rows("child_missions", "child_id = ?", (kept,))
    # The family's own rows are not the child's.
    assert rows("ramadan_marks", "child_id = 0 AND device_id = ?", (DEVICE,))
    assert rows("program_settings", "device_id = ?", (DEVICE,))


def test_an_unproven_delete_takes_the_profile_and_its_birth_month_only(monkeypatch):
    """PR #26's rule: without a proven session the route does exactly what it
    did before — the profile row, nothing more. The birth month is ON that row,
    so it goes; the program rows wait for a proven delete or the account's."""
    c = client()
    gone, _ = _populate(monkeypatch, c)
    assert c.delete(f"/api/children/{gone}").status_code == 200
    assert rows("child_profiles", "id = ?", (gone,)) == []
    assert rows("prayer_journeys", "child_id = ?", (gone,))


def test_another_family_cannot_delete_or_reach_the_rows(monkeypatch):
    c = client()
    gone, _ = _populate(monkeypatch, c)
    r = c.delete(f"/api/children/{gone}", headers={"X-Test-Device": OTHER})
    assert r.status_code == 404
    assert rows("prayer_journeys", "child_id = ?", (gone,))


def test_the_account_erase_reaches_every_program_row(monkeypatch):
    """PR #26's erase_account, the real one: it discovers every table with a
    device_id, so nothing of the family's programs is left behind."""
    from app.routers.privacy import erase_account

    c = client()
    _populate(monkeypatch, c)
    for table in V34_TABLES:
        assert rows(table, "device_id = ?", (DEVICE,)), table      # populated first
    erase_account(DEVICE)
    for table in V34_TABLES:
        assert rows(table) == [], table
    assert rows("child_missions") == [] and rows("child_profiles") == []


def test_the_policy_discloses_the_programs_and_the_birth_month():
    from pathlib import Path

    import pytest

    policy = Path(__file__).resolve().parents[2] / "docs" / "privacy-policy.md"
    if not policy.exists():
        pytest.skip("docs/ not present (backend-only image)")
    text = policy.read_text(encoding="utf-8")
    arabic, _, english = text.partition("## English")
    flat_en = " ".join(english.split())
    flat_ar = " ".join(arabic.split())
    assert "birth month (optional" in flat_en and "شهر الميلاد (اختياري" in flat_ar
    assert "**Family programs**" in flat_en and "**برامج الأسرة**" in flat_ar


def test_the_milestone_push_never_carries_a_childs_name(monkeypatch):
    from datetime import datetime, timezone

    from app.services import milestone_push as mp
    from app.services import push_sender

    monkeypatch.setenv("MILESTONES_MIN_BUILD", "1")
    c = client()
    cid = add_child(c, name="يوسف", birth_month="2020-03")
    conn = get_conn()
    conn.execute("INSERT INTO push_tokens (device_id, token, build_number) VALUES (?, 't', 5)",
                 (DEVICE,))
    conn.execute("INSERT INTO program_settings (device_id, tz_offset_minutes) VALUES (?, 180)",
                 (DEVICE,))
    conn.commit()
    conn.close()
    seen = []
    monkeypatch.setattr(push_sender, "send_to_device",
                        lambda d, t, b, data=None, **k: seen.append((t, b, data)) or
                        {"ok": True, "sent": True})
    mp.run_due_milestones(datetime(2027, 2, 1, 17, 0, tzinfo=timezone.utc))
    assert len(seen) == 1
    assert "يوسف" not in repr(seen) and seen[0][2]["child_id"] == str(cid)


def test_every_program_endpoint_refuses_an_anonymous_caller():
    """With the real AuthMiddleware, not the stub the other suites use: the
    family endpoints sit under /api/programs (added to the protected
    prefixes), the child ones under /api/children and child mode."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.middleware.auth import AuthMiddleware
    from app.routers.family_programs import router

    app = FastAPI()
    app.add_middleware(AuthMiddleware)
    app.include_router(router, prefix="/api")
    c = TestClient(app)
    for route in router.routes:
        path = "/api" + route.path.replace("{child_id}", "1").replace("{day}", "1") \
            .replace("{key}", "prayer_start")
        for method in route.methods - {"HEAD", "OPTIONS"}:
            r = c.request(method, path, json={})
            assert r.status_code == 401, (method, path, r.status_code)

    # And a real token gets through with its device bound — a path outside
    # the protected prefixes would 401 even then (the /api/sync lesson).
    from app.services import conversation_store as store
    _, token = store.create_session_with_token(DEVICE)
    r = c.get("/api/programs", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200 and r.json()["children"] == []
    r = c.get("/api/programs/ramadan/recap", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
