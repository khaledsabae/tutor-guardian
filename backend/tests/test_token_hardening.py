"""Audit H5 (rest): hashed bearer tokens, sliding expiry, log-safe device ids."""
import hashlib
import logging
import sqlite3

import pytest
from fastapi.testclient import TestClient

from app.core.log_safety import device_tag
from app.db.init_db import db_path, init_db
from app.services import conversation_store as store
from app.services import fiqh_guard


def _row(token: str):
    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(
            "SELECT token, device_id, expires_at, "
            "julianday(expires_at) - julianday('now') AS days_left "
            "FROM api_tokens WHERE token = ?",
            (hashlib.sha256(token.encode()).hexdigest(),),
        ).fetchone()
    finally:
        conn.close()


def _set_expiry(token: str, modifier: str) -> None:
    conn = sqlite3.connect(db_path())
    conn.execute(
        "UPDATE api_tokens SET expires_at = datetime('now', ?) WHERE token = ?",
        (modifier, hashlib.sha256(token.encode()).hexdigest()),
    )
    conn.commit()
    conn.close()


@pytest.fixture()
def db():
    init_db()


# ── storage ───────────────────────────────────────────────────────────────

def test_only_the_hash_is_stored(db):
    token = store.create_token("dev-1", "s-1")
    conn = sqlite3.connect(db_path())
    stored = [r[0] for r in conn.execute("SELECT token FROM api_tokens")]
    conn.close()
    assert stored == [hashlib.sha256(token.encode()).hexdigest()]
    assert token not in stored


def test_the_stored_hash_is_not_a_credential(db):
    token = store.create_token("dev-1", "s-1")
    assert store.validate_token(token) == {"device_id": "dev-1", "session_id": "s-1"}
    # Someone holding a copy of the table only has the digest.
    assert store.validate_token(hashlib.sha256(token.encode()).hexdigest()) is None
    assert store.validate_token("") is None


# ── expiry ────────────────────────────────────────────────────────────────

def test_new_tokens_expire_after_the_ttl(db, monkeypatch):
    monkeypatch.setenv("TOKEN_TTL_DAYS", "30")
    row = _row(store.create_token("dev-1", "s-1"))
    assert 29.9 < row["days_left"] <= 30


def test_an_expired_token_is_refused(db):
    token = store.create_token("dev-1", "s-1")
    _set_expiry(token, "-1 minute")
    assert store.validate_token(token) is None


def test_use_slides_the_expiry_once_half_is_gone(db, monkeypatch):
    monkeypatch.setenv("TOKEN_TTL_DAYS", "30")
    token = store.create_token("dev-1", "s-1")
    _set_expiry(token, "+10 days")                 # less than half of 30 left
    assert store.validate_token(token) is not None
    assert _row(token)["days_left"] > 29.9


def test_a_fresh_token_is_not_rewritten_on_every_request(db, monkeypatch):
    monkeypatch.setenv("TOKEN_TTL_DAYS", "30")
    token = store.create_token("dev-1", "s-1")
    _set_expiry(token, "+20 days")                 # more than half left
    before = _row(token)["expires_at"]
    store.validate_token(token)
    assert _row(token)["expires_at"] == before


# ── v28 migration ─────────────────────────────────────────────────────────

def _legacy_db() -> None:
    conn = sqlite3.connect(db_path())
    conn.executescript(
        """
        CREATE TABLE schema_version (version INTEGER NOT NULL);
        INSERT INTO schema_version VALUES (27);
        CREATE TABLE api_tokens (
            token TEXT PRIMARY KEY, device_id TEXT NOT NULL,
            session_id TEXT NOT NULL, expires_at TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')));
        INSERT INTO api_tokens (token, device_id, session_id)
            VALUES ('tg_legacy_plaintext', 'dev-old', 's-old');
        """
    )
    conn.commit()
    conn.close()


@pytest.fixture()
def legacy(tmp_path, monkeypatch):
    monkeypatch.setenv("CONVERSATIONS_DB", str(tmp_path / "legacy.db"))
    _legacy_db()


def test_legacy_plaintext_tokens_are_hashed_and_keep_working(legacy):
    init_db()
    conn = sqlite3.connect(db_path())
    rows = conn.execute("SELECT token, expires_at FROM api_tokens").fetchall()
    version = conn.execute("SELECT version FROM schema_version").fetchone()[0]
    conn.close()
    assert version == 28
    assert rows == [(hashlib.sha256(b"tg_legacy_plaintext").hexdigest(), rows[0][1])]
    assert rows[0][1] is not None                   # given a full TTL, not NULL
    # The install still holds the raw token: it must not be logged out.
    assert store.validate_token("tg_legacy_plaintext") == {
        "device_id": "dev-old", "session_id": "s-old"}


def test_the_v28_migration_is_idempotent(legacy):
    init_db()
    init_db()
    assert store.validate_token("tg_legacy_plaintext") is not None


# ── minting with an expired token as proof ────────────────────────────────

@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(fiqh_guard, "_log_block", lambda *a, **k: None)
    from app.config.guardrails_loader import load_guardrails_config
    from app.main import app

    init_db()
    app.state.guardrails_config = load_guardrails_config()
    return TestClient(app)


def _mint(c: TestClient, device_id: str, token: str | None = None):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return c.post("/api/chat/sessions", headers=headers, json={"device_id": device_id})


def test_an_expired_token_is_refused_by_the_api(client):
    token = _mint(client, "dev-1").json()["token"]
    _set_expiry(token, "-1 minute")
    assert client.get("/api/chat/sessions", headers={
        "Authorization": f"Bearer {token}"}).status_code == 401


def test_an_expired_token_still_proves_its_device_when_minting(client, monkeypatch):
    monkeypatch.setenv("SESSION_MINT_ENFORCE", "true")
    token = _mint(client, "dev-1").json()["token"]
    _set_expiry(token, "-1 minute")
    r = _mint(client, "dev-1", token)
    assert r.status_code == 201
    assert store.validate_token(r.json()["token"])["device_id"] == "dev-1"
    # …but only for its own device.
    assert _mint(client, "dev-2", token).status_code == 403


# ── device ids stay out of logs ───────────────────────────────────────────

def test_device_tag_is_stable_and_not_the_id():
    tag = device_tag("device-secret-123")
    assert tag == device_tag("device-secret-123")
    assert "device-secret-123" not in tag and tag.startswith("d:")
    assert device_tag(None) == "-"


def test_minting_without_proof_logs_a_tag_not_the_device_id(client, caplog):
    _mint(client, "device-secret-123")
    with caplog.at_level(logging.INFO, logger="app.routers.chat"):
        _mint(client, "device-secret-123")
    assert "device-secret-123" not in caplog.text
    assert device_tag("device-secret-123") in caplog.text


def test_push_send_failure_log_carries_no_device_id(monkeypatch, caplog):
    from app.services import push_sender

    def _boom():
        raise sqlite3.OperationalError("disk I/O error")

    monkeypatch.setattr(push_sender, "get_conn", _boom)
    with caplog.at_level(logging.WARNING, logger="app.services.push_sender"):
        push_sender._record_send("device-secret-123", "daily_tip")
    assert "device-secret-123" not in caplog.text
    assert device_tag("device-secret-123") in caplog.text
