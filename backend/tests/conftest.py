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
def _generous_session_mint_limit(monkeypatch):
    """Every test shares app.main's in-process limiter, and dozens mint a
    session from the same TestClient address. The per-IP minting budget
    (rate_limit._SESSION_LIMIT) is exercised by its own test, which sets it."""
    from app.middleware import rate_limit

    monkeypatch.setattr(rate_limit, "_SESSION_LIMIT", 1_000_000)


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
