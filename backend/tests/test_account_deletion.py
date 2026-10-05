"""Account deletion — DELETE /api/privacy/account (Google Play: in-app deletion).

Two halves, both needed:

* **Coverage by introspection.** Every table in the schema — the one init_db
  builds here AND the one production actually has (copied below from a
  read-only dump, because production diverges from init_db) — must either
  carry a device_id (deleted by discovery) or be classified in
  routers/privacy.py. An unclassified table fails the build: that is how the
  next table with personal data gets noticed before it ships.
* **Deletion by effect.** A row is seeded into every device-scoped table for
  two accounts; after the call, one account has zero rows anywhere and the
  other is untouched.
"""
from __future__ import annotations

import sqlite3

import pytest
from fastapi.testclient import TestClient

from app.db.init_db import db_path, get_conn
from app.routers import privacy as pv
from tests.device_proof_support import prove

# Copied 2026-10-04 from production (read-only: sqlite_master + PRAGMA
# table_info inside tg_backend, schema v29). Do not edit by hand — re-dump.
_PROD_TABLES_2026_10_04 = {
    'agreement_clauses': ('id', 'agreement_id', 'applies_to', 'clause_key', 'text_ar', 'is_custom', 'sort_order', 'acknowledged_at'),
    'api_tokens': ('token', 'device_id', 'session_id', 'created_at', 'expires_at'),
    'app_feedback': ('id', 'message', 'contact', 'audio_file', 'device_id', 'app_version', 'created_at', 'audio_b64', 'tg_message_id'),
    'chat_messages': ('id', 'session_id', 'role', 'content', 'domain', 'severity', 'mode', 'needs_human_review', 'created_at'),
    'chat_sessions': ('id', 'device_id', 'created_at', 'updated_at', 'metadata'),
    'child_challenges': ('id', 'device_id', 'child_id', 'challenge_key', 'topic', 'domain', 'status', 'note', 'started_at', 'resolved_at'),
    'child_daily_routines': ('id', 'device_id', 'child_id', 'routine_date', 'created_at', 'updated_at'),
    'child_licences': ('id', 'device_id', 'child_id', 'level_key', 'status', 'granted_at', 'talked_at', 'next_review_date', 'created_at'),
    'child_missions': ('id', 'device_id', 'child_id', 'mission_key', 'local_date', 'status', 'assigned_at', 'claimed_at', 'confirmed_at', 'parent_note'),
    'child_profiles': ('id', 'device_id', 'name', 'age_group', 'gender', 'created_at', 'updated_at', 'avatar_emoji'),
    'child_scenario_answers': ('id', 'device_id', 'child_id', 'scenario_key', 'level_key', 'choice_key', 'outcome', 'attempt', 'answered_at', 'parent_alerted_at'),
    'child_screen_sessions': ('id', 'device_id', 'child_id', 'surface', 'local_date', 'tz_offset_minutes', 'started_at', 'last_heartbeat_at', 'ended_at', 'ended_reason', 'counted_seconds', 'created_at'),
    'child_web_claims': ('code_hash', 'device_id', 'child_id', 'ttl_seconds', 'expires_at', 'used_at'),
    'coach_tips': ('id', 'device_id', 'child_id', 'date', 'domain', 'text', 'source', 'shown_at', 'tapped_at', 'created_at', 'lang'),
    'daily_login_streaks': ('id', 'device_id', 'child_id', 'date', 'created_at'),
    'family_agreements': ('id', 'device_id', 'child_id', 'version', 'status', 'signed_by_parent_at', 'signed_by_child_at', 'next_review_date', 'created_at'),
    'feedback_replies': ('id', 'feedback_id', 'device_id', 'reply_text', 'created_at', 'delivered_at', 'read_at'),
    'habit_templates': ('id', 'device_id', 'child_id', 'category', 'custom_name', 'is_active', 'created_at', 'updated_at'),
    'habits_value_events': ('id', 'device_id', 'child_id', 'category', 'habit_name', 'status', 'created_at', 'updated_at', 'submitted_by', 'device_timestamp'),
    'identity_links': ('device_id', 'google_id', 'linked_at'),
    'lesson_progress': ('id', 'device_id', 'child_id', 'path_id', 'lesson_id', 'status', 'started_at', 'completed_at', 'score', 'updated_at'),
    'parent_identities': ('google_id', 'email', 'display_name', 'created_at'),
    'push_sends': ('id', 'device_id', 'kind', 'sent_at'),
    'push_tokens': ('id', 'device_id', 'token', 'platform', 'updated_at', 'app_version', 'build_number'),
    'referral_clicks': ('id', 'ip', 'user_agent', 'code', 'clicked_at'),
    'referral_codes': ('device_id', 'code', 'created_at'),
    'referrals': ('id', 'referrer_device', 'referred_device', 'code', 'created_at'),
    'routine_events': ('id', 'routine_id', 'event_type', 'started_at', 'ended_at', 'feed_type', 'amount_ml', 'side', 'diaper_type', 'notes', 'source', 'created_at', 'updated_at'),
    'schema_version': ('version',),
    'story_cache': ('id', 'theme', 'age_group', 'gender', 'hero_name', 'story', 'created_at', 'served_count'),
    'tg_updates_seen': ('update_id', 'seen_at'),
    'user_backups': ('device_id', 'google_id', 'salt', 'nonce', 'payload', 'updated_at'),
    'user_feedback': ('id', 'session_id', 'rating', 'comment', 'created_at'),
}

_CLASSIFIED = (
    {t for t, *_ in pv.DEPENDENT_TABLES}
    | {t for t, _ in pv.OTHER_DEVICE_COLUMNS}
    | {t for t, _ in pv.IDENTITY_TABLES}
    | set(pv.NOT_DEVICE_DATA)
)


def _full_local_schema() -> dict[str, set[str]]:
    """init_db plus the tables other modules create lazily in the same DB."""
    from app.routers import feedback
    from app.services import coach_service, story_service

    conn = get_conn()
    feedback._ensure_app_feedback_table(conn)
    story_service._ensure_schema(conn)
    conn.commit()
    conn.close()
    coach_service._ensure_coach_tips_table()
    conn = get_conn()
    try:
        return pv._table_columns(conn)
    finally:
        conn.close()


def _unclassified(schema: dict) -> list[str]:
    return sorted(t for t, cols in schema.items()
                  if "device_id" not in cols and t not in _CLASSIFIED)


def test_every_local_table_is_deleted_or_classified():
    schema = _full_local_schema()
    assert len(schema) >= 30
    assert _unclassified(schema) == [], (
        "classify these tables in routers/privacy.py (or give them device_id)")


def test_every_production_table_is_deleted_or_classified():
    assert _unclassified({t: set(c) for t, c in _PROD_TABLES_2026_10_04.items()}) == []


@pytest.mark.parametrize("schema_name", ["local", "production"])
def test_device_columns_under_other_names_are_covered(schema_name):
    """`referrer_device`, `device`, `owner_device` … a device id under any
    other name is personal data the discovery pass would miss."""
    schema = (_full_local_schema() if schema_name == "local"
              else {t: set(c) for t, c in _PROD_TABLES_2026_10_04.items()})
    # A one-way hash of an erased device id (v35) carries "device" in its name
    # but is not an id: declared, and kept by the deletion on purpose.
    covered = set(pv.OTHER_DEVICE_COLUMNS) | set(pv.HASHED_DEVICE_COLUMNS)
    for table, cols in schema.items():
        for col in cols:
            if "device" in col and col not in ("device_id", "device_timestamp"):
                assert (table, col) in covered, (table, col)


def test_dependents_point_at_real_columns_in_production():
    prod = {t: set(c) for t, c in _PROD_TABLES_2026_10_04.items()}
    for table, column, parent, parent_col in pv.DEPENDENT_TABLES:
        assert column in prod[table], (table, column)
        assert parent_col in prod[parent] and "device_id" in prod[parent], parent
    for table, column in pv.IDENTITY_TABLES:
        assert column in prod[table], (table, column)


# ── Effect ────────────────────────────────────────────────────────────────


def _value(table: str, col: str, decl: str, device: str, ids: dict):
    # Every column that names a device names this one: a made-up id in PR #29's
    # `device_aliases.canonical_device` would read as a second, folded device.
    if col == "device_id" or col.endswith("_device"):
        return device
    if col == "child_id":
        return ids["child"]
    if col == "session_id":
        return ids["session"]
    if col == "google_id":
        return ids["google"]
    decl = (decl or "").upper()
    if "INT" in decl:
        return 1
    if "REAL" in decl or "FLOA" in decl or "DOUB" in decl:
        return 1.0
    return f"{table}.{col}.{device}"   # unique per device: TEXT keys never clash


def _seed_device_rows(conn: sqlite3.Connection, device: str, ids: dict) -> None:
    """One row in every table with a device_id, every NOT NULL column filled."""
    for (table,) in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall():
        info = conn.execute(f"PRAGMA table_info('{table}')").fetchall()
        if "device_id" not in {r[1] for r in info}:
            continue
        if table == "identity_links" and not ids.get("google"):
            continue  # a signed-out device has no link; signed-in ones get one below
        cols, vals = [], []
        for _cid, name, decl, notnull, default, pk in info:
            if pk and "INT" in (decl or "").upper():
                continue  # rowid alias: let SQLite number it
            if name in ("device_id", "child_id", "session_id", "google_id") or (
                    notnull and default is None) or pk:
                cols.append(name)
                vals.append(_value(table, name, decl, device, ids))
        conn.execute(
            f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
            vals,
        )


def _seed_account(device: str, google: str | None, *, linked: list[str] = (),
                  confirmed: bool = True) -> dict:
    """A device with a child, a chat, every device table, dependents, a
    referral and (optionally) a Google identity shared with `linked` devices."""
    conn = sqlite3.connect(db_path())        # foreign keys off: seed in any order
    ids: dict = {"google": google}
    for dev in [device, *linked]:
        ids["child"] = conn.execute(
            "INSERT INTO child_profiles (device_id, name, age_group) VALUES (?, 'سالم', '7-9')",
            (dev,)).lastrowid
        ids["session"] = f"sess-{dev}"
        conn.execute("INSERT INTO chat_sessions (id, device_id) VALUES (?, ?)", (ids["session"], dev))
        conn.execute("INSERT INTO chat_messages (session_id, role, content) VALUES (?, 'user', 'سؤال')",
                     (ids["session"],))
        # init_db declares user_feedback.message_id NOT NULL; production's
        # table has no such column (see the dump above). Seed whichever exists.
        fb_cols = {r[1] for r in conn.execute("PRAGMA table_info(user_feedback)")}
        if "message_id" in fb_cols:
            conn.execute("INSERT INTO user_feedback (session_id, message_id, rating) "
                         "VALUES (?, 1, 'up')", (ids["session"],))
        else:
            conn.execute("INSERT INTO user_feedback (session_id, rating) VALUES (?, 'up')",
                         (ids["session"],))
        _seed_device_rows(conn, dev, ids)
        routine = conn.execute(
            "SELECT id FROM child_daily_routines WHERE device_id = ?", (dev,)).fetchone()[0]
        conn.execute("INSERT INTO routine_events (routine_id, event_type, started_at) "
                     "VALUES (?, 'sleep', '2026-10-01')", (routine,))
        agreement = conn.execute(
            "SELECT id FROM family_agreements WHERE device_id = ?", (dev,)).fetchone()[0]
        conn.execute("INSERT INTO agreement_clauses (agreement_id, applies_to, text_ar) "
                     "VALUES (?, 'child', 'بند')", (agreement,))
        if google:
            # Linked from a session proven to hold the phone (identity.py) — the
            # only kind of link account deletion follows.
            conn.execute("INSERT OR REPLACE INTO identity_links (device_id, google_id, confirmed) "
                         "VALUES (?, ?, ?)", (dev, google, 1 if confirmed else 0))
    conn.execute("INSERT INTO referrals (referrer_device, referred_device, code) VALUES (?, ?, ?)",
                 (device, f"friend-of-{device}", f"code-{device}"))
    if google:
        conn.execute("INSERT OR IGNORE INTO parent_identities (google_id, email) VALUES (?, ?)",
                     (google, f"{google}@example.com"))
    conn.commit()
    conn.close()
    return ids


def _rows_for(devices: list[str], google: str | None = None) -> dict[str, int]:
    """Every row anywhere that still belongs to these devices / identity."""
    conn = sqlite3.connect(db_path())
    out: dict[str, int] = {}
    try:
        schema = pv._table_columns(conn)
        marks = ",".join("?" * len(devices))
        for table, cols in schema.items():
            if "device_id" in cols:
                out[table] = conn.execute(
                    f"SELECT COUNT(*) FROM {table} WHERE device_id IN ({marks})", devices).fetchone()[0]
        for table, column, parent, pcol in pv.DEPENDENT_TABLES:
            out[table] = conn.execute(
                f"SELECT COUNT(*) FROM {table} WHERE {column} IN "
                f"(SELECT {pcol} FROM {parent} WHERE device_id IN ({marks}))", devices).fetchone()[0]
        out["referrals"] = conn.execute(
            f"SELECT COUNT(*) FROM referrals WHERE referrer_device IN ({marks}) "
            f"OR referred_device IN ({marks})", devices * 2).fetchone()[0]
        if google:
            out["parent_identities"] = conn.execute(
                "SELECT COUNT(*) FROM parent_identities WHERE google_id = ?", (google,)).fetchone()[0]
    finally:
        conn.close()
    return out


@pytest.fixture
def client():
    from app.main import app
    with TestClient(app) as c:
        yield c


def _token(client, device: str) -> dict:
    tok = client.post("/api/chat/sessions", json={"device_id": device}).json()["token"]
    return {"Authorization": f"Bearer {tok}"}


def test_needs_auth_and_explicit_confirmation(client):
    assert client.delete("/api/privacy/account?confirm=true").status_code == 401
    h = _token(client, "dev-confirm")
    # A session that has not proven it holds the phone (MOBILE_API §9.0)…
    r = client.delete("/api/privacy/account?confirm=true", headers=h)
    assert r.status_code == 403 and r.json()["detail"]["code"] == "device_proof_required"
    prove(client, h, push_token="fcm-confirm")
    # …and, proven, still not without the explicit confirmation.
    r = client.delete("/api/privacy/account", headers=h)
    assert r.status_code == 400 and r.json()["detail"]["code"] == "confirm_required"


def test_signed_out_account_is_the_device(client):
    h = _token(client, "dev-solo")
    _seed_account("dev-solo", None)
    _seed_account("dev-bystander", None)
    prove(client, h)                       # against the push token just seeded
    before = _rows_for(["dev-solo"])
    assert all(before[t] for t in ("child_profiles", "chat_messages", "child_facts",
                                   "routine_events", "agreement_clauses", "push_tokens",
                                   "api_tokens", "referrals"))

    r = client.delete("/api/privacy/account?confirm=true", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["devices"] == 1 and body["signed_in"] is False
    assert sum(body["deleted"].values()) >= len(before)

    left = _rows_for(["dev-solo"])
    assert {t: n for t, n in left.items() if n} == {}
    kept = _rows_for(["dev-bystander"])
    assert all(kept[t] for t in ("child_profiles", "chat_messages", "child_facts",
                                 "routine_events", "agreement_clauses", "referrals"))

    # The token that made the call is revoked; a fresh start is possible.
    assert client.get("/api/children", headers=h).status_code == 401
    h2 = _token(client, "dev-solo")
    assert client.get("/api/children", headers=h2).json()["children"] == []


def test_signed_in_account_is_every_device_linked_to_the_google_identity(client):
    h = _token(client, "dev-phone")
    _seed_account("dev-phone", "g-parent", linked=["dev-old-phone"])
    _seed_account("dev-stranger", "g-stranger")
    prove(client, h)

    r = client.delete("/api/privacy/account?confirm=true", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["devices"] == 2 and r.json()["signed_in"] is True

    gone = _rows_for(["dev-phone", "dev-old-phone"], google="g-parent")
    assert {t: n for t, n in gone.items() if n} == {}
    conn = sqlite3.connect(db_path())
    backups = conn.execute(
        "SELECT COUNT(*) FROM user_backups WHERE google_id = 'g-parent'").fetchone()[0]
    conn.close()
    assert backups == 0
    kept = _rows_for(["dev-stranger"], google="g-stranger")
    assert kept["parent_identities"] == 1 and kept["child_profiles"] >= 1


def test_deletion_is_all_or_nothing(client, monkeypatch):
    _token(client, "dev-atomic")  # a real api_tokens row that must survive the failure
    _seed_account("dev-atomic", None)
    before = _rows_for(["dev-atomic"])

    real = pv.account_devices

    def explode(conn, device_id, tables):
        conn.execute("DELETE FROM child_profiles WHERE device_id = ?", (device_id,))
        raise RuntimeError("disk full")

    monkeypatch.setattr(pv, "account_devices", explode)
    with pytest.raises(RuntimeError):
        pv.erase_account("dev-atomic")
    monkeypatch.setattr(pv, "account_devices", real)
    assert _rows_for(["dev-atomic"]) == before
