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

The fixed app mints one id. This module repairs installs already split:

  * at push registration and at a proof-carrying session mint, a twin that
    presents its own birth-minute credential is folded into its family
    (`fold_twin`, `resolve_mint`) — the families whose app came back as the
    twin;
  * `ops/tools/repair_device_twins.py` folds the backlog under the same rule
    (`fold_pair`), operator-run, dry run by default.

Folding re-keys the twin's rows to the family's id, so the family's history is
where the app now looks. It does NOT move everything:

  * tokens: only the twin's birth-window tokens (the one presented among them).
    A token minted for the twin id later — by anyone who learned the id while
    SESSION_MINT_ENFORCE is off — stays with the twin and opens nothing;
  * a row the family already has once (a unique key: referral code, "referred
    once", lesson state) stays under the twin id, untouched — a referral code
    the twin shared keeps resolving. The twin's push row is the one exception:
    it is the family's own FCM token twice, so it is deleted (and logged);
  * identity_links / user_backups never move: a Google link or a backup is a
    credential to the whole account across devices.

Every moved or deleted row is written to device_fold_log in the fold's own
transaction — `revert_fold` puts it all back.

The evidence — ALL of it, or nothing folds:

  1. cohort: both devices born (first api token) on or after COHORT_START, the
     day the first splitting build shipped, and the twin before the cutoff
     `TWIN_FOLD_BORN_BEFORE` (env; default about two weeks after the fixed
     build reaches Play). Outside it, no install can be a twin;
  2. the twin has no child profile;
  3. its push_tokens row holds an FCM token F — per app instance, so a second
     holder of F is the same installation;
  4. exactly one other holder of F has a child: the family's device;
  5. both were born within TWIN_WINDOW_SECONDS of each other — the split
     happens in an install's first seconds, and a birth time cannot be forged
     later;
  6. the family identity went quiet after its first session (FIRST_SESSION):
     the app no longer uses it, which is the only case where folding helps
     anyone. Measured 2026-10-04: every family whose app came back as the twin
     fell silent within 18 minutes of its birth; families still using their
     identity were active 20 h - 16 days later. A family in use is never
     folded into — that is what keeps a device planted next to someone's
     install, or a family that registered someone else's FCM token, out;
  7. at runtime, the credential presented is the twin's own, issued inside the
     birth window, and still live (an expired token proves a device for a
     mint, never for a fold).

`resolve_mint`: the proof decides. A mint whose claimed id differs from the
proven device, with no evidence above, is minted for the proven device (the
caller holds its token) — not refused.
"""
from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
from datetime import datetime, timedelta, timezone

from app.core.log_safety import describe_rejected_id, device_tag
from app.db.init_db import ensure_device_twin_tables, get_conn, hash_token
from app.models.api import DEVICE_ID_MAX_LENGTH, DEVICE_ID_PATTERN

logger = logging.getLogger(__name__)

# Measured on production (2026-10-04): pairs sharing an FCM token with one
# child-holder were born 33 within 2 s, 1 within 5 s, 5 within 60 s; the rest
# days apart (identity resets, not twins). A minute keeps the slow devices.
TWIN_WINDOW_SECONDS = 60

# The family identity's first session. Observed maximum for a family whose app
# came back as the twin: 18 minutes. Two hours is the margin.
FIRST_SESSION = timedelta(hours=2)

# 1.0.58 (the first build that splits) shipped on 2026-09-12. No install born
# before it can be a twin.
COHORT_START = datetime(2026, 9, 12)

# Twins stop being born once fresh installs get the fixed build. Set
# TWIN_FOLD_BORN_BEFORE (ISO date, UTC) to the day the fixed build reached 100%
# on Play plus 14 days; after it, nothing folds at all.
_DEFAULT_COHORT_END = "2026-10-25"

# Columns that name a device in some table — read against the live schema at
# run time (production has tables the declared schema does not).
DEVICE_COLUMNS = ("device_id", "referrer_device", "referred_device")

# Tables a fold never re-keys: its own bookkeeping, and the cross-device
# credentials (a Google link, an encrypted backup) — moving the twin's onto the
# family would hand whoever made them a way back in.
FOLD_EXCLUDED_TABLES = frozenset({"device_aliases", "device_fold_log", "identity_links", "user_backups"})

_VALID_ID = re.compile(DEVICE_ID_PATTERN)


# ── small pieces ──────────────────────────────────────────────────────────

def is_valid_device_id(device_id: str | None) -> bool:
    """The rule SessionCreate enforces. Ids stored before it existed (one with
    spaces and seven children, two of keystore garbage) fail it — and the app
    holding one is refused on every mint. fullmatch: Python's `$` would accept
    a trailing newline that pydantic and the app refuse."""
    return (isinstance(device_id, str) and 0 < len(device_id) <= DEVICE_ID_MAX_LENGTH
            and _VALID_ID.fullmatch(device_id) is not None)


def session_mint_enforced() -> bool:
    """Same switch as app.routers.chat — read per call so a restart flips it."""
    return os.environ.get("SESSION_MINT_ENFORCE", "").strip().lower() in {"1", "true", "yes"}


def cohort_end() -> datetime:
    raw = os.environ.get("TWIN_FOLD_BORN_BEFORE", "").strip() or _DEFAULT_COHORT_END
    return _when(raw) or _when(_DEFAULT_COHORT_END)


def _when(value) -> datetime | None:
    """A stored timestamp as naive UTC, whatever form a writer used."""
    if not value:
        return None
    text = str(value).strip()
    try:
        moment = datetime.fromisoformat(text[:-1] + "+00:00" if text.endswith("Z") else text)
    except ValueError:
        return None
    if moment.tzinfo is not None:
        moment = moment.astimezone(timezone.utc).replace(tzinfo=None)
    return moment


def _within_window(a: datetime | None, b: datetime | None) -> bool:
    return a is not None and b is not None and abs((a - b).total_seconds()) <= TWIN_WINDOW_SECONDS


def _in_cohort(born: datetime | None) -> bool:
    return born is not None and COHORT_START <= born < cohort_end()


def first_seen(conn: sqlite3.Connection, device_id: str) -> datetime | None:
    """When the device got its first token — its birth on this server."""
    stamps = [_when(r[0]) for r in conn.execute(
        "SELECT created_at FROM api_tokens WHERE device_id = ?", (device_id,))]
    stamps = [s for s in stamps if s]
    return min(stamps) if stamps else None


def child_count(conn: sqlite3.Connection, device_id: str) -> int:
    return conn.execute(
        "SELECT COUNT(*) FROM child_profiles WHERE device_id = ?", (device_id,)
    ).fetchone()[0]


# The app's own footprints under a device id. Server-side writes (pushes sent,
# tips generated) are deliberately not here: they happen whether or not anyone
# uses the identity.
_ACTIVITY = (
    "SELECT updated_at FROM push_tokens WHERE device_id = ?",
    "SELECT created_at FROM api_tokens WHERE device_id = ?",
    "SELECT m.created_at FROM chat_messages m JOIN chat_sessions s ON s.id = m.session_id "
    "WHERE s.device_id = ?",
    "SELECT COALESCE(updated_at, completed_at, started_at) FROM lesson_progress WHERE device_id = ?",
    "SELECT COALESCE(updated_at, created_at) FROM child_profiles WHERE device_id = ?",
)


def last_activity(conn: sqlite3.Connection, device_id: str) -> datetime | None:
    seen: list[datetime] = []
    for sql in _ACTIVITY:
        try:
            seen += [s for s in (_when(r[0]) for r in conn.execute(sql, (device_id,))) if s]
        except sqlite3.OperationalError:
            continue        # a table or column this schema does not have
    return max(seen) if seen else None


def went_quiet(conn: sqlite3.Connection, device_id: str) -> bool:
    """Nothing done under this identity after its first session."""
    born = first_seen(conn, device_id)
    last = last_activity(conn, device_id)
    return born is not None and (last is None or last <= born + FIRST_SESSION)


def _credential(conn: sqlite3.Connection, token: str | None):
    """(device, issued_at, live) of a bearer token, expired or not; None if unknown."""
    if not token:
        return None
    row = conn.execute(
        "SELECT device_id, created_at, expires_at FROM api_tokens WHERE token = ?",
        (hash_token(token),),
    ).fetchone()
    if not row:
        return None
    expires = _when(row[2])
    live = expires is None or expires > datetime.now(timezone.utc).replace(tzinfo=None)
    return row[0], _when(row[1]), live


# ── the evidence ──────────────────────────────────────────────────────────

def family_of(conn: sqlite3.Connection, device_id: str, *, within_cohort: bool = True) -> str | None:
    """Conditions (1)-(5): the family device the data says `device_id` split
    off from, or None. `within_cohort=False` is for the survey's report only."""
    if not device_id or child_count(conn, device_id):
        return None                                                     # (2)
    row = conn.execute(
        "SELECT token FROM push_tokens WHERE device_id = ?", (device_id,)
    ).fetchone()
    if not row or not row[0]:
        return None                                                     # (3)
    holders = [r[0] for r in conn.execute(
        "SELECT device_id FROM push_tokens WHERE token = ? AND device_id != ?",
        (row[0], device_id),
    )]
    with_children = [d for d in holders if child_count(conn, d)]
    if len(with_children) != 1:
        return None                                                     # (4)
    canonical = with_children[0]
    twin_born, family_born = first_seen(conn, device_id), first_seen(conn, canonical)
    if not _within_window(twin_born, family_born):
        return None                                                     # (5)
    if within_cohort and not (_in_cohort(twin_born) and _in_cohort(family_born)):
        return None                                                     # (1)
    return canonical


def twin_canonical(conn: sqlite3.Connection, device_id: str, *, credential: str | None) -> str | None:
    """All seven conditions, for a request presenting `credential`."""
    canonical = family_of(conn, device_id)
    if canonical is None:
        return None
    cred = _credential(conn, credential)
    if cred is None:
        return None
    holder, issued, live = cred
    if holder != device_id or not live:
        return None                                                     # (7)
    if not _within_window(issued, first_seen(conn, canonical)):
        return None                                                     # (7)
    if not went_quiet(conn, canonical):
        return None                                                     # (6)
    return canonical


# ── the fold ──────────────────────────────────────────────────────────────

def device_columns(conn: sqlite3.Connection, *, include_excluded: bool = False) -> list[tuple[str, str]]:
    """Every (table, column) that names a device, from the live schema."""
    out = []
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' "
        "ORDER BY name"
    )]
    for table in tables:
        if table in FOLD_EXCLUDED_TABLES and not include_excluded:
            continue
        cols = {r[1] for r in conn.execute(f'PRAGMA table_info("{table}")')}
        out.extend((table, c) for c in DEVICE_COLUMNS if c in cols)
    return out


def has_footprint(conn: sqlite3.Connection, device_id: str) -> bool:
    """Whether any row anywhere names this device (or it was folded away)."""
    for table, col in device_columns(conn, include_excluded=True):
        if table == "device_aliases":
            continue
        if conn.execute(f'SELECT 1 FROM "{table}" WHERE "{col}" = ? LIMIT 1',
                        (device_id,)).fetchone():
            return True
    try:
        return conn.execute(
            "SELECT 1 FROM device_aliases WHERE device_id = ? OR canonical_device = ? LIMIT 1",
            (device_id, device_id)).fetchone() is not None
    except sqlite3.OperationalError:
        return False


def _row_json(conn: sqlite3.Connection, table: str, rowid: int) -> str:
    cur = conn.execute(f'SELECT * FROM "{table}" WHERE rowid = ?', (rowid,))
    names = [d[0] for d in cur.description]
    return json.dumps(dict(zip(names, cur.fetchone())), ensure_ascii=False, default=str)


def _log(conn, table, rowid, column, from_device, to_device, action, row_json=None) -> None:
    conn.execute(
        "INSERT INTO device_fold_log (table_name, row_id, column_name, from_device, "
        "to_device, action, row_json) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (table, rowid, column, from_device, to_device, action, row_json),
    )


def _fold_rows(conn: sqlite3.Connection, alias: str, canonical: str, *,
               all_tokens: bool = False) -> dict[str, int]:
    """Re-key `alias`'s rows to `canonical`, logging each. Inside a transaction."""
    if alias == canonical:
        raise ValueError("a device cannot be folded into itself")
    ensure_device_twin_tables(conn)
    family_born = first_seen(conn, canonical)
    counts: dict[str, int] = {}
    for table, col in device_columns(conn):
        rows = conn.execute(f'SELECT rowid FROM "{table}" WHERE "{col}" = ?', (alias,)).fetchall()
        for (rowid,) in rows:
            if (table, col) == ("api_tokens", "device_id") and not all_tokens:
                issued = conn.execute("SELECT created_at FROM api_tokens WHERE rowid = ?",
                                      (rowid,)).fetchone()[0]
                if not _within_window(_when(issued), family_born):
                    counts["api_tokens.device_id:kept"] = counts.get("api_tokens.device_id:kept", 0) + 1
                    continue
            moved = conn.execute(f'UPDATE OR IGNORE "{table}" SET "{col}" = ? WHERE rowid = ?',
                                 (canonical, rowid)).rowcount
            if moved:
                _log(conn, table, rowid, col, alias, canonical, "moved")
                counts[f"{table}.{col}"] = counts.get(f"{table}.{col}", 0) + 1
            elif (table, col) == ("push_tokens", "device_id"):
                # The family's own FCM token twice: every push would arrive twice.
                _log(conn, table, rowid, col, alias, canonical, "deleted",
                     _row_json(conn, table, rowid))
                conn.execute("DELETE FROM push_tokens WHERE rowid = ?", (rowid,))
                counts["push_tokens.device_id:deleted"] = counts.get("push_tokens.device_id:deleted", 0) + 1
            else:
                # A row the family already has once: it stays with the twin.
                counts[f"{table}.{col}:kept"] = counts.get(f"{table}.{col}:kept", 0) + 1
    # The app in the field keeps the twin's id: remember where it went, and
    # re-point anything that had been folded into the twin.
    for (rowid,) in conn.execute("SELECT rowid FROM device_aliases WHERE canonical_device = ?",
                                 (alias,)).fetchall():
        conn.execute("UPDATE device_aliases SET canonical_device = ? WHERE rowid = ?", (canonical, rowid))
        _log(conn, "device_aliases", rowid, "canonical_device", alias, canonical, "moved")
    conn.execute(
        "INSERT INTO device_aliases (device_id, canonical_device) VALUES (?, ?) "
        "ON CONFLICT(device_id) DO UPDATE SET canonical_device = excluded.canonical_device, "
        "folded_at = datetime('now')",
        (alias, canonical),
    )
    return counts


def _locked(conn: sqlite3.Connection, decide, apply):
    """decide() under the write lock; apply(result) when it holds. One commit."""
    if conn.in_transaction:
        raise RuntimeError("needs a connection with no open transaction")
    conn.execute("BEGIN IMMEDIATE")
    try:
        result = decide()
        counts = apply(result) if result is not None else None
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    return result, counts


def fold_twin(conn: sqlite3.Connection, device_id: str, *, credential: str | None) -> str | None:
    """Fold `device_id` into its family if it is a twin presenting its own
    birth-minute credential. Returns the family's id, or None.

    Push registration calls this on every launch: the common answer is read
    without the write lock, and a candidate is decided again under it."""
    if twin_canonical(conn, device_id, credential=credential) is None:
        return None
    canonical, counts = _locked(
        conn,
        lambda: twin_canonical(conn, device_id, credential=credential),
        lambda family: _fold_rows(conn, device_id, family),
    )
    if canonical is not None:
        logger.warning("device twin %s folded into %s (%s)", device_tag(device_id), device_tag(canonical),
                       ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    return canonical


def recover(device_id: str | None, *, credential: str | None) -> str | None:
    """`fold_twin` on its own connection, never raising into the caller: a
    failed repair must not cost a parent their push registration."""
    if not device_id:
        return None
    try:
        conn = get_conn()
        try:
            return fold_twin(conn, device_id, credential=credential)
        finally:
            conn.close()
    except Exception:
        logger.exception("device twin check failed for %s", device_tag(device_id))
        return None


def repairable(conn: sqlite3.Connection, twin: str, family: str) -> str | None:
    """What the operator's repair may do with a pair the data shows (or None):

      app_runs_as_twin — the family went quiet, the twin is in use: the case
                         that cost a family their child;
      phantom          — the twin went quiet (whether or not the family did):
                         nobody uses it; folding stops double pushes and counts.
    A pair whose two halves are both in use is not folded."""
    if family_of(conn, twin) != family:
        return None
    twin_quiet = went_quiet(conn, twin)
    if went_quiet(conn, family) and not twin_quiet:
        return "app_runs_as_twin"
    if twin_quiet:
        return "phantom"
    return None


def fold_pair(conn: sqlite3.Connection, twin: str, family: str, *,
              all_tokens: bool = False) -> tuple[str | None, dict | None]:
    """The repair script's fold: the pair is re-checked under the write lock."""
    return _locked(conn, lambda: repairable(conn, twin, family),
                   lambda _kind: _fold_rows(conn, twin, family, all_tokens=all_tokens))


def revert_fold(conn: sqlite3.Connection, alias: str) -> int:
    """Undo every fold out of `alias`, newest first, from device_fold_log."""
    def undo():
        entries = conn.execute(
            "SELECT id, table_name, row_id, column_name, from_device, action, row_json "
            "FROM device_fold_log WHERE from_device = ? ORDER BY id DESC", (alias,)).fetchall()
        for _id, table, rowid, column, from_device, action, row_json in entries:
            if action == "moved":
                conn.execute(f'UPDATE "{table}" SET "{column}" = ? WHERE rowid = ?', (from_device, rowid))
            elif action == "deleted":
                row = json.loads(row_json)
                names = ", ".join(f'"{k}"' for k in row)
                conn.execute(f'INSERT INTO "{table}" (rowid, {names}) VALUES (?, {", ".join("?" * len(row))})',
                             [rowid, *row.values()])
        conn.execute("DELETE FROM device_aliases WHERE device_id = ?", (alias,))
        conn.execute("DELETE FROM device_fold_log WHERE from_device = ?", (alias,))
        return len(entries)
    reverted, _ = _locked(conn, undo, lambda _n: None)
    return reverted


# ── session minting ───────────────────────────────────────────────────────

def canonical_of(device_id: str | None, conn: sqlite3.Connection | None = None) -> str | None:
    """The family device a folded id now stands for, or None."""
    if not device_id:
        return None
    own = conn is None
    try:
        conn = conn or get_conn()
        try:
            row = conn.execute("SELECT canonical_device FROM device_aliases WHERE device_id = ?",
                               (device_id,)).fetchone()
        finally:
            if own:
                conn.close()
    except sqlite3.Error:
        return None
    return row[0] if row else None


def _move_refused(conn: sqlite3.Connection, refused: str, new: str) -> str | None:
    """The proven device's own id is one the API refuses; the app claims a fresh
    valid one. Move everything to it — tokens too: this is a rename of the
    caller's own device, and `new` has no row anywhere (re-checked locked)."""
    moved, counts = _locked(
        conn,
        lambda: new if (not is_valid_device_id(refused) and is_valid_device_id(new)
                        and not has_footprint(conn, new)) else None,
        lambda target: _fold_rows(conn, refused, target, all_tokens=True),
    )
    if moved:
        logger.warning("device on a refused id (%s) moved to %s (%s)", describe_rejected_id(refused),
                       device_tag(new), ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    return moved


def resolve_mint(claimed: str | None, proof_device: str, *, proof: str) -> str:
    """The device a proof-carrying mint is for. The proof decides.

      * a claimed id that was folded stands for its family device;
      * the proven device on a refused id, claiming a brand-new valid id, is
        moved to it;
      * the proven device being a twin that presents its own live birth-minute
        token, from an install whose family identity went quiet, is folded
        into the family, and the session is the family's;
      * otherwise the session is the proven device's — whatever was claimed.
    Any failure falls back to the last line."""
    try:
        conn = get_conn()
        try:
            claimed = canonical_of(claimed, conn) or claimed
            if (claimed and claimed != proof_device and not is_valid_device_id(proof_device)
                    and is_valid_device_id(claimed) and not has_footprint(conn, claimed)):
                moved = _move_refused(conn, proof_device, claimed)
                if moved:
                    return moved
            return fold_twin(conn, proof_device, credential=proof) or proof_device
        finally:
            conn.close()
    except Exception:
        logger.exception("device twin check failed at mint for %s", device_tag(proof_device))
        return proof_device


# ── account deletion ──────────────────────────────────────────────────────

def related_devices(conn: sqlite3.Connection, devices) -> set[str]:
    """`devices` plus every id folded into them or that they were folded into:
    one account. An account deletion must start from this set — rows a fold
    left under a twin id (kept tokens, unique-key rows, a Google link) belong
    to the same family."""
    found = set(devices)
    try:
        while True:
            marks = ",".join("?" * len(found))
            more = {r[0] for r in conn.execute(
                f"SELECT device_id FROM device_aliases WHERE canonical_device IN ({marks}) "
                f"UNION SELECT canonical_device FROM device_aliases WHERE device_id IN ({marks})",
                [*found, *found])}
            if more <= found:
                return found
            found |= more
    except sqlite3.OperationalError:
        return found


def forget_devices(conn: sqlite3.Connection, devices) -> dict[str, int]:
    """Erase the twin bookkeeping for these devices. Runs inside the caller's
    transaction (the account-deletion path, PR #26's erase_account)."""
    devices = list(devices)
    if not devices:
        return {}
    marks = ",".join("?" * len(devices))
    counts = {}
    try:
        counts["device_aliases"] = conn.execute(
            f"DELETE FROM device_aliases WHERE device_id IN ({marks}) "
            f"OR canonical_device IN ({marks})", [*devices, *devices]).rowcount
        counts["device_fold_log"] = conn.execute(
            f"DELETE FROM device_fold_log WHERE from_device IN ({marks}) "
            f"OR to_device IN ({marks})", [*devices, *devices]).rowcount
    except sqlite3.OperationalError:
        pass
    return counts
