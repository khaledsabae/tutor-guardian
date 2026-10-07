"""Real HTTP feedback attribution; no external transport is permitted."""

from unittest.mock import Mock

import httpx
import pytest
import requests
from fastapi.testclient import TestClient

from app.db.init_db import get_conn
from app.main import app
from app.routers import feedback


DENIED = "غير مسموح بإرسال ملاحظات لهذه المحادثة."


@pytest.fixture(autouse=True)
def no_outbound_transport(monkeypatch):
    forbidden = Mock(side_effect=AssertionError("Real outbound transport attempted"))
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", forbidden)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", forbidden)
    monkeypatch.setattr(requests.sessions.Session, "request", forbidden)
    notify = Mock(side_effect=AssertionError("Answer feedback notified Telegram"))
    monkeypatch.setattr(feedback, "notify_new_feedback", notify)
    monkeypatch.setattr(feedback, "_deliver_reply", notify)
    yield
    forbidden.assert_not_called()
    notify.assert_not_called()


@pytest.fixture(params=["production", "fresh"])
def client(request):
    # The documented live table lacks message_id (test_account_deletion.py).
    # Exercise that shape AND init_db's actual NOT NULL message_id schema.
    if request.param == "production":
        with get_conn() as con:
            con.execute("DROP TABLE user_feedback")
            con.execute("""CREATE TABLE user_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL, rating TEXT NOT NULL, comment TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )""")
    return TestClient(app)  # no lifespan / model startup / background jobs


def _mint(client, device, proof=None):
    response = client.post(
        "/api/chat/sessions",
        json={"device_id": device},
        headers={} if proof is None else {"Authorization": f"Bearer {proof}"},
    )
    assert response.status_code == 201
    return response.json()


def _post(client, session, **payload):
    return client.post(
        "/api/feedback",
        json={"rating": "down", "comment": "ملاحظة", **payload},
        headers={"Authorization": f"Bearer {session['token']}"},
    )


def _rows():
    with get_conn() as con:
        return [
            tuple(row)
            for row in con.execute(
                "SELECT session_id, rating, comment FROM user_feedback ORDER BY id"
            )
        ]


@pytest.mark.parametrize("target", ["foreign", "unknown", "ownerless-unbound"])
def test_foreign_unknown_or_unbound_session_is_denied_without_write(client, target):
    caller = _mint(client, "feedback-device-A")
    other = _mint(client, "feedback-device-B")
    if target == "ownerless-unbound":
        with get_conn() as con:
            con.execute(
                "UPDATE chat_sessions SET device_id=NULL WHERE id=?", (other["session_id"],)
            )
    wanted = "missing-private-session" if target == "unknown" else other["session_id"]
    response = _post(client, caller, session_id=wanted)
    assert response.status_code == 403
    assert response.json() == {"detail": DENIED}
    assert wanted not in response.text
    assert _rows() == []


@pytest.mark.parametrize("supplied", ["own", "omitted", "null", "empty"])
def test_owned_feedback_and_optional_session_work(client, supplied):
    caller = _mint(client, "feedback-device-A")
    payload = {
        "own": {"session_id": caller["session_id"]},
        "omitted": {},
        "null": {"session_id": None},
        "empty": {"session_id": ""},
    }[supplied]
    response = _post(client, caller, **payload)
    assert response.status_code == 201, response.text
    assert response.json() == {"status": "ok"}
    assert _rows() == [(caller["session_id"], "down", "ملاحظة")]


def test_previous_owned_conversation_is_allowed_after_session_renewal(client, monkeypatch):
    monkeypatch.setenv("SESSION_MINT_ENFORCE", "true")
    previous = _mint(client, "feedback-device-A")
    current = _mint(client, "feedback-device-A", previous["token"])
    assert current["session_id"] != previous["session_id"]
    response = _post(client, current, session_id=previous["session_id"])
    assert response.status_code == 201
    assert _rows()[0][0] == previous["session_id"]


def test_legacy_ownerless_session_requires_its_authenticated_session_binding(client):
    caller = _mint(client, "feedback-device-A")
    with get_conn() as con:
        con.execute("UPDATE chat_sessions SET device_id=NULL WHERE id=?", (caller["session_id"],))
    response = _post(client, caller, session_id=caller["session_id"])
    assert response.status_code == 201
    assert _rows()[0][0] == caller["session_id"]


@pytest.mark.parametrize("credential", [None, "Bearer invalid", "Child-Bearer invalid"])
def test_middleware_unauthorized_requests_never_write(client, credential):
    owned = _mint(client, "feedback-device-A")
    response = client.post(
        "/api/feedback",
        json={"rating": "up", "session_id": owned["session_id"]},
        headers={} if credential is None else {"Authorization": credential},
    )
    assert response.status_code == 401
    assert _rows() == []


def test_fresh_schema_message_binding_uses_the_owned_conversation(client):
    caller = _mint(client, "feedback-device-A")
    other = _mint(client, "feedback-device-B")
    with get_conn() as con:
        own_message = con.execute(
            "INSERT INTO chat_messages (session_id, role, content) VALUES (?, 'assistant', 'رد')",
            (caller["session_id"],),
        ).lastrowid
        con.execute(
            "INSERT INTO chat_messages (session_id, role, content) VALUES (?, 'assistant', 'خاص')",
            (other["session_id"],),
        )
    response = _post(client, caller, session_id=caller["session_id"])
    assert response.status_code == 201
    with get_conn() as con:
        columns = {row["name"] for row in con.execute("PRAGMA table_info(user_feedback)")}
        if "message_id" in columns:
            assert con.execute("SELECT message_id FROM user_feedback").fetchone()[0] == own_message
