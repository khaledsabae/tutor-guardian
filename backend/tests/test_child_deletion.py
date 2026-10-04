"""P3 (PR #26 review): deleting a child deletes everything tied to the child.

DELETE /api/children/{id} used to remove only the child_profiles row, while the
privacy policy promised the child's progress, memory and tool data went too.
This test seeds a row in EVERY table that has a child_id column — found by
introspection, so a table added later is covered without editing this file —
plus the rows hanging off them, for two children of one family; deletes one;
and checks that nothing of it is left and nothing of its sibling is gone.
"""
from __future__ import annotations

import sqlite3

import pytest
from fastapi.testclient import TestClient

from app.db.init_db import db_path, get_conn
from app.routers import privacy as pv

DEVICE = "dev-two-kids"


def _full_schema() -> None:
    from app.routers import feedback
    from app.services import coach_service, story_service
    conn = get_conn()
    feedback._ensure_app_feedback_table(conn)
    story_service._ensure_schema(conn)
    conn.commit()
    conn.close()
    coach_service._ensure_coach_tips_table()


def _child_tables(conn) -> list[str]:
    return sorted(t for t, cols in pv._table_columns(conn).items()
                  if "child_id" in cols and t != "child_profiles")


def _value(table, col, decl, cid):
    if col == "device_id":
        return DEVICE
    if col == "child_id":
        return cid
    if "INT" in (decl or "").upper():
        return 1
    if any(k in (decl or "").upper() for k in ("REAL", "FLOA", "DOUB")):
        return 1.0
    return f"{table}.{col}.{cid}"


def _seed(cid: int) -> None:
    conn = sqlite3.connect(db_path())             # foreign keys off: any order
    for table in _child_tables(conn):
        info = conn.execute(f"PRAGMA table_info('{table}')").fetchall()
        cols, vals = [], []
        for _i, name, decl, notnull, default, pk in info:
            if pk and "INT" in (decl or "").upper():
                continue
            if name in ("device_id", "child_id") or (notnull and default is None) or pk:
                cols.append(name)
                vals.append(_value(table, name, decl, cid))
        conn.execute(f"INSERT INTO {table} ({', '.join(cols)}) "
                     f"VALUES ({', '.join('?' * len(cols))})", vals)
    routine = conn.execute("SELECT id FROM child_daily_routines WHERE child_id = ?",
                           (cid,)).fetchone()[0]
    conn.execute("INSERT INTO routine_events (routine_id, event_type, started_at) "
                 "VALUES (?, 'sleep', '2026-10-01')", (routine,))
    agreement = conn.execute("SELECT id FROM family_agreements WHERE child_id = ?",
                             (cid,)).fetchone()[0]
    conn.execute("INSERT INTO agreement_clauses (agreement_id, applies_to, text_ar) "
                 "VALUES (?, 'child', 'بند')", (agreement,))
    conn.commit()
    conn.close()


def _rows_of(cid: int) -> dict[str, int]:
    conn = sqlite3.connect(db_path())
    try:
        out = {t: conn.execute(f"SELECT COUNT(*) FROM {t} WHERE child_id = ?", (cid,)).fetchone()[0]
               for t in _child_tables(conn)}
        out["routine_events"] = conn.execute(
            "SELECT COUNT(*) FROM routine_events WHERE routine_id IN "
            "(SELECT id FROM child_daily_routines WHERE child_id = ?)", (cid,)).fetchone()[0]
        out["agreement_clauses"] = conn.execute(
            "SELECT COUNT(*) FROM agreement_clauses WHERE agreement_id IN "
            "(SELECT id FROM family_agreements WHERE child_id = ?)", (cid,)).fetchone()[0]
        out["child_profiles"] = conn.execute(
            "SELECT COUNT(*) FROM child_profiles WHERE id = ?", (cid,)).fetchone()[0]
        return out
    finally:
        conn.close()


@pytest.fixture
def client():
    from app.main import app
    with TestClient(app) as c:
        yield c


def test_deleting_a_child_deletes_every_child_linked_row(client):
    _full_schema()
    tok = client.post("/api/chat/sessions", json={"device_id": DEVICE}).json()["token"]
    h = {"Authorization": f"Bearer {tok}"}
    gone = client.post("/api/children", json={"name": "سالم", "age_group": "7-9"},
                       headers=h).json()["id"]
    kept = client.post("/api/children", json={"name": "سارة", "age_group": "4-6"},
                       headers=h).json()["id"]
    _seed(gone)
    _seed(kept)
    conn = get_conn()
    conn.execute("INSERT INTO lesson_progress (device_id, child_id, path_id, lesson_id) "
                 "VALUES (?, 0, 'p', 'legacy-device-row')", (DEVICE,))
    conn.commit()
    conn.close()
    before = _rows_of(gone)
    assert all(before.values()), before                          # every table seeded
    named_by_review = {"lesson_progress", "coach_tips", "child_missions", "family_agreements",
                       "agreement_clauses", "child_licences", "child_scenario_answers",
                       "child_screen_sessions", "daily_login_streaks", "child_facts",
                       "followups", "weekly_plans", "routine_events"}
    assert named_by_review <= set(before)

    assert client.delete(f"/api/children/{gone}", headers=h).status_code == 200
    left = {t: n for t, n in _rows_of(gone).items() if n}
    assert left == {}, f"rows left behind for the deleted child: {left}"
    assert all(_rows_of(kept).values())                          # the sibling is untouched
    conn = get_conn()
    legacy = conn.execute("SELECT COUNT(*) FROM lesson_progress WHERE child_id = 0").fetchone()[0]
    conn.close()
    assert legacy == 1                       # device-level legacy rows are not the child's
