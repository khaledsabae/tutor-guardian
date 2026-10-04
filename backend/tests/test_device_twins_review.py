"""PR #29 review — the nine adversarial scenarios, as regression tests.

Each scenario is the reviewer's (backend/tests/test_review_pr29_attacks.py in
the review scratch), with the assertion inverted: on the code before the fix
every one of these demonstrated a weakness; here each asserts it is closed.
Where a scenario needs a fold to happen legitimately (7, 8, 9), the family is
quiet — onboarded in its first minute and never used again, as production's
families whose app came back as the twin are.
"""
import sqlite3

import pytest
from fastapi.testclient import TestClient

from app.db.init_db import db_path, hash_token, init_db
from app.services import conversation_store as store
from app.services import device_twins as twins
from app.services import fiqh_guard

F_VICTIM = "victim-fcm-token:APA91b-secret-ish"


def _db():
    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    return conn


def _born(device, at):
    _, token = store.create_session_with_token(device_id=device)
    with _db() as conn:
        conn.execute("UPDATE api_tokens SET created_at = ? WHERE token = ?", (at, hash_token(token)))
    return token


_later_token = _born


def _child(device, name, at=None):
    """`at=None`: created now, as the reviewer's fixture did — a family in use."""
    with _db() as conn:
        if at is None:
            conn.execute("INSERT INTO child_profiles (device_id, name, age_group) VALUES (?, ?, '7-9')",
                         (device, name))
        else:
            conn.execute("INSERT INTO child_profiles (device_id, name, age_group, created_at, updated_at) "
                         "VALUES (?, ?, '7-9', ?, ?)", (device, name, at, at))


def _push(device, fcm, updated_at="2026-10-01 08:00:05"):
    with _db() as conn:
        conn.execute("INSERT INTO push_tokens (device_id, token, platform, updated_at) "
                     "VALUES (?, ?, 'android', ?) ON CONFLICT(device_id) DO UPDATE SET token=excluded.token",
                     (device, fcm, updated_at))


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(fiqh_guard, "_log_block", lambda *a, **k: None)
    monkeypatch.delenv("SESSION_MINT_ENFORCE", raising=False)
    monkeypatch.delenv("TWIN_FOLD_BORN_BEFORE", raising=False)
    from app.config.guardrails_loader import load_guardrails_config
    from app.main import app

    init_db()
    app.state.guardrails_config = load_guardrails_config()
    return TestClient(app, raise_server_exceptions=False)


def _b(t):
    return {"Authorization": f"Bearer {t}"}


def _children(c, token):
    r = c.get("/api/children", headers=_b(token))
    assert r.status_code == 200, r.text
    return [ch["name"] for ch in r.json()["children"]]


# 1. A device planted 40 s after a victim's install, holding the victim's FCM
#    token, is not absorbed into the victim's family — the family is in use.
def test_1_prepositioned_attacker_is_not_absorbed_into_a_family_in_use(client):
    _born("VICTIM", "2026-10-01 08:00:00"); _child("VICTIM", "VictimKid"); _push("VICTIM", F_VICTIM)
    t_att = _born("ATTACKER", "2026-10-01 08:00:40")
    r = client.post("/api/push/register", headers=_b(t_att), json={"token": F_VICTIM, "platform": "android"})
    assert r.status_code == 200
    assert r.json() == {"ok": True}                    # nothing folded, no id disclosed
    assert _children(client, t_att) == []


# 1b. …and outside the cohort nothing folds, even into a quiet family.
def test_1b_a_device_born_after_the_cutoff_never_folds(client, monkeypatch):
    monkeypatch.setenv("TWIN_FOLD_BORN_BEFORE", "2026-10-01T08:00:30")
    _born("VICTIM", "2026-10-01 08:00:00")
    _child("VICTIM", "VictimKid", at="2026-10-01 08:01:00")
    _push("VICTIM", F_VICTIM)
    t_att = _born("ATTACKER", "2026-10-01 08:00:40")
    assert client.post("/api/push/register", headers=_b(t_att),
                       json={"token": F_VICTIM}).json() == {"ok": True}
    assert _children(client, t_att) == []


# 2. A family that registered someone else's FCM token cannot absorb that
#    person's device on their next launch.
def test_2_victim_is_never_folded_into_an_attackers_family(client):
    _born("ATT_FAMILY", "2026-10-01 08:00:00"); _child("ATT_FAMILY", "AttackerKid")
    t_vic = _born("VICTIM2", "2026-10-01 08:00:20")
    _push("VICTIM2", F_VICTIM)
    sid = store.create_session("VICTIM2", {})
    store.add_message(sid, "user", "a private question from the victim")
    later = _later_token("ATT_FAMILY", "2026-10-03 09:00:00")
    assert client.post("/api/push/register", headers=_b(later), json={"token": F_VICTIM}).json() == {"ok": True}
    r = client.post("/api/push/register", headers=_b(t_vic), json={"token": F_VICTIM})
    assert r.json() == {"ok": True}
    sessions = client.get("/api/chat/sessions", headers=_b(later)).json()["sessions"]
    assert sid not in [s.get("id") or s.get("session_id") for s in sessions]
    assert store.session_owner(sid) == (True, "VICTIM2")


# 3. Proving one's own family and claiming a childless victim's id mints for
#    the proven device — the victim's device is never folded in.
def test_3_mint_claiming_a_victim_mints_for_the_proven_device_only(client):
    _born("ATT3", "2026-10-01 08:00:00"); _child("ATT3", "AttackerKid")
    _born("VIC3", "2026-10-01 08:00:20"); _push("VIC3", F_VICTIM)
    sid = store.create_session("VIC3", {})
    late = _later_token("ATT3", "2026-10-04 12:00:00")
    _push("ATT3", F_VICTIM)
    r = client.post("/api/chat/sessions", headers=_b(late), json={"device_id": "VIC3"})
    assert r.status_code == 201 and r.json()["device_id"] == "ATT3"
    with _db() as conn:
        assert conn.execute("SELECT device_id FROM chat_sessions WHERE id = ?", (sid,)).fetchone()[0] == "VIC3"


# 4. An expired birth-minute token proves its device for a mint — never a fold.
def test_4_expired_birth_token_cannot_fold_at_mint(client):
    _born("VIC4", "2026-10-01 08:00:00"); _child("VIC4", "VictimKid", at="2026-10-01 08:01:00")
    _push("VIC4", F_VICTIM)
    t_birth = _born("ATT4", "2026-10-01 08:00:50")
    with _db() as conn:
        conn.execute("UPDATE api_tokens SET expires_at = '2026-01-01 00:00:00' WHERE token = ?",
                     (hash_token(t_birth),))
    fresh = client.post("/api/chat/sessions", json={"device_id": "ATT4"}).json()["token"]
    assert client.post("/api/push/register", headers=_b(fresh), json={"token": F_VICTIM}).json() == {"ok": True}
    r = client.post("/api/chat/sessions", headers=_b(t_birth), json={"device_id": "VIC4"})
    assert r.status_code == 201 and r.json()["device_id"] == "ATT4"
    assert _children(client, r.json()["token"]) == []


# 5. A Google link never moves onto a family device.
def test_5_attackers_google_link_never_reaches_the_victim(client):
    _born("VIC5", "2026-10-01 08:00:00"); _child("VIC5", "VictimKid"); _push("VIC5", F_VICTIM)
    t_att = _born("ATT5", "2026-10-01 08:00:10")
    with _db() as conn:
        conn.execute("INSERT INTO parent_identities (google_id, email) VALUES ('g-att', 'x@example.invalid')")
        conn.execute("INSERT INTO identity_links (device_id, google_id) VALUES ('ATT5', 'g-att')")
    client.post("/api/push/register", headers=_b(t_att), json={"token": F_VICTIM})
    with _db() as conn:
        assert conn.execute("SELECT device_id FROM identity_links WHERE google_id='g-att'").fetchone()[0] == "ATT5"
    from app.routers import identity
    _born("ATT5_NEW", "2026-10-09 10:00:00")
    identity._link_identity("ATT5_NEW", "g-att", "x@example.invalid", "x")
    with _db() as conn:
        names = [r[0] for r in conn.execute("SELECT name FROM child_profiles WHERE device_id='ATT5_NEW'")]
    assert "VictimKid" not in names


# 6. A timestamp in another format is normalised; nothing in the check can
#    turn a push registration into a 500.
def test_6_timezone_aware_timestamp_is_not_a_500(client):
    _born("U6", "2026-10-01 08:00:00"); _child("U6", "Kid"); _push("U6", "fcm-6")
    t_h = _born("H6", "2026-10-01 08:00:01")
    with _db() as conn:
        conn.execute("UPDATE api_tokens SET created_at = '2026-10-01T08:00:00+00:00' WHERE device_id = 'U6'")
    r = client.post("/api/push/register", headers=_b(t_h), json={"token": "fcm-6"})
    assert r.status_code == 200 and r.json()["ok"] is True


# 7. The twin's referral code survives a fold: invites shared with it resolve.
def test_7_twins_shared_referral_code_keeps_resolving(client):
    _born("U7", "2026-10-01 08:00:00"); _child("U7", "Kid", at="2026-10-01 08:01:00"); _push("U7", "fcm-7")
    t_h = _born("H7", "2026-10-01 08:00:01"); _push("H7", "fcm-7", "2026-10-02 08:00:00")
    with _db() as conn:
        conn.execute("INSERT INTO referral_codes (device_id, code) VALUES ('U7', 'FAMCODE1'), ('H7', 'TWINCODE')")
    assert client.post("/api/push/register", headers=_b(t_h), json={"token": "fcm-7"}).json()["device_id"] == "U7"
    with _db() as conn:
        assert conn.execute("SELECT device_id FROM referral_codes WHERE code='TWINCODE'").fetchone()[0] == "H7"
    t_new = client.post("/api/chat/sessions", json={"device_id": "NEWINVITEE"}).json()["token"]
    r = client.post("/api/referral/claim", headers=_b(t_new), json={"code": "TWINCODE"})
    assert r.status_code != 404


# 8. Every row a fold moves is logged, and the fold can be reverted.
def test_8_fold_is_logged_row_by_row_and_reversible(client):
    _born("U8", "2026-10-01 08:00:00"); _child("U8", "Kid", at="2026-10-01 08:01:00"); _push("U8", "fcm-8")
    t_h = _born("H8", "2026-10-01 08:00:01"); _push("H8", "fcm-8")
    s1 = store.create_session("H8", {})
    assert client.post("/api/push/register", headers=_b(t_h), json={"token": "fcm-8"}).json()["device_id"] == "U8"
    with _db() as conn:
        assert conn.execute("SELECT device_id FROM chat_sessions WHERE id=?", (s1,)).fetchone()[0] == "U8"
        logged = {(r["table_name"], r["action"]) for r in conn.execute(
            "SELECT table_name, action FROM device_fold_log WHERE from_device = 'H8' AND to_device = 'U8'")}
        assert {("chat_sessions", "moved"), ("api_tokens", "moved"), ("push_tokens", "deleted")} <= logged
        assert twins.revert_fold(conn, "H8") > 0
        assert conn.execute("SELECT device_id FROM chat_sessions WHERE id=?", (s1,)).fetchone()[0] == "H8"
        assert conn.execute("SELECT COUNT(*) FROM device_aliases").fetchone()[0] == 0
    assert store.validate_token(t_h)["device_id"] == "H8"


# 9. A token minted for the twin by someone who only knew its id does not ride
#    the legitimate fold.
def test_9_foreign_token_does_not_ride_the_legit_fold(client):
    _born("U9", "2026-10-01 08:00:00"); _child("U9", "FamilyKid", at="2026-10-01 08:01:00")
    _push("U9", "fcm-9")
    t_app = _born("H9", "2026-10-01 08:00:01"); _push("H9", "fcm-9")
    foreign = client.post("/api/chat/sessions", json={"device_id": "H9"}).json()["token"]
    assert _children(client, foreign) == []
    assert client.post("/api/push/register", headers=_b(t_app), json={"token": "fcm-9"}).json()["device_id"] == "U9"
    assert _children(client, t_app) == ["FamilyKid"]
    assert _children(client, foreign) == []
