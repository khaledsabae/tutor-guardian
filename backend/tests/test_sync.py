import sqlite3
import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware

from app.db.init_db import init_db, get_conn
from app.routers.sync import router as sync_router
from app.services.crypto_sync import encrypt_database_payload, decrypt_database_payload

@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    db = tmp_path / "sync.db"
    monkeypatch.setenv("CONVERSATIONS_DB", str(db))
    init_db()
    return db

class _AuthStubMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, device_id: str = "test-device-sync"):
        super().__init__(app)
        self.device_id = device_id

    async def dispatch(self, request: Request, call_next):
        # Allow dynamically changing device_id in tests by checking request headers
        dev_id = request.headers.get("x-test-device-id", self.device_id)
        request.state.device_id = dev_id
        return await call_next(request)

@pytest.fixture
def app(tmp_db):
    a = FastAPI()
    a.add_middleware(_AuthStubMiddleware)
    a.include_router(sync_router)
    return a

@pytest.fixture
def client(app):
    with TestClient(app) as c:
        yield c

def test_crypto_sync_encryption_decryption():
    """Verify that DB bytes can be encrypted and decrypted back correctly."""
    db_bytes = b"Fake SQLite DB Header \x00\x01\x02\x03 and tables data"
    passphrase = "my-secure-parent-password"

    pkg = encrypt_database_payload(db_bytes, passphrase)
    assert "salt" in pkg
    assert "nonce" in pkg
    assert "payload" in pkg

    # Correct decryption
    decrypted = decrypt_database_payload(pkg, passphrase)
    assert decrypted == db_bytes

    # Wrong password raises error
    with pytest.raises(Exception):
        decrypt_database_payload(pkg, "wrong-password")

def test_sync_api_upload_download(client):
    """Test standard single-device backup upload and download."""
    upload_data = {
        "salt": "c2FsdF9iYXNlNjQ=",
        "nonce": "bm9uY2VfYmFzZTY0",
        "payload": "cGF5bG9hZF9iYXNlNjQ="
    }

    # Upload
    r = client.post("/api/sync/upload", json=upload_data, headers={"x-test-device-id": "device-1"})
    assert r.status_code == 200
    assert r.json()["ok"] is True

    # Download
    r = client.get("/api/sync/download", headers={"x-test-device-id": "device-1"})
    assert r.status_code == 200
    res = r.json()
    assert res["ok"] is True
    assert res["salt"] == upload_data["salt"]
    assert res["nonce"] == upload_data["nonce"]
    assert res["payload"] == upload_data["payload"]

def test_sync_api_download_missing(client):
    """Ensure download returns 404 if no backup exists for device/Google ID."""
    r = client.get("/api/sync/download", headers={"x-test-device-id": "device-unknown"})
    assert r.status_code == 404
    assert r.json()["detail"] == "No backup found"

def test_sync_cross_device_google_sync(client, tmp_db):
    """Verify cross-device backup restore via shared Google identity link."""
    # 1. Setup identity link mock data directly in sqlite DB
    conn = sqlite3.connect(tmp_db)
    # Link device-A and device-B to the same google_id
    conn.execute("INSERT INTO identity_links (device_id, google_id) VALUES (?, ?)", ("device-A", "google-123"))
    conn.execute("INSERT INTO identity_links (device_id, google_id) VALUES (?, ?)", ("device-B", "google-123"))
    conn.commit()
    conn.close()

    # 2. Upload backup from Device A
    backup_data = {
        "salt": "c2FsdF9kZXZpY2VfQQ==",
        "nonce": "bm9uY2VfZGV2aWNlX0E=",
        "payload": "cGF5bG9hZF9kZXZpY2VfQQ=="
    }
    r = client.post("/api/sync/upload", json=backup_data, headers={"x-test-device-id": "device-A"})
    assert r.status_code == 200

    # 3. Download backup from Device B (which has no direct backup of its own)
    r = client.get("/api/sync/download", headers={"x-test-device-id": "device-B"})
    assert r.status_code == 200
    res = r.json()
    assert res["ok"] is True
    assert res["salt"] == backup_data["salt"]
    assert res["nonce"] == backup_data["nonce"]
    assert res["payload"] == backup_data["payload"]
