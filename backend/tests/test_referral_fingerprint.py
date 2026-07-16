import pytest
from fastapi.testclient import TestClient
import sqlite3
from app.main import app
from app.db.init_db import db_path, get_conn
from app.routers.referral import REWARD_COINS


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_referral_fingerprint_happy_path(client):
    # 1. Register a referral code for a "referrer" device
    conn = get_conn()
    conn.execute(
        "INSERT INTO referral_codes (device_id, code) VALUES (?, ?)",
        ("referrer_device", "REF123")
    )
    conn.commit()
    conn.close()

    # 2. Simulate web landing click from IP 203.0.113.195 with referrer code REF123
    r_click = client.get("/go?ref=REF123", headers={"cf-connecting-ip": "203.0.113.195"})
    assert r_click.status_code == 200

    # Verify click was inserted into database
    conn = get_conn()
    click = conn.execute("SELECT * FROM referral_clicks").fetchone()
    assert click is not None
    assert click["ip"] == "203.0.113.195"
    assert click["code"] == "REF123"
    conn.close()

    # 3. Simulate first run from app with new device (same IP) calling claim with "AUTO"
    # First create a session to get a token for Bearer auth
    r_session = client.post("/api/chat/sessions", json={"device_id": "referee_device"})
    assert r_session.status_code == 201
    token = r_session.json()["token"]

    # Claim referral with AUTO
    r_claim = client.post(
        "/api/referral/claim",
        json={"code": "AUTO"},
        headers={"Authorization": f"Bearer {token}", "cf-connecting-ip": "203.0.113.195"}
    )
    assert r_claim.status_code == 200
    res = r_claim.json()
    assert res["ok"] is True
    assert res["already_claimed"] is False
    assert res["reward_coins"] == REWARD_COINS

    # Verify that the referral was correctly recorded in the referrals table
    conn = get_conn()
    ref = conn.execute("SELECT * FROM referrals WHERE referred_device = 'referee_device'").fetchone()
    assert ref is not None
    assert ref["referrer_device"] == "referrer_device"
    assert ref["code"] == "REF123"
    conn.close()


def test_referral_fingerprint_no_match(client):
    # Create session for the referee
    r_session = client.post("/api/chat/sessions", json={"device_id": "referee_device_no_match"})
    assert r_session.status_code == 201
    token = r_session.json()["token"]

    # Claim referral with AUTO when no web click exists for this IP
    r_claim = client.post(
        "/api/referral/claim",
        json={"code": "AUTO"},
        headers={"Authorization": f"Bearer {token}", "cf-connecting-ip": "198.51.100.5"}
    )
    assert r_claim.status_code == 200
    res = r_claim.json()
    assert res["ok"] is False
    assert res["already_claimed"] is False
    assert res["reward_coins"] == 0
    assert res["detail"] == "no_fingerprint_match"

    # Verify no referral was recorded
    conn = get_conn()
    ref = conn.execute("SELECT 1 FROM referrals WHERE referred_device = 'referee_device_no_match'").fetchone()
    assert ref is None
    conn.close()
