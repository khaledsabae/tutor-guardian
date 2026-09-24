"""SSE keep-alive while the model is silent (audit M13, server side).

The app drops a stream that sends nothing for 45 s. A slow first token
(retrieval, a cold local model, the fallback chain) must therefore still put
bytes on the wire — an SSE comment, which every client ignores.
"""
import time

from fastapi.testclient import TestClient

from app.routers import assistant
from app.services import ai_gateway


def test_silent_model_gets_keepalive_comments(monkeypatch):
    from app.main import app

    class _SlowProvider:
        name = "fake"
        model = "fake-model"

        def __init__(self, *a, **k):
            pass

        def stream(self, prompt, *, options):
            time.sleep(0.4)                         # thinking, no tokens yet
            yield {"response": "جواب", "done": False}
            yield {"response": "", "done": True,
                   "prompt_eval_count": 1, "eval_count": 1}

    monkeypatch.setattr(ai_gateway, "OllamaProvider", _SlowProvider)
    monkeypatch.setattr(assistant, "_STREAM_KEEPALIVE_S", 0.05)
    ai_gateway._gateway = None
    try:
        with TestClient(app) as client:
            sess = client.post("/api/chat/sessions", json={"device_id": "ka"})
            client.headers["Authorization"] = f"Bearer {sess.json()['token']}"
            resp = client.post("/api/assistant/stream", json={
                "age_group": "4-6", "severity": "خفيف",
                "message_text": "إزاي أعود ابني على الصلاة؟",
            })
        assert resp.status_code == 200
        body = resp.text
        assert ": keep-alive\n\n" in body
        assert body.index(": keep-alive") < body.index("event: token")
        # The event contract is unchanged: comments are not events.
        events = [line for line in body.split("\n") if line.startswith("event: ")]
        assert events[-1] == "event: done"
        assert all(e in ("event: token", "event: done") for e in events)
    finally:
        ai_gateway._gateway = None
