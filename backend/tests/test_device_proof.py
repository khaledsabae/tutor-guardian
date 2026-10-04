"""Device proof — the FCM challenge behind the protected routes (PR #26 review, round 2).

The token-chain proof is gone: it locked out for good a device that once minted
without proof (F1), and let any pre-deploy token upgrade itself any number of
times (F2). A session now proves it holds the phone by receiving a one-time
code on the device's current push token and posting it back.

Pinned here, in the order the review asked for them:
  * recovery after an unproven mint;
  * a phone transfer;
  * the old-token fallback;
  * old pre-deploy tokens get NO elevated rights;
  * a wrong, an expired and a reused code;
  * a code delivered to an old push token;
plus: switching memory off never needs a proof (F3), the destructive child
routes (F3), learning and prompt/coach facts only for proven sessions on a
memory build (F4), the no-push-token path, and the silent data message.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.db.init_db import get_conn, hash_token
from app.services import child_memory as cm
from app.services import device_proof, push_sender
from tests.device_proof_support import complete, fcm, prove, register_push, start
from tests.test_child_memory import _RecordingProvider, pipeline  # noqa: F401 — fixture


@pytest.fixture
def client():
    from app.main import app
    with TestClient(app) as c:
        yield c


def _mint(client, device: str, proof: str | None = None) -> dict:
    """A new session for `device`; `proof` = a token sent as Authorization (what
    builds ≥ 106 do when they mint). Returns request headers."""
    headers = {"Authorization": f"Bearer {proof}"} if proof else {}
    r = client.post("/api/chat/sessions", json={"device_id": device}, headers=headers)
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def _token(h: dict) -> str:
    return h["Authorization"][7:]


def _child(client, h, name: str = "سالم", age: str = "7-9") -> int:
    r = client.post("/api/children", json={"name": name, "age_group": age}, headers=h)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _fact(client, h, cid: int, text: str = "طفلي يخاف من الظلام") -> dict:
    r = client.post(f"/api/children/{cid}/memory", headers=h,
                    json={"category": "temperament", "fact": text})
    assert r.status_code == 201, r.text
    return r.json()


def _refused(r) -> bool:
    return r.status_code == 403 and r.json()["detail"]["code"] == "device_proof_required"


def _memory(client, h, cid):
    return client.get(f"/api/children/{cid}/memory", headers=h)


def _expire(h: dict) -> None:
    conn = get_conn()
    conn.execute("UPDATE api_tokens SET expires_at = datetime('now', '-1 day') WHERE token = ?",
                 (hash_token(_token(h)),))
    conn.commit()
    conn.close()


# ── Every protected route ─────────────────────────────────────────────────

PROTECTED = [
    ("delete", "/api/privacy/account?confirm=true", None),
    ("delete", "/api/privacy/memory", None),
    ("put", "/api/children/memory/settings", {"enabled": True}),
    ("get", "/api/children/followups/due", None),
    ("get", "/api/children/followups/1", None),
    ("post", "/api/children/followups/1/answer", {"outcome": "worked"}),
    ("post", "/api/children/followups/1/dismiss", None),
    ("get", "/api/children/{cid}/followups", None),
    ("get", "/api/children/{cid}/memory", None),
    ("post", "/api/children/{cid}/memory", {"category": "temperament", "fact": "طفلي هادئ"}),
    ("patch", "/api/children/{cid}/memory/1", {"status": "rejected"}),
    ("delete", "/api/children/{cid}/memory/1", None),
    ("delete", "/api/children/{cid}/memory", None),
]


@pytest.mark.parametrize("method,path,body", PROTECTED)
def test_every_protected_route_needs_a_proven_session(client, method, path, body):
    h = _mint(client, f"dev-route-{method}-{abs(hash(path)) % 10_000}")
    cid = _child(client, h)
    url = path.format(cid=cid)
    kwargs = {"headers": h}
    if body is not None:
        kwargs["json"] = body
    r = getattr(client, method)(url, **kwargs)
    assert _refused(r), (url, r.status_code, r.text)
    detail = r.json()["detail"]
    assert detail["message"] and detail["message_en"] and detail["support_email"]

    prove(client, h, push_token=f"fcm-{url}")
    r = getattr(client, method)(url, **kwargs)
    assert r.status_code != 403, (url, r.text)


def test_switching_memory_off_never_needs_a_proof(client):
    h = _mint(client, "dev-off")
    r = client.put("/api/children/memory/settings", json={"enabled": False}, headers=h)
    assert r.status_code == 200 and r.json()["enabled"] is False
    assert r.json()["proven"] is False
    assert _refused(client.put("/api/children/memory/settings", json={"enabled": True},
                               headers=h))
    # The settings themselves hold nothing remembered: readable without a proof.
    assert client.get("/api/children/memory/settings", headers=h).status_code == 200
    prove(client, h, push_token="fcm-off")
    r = client.put("/api/children/memory/settings", json={"enabled": True}, headers=h)
    assert r.status_code == 200 and r.json()["enabled"] is True and r.json()["proven"] is True


# ── The six scenarios the review named ────────────────────────────────────


def test_recovery_after_an_unproven_mint(client):
    """F1: a build < 106 mints without proof after this deploys, then the
    family updates. The chain design locked that device out for good."""
    first = _mint(client, "dev-f1")
    cid = _child(client, first)
    old_build = _mint(client, "dev-f1")                       # no Authorization at all
    updated = _mint(client, "dev-f1", proof=_token(old_build))  # the new build's mint
    assert _refused(_memory(client, updated, cid))
    assert _refused(client.delete("/api/privacy/account?confirm=true", headers=updated))

    prove(client, updated, push_token="fcm-f1")
    assert _memory(client, updated, cid).status_code == 200
    # Proving one session lends nothing to the others of the same device.
    assert _refused(_memory(client, old_build, cid))
    assert _refused(_memory(client, first, cid))
    r = client.delete("/api/privacy/account?confirm=true", headers=updated)
    assert r.status_code == 200, r.text


def test_a_phone_transfer(client):
    """The device id comes back from a backup on a new phone; the token does
    not. The new phone proves on its own push token, and the old phone's proof
    ends with the push token it was made against. A new phone looks exactly
    like a takeover (round 3), so the protected routes wait out the cooldown —
    memory can be switched off at once."""
    old_phone = _mint(client, "dev-move")
    prove(client, old_phone, push_token="fcm-old-phone")
    cid = _child(client, old_phone)
    _fact(client, old_phone, cid)

    new_phone = _mint(client, "dev-move")                    # restored id, no token
    register_push(client, new_phone, "fcm-new-phone")
    assert _refused(_memory(client, new_phone, cid))
    assert _refused(_memory(client, old_phone, cid))         # its push token is gone

    with fcm() as inbox:
        r = start(client, new_phone)
        assert r.status_code == 202
        code = inbox.last_for("fcm-new-phone")
        assert not [m for t, m in inbox.messages if t == "fcm-old-phone"]
        assert complete(client, new_phone, code["challenge_id"], code["code"]).status_code == 200
    r = _memory(client, new_phone, cid)
    assert r.status_code == 403 and r.json()["detail"]["code"] == "device_proof_cooldown"
    assert client.put("/api/children/memory/settings", json={"enabled": False},
                      headers=new_phone).status_code == 200
    conn = get_conn()
    conn.execute("UPDATE push_tokens SET token_since = datetime('now', '-73 hours') "
                 "WHERE device_id = 'dev-move'")
    conn.commit()
    conn.close()
    facts = _memory(client, new_phone, cid).json()["facts"]
    assert [f["fact"] for f in facts] == ["طفلي يخاف من الظلام"]


def test_the_old_token_fallback(client):
    """An install whose token lapsed (TOKEN_TTL_DAYS idle) mints its next
    session with the lapsed token as proof of the device. That still works —
    and gives the new session no rights it did not prove for itself."""
    lapsed = _mint(client, "dev-lapsed")
    prove(client, lapsed, push_token="fcm-lapsed")
    cid = _child(client, lapsed)
    _expire(lapsed)
    assert client.get("/api/children", headers=lapsed).status_code == 401

    fresh = _mint(client, "dev-lapsed", proof=_token(lapsed))
    assert client.get("/api/children", headers=fresh).status_code == 200
    assert _refused(_memory(client, fresh, cid))
    prove(client, fresh)                                     # the push token is unchanged
    assert _memory(client, fresh, cid).status_code == 200


def test_old_pre_deploy_tokens_get_no_elevated_rights(client, pipeline, monkeypatch):  # noqa: F811
    """F2: a token minted without proof before this deployed — even expired,
    even re-minted from over and over — gets nothing beyond what it had,
    while the owner's proven session keeps working."""
    owner = _mint(client, "dev-f2")
    prove(client, owner, push_token="fcm-f2", build=120)
    monkeypatch.setenv("CHILD_MEMORY_MIN_BUILD", "112")
    cid = _child(client, owner, age="4-6")
    _fact(client, owner, cid)

    pre_deploy = _mint(client, "dev-f2")
    _expire(pre_deploy)
    for _ in range(3):
        upgraded = _mint(client, "dev-f2", proof=_token(pre_deploy))
        assert _refused(_memory(client, upgraded, cid))
        assert _refused(client.delete(f"/api/children/{cid}", headers=upgraded))
        assert _refused(client.delete("/api/privacy/account?confirm=true", headers=upgraded))
        assert _refused(client.delete("/api/privacy/memory", headers=upgraded))
    # …nor through the assistant (F4): the remembered fact stays out of its prompt.
    _RecordingProvider.prompts = []
    r = client.post("/api/assistant/stream", headers=upgraded, json={
        "age_group": "4-6", "severity": "خفيف", "child_id": cid,
        "message_text": "ابني يرفض النوم وحده، ماذا أفعل؟"})
    assert r.status_code == 200
    assert _RecordingProvider.prompts
    assert not any("يخاف من الظلام" in p for p in _RecordingProvider.prompts)

    assert _memory(client, owner, cid).status_code == 200


def test_a_wrong_an_expired_and_a_reused_code(client):
    h = _mint(client, "dev-codes")
    register_push(client, h, "fcm-codes")

    # Wrong: refused; MAX_ATTEMPTS wrong answers burn the challenge.
    with fcm() as inbox:
        start(client, h)
        msg = inbox.last_for("fcm-codes")
    r = complete(client, h, msg["challenge_id"], "not-the-code")
    assert r.status_code == 409 and r.json()["detail"]["reason"] == "wrong_code"
    for _ in range(device_proof.MAX_ATTEMPTS - 1):
        complete(client, h, msg["challenge_id"], "still-wrong")
    r = complete(client, h, msg["challenge_id"], msg["code"])
    assert r.status_code == 409 and r.json()["detail"]["reason"] == "used"
    assert client.get("/api/device-proof", headers=h).json()["proven"] is False

    # Expired.
    with fcm() as inbox:
        start(client, h)
        msg = inbox.last_for("fcm-codes")
    conn = get_conn()
    conn.execute("UPDATE device_proof_challenges SET expires_at = datetime('now', '-1 second') "
                 "WHERE id = ?", (int(msg["challenge_id"]),))
    conn.commit()
    conn.close()
    r = complete(client, h, msg["challenge_id"], msg["code"])
    assert r.status_code == 409 and r.json()["detail"]["reason"] == "expired"

    # Reused: one use only — not even to restore a proof the device lost.
    with fcm() as inbox:
        start(client, h)
        msg = inbox.last_for("fcm-codes")
    assert complete(client, h, msg["challenge_id"], msg["code"]).status_code == 200
    r = complete(client, h, msg["challenge_id"], msg["code"])
    assert r.status_code == 409 and r.json()["detail"]["reason"] == "used"
    register_push(client, h, "fcm-codes-rotated")
    r = complete(client, h, msg["challenge_id"], msg["code"])
    assert r.status_code == 409
    assert client.get("/api/device-proof", headers=h).json()["proven"] is False

    # Every failure tells the app what to show, in both languages.
    detail = r.json()["detail"]
    assert detail["code"] == "proof_failed" and detail["message"] and detail["message_en"]


def test_a_code_delivered_to_an_old_push_token(client):
    h = _mint(client, "dev-oldpush")
    register_push(client, h, "fcm-before")
    with fcm() as inbox:
        start(client, h)
        msg = inbox.last_for("fcm-before")
    register_push(client, h, "fcm-after")                     # rotated before the answer
    r = complete(client, h, msg["challenge_id"], msg["code"])
    assert r.status_code == 409 and r.json()["detail"]["reason"] == "push_token_changed"
    # Burnt: switching back does not revive it.
    register_push(client, h, "fcm-before")
    r = complete(client, h, msg["challenge_id"], msg["code"])
    assert r.status_code == 409 and r.json()["detail"]["reason"] == "used"
    assert client.get("/api/device-proof", headers=h).json()["proven"] is False
    # A fresh challenge goes to the current token, and works.
    prove(client, h)
    assert client.get("/api/device-proof", headers=h).json()["proven"] is True


# ── Binding: a code proves only the session that asked for it ─────────────


def test_a_code_proves_only_the_session_that_asked(client):
    """Otherwise the owner's app, posting back a code it received, would prove
    a stranger's session that started the challenge."""
    stranger = _mint(client, "dev-bind")
    owner = _mint(client, "dev-bind")
    register_push(client, owner, "fcm-owner")
    with fcm() as inbox:
        assert start(client, stranger).status_code == 202
        msg = inbox.last_for("fcm-owner")                    # lands on the owner's phone
    r = complete(client, owner, msg["challenge_id"], msg["code"])
    assert r.status_code == 409 and r.json()["detail"]["reason"] == "other_session"
    r = complete(client, stranger, msg["challenge_id"], msg["code"])
    assert r.status_code == 409 and r.json()["detail"]["reason"] == "used"
    for h in (stranger, owner):
        assert client.get("/api/device-proof", headers=h).json()["proven"] is False
    # Another device's challenge id is simply not found.
    other = _mint(client, "dev-bind-other")
    assert complete(client, other, msg["challenge_id"], msg["code"]).status_code == 404


def test_the_code_never_leaves_in_a_response(client):
    h = _mint(client, "dev-secret")
    register_push(client, h, "fcm-secret")
    with fcm() as inbox:
        r = start(client, h)
        msg = inbox.last_for("fcm-secret")
    assert r.status_code == 202
    assert set(r.json()) == {"challenge_id", "expires_in"}
    assert msg["code"] not in r.text and int(msg["challenge_id"]) == r.json()["challenge_id"]
    conn = get_conn()
    stored = conn.execute("SELECT code_hash, push_token_hash, token_hash FROM "
                          "device_proof_challenges WHERE id = ?",
                          (r.json()["challenge_id"],)).fetchone()
    conn.close()
    assert msg["code"] not in tuple(stored) and "fcm-secret" not in tuple(stored)
    assert _token(h) not in tuple(stored)


# ── When the code cannot be delivered ─────────────────────────────────────


def test_no_push_token_says_so_with_the_support_path(client):
    h = _mint(client, "dev-nopush")
    r = start(client, h)
    assert r.status_code == 409
    d = r.json()["detail"]
    assert d["code"] == "no_push_token" and d["support_email"] == "support@alsaba.cloud"
    assert "support@alsaba.cloud" in d["message"] and "support@alsaba.cloud" in d["message_en"]
    assert client.get("/api/device-proof", headers=h).json() == {
        "proven": False, "proven_at": None, "push_registered": False,
        "cooldown_until": None, "deletion_paused_until": None}


def test_a_dead_push_token_is_forgotten_and_reported(client):
    h = _mint(client, "dev-deadpush")
    register_push(client, h, "fcm-dead")
    with fcm(fail={"ok": True, "sent": False, "reason": "unregistered"}):
        r = start(client, h)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "no_push_token"
    assert client.get("/api/device-proof", headers=h).json()["push_registered"] is False


def test_push_unavailable_is_a_503_with_the_support_path(client):
    h = _mint(client, "dev-nofcm")
    register_push(client, h, "fcm-nofcm")
    with fcm(fail={"ok": False, "error": "firebase_credentials_not_configured"}):
        r = start(client, h)
    assert r.status_code == 503
    assert r.json()["detail"]["code"] == "push_unavailable"
    assert r.json()["detail"]["support_email"]


def test_starts_are_rate_limited_per_session(client):
    h = _mint(client, "dev-rate")
    register_push(client, h, "fcm-rate")
    with fcm():
        codes = [start(client, h).status_code for _ in range(device_proof.MAX_STARTS_PER_SESSION_HOUR + 1)]
    assert codes[:-1] == [202] * device_proof.MAX_STARTS_PER_SESSION_HOUR
    assert codes[-1] == 429


def test_the_challenge_is_a_silent_data_message(monkeypatch):
    sent = []
    monkeypatch.setattr(push_sender, "_ensure_app", lambda: True)
    monkeypatch.setattr(push_sender.messaging, "send", lambda m, app=None: sent.append(m) or "id")
    r = push_sender.send_data_message(
        "fcm-x", {"type": "device_proof", "challenge_id": "7", "code": "c"}, ttl_seconds=300)
    assert r == {"ok": True, "sent": True}
    (m,) = sent
    assert m.notification is None and m.android.notification is None
    assert m.data == {"type": "device_proof", "challenge_id": "7", "code": "c"}
    assert m.android.priority == "high" and m.android.ttl == 300
    assert m.token == "fcm-x"


# ── Destructive child routes (F3) ─────────────────────────────────────────


def test_child_deletion_needs_a_proof_once_the_device_enrolled(client):
    owner = _mint(client, "dev-del")
    prove(client, owner, push_token="fcm-del")
    keep, gone = _child(client, owner, "سالم"), _child(client, owner, "منى")
    _fact(client, owner, keep)
    stranger = _mint(client, "dev-del")
    assert _refused(client.delete(f"/api/children/{keep}", headers=stranger))
    assert _refused(client.delete(f"/api/children/{keep}/progress", headers=stranger))
    assert len(_memory(client, owner, keep).json()["facts"]) == 1
    assert client.delete(f"/api/children/{gone}", headers=owner).status_code == 200
    assert client.delete(f"/api/children/{keep}/progress", headers=owner).status_code == 200


def test_child_deletion_on_a_build_that_cannot_prove_still_works(client, monkeypatch):
    """No build on Play can answer a challenge yet. A device that never proved
    (and so has no memory: nothing writes memory without a proof) keeps the
    child deletion it has today — until the forced-update floor reaches the
    build that can prove."""
    h = _mint(client, "dev-legacy")
    a, b = _child(client, h, "سالم"), _child(client, h, "منى")
    assert client.delete(f"/api/children/{a}", headers=h).status_code == 200

    monkeypatch.setenv("CHILD_MEMORY_MIN_BUILD", "112")
    monkeypatch.setenv("MINIMUM_BUILD_NUMBER", "112")
    assert _refused(client.delete(f"/api/children/{b}", headers=h))
    assert _refused(client.delete(f"/api/children/{b}/progress", headers=h))


# ── Learning and injection (F4) ───────────────────────────────────────────


def test_memory_is_used_and_learned_only_for_a_proven_session_on_a_memory_build(
        client, monkeypatch):
    monkeypatch.setenv("CHILD_MEMORY_MIN_BUILD", "112")
    owner = _mint(client, "dev-f4")
    prove(client, owner, push_token="fcm-f4", build=120)
    cid = _child(client, owner, age="4-6")
    _fact(client, owner, cid)

    assert cm.memory_in_use("dev-f4", proven=True)
    assert not cm.memory_in_use("dev-f4", proven=False)
    _, block, n = cm.prompt_context("dev-f4", child_id=cid, age_group="4-6",
                                    question="النوم", proven=True)
    assert n == 1 and "يخاف من الظلام" in block
    assert cm.prompt_context("dev-f4", child_id=cid, age_group="4-6",
                             question="النوم", proven=False)[1:] == ("", 0)
    assert "يخاف من الظلام" in cm.coach_facts("dev-f4", cid, "النوم", proven=True)
    assert cm.coach_facts("dev-f4", cid, "النوم", proven=False) == ""
    assert cm.schedule_extraction("dev-f4", cid, question="q", answer="a",
                                  proven=False) is None
    assert cm.extract_and_store("dev-f4", cid, question="ابني يرفض النوم وحده",
                                answer="…", proven=False) is None

    # A build without the memory screen: nothing used, nothing learned.
    register_push(client, owner, "fcm-f4", build=100)
    assert not cm.memory_in_use("dev-f4", proven=True)


def test_account_deletion_takes_the_proof_rows_with_it(client):
    h = _mint(client, "dev-wipe")
    prove(client, h, push_token="fcm-wipe")
    assert client.delete("/api/privacy/account?confirm=true", headers=h).status_code == 200
    conn = get_conn()
    left = {t: conn.execute(f"SELECT COUNT(*) FROM {t} WHERE device_id = 'dev-wipe'").fetchone()[0]
            for t in ("device_proofs", "device_proof_sessions", "device_proof_challenges")}
    conn.close()
    assert left == {"device_proofs": 0, "device_proof_sessions": 0,
                    "device_proof_challenges": 0}
