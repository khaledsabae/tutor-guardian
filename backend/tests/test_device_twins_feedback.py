"""Feedback and replies follow a folded device (PR #29 review, item 7).

An old build keeps the twin's id on disk and sends it in the unauthenticated
feedback body; a reply to feedback filed before the fold names the twin too.
Both must land on the family device, which is who the app is after the fold.
"""
from .test_device_twins import _bearer, _db, _register, _split_install, client  # noqa: F401


def test_feedback_and_replies_reach_the_family_after_a_fold(client, monkeypatch):  # noqa: F811
    from app.routers import feedback as fb
    monkeypatch.setattr(fb, "notify_new_feedback", lambda *a, **k: None)
    monkeypatch.setattr("app.services.push_sender.send_to_device", lambda *a, **k: None)
    _, t_h, _ = _split_install()
    with _db() as conn:          # feedback filed while the app was the twin
        fb._ensure_app_feedback_table(conn)
        conn.execute("INSERT INTO app_feedback (id, message, device_id, created_at) "
                     "VALUES ('f-before', 'hi', 'H', '2026-10-01 09:00:00')")
    _register(client, t_h)
    # An old build still sends the twin's id in the (unauthenticated) body.
    r = client.post("/api/feedback/app", json={"message": "after", "device_id": "H"})
    assert r.status_code == 201
    with _db() as conn:
        assert conn.execute("SELECT device_id FROM app_feedback WHERE id = ?",
                            (r.json()["id"],)).fetchone()[0] == "U"
    fb._deliver_reply("f-before", "H", "a reply to the twin-era feedback")
    replies = client.get("/api/feedback/replies", headers=_bearer(t_h)).json()["items"]
    assert [x["reply_text"] for x in replies] == ["a reply to the twin-era feedback"]
