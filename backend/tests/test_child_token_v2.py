"""Child tokens carry no device id (PR #26 review, P1).

A child's web token used to carry the parent's device id in readable base64: a
teen could decode it and act as the parent's device. v2 tokens bind to the
device with an HMAC instead; v1 tokens are still accepted until they expire,
and only v2 is issued.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time

from app.db.init_db import get_conn
from app.services import child_token


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
