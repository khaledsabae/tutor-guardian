"""What the three family programs share: content, age, the family's clock.

The programs are content-first: «رمضان العائلة», «رحلة الصلاة» and the
proactive milestones are written in `knowledge_base/curriculum/programs/`
(PR #23, documented in `knowledge_base/curriculum/schema.md` §8) and the
server's job is to pick the right piece for a child on a day — not to
re-author it. So nothing here invents text; every string a parent or child
reads comes out of those files, in their language (`content_lang`).

Four rules every program endpoint inherits from this module:

* **Age by birth month when known, else by band.** A child's optional
  `birth_month` (YYYY-MM) beats a stale `age_group` the parent picked two
  years ago; without it, the band decides (schema.md §8.3/§8.4). Responses
  say which one was used (`age.basis`).
* **The family's own date.** The day is computed from the UTC offset the app
  sends, never guessed: the Ramadan day, the prayer week and the milestone
  month all turn over at the family's midnight, not the server's. An offset
  the app never sent is never invented for a push either (milestone_push).
* **A feature the app cannot show is not promised.** `requires_feature`
  content is shown only when the server serves the feature AND the client
  says it can show it; otherwise its `fallback_text` is (`features_for`).
* **Read-only content.** The parsed files are cached and shared between
  requests — nothing here mutates them; responses are built from copies.
"""
from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Optional

from app.db.init_db import get_conn
from app.services import content_lang

logger = logging.getLogger(__name__)

PROGRAMS_DIR = (
    Path(__file__).resolve().parents[3] / "knowledge_base" / "curriculum" / "programs"
)

# Same bounds as the child surface (child_budget): UTC-12 … UTC+14.
MIN_TZ_OFFSET_MINUTES = -12 * 60
MAX_TZ_OFFSET_MINUTES = 14 * 60

_UTC = timezone.utc


class ProgramUnavailable(Exception):
    """The program file is missing, unreadable or unpublished."""


class ChildNotFound(Exception):
    """The child does not exist or belongs to another device."""


# ── Content ────────────────────────────────────────────────────────────────

def lang_code(lang: Optional[str]) -> str:
    """'en' or 'ar' — the two languages the programs ship in."""
    return content_lang.normalise(lang) or "ar"


@lru_cache(maxsize=16)
def _parse(path: str, mtime_ns: int) -> dict:  # noqa: ARG001 — mtime keys the cache
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _read(path: Path) -> Optional[dict]:
    try:
        doc = _parse(str(path), path.stat().st_mtime_ns)
    except (OSError, ValueError) as exc:
        logger.warning("program file unreadable: %s (%s)", path.name, exc)
        return None
    return doc if doc.get("is_published", False) else None


def load_program(name: str, lang: Optional[str] = None) -> dict:
    """The program in the reader's language, else in Arabic.

    The translation is preferred; a translation that is missing, broken or
    unpublished falls back to the Arabic source rather than hiding the
    program (content_lang's rule: Arabic they cannot read is better than a
    false "this does not exist for your child").
    """
    path = content_lang.localised(PROGRAMS_DIR, f"{name}.json", lang)
    doc = _read(path)
    if doc is None and path != PROGRAMS_DIR / f"{name}.json":
        doc = _read(PROGRAMS_DIR / f"{name}.json")
    if doc is None:
        raise ProgramUnavailable(name)
    return doc


def evidence_for(doc: dict, ids: Optional[Iterable[str]]) -> list[dict[str, Any]]:
    """The hadith cards an item points at, in the order it lists them.

    Hadith are shown only from these cards (schema.md §8.1) — free text says
    «الحديث المرفق» and never quotes — so every payload that carries
    `evidence_ids` carries the cards themselves.
    """
    by_id = {e.get("id"): e for e in doc.get("evidence", [])}
    out = []
    for eid in ids or ():
        card = by_id.get(eid)
        if card is None:
            continue
        out.append({k: card[k] for k in
                    ("id", "kind", "text_ar", "source", "provenance", "context", "meaning")
                    if k in card})
    return out


def arabic_digits(text: str) -> str:
    """Western digits → Arabic-Indic, as the Arabic UI writes them (١٤٤٨)."""
    return text.translate(str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩"))


def localise_number(value: Any, lang: str) -> str:
    text = str(value)
    return arabic_digits(text) if lang == "ar" else text


# ── Age ────────────────────────────────────────────────────────────────────

_BIRTH_MONTH = re.compile(r"^(\d{4})-(0[1-9]|1[0-2])$")

# A birth month may be up to this many months ahead (an expected baby —
# prenatal-1 covers pregnancy) and no further back than the app's oldest band.
BIRTH_MONTH_MAX_AHEAD_MONTHS = 10
BIRTH_MONTH_MAX_AGE_YEARS = 19


def parse_birth_month(value: Optional[str]) -> Optional[tuple[int, int]]:
    if not value:
        return None
    m = _BIRTH_MONTH.match(value.strip())
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def validate_birth_month(value: str, today: Optional[date] = None) -> str:
    """'YYYY-MM' within [today − 19 years, today + 10 months]; ValueError otherwise."""
    parsed = parse_birth_month(value)
    if parsed is None:
        raise ValueError("birth_month must be YYYY-MM (e.g. 2019-03)")
    today = today or datetime.now(_UTC).date()
    index = parsed[0] * 12 + parsed[1] - 1
    now_index = today.year * 12 + today.month - 1
    if index > now_index + BIRTH_MONTH_MAX_AHEAD_MONTHS:
        raise ValueError("birth_month is too far in the future")
    if index < now_index - BIRTH_MONTH_MAX_AGE_YEARS * 12:
        raise ValueError("birth_month is too far in the past")
    return f"{parsed[0]:04d}-{parsed[1]:02d}"


def age_in_months(birth_month: str, on: date) -> Optional[int]:
    """Whole calendar months from the birth month to `on`'s month.

    The day of birth is not stored, so a child counts as N months old from the
    first of the month in which they reach N — at most a month early, which
    every program here can absorb (the milestones alert a month ahead anyway).
    """
    parsed = parse_birth_month(birth_month)
    if parsed is None:
        return None
    return (on.year - parsed[0]) * 12 + (on.month - parsed[1])


def band_for_age_months(months: int) -> str:
    """The app band a known age falls in.

    Under a year is prenatal-1 (pregnancy → 1 year). One to three is 2-3:
    the taxonomy's split of the old 0-3 leaves the second year between the
    two labels, and a walking, scribbling one-year-old is closer to the 2-3
    content than to pregnancy content.
    """
    if months < 12:
        return "prenatal-1"
    years = months // 12
    for upper, band in ((4, "2-3"), (7, "4-6"), (10, "7-9"), (13, "10-12"), (16, "13-15")):
        if years < upper:
            return band
    return "16-18"


def child_age(row: sqlite3.Row | dict, on: date) -> dict[str, Any]:
    """{basis, band, months, years} for a child profile row on a date.

    `band` is the raw profile label when the birth month is unknown —
    including the legacy "0-3", which the programs' band maps name
    explicitly — so callers look it up in a program's `band_map` as is.
    """
    keys = row.keys() if hasattr(row, "keys") else ()
    birth_month = row["birth_month"] if "birth_month" in keys else None
    months = age_in_months(birth_month, on) if birth_month else None
    if months is not None:
        return {"basis": "birth_month", "band": band_for_age_months(months),
                "months": months, "years": months // 12 if months >= 0 else None}
    return {"basis": "age_group", "band": (row["age_group"] or "").strip(),
            "months": None, "years": None}


# ── The family's clock ─────────────────────────────────────────────────────

def validate_tz_offset(tz_offset_minutes: Optional[int]) -> Optional[int]:
    if tz_offset_minutes is None:
        return None
    if not (MIN_TZ_OFFSET_MINUTES <= tz_offset_minutes <= MAX_TZ_OFFSET_MINUTES):
        raise ValueError("tz_offset_minutes must be between -720 and 840")
    return int(tz_offset_minutes)


def as_of_enabled() -> bool:
    """`as_of` (a date override for QA) is honoured only when the server says
    so — off unless PROGRAMS_AS_OF_ENABLED is set. Read per call."""
    return os.environ.get("PROGRAMS_AS_OF_ENABLED", "").strip().lower() in {"1", "true", "yes"}


def _utcnow() -> datetime:
    return datetime.now(_UTC)


def local_today(tz_offset_minutes: Optional[int], now: Optional[datetime] = None) -> date:
    """The family's calendar date. An omitted offset reads as UTC for the
    response only — it is never stored as the family's offset."""
    moment = now or _utcnow()
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=_UTC)
    return (moment.astimezone(_UTC) + timedelta(minutes=tz_offset_minutes or 0)).date()


def parse_as_of(as_of: Optional[str]) -> Optional[date]:
    if not as_of:
        return None
    try:
        return date.fromisoformat(as_of)
    except ValueError as exc:
        raise ValueError("as_of must be YYYY-MM-DD") from exc


# ── Device settings (program_settings) ─────────────────────────────────────

def remember_device(device_id: str, tz_offset_minutes: Optional[int],
                    lang: Optional[str]) -> None:
    """Keep what the app told us about the family's clock and language.

    Only provided values are written; an omitted offset never erases a known
    one. The milestone push reads both: the hour it may send at, and the
    language it sends in.
    """
    if tz_offset_minutes is None and lang is None:
        return
    code = content_lang.normalise(lang) or ("ar" if lang else None)
    conn = get_conn()
    try:
        known = conn.execute(
            "SELECT tz_offset_minutes, lang FROM program_settings WHERE device_id = ?",
            (device_id,),
        ).fetchone()
        if known is not None and (tz_offset_minutes is None
                                  or known["tz_offset_minutes"] == tz_offset_minutes) \
                and (code is None or known["lang"] == code):
            return  # nothing new: a read stays a read
        conn.execute(
            """
            INSERT INTO program_settings (device_id, tz_offset_minutes, lang, updated_at)
            VALUES (?, ?, ?, datetime('now'))
            ON CONFLICT(device_id) DO UPDATE SET
                tz_offset_minutes = COALESCE(excluded.tz_offset_minutes,
                                             program_settings.tz_offset_minutes),
                lang = COALESCE(excluded.lang, program_settings.lang),
                updated_at = excluded.updated_at
            """,
            (device_id, tz_offset_minutes, code),
        )
        conn.commit()
    finally:
        conn.close()


def device_settings(device_id: str) -> dict[str, Any]:
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM program_settings WHERE device_id = ?", (device_id,)
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return {"tz_offset_minutes": None, "lang": None, "ramadan_year": None,
                "ramadan_shift_days": 0, "ramadan_days": None}
    return dict(row)


# ── Children ───────────────────────────────────────────────────────────────

def owned_child(device_id: str, child_id: int) -> sqlite3.Row:
    """The child row, if it belongs to this device. ChildNotFound otherwise —
    never "it exists but is not yours"."""
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM child_profiles WHERE id = ?", (child_id,)
        ).fetchone()
    finally:
        conn.close()
    if row is None or row["device_id"] != device_id:
        raise ChildNotFound(child_id)
    return row


def device_children(device_id: str) -> list[sqlite3.Row]:
    conn = get_conn()
    try:
        return conn.execute(
            "SELECT * FROM child_profiles WHERE device_id = ? ORDER BY created_at ASC, id ASC",
            (device_id,),
        ).fetchall()
    finally:
        conn.close()


def reached_puberty(device_id: str, child_id: int) -> bool:
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT reached_puberty FROM program_children WHERE child_id = ? AND device_id = ?",
            (child_id, device_id),
        ).fetchone()
    finally:
        conn.close()
    return bool(row and row["reached_puberty"])


def gender_of(row: sqlite3.Row | dict) -> Optional[str]:
    """'male' | 'female' | None. The column is free text (max 20); the app
    sends 'male'/'female', and nothing else is guessed at."""
    raw = (row["gender"] or "").strip().lower() if row["gender"] else ""
    if raw in {"male", "m", "boy", "ذكر", "ولد"}:
        return "male"
    if raw in {"female", "f", "girl", "أنثى", "انثى", "بنت"}:
        return "female"
    return None


# Rows of these tables are about one child (child_id = that child). Family
# rows (ramadan_marks with child_id 0, program_settings) are not. Nothing here
# deletes them: routers/privacy.erase_child (a proven child delete) and
# erase_account discover every table by child_id / device_id — this list is
# what tests/test_programs_privacy.py holds those sweeps to.
PER_CHILD_TABLES: tuple[str, ...] = (
    "program_children", "ramadan_fasting", "ramadan_marks",
    "prayer_journeys", "milestone_alerts",
)


# ── Feature gating ─────────────────────────────────────────────────────────

# A content item that `requires_feature: X` promises a screen. It is shown only
# when this server serves X (a request for the route below would be routed)
# AND the calling build can show it (the client lists X in `features`). Either
# alone is not enough: the endpoint without the screen is a promise the app
# cannot keep, and the screen without the endpoint is an empty page.
FEATURE_ROUTES: dict[str, tuple[str, str]] = {
    "weekly_plan": ("GET", "/api/children/0/weekly-plan"),
}


def _routes_to(app: Any, method: str, path: str) -> bool:
    """Would this app route `method path` to an endpoint?

    Asked through Starlette's routing contract (`route.matches`) rather than by
    reading `app.routes`: FastAPI 0.142 — production's — no longer copies an
    included router's routes into the app's list (it keeps one lazy
    `_IncludedRouter` per include), so a walk over `app.routes` finds nothing
    there while finding everything under 0.136. Matching works on both.
    """
    from starlette.routing import Match

    scope = {"type": "http", "method": method, "path": path, "root_path": "",
             "headers": [], "query_string": b""}
    router = getattr(app, "router", app)
    try:
        return any(route.matches(scope)[0] == Match.FULL
                   for route in getattr(router, "routes", None) or ())
    except Exception:  # noqa: BLE001 — unknown means unavailable, never a 500
        logger.warning("feature probe failed for %s %s", method, path, exc_info=True)
        return False


def server_features(app: Any) -> set[str]:
    return {feature for feature, (method, path) in FEATURE_ROUTES.items()
            if _routes_to(app, method, path)}


def parse_client_features(raw: Optional[str]) -> set[str]:
    if not raw:
        return set()
    return {f.strip().lower() for f in raw.split(",") if f.strip()}


def features_for(app: Any, client_raw: Optional[str]) -> set[str]:
    return server_features(app) & parse_client_features(client_raw)
