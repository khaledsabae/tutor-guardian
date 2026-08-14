"""Admin reply endpoint — the supported way to answer a parent off Telegram.

Before this existed the only way to send a reply outside Telegram was a
hand-written INSERT into `feedback_replies` against the production DB. These
tests hold the line that made the endpoint worth building rather than a second
way to do the same unguarded thing: it must refuse without the admin key,
refuse for feedback that does not exist, refuse when there is nobody to deliver
to, and not deliver the same words twice when a curl is retried.
"""
import importlib

from fastapi.testclient import TestClient

_KEY = "test-admin-key-value"


def _build_client(monkeypatch, tmp_path, *, key: str = _KEY):
    """Rebuild the app with the given admin key — the router reads it into a
    module-level constant at import time."""
    monkeypatch.setenv("CONVERSATIONS_DB", str(tmp_path / "test.db"))
    monkeypatch.setenv("FEEDBACK_ADMIN_KEY", key)

    import app.routers.feedback as feedback_module
    importlib.reload(feedback_module)
    import app.main as main_module
    importlib.reload(main_module)

    from app.db.init_db import init_db
    init_db()
    return TestClient(main_module.app), feedback_module


def _seed(fid: str, device_id: str | None):
    from app.db.init_db import get_conn
    from app.routers.feedback import _ensure_app_feedback_table

    con = get_conn()
    _ensure_app_feedback_table(con)
    con.execute(
        "INSERT INTO app_feedback (id, message, device_id, created_at) "
        "VALUES (?,?,?,?)",
        (fid, "التقدّم مش بيتسجّل", device_id, "2026-08-14T00:00:00Z"),
    )
    con.commit()
    con.close()


def _replies():
    from app.db.init_db import get_conn
    con = get_conn()
    rows = con.execute(
        "SELECT feedback_id, device_id, reply_text FROM feedback_replies"
    ).fetchall()
    con.close()
    return [tuple(r) for r in rows]


def _capture_push(monkeypatch) -> list:
    """Intercept the push nudge at its real import site.

    `_deliver_reply` does `from app.services.push_sender import send_to_device`
    *inside* the function, so patching the attribute on the feedback module
    patches something nobody reads — the test then passes because the real push
    raises and `_deliver_reply` swallows it, which looks like delivery working.
    """
    sent = []
    import app.services.push_sender as push
    monkeypatch.setattr(push, "send_to_device",
                        lambda *a, **k: sent.append((a, k)))
    return sent


def _post(client, fid, text, key=_KEY):
    return client.post(
        f"/api/feedback/app/{fid}/reply",
        json={"text": text},
        headers={"x-admin-key": key},
    )


# ── The guards ───────────────────────────────────────────────────────────────

def test_without_the_admin_key_nothing_is_sent(monkeypatch, tmp_path):
    client, _ = _build_client(monkeypatch, tmp_path)
    _seed("aaaa1111", "dev-1")

    resp = client.post("/api/feedback/app/aaaa1111/reply",
                       json={"text": "أهلًا"})

    assert resp.status_code == 403
    assert _replies() == []


def test_an_unset_admin_key_fails_closed(monkeypatch, tmp_path):
    """An empty key in the environment must not become an empty key that
    matches — otherwise the endpoint is public."""
    client, _ = _build_client(monkeypatch, tmp_path, key="")
    _seed("aaaa1111", "dev-1")

    resp = _post(client, "aaaa1111", "أهلًا", key="")

    assert resp.status_code == 403
    assert _replies() == []


def test_unknown_feedback_is_404_not_a_stored_orphan(monkeypatch, tmp_path):
    """Asserting only the status code here proves nothing: a missing *route*
    is also a 404, so this passed unchanged against the code that had no
    endpoint at all. The body is what separates "the handler rejected it" from
    "there was no handler"."""
    client, _ = _build_client(monkeypatch, tmp_path)

    resp = _post(client, "does-not-exist", "أهلًا")

    assert resp.status_code == 404
    assert resp.json()["detail"] == "no such feedback"
    assert _replies() == []


def test_feedback_with_no_device_is_refused(monkeypatch, tmp_path):
    """Storing a reply for a row with no device would report success for a
    message that reaches nobody."""
    client, _ = _build_client(monkeypatch, tmp_path)
    _seed("bbbb2222", None)

    resp = _post(client, "bbbb2222", "أهلًا")

    assert resp.status_code == 409
    assert _replies() == []


def test_blank_text_is_rejected(monkeypatch, tmp_path):
    client, _ = _build_client(monkeypatch, tmp_path)
    _seed("aaaa1111", "dev-1")

    assert _post(client, "aaaa1111", "   ").status_code == 422
    assert _replies() == []


def test_overlong_text_is_rejected(monkeypatch, tmp_path):
    client, feedback_module = _build_client(monkeypatch, tmp_path)
    _seed("aaaa1111", "dev-1")

    too_long = "ا" * (feedback_module._MAX_REPLY_LEN + 1)

    assert _post(client, "aaaa1111", too_long).status_code == 422
    assert _replies() == []


# ── Delivery ─────────────────────────────────────────────────────────────────

def test_a_valid_reply_reaches_the_parent(monkeypatch, tmp_path):
    client, _ = _build_client(monkeypatch, tmp_path)
    sent = _capture_push(monkeypatch)
    _seed("aaaa1111", "dev-1")

    resp = _post(client, "aaaa1111", "طمّنك — المشكلة اتصلحت.")

    assert resp.status_code == 201
    assert resp.json()["status"] == "queued"
    assert resp.json()["device_id"] == "dev-1"
    assert _replies() == [("aaaa1111", "dev-1", "طمّنك — المشكلة اتصلحت.")]
    # The nudge is part of the contract, not a side effect: without this the
    # test passes just as happily when push raises and is swallowed.
    assert len(sent) == 1
    assert sent[0][0][0] == "dev-1"


def test_the_parent_can_read_it_through_the_normal_endpoint(monkeypatch, tmp_path):
    """Delivery must go through the same table the app already polls, not a
    parallel one — the endpoint is a second way in, not a second mechanism."""
    client, _ = _build_client(monkeypatch, tmp_path)
    sent = _capture_push(monkeypatch)
    _seed("aaaa1111", "dev-1")
    _post(client, "aaaa1111", "الإصلاح نزل.")

    from app.db.init_db import get_conn
    con = get_conn()
    stored = con.execute(
        "SELECT reply_text FROM feedback_replies WHERE device_id = ?",
        ("dev-1",),
    ).fetchall()
    con.close()

    assert [r[0] for r in stored] == ["الإصلاح نزل."]
    assert len(sent) == 1


def test_a_retried_post_does_not_reply_twice(monkeypatch, tmp_path):
    """A curl that times out and is re-run must not say the same thing to a
    parent twice — the Telegram path gets this from _claim_update."""
    client, _ = _build_client(monkeypatch, tmp_path)
    sent = _capture_push(monkeypatch)
    _seed("aaaa1111", "dev-1")

    first = _post(client, "aaaa1111", "الإصلاح نزل.")
    second = _post(client, "aaaa1111", "الإصلاح نزل.")

    assert first.status_code == 201
    # 200, not 201: a duplicate creates nothing, and a caller that trusts the
    # status code instead of the body must not read it as "sent".
    assert second.status_code == 200
    assert first.json()["status"] == "queued"
    assert second.json()["status"] == "duplicate"
    assert second.json()["delivered"] is False
    assert len(_replies()) == 1
    assert len(sent) == 1, "the retry must not nudge the parent a second time"


def test_a_genuinely_different_follow_up_still_goes_through(monkeypatch, tmp_path):
    """The duplicate guard keys on the text, so a real second message must not
    be swallowed by it."""
    client, _ = _build_client(monkeypatch, tmp_path)
    sent = _capture_push(monkeypatch)
    _seed("aaaa1111", "dev-1")

    _post(client, "aaaa1111", "جاري الإصلاح.")
    second = _post(client, "aaaa1111", "الإصلاح نزل.")

    assert second.json()["status"] == "queued"
    assert len(_replies()) == 2
    assert len(sent) == 2
