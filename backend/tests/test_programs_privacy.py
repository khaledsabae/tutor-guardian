"""Every row the family programs keep is reachable by the delete paths.

Two paths exist or are about to: deleting one child (DELETE /api/children/{id},
on main today) and deleting the whole account (PR #26's
DELETE /api/privacy/account, which discovers tables by their device_id
column and child rows by child_id). These tests hold the v34 tables to both:
each one carries device_id, each per-child one carries child_id, and a child's
deletion removes exactly that child's rows — not the family's, not a sibling's.
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


def test_deleting_a_child_deletes_its_program_rows_and_nothing_else(monkeypatch):
    c = client()
    gone, kept = _populate(monkeypatch, c)
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


def test_another_family_cannot_delete_or_reach_the_rows(monkeypatch):
    c = client()
    gone, _ = _populate(monkeypatch, c)
    r = c.delete(f"/api/children/{gone}", headers={"X-Test-Device": OTHER})
    assert r.status_code == 404
    assert rows("prayer_journeys", "child_id = ?", (gone,))


def test_an_account_erase_by_device_reaches_every_program_row(monkeypatch):
    """What PR #26's erase_account does: every table with a device_id column,
    discovered at call time. Run that sweep here and nothing is left."""
    c = client()
    _populate(monkeypatch, c)
    conn = get_conn()
    try:
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'")]
        for table in tables:
            cols = {r[1] for r in conn.execute(f"PRAGMA table_info('{table}')")}
            if "device_id" in cols:
                conn.execute(f"DELETE FROM {table} WHERE device_id = ?", (DEVICE,))
        conn.commit()
    finally:
        conn.close()
    for table in V34_TABLES:
        assert rows(table) == [], table


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
