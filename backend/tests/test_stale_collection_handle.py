"""A collection deleted underneath the cached handle must not take the app down.

`_collection` is a process-wide singleton. When the collection it points at is
deleted and recreated — by the rebuild path, or by any other process opening the
same persist directory — Chroma raises on every later call in this process and
the assistant answers 500 to every parent until someone restarts the container.

That happened in production on 2026-07-29: a diagnostic `docker exec … python -c
"_ensure_index()"` rebuilt the collection while uvicorn held the old handle.
"""
import pytest

from app.services import retrieval


class _StaleThenLive:
    """First call raises as a dead handle would; later calls succeed."""

    def __init__(self, error):
        self.error = error
        self.calls = 0

    def __call__(self, collection):
        self.calls += 1
        if self.calls == 1:
            raise self.error
        return "ok"


@pytest.fixture
def _restore_handle():
    saved = retrieval._collection
    yield
    retrieval._collection = saved


def test_stale_handle_is_reacquired_not_propagated(monkeypatch, _restore_handle):
    acquired = []
    monkeypatch.setattr(retrieval, "_get_collection",
                        lambda: acquired.append(1) or "collection")
    op = _StaleThenLive(retrieval._STALE_COLLECTION_ERRORS[0]("gone"))

    assert retrieval.with_live_collection(op) == "ok"
    assert op.calls == 2, "should retry exactly once"
    assert len(acquired) == 2, "should re-acquire the handle before retrying"


def test_handle_is_dropped_before_the_retry(monkeypatch, _restore_handle):
    """Re-acquiring is pointless if the dead handle is still cached."""
    seen = []

    def _fake_get():
        seen.append(retrieval._collection)
        return "collection"

    monkeypatch.setattr(retrieval, "_get_collection", _fake_get)
    retrieval._collection = "dead-handle"
    retrieval.with_live_collection(_StaleThenLive(retrieval._STALE_COLLECTION_ERRORS[0]("gone")))

    assert seen[-1] is None, "the stale handle must be cleared before re-acquiring"


def test_an_unrelated_error_is_not_retried(monkeypatch, _restore_handle):
    """Only a stale handle earns a second attempt — real bugs must surface."""
    monkeypatch.setattr(retrieval, "_get_collection", lambda: "collection")

    def _boom(collection):
        raise RuntimeError("something else entirely")

    with pytest.raises(RuntimeError, match="something else entirely"):
        retrieval.with_live_collection(_boom)


def test_a_persistently_dead_collection_still_raises(monkeypatch, _restore_handle):
    """One retry, not an infinite loop — a genuinely missing collection surfaces."""
    monkeypatch.setattr(retrieval, "_get_collection", lambda: "collection")
    err = retrieval._STALE_COLLECTION_ERRORS[0]

    def _always_stale(collection):
        raise err("gone for good")

    with pytest.raises(err):
        retrieval.with_live_collection(_always_stale)


def test_stale_error_types_resolved():
    """The tuple must never be empty, or `except ()` would catch nothing."""
    assert retrieval._STALE_COLLECTION_ERRORS
    assert all(isinstance(e, type) for e in retrieval._STALE_COLLECTION_ERRORS)
