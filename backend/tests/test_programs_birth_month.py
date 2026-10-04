"""The optional birth month on a child profile (schema v34).

It is what times the milestone reminders and the Prayer Journey's entry, so it
has to be validated on the way in, readable on the way out, clearable, and gone
when the child is.
"""
from datetime import date

import pytest

from app.db.init_db import get_conn, init_db
from app.services import programs_common as pc
from tests.programs_support import DEVICE, OTHER, add_child, client, rows


def test_create_with_a_birth_month_and_read_it_back():
    c = client()
    cid = add_child(c, birth_month="2019-03")
    listed = c.get("/api/children").json()["children"]
    assert [ch["birth_month"] for ch in listed if ch["id"] == cid] == ["2019-03"]


def test_a_child_without_one_reads_null_and_old_payloads_still_work():
    """Builds on Play send no birth_month at all; nothing about them changes."""
    c = client()
    r = c.post("/api/children", json={"name": "سارة", "age_group": "4-6"})
    assert r.status_code == 201
    assert r.json()["birth_month"] is None


@pytest.mark.parametrize("bad", ["2019-3", "2019-13", "2019-00", "19-03", "2019/03",
                                 "2019-03-01", "abcd-ef", " ", "1990-01"])
def test_malformed_or_implausible_months_are_refused(bad):
    c = client()
    r = c.post("/api/children", json={"name": "x", "age_group": "7-9", "birth_month": bad})
    assert r.status_code == 422, bad


def test_the_validation_window(monkeypatch):
    today = date(2026, 10, 4)
    assert pc.validate_birth_month("2027-08", today) == "2027-08"      # 10 months ahead
    with pytest.raises(ValueError):
        pc.validate_birth_month("2027-09", today)                       # 11 months ahead
    assert pc.validate_birth_month("2007-10", today) == "2007-10"      # 19 years back
    with pytest.raises(ValueError):
        pc.validate_birth_month("2007-09", today)


def test_patch_sets_changes_and_clears_it():
    c = client()
    cid = add_child(c)
    r = c.patch(f"/api/children/{cid}", json={"birth_month": "2018-11"})
    assert r.status_code == 200 and r.json()["birth_month"] == "2018-11"
    # Another field alone leaves it untouched.
    r = c.patch(f"/api/children/{cid}", json={"name": "عمر"})
    assert r.json()["birth_month"] == "2018-11"
    # An explicit null clears it — and counts as a change (not a 422 no-op).
    r = c.patch(f"/api/children/{cid}", json={"birth_month": None})
    assert r.status_code == 200 and r.json()["birth_month"] is None
    assert rows("child_profiles", "id = ?", (cid,))[0]["birth_month"] is None


def test_patch_refuses_a_bad_month_and_another_devices_child():
    c = client()
    cid = add_child(c)
    assert c.patch(f"/api/children/{cid}", json={"birth_month": "2018-13"}).status_code == 422
    r = c.patch(f"/api/children/{cid}", json={"birth_month": "2018-01"},
                headers={"X-Test-Device": OTHER})
    assert r.status_code == 404


def test_deleting_the_child_deletes_the_month_with_the_row():
    c = client()
    cid = add_child(c, birth_month="2019-03")
    assert c.delete(f"/api/children/{cid}").status_code == 200
    assert rows("child_profiles", "id = ?", (cid,)) == []


def test_the_migration_adds_the_column_to_a_production_shaped_table(tmp_path, monkeypatch):
    """child_profiles as production has it (sqlite_master, read-only, 2026-10-04):
    eight columns, avatar_emoji appended by an old ALTER, no birth_month."""
    db = tmp_path / "prod_shape.db"
    monkeypatch.setenv("CONVERSATIONS_DB", str(db))
    conn = get_conn()
    conn.executescript(
        """
        CREATE TABLE child_profiles (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id   TEXT NOT NULL,
            name        TEXT NOT NULL,
            age_group   TEXT NOT NULL,  -- enum from CANONICAL_AGE_GROUPS
            gender      TEXT,
            created_at  TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
        , avatar_emoji TEXT);
        INSERT INTO child_profiles (device_id, name, age_group) VALUES ('d', 'n', '7-9');
        CREATE TABLE child_missions (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id     TEXT NOT NULL,
            child_id      INTEGER NOT NULL,
            mission_key   TEXT NOT NULL,
            local_date    TEXT NOT NULL,
            status        TEXT NOT NULL DEFAULT 'assigned',
            assigned_at   TEXT NOT NULL DEFAULT (datetime('now')),
            claimed_at    TEXT,
            confirmed_at  TEXT,
            parent_note   TEXT,
            UNIQUE (child_id, local_date, mission_key)
        );
        INSERT INTO child_missions (device_id, child_id, mission_key, local_date, status)
        VALUES ('d', 1, 'mission_7-9_green_hunt', '2026-08-21', 'expired');
        """
    )
    conn.close()
    init_db()
    init_db()  # idempotent
    conn = get_conn()
    try:
        profile_cols = {r[1] for r in conn.execute("PRAGMA table_info(child_profiles)")}
        mission_cols = {r[1] for r in conn.execute("PRAGMA table_info(child_missions)")}
        kept = conn.execute("SELECT name, birth_month FROM child_profiles").fetchone()
        old_mission = conn.execute("SELECT source FROM child_missions").fetchone()
        version = conn.execute("SELECT version FROM schema_version").fetchone()[0]
    finally:
        conn.close()
    assert "birth_month" in profile_cols and "source" in mission_cols
    assert tuple(kept) == ("n", None)
    assert old_mission["source"] is None          # existing rows stay bank rows
    assert version >= 34


def test_a_google_relink_copies_the_month_with_the_profile():
    """identity._merge_legacy_device_data copies a reinstalled family's
    children to the new device; the month travels with them."""
    from app.routers.identity import _merge_legacy_device_data

    c = client()
    add_child(c, birth_month="2020-05", device=OTHER)
    conn = get_conn()
    try:
        conn.execute("INSERT OR IGNORE INTO parent_identities (google_id) VALUES ('g1')")
        for device in (OTHER, DEVICE):
            conn.execute("INSERT INTO identity_links (device_id, google_id) VALUES (?, 'g1')",
                         (device,))
        conn.commit()
        _merge_legacy_device_data(conn, DEVICE, "g1")
    finally:
        conn.close()
    assert [r["birth_month"] for r in rows("child_profiles", "device_id = ?", (DEVICE,))] \
        == ["2020-05"]
