"""Audit L11: one-time QR claim codes for the teen web surface are durable,
single-use under concurrency, and stored so that a copy of the table is useless.
"""
import importlib
import sqlite3
import threading
import time

import pytest

from app.db.init_db import db_path, init_db
from app.services import child_token


@pytest.fixture
def db(monkeypatch):
    monkeypatch.setenv("CHILD_MODE_SECRET", "test-secret-for-claims")
    init_db()


def _rows():
    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute("SELECT * FROM child_web_claims")]
    finally:
        conn.close()


def test_a_code_redeems_once_for_a_web_token(db):
    # A v2 web token resolves its device from the child's profile (it no
    # longer carries the parent's device id), so the child must exist.
    from app.db.init_db import get_conn
    conn = get_conn()
    conn.execute("INSERT INTO child_profiles (id, device_id, name, age_group) "
                 "VALUES (7, 'dev-1', 'سالم', '13-15')")
    conn.commit()
    conn.close()
    code = child_token.create_claim_code("dev-1", 7, ttl_seconds=3600)
    first = child_token.redeem_claim_code(code)
    assert first["child_id"] == 7
    payload = child_token.verify_child_token(first["token"], allow_web=True)
    assert payload["scope"] == "habit_child_web" and payload["device_id"] == "dev-1"
    assert child_token.redeem_claim_code(code) is None


def test_a_code_survives_a_restart(db):
    # The old dict lived in the module: a deploy between showing the QR and the
    # teen scanning it lost the code. Reloading the module is that restart.
    code = child_token.create_claim_code("dev-1", 7)
    importlib.reload(child_token)
    assert child_token.redeem_claim_code(code) is not None


def test_concurrent_redeems_yield_exactly_one_token(db):
    code = child_token.create_claim_code("dev-1", 7)
    results, start = [], threading.Barrier(8)

    def redeem():
        start.wait()
        results.append(child_token.redeem_claim_code(code))

    threads = [threading.Thread(target=redeem) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sum(r is not None for r in results) == 1


def test_an_expired_code_is_refused(db, monkeypatch):
    code = child_token.create_claim_code("dev-1", 7)
    real = time.time
    monkeypatch.setattr(child_token.time, "time", lambda: real() + 121)
    assert child_token.redeem_claim_code(code) is None


def test_the_table_holds_neither_the_code_nor_a_token(db):
    code = child_token.create_claim_code("dev-1", 7)
    rows = _rows()
    assert len(rows) == 1
    flat = " ".join(str(v) for v in rows[0].values())
    assert code not in flat
    assert "token" not in rows[0]


def test_expired_rows_are_pruned_on_create(db, monkeypatch):
    child_token.create_claim_code("dev-1", 7)
    real = time.time
    monkeypatch.setattr(child_token.time, "time", lambda: real() + 600)
    child_token.create_claim_code("dev-2", 8)
    assert [r["device_id"] for r in _rows()] == ["dev-2"]
