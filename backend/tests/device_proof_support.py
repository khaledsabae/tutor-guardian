"""Run the real device-proof challenge from a test (services/device_proof.py).

FCM is replaced by an inbox that records each silent data message — what the
phone holding that push token would receive. Everything else is the real
start → complete flow through the API.
"""
from __future__ import annotations

from contextlib import contextmanager
from unittest import mock

from app.services import push_sender


class Inbox:
    """Stands in for FCM: every data message, keyed by the push token it went to."""

    def __init__(self, fail: dict | None = None):
        self.messages: list[tuple[str, dict]] = []
        self.fail = fail

    def __call__(self, token, data, ttl_seconds):
        if self.fail is not None:
            return self.fail
        self.messages.append((token, dict(data)))
        return {"ok": True, "sent": True}

    def last_for(self, push_token: str) -> dict:
        got = [d for t, d in self.messages if t == push_token]
        assert got, f"nothing was delivered to {push_token!r}"
        return got[-1]


@contextmanager
def fcm(fail: dict | None = None):
    inbox = Inbox(fail)
    with mock.patch.object(push_sender, "send_data_message", inbox):
        yield inbox


def register_push(client, headers: dict, push_token: str, build: int | None = None) -> None:
    body: dict = {"token": push_token}
    if build is not None:
        body["build_number"] = build
    r = client.post("/api/push/register", json=body, headers=headers)
    assert r.status_code == 200 and r.json().get("ok"), r.text


def start(client, headers: dict):
    return client.post("/api/device-proof/start", headers=headers)


def complete(client, headers: dict, challenge_id, code: str):
    return client.post("/api/device-proof/complete", headers=headers,
                       json={"challenge_id": str(challenge_id), "code": code})


def prove(client, headers: dict, push_token: str | None = None,
          build: int | None = None) -> dict:
    """Prove this session: register `push_token` first when given, then start,
    read the code off the 'phone', and post it back. Returns complete()'s body."""
    if push_token is not None:
        register_push(client, headers, push_token, build)
    with fcm() as inbox:
        r = start(client, headers)
        assert r.status_code == 202, r.text
        _, data = inbox.messages[-1]
        assert data["type"] == "device_proof"
        r = complete(client, headers, data["challenge_id"], data["code"])
        assert r.status_code == 200, r.text
    return r.json()
