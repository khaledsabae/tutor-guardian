"""«ادعم المربّي» — the support ledger, its Play verifier, and the monthly sum.

The app is free and stays free: a support purchase unlocks nothing, credits no
coins and earns no badge. It exists so families who want the app to keep
running can carry part of its cost, and the transparency page tells everyone
how much of this month's cost they carried.

Why Play Billing, and not a link to a donation page
---------------------------------------------------
Google Play Payments policy, §1 and §3
(https://support.google.com/googleplay/android-developer/answer/9858738):
apps "accepting payment for access to in-app features or services, including
any app functionality, digital content or goods" must use Play's billing
system; the billing system "must not be used" for "tax exempt donations", and
"apps may not lead users to a payment method other than Google Play's billing
system" outside §3/§8/§9. The developer is an individual, not a registered
tax-exempt organisation, so the §3 carve-out does not apply and an external
donation link would breach §4. The FAQ's peer-to-peer tip exception
(https://support.google.com/googleplay/android-developer/answer/10281818) is
for tips passed 100% to a *creator* on a platform, not to the app's own
developer. That leaves consumable in-app products, verified here.

What the ledger stores
----------------------
One row per verified purchase: product, amount in micros, currency, a rough USD
figure, and the date. The purchase token and order id are kept only as sha256 —
enough to make a retry idempotent and to match a refund later. There is **no
device id**: the transparency sum needs a month, not a donor, and a table that
never names a device has nothing for the privacy delete path to erase.

Configuration (all read at call time, so a restart is enough)
-------------------------------------------------------------
``DONATIONS_ENABLED``        ``true`` to show the support surface. Default off.
                             Ignored (treated as off) unless the verifier below
                             is configured — never sell what cannot be verified.
``PLAY_SERVICE_ACCOUNT``     Path to the Play service-account JSON (the same
                             variable ``scripts/play_upload.py`` reads). Needs
                             the "view financial data" + "manage orders"
                             permissions in Play Console.
``PLAY_PACKAGE_NAME``        Default ``com.alsaba.almorabbi``.
``DONATION_PRODUCT_IDS``     Comma list. Default
                             ``support_small,support_medium,support_large``.
``COST_MONTHLY_USD``         This month's running cost in USD. Unset → the page
                             shows what was given but hides the percentage
                             (a percentage of an unknown is not transparency).
``COST_BREAKDOWN_USD``       Optional itemisation, ``server=12,ai=25,other=3``.
                             Keys: ``[a-z_]{1,24}``; the app labels the known
                             ones (server, ai, domain, other).
``DONATIONS_PLAY_FEE``       Google's service fee deducted before counting.
                             Default ``0.15``.
``DONATIONS_FX_USD_JSON``    Optional ``{"EGP": 0.0205, ...}`` overriding or
                             extending the built-in rough rates below.

How "covered" is computed (rough, and labelled as rough in the app)
-------------------------------------------------------------------
1. Amount: the order's ``total`` minus its ``tax`` from ``orders.get`` (what
   the buyer paid, net of VAT). If the order cannot be read — test purchases
   have no retrievable order — the store price the app showed is used instead
   (``amount_source`` records which).
2. To USD with a static table of approximate rates (``_USD_PER_UNIT``). Rates
   drift; for a sentence that says "covered about 40%", a few percent of drift
   is noise, and a live FX dependency would be one more thing to break. An
   unknown currency is stored with ``usd_cents`` NULL and reported as
   ``unpriced`` rather than guessed.
3. Minus Play's fee (``DONATIONS_PLAY_FEE``). The figure is what reaches the
   developer, which is what pays the bills.
4. Test purchases (Play ``purchaseType`` 0, i.e. licence testers) are recorded
   but never counted.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Protocol
from urllib.parse import quote

from app.db.init_db import get_conn

logger = logging.getLogger(__name__)

DEFAULT_PRODUCT_IDS = ("support_small", "support_medium", "support_large")
DEFAULT_PACKAGE = "com.alsaba.almorabbi"
DEFAULT_PLAY_FEE = 0.15

# Approximate USD per one unit of currency, autumn 2026. Covers the currencies
# the audience actually pays in (Egypt and the Gulf first, then the diaspora).
# Rough by design — see the module docstring, step 2.
_USD_PER_UNIT: dict[str, float] = {
    "USD": 1.0, "EUR": 1.08, "GBP": 1.27, "CAD": 0.73, "AUD": 0.66,
    "CHF": 1.13, "SEK": 0.095, "NOK": 0.093, "DKK": 0.145,
    "SAR": 0.2667, "AED": 0.2723, "QAR": 0.2747, "KWD": 3.26, "BHD": 2.65,
    "OMR": 2.60, "JOD": 1.41, "EGP": 0.0205, "MAD": 0.10, "DZD": 0.0074,
    "TND": 0.32, "IQD": 0.00076, "LYD": 0.18, "TRY": 0.026, "PKR": 0.0036,
    "INR": 0.012, "BDT": 0.0083, "IDR": 0.000062, "MYR": 0.22, "SGD": 0.75,
    "NGN": 0.00065, "ZAR": 0.055, "KES": 0.0077,
}

_BREAKDOWN_KEY = re.compile(r"^[a-z_]{1,24}$")


# ── Configuration ─────────────────────────────────────────────────────────

def _truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes"}


def package_name() -> str:
    return os.environ.get("PLAY_PACKAGE_NAME", "").strip() or DEFAULT_PACKAGE


def product_ids() -> tuple[str, ...]:
    raw = os.environ.get("DONATION_PRODUCT_IDS", "")
    ids = tuple(p.strip() for p in raw.split(",") if p.strip())
    return ids or DEFAULT_PRODUCT_IDS


def service_account_path() -> Optional[Path]:
    raw = os.environ.get("PLAY_SERVICE_ACCOUNT", "").strip()
    if not raw:
        return None
    path = Path(raw)
    return path if path.is_file() else None


def flag_enabled() -> bool:
    return _truthy("DONATIONS_ENABLED")


def is_enabled() -> bool:
    """The flag AND a verifier able to check what is sold.

    A flag flipped on before the service account is mounted would sell
    purchases that can never be verified, consumed, or counted — and Play
    refunds an unacknowledged purchase after three days, so the family would
    see the charge vanish. Off until both are true.
    """
    if not flag_enabled():
        return False
    if _verifier_override is not None:
        return True
    if service_account_path() is None:
        logger.warning("DONATIONS_ENABLED is set but PLAY_SERVICE_ACCOUNT is "
                       "missing or unreadable — the support surface stays hidden")
        return False
    return True


def monthly_cost_usd() -> Optional[float]:
    raw = os.environ.get("COST_MONTHLY_USD", "").strip()
    try:
        value = float(raw)
    except ValueError:
        return None
    return value if value > 0 else None


def cost_breakdown() -> list[dict[str, Any]]:
    raw = os.environ.get("COST_BREAKDOWN_USD", "").strip()
    items: list[dict[str, Any]] = []
    for part in raw.split(","):
        if "=" not in part:
            continue
        key, _, value = part.partition("=")
        key = key.strip().lower()
        try:
            usd = float(value.strip())
        except ValueError:
            continue
        if _BREAKDOWN_KEY.match(key) and usd > 0:
            items.append({"key": key, "usd": round(usd, 2)})
    return items


def play_fee() -> float:
    try:
        fee = float(os.environ.get("DONATIONS_PLAY_FEE", DEFAULT_PLAY_FEE))
    except ValueError:
        return DEFAULT_PLAY_FEE
    return fee if 0 <= fee < 1 else DEFAULT_PLAY_FEE


def _fx_table() -> dict[str, float]:
    table = dict(_USD_PER_UNIT)
    raw = os.environ.get("DONATIONS_FX_USD_JSON", "").strip()
    if raw:
        try:
            extra = json.loads(raw)
            for code, rate in extra.items():
                if isinstance(code, str) and isinstance(rate, (int, float)) and rate > 0:
                    table[code.upper()] = float(rate)
        except (ValueError, AttributeError):
            logger.warning("DONATIONS_FX_USD_JSON is not a JSON object — ignored")
    return table


def to_usd_cents(amount_micros: Optional[int], currency: Optional[str]) -> Optional[int]:
    """Rough USD cents *after Play's fee*, or None for an unknown currency."""
    if amount_micros is None or not currency:
        return None
    rate = _fx_table().get(currency.upper())
    if rate is None:
        return None
    usd = amount_micros / 1_000_000 * rate * (1 - play_fee())
    return int(round(usd * 100))


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


# ── The verifier ──────────────────────────────────────────────────────────

class VerificationUnavailable(Exception):
    """Play could not be asked (no credentials, network, 5xx). Retryable."""


class InvalidPurchase(Exception):
    """Play answered, and the token is not a completed purchase of this product."""


class PlayVerifier(Protocol):
    def get_purchase(self, product_id: str, token: str) -> dict[str, Any]: ...
    def get_order(self, order_id: str) -> Optional[dict[str, Any]]: ...
    def consume(self, product_id: str, token: str) -> None: ...


class GooglePlayVerifier:
    """Android Publisher v3 over REST, authenticated with the service account.

    REST through google-auth's AuthorizedSession rather than
    google-api-python-client: google-auth is already installed (firebase-admin
    depends on it) and three endpoints do not justify a new dependency.
    """

    _BASE = "https://androidpublisher.googleapis.com/androidpublisher/v3/applications"
    _SCOPE = "https://www.googleapis.com/auth/androidpublisher"

    def __init__(self, sa_path: Path, package: str):
        from google.auth.transport.requests import AuthorizedSession
        from google.oauth2 import service_account

        creds = service_account.Credentials.from_service_account_file(
            str(sa_path), scopes=[self._SCOPE])
        self._session = AuthorizedSession(creds)
        self._app = f"{self._BASE}/{package}"

    def _call(self, method: str, url: str) -> Any:
        try:
            resp = self._session.request(method, url, timeout=20)
        except Exception as exc:  # noqa: BLE001 — network/auth: retry later
            raise VerificationUnavailable(str(exc)) from exc
        if resp.status_code >= 500 or resp.status_code in (401, 403, 429):
            raise VerificationUnavailable(f"play {resp.status_code}")
        return resp

    def _token_url(self, product_id: str, token: str) -> str:
        return (f"{self._app}/purchases/products/{quote(product_id, safe='')}"
                f"/tokens/{quote(token, safe='')}")

    def get_purchase(self, product_id: str, token: str) -> dict[str, Any]:
        resp = self._call("GET", self._token_url(product_id, token))
        if resp.status_code != 200:
            raise InvalidPurchase(f"play {resp.status_code}")
        return resp.json()

    def get_order(self, order_id: str) -> Optional[dict[str, Any]]:
        resp = self._call("GET", f"{self._app}/orders/{quote(order_id, safe='')}")
        return resp.json() if resp.status_code == 200 else None

    def consume(self, product_id: str, token: str) -> None:
        resp = self._call("POST", self._token_url(product_id, token) + ":consume")
        if resp.status_code not in (200, 204):
            raise VerificationUnavailable(f"consume {resp.status_code}")


_verifier_override: Optional[PlayVerifier] = None


def set_verifier(verifier: Optional[PlayVerifier]) -> None:
    """Tests inject a fake; production builds the Google one lazily."""
    global _verifier_override
    _verifier_override = verifier


def _verifier() -> PlayVerifier:
    if _verifier_override is not None:
        return _verifier_override
    sa = service_account_path()
    if sa is None:
        raise VerificationUnavailable("PLAY_SERVICE_ACCOUNT not configured")
    return GooglePlayVerifier(sa, package_name())


# ── Recording ─────────────────────────────────────────────────────────────

def _money_micros(money: Optional[dict[str, Any]]) -> Optional[int]:
    if not money:
        return None
    try:
        units = int(money.get("units", 0) or 0)
        nanos = int(money.get("nanos", 0) or 0)
    except (TypeError, ValueError):
        return None
    return units * 1_000_000 + nanos // 1_000


def _amount_from_order(order: Optional[dict[str, Any]]) -> tuple[Optional[int], Optional[str]]:
    if not order:
        return None, None
    total = order.get("total") or {}
    gross = _money_micros(total)
    if gross is None:
        return None, None
    tax = _money_micros(order.get("tax")) or 0
    return max(gross - tax, 0), total.get("currencyCode")


def record_purchase(product_id: str, token: str,
                    client_price_micros: Optional[int] = None,
                    client_currency: Optional[str] = None) -> dict[str, Any]:
    """Verify one purchase with Play, add it to the ledger, consume it.

    Idempotent on the token: the app re-sends every unfinished purchase on the
    next launch, so the same token can arrive twice. The second call does not
    add a row; it only retries the consume if the first one failed.

    Returns ``{"ok", "consumed", "already_recorded", "pending"}``. Raises
    ``ValueError`` for a product this server does not sell,
    ``InvalidPurchase`` and ``VerificationUnavailable`` as named.
    """
    if product_id not in product_ids():
        raise ValueError("unknown_product")
    verifier = _verifier()
    token_hash = _sha(token)

    conn = get_conn()
    try:
        existing = conn.execute(
            "SELECT id, consumed FROM donations WHERE token_hash = ?",
            (token_hash,)).fetchone()
        if existing is not None:
            consumed = bool(existing["consumed"])
            if not consumed:
                consumed = _try_consume(verifier, conn, existing["id"], product_id, token)
            return {"ok": True, "consumed": consumed,
                    "already_recorded": True, "pending": False}

        purchase = verifier.get_purchase(product_id, token)
        state = purchase.get("purchaseState")
        if state == 2:
            # Pending (cash at a kiosk, a slow carrier bill). Nothing to count
            # yet; the app re-sends it once Play reports it purchased.
            return {"ok": False, "consumed": False,
                    "already_recorded": False, "pending": True}
        if state != 0:
            raise InvalidPurchase(f"purchaseState={state}")

        is_test = purchase.get("purchaseType") == 0
        order_id = purchase.get("orderId")
        micros, currency, source = None, None, "none"
        if order_id and not is_test:
            try:
                micros, currency = _amount_from_order(verifier.get_order(order_id))
            except VerificationUnavailable:
                micros, currency = None, None
            if micros is not None:
                source = "order"
        if micros is None and client_price_micros is not None and client_currency:
            micros, currency, source = int(client_price_micros), client_currency, "client"

        cur = conn.execute(
            "INSERT OR IGNORE INTO donations (token_hash, order_hash, product_id, "
            "amount_micros, currency, usd_cents, amount_source, is_test) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (token_hash, _sha(order_id) if order_id else None, product_id,
             micros, currency.upper() if currency else None,
             to_usd_cents(micros, currency), source, 1 if is_test else 0),
        )
        conn.commit()
        row_id = cur.lastrowid
        if not row_id:  # lost a race with a concurrent retry of the same token
            row = conn.execute("SELECT id FROM donations WHERE token_hash = ?",
                               (token_hash,)).fetchone()
            row_id = row["id"]

        consumed = purchase.get("consumptionState") == 1
        if consumed:
            conn.execute("UPDATE donations SET consumed = 1 WHERE id = ?", (row_id,))
            conn.commit()
        else:
            consumed = _try_consume(verifier, conn, row_id, product_id, token)
        return {"ok": True, "consumed": consumed,
                "already_recorded": False, "pending": False}
    finally:
        conn.close()


def _try_consume(verifier: PlayVerifier, conn, row_id: int,
                 product_id: str, token: str) -> bool:
    """Consume server-side; on failure say so, and the app consumes locally.

    Consuming is what lets the same family support again — an unconsumed
    consumable cannot be bought a second time.
    """
    try:
        verifier.consume(product_id, token)
    except VerificationUnavailable as exc:
        logger.warning("support purchase consume failed: %s", exc)
        return False
    conn.execute("UPDATE donations SET consumed = 1 WHERE id = ?", (row_id,))
    conn.commit()
    return True


# ── Transparency ──────────────────────────────────────────────────────────

def transparency(now: Optional[datetime] = None) -> dict[str, Any]:
    """This month's cost, what supporters covered, and the share — aggregates only."""
    now = now or datetime.now(timezone.utc)
    month = now.strftime("%Y-%m")
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT COUNT(*) AS n, COALESCE(SUM(usd_cents), 0) AS cents, "
            "SUM(CASE WHEN usd_cents IS NULL THEN 1 ELSE 0 END) AS unpriced "
            "FROM donations WHERE is_test = 0 AND substr(created_at, 1, 7) = ?",
            (month,)).fetchone()
    finally:
        conn.close()

    covered_usd = round((row["cents"] or 0) / 100, 2)
    cost = monthly_cost_usd()
    pct = None
    if cost is not None:
        pct = int(round(100 * covered_usd / cost))
    return {
        "enabled": is_enabled(),
        "month": month,
        "cost_usd": cost,
        "covered_usd": covered_usd,
        "covered_pct": pct,
        "supports": int(row["n"] or 0),
        "unpriced": int(row["unpriced"] or 0),
        "breakdown": cost_breakdown() if cost is not None else [],
        "approximate": True,
    }
