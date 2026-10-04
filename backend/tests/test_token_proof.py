"""P1 (PR #26 review): knowing a device id must not be owning the family's data.

Before: any caller could mint a token for any known device id (minting without
proof is only logged until SESSION_MINT_ENFORCE is set), and a child's web token
carried the parent's device id in readable base64. A teen could decode it, mint
a parent session, and wipe the family or read the child memory.

Now proof of possession is recorded at mint, the irreversible and most private
routes require it, an unproven token cannot launder itself into a proven one,
and child tokens carry no device id.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time

import pytest
from fastapi.testclient import TestClient

from app.db.init_db import get_conn
from app.services import child_token


@pytest.fixture
def client():
    from app.main import app
    with TestClient(app) as c:
        yield c


def _mint(client, device, proof: str | None = None) -> str:
    headers = {"Authorization": f"Bearer {proof}"} if proof else {}
    r = client.post("/api/chat/sessions", json={"device_id": device}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["token"]


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _child(client, token) -> int:
    return client.post("/api/children", json={"name": "سالم", "age_group": "7-9"},
                       headers=_h(token)).json()["id"]


PROTECTED = [
    ("delete", "/api/privacy/account?confirm=true"),
    ("delete", "/api/privacy/memory"),
    ("get", "/api/children/memory/settings"),
    ("get", "/api/children/followups/due"),
    ("get", "/api/children/{cid}/memory"),
    ("delete", "/api/children/{cid}/memory"),
]


@pytest.mark.parametrize("method,path", PROTECTED)
def test_a_token_minted_without_proof_cannot_use_protected_routes(client, method, path):
    owner = _mint(client, "dev-victim")                  # the real install: first token
    cid = _child(client, owner)
    attacker = _mint(client, "dev-victim")               # knows the id, holds no proof
    r = getattr(client, method)(path.format(cid=cid), headers=_h(attacker))
    assert r.status_code == 403, r.text
    assert r.json()["detail"]["code"] == "proof_required"
    # The owner's own token works.
    ok = getattr(client, method)(path.format(cid=cid), headers=_h(owner))
    assert ok.status_code == 200, ok.text


def test_an_unproven_token_cannot_launder_itself_into_a_proven_one(client):
    owner = _mint(client, "dev-launder")
    attacker = _mint(client, "dev-launder")
    laundered = _mint(client, "dev-launder", proof=attacker)
    assert client.get("/api/children/memory/settings", headers=_h(laundered)).status_code == 403
    # The owner re-mints with its own token as proof: still proven.
    renewed = _mint(client, "dev-launder", proof=owner)
    assert client.get("/api/children/memory/settings", headers=_h(renewed)).status_code == 200


def test_a_pre_proof_token_upgrades_by_minting_with_itself_as_proof(client):
    legacy = _mint(client, "dev-legacy")
    conn = get_conn()
    conn.execute("UPDATE api_tokens SET proven = NULL WHERE device_id = 'dev-legacy'")
    conn.commit()
    conn.close()
    assert client.get("/api/children/memory/settings", headers=_h(legacy)).status_code == 403
    upgraded = _mint(client, "dev-legacy", proof=legacy)
    assert client.get("/api/children/memory/settings", headers=_h(upgraded)).status_code == 200


def test_ordinary_routes_still_accept_an_unproven_token(client):
    _mint(client, "dev-plain")
    unproven = _mint(client, "dev-plain")
    assert client.get("/api/children", headers=_h(unproven)).status_code == 200


# ── Child tokens: no device id inside ─────────────────────────────────────


def _payload(token: str) -> dict:
    b64 = token.split(".")[0]
    return json.loads(base64.urlsafe_b64decode(b64 + "=" * (-len(b64) % 4)))


def _profile(device: str) -> int:
    conn = get_conn()
    cid = conn.execute("INSERT INTO child_profiles (device_id, name, age_group) "
                       "VALUES (?, 'سالم', '13-15')", (device,)).lastrowid
    conn.commit()
    conn.close()
    return cid


def test_child_tokens_no_longer_carry_the_device_id():
    cid = _profile("dev-parent-secret")
    token = child_token.issue_child_token("dev-parent-secret", cid, ttl_seconds=600, is_web=True)
    payload = _payload(token)
    assert "device_id" not in payload and "dev-parent-secret" not in json.dumps(payload)
    verified = child_token.verify_child_token(token)
    assert verified["device_id"] == "dev-parent-secret" and verified["child_id"] == cid


def test_a_child_token_dies_with_its_child():
    cid = _profile("dev-gone")
    token = child_token.issue_child_token("dev-gone", cid)
    conn = get_conn()
    conn.execute("DELETE FROM child_profiles WHERE id = ?", (cid,))
    conn.commit()
    conn.close()
    assert child_token.verify_child_token(token) is None


def test_a_forged_binding_is_rejected():
    cid = _profile("dev-real")
    token = child_token.issue_child_token("dev-real", cid)
    payload = _payload(token)
    payload["dh"] = "x" * 24
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    sig = hmac.new(os.environ["CHILD_MODE_SECRET"].encode(), body, hashlib.sha256).digest()
    forged = (base64.urlsafe_b64encode(body).rstrip(b"=").decode() + "." +
              base64.urlsafe_b64encode(sig).rstrip(b"=").decode())
    assert child_token.verify_child_token(forged) is None


def test_old_format_tokens_are_accepted_until_they_expire():
    now = int(time.time())
    old = {"scope": "habit_child_web", "device_id": "dev-v1", "child_id": 5,
           "iat": now, "exp": now + 60}
    body = json.dumps(old, separators=(",", ":"), sort_keys=True).encode()
    sig = hmac.new(os.environ["CHILD_MODE_SECRET"].encode(), body, hashlib.sha256).digest()
    token = (base64.urlsafe_b64encode(body).rstrip(b"=").decode() + "." +
             base64.urlsafe_b64encode(sig).rstrip(b"=").decode())
    assert child_token.verify_child_token(token)["device_id"] == "dev-v1"
    # …and only the new format is issued.
    cid = _profile("dev-v1")
    assert "device_id" not in _payload(child_token.issue_child_token("dev-v1", cid))
