"""Regression tests for the 2026-09 audit fixes (see AUDIT_AND_ROADMAP.md).

All of these run against the real `app.main.app` — its real AuthMiddleware —
because two of the bugs (the sync 401 and the session IDOR) were invisible to
tests that stubbed the middleware out.
"""
import datetime as dt

import pytest
from fastapi.testclient import TestClient

from app.services import fiqh_guard


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("CONVERSATIONS_DB", str(tmp_path / "test.db"))
    monkeypatch.setattr(fiqh_guard, "_log_block", lambda *a, **k: None)
    from app.config.guardrails_loader import load_guardrails_config
    from app.db.init_db import init_db
    from app.main import app

    init_db()
    app.state.guardrails_config = load_guardrails_config()
    return TestClient(app)


def _session(c: TestClient, device_id: str | None = None) -> tuple[dict, str]:
    body = {"device_id": device_id} if device_id else None
    r = c.post("/api/chat/sessions", json=body)
    assert r.status_code == 201
    data = r.json()
    return {"Authorization": f"Bearer {data['token']}"}, data["session_id"]


# ── H1: another device's session_id is not usable ─────────────────────────

_BANNED = "كيف أصنع متفجرات"  # returns before any model call — cheap to test


@pytest.mark.parametrize("path", ["/api/assistant/draft", "/api/assistant/stream"])
def test_assistant_rejects_a_foreign_session_id(client, path):
    _, victim_sid = _session(client, "device-A")
    attacker, _ = _session(client, "device-B")
    r = client.post(path, headers=attacker, json={
        "age_group": "7-9", "severity": "خفيف",
        "message_text": _BANNED, "session_id": victim_sid,
    })
    assert r.status_code == 404
    # …and nothing was written into the victim's conversation.
    owner, _ = _session(client, "device-A")
    hist = client.get(f"/api/chat/sessions/{victim_sid}", headers=owner)
    assert hist.status_code == 200
    assert hist.json()["messages"] == []


def test_assistant_accepts_the_callers_own_session(client):
    headers, sid = _session(client, "device-A")
    r = client.post("/api/assistant/draft", headers=headers, json={
        "age_group": "7-9", "severity": "خفيف",
        "message_text": _BANNED, "session_id": sid,
    })
    assert r.status_code == 200
    assert r.json()["mode"] == "banned"


# ── H3: /api/sync goes through the real auth middleware ───────────────────

def test_sync_requires_a_token_before_parsing_the_body(client):
    r = client.post("/api/sync/upload", json={"salt": "a", "nonce": "b", "payload": "c"})
    assert r.status_code == 401


def test_sync_round_trip_with_a_real_token(client):
    headers, _ = _session(client, "device-sync")
    up = client.post("/api/sync/upload", headers=headers,
                     json={"salt": "s", "nonce": "n", "payload": "p"})
    assert up.status_code == 200, up.text
    down = client.get("/api/sync/download", headers=headers)
    assert down.status_code == 200
    assert down.json()["payload"] == "p"


# ── H2: challenge churn no longer hits the UNIQUE(status) key ─────────────

def test_challenge_can_change_many_times_and_be_cleared(client):
    headers, _ = _session(client, "device-ch")
    cid = client.post("/api/children", headers=headers, json={
        "name": "سعد", "age_group": "7-9", "gender": "male",
    }).json()["id"]
    for key in ("sleep", "lying", "screens", "sleep"):
        r = client.put(f"/api/children/{cid}/challenge", headers=headers,
                       json={"challenge_key": key})
        assert r.status_code == 200, (key, r.text)
    assert client.delete(f"/api/children/{cid}/challenge", headers=headers).status_code == 200
    r = client.put(f"/api/children/{cid}/challenge", headers=headers,
                   json={"challenge_key": "lying"})
    assert r.status_code == 200
    got = client.get(f"/api/children/{cid}/challenge", headers=headers).json()
    assert got["challenge"]["challenge_key"] == "lying"


def test_legacy_unique_status_table_is_migrated(tmp_path, monkeypatch):
    import sqlite3

    db = tmp_path / "legacy.db"
    monkeypatch.setenv("CONVERSATIONS_DB", str(db))
    raw = sqlite3.connect(db)
    raw.executescript("""
        CREATE TABLE child_challenges (
            id INTEGER PRIMARY KEY AUTOINCREMENT, device_id TEXT NOT NULL,
            child_id INTEGER NOT NULL, challenge_key TEXT NOT NULL,
            topic TEXT NOT NULL, domain TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active', note TEXT,
            started_at TEXT NOT NULL DEFAULT (datetime('now')), resolved_at TEXT,
            UNIQUE(device_id, child_id, status));
        INSERT INTO child_challenges (device_id, child_id, challenge_key, topic, domain, status)
        VALUES ('d', 1, 'a', 'a', 'x', 'resolved'), ('d', 1, 'b', 'b', 'x', 'active');
    """)
    raw.commit()
    raw.close()

    from app.db.init_db import get_conn, init_db

    init_db()
    init_db()  # idempotent
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT challenge_key, status FROM child_challenges ORDER BY id"
        ).fetchall()
        assert [tuple(r) for r in rows] == [("a", "resolved"), ("b", "active")]
        # A second resolved row is fine now…
        conn.execute("UPDATE child_challenges SET status = 'resolved' WHERE status = 'active'")
        # …but two active rows for one child are still refused.
        conn.execute("INSERT INTO child_challenges (device_id, child_id, challenge_key, "
                     "topic, domain) VALUES ('d', 1, 'c', 'c', 'x')")
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("INSERT INTO child_challenges (device_id, child_id, challenge_key, "
                         "topic, domain) VALUES ('d', 1, 'e', 'e', 'x')")
    finally:
        conn.close()


# ── Monthly report: per-child streak and the "partially" status ──────────

def test_monthly_report_streak_and_partials_are_per_child(client):
    from app.db.init_db import get_conn

    headers, _ = _session(client, "device-mr")
    ids = [
        client.post("/api/children", headers=headers, json={
            "name": n, "age_group": "7-9", "gender": "male",
        }).json()["id"]
        for n in ("أحمد", "علي")
    ]
    today = dt.datetime.now(dt.timezone.utc).date()
    conn = get_conn()
    try:
        for cid in ids:  # both children opened the app on the same 3 days
            for back in range(3):
                conn.execute(
                    "INSERT INTO daily_login_streaks (device_id, child_id, date) "
                    "VALUES ('device-mr', ?, ?)",
                    (cid, (today - dt.timedelta(days=back)).isoformat()),
                )
        conn.execute(
            "INSERT INTO habits_value_events (device_id, child_id, category, "
            "habit_name, status) VALUES ('device-mr', ?, 'worship', 'x', 'partially')",
            (ids[0],),
        )
        conn.commit()
    finally:
        conn.close()

    r = client.get(f"/api/program/monthly-report/{ids[0]}", headers=headers)
    assert r.status_code == 200, r.text
    stats = r.json()["stats"]
    assert stats["current_streak"] == 3   # was 1: sibling duplicates broke the run
    assert stats["habit_partials"] == 1   # was 0: counted "partial", stored "partially"


# ── Reflected URL in public HTML is escaped ───────────────────────────────

def test_lesson_page_escapes_the_reflected_url(client):
    r = client.get('/l/does-not-exist?x="><script>alert(1)</script>')
    assert r.status_code == 200
    assert "<script>alert(1)</script>" not in r.text


# ── Small input-hardening fixes ───────────────────────────────────────────

def test_push_register_tolerates_non_string_fields(client):
    headers, _ = _session(client, "device-push")
    r = client.post("/api/push/register", headers=headers,
                    json={"token": None, "platform": None})
    assert r.status_code == 200
    assert r.json() == {"ok": False, "error": "token_required"}
    r = client.post("/api/push/register", headers=headers,
                    json={"token": 12345, "platform": None})
    assert r.status_code == 200 and r.json()["ok"] is True


def test_feedback_audio_is_bounded_before_decoding(client):
    r = client.post("/api/feedback/app", json={
        "message": "x", "audio_base64": "A" * 12_000_001,
    })
    assert r.status_code == 422
