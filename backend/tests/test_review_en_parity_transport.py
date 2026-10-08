"""The transport under the review gate: an operator can bound a run.

`post()` used to hardcode 8 attempts and a 600-second request, so a review
could hang for hours with no knob to bound it. These tests pin the minimal
contract: module-level defaults, `post(timeout=None)` following the configured
timeout, an explicit timeout still winning, exhaustion after exactly the
configured number of attempts, and the CLI refusing values that bound nothing.
No network, no live model: `urlopen`, `time.sleep` and `_api_key` are patched.
"""
import importlib.util
import io
import json
import sys
import urllib.error
from pathlib import Path

import pytest

_TOOL = Path(__file__).resolve().parents[2] / "ops" / "tools" / "review_en_parity.py"

_OK_BODY = json.dumps({"choices": [{"message": {"content": "ok"}}], "usage": {}})


@pytest.fixture(scope="module")
def rp():
    spec = importlib.util.spec_from_file_location("review_en_parity_transport", _TOOL)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    argv, sys.argv = sys.argv, [sys.argv[0]]
    try:
        spec.loader.exec_module(module)
    finally:
        sys.argv = argv
    return module


@pytest.fixture()
def no_network(rp, monkeypatch):
    """No live calls and no real waiting: patch sleep, the key, and urlopen."""
    monkeypatch.setattr(rp, "_api_key", lambda: "test-key")
    monkeypatch.setattr(rp.time, "sleep", lambda *_: None)
    calls = {"n": 0, "timeouts": []}

    def fake_urlopen(req, timeout=None):
        calls["n"] += 1
        calls["timeouts"].append(timeout)
        return io.StringIO(_OK_BODY)

    monkeypatch.setattr(rp.urllib.request, "urlopen", fake_urlopen)
    return calls


# ── defaults ──────────────────────────────────────────────────────────────

def test_defaults_preserve_the_hardcoded_transport(rp):
    assert rp.REQUEST_TIMEOUT == 600
    assert rp.REQUEST_ATTEMPTS == 8


# ── post() follows the configured timeout ─────────────────────────────────

def test_post_without_timeout_uses_the_configured_one(rp, monkeypatch, no_network):
    monkeypatch.setattr(rp, "REQUEST_TIMEOUT", 5)
    content, _usage = rp.post("glm-5.2", "s", "u")
    assert content == "ok"
    assert no_network["timeouts"] == [5]


def test_an_explicit_timeout_overrides_the_configured_one(rp, monkeypatch, no_network):
    monkeypatch.setattr(rp, "REQUEST_TIMEOUT", 5)
    rp.post("glm-5.2", "s", "u", timeout=17)
    assert no_network["timeouts"] == [17]


# ── retry exhaustion is exactly the configured count ──────────────────────

def test_post_gives_up_after_exactly_the_configured_attempts(rp, monkeypatch, no_network):
    monkeypatch.setattr(rp, "REQUEST_ATTEMPTS", 3)

    def always_down(req, timeout=None):
        no_network["n"] += 1
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr(rp.urllib.request, "urlopen", always_down)
    with pytest.raises(RuntimeError):
        rp.post("glm-5.2", "s", "u")
    assert no_network["n"] == 3


def test_post_exhausts_the_default_eight_attempts(rp, monkeypatch, no_network):
    def always_down(req, timeout=None):
        no_network["n"] += 1
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr(rp.urllib.request, "urlopen", always_down)
    with pytest.raises(RuntimeError):
        rp.post("glm-5.2", "s", "u")
    assert no_network["n"] == rp.REQUEST_ATTEMPTS == 8


# ── the CLI bounds the run ─────────────────────────────────────────────────

@pytest.mark.parametrize("flag", ["--request-timeout", "--request-attempts"])
@pytest.mark.parametrize("bad", ["0", "-5"])
def test_cli_rejects_values_that_bound_nothing(rp, monkeypatch, flag, bad):
    monkeypatch.setattr(rp, "collect", lambda kinds: [])
    with pytest.raises(SystemExit) as e:
        rp.main(["run", "--only", "lesson_x", flag, bad])
    assert e.value.code == 2


def test_run_startup_assigns_the_configured_transport(rp, monkeypatch):
    monkeypatch.setattr(rp, "collect", lambda kinds: [])
    monkeypatch.setattr(rp, "run", lambda items, args: {
        "stamped": [], "fixed": [], "arabic_proposals": [], "arabic_applied": [],
        "unresolved": {}, "rounds": 0})
    # seed via monkeypatch so teardown restores the module defaults
    monkeypatch.setattr(rp, "REQUEST_TIMEOUT", 600)
    monkeypatch.setattr(rp, "REQUEST_ATTEMPTS", 8)
    rp.main(["run", "--only", "lesson_x", "--request-timeout", "45",
             "--request-attempts", "2"])
    assert rp.REQUEST_TIMEOUT == 45
    assert rp.REQUEST_ATTEMPTS == 2


# ── REVIEW_ROUTES: an opt-in provider switch ───────────────────────────────

_ROUTE = {"provider": "openrouter", "base_url": "https://router.example/v1/chat/completions",
          "key_env": "TEST_ROUTER_KEY", "model": "z-ai/glm-5.2"}


@pytest.fixture()
def routed(rp, monkeypatch, tmp_path, no_network):
    """glm-5.2 routed to a fake OpenAI-compatible provider; the key lives in a .env file."""
    env = tmp_path / ".env"
    env.write_text("OTHER=1\nexport TEST_ROUTER_KEY='dummy-route-key'\n", encoding="utf-8")
    log = tmp_path / "calls.jsonl"
    monkeypatch.setenv("REVIEW_ROUTES", json.dumps({"glm-5.2": {**_ROUTE, "key_file": str(env)}}))
    monkeypatch.setenv("REVIEW_CALL_LOG", str(log))
    monkeypatch.delenv("TEST_ROUTER_KEY", raising=False)
    monkeypatch.setattr(rp, "_route_keys", {})
    monkeypatch.setattr(rp, "_capped", rp.threading.Event())
    seen = []

    def fake_urlopen(req, timeout=None):
        no_network["n"] += 1
        seen.append(req)
        return io.StringIO(json.dumps({"choices": [{"message": {"content": "ok"}}],
                                       "usage": {"prompt_tokens": 11, "completion_tokens": 3,
                                                 "total_tokens": 14}}))

    monkeypatch.setattr(rp.urllib.request, "urlopen", fake_urlopen)
    return {"seen": seen, "log": log, "calls": no_network}


def test_unset_routes_keep_ollama(rp, monkeypatch, no_network):
    monkeypatch.delenv("REVIEW_ROUTES", raising=False)
    seen = []
    monkeypatch.setattr(rp.urllib.request, "urlopen",
                        lambda req, timeout=None: seen.append(req) or io.StringIO(_OK_BODY))
    rp.post("glm-5.2", "s", "u")
    assert seen[0].full_url == rp.API_URL
    assert json.loads(seen[0].data)["model"] == "glm-5.2"
    assert rp.provider_of("glm-5.2") == {"provider": "ollama-cloud", "model": "glm-5.2"}


def test_routed_reviewer_uses_its_provider_model_and_key(rp, routed):
    content, usage = rp.post("glm-5.2", "s", "u")
    req = routed["seen"][0]
    assert content == "ok" and usage["total_tokens"] == 14
    assert req.full_url == _ROUTE["base_url"]
    assert json.loads(req.data)["model"] == "z-ai/glm-5.2"
    assert req.get_header("Authorization") == "Bearer dummy-route-key"
    assert rp.provider_of("glm-5.2") == {"provider": "openrouter", "model": "z-ai/glm-5.2"}


def test_call_log_has_tokens_and_never_the_key(rp, routed):
    rp.post("glm-5.2", "s", "u")
    text = routed["log"].read_text(encoding="utf-8")
    entry = json.loads(text.splitlines()[0])
    assert entry["provider"] == "openrouter" and entry["model"] == "z-ai/glm-5.2"
    assert (entry["prompt_tokens"], entry["completion_tokens"]) == (11, 3)
    assert "dummy-route-key" not in text


@pytest.mark.parametrize("code", [402, 429])
def test_routed_provider_stops_on_the_first_402_or_429(rp, routed, monkeypatch, code):
    def refuse(req, timeout=None):
        routed["calls"]["n"] += 1
        raise urllib.error.HTTPError(req.full_url, code, "no", {}, io.BytesIO(b"rate"))

    monkeypatch.setattr(rp.urllib.request, "urlopen", refuse)
    with pytest.raises((rp.UsageCapError, RuntimeError)):
        rp.post("glm-5.2", "s", "u")
    assert routed["calls"]["n"] == 1
    assert rp._capped.is_set()


def test_route_must_keep_the_reviewer_family(rp, monkeypatch):
    monkeypatch.setenv("REVIEW_ROUTES", json.dumps(
        {"glm-5.2": {**_ROUTE, "model": "deepseek/deepseek-v4-pro"}}))
    with pytest.raises(ValueError):
        rp.routes()


def test_routed_verdicts_are_cached_apart_and_stamped_with_the_provider(rp, routed):
    assert rp._cache_key("glm-5.2", "abc").startswith("glm-5.2@openrouter:z-ai/glm-5.2|")
    assert rp._cache_key("deepseek-v4-pro", "abc").startswith("deepseek-v4-pro|")


def test_routed_call_has_a_hard_deadline_on_the_whole_reply(rp, routed, monkeypatch):
    """A provider that keeps the socket alive must not outlive the configured timeout."""
    import threading
    release = threading.Event()

    def trickle(req, timeout=None):
        routed["calls"]["n"] += 1
        release.wait(5)
        return io.StringIO(_OK_BODY)

    monkeypatch.setattr(rp.urllib.request, "urlopen", trickle)
    monkeypatch.setattr(rp, "REQUEST_ATTEMPTS", 1)
    with pytest.raises(RuntimeError):
        rp.post("glm-5.2", "s", "u", timeout=0.2)
    release.set()
    entry = json.loads(routed["log"].read_text(encoding="utf-8").splitlines()[-1])
    assert entry["status"] == "TimeoutError"


def test_route_extra_adds_provider_fields_but_never_overrides_the_request(rp, routed, monkeypatch):
    table = json.loads(rp.os.environ["REVIEW_ROUTES"])
    table["glm-5.2"]["extra"] = {"provider": {"sort": "throughput"}, "model": "other", "temperature": 1}
    monkeypatch.setenv("REVIEW_ROUTES", json.dumps(table))
    rp.post("glm-5.2", "s", "u")
    sent = json.loads(routed["seen"][0].data)
    assert sent["provider"] == {"sort": "throughput"}
    assert sent["model"] == "z-ai/glm-5.2" and sent["temperature"] == 0.1
