"""PR #26 final review — the seven probes, inverted into regression tests.

Each probe (review-pr26/final/probes) passed on e420b001, proving a live or a
dormant hole. Each test here is that probe with its assertions turned around.

The principle behind every fix: until SESSION_MINT_ENFORCE is on, a session
for a known device id is cheap — so a destructive effect either needs a
confirmed session (proven to hold the phone, outside every pause) or is
limited to what the old behaviour already allowed.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from httpx import Response

from app.db.init_db import get_conn
from app.services import child_memory as cm
from app.services import device_alerts, push_sender
from tests.device_proof_support import fcm, prove, register_push, start


@pytest.fixture
def client():
    from app.main import app
    with TestClient(app) as c:
        yield c


def _mint(client, device):
    r = client.post("/api/chat/sessions", json={"device_id": device})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def _family(client, device):
    owner = _mint(client, device)
    prove(client, owner, push_token=f"fcm-owner-{device}", build=120)
    cid = client.post("/api/children", json={"name": "سالم", "age_group": "4-6"},
                      headers=owner).json()["id"]
    r = client.post(f"/api/children/{cid}/memory", headers=owner,
                    json={"category": "challenge", "fact": "طفلي يخاف من الظلام ويستيقظ ليلًا"})
    assert r.status_code == 201, r.text
    return owner, cid


def _age(device, table, col, hours):
    conn = get_conn()
    conn.execute(f"UPDATE {table} SET {col} = datetime('now', ?) WHERE device_id = ?",
                 (f"-{hours} hours", device))
    conn.commit()
    conn.close()


def _make_established(device, hours=100):
    for t in ("api_tokens", "chat_sessions", "child_profiles"):
        _age(device, t, "created_at", hours)


def _code(r):
    return r.json()["detail"]["code"]


def _one(sql, *args):
    conn = get_conn()
    try:
        return conn.execute(sql, args).fetchone()
    finally:
        conn.close()


# ── Item 3 (F1): a dead token does not turn a change into a "first token" ───


def test_a_dead_token_does_not_launder_the_cooldown(client, monkeypatch):
    monkeypatch.setenv("CHILD_MEMORY_MIN_BUILD", "112")
    owner, cid = _family(client, "dev-launder")
    _make_established("dev-launder")
    intruder = _mint(client, "dev-launder")
    register_push(client, intruder, "fcm-intruder-dead")          # unvouched change
    assert client.get(f"/api/children/{cid}/memory", headers=intruder).status_code == 403
    with fcm(fail={"ok": True, "sent": False, "reason": "unregistered"}):
        assert start(client, intruder).status_code == 409         # FCM: that token is dead
    # A tombstone, not a hole: the row stays, with no token.
    row = _one("SELECT token FROM push_tokens WHERE device_id = 'dev-launder'")
    assert row is not None and row[0] == ""
    assert client.get("/api/push/token", headers=intruder).json()["registered"] is False
    # The intruder's next token is a change — the device confirmed before —
    # not a first token: everything pauses.
    prove(client, intruder, push_token="fcm-intruder-live", build=120)
    r = client.get(f"/api/children/{cid}/memory", headers=intruder)
    assert r.status_code == 403 and _code(r) == "device_proof_cooldown"
    assert client.get("/api/device-proof", headers=intruder).json()["cooldown_until"]


def test_a_reaped_owner_token_does_not_open_the_device(client):
    """The owner's token died (uninstall) and a push reaped it. Whoever
    registers next is not a "first token": the device confirmed before."""
    owner, cid = _family(client, "dev-reaped")
    _make_established("dev-reaped")
    push_sender._remove_token("dev-reaped")                        # what UnregisteredError does
    assert _one("SELECT token FROM push_tokens WHERE device_id = 'dev-reaped'")[0] == ""
    intruder = _mint(client, "dev-reaped")
    prove(client, intruder, push_token="fcm-intruder-first", build=120)
    r = client.get(f"/api/children/{cid}/memory", headers=intruder)
    assert r.status_code == 403 and _code(r) == "device_proof_cooldown"
    assert client.delete("/api/privacy/account?confirm=true", headers=intruder).status_code == 403


def test_send_to_device_tombstones_only_the_token_it_tried(monkeypatch):
    """A newer token registered while a push was in flight survives."""
    conn = get_conn()
    conn.execute("INSERT INTO push_tokens (device_id, token) VALUES ('dev-race', 'fcm-new')")
    conn.commit()
    conn.close()
    push_sender.remove_token_if_current("dev-race", "fcm-old")
    assert _one("SELECT token FROM push_tokens WHERE device_id = 'dev-race'")[0] == "fcm-new"
    push_sender.remove_token_if_current("dev-race", "fcm-new")
    assert _one("SELECT token FROM push_tokens WHERE device_id = 'dev-race'")[0] == ""


# ── Item 1 (F2): account deletion follows only confirmed Google links ───────

_WEB = "620240456244-d7a3fd35ianuu34i1sobb0pj4ncttmdu.apps.googleusercontent.com"


def _google(sub):
    return Response(200, json={"iss": "https://accounts.google.com", "sub": sub,
                               "aud": _WEB, "exp": "9999999999"})


def test_an_unconfirmed_link_does_not_carry_account_deletion_to_the_victim(client):
    victim_owner, cid = _family(client, "dev-victim-g")
    _make_established("dev-victim-g")
    attacker = _mint(client, "dev-attacker-own")
    prove(client, attacker, push_token="fcm-attacker-own")
    with patch("app.routers.identity.httpx.AsyncClient.get", new_callable=AsyncMock,
               return_value=_google("g-attacker")):
        assert client.post("/api/identity/link-google", json={"id_token": "t"},
                           headers=attacker).json()["ok"] is True
        bare = _mint(client, "dev-victim-g")                       # no proof, no push token
        assert client.post("/api/identity/link-google", json={"id_token": "t"},
                           headers=bare).json()["ok"] is True
    assert _one("SELECT confirmed FROM identity_links WHERE device_id = 'dev-victim-g'")[0] == 0
    assert _one("SELECT confirmed FROM identity_links WHERE device_id = 'dev-attacker-own'")[0] == 1

    r = client.delete("/api/privacy/account?confirm=true", headers=attacker)
    assert r.status_code == 200 and r.json()["devices"] == 1, r.text
    conn = get_conn()
    left = {t: conn.execute(f"SELECT COUNT(*) FROM {t} WHERE device_id = 'dev-victim-g'"
                            ).fetchone()[0]
            for t in ("child_profiles", "child_facts", "push_tokens", "device_proofs")}
    links = conn.execute("SELECT COUNT(*) FROM identity_links WHERE google_id = 'g-attacker'"
                         ).fetchone()[0]
    conn.close()
    assert left == {"child_profiles": 1, "child_facts": 1, "push_tokens": 1,
                    "device_proofs": 1}                            # the family is untouched
    assert links == 0                                              # only the link to nothing goes
    assert client.get("/api/children", headers=victim_owner).status_code == 200


def test_through_its_own_unconfirmed_link_the_caller_deletes_only_itself(client):
    """A phone linked to the family's Google account without a proof — an old
    build's link, or someone else's — cannot take the account with it."""
    family_phone, _ = _family(client, "dev-family-phone")
    caller = _mint(client, "dev-unconfirmed-phone")
    prove(client, caller, push_token="fcm-unconfirmed-phone")
    conn = get_conn()
    conn.execute("INSERT INTO parent_identities (google_id, email) VALUES ('g-family', 'f@example.com')")
    conn.execute("INSERT INTO identity_links (device_id, google_id, confirmed) "
                 "VALUES ('dev-family-phone', 'g-family', 1)")
    conn.execute("INSERT INTO identity_links (device_id, google_id, confirmed) "
                 "VALUES ('dev-unconfirmed-phone', 'g-family', 0)")
    conn.commit()
    conn.close()
    r = client.delete("/api/privacy/account?confirm=true", headers=caller)
    assert r.status_code == 200 and r.json()["devices"] == 1 and r.json()["signed_in"] is False
    assert _one("SELECT COUNT(*) FROM child_profiles WHERE device_id = 'dev-family-phone'")[0] == 1
    assert _one("SELECT COUNT(*) FROM parent_identities WHERE google_id = 'g-family'")[0] == 1
    assert _one("SELECT COUNT(*) FROM identity_links WHERE device_id = 'dev-family-phone'")[0] == 1
    assert _one("SELECT COUNT(*) FROM identity_links WHERE device_id = 'dev-unconfirmed-phone'")[0] == 0
    assert client.get("/api/children", headers=family_phone).status_code == 200


def test_a_bare_session_cannot_move_a_confirmed_link(client):
    owner, _ = _family(client, "dev-linked")
    with patch("app.routers.identity.httpx.AsyncClient.get", new_callable=AsyncMock,
               return_value=_google("g-owner")):
        assert client.post("/api/identity/link-google", json={"id_token": "t"},
                           headers=owner).json()["ok"] is True
    bare = _mint(client, "dev-linked")
    with patch("app.routers.identity.httpx.AsyncClient.get", new_callable=AsyncMock,
               return_value=_google("g-someone-else")):
        r = client.post("/api/identity/link-google", json={"id_token": "t"}, headers=bare)
    assert r.json() == {"ok": False, "error": "device_proof_required"}
    assert tuple(_one("SELECT google_id, confirmed FROM identity_links "
                      "WHERE device_id = 'dev-linked'")) == ("g-owner", 1)
    # …and re-linking the same account from a bare session does not downgrade it.
    with patch("app.routers.identity.httpx.AsyncClient.get", new_callable=AsyncMock,
               return_value=_google("g-owner")):
        assert client.post("/api/identity/link-google", json={"id_token": "t"},
                           headers=bare).json()["ok"] is True
    assert _one("SELECT confirmed FROM identity_links WHERE device_id = 'dev-linked'")[0] == 1


# ── Item 2 (F3): child deletion honours the pause; unconfirmed = old effect ──


def _legacy_family(client, device):
    h = _mint(client, device)
    cid = client.post("/api/children", json={"name": "سالم", "age_group": "4-6"},
                      headers=h).json()["id"]
    conn = get_conn()
    conn.execute("INSERT INTO lesson_progress (device_id, child_id, path_id, lesson_id, status) "
                 "VALUES (?, ?, 'p', 'l', 'completed')", (device, cid))
    conn.commit()
    conn.close()
    _make_established(device)
    return h, cid


def test_the_first_token_pause_covers_child_deletion_without_a_proof(client):
    _, cid = _legacy_family(client, "dev-legacy-fam")
    intruder = _mint(client, "dev-legacy-fam")
    register_push(client, intruder, "fcm-intruder-first")           # first token, established
    assert client.get("/api/device-proof", headers=intruder).json()["deletion_paused_until"]
    r = client.delete(f"/api/children/{cid}", headers=intruder)
    assert r.status_code == 403 and _code(r) == "device_proof_cooldown"
    r = client.delete(f"/api/children/{cid}/progress", headers=intruder)
    assert r.status_code == 403 and _code(r) == "device_proof_cooldown"
    assert _one("SELECT COUNT(*) FROM lesson_progress WHERE child_id = ?", cid)[0] == 1


def test_an_unconfirmed_child_deletion_does_only_what_it_did_before(client):
    """A device that never proved, outside every pause: the old route — the
    profile row, nothing more. Progress (no foreign key) stays, as it did."""
    h, cid = _legacy_family(client, "dev-legacy-old")
    assert client.delete(f"/api/children/{cid}", headers=h).status_code == 200
    assert _one("SELECT COUNT(*) FROM child_profiles WHERE id = ?", cid)[0] == 0
    assert _one("SELECT COUNT(*) FROM lesson_progress WHERE child_id = ?", cid)[0] == 1


# ── Item 5 (F4): a second notice within a day is delayed, not dropped ──────

DAY = datetime(2026, 10, 5, 9, 0)


def test_a_second_takeover_within_a_day_is_told_the_next_day(client, monkeypatch):
    sent = []
    monkeypatch.setattr(push_sender, "send_notification_to_token",
                        lambda token, *a, **k: sent.append(token) or {"ok": True, "sent": True})
    owner, cid = _family(client, "dev-twice")
    cm.record_tz_offset("dev-twice", 180)
    intruder = _mint(client, "dev-twice")
    register_push(client, intruder, "fcm-x1")
    assert device_alerts.run_due_alerts(DAY)["sent"] == 1           # owner told once
    register_push(client, owner, "fcm-owner-dev-twice")             # owner takes it back
    assert client.get(f"/api/children/{cid}/memory", headers=owner).status_code == 200
    intruder2 = _mint(client, "dev-twice")
    prove(client, intruder2, push_token="fcm-x2")                   # takeover #2, same day
    out = device_alerts.run_due_alerts(DAY)
    assert out["sent"] == 0 and out["waiting"] == 1                 # owed, and waiting
    assert _one("SELECT old_token FROM device_alerts WHERE device_id='dev-twice'")[0] == \
        "fcm-owner-dev-twice"
    assert device_alerts.run_due_alerts(DAY + timedelta(hours=25))["sent"] == 1
    assert sent == ["fcm-owner-dev-twice", "fcm-owner-dev-twice"]  # told about both


# ── Item 6 (F5): the weekly plan uses memory only for a confirmed session ──


def test_the_weekly_plan_keeps_memory_from_an_unproven_session(client, monkeypatch):
    monkeypatch.setenv("CHILD_MEMORY_MIN_BUILD", "112")
    owner, cid = _family(client, "dev-plan-leak")
    cm.record_tz_offset("dev-plan-leak", 180)
    bare = _mint(client, "dev-plan-leak")
    assert client.get(f"/api/children/{cid}/memory", headers=bare).status_code == 403
    plan = client.get(f"/api/children/{cid}/weekly-plan?tz_offset_minutes=-600",
                      headers=bare).json()
    assert plan["focus"]["reason"] != "memory"
    # The unproven session did not move the family's clock.
    assert _one("SELECT tz_offset_minutes FROM child_memory_settings "
                "WHERE device_id='dev-plan-leak'")[0] == 180
    # The confirmed owner gets the plan memory shaped — a different cached plan.
    mine = client.get(f"/api/children/{cid}/weekly-plan", headers=owner).json()
    assert mine["focus"]["reason"] == "memory" and mine["focus"]["topic"] in ("sleep", "fear")
    again = client.get(f"/api/children/{cid}/weekly-plan", headers=bare).json()
    assert again["focus"]["reason"] != "memory"


# ── Item 4 (F6): the owner taking the device back ends the other proofs ─────


def test_a_settled_intruder_cannot_retake_the_device_silently(client, monkeypatch):
    sent = []
    monkeypatch.setattr(push_sender, "send_notification_to_token",
                        lambda token, *a, **k: sent.append(token) or {"ok": True, "sent": True})
    owner, cid = _family(client, "dev-settle")
    cm.record_tz_offset("dev-settle", 180)
    intruder = _mint(client, "dev-settle")
    prove(client, intruder, push_token="fcm-intr")                 # takeover, cooldown
    assert device_alerts.run_due_alerts(DAY)["sent"] == 1
    _age("dev-settle", "push_tokens", "token_since", 73)
    prove(client, intruder)                                         # re-proved: clean
    register_push(client, owner, "fcm-owner-dev-settle")            # owner takes it back
    assert client.get(f"/api/children/{cid}/memory", headers=owner).status_code == 200
    r = client.get(f"/api/children/{cid}/memory", headers=intruder)
    assert r.status_code == 403 and _code(r) == "device_proof_required"   # its proof is gone
    conn = get_conn()
    conn.execute("UPDATE device_alerts SET sent_at = datetime('now', '-2 days')")
    conn.commit()
    conn.close()
    register_push(client, intruder, "fcm-intr")                     # tries to flip back
    st = client.get("/api/device-proof", headers=intruder).json()
    assert st["cooldown_until"] and st["deletion_paused_until"]
    prove(client, intruder)
    r = client.get(f"/api/children/{cid}/memory", headers=intruder)
    assert r.status_code == 403 and _code(r) == "device_proof_cooldown"
    assert _one("SELECT old_token FROM device_alerts WHERE device_id='dev-settle'")[0] == \
        "fcm-owner-dev-settle"                                      # the owner is owed a notice
    r = client.delete("/api/privacy/account?confirm=true", headers=intruder)
    assert r.status_code == 403


# ── Item 8: every timestamp the API returns is ISO 8601, UTC, with Z ───────

_ISO_Z = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$"


def test_every_timestamp_is_iso_8601_with_z(client, monkeypatch):
    import re
    stamp = re.compile(_ISO_Z)
    monkeypatch.setenv("CHILD_MEMORY_MIN_BUILD", "112")
    owner, cid = _family(client, "dev-iso")
    seen = []
    status = client.get("/api/device-proof", headers=owner).json()
    seen.append(status["proven_at"])
    facts = client.get(f"/api/children/{cid}/memory", headers=owner).json()["facts"]
    seen += [facts[0]["created_at"], facts[0]["updated_at"]]
    conn = get_conn()
    conn.execute("INSERT INTO followups (device_id, child_id, strategy, topic, due_at) "
                 "VALUES ('dev-iso', ?, 'روتين', 'sleep', datetime('now', '-1 hour'))", (cid,))
    conn.commit()
    conn.close()
    fu = client.get("/api/children/followups/due", headers=owner).json()["followups"][0]
    seen += [fu["due_at"], fu["created_at"]]
    seen.append(client.get(f"/api/children/{cid}/weekly-plan", headers=owner).json()["generated_at"])
    intruder = _mint(client, "dev-iso")
    prove(client, intruder, push_token="fcm-iso-intruder")
    r = client.get(f"/api/children/{cid}/memory", headers=intruder)
    seen.append(r.json()["detail"]["available_at"])
    seen.append(client.get("/api/device-proof", headers=intruder).json()["cooldown_until"])
    seen.append(client.get("/api/children/memory/settings", headers=intruder).json()["cooldown_until"])
    register_push(client, owner, "fcm-owner-dev-iso")             # the owner takes it back
    seen.append(client.delete("/api/privacy/memory", headers=owner).json()["deleted_at"])
    seen.append(client.delete("/api/privacy/account?confirm=true", headers=owner).json()["deleted_at"])
    assert all(isinstance(v, str) and stamp.match(v) for v in seen), seen
