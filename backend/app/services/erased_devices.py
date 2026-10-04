"""Erased devices — an account deleted in the app stays deleted.

After an in-app account deletion the app starts over as a new device
(MOBILE_API §10). But Android's Auto Backup can restore the old install's
storage on a reinstall — its device id, and the chat and children it had
cached — and the app then mints a session for that id: the account the parent
deleted "comes back" on the phone (review of PR #36). So every account erase
keeps, for each device id it removed, a one-way hash in `erased_devices` —
never the id — and a session mint that claims such an id without a live token
of it answers

    410 {"detail": {"code": "device_erased", "message": "…", "message_en": "…"}}

to an app build that knows what to do with it: wipe what the backup restored
and start over as a new device. Which builds know is ERASED_DEVICE_410_MIN_BUILD
(unset = none yet) against the `X-App-Build` header the app sends with the
mint. Every other mint is served exactly as before — a fresh, empty session —
so builds already on phones never break.

The same answer settles a deletion whose response was lost: a 410 for the
device id means the erase went through; a 201 means it did not (MOBILE_API §10).

The hash: HMAC-SHA256 under ERASED_DEVICE_PEPPER when that is set, else a
domain-separated SHA-256. The app's device ids are random UUIDv4s (122 bits),
so neither form can be turned back into an id; the pepper also covers the few
older ids that are not random. Lookups try both forms, so setting the pepper
later keeps every earlier tombstone working — but never change it once set:
tombstones written under the old value would stop matching.

Kept with no expiry: a backup can be restored long after the deletion, and the
hash says nothing about anyone without the id itself.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
import sqlite3
from typing import Iterable, Optional

from app.db.init_db import get_conn

logger = logging.getLogger(__name__)

TABLE = "erased_devices"
CREATE_TABLE = (
    "CREATE TABLE IF NOT EXISTS erased_devices ("
    " device_hash TEXT PRIMARY KEY,"
    " erased_at   TEXT NOT NULL DEFAULT (datetime('now')))"
)

BUILD_HEADER = "X-App-Build"
MIN_BUILD_ENV = "ERASED_DEVICE_410_MIN_BUILD"
PEPPER_ENV = "ERASED_DEVICE_PEPPER"
_DOMAIN = b"almorabbi:erased-device:v1:"

CODE = "device_erased"
MESSAGE = "حُذف هذا الحساب نهائيًا. سيبدأ التطبيق من جديد على هذا الهاتف."
MESSAGE_EN = "This account was deleted. The app will start over on this phone."


def _pepper() -> Optional[bytes]:
    raw = os.environ.get(PEPPER_ENV, "").strip()
    return raw.encode("utf-8") if raw else None


def _hash_forms(device_id: str) -> list[str]:
    """Every form a tombstone of `device_id` may have been written in — the
    current one first."""
    data = _DOMAIN + device_id.encode("utf-8")
    forms = [hashlib.sha256(data).hexdigest()]
    pepper = _pepper()
    if pepper is not None:
        forms.insert(0, hmac.new(pepper, data, hashlib.sha256).hexdigest())
    return forms


def device_hash(device_id: str) -> str:
    """What `erased_devices` stores for a device id (written now)."""
    return _hash_forms(device_id)[0]


def record(conn: sqlite3.Connection, device_ids: Iterable[str]) -> int:
    """Tombstone every id in `device_ids`, inside the caller's transaction —
    the erase's own (routers/privacy.erase_account): no tombstone without the
    erase, no erase without its tombstones. A repeat erase moves `erased_at`.
    Returns how many ids were recorded."""
    ids = sorted({d for d in device_ids if d})
    if not ids:
        return 0
    conn.execute(CREATE_TABLE)          # a store the v35 step has not reached yet
    conn.executemany(
        "INSERT INTO erased_devices (device_hash, erased_at) VALUES (?, datetime('now')) "
        "ON CONFLICT(device_hash) DO UPDATE SET erased_at = excluded.erased_at",
        [(device_hash(d),) for d in ids],
    )
    return len(ids)


def is_erased(device_id: Optional[str]) -> bool:
    """Was this device id removed by an account deletion? Fails open: an
    unreadable store must not stop anyone from minting a session."""
    if not device_id:
        return False
    forms = _hash_forms(device_id)
    try:
        conn = get_conn()
        try:
            row = conn.execute(
                f"SELECT 1 FROM erased_devices WHERE device_hash IN "
                f"({','.join('?' * len(forms))}) LIMIT 1", forms).fetchone()
        finally:
            conn.close()
    except sqlite3.Error as exc:
        logger.warning("erased devices: lookup failed (%s) — minting as before", exc)
        return False
    return row is not None


def min_build() -> Optional[int]:
    """The first app build that understands `410 device_erased`; None = off.
    Read per call, so the VPS can set it on restart and tests per case."""
    raw = os.environ.get(MIN_BUILD_ENV, "").strip()
    try:
        value = int(raw) if raw else 0
    except ValueError:
        return None
    return value if value > 0 else None


def app_build(headers) -> Optional[int]:
    """The build number the app sends in `X-App-Build`, or None."""
    raw = (headers.get(BUILD_HEADER) or "").strip()
    return int(raw) if raw.isdigit() and len(raw) <= 9 else None


def understands_410(headers) -> bool:
    """Is this mint from a build that handles `410 device_erased`?"""
    floor, build = min_build(), app_build(headers)
    return floor is not None and build is not None and build >= floor


def refusal() -> dict:
    """The 410 body's `detail`."""
    return {"code": CODE, "message": MESSAGE, "message_en": MESSAGE_EN}
