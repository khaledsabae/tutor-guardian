"""«ادعم المربّي» — the ledger, the verifier contract, and the transparency sum.

Play itself is faked: the contract under test is what this server does with
each answer Play can give (purchased / pending / cancelled / unreachable /
refused), and that the ledger never holds a token, an order id, or a device.
Where the real GooglePlayVerifier is under test, only its HTTP session is
replaced — the credentials are a real service-account JSON with a freshly
generated key, parsed by google-auth exactly as in production.
"""
from __future__ import annotations

import functools
import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest
import requests
from fastapi.testclient import TestClient

from app.db.init_db import get_conn
from app.main import app
from app.middleware import rate_limit
from app.services import donations

REPO_ROOT = Path(__file__).resolve().parents[2]


class FakePlay:
    def __init__(self):
        self.purchases: dict[str, dict] = {}
        self.orders: dict[str, dict] = {}
        self.consumed: list[str] = []
        self.voided: set[str] = set()
        self.voided_calls = 0
        self.consume_fails = False
        self.down = False

    def get_purchase(self, product_id, token):
        if self.down:
            raise donations.VerificationUnavailable("down")
        if token not in self.purchases:
            raise donations.InvalidPurchase("http 400")
        return self.purchases[token]

    def get_order(self, order_id):
        return self.orders.get(order_id)

    def consume(self, product_id, token):
        if self.consume_fails:
            raise donations.VerificationUnavailable("consume http 500")
        self.consumed.append(token)

    def voided_tokens(self, start_ms):
        self.voided_calls += 1
        return set(self.voided)


@pytest.fixture
def play(monkeypatch):
    """Donations on, with a fake Play behind the process's one verifier."""
    fake = FakePlay()
    monkeypatch.setenv("DONATIONS_ENABLED", "true")
    monkeypatch.setattr(donations, "_credentials", lambda: object())
    monkeypatch.setattr(donations, "_verifier", lambda: fake)
    for name in ("COST_MONTHLY_USD", "COST_BREAKDOWN_USD", "DONATIONS_PLAY_FEE",
                 "DONATION_PRODUCT_IDS", "DONATIONS_FX_USD_JSON"):
        monkeypatch.delenv(name, raising=False)
    return fake


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def _token(client, device="donor_device") -> str:
    r = client.post("/api/chat/sessions", json={"device_id": device})
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


@functools.lru_cache(maxsize=1)
def _service_account_info() -> dict:
    """A real service-account JSON shape with a real RSA key — no network use."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption()).decode()
    return {
        "type": "service_account", "project_id": "tg-support-test",
        "private_key_id": "k1", "private_key": pem,
        "client_email": "support-verify@tg-support-test.iam.gserviceaccount.com",
        "client_id": "1", "token_uri": "https://oauth2.googleapis.com/token",
    }


def _write_service_account(tmp_path: Path) -> Path:
    path = tmp_path / "play_service_account.json"
    path.write_text(json.dumps(_service_account_info()), encoding="utf-8")
    return path


class _Resp:
    def __init__(self, status, body=None, raw=None):
        self.status_code = status
        self._body = body
        self._raw = raw

    def json(self):
        if self._raw is not None:
            return json.loads(self._raw)
        return self._body if self._body is not None else {}


class _RoutedSession:
    """Answers like Play for the four endpoints the verifier calls."""

    def __init__(self, purchase=None, consume_status=204, order=None):
        self.purchase = purchase or {"purchaseState": 0, "consumptionState": 0,
                                     "orderId": "GPA.routed"}
        self.consume_status = consume_status
        self.order = order
        self.calls: list[tuple[str, str]] = []

    def request(self, method, url, params=None, timeout=None):
        self.calls.append((method, url))
        if url.endswith(":consume"):
            return _Resp(self.consume_status)
        if "/orders/" in url:
            return _Resp(200, self.order) if self.order else _Resp(404, {})
        if url.endswith("/voidedpurchases"):
            return _Resp(200, {})
        return _Resp(200, self.purchase)


def _google(session) -> donations.GooglePlayVerifier:
    v = donations.GooglePlayVerifier(object(), "com.alsaba.almorabbi")
    v._session = lambda: session  # the only seam: no real HTTP
    return v


# ── Gating ────────────────────────────────────────────────────────────────

def test_off_by_default(monkeypatch, client):
    monkeypatch.delenv("DONATIONS_ENABLED", raising=False)
    cfg = client.get("/api/app-config").json()
    assert cfg["donations_enabled"] is False
    # Additive: the old field is still there for builds that only read it.
    assert "minimum_build_number" in cfg


def test_flag_alone_is_not_enough_without_a_service_account(monkeypatch, tmp_path, client):
    """Never sell what cannot be verified — Play would refund it in 3 days."""
    monkeypatch.setenv("DONATIONS_ENABLED", "true")
    monkeypatch.setenv("PLAY_SERVICE_ACCOUNT", str(tmp_path / "missing.json"))
    assert client.get("/api/app-config").json()["donations_enabled"] is False


@pytest.mark.parametrize("content", ["{not json", "[1, 2]", b"\xff\xfe\x00binary"])
def test_flag_with_an_unusable_service_account_stays_off(monkeypatch, tmp_path, content):
    """The file existing is not enough: it must parse into credentials (item 2)."""
    path = tmp_path / "play_service_account.json"
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_text(content, encoding="utf-8")
    monkeypatch.setenv("DONATIONS_ENABLED", "true")
    monkeypatch.setenv("PLAY_SERVICE_ACCOUNT", str(path))
    assert donations.is_enabled() is False


def test_unreadable_service_account_stays_off(monkeypatch, tmp_path):
    """The production failure mode: a 0600 root:root file in the bind mount."""
    path = _write_service_account(tmp_path)
    path.chmod(0o000)
    if os.access(path, os.R_OK):
        pytest.skip("running as root — permission bits are not enforced")
    monkeypatch.setenv("DONATIONS_ENABLED", "true")
    monkeypatch.setenv("PLAY_SERVICE_ACCOUNT", str(path))
    assert donations.is_enabled() is False


def test_a_real_service_account_enables_it(monkeypatch, tmp_path, client):
    monkeypatch.setenv("DONATIONS_ENABLED", "true")
    monkeypatch.setenv("PLAY_SERVICE_ACCOUNT", str(_write_service_account(tmp_path)))
    cfg = client.get("/api/app-config").json()
    assert cfg["donations_enabled"] is True
    assert cfg["donation_product_ids"] == list(donations.DEFAULT_PRODUCT_IDS)


def test_default_service_account_path_is_the_mounted_secrets_dir(monkeypatch):
    """Item 9: /app/backend/secrets is what production bind-mounts."""
    monkeypatch.delenv("PLAY_SERVICE_ACCOUNT", raising=False)
    path = donations.service_account_path()
    assert path.name == "play_service_account.json"
    assert path.parent.name == "secrets" and path.parent.parent.name == "backend"


def test_env_example_asks_for_a_dedicated_least_privilege_account():
    """Item 9: the upload account can push releases; it must not be reused."""
    text = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")
    section = text[text.index("ادعم المربّي"):]
    assert "DEDICATED" in section
    assert "View financial data" in section and "Manage orders" in section
    assert "/app/backend/secrets/play_service_account.json" in section
    assert "OPERATIONS_LOG" in section


def test_app_config_survives_a_secret_it_cannot_even_stat(monkeypatch, caplog, client):
    """Item 6: /api/app-config is the force-update gate for every build.

    A directory the container user cannot search makes `is_file()` raise
    PermissionError. That used to propagate into the gate: a 500 on every
    launch. It must answer, say off, and log once — not once per launch.
    """
    monkeypatch.setenv("DONATIONS_ENABLED", "true")
    monkeypatch.setenv("PLAY_SERVICE_ACCOUNT", "/root/locked/play_service_account.json")
    real_is_file = Path.is_file

    def denied(self):
        if "play_service_account" in str(self):
            raise PermissionError(13, "Permission denied")
        return real_is_file(self)

    monkeypatch.setattr(Path, "is_file", denied)
    caplog.set_level(logging.WARNING, logger="app.services.donations")
    for _ in range(3):
        r = client.get("/api/app-config")
        assert r.status_code == 200
        assert r.json()["donations_enabled"] is False
    assert client.get("/api/support/transparency").status_code == 200
    unusable = [r for r in caplog.records if "is unusable" in r.getMessage()]
    assert len(unusable) == 1
    assert "PermissionError" in unusable[0].getMessage()


class _Clock:
    """A monotonic clock the test can move."""

    def __init__(self):
        self.now = 1_000.0

    def __call__(self):
        return self.now


def _messages(caplog, needle):
    return [r.getMessage() for r in caplog.records if needle in r.getMessage()]


def test_sale_path_403_hides_support_for_a_bounded_window(monkeypatch, caplog):
    """Item 1 (delta): closed by the sale path, reopened by the clock.

    A refusal on reading a purchase hides support for REPROBE_SECONDS, then
    the gate reopens and the next verify is the probe; a second refusal in a
    row doubles the window; a success ends the state. Every change is logged.
    """
    monkeypatch.setenv("DONATIONS_ENABLED", "true")
    monkeypatch.setattr(donations, "_credentials", lambda: object())
    clock = _Clock()
    monkeypatch.setattr(donations, "_clock", clock)
    status = {"code": 403}

    class Play:
        def request(self, method, url, params=None, timeout=None):
            return _Resp(status["code"], {"purchaseState": 0})

    verifier = _google(Play())
    caplog.set_level(logging.INFO, logger="app.services.donations")

    with pytest.raises(donations.VerificationUnavailable):
        verifier.get_purchase("support_small", "tok_refused_1")
    assert donations.is_enabled() is False
    with pytest.raises(donations.VerificationUnavailable):
        donations._verifier()  # no Play call while closed

    clock.now += donations.REPROBE_SECONDS - 1
    assert donations.is_enabled() is False
    clock.now += 2
    assert donations.is_enabled() is True  # reopened: the next verify probes
    assert len(_messages(caplog, "refusal window over")) == 1

    with pytest.raises(donations.VerificationUnavailable):
        verifier.get_purchase("support_small", "tok_refused_2")
    clock.now += donations.REPROBE_SECONDS + 1
    assert donations.is_enabled() is False  # doubled the second time
    clock.now += donations.REPROBE_SECONDS
    assert donations.is_enabled() is True

    status["code"] = 200
    verifier.get_purchase("support_small", "tok_works_3")
    assert donations.is_enabled() is True
    closed = _messages(caplog, "refused the support credentials")
    assert len(closed) == 2
    assert "for 12 min (refusal 1" in closed[0] and "for 24 min (refusal 2" in closed[1]
    assert len(_messages(caplog, "support restored")) == 1


def test_a_401_from_the_public_page_never_closes_the_gate(monkeypatch, tmp_path):
    """Item 1 (delta), from the review's probe: the voided-purchases read runs
    off an anonymous GET; its 401 must not take support down for the process."""
    sa = _write_service_account(tmp_path)
    monkeypatch.setenv("DONATIONS_ENABLED", "true")
    monkeypatch.setenv("PLAY_SERVICE_ACCOUNT", str(sa))

    class Session(_RoutedSession):
        voided_status = 401  # e.g. permission not yet propagated

        def request(self, method, url, params=None, timeout=None):
            if url.endswith("/voidedpurchases"):
                self.calls.append((method, url))
                return _Resp(self.voided_status, {})
            if "/orders/" in url:
                self.calls.append((method, url))
                return _Resp(403, {})  # orders permission missing: figures only
            return super().request(method, url, params=params, timeout=timeout)

    session = Session(purchase={"purchaseState": 0, "consumptionState": 0,
                                "orderId": "GPA.probe"})
    monkeypatch.setattr(donations.GooglePlayVerifier, "_session", lambda self: session)

    with TestClient(app) as c:
        assert c.get("/api/app-config").json()["donations_enabled"] is True
        assert c.get("/api/support/transparency").status_code == 200
        donations._reconciler.join(timeout=10)
        assert any(u.endswith("/voidedpurchases") for _, u in session.calls)
        assert c.get("/api/app-config").json()["donations_enabled"] is True
        r = c.post("/api/support/verify",
                   json={"product_id": "support_small", "purchase_token": "tok_valid_123"},
                   headers={"Authorization": f"Bearer {_token(c)}"})
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is True
    assert donations.credentials_rejected() is False


@pytest.mark.parametrize("retryable,closes", [(False, True), (True, False)])
def test_a_revoked_key_closes_the_gate_and_says_so(monkeypatch, tmp_path, caplog,
                                                   retryable, closes):
    """Item 2 (delta), from the review's probe: a revoked key or a disabled
    account fails at token mint — a RefreshError, not a 401 — and used to be
    a silent 503 forever with the gate open."""
    from google.auth.exceptions import RefreshError

    class Dead:
        def request(self, method, url, params=None, timeout=None):
            raise RefreshError("invalid_grant: Invalid JWT Signature.",
                               retryable=retryable)

    sa = _write_service_account(tmp_path)
    monkeypatch.setenv("DONATIONS_ENABLED", "true")
    monkeypatch.setenv("PLAY_SERVICE_ACCOUNT", str(sa))
    monkeypatch.setattr(donations.GooglePlayVerifier, "_session", lambda self: Dead())
    caplog.set_level(logging.INFO, logger="app.services.donations")
    with TestClient(app) as c:
        bearer = _token(c)
        codes = [c.post("/api/support/verify",
                        json={"product_id": "support_small",
                              "purchase_token": f"tok_revoked_{i:03d}"},
                        headers={"Authorization": f"Bearer {bearer}"}).status_code
                 for i in range(3)]
        enabled = c.get("/api/app-config").json()["donations_enabled"]
    assert codes == [503, 503, 503]
    refused = _messages(caplog, "refused the support credentials (RefreshError)")
    if closes:
        assert enabled is False
        assert len(refused) == 1  # once, not once per request
    else:
        # A retryable refresh failure is an outage, not a revoked key.
        assert enabled is True and refused == []


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
    # No developer revenue on this order: total − tax, less the 15% fee.
    assert row["amount_micros"] == 100_000_000
    assert row["currency"] == "EGP"
    assert row["amount_source"] == "order_total"
    assert row["usd_cents"] == 174  # 100 × 0.0205 × 0.85
    assert row["consumed"] == 1
    assert row["purchase_type"] is None
    # Nothing that names the purchase, the order, or the device.
    assert row["token_hash"] == hashlib.sha256(b"tok_real_123").hexdigest()
    assert row["order_hash"] == hashlib.sha256(b"GPA.1").hexdigest()
    assert "device_id" not in row
    assert "tok_real_123" not in str(row) and "GPA.1" not in str(row)


def test_developer_revenue_is_used_when_play_reports_it(play):
    """Item 20: Play's own net figure beats the fee approximation."""
    play.purchases["tok_rev_1"] = _purchased("GPA.rev")
    play.orders["GPA.rev"] = {
        "total": {"currencyCode": "EGP", "units": "120"},
        "tax": {"currencyCode": "EGP", "units": "20"},
        "developerRevenueInBuyerCurrency": {"currencyCode": "EGP", "units": "80"},
    }
    donations.record_purchase("support_small", "tok_rev_1")
    [row] = _rows()
    assert row["amount_source"] == "order_revenue"
    assert row["amount_micros"] == 80_000_000
    assert row["usd_cents"] == 164  # 80 × 0.0205 — no second fee deduction


def test_same_token_twice_is_one_row(play):
    play.purchases["tok_twice_1"] = _purchased("GPA.2")
    first = donations.record_purchase("support_small", "tok_twice_1")
    second = donations.record_purchase("support_small", "tok_twice_1")
    assert first["already_recorded"] is False
    assert second["already_recorded"] is True
    assert len(_rows()) == 1
    assert play.consumed == ["tok_twice_1"]  # not consumed a second time


def test_a_recorded_token_never_builds_a_verifier_or_calls_play(play, monkeypatch):
    """Item 8: the ledger is asked first; Play only for what it has not seen."""
    play.purchases["tok_seen_1"] = _purchased("GPA.seen")
    donations.record_purchase("support_small", "tok_seen_1")

    def no_verifier():
        raise AssertionError("a verifier was built for a recorded token")

    monkeypatch.setattr(donations, "_verifier", no_verifier)
    res = donations.record_purchase("support_small", "tok_seen_1")
    assert res == {"ok": True, "consumed": True,
                   "already_recorded": True, "pending": False}


def test_a_removed_product_is_still_recognised_by_its_token(play, monkeypatch, client):
    """Item 17: the token is looked up before the allowlist."""
    play.purchases["tok_old_product"] = _purchased("GPA.old")
    play.consume_fails = True
    donations.record_purchase("support_small", "tok_old_product")
    monkeypatch.setenv("DONATION_PRODUCT_IDS", "support_tiny,support_huge")
    play.consume_fails = False
    r = client.post("/api/support/verify",
                    headers={"Authorization": f"Bearer {_token(client)}"},
                    json={"product_id": "support_small",
                          "purchase_token": "tok_old_product"})
    assert r.status_code == 200, r.text
    assert r.json()["already_recorded"] is True
    assert r.json()["consumed"] is True  # and the pending consume went through
    assert play.consumed == ["tok_old_product"]


def test_failed_consume_is_retried_on_resend(play):
    play.purchases["tok_retry_1"] = _purchased("GPA.3")
    play.consume_fails = True
    first = donations.record_purchase("support_medium", "tok_retry_1")
    assert first == {"ok": True, "consumed": False,
                     "already_recorded": False, "pending": False}
    assert _rows()[0]["consumed"] == 0

    play.consume_fails = False
    second = donations.record_purchase("support_medium", "tok_retry_1")
    assert second["consumed"] is True and second["already_recorded"] is True
    assert _rows()[0]["consumed"] == 1


def test_concurrent_requests_for_one_token_consume_it_once(play):
    """Item 18: the loser of the insert race reports, and consumes nothing."""
    play.purchases["tok_race_1"] = _purchased("GPA.race")
    real_get = play.get_purchase

    def get_while_the_winner_inserts(product_id, token):
        result = real_get(product_id, token)
        conn = get_conn()
        conn.execute("INSERT INTO donations (token_hash, product_id, consumed) "
                     "VALUES (?, ?, 1)",
                     (hashlib.sha256(token.encode()).hexdigest(), product_id))
        conn.commit()
        conn.close()
        return result

    play.get_purchase = get_while_the_winner_inserts
    res = donations.record_purchase("support_small", "tok_race_1")
    assert res == {"ok": True, "consumed": True,
                   "already_recorded": True, "pending": False}
    assert play.consumed == []
    assert len(_rows()) == 1


def test_a_real_purchase_is_never_priced_from_the_client(play):
    """Item 5: without a readable order the row is stored unpriced."""
    play.purchases["tok_noorder"] = _purchased("GPA.missing")
    donations.record_purchase("support_large", "tok_noorder", 10_000_000_000, "USD")
    [row] = _rows()
    assert row["amount_micros"] is None and row["usd_cents"] is None
    assert row["amount_source"] == "none"
    assert row["reprice_order_id"] == "GPA.missing"  # priced later from Play, not the client
    body = donations.transparency()
    assert body["covered_usd"] == 0
    assert body["unpriced"] == 1 and body["supports"] == 1


def test_a_test_purchase_keeps_the_client_price_and_is_never_counted(play, monkeypatch):
    monkeypatch.setenv("COST_MONTHLY_USD", "10")
    play.purchases["tok_tester"] = _purchased("GPA.test", ptype=0)
    donations.record_purchase("support_small", "tok_tester", 5_000_000, "usd")
    [row] = _rows()
    assert row["purchase_type"] == 0
    assert row["amount_source"] == "client" and row["currency"] == "USD"
    body = donations.transparency()
    assert body["covered_usd"] == 0 and body["covered_pct"] == 0
    assert body["supports"] == 0


@pytest.mark.parametrize("ptype", [1, 2])
def test_promo_and_rewarded_purchases_are_not_money(play, ptype):
    """Item 5: a promo code or a rewarded ad paid nothing in."""
    play.purchases[f"tok_free_{ptype}"] = _purchased(f"GPA.free{ptype}", ptype=ptype)
    play.orders[f"GPA.free{ptype}"] = {"total": {"currencyCode": "USD", "units": "10"}}
    donations.record_purchase("support_small", f"tok_free_{ptype}", 10_000_000, "USD")
    assert _rows()[0]["purchase_type"] == ptype
    body = donations.transparency()
    assert body["covered_usd"] == 0 and body["supports"] == 0


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


@pytest.mark.parametrize("error", [ValueError("Expecting value: line 1"),
                                   KeyError("purchaseState"), TypeError("x")])
def test_unexpected_errors_are_a_retryable_5xx_never_unknown_product(
        play, client, caplog, error):
    """Item 3: a bad reply or a config slip must not tell the app "bad purchase".

    A broad `except ValueError` used to turn Play's malformed JSON into
    400 unknown_product, and the app stops retrying a 400.
    """
    def broken(product_id, token):
        raise error

    play.get_purchase = broken
    caplog.set_level(logging.ERROR, logger="app.routers.support")
    r = client.post("/api/support/verify",
                    headers={"Authorization": f"Bearer {_token(client)}"},
                    json={"product_id": "support_small", "purchase_token": "tok_odd_1"})
    assert r.status_code == 503
    assert r.json()["detail"] == "verification_unavailable"
    assert type(error).__name__ in caplog.text


def test_play_returning_non_json_is_retryable(monkeypatch, client):
    monkeypatch.setattr(donations, "_verifier", lambda: _google(
        type("S", (), {"request": lambda self, *a, **k: _Resp(200, raw="<html>")})()))
    r = client.post("/api/support/verify",
                    headers={"Authorization": f"Bearer {_token(client)}"},
                    json={"product_id": "support_small", "purchase_token": "tok_html_1"})
    assert r.status_code == 503


def test_transport_errors_never_put_the_token_in_logs(monkeypatch, caplog, client):
    """Item 7: a requests error quotes the URL, and the URL holds the token."""
    token = "SECRETTOKEN_never_in_logs_42"

    class Boom:
        def request(self, method, url, params=None, timeout=None):
            raise requests.exceptions.ConnectionError(
                "HTTPSConnectionPool(host='androidpublisher.googleapis.com', "
                f"port=443): Max retries exceeded with url: {url}")

    verifier = _google(Boom())
    with pytest.raises(donations.VerificationUnavailable) as err:
        verifier.get_purchase("support_small", token)
    assert token not in str(err.value)
    assert err.value.__cause__ is None and err.value.__suppress_context__

    # And through the paths that log: a 503 from verify, and a failed consume
    # of an already-recorded purchase.
    caplog.set_level(logging.DEBUG)
    monkeypatch.setattr(donations, "_verifier", lambda: verifier)
    r = client.post("/api/support/verify",
                    headers={"Authorization": f"Bearer {_token(client)}"},
                    json={"product_id": "support_small", "purchase_token": token})
    assert r.status_code == 503
    conn = get_conn()
    conn.execute("INSERT INTO donations (token_hash, product_id) VALUES (?, ?)",
                 (hashlib.sha256(token.encode()).hexdigest(), "support_small"))
    conn.commit()
    conn.close()
    assert donations.record_purchase("support_small", token)["consumed"] is False
    assert "consume failed (ConnectionError)" in caplog.text
    assert token not in caplog.text


def test_credentials_and_verifier_are_built_once_per_process(monkeypatch, tmp_path):
    """Item 8: one parse of the key, one verifier — not one per purchase."""
    monkeypatch.setenv("DONATIONS_ENABLED", "true")
    monkeypatch.setenv("PLAY_SERVICE_ACCOUNT", str(_write_service_account(tmp_path)))
    reads = []
    real_read = donations.read_service_account

    def counting_read(path, **kw):
        reads.append(path)
        return real_read(path, **kw)

    monkeypatch.setattr(donations, "read_service_account", counting_read)
    session = _RoutedSession()
    monkeypatch.setattr(donations.GooglePlayVerifier, "_session", lambda self: session)

    assert donations.is_enabled() is True
    for i in range(3):
        res = donations.record_purchase("support_small", f"tok_once_{i}")
        assert res["ok"] is True and res["consumed"] is True
    assert len(reads) == 1
    assert donations._verifier() is donations._verifier()
    assert sum(1 for m, _ in session.calls if m == "POST") == 3


def _verify_status(c, bearer, token="tok_rl_unknown"):
    return c.post("/api/support/verify",
                  headers={"Authorization": f"Bearer {bearer}"},
                  json={"product_id": "support_small", "purchase_token": token}
                  ).status_code


def test_verify_is_rate_limited_per_address(play, monkeypatch):
    """Item 8: six devices behind one address share one small budget."""
    monkeypatch.setattr(rate_limit, "_SUPPORT_VERIFY_LIMIT", 5)
    with TestClient(app, client=("198.51.100.17", 40000)) as c:
        bearers = [_token(c, f"rl_ip_dev_{i}") for i in range(6)]
        codes = [_verify_status(c, b) for b in bearers]
    assert 429 not in codes[:5]
    assert codes[5] == 429


def test_verify_is_rate_limited_per_device(play, monkeypatch):
    """Item 8: one device cannot buy a fresh budget by changing address."""
    monkeypatch.setattr(rate_limit, "_SUPPORT_VERIFY_LIMIT", 5)
    with TestClient(app, client=("198.51.100.30", 40000)) as c:
        bearer = _token(c, "rl_one_device")
    codes = []
    for i in range(6):
        with TestClient(app, client=(f"198.51.100.{40 + i}", 40000)) as c:
            codes.append(_verify_status(c, bearer))
    assert 429 not in codes[:5]
    assert codes[5] == 429


# ── Transparency ──────────────────────────────────────────────────────────

def test_transparency_payload_is_aggregates_only(play, client):
    """Item 23: no flag echo, no constant fields — just the figures."""
    body = client.get("/api/support/transparency").json()
    assert set(body) == {"month", "cost_usd", "covered_usd", "covered_pct",
                         "supports", "unpriced", "breakdown"}


def test_transparency_hides_the_percentage_without_a_cost(play, client):
    play.purchases["tok_t1"] = _purchased("GPA.t1")
    play.orders["GPA.t1"] = {"total": {"currencyCode": "USD", "units": "1"}}
    donations.record_purchase("support_small", "tok_t1")
    body = client.get("/api/support/transparency").json()
    assert body["cost_usd"] is None
    assert body["covered_pct"] is None
    assert body["covered_usd"] == 0.85
    assert body["supports"] == 1
    assert body["breakdown"] == []


def test_transparency_percentage_and_breakdown(play, client, monkeypatch):
    monkeypatch.setenv("COST_MONTHLY_USD", "40")
    # hosting is not a line the app can label — it would render as a second
    # «أخرى» (item 23).
    monkeypatch.setenv("COST_BREAKDOWN_USD",
                       "server=12, ai=25 ,other=3,hosting=5,BAD KEY=9,x=nope")
    for i in range(4):
        play.purchases[f"tok_p{i}"] = _purchased(f"GPA.p{i}")
        play.orders[f"GPA.p{i}"] = {"total": {"currencyCode": "USD", "units": "10"}}
        donations.record_purchase("support_large", f"tok_p{i}")
    body = client.get("/api/support/transparency").json()
    assert body["cost_usd"] == 40.0
    assert body["covered_usd"] == 34.0          # 4 × $10 × 0.85
    assert body["covered_pct"] == 85
    assert body["breakdown"] == [{"key": "server", "usd": 12.0},
                                 {"key": "ai", "usd": 25.0},
                                 {"key": "other", "usd": 3.0}]


def test_unknown_currency_is_reported_not_guessed(play):
    play.purchases["tok_xyz"] = _purchased("GPA.xyz")
    play.orders["GPA.xyz"] = {"total": {"currencyCode": "XYZ", "units": "5"}}
    donations.record_purchase("support_small", "tok_xyz")
    assert _rows()[0]["usd_cents"] is None
    body = donations.transparency()
    assert body["unpriced"] == 1 and body["covered_usd"] == 0


def test_only_this_month_counts(play):
    play.purchases["tok_old"] = _purchased("GPA.old")
    play.orders["GPA.old"] = {"total": {"currencyCode": "USD", "units": "1"}}
    donations.record_purchase("support_small", "tok_old")
    conn = get_conn()
    conn.execute("UPDATE donations SET created_at = '2026-09-30 23:59:59'")
    conn.commit()
    conn.close()
    body = donations.transparency(datetime(2026, 10, 4, tzinfo=timezone.utc))
    assert body["month"] == "2026-10"
    assert body["covered_usd"] == 0 and body["supports"] == 0
    september = donations.transparency(datetime(2026, 9, 30, 23, tzinfo=timezone.utc))
    assert september["supports"] == 1


def test_month_totals_use_the_created_at_index():
    """Item 21: a range on created_at, not substr() — so the index is used."""
    conn = get_conn()
    try:
        plan = " ".join(str(tuple(r)) for r in conn.execute(
            "EXPLAIN QUERY PLAN " + donations.MONTH_TOTALS_SQL,
            ("2026-10-01 00:00:00", "2026-11-01 00:00:00")).fetchall())
    finally:
        conn.close()
    assert "ix_donations_created" in plan


def test_voided_purchases_stop_counting(play, monkeypatch):
    """Item 22: refunds and chargebacks are reconciled — no cron."""
    monkeypatch.setenv("COST_MONTHLY_USD", "10")
    for token in ("tok_keep", "tok_refunded"):
        play.purchases[token] = _purchased(f"GPA.{token}")
        play.orders[f"GPA.{token}"] = {"total": {"currencyCode": "USD", "units": "5"}}
        donations.record_purchase("support_medium", token)
    play.voided = {"tok_refunded"}

    assert donations.run_reconciliation() is True
    body = donations.transparency()
    assert body["supports"] == 1
    assert body["covered_usd"] == 4.25  # one $5 purchase, less the fee
    assert {r["token_hash"]: r["voided"] for r in _rows()}[
        hashlib.sha256(b"tok_refunded").hexdigest()] == 1


def test_the_public_page_never_waits_on_play(play, monkeypatch):
    """Item 5 (delta): the check runs in the background, single-flight; the
    GET serves the last computed values and returns while Play is slow."""
    import threading
    import time as _time

    release = threading.Event()
    entered = threading.Event()
    calls = []

    def slow_voided(start_ms):
        calls.append(start_ms)
        entered.set()
        release.wait(10)
        return {"tok_refunded"}

    play.voided_tokens = slow_voided
    for token in ("tok_keep", "tok_refunded"):
        play.purchases[token] = _purchased(f"GPA.{token}")
        play.orders[f"GPA.{token}"] = {"total": {"currencyCode": "USD", "units": "5"}}
        donations.record_purchase("support_medium", token)

    started = _time.monotonic()
    first = donations.transparency()
    assert _time.monotonic() - started < 2  # did not wait on Play
    assert entered.wait(5)                   # …but the check did start
    assert first["supports"] == 2            # last computed values: no voids yet

    # While it runs, more reads neither wait nor start a second one.
    donations._last_reconcile_start = None   # even if one were due
    donations.transparency()
    assert donations.run_reconciliation() is False  # single-flight
    assert len(calls) == 1

    release.set()
    donations._reconciler.join(timeout=10)
    assert donations.transparency()["supports"] == 1  # the void, once computed


def test_reconciliation_is_due_at_most_every_six_hours(play, monkeypatch):
    clock = _Clock()
    monkeypatch.setattr(donations, "_clock", clock)
    calls = []
    play.voided_tokens = lambda start_ms: calls.append(start_ms) or set()
    for _ in range(3):
        donations.transparency()
        donations._reconciler.join(timeout=10)
    assert len(calls) == 1
    clock.now += donations.RECONCILE_EVERY_SECONDS + 1
    donations.transparency()
    donations._reconciler.join(timeout=10)
    assert len(calls) == 2


def test_an_unreadable_order_is_logged_and_priced_later(play, caplog, monkeypatch):
    """Item 4 (delta): unpriced is a waiting state, not a final one."""
    monkeypatch.setenv("COST_MONTHLY_USD", "10")
    play.purchases["tok_late_order"] = _purchased("GPA.late")  # order not readable yet
    caplog.set_level(logging.WARNING, logger="app.services.donations")
    donations.record_purchase("support_small", "tok_late_order")
    assert _messages(caplog, "recorded unpriced (order not readable yet)")
    [row] = _rows()
    assert row["usd_cents"] is None and row["reprice_order_id"] == "GPA.late"
    assert donations.transparency()["unpriced"] == 1

    play.orders["GPA.late"] = {"total": {"currencyCode": "USD", "units": "5"}}
    assert donations.run_reconciliation() is True
    [row] = _rows()
    assert row["usd_cents"] == 425 and row["amount_source"] == "order_total"
    assert row["reprice_order_id"] is None  # the plain order id is gone again
    body = donations.transparency()
    assert body["unpriced"] == 0 and body["covered_usd"] == 4.25


def test_reconciliation_failure_leaves_the_page_answering(play, monkeypatch, client):
    def broken(start_ms):
        raise donations.VerificationUnavailable("http 500")

    play.voided_tokens = broken
    r = client.get("/api/support/transparency")
    assert r.status_code == 200


def test_fx_override_and_fee(monkeypatch):
    monkeypatch.setenv("DONATIONS_FX_USD_JSON", '{"egp": 0.02, "bad": -1}')
    monkeypatch.setenv("DONATIONS_PLAY_FEE", "0.30")
    assert donations.to_usd_cents(100_000_000, "EGP") == 140  # 100 × 0.02 × 0.7
    assert donations.to_usd_cents(100_000_000, "EGP", fee_deducted=True) == 200
    assert donations.to_usd_cents(1_000_000, "BAD") is None
    monkeypatch.setenv("DONATIONS_PLAY_FEE", "7")  # nonsense → default 15%
    assert donations.to_usd_cents(1_000_000, "USD") == 85


# ── The real verifier's mapping of Play's HTTP answers ─────────────────────

class _Script:
    def __init__(self, answers):
        self.answers = answers
        self.calls = []

    def request(self, method, url, params=None, timeout=None):
        self.calls.append((method, url, params))
        return self.answers.pop(0)


def test_google_verifier_urls_and_status_mapping():
    session = _Script([_Resp(200, {"purchaseState": 0}), _Resp(204), _Resp(404, {}),
                       _Resp(200, {"voidedPurchases": [{"purchaseToken": "v1"}],
                                   "tokenPagination": {"nextPageToken": "p2"}}),
                       _Resp(200, {"voidedPurchases": [{"purchaseToken": "v2"}]})])
    v = _google(session)
    assert v.get_purchase("support_small", "a.b/c+d") == {"purchaseState": 0}
    v.consume("support_small", "a.b/c+d")
    assert v.get_order("GPA.1") is None
    assert v.voided_tokens(1_000) == {"v1", "v2"}
    (m1, u1, _), (m2, u2, _), (_, u3, _), (_, u4, p4), (_, _, p5) = session.calls
    assert m1 == "GET" and u1.endswith(
        "/com.alsaba.almorabbi/purchases/products/support_small/tokens/a.b%2Fc%2Bd")
    assert m2 == "POST" and u2.endswith("/tokens/a.b%2Fc%2Bd:consume")
    assert u3.endswith("/orders/GPA.1")
    assert u4.endswith("/purchases/voidedpurchases")
    assert p4["startTime"] == "1000" and p4["type"] == "0" and "token" not in p4
    assert p5["token"] == "p2"


@pytest.mark.parametrize("status,exc", [
    (400, donations.InvalidPurchase), (410, donations.InvalidPurchase),
    (401, donations.VerificationUnavailable), (403, donations.VerificationUnavailable),
    (429, donations.VerificationUnavailable), (503, donations.VerificationUnavailable),
])
def test_google_verifier_separates_rejection_from_outage(status, exc):
    with pytest.raises(exc):
        _google(_Script([_Resp(status, {})])).get_purchase("support_small", "tok")


# ── The shared credential loader ──────────────────────────────────────────

def test_shared_loader_degrades_on_binary_and_non_object_files(tmp_path):
    """push and support read their secrets through one hardened loader."""
    from app.core.service_account import read_service_account
    from app.services import push_sender

    binary = tmp_path / "binary.json"
    binary.write_bytes(b"\xff\xfe\x00\x81")
    listy = tmp_path / "list.json"
    listy.write_text("[1, 2, 3]", encoding="utf-8")
    for path in (binary, listy):
        assert read_service_account(path, label="T", feature="t") is None
        assert push_sender._read_service_account(path) is None


# ── The ledger's first shape (765be74f) is brought forward ────────────────

_OLD_DONATIONS = """
CREATE TABLE donations (
    id INTEGER PRIMARY KEY AUTOINCREMENT, token_hash TEXT NOT NULL UNIQUE,
    order_hash TEXT, product_id TEXT NOT NULL, amount_micros INTEGER,
    currency TEXT, usd_cents INTEGER, amount_source TEXT NOT NULL DEFAULT 'none',
    is_test INTEGER NOT NULL DEFAULT 0, consumed INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')));
CREATE INDEX ix_donations_created ON donations (created_at);
"""


def _columns():
    conn = get_conn()
    try:
        return {r[1] for r in conn.execute("PRAGMA table_info(donations)")}
    finally:
        conn.close()


def test_an_empty_first_shape_table_is_recreated():
    from app.db.init_db import init_db

    conn = get_conn()
    conn.executescript("DROP TABLE donations;" + _OLD_DONATIONS)
    conn.close()
    init_db()
    cols = _columns()
    assert {"purchase_type", "voided", "reprice_order_id"} <= cols
    assert "is_test" not in cols


def test_a_first_shape_table_with_rows_gains_columns_and_keeps_test_rows_out(play):
    from app.db.init_db import init_db

    conn = get_conn()
    conn.executescript("DROP TABLE donations;" + _OLD_DONATIONS)
    conn.execute("INSERT INTO donations (token_hash, product_id, usd_cents, is_test) "
                 "VALUES ('h-test', 'support_small', 500, 1), "
                 "('h-real', 'support_small', 300, 0)")
    conn.commit()
    conn.close()
    init_db()
    assert {"purchase_type", "voided", "reprice_order_id"} <= _columns()
    rows = {r["token_hash"]: r for r in _rows()}
    assert rows["h-test"]["purchase_type"] == 0
    assert rows["h-real"]["purchase_type"] is None
    body = donations.transparency()
    assert body["supports"] == 1 and body["covered_usd"] == 3.0
