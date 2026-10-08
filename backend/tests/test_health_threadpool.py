"""Deep health probes must leave the event loop free for the cheap health route."""

import asyncio
import threading

import httpx
import pytest
from fastapi import FastAPI

from app.db import init_db
from app.routers import health
from app.services import reranker, retrieval


class FakeConnection:
    def execute(self, statement):
        assert statement == "SELECT 1"
        return self

    def fetchone(self):
        return (1,)

    def close(self):
        pass


class FakeCollection:
    def count(self):
        return 1


@pytest.fixture
def health_app(monkeypatch):
    monkeypatch.setattr(init_db, "get_conn", FakeConnection)
    monkeypatch.setattr(retrieval, "_get_collection", FakeCollection)
    monkeypatch.setattr(reranker, "is_disabled", lambda: False)
    app = FastAPI()
    app.include_router(health.router)
    return app


@pytest.mark.parametrize("blocked_probe", ["sqlite", "chromadb"])
def test_cheap_health_completes_while_deep_probe_is_blocked(health_app, monkeypatch,
                                                         blocked_probe):
    entered = threading.Event()
    release = threading.Event()

    def block():
        entered.set()
        assert release.wait(timeout=5), "Probe watchdog did not release the fake I/O"

    if blocked_probe == "sqlite":
        class SlowConnection(FakeConnection):
            def execute(self, statement):
                block()
                return super().execute(statement)

        monkeypatch.setattr(init_db, "get_conn", SlowConnection)
    else:
        class SlowCollection(FakeCollection):
            def count(self):
                block()
                return super().count()

        monkeypatch.setattr(retrieval, "_get_collection", SlowCollection)

    # asyncio timeouts cannot rescue an event loop blocked by synchronous I/O.
    # A separate watchdog makes the original broken route fail finitely.
    watchdog = threading.Timer(3, release.set)
    watchdog.start()

    async def requests():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=health_app),
                                    base_url="http://health.test") as client:
            deep = asyncio.create_task(client.get("/health"))
            try:
                assert await asyncio.to_thread(entered.wait, 2), "Deep probe never started"
                cheap = await asyncio.wait_for(client.get("/api/health"), timeout=1)
                completed_before_release = not release.is_set()
                assert cheap.status_code == 200
                assert cheap.json() == {"status": "ok"}
            finally:
                release.set()
                deep_response = await asyncio.wait_for(deep, timeout=5)
            assert deep_response.status_code == 200
            assert deep_response.json() == {
                "status": "ok",
                "checks": {"sqlite": "ok", "chromadb": "ok", "reranker": "ok"},
            }
            return completed_before_release

    try:
        completed_before_release = asyncio.run(requests())
    finally:
        release.set()
        watchdog.cancel()
        watchdog.join(timeout=5)

    assert completed_before_release, "Cheap health waited for the blocked deep probe"


@pytest.mark.parametrize("failure, expected_status, expected_checks", [
    (None, 200, {"sqlite": "ok", "chromadb": "ok", "reranker": "ok"}),
    ("sqlite", 500, {"sqlite": "error: SQLite unavailable", "chromadb": "ok",
                     "reranker": "ok"}),
    ("unloaded", 200, {"sqlite": "ok", "chromadb": "not_loaded", "reranker": "ok"}),
    ("chromadb", 200, {"sqlite": "ok", "chromadb": "not_ready: Chroma unavailable",
                       "reranker": "ok"}),
    ("disabled", 200, {"sqlite": "ok", "chromadb": "ok",
                       "reranker": "disabled_after_strikes"}),
    ("reranker", 200, {"sqlite": "ok", "chromadb": "ok",
                       "reranker": "unknown: Reranker unavailable"}),
])
def test_deep_health_preserves_response_and_degraded_status(health_app, monkeypatch,
                                                           failure, expected_status,
                                                           expected_checks):
    def sqlite_failure():
        raise RuntimeError("SQLite unavailable")

    def chroma_failure():
        raise RuntimeError("Chroma unavailable")

    def reranker_failure():
        raise RuntimeError("Reranker unavailable")

    if failure == "sqlite":
        monkeypatch.setattr(init_db, "get_conn", sqlite_failure)
    elif failure == "unloaded":
        monkeypatch.setattr(retrieval, "_get_collection", lambda: None)
    elif failure == "chromadb":
        monkeypatch.setattr(retrieval, "_get_collection", chroma_failure)
    elif failure == "disabled":
        monkeypatch.setattr(reranker, "is_disabled", lambda: True)
    elif failure == "reranker":
        monkeypatch.setattr(reranker, "is_disabled", reranker_failure)

    async def request():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=health_app),
                                    base_url="http://health.test") as client:
            return await client.get("/health")

    response = asyncio.run(request())
    assert response.status_code == expected_status
    assert response.json() == {
        "status": "down" if expected_status == 500 else "ok",
        "checks": expected_checks,
    }
