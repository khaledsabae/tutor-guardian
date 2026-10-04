"""Turn races on a real uvicorn server — PR #24 round 2 (probes2).

test_answer_reliability drives the handlers in-process and closes the body
iterator by hand. Here the client really drops its socket, and uvicorn and
Starlette notice it the way they do in production (on the next write, with
ASGI 2.4). Scripted model, stubbed classification and retrieval.

Every wait is bounded: on a regression a test fails, it does not hang.
"""
from __future__ import annotations

import asyncio
import http.client
import json
import socket
import threading
import time
import uuid
from types import SimpleNamespace

import pytest

from app.routers import assistant
from app.services import ai_gateway, answer_cache
from app.services import conversation_store as store

_WAIT_S = 10.0


def _unit():
    return {
        "unit_id": "u-medical-1", "document": "passage: نصيحة تربوية موثقة عن النوم.",
        "metadata": {"domain": "medical", "reference_info": "مرجع تربوي موثق",
                     "title": "النوم", "age_group": "4-6"},
        "rerank_score": 0.5, "distance": 0.2, "source_domain": "medical",
    }


@pytest.fixture
def live(monkeypatch):
    """A uvicorn server on a free port. `live.script` is the model's answer:
    ("token", text) | ("gate", name) — a gate waits until the test opens it."""
    m = SimpleNamespace(prompts=[], tokens=[], flags=[], script=[],
                        thinking={}, gates={}, port=None)

    def gate(name: str) -> threading.Event:
        return m.gates.setdefault(name, threading.Event())

    m.gate = gate

    class _Scripted:
        name = "fake"
        model = "fake-model"

        def __init__(self, *a, **k):
            self.timeout = 60

        def stream(self, prompt, *, options):
            m.prompts.append(prompt)
            for kind, value in m.script:
                if kind == "token":
                    m.tokens.append(value)
                    yield {"response": value, "done": False}
                else:
                    gate(value).wait(_WAIT_S)
            yield {"response": "", "done": True, "prompt_eval_count": 1, "eval_count": 1}

        def generate(self, prompt, *, options):
            return {"response": "رد", "done": True}

    async def _classify(query_text):
        held = m.thinking.get(query_text)
        if held is not None:  # the "thinking" seconds before the answer
            deadline = time.monotonic() + _WAIT_S
            while not held.is_set() and time.monotonic() < deadline:
                await asyncio.sleep(0.01)
        return ["medical"], ""

    async def _no_ayah(_q):
        return None

    monkeypatch.setattr(ai_gateway, "OllamaProvider", _Scripted)
    monkeypatch.setattr(ai_gateway, "_gateway", None)
    monkeypatch.setattr(ai_gateway, "_log_call", lambda *a, **k: None)
    monkeypatch.setattr(assistant, "_classify_and_rewrite", _classify)
    monkeypatch.setattr(answer_cache, "lookup", lambda *a, **k: None)
    monkeypatch.setattr(answer_cache, "store", lambda *a, **k: None)
    monkeypatch.setattr(assistant, "_ensure_index", lambda: None)
    monkeypatch.setattr(assistant, "retrieve_hybrid", lambda **kw: [_unit()])
    monkeypatch.setattr(assistant, "log_retrieval", lambda *a, **k: None)
    monkeypatch.setattr(assistant, "resolve_ayah_reference", _no_ayah)
    monkeypatch.setattr(assistant, "log_session", lambda **kw: m.flags.append(kw.get("flag", "")))
    monkeypatch.setattr(assistant, "_STREAM_KEEPALIVE_S", 0.1)

    import uvicorn
    from app.main import app

    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=0, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 15
    while not server.started:
        assert time.monotonic() < deadline, "uvicorn did not start"
        time.sleep(0.02)
    m.port = server.servers[0].sockets[0].getsockname()[1]
    try:
        yield m
    finally:
        for g in list(m.gates.values()) + list(m.thinking.values()):
            g.set()
        server.should_exit = True
        thread.join(10)
        ai_gateway._gateway = None
        assistant._ACTIVE_TURNS.clear()


# ── Client side ────────────────────────────────────────────────────────────

def _http(m, method, path, body=None, token=None):
    conn = http.client.HTTPConnection("127.0.0.1", m.port, timeout=_WAIT_S)
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    conn.request(method, path, body=json.dumps(body) if body is not None else None,
                 headers=headers)
    resp = conn.getresponse()
    data = resp.read()
    conn.close()
    return resp.status, (json.loads(data) if data else None)


def _session(m):
    status, data = _http(m, "POST", "/api/chat/sessions",
                         {"device_id": f"race-{uuid.uuid4().hex[:12]}"})
    assert status in (200, 201), data
    return data["session_id"], data["token"]


class _Stream:
    """One POST /api/assistant/stream on a raw socket, so it can be dropped."""

    def __init__(self, m, sid, token, text):
        body = json.dumps({"age_group": "4-6", "severity": "خفيف",
                           "message_text": text, "session_id": sid}).encode()
        self.sock = socket.create_connection(("127.0.0.1", m.port), timeout=_WAIT_S)
        self.sock.sendall(
            b"POST /api/assistant/stream HTTP/1.1\r\nHost: test\r\n"
            b"Content-Type: application/json\r\n"
            + f"Authorization: Bearer {token}\r\nContent-Length: {len(body)}\r\n\r\n".encode()
            + body)
        self.buf = b""

    def read_until(self, marker: str) -> str:
        deadline = time.monotonic() + _WAIT_S
        while marker.encode() not in self.buf:
            assert time.monotonic() < deadline, f"no {marker!r} in {self.buf[-300:]!r}"
            chunk = self.sock.recv(4096)
            if not chunk:
                break
            self.buf += chunk
        return self.buf.decode("utf-8", "replace")

    def read_to_end(self, within: float = _WAIT_S) -> str:
        """Until the server ends the response (chunked terminator) or closes."""
        deadline = time.monotonic() + within
        while not self.buf.endswith(b"0\r\n\r\n"):
            left = deadline - time.monotonic()
            assert left > 0, f"stream did not end within {within}s: {self.buf[-300:]!r}"
            self.sock.settimeout(left)
            try:
                chunk = self.sock.recv(4096)
            except socket.timeout:
                continue
            if not chunk:
                break
            self.buf += chunk
        return self.buf.decode("utf-8", "replace")

    def turn_id(self) -> int:
        text = self.read_until("event: turn")
        frame = text.split("event: turn\ndata: ", 1)[1].split("\n", 1)[0]
        return json.loads(frame)["message_id"]

    def close(self) -> None:
        self.sock.close()


def _rows(sid):
    conn = store.get_conn()
    try:
        return [(r["role"], r["content"], r["mode"]) for r in conn.execute(
            "SELECT role, content, mode FROM chat_messages WHERE session_id = ? ORDER BY id",
            (sid,))]
    finally:
        conn.close()


def _wait_for(check, what: str):
    deadline = time.monotonic() + _WAIT_S
    while True:
        value = check()
        if value:
            return value
        assert time.monotonic() < deadline, f"timed out waiting for {what}"
        time.sleep(0.02)


def _quiet(m, settle_s: float = 0.3) -> None:
    """Let anything still scheduled on the server run before asserting."""
    time.sleep(settle_s)


# ── Scenarios ──────────────────────────────────────────────────────────────

def test_dropped_reader_leaves_a_pending_row_that_is_finished_in_place(live):
    """A (T5) — the row is reserved as 'pending' the moment the reader leaves,
    visible in the history the app reloads, then filled with the answer."""
    live.script = [("token", "P1 "), ("gate", "rest"), ("token", "P2 "), ("token", "P3")]
    sid, tok = _session(live)
    s = _Stream(live, sid, tok, "Q1 النوم")
    s.read_until("event: token")
    s.close()

    _wait_for(lambda: _rows(sid)[1:] == [("assistant", "P1", "pending")], "the pending row")
    _, hist = _http(live, "GET", f"/api/chat/sessions/{sid}", token=tok)
    assert [(m["role"], m["mode"]) for m in hist["messages"]] == [
        ("user", None), ("assistant", "pending")]

    live.gate("rest").set()
    _wait_for(lambda: _rows(sid)[1:] == [("assistant", "P1 P2 P3", "llm_generated")],
              "the finished answer")
    assert "completed_after_disconnect" in live.flags


def test_reader_leaving_while_thinking_still_gets_its_answer(live):
    """B — the app went to the background before the first token."""
    live.script = [("token", "P1 "), ("token", "P2")]
    live.thinking["Q1 قبل البث"] = held = threading.Event()
    sid, tok = _session(live)
    s = _Stream(live, sid, tok, "Q1 قبل البث")
    s.turn_id()
    s.close()
    _quiet(live)
    held.set()

    _wait_for(lambda: _rows(sid)[1:] == [("assistant", "P1 P2", "llm_generated")],
              "the answer finished without a reader")
    assert len(live.prompts) == 1


def test_stop_while_reading_keeps_what_was_shown(live):
    """C — Stop with the reader still connected: the stream ends, the words
    shown are kept as 'interrupted', the rest is never generated."""
    live.script = [("token", "P1 "), ("gate", "rest"), ("token", "P2")]
    sid, tok = _session(live)
    s = _Stream(live, sid, tok, "Q1 توقف")
    qid = s.turn_id()
    s.read_until("event: token")

    status, body = _http(live, "POST", f"/api/chat/sessions/{sid}/stop", {"message_id": qid}, tok)
    assert (status, body) == (200, {"stopped": True})
    # The stream ends now — the model is still holding (gate shut) and would
    # not have sent another token to end it on.
    rest = s.read_to_end(within=3.0)
    assert "event: done" not in rest and "P2" not in rest
    s.close()
    live.gate("rest").set()
    _quiet(live)
    assert _rows(sid) == [("user", "Q1 توقف", None), ("assistant", "P1", "interrupted")]
    assert "stopped_by_parent" in live.flags


def test_stop_after_the_reader_left_keeps_only_what_was_seen(live):
    """D (T7) — the app closes the stream, then its Stop arrives: what the
    background completion produced in between was never on screen."""
    live.script = [("token", "P1 "), ("gate", "more"), ("token", "P2 "), ("token", "P3 "),
                   ("gate", "rest"), ("token", "P4")]
    sid, tok = _session(live)
    s = _Stream(live, sid, tok, "Q1 أغلق ثم أوقف")
    qid = s.turn_id()
    s.read_until("event: token")
    s.close()
    _wait_for(lambda: _rows(sid)[1:] == [("assistant", "P1", "pending")], "the pending row")
    live.gate("more").set()
    _wait_for(lambda: "P3 " in live.tokens, "tokens after the reader left")

    status, body = _http(live, "POST", f"/api/chat/sessions/{sid}/stop", {"message_id": qid}, tok)
    assert (status, body) == (200, {"stopped": True})
    live.gate("rest").set()
    _quiet(live)
    assert _rows(sid)[1:] == [("assistant", "P1", "interrupted")]
    assert "completed_after_disconnect" not in live.flags


@pytest.mark.parametrize("first_reader_stays", [False, True])
def test_new_question_while_thinking_cuts_the_old_turn(live, first_reader_stays):
    """F/H (T1) — Q2 while Q1 is still being classified: Q1 never reaches
    the model, and the app reloads Q1, Q2, A2 — not A1 under Q2."""
    live.script = [("token", "P1 "), ("token", "P2")]
    live.thinking["Q1 سؤال"] = held = threading.Event()
    sid, tok = _session(live)
    s1 = _Stream(live, sid, tok, "Q1 سؤال")
    s1.turn_id()
    if not first_reader_stays:
        s1.close()  # the app's stopStreaming() before it sends Q2

    s2 = _Stream(live, sid, tok, "Q2 تفصيل")
    assert "event: done" in s2.read_to_end()
    s2.close()
    held.set()
    if first_reader_stays:
        assert "event: done" not in s1.read_to_end()
        s1.close()
    _quiet(live)

    assert _rows(sid) == [("user", "Q1 سؤال", None), ("user", "Q2 تفصيل", None),
                          ("assistant", "P1 P2", "llm_generated")]
    assert len(live.prompts) == 1
    assert "superseded" in live.flags
    _, hist = _http(live, "GET", f"/api/chat/sessions/{sid}", token=tok)
    assert [m["role"] for m in hist["messages"]] == ["user", "user", "assistant"]


def test_stop_for_the_newer_turn_is_not_lost_to_the_older_one(live):
    """H2 (T1) — the older turn finished thinking after Q2 started and took
    the session's slot back: Stop for Q2 answered stopped:false and Q2's
    answer was generated in full."""
    live.script = [("token", "P1 "), ("gate", "rest"), ("token", "P2")]
    live.thinking["Q1 سؤال ب"] = held = threading.Event()
    sid, tok = _session(live)
    s1 = _Stream(live, sid, tok, "Q1 سؤال ب")
    s1.turn_id()
    s1.close()
    s2 = _Stream(live, sid, tok, "Q2 تفصيل ب")
    q2 = s2.turn_id()
    s2.read_until("event: token")
    held.set()  # Q1's pipeline resumes now, with Q2 mid-answer
    _quiet(live)

    status, body = _http(live, "POST", f"/api/chat/sessions/{sid}/stop", {"message_id": q2}, tok)
    assert (status, body) == (200, {"stopped": True})
    assert "event: done" not in s2.read_to_end()
    s2.close()
    live.gate("rest").set()
    _quiet(live)
    assert _rows(sid) == [("user", "Q1 سؤال ب", None), ("user", "Q2 تفصيل ب", None),
                          ("assistant", "P1", "interrupted")]
    assert len(live.prompts) == 1
