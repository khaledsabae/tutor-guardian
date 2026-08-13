"""Feedback reply loop — security gates and routing.

The Telegram webhook is a public, unauthenticated endpoint that writes to the
DB and triggers push notifications. Everything it accepts is attacker-supplied,
so the guards are the point of this file: an unset secret must fail closed, a
wrong secret must be rejected, and a valid secret from the wrong chat must
still go nowhere.
"""
import importlib

import pytest
from fastapi.testclient import TestClient

_SECRET = "test-webhook-secret-value"
_CHAT = "123456789"


def _build_client(monkeypatch, tmp_path, *, secret: str, chat: str = _CHAT):
    """Rebuild the app with the given Telegram env, since the router reads
    these into module-level constants at import time."""
    monkeypatch.setenv("CONVERSATIONS_DB", str(tmp_path / "test.db"))
    monkeypatch.setenv("FEEDBACK_TELEGRAM_BOT_TOKEN", "dummy-token")
    monkeypatch.setenv("FEEDBACK_TELEGRAM_CHAT_ID", chat)
    monkeypatch.setenv("FEEDBACK_TELEGRAM_WEBHOOK_SECRET", secret)

    import app.routers.feedback as feedback_module
    importlib.reload(feedback_module)
    import app.main as main_module
    importlib.reload(main_module)

    from app.db.init_db import init_db
    init_db()
    return TestClient(main_module.app), feedback_module


def _seed_feedback(fid: str, device_id: str | None, tg_message_id: int | None):
    from app.db.init_db import get_conn
    from app.routers.feedback import _ensure_app_feedback_table

    con = get_conn()
    _ensure_app_feedback_table(con)
    con.execute(
        "INSERT INTO app_feedback (id, message, device_id, created_at, "
        "tg_message_id) VALUES (?,?,?,?,?)",
        (fid, "التطبيق بيقفل فجأة", device_id, "2026-07-25T00:00:00Z",
         tg_message_id),
    )
    con.commit()
    con.close()


def _update(text: str, *, chat: str = _CHAT, reply_message_id: int | None = 555,
            reply_text: str = "شكرًا #fb_aaaaaaaa"):
    msg = {"chat": {"id": int(chat)}, "text": text}
    if reply_message_id is not None:
        msg["reply_to_message"] = {
            "message_id": reply_message_id,
            "text": reply_text,
        }
    return {"update_id": 1, "message": msg}


def _replies_in_db() -> list[tuple]:
    from app.db.init_db import get_conn
    con = get_conn()
    rows = con.execute(
        "SELECT feedback_id, device_id, reply_text FROM feedback_replies"
    ).fetchall()
    con.close()
    return [tuple(r) for r in rows]


# ── The three guards ─────────────────────────────────────────────────────────

def test_missing_secret_config_fails_closed(monkeypatch, tmp_path):
    """An unconfigured secret must reject everything, not accept everything."""
    client, _ = _build_client(monkeypatch, tmp_path, secret="")
    resp = client.post(
        "/api/feedback/telegram/webhook",
        json=_update("رد"),
        headers={"X-Telegram-Bot-Api-Secret-Token": ""},
    )
    assert resp.status_code == 403


def test_wrong_secret_is_rejected(monkeypatch, tmp_path):
    client, _ = _build_client(monkeypatch, tmp_path, secret=_SECRET)
    resp = client.post(
        "/api/feedback/telegram/webhook",
        json=_update("رد"),
        headers={"X-Telegram-Bot-Api-Secret-Token": "not-the-secret"},
    )
    assert resp.status_code == 403


def test_absent_secret_header_is_rejected(monkeypatch, tmp_path):
    client, _ = _build_client(monkeypatch, tmp_path, secret=_SECRET)
    resp = client.post("/api/feedback/telegram/webhook", json=_update("رد"))
    assert resp.status_code == 403


def test_valid_secret_from_wrong_chat_writes_nothing(monkeypatch, tmp_path):
    """A leaked secret alone must not be enough to inject a reply."""
    client, _ = _build_client(monkeypatch, tmp_path, secret=_SECRET)
    _seed_feedback("a" * 32, "device-1", 555)

    resp = client.post(
        "/api/feedback/telegram/webhook",
        json=_update("رد من مهاجم", chat="99999999"),
        headers={"X-Telegram-Bot-Api-Secret-Token": _SECRET},
    )
    # Answers 200 so Telegram stops retrying, but stores nothing.
    assert resp.status_code == 200
    assert _replies_in_db() == []


# ── Routing ──────────────────────────────────────────────────────────────────

def test_reply_is_matched_by_telegram_message_id(monkeypatch, tmp_path):
    client, feedback_module = _build_client(monkeypatch, tmp_path, secret=_SECRET)
    _seed_feedback("a" * 32, "device-1", 555)
    # Don't let a real FCM call escape the test.
    monkeypatch.setattr(
        "app.services.push_sender.send_to_device",
        lambda *a, **k: {"ok": True},
    )

    resp = client.post(
        "/api/feedback/telegram/webhook",
        json=_update("تم إصلاحها في التحديث الجاي"),
        headers={"X-Telegram-Bot-Api-Secret-Token": _SECRET},
    )
    assert resp.status_code == 200
    rows = _replies_in_db()
    assert len(rows) == 1
    assert rows[0][0] == "a" * 32
    assert rows[0][1] == "device-1"
    assert rows[0][2] == "تم إصلاحها في التحديث الجاي"


def test_reply_falls_back_to_the_hashtag(monkeypatch, tmp_path):
    """Replying to the voice-note message has a different message id, so the
    #fb_ tag in its caption is what saves the correlation."""
    client, _ = _build_client(monkeypatch, tmp_path, secret=_SECRET)
    _seed_feedback("a" * 32, "device-1", 555)
    monkeypatch.setattr(
        "app.services.push_sender.send_to_device",
        lambda *a, **k: {"ok": True},
    )

    resp = client.post(
        "/api/feedback/telegram/webhook",
        json=_update("سمعت الرسالة", reply_message_id=9999,
                     reply_text="🎤 #fb_" + "a" * 8),
        headers={"X-Telegram-Bot-Api-Secret-Token": _SECRET},
    )
    assert resp.status_code == 200
    rows = _replies_in_db()
    assert len(rows) == 1
    assert rows[0][0] == "a" * 32


def test_non_reply_message_is_ignored(monkeypatch, tmp_path):
    client, _ = _build_client(monkeypatch, tmp_path, secret=_SECRET)
    resp = client.post(
        "/api/feedback/telegram/webhook",
        json=_update("مجرد ملاحظة لنفسي", reply_message_id=None),
        headers={"X-Telegram-Bot-Api-Secret-Token": _SECRET},
    )
    assert resp.status_code == 200
    assert _replies_in_db() == []


def test_unmatched_reply_is_dropped_quietly(monkeypatch, tmp_path):
    client, _ = _build_client(monkeypatch, tmp_path, secret=_SECRET)
    resp = client.post(
        "/api/feedback/telegram/webhook",
        json=_update("رد", reply_message_id=4242, reply_text="بلا وسم"),
        headers={"X-Telegram-Bot-Api-Secret-Token": _SECRET},
    )
    assert resp.status_code == 200
    assert _replies_in_db() == []


def test_oversized_body_is_rejected(monkeypatch, tmp_path):
    client, _ = _build_client(monkeypatch, tmp_path, secret=_SECRET)
    resp = client.post(
        "/api/feedback/telegram/webhook",
        content=b'{"padding":"' + b"x" * 70_000 + b'"}',
        headers={
            "X-Telegram-Bot-Api-Secret-Token": _SECRET,
            "Content-Type": "application/json",
        },
    )
    assert resp.status_code == 413


# ── Reading replies back ─────────────────────────────────────────────────────

def test_replies_endpoint_requires_auth(monkeypatch, tmp_path):
    client, _ = _build_client(monkeypatch, tmp_path, secret=_SECRET)
    assert client.get("/api/feedback/replies").status_code == 401


def test_device_only_sees_its_own_replies(monkeypatch, tmp_path):
    """The device id comes from the caller's token, so one device must never be
    able to read another's correspondence."""
    client, _ = _build_client(monkeypatch, tmp_path, secret=_SECRET)

    session = client.post("/api/chat/sessions")
    assert session.status_code == 201
    headers = {"Authorization": f"Bearer {session.json()['token']}"}

    # A reply belonging to somebody else entirely.
    from app.db.init_db import get_conn
    con = get_conn()
    con.execute(
        "INSERT INTO feedback_replies (id, feedback_id, device_id, reply_text, "
        "created_at) VALUES ('r1','f1','someone-elses-device','سرّي','2026-07-25')"
    )
    con.commit()
    con.close()

    resp = client.get("/api/feedback/replies", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["count"] == 0
    assert "سرّي" not in resp.text


def test_cannot_mark_another_devices_reply_read(monkeypatch, tmp_path):
    client, _ = _build_client(monkeypatch, tmp_path, secret=_SECRET)
    session = client.post("/api/chat/sessions")
    headers = {"Authorization": f"Bearer {session.json()['token']}"}

    from app.db.init_db import get_conn
    con = get_conn()
    con.execute(
        "INSERT INTO feedback_replies (id, feedback_id, device_id, reply_text, "
        "created_at) VALUES ('r1','f1','someone-elses-device','x','2026-07-25')"
    )
    con.commit()
    con.close()

    resp = client.post("/api/feedback/replies/r1/read", headers=headers)
    assert resp.status_code == 404


@pytest.fixture(autouse=True)
def _restore_modules():
    """The tests reload app modules with different env; put them back so later
    test files see the unmodified app."""
    yield
    import app.routers.feedback as feedback_module
    importlib.reload(feedback_module)
    import app.main as main_module
    importlib.reload(main_module)


# ── Telegram redelivery ──────────────────────────────────────────────────────

def test_the_same_update_delivered_twice_reaches_the_parent_once(monkeypatch, tmp_path):
    """Telegram redelivers any update it did not get a 200 for — a container
    restart, an nginx 502, a timeout after the reply had already been pushed.
    Nothing read update_id, so the parent got Khaled's answer twice: two push
    notifications and two rows in feedback_replies."""
    client, _ = _build_client(monkeypatch, tmp_path, secret=_SECRET)
    _seed_feedback("aaaaaaaa-0000", "device-1", 555)

    for _ in range(2):
        resp = client.post(
            "/api/feedback/telegram/webhook",
            json=_update("تمام، اتصلحت"),
            headers={"X-Telegram-Bot-Api-Secret-Token": _SECRET},
        )
        assert resp.status_code == 200

    assert len(_replies_in_db()) == 1


def test_a_different_update_still_gets_through(monkeypatch, tmp_path):
    """The guard keys on the update, not on the feedback row — a second, real
    reply to the same person must still arrive."""
    client, _ = _build_client(monkeypatch, tmp_path, secret=_SECRET)
    _seed_feedback("aaaaaaaa-0000", "device-1", 555)

    first = _update("رد أول")
    second = _update("رد تاني")
    second["update_id"] = 2

    for payload in (first, second):
        client.post(
            "/api/feedback/telegram/webhook",
            json=payload,
            headers={"X-Telegram-Bot-Api-Secret-Token": _SECRET},
        )

    assert len(_replies_in_db()) == 2
