"""«ادعم المربّي» — the ledger, the verifier contract, and the transparency sum.

Play itself is faked: the contract under test is what this server does with
each answer Play can give (purchased / pending / cancelled / unreachable), and
that the ledger never holds a token, an order id, or a device.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.db.init_db import get_conn
from app.main import app
from app.services import donations


class FakePlay:
    def __init__(self):
        self.purchases: dict[str, dict] = {}
        self.orders: dict[str, dict] = {}
        self.consumed: list[str] = []
        self.consume_fails = False
        self.down = False

    def get_purchase(self, product_id, token):
        if self.down:
            raise donations.VerificationUnavailable("down")
        if token not in self.purchases:
            raise donations.InvalidPurchase("play 400")
        return self.purchases[token]

    def get_order(self, order_id):
        return self.orders.get(order_id)

    def consume(self, product_id, token):
        if self.consume_fails:
            raise donations.VerificationUnavailable("consume 500")
        self.consumed.append(token)


@pytest.fixture
def play(monkeypatch):
    fake = FakePlay()
    donations.set_verifier(fake)
    monkeypatch.setenv("DONATIONS_ENABLED", "true")
    monkeypatch.delenv("COST_MONTHLY_USD", raising=False)
    monkeypatch.delenv("COST_BREAKDOWN_USD", raising=False)
    monkeypatch.delenv("DONATIONS_PLAY_FEE", raising=False)
    monkeypatch.delenv("DONATION_PRODUCT_IDS", raising=False)
    yield fake
    donations.set_verifier(None)


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def _token(client) -> str:
    r = client.post("/api/chat/sessions", json={"device_id": "donor_device"})
    assert r.status_code == 201
    return r.json()["token"]


def _purchased(order_id="GPA.1", consumption=0, ptype=None):
    p = {"purchaseState": 0, "consumptionState": consumption, "orderId": order_id}
    if ptype is not None:
        p["purchaseType"] = ptype
    return p


def _rows():
    conn = get_conn()
    try:
        return [dict(r) for r in conn.execute("SELECT * FROM donations").fetchall()]
    finally:
        conn.close()


# ── Gating ────────────────────────────────────────────────────────────────

def test_off_by_default(monkeypatch, client):
    monkeypatch.delenv("DONATIONS_ENABLED", raising=False)
    cfg = client.get("/api/app-config").json()
    assert cfg["donations_enabled"] is False
    # Additive: the old field is still there for builds that only read it.
    assert "minimum_build_number" in cfg


def test_flag_alone_is_not_enough_without_a_verifier(monkeypatch, client):
    """Never sell what cannot be verified — Play would refund it in 3 days."""
    donations.set_verifier(None)
    monkeypatch.setenv("DONATIONS_ENABLED", "true")
    monkeypatch.delenv("PLAY_SERVICE_ACCOUNT", raising=False)
    assert client.get("/api/app-config").json()["donations_enabled"] is False


def test_flag_and_verifier_enable_it(play, client):
    cfg = client.get("/api/app-config").json()
    assert cfg["donations_enabled"] is True
    assert cfg["donation_product_ids"] == list(donations.DEFAULT_PRODUCT_IDS)


def test_verify_requires_auth(play, client):
    r = client.post("/api/support/verify",
                    json={"product_id": "support_small", "purchase_token": "tok_abcdefgh"})
    assert r.status_code == 401


# ── Recording ─────────────────────────────────────────────────────────────

def test_verified_purchase_is_recorded_consumed_and_anonymous(play, client):
    play.purchases["tok_real_123"] = _purchased("GPA.1")
    play.orders["GPA.1"] = {
        "total": {"currencyCode": "EGP", "units": "120", "nanos": 0},
        "tax": {"currencyCode": "EGP", "units": "20", "nanos": 0},
    }
    r = client.post("/api/support/verify",
                    headers={"Authorization": f"Bearer {_token(client)}"},
                    json={"product_id": "support_small", "purchase_token": "tok_real_123"})
    assert r.status_code == 200, r.text
    assert r.json() == {"ok": True, "consumed": True,
                        "already_recorded": False, "pending": False}
    assert play.consumed == ["tok_real_123"]

    [row] = _rows()
    # Net of tax: 120 - 20 = 100 EGP.
    assert row["amount_micros"] == 100_000_000
    assert row["currency"] == "EGP"
    assert row["amount_source"] == "order"
    # 100 EGP × 0.0205 × (1 - 0.15) ≈ 1.74 USD.
    assert row["usd_cents"] == 174
    assert row["consumed"] == 1
    # Nothing that names the purchase, the order, or the device.
    assert row["token_hash"] == hashlib.sha256(b"tok_real_123").hexdigest()
    assert row["order_hash"] == hashlib.sha256(b"GPA.1").hexdigest()
    assert "device_id" not in row
    assert "tok_real_123" not in str(row) and "GPA.1" not in str(row)


def test_same_token_twice_is_one_row(play):
    play.purchases["tok_twice_1"] = _purchased("GPA.2")
    first = donations.record_purchase("support_small", "tok_twice_1", 1_000_000, "USD")
    second = donations.record_purchase("support_small", "tok_twice_1", 1_000_000, "USD")
    assert first["already_recorded"] is False
    assert second["already_recorded"] is True
    assert len(_rows()) == 1
    assert play.consumed == ["tok_twice_1"]  # not consumed a second time


def test_failed_consume_is_retried_on_resend(play):
    play.purchases["tok_retry_1"] = _purchased("GPA.3")
    play.consume_fails = True
    first = donations.record_purchase("support_medium", "tok_retry_1", 3_000_000, "USD")
    assert first == {"ok": True, "consumed": False,
                     "already_recorded": False, "pending": False}
    assert _rows()[0]["consumed"] == 0

    play.consume_fails = False
    second = donations.record_purchase("support_medium", "tok_retry_1", 3_000_000, "USD")
    assert second["consumed"] is True and second["already_recorded"] is True
    assert _rows()[0]["consumed"] == 1


def test_client_price_is_the_fallback_when_the_order_is_unreadable(play):
    play.purchases["tok_noorder"] = _purchased("GPA.missing")
    donations.record_purchase("support_large", "tok_noorder", 10_000_000, "usd")
    [row] = _rows()
    assert row["amount_source"] == "client"
    assert row["currency"] == "USD"
    assert row["usd_cents"] == 850  # $10 less the 15% fee


def test_pending_purchase_is_not_recorded(play, client):
    play.purchases["tok_pending"] = {"purchaseState": 2, "consumptionState": 0}
    r = client.post("/api/support/verify",
                    headers={"Authorization": f"Bearer {_token(client)}"},
                    json={"product_id": "support_small", "purchase_token": "tok_pending"})
    assert r.status_code == 202
    assert r.json()["pending"] is True
    assert _rows() == []
    assert play.consumed == []


@pytest.mark.parametrize("state", [1, None])
def test_cancelled_or_malformed_purchase_is_rejected(play, client, state):
    play.purchases["tok_bad_state"] = {"purchaseState": state}
    r = client.post("/api/support/verify",
                    headers={"Authorization": f"Bearer {_token(client)}"},
                    json={"product_id": "support_small", "purchase_token": "tok_bad_state"})
    assert r.status_code == 400
    assert _rows() == []


def test_unknown_token_and_unknown_product_are_rejected(play, client):
    auth = {"Authorization": f"Bearer {_token(client)}"}
    r = client.post("/api/support/verify", headers=auth,
                    json={"product_id": "support_small", "purchase_token": "tok_forged_x"})
    assert r.status_code == 400 and r.json()["detail"] == "invalid_purchase"
    r = client.post("/api/support/verify", headers=auth,
                    json={"product_id": "premium_unlock", "purchase_token": "tok_forged_x"})
    assert r.status_code == 400 and r.json()["detail"] == "unknown_product"


def test_play_unreachable_is_retryable_not_a_rejection(play, client):
    play.down = True
    r = client.post("/api/support/verify",
                    headers={"Authorization": f"Bearer {_token(client)}"},
                    json={"product_id": "support_small", "purchase_token": "tok_later_1"})
    assert r.status_code == 503
    assert _rows() == []


# ── Transparency ──────────────────────────────────────────────────────────

def test_transparency_hides_the_percentage_without_a_cost(play, client):
    play.purchases["tok_t1"] = _purchased("GPA.t1")
    donations.record_purchase("support_small", "tok_t1", 1_000_000, "USD")
    body = client.get("/api/support/transparency").json()
    assert body["cost_usd"] is None
    assert body["covered_pct"] is None
    assert body["covered_usd"] == 0.85
    assert body["supports"] == 1
    assert body["breakdown"] == []


def test_transparency_percentage_and_breakdown(play, client, monkeypatch):
    monkeypatch.setenv("COST_MONTHLY_USD", "40")
    monkeypatch.setenv("COST_BREAKDOWN_USD", "server=12, ai=25 ,other=3,BAD KEY=9,x=nope")
    for i in range(4):
        play.purchases[f"tok_p{i}"] = _purchased(f"GPA.p{i}")
        donations.record_purchase("support_large", f"tok_p{i}", 10_000_000, "USD")
    body = client.get("/api/support/transparency").json()
    assert body["cost_usd"] == 40.0
    assert body["covered_usd"] == 34.0          # 4 × $10 × 0.85
    assert body["covered_pct"] == 85
    assert body["breakdown"] == [{"key": "server", "usd": 12.0},
                                 {"key": "ai", "usd": 25.0},
                                 {"key": "other", "usd": 3.0}]


def test_test_purchases_are_recorded_but_never_counted(play, client, monkeypatch):
    monkeypatch.setenv("COST_MONTHLY_USD", "10")
    play.purchases["tok_tester"] = _purchased("GPA.test", ptype=0)
    donations.record_purchase("support_small", "tok_tester", 5_000_000, "USD")
    assert _rows()[0]["is_test"] == 1
    body = client.get("/api/support/transparency").json()
    assert body["covered_usd"] == 0 and body["covered_pct"] == 0
    assert body["supports"] == 0


def test_unknown_currency_is_reported_not_guessed(play):
    play.purchases["tok_xyz"] = _purchased("GPA.xyz")
    donations.record_purchase("support_small", "tok_xyz", 5_000_000, "XYZ")
    assert _rows()[0]["usd_cents"] is None
    body = donations.transparency()
    assert body["unpriced"] == 1 and body["covered_usd"] == 0


def test_only_this_month_counts(play):
    play.purchases["tok_old"] = _purchased("GPA.old")
    donations.record_purchase("support_small", "tok_old", 1_000_000, "USD")
    conn = get_conn()
    conn.execute("UPDATE donations SET created_at = '2020-01-15 10:00:00'")
    conn.commit()
    conn.close()
    body = donations.transparency(datetime(2026, 10, 4, tzinfo=timezone.utc))
    assert body["month"] == "2026-10"
    assert body["covered_usd"] == 0 and body["supports"] == 0


def test_fx_override_and_fee(monkeypatch):
    monkeypatch.setenv("DONATIONS_FX_USD_JSON", '{"egp": 0.02, "bad": -1}')
    monkeypatch.setenv("DONATIONS_PLAY_FEE", "0.30")
    assert donations.to_usd_cents(100_000_000, "EGP") == 140  # 100 × 0.02 × 0.7
    assert donations.to_usd_cents(1_000_000, "BAD") is None
    monkeypatch.setenv("DONATIONS_PLAY_FEE", "7")  # nonsense → default 15%
    assert donations.to_usd_cents(1_000_000, "USD") == 85


# ── The real verifier's mapping of Play's HTTP answers ─────────────────────

class _Resp:
    def __init__(self, status, body=None):
        self.status_code = status
        self._body = body or {}

    def json(self):
        return self._body


class _Session:
    def __init__(self, answers):
        self.answers = answers
        self.calls = []

    def request(self, method, url, timeout):
        self.calls.append((method, url))
        return self.answers.pop(0)


def _google(answers):
    v = object.__new__(donations.GooglePlayVerifier)
    v._session = _Session(answers)
    v._app = donations.GooglePlayVerifier._BASE + "/com.alsaba.almorabbi"
    return v


def test_google_verifier_urls_and_status_mapping():
    v = _google([_Resp(200, {"purchaseState": 0}), _Resp(204), _Resp(404)])
    assert v.get_purchase("support_small", "a.b/c+d") == {"purchaseState": 0}
    v.consume("support_small", "a.b/c+d")
    assert v.get_order("GPA.1") is None
    (m1, u1), (m2, u2), (_, u3) = v._session.calls
    assert m1 == "GET" and u1.endswith(
        "/com.alsaba.almorabbi/purchases/products/support_small/tokens/a.b%2Fc%2Bd")
    assert m2 == "POST" and u2.endswith("/tokens/a.b%2Fc%2Bd:consume")
    assert u3.endswith("/orders/GPA.1")


@pytest.mark.parametrize("status,exc", [
    (400, donations.InvalidPurchase), (410, donations.InvalidPurchase),
    (401, donations.VerificationUnavailable), (403, donations.VerificationUnavailable),
    (429, donations.VerificationUnavailable), (503, donations.VerificationUnavailable),
])
def test_google_verifier_separates_rejection_from_outage(status, exc):
    with pytest.raises(exc):
        _google([_Resp(status)]).get_purchase("support_small", "tok")
