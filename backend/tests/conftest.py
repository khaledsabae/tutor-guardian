"""Shared test fixtures — isolates the conversation DB to a temp file."""
import os
import tempfile

import pytest


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
    monkeypatch.setattr(donations, "_unhealthy", False)
    monkeypatch.setattr(donations, "_voided_checked_at", None)
    yield
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
