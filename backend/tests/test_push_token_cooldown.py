"""The push-token takeover (PR #26 review, round 3).

The attack: someone who knows a device id mints a session (no proof needed
before SESSION_MINT_ENFORCE), registers an FCM token they control for that
device, asks for a challenge, receives the code, and their session is proven.

What stops it: an unvouched push-token change pauses every protected route for
72 hours — even for a session proven on the new token — and the previous token
gets a notice; the owner, opening the app, re-registers their token, which
voids the newcomer's proof and is vouched for by the owner's own clean proof.
"""
from __future__ import annotations

from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app.db.init_db import get_conn
from app.services import child_memory as cm
from app.services import device_alerts, push_sender
from tests.device_proof_support import complete, fcm, prove, register_push, start
from tests.test_child_memory import _RecordingProvider, pipeline  # noqa: F401 — fixture


@pytest.fixture
def client():
    from app.main import app
    with TestClient(app) as c:
        yield c


def _mint(client, device: str) -> dict:
    r = client.post("/api/chat/sessions", json={"device_id": device})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def _family(client, device: str) -> tuple[dict, int]:
    """The owner: a proven session on their own phone, a child, a fact."""
    owner = _mint(client, device)
    prove(client, owner, push_token=f"fcm-owner-{device}")
    cid = client.post("/api/children", json={"name": "سالم", "age_group": "4-6"},
                      headers=owner).json()["id"]
    r = client.post(f"/api/children/{cid}/memory", headers=owner,
                    json={"category": "temperament", "fact": "طفلي يخاف من الظلام"})
    assert r.status_code == 201, r.text
    return owner, cid


def _code(r) -> str:
    return r.json()["detail"]["code"]


def _cooling(r) -> bool:
    return r.status_code == 403 and _code(r) == "device_proof_cooldown" \
        and r.json()["detail"]["available_at"]


def _age_token(device: str, hours: int) -> None:
    conn = get_conn()
    conn.execute("UPDATE push_tokens SET token_since = datetime('now', ?) WHERE device_id = ?",
                 (f"-{hours} hours", device))
    conn.commit()
    conn.close()


def _protected(client, h, cid) -> list:
    return [
        client.get(f"/api/children/{cid}/memory", headers=h),
        client.delete("/api/privacy/memory", headers=h),
        client.delete(f"/api/children/{cid}", headers=h),
        client.delete("/api/privacy/account?confirm=true", headers=h),
    ]


# ── The takeover sequence ─────────────────────────────────────────────────


def test_the_takeover_sequence_is_refused_within_72_hours(client, pipeline):  # noqa: F811
    owner, cid = _family(client, "dev-victim")
    cm.record_tz_offset("dev-victim", 180)

    intruder = _mint(client, "dev-victim")                    # knows the device id
    prove(client, intruder, push_token="fcm-intruder")         # their phone, their code
    for r in _protected(client, intruder, cid):
        assert _cooling(r), r.text
    settings = client.get("/api/children/memory/settings", headers=intruder).json()
    assert settings["proven"] is False and settings["cooldown_until"]
    # …nor through the assistant: no remembered fact in the prompt.
    _RecordingProvider.prompts = []
    r = client.post("/api/assistant/stream", headers=intruder, json={
        "age_group": "4-6", "severity": "خفيف", "child_id": cid,
        "message_text": "ابني يرفض النوم وحده، ماذا أفعل؟"})
    assert r.status_code == 200 and _RecordingProvider.prompts
    assert not any("يخاف من الظلام" in p for p in _RecordingProvider.prompts)
    # A second session minted after their token went in gets no exception —
    # «the token predates the session» would have let exactly this through.
    second = _mint(client, "dev-victim")
    prove(client, second)
    assert all(_cooling(r) for r in _protected(client, second, cid))
    # The family's data is all still there.
    conn = get_conn()
    assert conn.execute("SELECT COUNT(*) FROM child_facts WHERE child_id = ?", (cid,)).fetchone()[0] == 1
    conn.close()


def test_the_owner_opening_the_app_takes_it_back_at_once(client):
    owner, cid = _family(client, "dev-back")
    intruder = _mint(client, "dev-back")
    prove(client, intruder, push_token="fcm-intruder-back")
    # The owner opens the app: it re-registers their own token. Their clean
    # proof of that token vouches for it — no cooldown — and the intruder's
    # proof (made on the other token) is void.
    register_push(client, owner, "fcm-owner-dev-back")
    assert client.get(f"/api/children/{cid}/memory", headers=owner).status_code == 200
    r = client.get(f"/api/children/{cid}/memory", headers=intruder)
    assert r.status_code == 403 and _code(r) == "device_proof_required"
    # Putting their token back does not help the intruder: the take-back ended
    # every proof tied to another token (final review, item 4), so nothing
    # vouches for it — the change is unvouched, and everything pauses again.
    register_push(client, intruder, "fcm-intruder-back")
    assert client.get("/api/device-proof", headers=intruder).json()["cooldown_until"]
    prove(client, intruder)
    assert _cooling(client.get(f"/api/children/{cid}/memory", headers=intruder))


# ── The legitimate owner ──────────────────────────────────────────────────


def test_the_owner_after_a_reinstall_can_switch_memory_off_at_once_and_waits_for_the_rest(client):
    _, cid = _family(client, "dev-reinstall")
    fresh = _mint(client, "dev-reinstall")                    # same id, restored; new token
    register_push(client, fresh, "fcm-after-reinstall")
    r = client.put("/api/children/memory/settings", json={"enabled": False}, headers=fresh)
    assert r.status_code == 200 and r.json()["enabled"] is False
    prove(client, fresh)
    assert all(_cooling(r) for r in _protected(client, fresh, cid))
    assert client.get("/api/device-proof", headers=fresh).json()["cooldown_until"]
    _age_token("dev-reinstall", 71)
    assert _cooling(client.get(f"/api/children/{cid}/memory", headers=fresh))
    _age_token("dev-reinstall", 73)                           # the cooldown is over
    assert client.get(f"/api/children/{cid}/memory", headers=fresh).status_code == 200


def test_a_token_the_owner_rotated_from_a_proven_session_needs_no_wait(client):
    """FCM rotates a token under the same install: the session that proved the
    old token vouches for the new one. Any session minted after it — the
    token predates it — is served at once."""
    owner, cid = _family(client, "dev-rotate")
    register_push(client, owner, "fcm-rotated")               # onTokenRefresh
    prove(client, owner)                                      # on the new token
    assert client.get(f"/api/children/{cid}/memory", headers=owner).status_code == 200
    later = _mint(client, "dev-rotate")
    prove(client, later)
    assert client.get(f"/api/children/{cid}/memory", headers=later).status_code == 200
    conn = get_conn()
    assert conn.execute("SELECT old_token FROM device_alerts WHERE device_id = 'dev-rotate'"
                        ).fetchone() is None                  # and no alarm about it
    conn.close()


def test_a_first_token_is_not_a_change(client):
    h = _mint(client, "dev-first")
    prove(client, h, push_token="fcm-first")
    assert client.get("/api/device-proof", headers=h).json()["cooldown_until"] is None
    assert client.put("/api/children/memory/settings", json={"enabled": True},
                      headers=h).status_code == 200


def test_a_code_sent_before_the_token_changed_is_void(client):
    """Item 3: the proof is bound to the token hash at send time."""
    owner, _ = _family(client, "dev-void")
    with fcm() as inbox:
        assert start(client, owner).status_code == 202
        msg = inbox.last_for("fcm-owner-dev-void")
    intruder = _mint(client, "dev-void")
    register_push(client, intruder, "fcm-other")
    r = complete(client, owner, msg["challenge_id"], msg["code"])
    assert r.status_code == 409 and r.json()["detail"]["reason"] == "push_token_changed"


# ── A first token (round 4) ───────────────────────────────────────────────


def _make_established(device: str, hours: int = 100) -> None:
    """Age everything the device has: an established device, not a new install."""
    conn = get_conn()
    for table in ("api_tokens", "chat_sessions", "child_profiles"):
        conn.execute(f"UPDATE {table} SET created_at = datetime('now', ?) WHERE device_id = ?",
                     (f"-{hours} hours", device))
    conn.commit()
    conn.close()


def _tokenless_family(client, device: str) -> int:
    """A device with a child and history, and no push token on file — like 43%
    of the devices with children today."""
    h = _mint(client, device)
    cid = client.post("/api/children", json={"name": "سالم", "age_group": "4-6"},
                      headers=h).json()["id"]
    _make_established(device)
    return cid


def test_a_first_token_on_an_established_device_pauses_only_the_irreversible(client):
    """Whoever registers the first token — the family that just updated, or
    anyone who knows the id — cannot delete the account or a child for 72 hours.
    Memory stays open: the family keeps the memory screen (it is empty here)."""
    cid = _tokenless_family(client, "dev-tokenless")
    h = _mint(client, "dev-tokenless")
    prove(client, h, push_token="fcm-first-ever")

    assert client.get(f"/api/children/{cid}/memory", headers=h).status_code == 200
    assert client.put("/api/children/memory/settings", json={"enabled": False},
                      headers=h).status_code == 200
    assert client.delete("/api/privacy/memory", headers=h).status_code == 200
    settings = client.get("/api/children/memory/settings", headers=h).json()
    assert settings["proven"] is True and settings["cooldown_until"] is None
    status = client.get("/api/device-proof", headers=h).json()
    assert status["deletion_paused_until"] and status["cooldown_until"] is None

    _age_token("dev-tokenless", 71)
    assert _cooling(client.delete("/api/privacy/account?confirm=true", headers=h))
    assert _cooling(client.delete(f"/api/children/{cid}", headers=h))
    assert _cooling(client.delete(f"/api/children/{cid}/progress", headers=h))
    _age_token("dev-tokenless", 73)
    assert client.delete(f"/api/children/{cid}/progress", headers=h).status_code == 200
    assert client.delete("/api/privacy/account?confirm=true", headers=h).status_code == 200


def test_a_brand_new_install_is_not_paused(client):
    """Nothing older than 72 hours: an id that has not existed long enough to
    leak, and a family deleting an onboarding mistake."""
    h = _mint(client, "dev-onboarding")
    prove(client, h, push_token="fcm-onboarding")
    cid = client.post("/api/children", json={"name": "سالم", "age_group": "4-6"},
                      headers=h).json()["id"]
    assert client.get("/api/device-proof", headers=h).json()["deletion_paused_until"] is None
    assert client.delete(f"/api/children/{cid}", headers=h).status_code == 200
    assert client.delete("/api/privacy/account?confirm=true", headers=h).status_code == 200


def test_vouched_rotations_are_unaffected(client):
    """The pause belongs to the first token. Once its 72 hours are over, the
    install that proved it rotates its FCM token freely — even though that proof
    was made inside the pause."""
    cid = _tokenless_family(client, "dev-settled")
    h = _mint(client, "dev-settled")
    prove(client, h, push_token="fcm-settled-1")
    _age_token("dev-settled", 73)
    register_push(client, h, "fcm-settled-2")                # onTokenRefresh
    prove(client, h)
    status = client.get("/api/device-proof", headers=h).json()
    assert status["cooldown_until"] is None and status["deletion_paused_until"] is None
    assert client.delete(f"/api/children/{cid}", headers=h).status_code == 200


def test_a_first_token_cannot_be_rotated_out_of_its_pause(client, notices):
    """Whoever holds the first token cannot escape its 72 hours by moving to
    another token: their proof was made inside the pause, so it vouches for
    nothing — the move is an unvouched change, everything pauses, and the
    first token's phone is told."""
    cid = _tokenless_family(client, "dev-escape")
    h = _mint(client, "dev-escape")
    prove(client, h, push_token="fcm-escape-1")
    register_push(client, h, "fcm-escape-2")
    prove(client, h)
    assert _cooling(client.delete("/api/privacy/account?confirm=true", headers=h))
    assert _cooling(client.get(f"/api/children/{cid}/memory", headers=h))
    assert device_alerts.run_due_alerts(DAY)["sent"] == 1
    assert [n["token"] for n in notices] == ["fcm-escape-1"]


# ── The notice to the previous token ──────────────────────────────────────


@pytest.fixture
def notices(monkeypatch):
    sent: list[dict] = []

    def fake(token, title, body, data=None, channel_id="x"):
        sent.append({"token": token, "title": title, "body": body, "data": data,
                     "channel": channel_id})
        return {"ok": True, "sent": True}

    monkeypatch.setattr(push_sender, "send_notification_to_token", fake)
    return sent


DAY = datetime(2026, 10, 5, 9, 0)        # 12:00 at UTC+3
NIGHT = datetime(2026, 10, 5, 21, 0)     # 00:00 at UTC+3


def test_the_alert_goes_to_the_old_token_once(client, notices):
    _family(client, "dev-alert")
    cm.record_tz_offset("dev-alert", 180)
    intruder = _mint(client, "dev-alert")
    register_push(client, intruder, "fcm-intruder-1")
    register_push(client, intruder, "fcm-intruder-2")         # a second change, same day

    assert device_alerts.run_due_alerts(NIGHT)["sent"] == 0   # quiet hours
    assert notices == []
    assert device_alerts.run_due_alerts(DAY)["sent"] == 1
    assert [n["token"] for n in notices] == ["fcm-owner-dev-alert"]
    n = notices[0]
    assert n["data"] == {"type": "account_alert"} and n["channel"] == "almorabbi_safety"
    assert "سالم" not in n["title"] + n["body"] and "dev-alert" not in n["title"] + n["body"]
    assert "open the app" in n["body"] and "افتح التطبيق" in n["body"]
    # Once: nothing more today, and the old token is forgotten.
    assert device_alerts.run_due_alerts(DAY)["sent"] == 0
    conn = get_conn()
    assert conn.execute("SELECT old_token FROM device_alerts WHERE device_id = 'dev-alert'"
                        ).fetchone()[0] is None
    conn.close()


def test_an_alert_to_a_phone_that_is_gone_just_forgets_the_token(client, monkeypatch):
    _family(client, "dev-gone")
    register_push(client, _mint(client, "dev-gone"), "fcm-new")
    monkeypatch.setattr(push_sender, "send_notification_to_token",
                        lambda *a, **k: {"ok": True, "sent": False, "reason": "unregistered"})
    assert device_alerts.run_due_alerts(DAY)["dead"] == 1
    conn = get_conn()
    row = conn.execute("SELECT old_token FROM device_alerts WHERE device_id = 'dev-gone'").fetchone()
    conn.close()
    assert row[0] is None


def test_the_alert_sweep_runs_in_the_backend_loop():
    from app import main
    assert ("Account alert", device_alerts.run_due_alerts) in main._LOCAL_HOUR_JOBS
