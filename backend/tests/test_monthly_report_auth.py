"""Monthly report privacy tests — a child's name/progress must never be
publicly enumerable (regression for the unauthenticated endpoint)."""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("CONVERSATIONS_DB", str(tmp_path / "test.db"))
    from app.db.init_db import get_conn, init_db
    init_db()
    conn = get_conn()
    try:
        cur = conn.execute(
            "INSERT INTO child_profiles (device_id, name, age_group) "
            "VALUES ('dev-A', 'سرّي', '4-6')"
        )
        child_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()
    from app.main import app
    return TestClient(app), child_id


def _auth_headers(client: TestClient) -> dict:
    resp = client.post("/api/chat/sessions")
    assert resp.status_code == 201
    return {"Authorization": f"Bearer {resp.json()['token']}"}


def test_unauthenticated_monthly_report_is_rejected(client):
    c, child_id = client
    resp = c.get(f"/api/program/monthly-report/{child_id}")
    assert resp.status_code == 401
    assert "سرّي" not in resp.text


def test_foreign_device_cannot_read_another_familys_child(client):
    c, child_id = client
    headers = _auth_headers(c)  # a fresh device ≠ dev-A
    resp = c.get(f"/api/program/monthly-report/{child_id}", headers=headers)
    assert resp.status_code == 404
    assert "سرّي" not in resp.text
