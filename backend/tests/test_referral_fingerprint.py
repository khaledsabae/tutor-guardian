import pytest
from fastapi.testclient import TestClient
import sqlite3
from app.main import app
from app.db.init_db import db_path, get_conn
from app.routers.referral import REWARD_COINS


# Production traffic arrives Cloudflare → nginx → app, so the TCP peer is the
# nginx container on the Docker network. ClientIPMiddleware only believes
# CF-Connecting-IP / X-Forwarded-For from such a trusted peer (audit H4).
_NGINX_PEER = ("172.18.0.5", 50000)


@pytest.fixture
def client():
    with TestClient(app, client=_NGINX_PEER) as c:
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


def test_spoofed_client_header_from_an_untrusted_peer_is_ignored():
    """A caller reaching the app directly cannot pick the IP it is matched on."""
    conn = get_conn()
    conn.execute("INSERT INTO referral_codes (device_id, code) VALUES (?, ?)",
                 ("referrer_device_2", "REF999"))
    conn.execute("INSERT INTO referral_clicks (ip, user_agent, code) VALUES (?, ?, ?)",
                 ("203.0.113.77", "ua", "REF999"))
    conn.commit()
    conn.close()

    with TestClient(app, client=("198.51.100.9", 4000)) as direct:
        token = direct.post("/api/chat/sessions",
                            json={"device_id": "spoofer_device"}).json()["token"]
        r = direct.post(
            "/api/referral/claim",
            json={"code": "AUTO"},
            headers={"Authorization": f"Bearer {token}",
                     "cf-connecting-ip": "203.0.113.77",
                     "x-forwarded-for": "203.0.113.77"},
        )
    assert r.status_code == 200
    assert r.json()["ok"] is False  # matched on its real address, not the forged one


# ── Audit M8: the landing page cannot be used to flood referral_clicks ──────

def _codes(*codes):
    conn = get_conn()
    for i, c in enumerate(codes):
        conn.execute("INSERT INTO referral_codes (device_id, code) VALUES (?, ?)",
                     (f"owner-{i}-{c}", c))
    conn.commit()
    conn.close()


def _clicks():
    conn = get_conn()
    rows = conn.execute("SELECT ip, code, user_agent FROM referral_clicks").fetchall()
    conn.close()
    return rows


def test_unknown_codes_are_not_recorded(client):
    r = client.get("/go?ref=NOPE99", headers={"cf-connecting-ip": "203.0.113.7"})
    assert r.status_code == 200          # the page still renders
    assert _clicks() == []


def test_repeat_clicks_refresh_instead_of_piling_up(client):
    _codes("REF123")
    for _ in range(5):
        client.get("/go?ref=REF123", headers={"cf-connecting-ip": "203.0.113.7"})
    assert len(_clicks()) == 1


def test_clicks_per_ip_are_capped(client):
    codes = [f"C{i:04d}" for i in range(25)]
    _codes(*codes)
    for code in codes:
        assert client.get(f"/go?ref={code}",
                          headers={"cf-connecting-ip": "203.0.113.7"}).status_code == 200
    assert len(_clicks()) == 20
    # Another visitor is unaffected.
    client.get("/go?ref=C0000", headers={"cf-connecting-ip": "198.51.100.4"})
    assert len(_clicks()) == 21


def test_user_agent_is_truncated(client):
    _codes("REF123")
    client.get("/go?ref=REF123", headers={"cf-connecting-ip": "203.0.113.7",
                                          "user-agent": "x" * 5000})
    assert len(_clicks()[0]["user_agent"]) == 256
