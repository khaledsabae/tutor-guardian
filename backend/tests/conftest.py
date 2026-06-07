"""Shared test fixtures — isolates the conversation DB to a temp file."""
import os
import tempfile

import pytest


@pytest.fixture(autouse=True)
def _temp_conversations_db(monkeypatch):
    """Point every test at a throwaway SQLite DB so tests don't touch ops/."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    monkeypatch.setenv("CONVERSATIONS_DB", path)  # resolved at call time by db_path()
    from app.db.init_db import init_db
    init_db()
    yield
    try:
        os.remove(path)
    except OSError:
        pass
