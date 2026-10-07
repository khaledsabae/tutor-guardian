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
