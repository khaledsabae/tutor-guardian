"""Shutdown and Linux fork regressions for the opt-in reservation settler."""
import dataclasses
import json
import os
import signal
import threading

import httpx
import pytest
import yaml
from fastapi.testclient import TestClient

from app.services import ai_gateway as gw
from app.services import cloud_budget as cb
from tests.test_cloud_budget_operability import (
    ROOT, WALLET, _attempts, _grab, _provider, _sse, capped,
)


def test_lifespan_shutdown_settles_inflight_reservations(capped, monkeypatch):  # noqa: F811
    from app import main

    settler = cb.BackgroundSettler()
    monkeypatch.setattr(cb, "SETTLER", settler)
    ledger = cb.CloudBudget(capped)

    def handler(request):
        _grab(ledger, 0.5)
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, content=_sse())

    with TestClient(main.app):
        _provider(handler).generate("س", options={"num_predict": 100})
        assert _attempts(capped) == [(1048576, 0)]
    assert _attempts(capped) == [(7, 1)]
    assert not settler._pending
    assert not settler._thread.is_alive()


def test_lifespan_shutdown_does_not_touch_settler_when_cap_off(monkeypatch):
    from app import main

    monkeypatch.setattr(gw, "LLM", dataclasses.replace(gw.LLM, cloud_budget_enforce=False))

    def forbidden(*args, **kwargs):
        pytest.fail("disabled cap must not start or drain the settler")

    monkeypatch.setattr(cb.SETTLER, "drain", forbidden)
    with TestClient(main.app):
        pass


def test_production_backend_has_time_to_drain():
    compose = yaml.safe_load((ROOT / "docker-compose.production.yml").read_text())
    assert compose["services"]["backend"]["container_name"] == "tg_backend"
    assert compose["services"]["backend"].get("stop_grace_period") == "20s"


@pytest.mark.skipif(not hasattr(os, "fork"), reason="requires Linux/POSIX fork")
def test_forked_worker_resets_settler_and_locked_ledger_state(capped, monkeypatch):  # noqa: F811
    parent = cb.BackgroundSettler()
    monkeypatch.setattr(cb, "SETTLER", parent)
    ledger = cb.CloudBudget(capped)
    ticket = ledger.reserve(WALLET, 10 * 1048576, 1048576, legacy_aliases=cb.PAID_ALIASES)
    writing = threading.Event()
    release = threading.Event()
    write_anchor = ledger._write_anchor

    def pause_before_anchor(conn):
        writing.set()
        assert release.wait(5), "parent transaction was not released"
        write_anchor(conn)

    monkeypatch.setattr(ledger, "_write_anchor", pause_before_anchor)
    monkeypatch.setattr(ledger, "try_settle_now", lambda *args: False)
    assert parent.submit(ledger, ticket, 5, 2)
    assert writing.wait(3), "parent must hold the transaction flock at fork"
    parent_thread = parent._thread
    local = cb._process_lock(ledger.anchor_path)
    sink_token = gw._RESERVATION_SINK.set([ticket.id])
    read_fd, write_fd = os.pipe()
    try:
        # These locks are inherited locked; the child must replace, never acquire them.
        with parent._guard, cb._PROCESS_LOCKS_GUARD:
            pid = os.fork()
        if pid == 0:
            os.close(read_fd)
            signal.signal(signal.SIGALRM, lambda *_: os._exit(124))
            signal.alarm(5)
            try:
                assert cb.SETTLER is not parent
                assert cb.SETTLER._thread is None
                assert not cb.SETTLER._pending
                assert gw._RESERVATION_SINK.get() is None
                assert cb._process_lock(ledger.anchor_path) is not local
                charge = gw._reserve_wire_budget("https://api.deepseek.com", "deepseek", [], 100,
                                                 model="test-model")
                charge.settle(3, 1)
                assert cb.SETTLER.drain(timeout=3) == []
                assert cb.SETTLER._thread is None or not cb.SETTLER._thread.is_alive()
                os.write(write_fd, json.dumps({"ok": True}).encode())
                os._exit(0)
            except BaseException as exc:
                os.write(write_fd, json.dumps({"error": repr(exc)}).encode())
                os._exit(1)
        os.close(write_fd)
        release.set()
        _, status = os.waitpid(pid, 0)
        result = os.read(read_fd, 4096).decode()
        assert os.waitstatus_to_exitcode(status) == 0, result
        assert json.loads(result) == {"ok": True}
        assert cb.SETTLER is parent and parent._thread is parent_thread
        assert parent.flush(timeout=3)
        assert sorted(_attempts(capped)) == [(4, 1), (7, 1)]
    finally:
        release.set()
        gw._RESERVATION_SINK.reset(sink_token)
        os.close(read_fd)
        parent.drain(timeout=3)
