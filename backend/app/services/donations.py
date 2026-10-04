"""«ادعم المربّي» — the support ledger, its Play verifier, and the monthly sum.

The app is free and stays free: a support purchase unlocks nothing, credits no
coins and earns no badge. It exists so families who want the app to keep
running can carry part of its cost, and the transparency page tells everyone
how much of this month's cost they carried.

Why Play Billing at all, and not a link to a donation page
----------------------------------------------------------
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
figure, Play's purchaseType, whether it was consumed, whether Play later voided
it, and the date. The purchase token and order id are kept only as sha256 —
enough to make a retry idempotent and to match a refund. There is **no device
id**: the transparency sum needs a month, not a donor, and a table that never
names a device has nothing for the privacy delete path to erase.

Configuration — read ONCE per process; restart after changing any of it
------------------------------------------------------------------------
``DONATIONS_ENABLED``        ``true`` to show the support surface. Default off,
                             and treated as off unless the service account
                             below loads — never sell what cannot be verified.
``PLAY_SERVICE_ACCOUNT``     Path to the service-account JSON. Default
                             ``/app/backend/secrets/play_service_account.json``
                             — the ``./backend/secrets`` bind mount, which must
                             be readable by the container user (uid 10001).
                             Use a DEDICATED least-privilege account with only
                             "View financial data" and "Manage orders and
                             subscriptions" — NOT the account
                             ``scripts/play_upload.py`` uses, which can push
                             releases to production.
``PLAY_PACKAGE_NAME``        Default ``com.alsaba.almorabbi``.
``DONATION_PRODUCT_IDS``     Comma list. Default
                             ``support_small,support_medium,support_large``.
``COST_MONTHLY_USD``         This month's running cost in USD. Unset → the page
                             shows what was given but hides the percentage
                             (a percentage of an unknown is not transparency).
``COST_BREAKDOWN_USD``       Optional itemisation, ``server=12,ai=25,other=3``.
                             Only ``server``, ``ai``, ``domain`` and ``other``
                             are shown — the keys the app has labels for.
``DONATIONS_PLAY_FEE``       Google's fee, used only when the order does not
                             report the developer's revenue. Default ``0.15``.
``DONATIONS_FX_USD_JSON``    Optional ``{"EGP": 0.0205, ...}`` overriding or
                             extending the built-in rough rates below.

How "covered" is computed (rough, and labelled as rough in the app)
-------------------------------------------------------------------
1. Amount: the order's ``developerRevenueInBuyerCurrency`` — what reaches the
   developer after Google's fee and taxes. If the order does not report it,
   ``total`` minus ``tax``, less ``DONATIONS_PLAY_FEE``. If no order can be read
   at all the row is stored **unpriced**: the price the app reports is never
   counted as money, and is kept only on test rows, which are never counted.
2. To USD with a static table of approximate rates (``_USD_PER_UNIT``). Rates
   drift; for a sentence that says "covered about 40%", a few percent of drift
   is noise, and a live FX dependency would be one more thing to break. An
   unknown currency is stored with ``usd_cents`` NULL and reported as
   ``unpriced`` rather than guessed.
3. Never counted: test purchases (Play ``purchaseType`` 0), promo-code (1) and
   rewarded (2) purchases, and anything Play has since voided — refunds,
   chargebacks, and the automatic refund of a purchase never acknowledged
   within three days. Voids are reconciled from the Voided Purchases API on a
   transparency read, at most once every ``VOIDED_RECHECK_SECONDS`` per
   process — no cron.
"""
from __future__ import annotations

import functools
import hashlib
import json
import logging
import os
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional, Protocol
from urllib.parse import quote

from app.core.service_account import read_service_account
from app.db.init_db import get_conn

logger = logging.getLogger(__name__)

DEFAULT_PRODUCT_IDS = ("support_small", "support_medium", "support_large")
DEFAULT_PACKAGE = "com.alsaba.almorabbi"
DEFAULT_PLAY_FEE = 0.15
# …/backend/secrets/, the directory production bind-mounts read-only (the same
# one push_sender reads its Firebase credential from).
DEFAULT_SERVICE_ACCOUNT = (
    Path(__file__).resolve().parents[3] / "backend" / "secrets"
    / "play_service_account.json"
)
# The cost lines the app has labels for. Anything else would render as a second
# «أخرى» row, so it is not shown at all.
COST_KEYS = ("server", "ai", "domain", "other")
VOIDED_RECHECK_SECONDS = 6 * 3600
_SCOPE = "https://www.googleapis.com/auth/androidpublisher"

# Play's ProductPurchase.purchaseType. Absent for an ordinary purchase.
PURCHASE_TYPE_TEST = 0
PURCHASE_TYPE_PROMO = 1
PURCHASE_TYPE_REWARDED = 2

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


# ── Errors ────────────────────────────────────────────────────────────────

class VerificationUnavailable(Exception):
    """Play could not be asked (no credentials, network, 5xx). Retryable.

    The message is always a fixed reason — "http 503", "ConnectionError" —
    never text from the transport: a requests error quotes the request URL,
    and the URL carries the purchase token.
    """


class InvalidPurchase(Exception):
    """Play answered, and the token is not a completed purchase of this product."""


class UnknownProduct(Exception):
    """The app sent a product id this server does not sell."""


def _reason(exc: BaseException) -> str:
    """What may be logged about [exc]: our own fixed reasons, else the type."""
    if isinstance(exc, (VerificationUnavailable, InvalidPurchase)) and exc.args:
        return str(exc.args[0])
    return type(exc).__name__


# ── Configuration ─────────────────────────────────────────────────────────

def _truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes"}


def package_name() -> str:
    return os.environ.get("PLAY_PACKAGE_NAME", "").strip() or DEFAULT_PACKAGE


def product_ids() -> tuple[str, ...]:
    raw = os.environ.get("DONATION_PRODUCT_IDS", "")
    ids = tuple(p.strip() for p in raw.split(",") if p.strip())
    return ids or DEFAULT_PRODUCT_IDS


def service_account_path() -> Path:
    raw = os.environ.get("PLAY_SERVICE_ACCOUNT", "").strip()
    return Path(raw) if raw else DEFAULT_SERVICE_ACCOUNT


def flag_enabled() -> bool:
    return _truthy("DONATIONS_ENABLED")


@functools.lru_cache(maxsize=1)
def _credentials():
    """The Play credentials, parsed once per process, or None.

    Goes through the hardened loader push uses (a 0600 root:root file in the
    bind mount reads as "unusable", not as an exception), and catches the rest
    too — `is_file()` itself raises PermissionError when the directory cannot
    be searched. Every failure is logged once, by type only.
    """
    try:
        path = service_account_path()
        if not path.is_file():
            return None
        info = read_service_account(path, label="Play", feature="support verification")
        if info is None:
            return None
        from google.oauth2 import service_account

        return service_account.Credentials.from_service_account_info(
            info, scopes=[_SCOPE])
    except Exception as exc:  # noqa: BLE001 — optional feature: degrade, never raise
        logger.error("Play service account is unusable (%s) — support "
                     "verification disabled", type(exc).__name__)
        return None


_unhealthy = False
_state_lock = threading.Lock()


def _mark_unhealthy(status: int) -> None:
    """Play refused the credentials (401/403): stop offering support.

    A 401 that survives google-auth's own token refresh, or a 403, means the
    account lost its permissions — every purchase from here on would be
    unverifiable and refunded after three days. Logged once.
    """
    global _unhealthy
    with _state_lock:
        if _unhealthy:
            return
        _unhealthy = True
    logger.error("Play rejected the support service account (HTTP %s) — support "
                 "hidden and verification off until restart; check the "
                 "account's permissions in Play Console", status)


@functools.lru_cache(maxsize=1)
def _gate() -> bool:
    """The flag AND credentials that load — computed once, never raising.

    /api/app-config is the force-update gate: it must answer every build even
    when this cannot be computed, so any failure here is "off", warned once.
    """
    try:
        if not flag_enabled():
            return False
        if _credentials() is None:
            logger.warning("DONATIONS_ENABLED is set but the Play service account "
                           "at %s could not be loaded — the support surface "
                           "stays hidden", service_account_path())
            return False
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("support gate could not be computed (%s) — the support "
                       "surface stays hidden", type(exc).__name__)
        return False


def is_enabled() -> bool:
    return _gate() and not _unhealthy


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
        if key in COST_KEYS and usd > 0:
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


def to_usd_cents(amount_micros: Optional[int], currency: Optional[str], *,
                 fee_deducted: bool = False) -> Optional[int]:
    """Rough USD cents reaching the developer, or None for an unknown currency.

    [fee_deducted] is true when the amount is already the developer's revenue;
    otherwise Google's fee is taken off here.
    """
    if amount_micros is None or not currency:
        return None
    rate = _fx_table().get(currency.upper())
    if rate is None:
        return None
    usd = amount_micros / 1_000_000 * rate
    if not fee_deducted:
        usd *= 1 - play_fee()
    return int(round(usd * 100))


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


# ── The verifier ──────────────────────────────────────────────────────────

class PlayVerifier(Protocol):
    def get_purchase(self, product_id: str, token: str) -> dict[str, Any]: ...
    def get_order(self, order_id: str) -> Optional[dict[str, Any]]: ...
    def consume(self, product_id: str, token: str) -> None: ...
    def voided_tokens(self, start_ms: int) -> set[str]: ...


class GooglePlayVerifier:
    """Android Publisher v3 over REST, authenticated with the service account.

    REST through google-auth's AuthorizedSession rather than
    google-api-python-client: google-auth is already installed and four
    endpoints do not justify a new dependency. The credentials are shared for
    the life of the process; a session is opened per call, so concurrent
    requests in the threadpool never share one.
    """

    _BASE = "https://androidpublisher.googleapis.com/androidpublisher/v3/applications"

    def __init__(self, credentials: Any, package: str):
        self._credentials = credentials
        self._app = f"{self._BASE}/{quote(package, safe='')}"

    def _session(self):
        from google.auth.transport.requests import AuthorizedSession

        return AuthorizedSession(self._credentials)

    def _call(self, method: str, url: str, params: Optional[dict] = None):
        try:
            resp = self._session().request(method, url, params=params, timeout=20)
        except Exception as exc:  # noqa: BLE001 — network/auth: retry later
            # `from None`: the transport error's text and its chain quote the URL.
            raise VerificationUnavailable(type(exc).__name__) from None
        if resp.status_code in (401, 403):
            _mark_unhealthy(resp.status_code)
            raise VerificationUnavailable(f"http {resp.status_code}")
        if resp.status_code >= 500 or resp.status_code == 429:
            raise VerificationUnavailable(f"http {resp.status_code}")
        return resp

    @staticmethod
    def _json(resp) -> dict[str, Any]:
        try:
            data = resp.json()
        except ValueError:
            raise VerificationUnavailable("invalid json") from None
        if not isinstance(data, dict):
            raise VerificationUnavailable("invalid json")
        return data

    def _token_url(self, product_id: str, token: str) -> str:
        return (f"{self._app}/purchases/products/{quote(product_id, safe='')}"
                f"/tokens/{quote(token, safe='')}")

    def get_purchase(self, product_id: str, token: str) -> dict[str, Any]:
        resp = self._call("GET", self._token_url(product_id, token))
        if resp.status_code != 200:
            raise InvalidPurchase(f"http {resp.status_code}")
        return self._json(resp)

    def get_order(self, order_id: str) -> Optional[dict[str, Any]]:
        resp = self._call("GET", f"{self._app}/orders/{quote(order_id, safe='')}")
        return self._json(resp) if resp.status_code == 200 else None

    def consume(self, product_id: str, token: str) -> None:
        resp = self._call("POST", self._token_url(product_id, token) + ":consume")
        if resp.status_code not in (200, 204):
            raise VerificationUnavailable(f"consume http {resp.status_code}")

    def voided_tokens(self, start_ms: int, max_pages: int = 5) -> set[str]:
        tokens: set[str] = set()
        page: Optional[str] = None
        for _ in range(max_pages):
            params = {"startTime": str(start_ms), "type": "0", "maxResults": "1000"}
            if page:
                params["token"] = page
            resp = self._call("GET", f"{self._app}/purchases/voidedpurchases",
                              params=params)
            if resp.status_code != 200:
                raise VerificationUnavailable(f"voided http {resp.status_code}")
            data = self._json(resp)
            for item in data.get("voidedPurchases") or []:
                token = item.get("purchaseToken") if isinstance(item, dict) else None
                if isinstance(token, str) and token:
                    tokens.add(token)
            page = (data.get("tokenPagination") or {}).get("nextPageToken")
            if not page:
                break
        return tokens


@functools.lru_cache(maxsize=1)
def _cached_verifier() -> Optional[GooglePlayVerifier]:
    creds = _credentials()
    return None if creds is None else GooglePlayVerifier(creds, package_name())


def _verifier() -> PlayVerifier:
    """The one verifier this process uses, or VerificationUnavailable."""
    if _unhealthy:
        raise VerificationUnavailable("unhealthy")
    verifier = _cached_verifier()
    if verifier is None:
        raise VerificationUnavailable("no credentials")
    return verifier


# ── Recording ─────────────────────────────────────────────────────────────

def _money_micros(money: Any) -> Optional[int]:
    if not isinstance(money, dict) or not money:
        return None
    try:
        units = int(money.get("units", 0) or 0)
        nanos = int(money.get("nanos", 0) or 0)
    except (TypeError, ValueError):
        return None
    return units * 1_000_000 + nanos // 1_000


def _amount_from_order(order: Optional[dict[str, Any]]
                       ) -> tuple[Optional[int], Optional[str], str]:
    """(micros, currency, source) — source says whether the fee is already off."""
    if not order:
        return None, None, "none"
    revenue = order.get("developerRevenueInBuyerCurrency")
    micros = _money_micros(revenue)
    if micros is not None and revenue.get("currencyCode"):
        return micros, revenue["currencyCode"], "order_revenue"
    total = order.get("total")
    gross = _money_micros(total)
    if gross is None or not total.get("currencyCode"):
        return None, None, "none"
    tax = _money_micros(order.get("tax")) or 0
    return max(gross - tax, 0), total["currencyCode"], "order_total"


def _row_for(conn, token_hash: str):
    return conn.execute(
        "SELECT id, product_id, consumed FROM donations WHERE token_hash = ?",
        (token_hash,)).fetchone()


def _try_consume(conn, row_id: int, product_id: str, token: str) -> bool:
    """Consume server-side; on failure say so, and the app consumes locally.

    Consuming is what lets the same family support again — an unconsumed
    consumable cannot be bought a second time. Only ever called for a row that
    is already recorded, so a local consume can never lose money from the sum.
    """
    try:
        _verifier().consume(product_id, token)
    except VerificationUnavailable as exc:
        logger.warning("support purchase consume failed (%s)", _reason(exc))
        return False
    conn.execute("UPDATE donations SET consumed = 1 WHERE id = ?", (row_id,))
    conn.commit()
    return True


def _already(conn, row, token: str) -> dict[str, Any]:
    consumed = bool(row["consumed"])
    if not consumed:
        consumed = _try_consume(conn, row["id"], row["product_id"], token)
    return {"ok": True, "consumed": consumed, "already_recorded": True,
            "pending": False}


def record_purchase(product_id: str, token: str,
                    client_price_micros: Optional[int] = None,
                    client_currency: Optional[str] = None) -> dict[str, Any]:
    """Verify one purchase with Play, add it to the ledger, consume it.

    Idempotent on the token, and the token is looked up FIRST — before the
    product allowlist, before a verifier exists, before Play is called. The
    app re-sends every unfinished purchase on each launch, so a token can
    arrive many times, including for a product since dropped from
    DONATION_PRODUCT_IDS; none of that may cost a Play call or lose the row.

    Returns ``{"ok", "consumed", "already_recorded", "pending"}``. Raises
    ``UnknownProduct``, ``InvalidPurchase`` and ``VerificationUnavailable``.
    """
    token_hash = _sha(token)
    conn = get_conn()
    try:
        existing = _row_for(conn, token_hash)
        if existing is not None:
            return _already(conn, existing, token)
        if product_id not in product_ids():
            raise UnknownProduct(product_id)

        verifier = _verifier()
        purchase = verifier.get_purchase(product_id, token)
        state = purchase.get("purchaseState")
        if state == 2:
            # Pending (cash at a kiosk, a slow carrier bill). Nothing to count
            # yet; the app re-sends it once Play reports it purchased.
            return {"ok": False, "consumed": False,
                    "already_recorded": False, "pending": True}
        if state != 0:
            raise InvalidPurchase(f"purchaseState={state}")

        ptype = purchase.get("purchaseType")
        if ptype not in (PURCHASE_TYPE_TEST, PURCHASE_TYPE_PROMO,
                         PURCHASE_TYPE_REWARDED):
            ptype = None
        order_id = purchase.get("orderId")
        micros, currency, source = None, None, "none"
        if order_id and ptype is None:
            try:
                micros, currency, source = _amount_from_order(
                    verifier.get_order(order_id))
            except VerificationUnavailable:
                micros, currency, source = None, None, "none"
        if (micros is None and ptype == PURCHASE_TYPE_TEST
                and client_price_micros is not None and client_currency):
            # Only a test row may carry the price the app reports — and test
            # rows are never counted. A real purchase without a readable order
            # stays unpriced rather than counting a client-supplied number.
            micros, currency, source = int(client_price_micros), client_currency, "client"

        cur = conn.execute(
            "INSERT OR IGNORE INTO donations (token_hash, order_hash, product_id, "
            "amount_micros, currency, usd_cents, amount_source, purchase_type) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (token_hash, _sha(order_id) if order_id else None, product_id,
             micros, currency.upper() if currency else None,
             to_usd_cents(micros, currency, fee_deducted=source == "order_revenue"),
             source, ptype),
        )
        conn.commit()
        if cur.rowcount == 0:
            # A concurrent request for the same token inserted first; it owns
            # the consume. This one reports the row, and consumes nothing.
            row = _row_for(conn, token_hash)
            return {"ok": True, "consumed": bool(row and row["consumed"]),
                    "already_recorded": True, "pending": False}

        row_id = cur.lastrowid
        if purchase.get("consumptionState") == 1:
            conn.execute("UPDATE donations SET consumed = 1 WHERE id = ?", (row_id,))
            conn.commit()
            consumed = True
        else:
            consumed = _try_consume(conn, row_id, product_id, token)
        return {"ok": True, "consumed": consumed,
                "already_recorded": False, "pending": False}
    finally:
        conn.close()


# ── Transparency ──────────────────────────────────────────────────────────

# A range on created_at, not substr(): the range can use ix_donations_created.
MONTH_TOTALS_SQL = (
    "SELECT COUNT(*) AS n, COALESCE(SUM(usd_cents), 0) AS cents, "
    "COALESCE(SUM(CASE WHEN usd_cents IS NULL THEN 1 ELSE 0 END), 0) AS unpriced "
    "FROM donations WHERE created_at >= ? AND created_at < ? "
    "AND purchase_type IS NULL AND voided = 0"
)

_voided_checked_at: Optional[float] = None


def _month_bounds(now: datetime) -> tuple[str, str, str]:
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    following = (start + timedelta(days=32)).replace(day=1)
    fmt = "%Y-%m-%d %H:%M:%S"  # the shape SQLite's datetime('now') writes
    return start.strftime("%Y-%m"), start.strftime(fmt), following.strftime(fmt)


def _reconcile_voided(now: datetime) -> None:
    """Mark the rows Play reports voided — refunds, chargebacks, auto-refunds.

    Runs on a transparency read, at most once per VOIDED_RECHECK_SECONDS per
    process, so a page anyone can load costs at most four Play calls a day and
    no cron exists for it. The API reaches back 30 days; that covers the month
    on display. Any failure leaves the figures as they were, logged by reason.
    """
    global _voided_checked_at
    clock = time.monotonic()
    if (_voided_checked_at is not None
            and clock - _voided_checked_at < VOIDED_RECHECK_SECONDS):
        return
    _voided_checked_at = clock
    try:
        if not is_enabled():
            return
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        since = max(month_start, now - timedelta(days=29))
        tokens = _verifier().voided_tokens(int(since.timestamp() * 1000))
        hashes = [_sha(t) for t in tokens]
        if not hashes:
            return
        conn = get_conn()
        try:
            for i in range(0, len(hashes), 500):
                chunk = hashes[i:i + 500]
                conn.execute(
                    "UPDATE donations SET voided = 1 WHERE voided = 0 AND token_hash "
                    f"IN ({','.join('?' * len(chunk))})", chunk)
            conn.commit()
        finally:
            conn.close()
    except Exception as exc:  # noqa: BLE001 — the page must still answer
        logger.warning("voided-purchase reconciliation skipped (%s)", _reason(exc))


def transparency(now: Optional[datetime] = None) -> dict[str, Any]:
    """This month's cost, what supporters covered, and the share — aggregates only."""
    now = now or datetime.now(timezone.utc)
    _reconcile_voided(now)
    month, start, end = _month_bounds(now)
    conn = get_conn()
    try:
        row = conn.execute(MONTH_TOTALS_SQL, (start, end)).fetchone()
    finally:
        conn.close()

    covered_usd = round((row["cents"] or 0) / 100, 2)
    cost = monthly_cost_usd()
    pct = None if cost is None else int(round(100 * covered_usd / cost))
    return {
        "month": month,
        "cost_usd": cost,
        "covered_usd": covered_usd,
        "covered_pct": pct,
        "supports": int(row["n"] or 0),
        "unpriced": int(row["unpriced"] or 0),
        "breakdown": cost_breakdown() if cost is not None else [],
    }
