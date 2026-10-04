"""Install attribution — the one place that builds a Google Play link.

Every public page that sends a visitor to Play takes its link from here: the
share/install landing (`/`, `/go`, `/ui/`), the lesson and path pages (`/l`,
`/p`), the SEO articles (`/seo/*`) and `/methodology`. The link carries an
install referrer that two readers parse, neither of which can change from here:

* **the app** (`mobile/lib/features/referral/referral_service.dart`) upper-cases
  the referrer and claims the first `REF_([A-Z0-9]{4,16})` in it — once, on
  first launch, and never again. A claim that 404s is lost for good: it does
  not fall back to the AUTO (IP) match.
* **Firebase Analytics** reads `utm_*` from it as a query string; that is what
  fills GA4's first-user source / medium / campaign.

So the referrer is `ref_<CODE>&utm_source=…&…`, URL-encoded once more as the
value of Play's `referrer` parameter (Google's documented format). A referral
code alone still yields exactly `…&referrer=ref_<CODE>`, the string the app has
always been handed.

Why it lives server-side: `30bc1d5f` (15 Aug) carried utm_* to Play from page
JavaScript on `/ui/`; `e35bcdc2` (13 Sep) rewrote that page for the cinematic
landing and the script went with it, so campaign installs read as `(direct)`
in GA4 again and the page's buttons stopped linking to Play at all.
`tests/test_landing_attribution.py` renders every public page and fails if any
of them reaches Play without this.

Campaign codes
--------------
A campaign code is a referral code with no device behind it: two letters
naming the channel plus a number — `DA01`, `WAAR`, `KT001` (4–16 letters or
digits, never shaped like a six-character device code) — so it fits the app's
parser and never needs registering: a link carrying one works the moment it
is shared. `POST /api/referral/claim` records
an unknown but well-formed campaign code instead of answering 404, and the
landing pages record its clicks. The prefixes are the ones the Ramadan
marketing kit hands out (`docs/marketing/2026-10-ramadan/00_README.md`).
Which person holds which code stays out of git.

Hyphenated codes (`c-wa-ramadan`) were considered and cannot work: builds
already on Play stop the claim at the first character outside `[A-Z0-9]`.
"""
from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from urllib.parse import quote

from app.db.init_db import get_conn

logger = logging.getLogger(__name__)

PLAY_URL = "https://play.google.com/store/apps/details?id=com.alsaba.almorabbi"

# What the app's parser and POST /api/referral/claim accept.
CODE_RE = re.compile(r"^[A-Z0-9]{4,16}$")
_SEPARATORS = re.compile(r"[\s_-]+")

# prefix → (utm_source, utm_medium) GA4 shows when the link brings no utm_* of
# its own. Explicit utm_* on the link always win, key by key.
CAMPAIGN_CHANNELS: dict[str, tuple[str, str]] = {
    "DA": ("preacher_ar", "social"),   # دعاة ومربّون بالعربية — DA01…
    "EN": ("preacher_en", "social"),   # preachers & educators in English — EN01…
    "WA": ("whatsapp", "social"),      # قناتا واتساب — WAAR, WAEN
    "KT": ("kuttab", "offline"),       # كتاتيب وحضانات ومدارس — KT001…
    "CM": ("community", "social"),     # English community groups — CM01…
    "PD": ("paid", "paid"),            # تعزيز مدفوع — PD01…
    "OT": ("other", "referral"),       # anything else — OT01…
}
CAMPAIGN_RE = re.compile(
    r"^(?:" + "|".join(CAMPAIGN_CHANNELS) + r")[A-Z0-9]{2,14}$"
)
# Device codes (referral.py hands them out) are exactly six characters from
# an alphabet without 0/O/1/I, so they read aloud unambiguously. A code of
# that shape is a person's invite even when it starts like a campaign:
# production has `EN…` device codes, and reading them as English preachers
# would credit a campaign with a parent's invites.
DEVICE_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
DEVICE_CODE_LEN = 6
# '#' is outside the device-id pattern POST /api/chat/sessions admits, so no
# client can mint a session as a campaign and read its invite count.
CAMPAIGN_OWNER_PREFIX = "campaign#"

UTM_KEYS = ("utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content")
UTM_MAX_CHARS = 100  # GA4 truncates campaign dimensions at 100

# referral_clicks bounds (audit M8: these routes sit outside /api, so the rate
# limiter never sees them).
_CLICK_REFRESH_WINDOW = "-10 minutes"
MAX_CLICKS_PER_IP_PER_HOUR = 20
_MAX_UA_CHARS = 256
# Link-preview fetchers, not people: sharing a link in a chat fetches its
# preview, and 99 of 641 production clicks (15%) were facebookexternalhit,
# WhatsApp or TelegramBot (read-only, 2026-10-04). Named tokens only — a bare
# "bot" would also match phones such as the CUBOT range.
PREVIEW_FETCHER_RE = re.compile(
    r"facebookexternalhit|Facebot|WhatsApp/|TelegramBot|Twitterbot|Slackbot|"
    r"Discordbot|LinkedInBot|Googlebot|bingbot|Applebot|SkypeUriPreview",
    re.IGNORECASE,
)


def normalize_code(raw: str | None) -> str | None:
    """`' da-01 '` → `'DA01'`; None when it cannot be a referral code."""
    code = _SEPARATORS.sub("", raw or "").upper()
    return code if CODE_RE.match(code) else None


def is_device_shaped(code: str) -> bool:
    return len(code) == DEVICE_CODE_LEN and set(code) <= set(DEVICE_CODE_ALPHABET)


def is_campaign_code(code: str | None) -> bool:
    """A channel prefix and not a possible device code: DA01, WAAR, KT001."""
    return bool(code) and bool(CAMPAIGN_RE.match(code)) and not is_device_shaped(code)


def campaign_channel(code: str) -> str | None:
    """`'DA01'` → `'preacher_ar'`; None for anything that is not a campaign code."""
    return CAMPAIGN_CHANNELS[code[:2]][0] if is_campaign_code(code) else None


def campaign_owner(code: str) -> str:
    """The `referrals.referrer_device` a campaign claim is recorded under."""
    return CAMPAIGN_OWNER_PREFIX + code


def clean_utm(params: Mapping[str, str]) -> dict[str, str]:
    """The utm_* a landing URL arrived with: known keys only, printable, bounded."""
    out: dict[str, str] = {}
    for key in UTM_KEYS:
        value = params.get(key)
        if not value:
            continue
        value = "".join(ch for ch in value if ch.isprintable()).strip()[:UTM_MAX_CHARS]
        if value:
            out[key] = value
    return out


def attribution_utm(code: str | None, params: Mapping[str, str]) -> dict[str, str]:
    """utm_* for the Play link: a campaign code's channel, overridden by the URL's own."""
    utm: dict[str, str] = {}
    if is_campaign_code(code):
        source, medium = CAMPAIGN_CHANNELS[code[:2]]
        utm = {"utm_source": source, "utm_medium": medium, "utm_campaign": code}
    utm.update(clean_utm(params))
    return utm


def _referrer_value(value: str) -> str:
    # Percent-encode everything, '_' included: the app's REF_<code> match is
    # unanchored, so a raw `ref_XYZ1` inside a utm value would be claimed (and
    # 404) in place of the real code. Firebase decodes %5F back to '_'.
    return quote(value, safe="").replace("_", "%5F")


def install_referrer(code: str | None, utm: Mapping[str, str] | None = None) -> str:
    """`ref_<CODE>&utm_source=…` — what Play hands the app on first launch."""
    parts = [f"ref_{code}"] if code else []
    for key in UTM_KEYS:
        if utm and utm.get(key):
            parts.append(f"{key}={_referrer_value(utm[key])}")
    return "&".join(parts)


def play_install_url(code: str | None = None, utm: Mapping[str, str] | None = None) -> str:
    referrer = install_referrer(code, utm)
    if not referrer:
        return PLAY_URL
    return f"{PLAY_URL}&referrer={quote(referrer, safe='')}"


def landing_attribution(query: Mapping[str, str]) -> tuple[str, str | None]:
    """(Play link, normalised ref code or None) for a landing page's query string."""
    code = normalize_code(query.get("ref"))
    return play_install_url(code, attribution_utm(code, query)), code


def attribute_visit(request) -> str:
    """The Play link for a public page visit; records the click if it carries a code.

    `request.client.host` is the visitor's address as ClientIPMiddleware
    resolved it — from trusted proxies only, never from a caller's header.
    """
    install_url, code = landing_attribution(request.query_params)
    if code:
        ip = request.client.host if request.client else "unknown"
        record_click(ip, request.headers.get("user-agent", ""), code)
    return install_url


def record_click(ip: str, user_agent: str, code: str) -> None:
    """Remember that this IP followed this code, within bounds.

    The AUTO claim matches a first launch to the latest click from the same IP
    within 24 h — the fallback when Play loses the referrer.

    * Only codes that can be claimed are recorded: an existing referral code or
      a well-formed campaign code. Random codes cannot fill the table.
    * Link-preview fetchers are not visitors, and never install the app.
    * The same IP and code again within 10 minutes refreshes the existing row
      instead of adding one ("last link followed wins", without duplicates).
    * At most 20 new rows per IP per hour; beyond that the page still renders,
      the click is just not recorded.
    """
    if PREVIEW_FETCHER_RE.search(user_agent or ""):
        return
    conn = get_conn()
    try:
        if not is_campaign_code(code) and not conn.execute(
            "SELECT 1 FROM referral_codes WHERE code = ?", (code,)
        ).fetchone():
            return
        recent = conn.execute(
            "SELECT id FROM referral_clicks WHERE ip = ? AND code = ? "
            "AND clicked_at > datetime('now', ?) ORDER BY id DESC LIMIT 1",
            (ip, code, _CLICK_REFRESH_WINDOW),
        ).fetchone()
        if recent:
            conn.execute(
                "UPDATE referral_clicks SET clicked_at = datetime('now') WHERE id = ?",
                (recent["id"],),
            )
        else:
            (count,) = conn.execute(
                "SELECT COUNT(*) FROM referral_clicks "
                "WHERE ip = ? AND clicked_at > datetime('now', '-1 hour')",
                (ip,),
            ).fetchone()
            if count >= MAX_CLICKS_PER_IP_PER_HOUR:
                return
            conn.execute(
                "INSERT INTO referral_clicks (ip, user_agent, code) VALUES (?, ?, ?)",
                (ip, user_agent[:_MAX_UA_CHARS], code),
            )
        conn.commit()
    except Exception:  # noqa: BLE001 — a click log must never break the page
        logger.warning("referral click not recorded", exc_info=True)
    finally:
        conn.close()
