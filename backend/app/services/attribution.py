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
A campaign code is a referral code with no device behind it: exactly two
letters naming the channel and two digits — `DA01`, `WA02`, `KT17`. It fits
the app's parser and never needs registering: a link carrying one works the
moment it is shared. `POST /api/referral/claim` records an unknown campaign
code instead of answering 404, and the landing pages record its clicks. The
prefixes are the Ramadan marketing kit's
(`docs/marketing/2026-10-ramadan/00_README.md`). Which person holds which code
stays out of git.

Why exactly four characters: a personal code is six characters, so any typo
of one (a dropped, added, swapped or wrong character) is five, six or seven.
Under the earlier rule (prefix plus 2–14 characters) `ENV9Z`, a typo of the
real personal code `ENV9Z5`, was accepted as a campaign. That used up the
installing device's one claim, and the friend who invited it was never
credited.

Hyphenated codes (`c-wa-ramadan`) were considered and cannot work: builds
already on Play stop the claim at the first character outside `[A-Z0-9]`.
"""
from __future__ import annotations

import ipaddress
import logging
import re
import unicodedata
from collections import Counter
from collections.abc import Mapping
from urllib.parse import quote

from app.db.init_db import get_conn

logger = logging.getLogger(__name__)

PLAY_URL = "https://play.google.com/store/apps/details?id=com.alsaba.almorabbi"

# What the app's parser and POST /api/referral/claim accept.
CODE_RE = re.compile(r"^[A-Z0-9]{4,16}$")
_SEPARATORS = re.compile(r"[\s_\-‐-―ـ]+")
_FIRST_RUN = re.compile(r"[A-Za-z0-9]+")
# A code typed on an Arabic keyboard can arrive as «DA٠١».
_EASTERN_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")

# prefix → (utm_source, utm_medium) GA4 shows when the link brings no utm_* of
# its own. Explicit utm_* on the link always win, key by key.
CAMPAIGN_CHANNELS: dict[str, tuple[str, str]] = {
    "DA": ("preacher_ar", "social"),   # دعاة ومربّون بالعربية — DA01…
    "EN": ("preacher_en", "social"),   # preachers & educators in English — EN01…
    "WA": ("whatsapp", "social"),      # قناتا واتساب — WA01 (عربي)، WA02 (English)
    "KT": ("kuttab", "offline"),       # كتاتيب وحضانات ومدارس — KT01…
    "CM": ("community", "social"),     # English community groups — CM01…
    "PD": ("paid", "paid"),            # تعزيز مدفوع — PD01…
    "OT": ("other", "referral"),       # anything else — OT01…
}
# Exactly four characters. Personal codes are six, so no typo of one can land
# here (see the module docstring). ASCII digits only: \d would also match «٠».
CAMPAIGN_RE = re.compile(r"^(?:" + "|".join(CAMPAIGN_CHANNELS) + r")[0-9]{2}$")
# Device codes (referral.py hands them out): exactly six characters from an
# alphabet without 0/O/1/I, so they read aloud unambiguously.
DEVICE_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
DEVICE_CODE_LEN = 6
# '#' is outside the device-id pattern POST /api/chat/sessions admits, so no
# client can mint a session as a campaign and read its invite count.
CAMPAIGN_OWNER_PREFIX = "campaign#"

UTM_KEYS = ("utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content")
UTM_MAX_CHARS = 100  # GA4 truncates campaign dimensions at 100

# referral_clicks bounds (audit M8: these routes sit outside /api, so the rate
# limiter never sees them). Eight public routes write here, into the app-wide
# SQLite, so every bound is about writes.
_CLICK_REFRESH_WINDOW = "-10 minutes"
_CLICK_FRESH_WINDOW = "-60 seconds"  # same IP and code again: no write at all
MAX_CLICKS_PER_IP_PER_HOUR = 20      # per IPv4 address or IPv6 /64
MAX_NEW_CLICKS_PER_MINUTE = 300      # across everyone; a viral post is far below
CLICK_RAW_RETENTION_DAYS = 7         # then folded into referral_click_days
_MAX_UA_CHARS = 256
# Browsers that load a page speculatively say so; that is not a visit.
_PREFETCH_HEADERS = ("sec-purpose", "purpose", "x-purpose", "x-moz")
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
    """`' da-01 '`, `'‏DA01،'`, `'DA٠١.'` → `'DA01'`; None when it cannot be a code.

    Codes arrive pasted out of chat messages: bidi and zero-width marks
    (Unicode category Cf) ride along invisibly, and the sentence goes on
    («DA01،»). So: drop Cf characters, read Eastern Arabic digits, drop
    separators, and take the first run of Latin letters and digits.
    """
    text = "".join(ch for ch in raw or "" if unicodedata.category(ch) != "Cf")
    text = _SEPARATORS.sub("", text.translate(_EASTERN_DIGITS))
    run = _FIRST_RUN.search(text)
    code = run.group(0).upper() if run else ""
    return code if CODE_RE.match(code) else None


def is_campaign_code(code: str | None) -> bool:
    """Two channel letters and two digits: DA01, WA02, KT17."""
    return bool(code) and bool(CAMPAIGN_RE.match(code))


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


def is_tagged(query: Mapping[str, str]) -> bool:
    """True when the URL carries attribution (?ref= or utm_*)."""
    return bool(query.get("ref")) or any(k.startswith("utm_") for k in query.keys())


def cache_control(query: Mapping[str, str]) -> str:
    """A tagged page carries that visitor's Play link: no shared cache may keep it."""
    return "private, no-store" if is_tagged(query) else "public, max-age=3600"


def is_prefetch(headers: Mapping[str, str]) -> bool:
    """Sec-Purpose / Purpose / X-Purpose / X-Moz: prefetch or preview."""
    for name in _PREFETCH_HEADERS:
        value = (headers.get(name) or "").lower()
        if "prefetch" in value or "preview" in value:
            return True
    return False


def ip_bucket(ip: str) -> str:
    """The unit a click is counted and matched by: an IPv4 address, or an IPv6 /64.

    A phone keeps its /64 but rotates the rest (privacy addresses), so the /64
    is what the AUTO claim has to match on; and per-address limits are worth
    nothing when one /64 holds 2^64 addresses.
    """
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return ip
    if addr.version == 6:
        if addr.ipv4_mapped:
            return str(addr.ipv4_mapped)
        return str(ipaddress.ip_network(f"{addr}/64", strict=False))
    return str(addr)


def attribute_visit(request) -> str:
    """The Play link for a public page visit; records the click if it carries a code.

    `request.client.host` is the visitor's address as ClientIPMiddleware
    resolved it — from trusted proxies only, never from a caller's header.
    """
    install_url, code = landing_attribution(request.query_params)
    if code and not is_prefetch(request.headers):
        ip = request.client.host if request.client else "unknown"
        record_click(ip, request.headers.get("user-agent", ""), code)
    return install_url


def record_click(ip: str, user_agent: str, code: str) -> None:
    """Remember that this IP followed this code, within bounds.

    The AUTO claim matches a first launch to the latest click from the same IP
    (IPv6: the same /64) within 24 h — the fallback when Play loses the referrer.

    * Only codes that can be claimed are recorded: an existing referral code or
      a well-formed campaign code. Random codes cannot fill the table.
    * Link-preview fetchers are not visitors, and never install the app.
    * The same IP and code again within 60 seconds writes nothing; within 10
      minutes it refreshes the row instead of adding one ("last link followed
      wins", without duplicates).
    * At most 20 new rows per IP per hour and 300 per minute overall; beyond
      that the page still renders, the click is just not recorded.
    * Nothing here can fail the page — not even opening the database.
    """
    if PREVIEW_FETCHER_RE.search(user_agent or ""):
        return
    bucket = ip_bucket(ip)
    conn = None
    try:
        conn = get_conn()
        if not is_campaign_code(code) and not conn.execute(
            "SELECT 1 FROM referral_codes WHERE code = ?", (code,)
        ).fetchone():
            return
        recent = conn.execute(
            "SELECT id, clicked_at > datetime('now', ?) AS fresh FROM referral_clicks "
            "WHERE ip = ? AND code = ? AND clicked_at > datetime('now', ?) "
            "ORDER BY id DESC LIMIT 1",
            (_CLICK_FRESH_WINDOW, bucket, code, _CLICK_REFRESH_WINDOW),
        ).fetchone()
        if recent:
            if recent["fresh"]:
                return
            conn.execute(
                "UPDATE referral_clicks SET clicked_at = datetime('now') WHERE id = ?",
                (recent["id"],),
            )
        else:
            (per_ip,) = conn.execute(
                "SELECT COUNT(*) FROM referral_clicks "
                "WHERE ip = ? AND clicked_at > datetime('now', '-1 hour')",
                (bucket,),
            ).fetchone()
            if per_ip >= MAX_CLICKS_PER_IP_PER_HOUR:
                return
            (per_minute,) = conn.execute(
                "SELECT COUNT(*) FROM referral_clicks "
                "WHERE clicked_at > datetime('now', '-1 minute')"
            ).fetchone()
            if per_minute >= MAX_NEW_CLICKS_PER_MINUTE:
                return
            conn.execute(
                "INSERT INTO referral_clicks (ip, user_agent, code) VALUES (?, ?, ?)",
                (bucket, (user_agent or "")[:_MAX_UA_CHARS], code),
            )
        conn.commit()
    except Exception:  # noqa: BLE001 — a click log must never break the page
        logger.warning("referral click not recorded", exc_info=True)
    finally:
        if conn is not None:
            conn.close()


def compact_referral_clicks(*, keep_days: int = CLICK_RAW_RETENTION_DAYS,
                            dry_run: bool = False) -> int:
    """Fold raw clicks older than `keep_days` into per-code daily counts.

    A raw row holds an IP and a user agent, and only the 24-hour AUTO match
    needs them; campaign_report.py needs the counts, for months. Link-preview
    fetches from before they stopped being recorded are dropped, not counted.
    Runs daily from ops/scripts/cron_push_triggers.py (no cron of its own).
    Returns the number of raw rows folded.
    """
    conn = get_conn()
    try:
        cutoff = f"-{int(keep_days)} days"
        if dry_run:
            (n,) = conn.execute(
                "SELECT COUNT(*) FROM referral_clicks WHERE clicked_at < datetime('now', ?)",
                (cutoff,),
            ).fetchone()
            return n
        conn.execute("BEGIN IMMEDIATE")
        rows = conn.execute(
            "SELECT id, code, user_agent, date(clicked_at) AS day FROM referral_clicks "
            "WHERE clicked_at < datetime('now', ?)",
            (cutoff,),
        ).fetchall()
        counts = Counter(
            (r["day"], r["code"]) for r in rows
            if not PREVIEW_FETCHER_RE.search(r["user_agent"] or "")
        )
        conn.executemany(
            "INSERT INTO referral_click_days (day, code, clicks) VALUES (?, ?, ?) "
            "ON CONFLICT(day, code) DO UPDATE SET clicks = clicks + excluded.clicks",
            [(day, code, n) for (day, code), n in counts.items()],
        )
        conn.executemany("DELETE FROM referral_clicks WHERE id = ?",
                         [(r["id"],) for r in rows])
        conn.commit()
        return len(rows)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
