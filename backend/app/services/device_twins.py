"""
Device twins — one install that the app split into two device ids
=================================================================
From 1.0.58 to 1.0.67 every app process ran `main()` twice: an unused audio
package's plugin started a second Flutter engine (mobile/pubspec.yaml has the
story). On a fresh install each copy minted its own device id. The parent
onboarded in the visible copy, so the child belongs to one id; the headless
copy left a childless id holding the same FCM token — and whichever copy wrote
the keystore last is who the app is after a restart. For some families that is
the childless one: their child "vanished", though every row is still here.

The fixed app mints one id. This module repairs installs already split, from
both directions the app reaches us:

  * push registration (every launch) — `fold_twin` on the registering device;
  * session minting with a device proof (builds >= 106) — `resolve_mint`.

A twin is folded into the family's device: every row it owns is re-keyed to
the family's id, its tokens included, so the token the app holds now opens the
family's data. Nothing is copied and nothing of the family's is touched.

The evidence (`twin_canonical`) — ALL of it is required:

  1. the twin has no child profile;
  2. its push_tokens row holds an FCM token F. F is per app instance: a second
     holder of F is the same installation, not a neighbour;
  3. exactly one other holder of F has a child — the family's device;
  4. both were first seen (first api token) within TWIN_WINDOW_SECONDS. The
     split happens in an install's first seconds, and a creation time cannot be
     forged later: a stolen F can never point a new device at an old family;
  5. the credential presented belongs to one of the two. When it is the
     twin's own, it must have been issued in that same window — while
     SESSION_MINT_ENFORCE is off, anyone who learns a device id can mint a new
     token for it, and such a token never qualifies. Once enforcement is on,
     every token descends from a proof, so any of the twin's tokens will do.

Anything short of that — two devices with children, a token shared by devices
born days apart, a credential minted later — is left alone. The one-off
`ops/tools/repair_device_twins.py` applies the same rule to the backlog.
"""
from __future__ import annotations

import logging
import os
import sqlite3
from datetime import datetime

from app.core.log_safety import device_tag
from app.db.init_db import ensure_device_aliases_table, get_conn, hash_token

logger = logging.getLogger(__name__)

# Measured on production (2026-10-04): of the device pairs sharing an FCM token
# with exactly one child-holder, 25 were born within 5 s of each other, 5 more
# within 60 s, and the rest days apart (identity resets, not twins). A minute
# keeps the slow devices and nothing else.
TWIN_WINDOW_SECONDS = 60

# Columns that name a device in some table. Read against the live schema at run
# time — production has tables the declared schema does not (see
# fixtures-must-be-copied-not-written in the project notes).
DEVICE_COLUMNS = ("device_id", "referrer_device", "referred_device")


def session_mint_enforced() -> bool:
    """Same switch as app.routers.chat — read per call so a restart flips it."""
    return os.environ.get("SESSION_MINT_ENFORCE", "").strip().lower() in {"1", "true", "yes"}


def _when(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def first_seen(conn: sqlite3.Connection, device_id: str) -> datetime | None:
    """When the device got its first token — its birth on this server."""
    row = conn.execute(
        "SELECT MIN(created_at) FROM api_tokens WHERE device_id = ?", (device_id,)
    ).fetchone()
    return _when(row[0]) if row else None


def child_count(conn: sqlite3.Connection, device_id: str) -> int:
    return conn.execute(
        "SELECT COUNT(*) FROM child_profiles WHERE device_id = ?", (device_id,)
    ).fetchone()[0]


def _credential(conn: sqlite3.Connection, token: str | None) -> tuple[str, datetime | None] | None:
    """(device, issued_at) of a bearer token, expired or not; None if unknown."""
    if not token:
        return None
    row = conn.execute(
        "SELECT device_id, created_at FROM api_tokens WHERE token = ?", (hash_token(token),)
    ).fetchone()
    return (row[0], _when(row[1])) if row else None


def _within_window(a: datetime | None, b: datetime | None) -> bool:
    return a is not None and b is not None and abs((a - b).total_seconds()) <= TWIN_WINDOW_SECONDS


def family_of(conn: sqlite3.Connection, device_id: str) -> str | None:
    """Conditions (1)-(4): the family device the data says `device_id` split
    off from, or None. No credential involved — the operator's repair script
    uses exactly this; requests add (5) through `twin_canonical`."""
    if not device_id or child_count(conn, device_id):
        return None                                                     # (1)
    row = conn.execute(
        "SELECT token FROM push_tokens WHERE device_id = ?", (device_id,)
    ).fetchone()
    if not row or not row[0]:
        return None                                                     # (2)
    holders = [r[0] for r in conn.execute(
        "SELECT device_id FROM push_tokens WHERE token = ? AND device_id != ?",
        (row[0], device_id),
    )]
    with_children = [d for d in holders if child_count(conn, d)]
    if len(with_children) != 1:
        return None                                                     # (3)
    canonical = with_children[0]
    if not _within_window(first_seen(conn, device_id), first_seen(conn, canonical)):
        return None                                                     # (4)
    return canonical


def twin_canonical(
    conn: sqlite3.Connection, device_id: str, *, credential: str | None
) -> str | None:
    """The family device `device_id` split off from, or None — all five
    conditions of the module doc, for a request presenting `credential`."""
    canonical = family_of(conn, device_id)
    if canonical is None:
        return None
    cred = _credential(conn, credential)
    if cred is None:
        return None                                                     # (5)
    holder, issued = cred
    if holder == canonical:
        return canonical
    if holder != device_id:
        return None
    if not session_mint_enforced() and not _within_window(issued, first_seen(conn, canonical)):
        return None
    return canonical


def device_columns(conn: sqlite3.Connection) -> list[tuple[str, str]]:
    """Every (table, column) that names a device, from the live schema."""
    out = []
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' "
        "ORDER BY name"
    )]
    for table in tables:
        cols = {r[1] for r in conn.execute(f'PRAGMA table_info("{table}")')}
        out.extend((table, c) for c in DEVICE_COLUMNS if c in cols)
    return out


def _carry_push_census(conn: sqlite3.Connection, alias: str, canonical: str) -> None:
    """The twin's push row is the live one when the app runs as the twin: keep
    its token and build census on the family's row, which survives the fold."""
    conn.execute(
        """
        UPDATE push_tokens SET
            token        = (SELECT a.token FROM push_tokens a WHERE a.device_id = :alias),
            platform     = (SELECT a.platform FROM push_tokens a WHERE a.device_id = :alias),
            updated_at   = (SELECT a.updated_at FROM push_tokens a WHERE a.device_id = :alias),
            app_version  = COALESCE((SELECT a.app_version FROM push_tokens a
                                     WHERE a.device_id = :alias), app_version),
            build_number = COALESCE((SELECT a.build_number FROM push_tokens a
                                     WHERE a.device_id = :alias), build_number)
        WHERE device_id = :canonical
          AND EXISTS (SELECT 1 FROM push_tokens a WHERE a.device_id = :alias
                      AND a.updated_at >= push_tokens.updated_at)
        """,
        {"alias": alias, "canonical": canonical},
    )


def _fold_rows(conn: sqlite3.Connection, alias: str, canonical: str) -> dict[str, int]:
    """Re-key every row of `alias` to `canonical`. Must run inside a transaction.

    Where the family already has the row a unique key allows only once (its
    push row, referral code, the "referred once" claim the twin double-counted),
    the family's row stays and the twin's duplicate is dropped.
    """
    if alias == canonical:
        raise ValueError("a device cannot be folded into itself")
    has_push = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'push_tokens'"
    ).fetchone()
    if has_push:
        _carry_push_census(conn, alias, canonical)
    counts: dict[str, int] = {}
    for table, col in device_columns(conn):
        moved = conn.execute(
            f'UPDATE OR IGNORE "{table}" SET "{col}" = ? WHERE "{col}" = ?', (canonical, alias)
        ).rowcount
        dropped = conn.execute(f'DELETE FROM "{table}" WHERE "{col}" = ?', (alias,)).rowcount
        if moved:
            counts[f"{table}.{col}"] = moved
        if dropped:
            counts[f"{table}.{col}:dropped"] = dropped
    # The app keeps the twin's id on disk and will mint with it again: remember
    # where it went (and re-point anything that had been folded into the twin).
    ensure_device_aliases_table(conn)
    conn.execute(
        "INSERT INTO device_aliases (alias, canonical) VALUES (?, ?) "
        "ON CONFLICT(alias) DO UPDATE SET canonical = excluded.canonical, "
        "folded_at = datetime('now')",
        (alias, canonical),
    )
    conn.execute("UPDATE device_aliases SET canonical = ? WHERE canonical = ?", (canonical, alias))
    return counts


def canonical_of(device_id: str | None) -> str | None:
    """The family device a folded id now stands for, or None."""
    if not device_id:
        return None
    try:
        conn = get_conn()
        try:
            row = conn.execute(
                "SELECT canonical FROM device_aliases WHERE alias = ?", (device_id,)
            ).fetchone()
        finally:
            conn.close()
    except sqlite3.Error:
        return None
    return row[0] if row else None


def merge_device(conn: sqlite3.Connection, alias: str, canonical: str) -> dict[str, int]:
    """Fold `alias` into `canonical` in one transaction (the repair script's
    entry; it has already checked the evidence). Returns per-table counts."""
    if conn.in_transaction:
        raise RuntimeError("merge_device needs a connection with no open transaction")
    conn.execute("BEGIN IMMEDIATE")
    try:
        counts = _fold_rows(conn, alias, canonical)
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    return counts


def fold_twin(conn: sqlite3.Connection, device_id: str, *, credential: str | None) -> str | None:
    """If `device_id` is a split-off twin, fold it into the family's device.

    Returns the family's device id, or None when nothing was done. Push
    registration calls this on every launch, so the common answer — not a
    twin — is read without taking the write lock. A candidate is checked again
    inside one IMMEDIATE transaction with the fold, so the two engines of an
    old build registering at the same moment fold once, not twice.
    """
    if conn.in_transaction:
        raise RuntimeError("fold_twin needs a connection with no open transaction")
    if twin_canonical(conn, device_id, credential=credential) is None:
        return None
    conn.execute("BEGIN IMMEDIATE")
    try:
        canonical = twin_canonical(conn, device_id, credential=credential)
        counts = _fold_rows(conn, device_id, canonical) if canonical else {}
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    if canonical is not None:
        logger.warning("device twin %s folded into %s (%s)", device_tag(device_id),
                       device_tag(canonical), ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    return canonical


def recover(device_id: str | None, *, credential: str | None) -> str | None:
    """`fold_twin` on its own connection, never raising into the caller: a
    failed repair must not cost a parent their push registration or session."""
    if not device_id:
        return None
    try:
        conn = get_conn()
        try:
            return fold_twin(conn, device_id, credential=credential)
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("device twin check failed for %s", device_tag(device_id))
        return None


def resolve_mint(claimed: str | None, proof_device: str, *, proof: str) -> str | None:
    """The device a proof-carrying mint is for, or None to refuse (403).

    The proof decides, as before: a caller holding a token of device P mints
    for P, and a mint claiming another device C is refused — EXCEPT when C and
    P are the two halves of one split install. Then the caller (proven as one
    half) gets the family's half, and the other half is folded into it:

      * P is C's childless twin — the app on disk says C (the family) but its
        last token was the twin's: mint for C;
      * C is P's childless twin — the app on disk says the twin but still holds
        the family's token: mint for P.

    After that, whichever device it is, if it is itself a childless twin of the
    family's device it is folded too (the app came back as the twin).

    A claimed id that was already folded stands for its family device: the app
    in the field still has the twin's id on disk.
    """
    device = proof_device
    claimed = canonical_of(claimed) or claimed
    if claimed and claimed != proof_device:
        try:
            conn = get_conn()
            try:
                # Decide first, fold second: a refused mint changes nothing.
                if twin_canonical(conn, proof_device, credential=proof) == claimed:
                    fold_twin(conn, proof_device, credential=proof)
                    device = claimed
                elif twin_canonical(conn, claimed, credential=proof) == proof_device:
                    fold_twin(conn, claimed, credential=proof)
                    device = proof_device
                else:
                    return None
            finally:
                conn.close()
        except sqlite3.Error:
            logger.exception("device twin check failed at mint for %s", device_tag(proof_device))
            return None  # exactly what a mismatch got before: refused
    return recover(device, credential=proof) or device
