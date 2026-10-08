"""Shared test fixtures — isolates the conversation DB to a temp file."""
import ipaddress
import os
import socket
import sys
import tempfile

import pytest


# ── Hugging Face models load from the local cache only ────────────────────
# SentenceTransformer("intfloat/multilingual-e5-small") sends HEAD requests to
# huggingface.co on every load, even with the weights fully cached — so any
# test that reaches the real embedder (an index rebuild, a vector query)
# connects out. Under the guard below that connect is refused, and
# huggingface_hub 1.16 then closes its shared httpx client and retries on the
# closed one: "Cannot send a request, as the client has been closed" — a
# RuntimeError its cache fallback never catches, so /assistant/stream answered
# `event: error`. Offline mode is what the golden CI (ops/tools/golden_ci.py)
# already runs with; the weights come from the cache that CI's backend-env
# step fills before pytest starts. huggingface_hub reads the flag once, at
# import — hence module level, before any test can import it.
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
if "huggingface_hub.constants" in sys.modules:  # a plugin imported it first
    sys.modules["huggingface_hub.constants"].HF_HUB_OFFLINE = True


# ── No test reaches the network ───────────────────────────────────────────
# A test that talks to a real host is slow, flaky and leaks the question it
# sends. Production code often swallows a network error on purpose (best-effort
# enrichment), so refusing the connect alone is not enough: the leak would pass
# silently. Every non-loopback attempt is refused AND recorded, and the test
# fails at teardown with the targets it tried. A test that truly needs the
# network says so with @pytest.mark.allow_network (none does today).

def _is_local(address) -> bool:
    if not isinstance(address, tuple):  # AF_UNIX path / abstract socket
        return True
    host = str(address[0]).split("%", 1)[0]
    if host == "localhost":
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False  # a hostname other than localhost would be resolved
    mapped = getattr(ip, "ipv4_mapped", None)
    ip = mapped or ip
    return ip.is_loopback or ip.is_unspecified


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "allow_network: this test may open non-loopback sockets (must be justified)",
    )


@pytest.fixture(autouse=True)
def _no_network(request, monkeypatch):
    if request.node.get_closest_marker("allow_network"):
        yield
        return

    attempts: list[str] = []

    def _guard(original, address_index):
        def guarded(sock, *args, **kwargs):
            address = args[address_index] if len(args) > address_index else kwargs.get("address")
            if address is not None and not _is_local(address):
                attempts.append(repr(address))
                raise ConnectionRefusedError(
                    f"test network guard: connection to {address!r} refused")
            return original(sock, *args, **kwargs)
        return guarded

    monkeypatch.setattr(socket.socket, "connect", _guard(socket.socket.connect, 0))
    monkeypatch.setattr(socket.socket, "connect_ex", _guard(socket.socket.connect_ex, 0))
    # sendto(data, address) / sendto(data, flags, address): the address is last.
    original_sendto = socket.socket.sendto

    def guarded_sendto(sock, data, *rest):
        if rest and not _is_local(rest[-1]):
            attempts.append(repr(rest[-1]))
            raise ConnectionRefusedError(
                f"test network guard: datagram to {rest[-1]!r} refused")
        return original_sendto(sock, data, *rest)

    monkeypatch.setattr(socket.socket, "sendto", guarded_sendto)
    yield
    if attempts:
        pytest.fail(
            f"test opened {len(attempts)} non-loopback socket(s): "
            f"{sorted(set(attempts))} — mock the client, or mark the test "
            "@pytest.mark.allow_network",
            pytrace=False,
        )


@pytest.fixture(autouse=True)
def mock_domain_classifier_llm(monkeypatch):
    """Globally mock domain classifier LLM calls to prevent tests from hitting live Ollama."""
    monkeypatch.setattr(
        "app.services.domain_classifier._call_llm",
        lambda *args, **kwargs: ["tarbiyah"]
    )


@pytest.fixture(autouse=True)
def _closed_primary_breaker():
    """The primary-LLM circuit breaker is module state; one test's failures
    must not open it for the next."""
    from app.services.ai_gateway import primary_breaker

    primary_breaker.reset()
    yield
    primary_breaker.reset()


@pytest.fixture(autouse=True)
def _generous_session_mint_limit(monkeypatch):
    """Every test shares app.main's in-process limiter, and dozens mint a
    session from the same TestClient address. The per-IP minting budget
    (rate_limit._SESSION_LIMIT) is exercised by its own test, which sets it."""
    from app.middleware import rate_limit

    monkeypatch.setattr(rate_limit, "_SESSION_LIMIT", 1_000_000)


@pytest.fixture(autouse=True)
def _generous_support_verify_limit(monkeypatch):
    """Same reason as the session limit above: every test's TestClient shares
    one address and one in-process limiter. The verify budget is exercised by
    its own test, which sets it."""
    from app.middleware import rate_limit

    monkeypatch.setattr(rate_limit, "_SUPPORT_VERIFY_LIMIT", 1_000_000)


@pytest.fixture(autouse=True)
def _fresh_support_state(monkeypatch):
    """donations computes its gate, credentials and verifier once per process
    (by design — see its docstring). Tests change the environment between
    cases, so each one starts from a cold process state."""
    from app.services import donations

    # Captured now: a test may monkeypatch these names, and this teardown runs
    # before monkeypatch restores them.
    caches = (donations._gate, donations._credentials, donations._cached_verifier)
    for cached in caches:
        cached.cache_clear()
    for name, cold in (("_rejected_until", None), ("_rejections", 0),
                       ("_reprobe_logged", False), ("_last_reconcile_start", None),
                       ("_reconciler", None)):
        monkeypatch.setattr(donations, name, cold)
    yield
    # A background reconciliation started by this test finishes inside it.
    thread = donations._reconciler
    if thread is not None:
        thread.join(timeout=10)
    for cached in caches:
        cached.cache_clear()


@pytest.fixture(autouse=True)
def _skip_startup_warmup(monkeypatch):
    """Every `TestClient(app)` runs the app's lifespan, and its warm-ups (ONNX
    embedder, ChromaDB index, reranker, an Ollama ping with a 5 s timeout) cost
    seconds per boot — on the CI runner, about a minute per smoke test. Tests
    that need retrieval or a model mock it; nothing here tests the warm-up."""
    monkeypatch.setenv("SKIP_WARMUP", "1")


@pytest.fixture(autouse=True)
def _temp_conversations_db(monkeypatch):
    """Point every test at a throwaway SQLite DB so tests don't touch ops/."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    monkeypatch.setenv("CONVERSATIONS_DB", path)  # resolved at call time by db_path()
    monkeypatch.setenv("CHILD_MODE_SECRET", "test-child-mode-secret")  # child_token fails closed without it
    from app.db.init_db import init_db
    init_db()
    yield
    try:
        os.remove(path)
    except OSError:
        pass
