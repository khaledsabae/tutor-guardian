"""Campaign codes: a campaign install can no longer be lost to a 404.

The app makes exactly one claim per install (referral_service.dart sets
`referral.referrer_checked` before it tries), and a 404 is not retried and
does not fall back to the AUTO match. Until now a code had to exist in
referral_codes to be claimable, and in production none but device codes did
(4,384 rows, all six-character device codes, read-only 2026-10-04) — so any
campaign link shared before someone wrote its row by hand lost every install.
"""
import pytest
from fastapi.testclient import TestClient

from app.db.init_db import get_conn
from app.main import app
from app.routers.referral import REWARD_COINS

_NGINX_PEER = ("172.18.0.5", 50000)


@pytest.fixture
def client():
    with TestClient(app, client=_NGINX_PEER) as c:
        yield c


def _token(client, device_id: str) -> dict:
    r = client.post("/api/chat/sessions", json={"device_id": device_id})
    assert r.status_code == 201
    return {"Authorization": f"Bearer {r.json()['token']}"}


def _referral_of(device_id: str):
    conn = get_conn()
    try:
        return conn.execute(
            "SELECT referrer_device, code, via FROM referrals WHERE referred_device = ?",
            (device_id,),
        ).fetchone()
    finally:
        conn.close()


def test_a_never_seen_campaign_code_is_claimed_not_404(client):
    headers = _token(client, "new-install-1")
    r = client.post("/api/referral/claim", json={"code": "DA01"}, headers=headers)
    assert r.status_code == 200, r.text
    assert r.json() == {"ok": True, "already_claimed": False, "reward_coins": REWARD_COINS}
    row = _referral_of("new-install-1")
    assert (row["referrer_device"], row["code"]) == ("campaign#DA01", "DA01")


def test_a_hand_typed_campaign_code_is_normalised(client):
    # The deep-link path sends `ref` as it appears in the link, upper-cased.
    headers = _token(client, "new-install-2")
    r = client.post("/api/referral/claim", json={"code": "kt-17"}, headers=headers)
    assert r.json()["ok"] is True
    assert _referral_of("new-install-2")["code"] == "KT17"


def test_a_device_can_still_be_attributed_only_once(client):
    headers = _token(client, "new-install-3")
    assert client.post("/api/referral/claim", json={"code": "WA01"},
                       headers=headers).json()["ok"] is True
    again = client.post("/api/referral/claim", json={"code": "DA02"}, headers=headers)
    assert again.json() == {"ok": False, "already_claimed": True, "reward_coins": 0}
    assert _referral_of("new-install-3")["code"] == "WA01"


def test_unknown_personal_codes_still_404(client):
    headers = _token(client, "new-install-4")
    r = client.post("/api/referral/claim", json={"code": "ZZZZ22"}, headers=headers)
    assert r.status_code == 404
    assert _referral_of("new-install-4") is None


def test_a_real_device_code_still_credits_the_device(client):
    conn = get_conn()
    conn.execute("INSERT INTO referral_codes (device_id, code) VALUES (?, ?)",
                 ("inviter-device", "ABC234"))
    conn.commit()
    conn.close()
    headers = _token(client, "new-install-5")
    assert client.post("/api/referral/claim", json={"code": "abc234"},
                       headers=headers).json()["ok"] is True
    assert _referral_of("new-install-5")["referrer_device"] == "inviter-device"


def test_auto_claim_finds_a_campaign_click(client):
    # Play lost the referrer; the visitor had opened a campaign link from this IP.
    ip = {"cf-connecting-ip": "203.0.113.50"}
    assert client.get("/go?ref=PD01", headers=ip).status_code == 200
    headers = {**_token(client, "new-install-6"), **ip}
    r = client.post("/api/referral/claim", json={"code": "AUTO"}, headers=headers)
    assert r.json()["ok"] is True
    assert _referral_of("new-install-6")["code"] == "PD01"


def test_nobody_can_sign_in_as_a_campaign(client):
    # Otherwise GET /api/referral/me would show that device the campaign's
    # installs as its own invites.
    r = client.post("/api/chat/sessions", json={"device_id": "campaign#DA01"})
    assert r.status_code == 422


def test_the_share_url_is_unchanged(client):
    headers = _token(client, "new-install-7")
    me = client.get("/api/referral/me", headers=headers).json()
    assert me["share_url"] == (
        "https://play.google.com/store/apps/details?id=com.alsaba.almorabbi"
        f"&referrer=ref_{me['code']}")


def test_a_device_code_that_starts_like_a_campaign_stays_a_persons_invite(client):
    # ENV9Z5 exists in production as a parent's own code.
    conn = get_conn()
    conn.execute("INSERT INTO referral_codes (device_id, code) VALUES (?, ?)",
                 ("parent-device", "ENV9Z5"))
    conn.commit()
    conn.close()
    page = client.get("/go?ref=ENV9Z5").text
    # The legacy link exactly — no campaign utm invented for a parent's invite.
    assert ('href="https://play.google.com/store/apps/details?id=com.alsaba.almorabbi'
            '&amp;referrer=ref_ENV9Z5"') in page
    headers = _token(client, "new-install-8")
    assert client.post("/api/referral/claim", json={"code": "ENV9Z5"},
                       headers=headers).json()["ok"] is True
    assert _referral_of("new-install-8")["referrer_device"] == "parent-device"


def test_a_typo_of_a_personal_code_is_not_taken_for_a_campaign(client):
    # Reproduced on the previous rule: ENV9Z (ENV9Z5 with its last character
    # dropped) answered ok:true as an English-preacher campaign, used up the
    # device's one claim, and the friend who invited it was never credited.
    conn = get_conn()
    conn.execute("INSERT INTO referral_codes (device_id, code) VALUES (?, ?)",
                 ("friend-device", "ENV9Z5"))
    conn.commit()
    conn.close()
    headers = _token(client, "typo-install")
    r = client.post("/api/referral/claim", json={"code": "ENV9Z"}, headers=headers)
    assert r.status_code == 404
    assert _referral_of("typo-install") is None           # the claim is not used up
    r = client.post("/api/referral/claim", json={"code": "ENV9Z5"}, headers=headers)
    assert r.json()["ok"] is True
    assert _referral_of("typo-install")["referrer_device"] == "friend-device"


def test_how_a_claim_was_made_is_recorded(client):
    headers = _token(client, "exact-install")
    client.post("/api/referral/claim", json={"code": "DA05"}, headers=headers)
    assert _referral_of("exact-install")["via"] == "code"

    ip = {"cf-connecting-ip": "203.0.113.60"}
    client.get("/go?ref=DA05", headers=ip)
    headers = {**_token(client, "guessed-install"), **ip}
    client.post("/api/referral/claim", json={"code": "AUTO"}, headers=headers)
    row = _referral_of("guessed-install")
    assert (row["code"], row["via"]) == ("DA05", "auto")


def test_auto_matches_a_phone_across_its_ipv6_privacy_addresses(client):
    # The click and the first launch come from the same /64 but different
    # interface ids — what IPv6 privacy addressing does between the two.
    client.get("/go?ref=CM03", headers={"cf-connecting-ip": "2001:db8:5:6::a1"})
    headers = {**_token(client, "v6-install"), "cf-connecting-ip": "2001:db8:5:6::b2"}
    r = client.post("/api/referral/claim", json={"code": "AUTO"}, headers=headers)
    assert r.json()["ok"] is True
    assert _referral_of("v6-install")["code"] == "CM03"
