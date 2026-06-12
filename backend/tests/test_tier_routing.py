"""Phase 1 tests — cloud quality tier plumbing.

Covers: <think> stripping across chunk boundaries, tier routing policy,
the circuit breaker, privacy redaction, and the SSE contract (token/done
event sequence must be unchanged with the flag off).
"""
import json

import pytest

from app.services.ai_gateway import _ThinkFilter
from app.services import tier_router
from app.services.privacy import redact_for_cloud


# ── _ThinkFilter ──────────────────────────────────────────────────────────
def test_think_filter_noop_for_plain_text():
    f = _ThinkFilter()
    assert f.feed("مرحباً ") == "مرحباً "
    assert f.feed("بك") == "بك"


def test_think_filter_strips_whole_block():
    f = _ThinkFilter()
    out = f.feed("<think>internal reasoning</think>الجواب")
    assert out == "الجواب"


def test_think_filter_strips_block_split_across_chunks():
    f = _ThinkFilter()
    parts = ["<thi", "nk>سر داخلي", " طويل</thi", "nk>النص ", "الظاهر"]
    out = "".join(f.feed(p) for p in parts)
    assert out == "النص الظاهر"


def test_think_filter_partial_open_tag_not_swallowed():
    f = _ThinkFilter()
    # "<th" could start a tag — held back, then released when it isn't one.
    out = f.feed("a<th") + f.feed("b>c")
    assert out == "a<thb>c"


# ── choose_tier ───────────────────────────────────────────────────────────
@pytest.fixture()
def _cloud_on(monkeypatch):
    # LLMConfig is a frozen dataclass — swap the module's reference instead.
    from types import SimpleNamespace
    monkeypatch.setattr(
        tier_router, "LLM",
        SimpleNamespace(cloud_tier_enabled=True,
                        azure_endpoint="https://x", azure_api_key="k"),
    )
    # reset breaker state
    tier_router._consecutive_failures = 0
    tier_router._circuit_open_until = 0.0
    yield


def test_choose_tier_disabled_by_default():
    tier, reason = tier_router.choose_tier("سؤال", ["medical"], "خفيف", [])
    assert tier == "local_fast"
    assert reason == "cloud_disabled"


def test_choose_tier_severity_routes_cloud(_cloud_on):
    tier, reason = tier_router.choose_tier("سؤال", ["medical"], "متوسط",
                                           [{"distance": 0.3}])
    assert tier == "cloud_quality"
    assert "severity" in reason


def test_choose_tier_fiqh_routes_cloud(_cloud_on):
    tier, _ = tier_router.choose_tier("سؤال", ["fiqh"], "خفيف",
                                      [{"distance": 0.3}])
    assert tier == "cloud_quality"


def test_choose_tier_weak_retrieval_routes_cloud(_cloud_on):
    tier, reason = tier_router.choose_tier("سؤال", ["cyber"], "خفيف",
                                           [{"distance": 0.8}])
    assert (tier, reason) == ("cloud_quality", "weak_retrieval")


def test_choose_tier_default_local(_cloud_on):
    tier, reason = tier_router.choose_tier("سؤال قصير", ["cyber"], "خفيف",
                                           [{"distance": 0.3}])
    assert (tier, reason) == ("local_fast", "default")


def test_circuit_breaker_opens_after_failures(_cloud_on):
    tier_router.record_cloud_result(False)
    tier_router.record_cloud_result(False)
    tier, reason = tier_router.choose_tier("سؤال", ["fiqh"], "شديد", [])
    assert (tier, reason) == ("local_fast", "cloud_circuit_open")
    # success resets after cool-down — simulate by clearing the window
    tier_router._circuit_open_until = 0.0
    tier_router.record_cloud_result(True)
    tier, _ = tier_router.choose_tier("سؤال", ["fiqh"], "شديد", [])
    assert tier == "cloud_quality"


# ── privacy redaction ─────────────────────────────────────────────────────
def test_redact_replaces_known_names(monkeypatch):
    from app.services import privacy
    monkeypatch.setattr(privacy, "known_child_names", lambda: ("أحمد", "سارة"))
    out = redact_for_cloud("ابني أحمد بيضرب أخته سارة ولأحمد عادة العناد")
    assert "أحمد" not in out
    assert "سارة" not in out
    assert "طفلي" in out


def test_redact_handles_empty_and_no_names(monkeypatch):
    from app.services import privacy
    monkeypatch.setattr(privacy, "known_child_names", lambda: ())
    assert redact_for_cloud("") == ""
    assert redact_for_cloud("نص عادي") == "نص عادي"


# ── SSE contract (flag off ⇒ unchanged event sequence) ────────────────────
def test_stream_sse_contract(monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.services import ai_gateway

    class _FakeProvider:
        name = "fake"
        model = "fake-model"

        def __init__(self, *a, **k):
            pass

        def stream(self, prompt, *, options):
            yield {"response": "جزء أول ", "done": False}
            yield {"response": "وجزء ثانٍ", "done": False}
            yield {"response": "", "done": True,
                   "prompt_eval_count": 10, "eval_count": 5}

    monkeypatch.setattr(ai_gateway, "OllamaProvider", _FakeProvider)
    ai_gateway._gateway = None  # rebuild with the fake

    with TestClient(app) as client:
        sess = client.post("/api/chat/sessions", json={"device_id": "t"})
        client.headers["Authorization"] = f"Bearer {sess.json()['token']}"
        resp = client.post("/api/assistant/stream", json={
            "age_group": "4-6", "severity": "خفيف",
            "message_text": "إزاي أعود ابني على الصلاة؟",
        })
        assert resp.status_code == 200
        events = [l for l in resp.text.split("\n") if l.startswith("event: ")]
        # token events then exactly one terminal done event
        assert events[-1] == "event: done"
        assert all(e in ("event: token", "event: done") for e in events)
        done_payload = json.loads(
            resp.text.split("event: done\ndata: ")[1].split("\n")[0]
        )
        assert "reply_text" in done_payload and "mode" in done_payload

    ai_gateway._gateway = None  # don't leak the fake to other tests
