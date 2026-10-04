"""Proof that a session holds the phone behind its device id — an FCM challenge.

Why it exists. A device id is not a secret: v1 child tokens carried it in the
clear, and until SESSION_MINT_ENFORCE is on, anyone who knows one can mint a
session for it. Account deletion, child memory and the destructive child
routes therefore ask for more than a session — proof that the session can
receive a message sent to the device's CURRENT push token (PR #26 review,
round 2: the earlier token-chain proof could lock a family out for good, and
let any pre-deploy token upgrade itself any number of times).

The flow (MOBILE_API.md §9.0):
  1. `POST /api/device-proof/start` — the server makes a single-use code with a
     short lifetime, sends it as a silent data message to the device's current
     push token, and answers `{challenge_id, expires_in}`. The code never
     appears in any response.
  2. The app receives `{type: "device_proof", challenge_id, code}` and posts it
     to `POST /api/device-proof/complete` with the SAME session token.
  3. That session is proven. The device row records when, and the push token
     the code was delivered to; the session row is what the guards read.

What "proven" means, exactly: the session completed a challenge, AND the push
token the code went to is still the device's current one. A new push token —
rotation, reinstall, another phone — ends every earlier proof of that device,
and the app proves again. Nothing depends on earlier tokens: any session can
prove itself at any time, any number of times.

Why the proof is per session as well as per device. If the device row alone
granted the rights, every session minted from a bare device id would ride on
the owner's proof — the probes that read memory through the assistant, deleted
a child, or deleted the account with an unproven session would all pass again.
So a session that did not complete a challenge itself is never proven.

The push-token cooldown (PR #26 review, round 3). A session can register any
FCM token for its device, so before SESSION_MINT_ENFORCE someone who knows a
device id could register a token they control and pass the challenge on it.
So a push token that replaced another without being vouched for pauses every
protected route for COOLDOWN_HOURS — even for a session proven on it — and the
previous token gets a notice (services/device_alerts.py). The owner, on opening
the app, re-registers their own token: the newcomer's proof is void, and the
owner's is good again at once.

Vouched for (routers/push.py → vouches_for) means the session registering the
new token holds a *clean* proof — one made outside any cooldown — of either
  * the token being replaced: the owner's own install rotating its FCM token
    (a proof of the current token also counts once that token's cooldown has
    run out — by then it is as settled as any), or
  * the new token itself: the owner taking their token back after a takeover.
A proof made during a cooldown is not clean, so it can never vouch: a newcomer
cannot hand the account to itself, rotate its way out of a cooldown, nor take
the account back from the owner.

A first token (none before) is not a change and warns no one — there is no
previous phone. But on an *established* device (anything older than the
cooldown: a session, a child) it pauses the irreversible routes — account
deletion, child deletion — for COOLDOWN_HOURS (round 4): 43% of devices with
children have no token on file, and without this anyone who knew one of their
ids could delete the account in one step. Memory stays open: it is empty there.
A brand-new install (nothing older than the cooldown) is not paused: its id has
not existed long enough to leak, and onboarding families delete mistakes.

What it cannot do: an owner who does not open the app for COOLDOWN_HOURS has no
one to answer the notice. Closing that is SESSION_MINT_ENFORCE's job (the PR
description's residual-risk section).

Hashes only: the code, the session token and the push token are compared as
sha256 digests and never stored in the clear here.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
import secrets
import sqlite3
from typing import NamedTuple, Optional

from app.core.log_safety import device_tag
from app.db.init_db import get_conn, hash_token

logger = logging.getLogger(__name__)

CODE_TTL_S = 300                 # five minutes: the app answers within seconds
MAX_ATTEMPTS = 5                 # wrong codes before a challenge is burnt
MAX_STARTS_PER_SESSION_HOUR = 5
MAX_STARTS_PER_DEVICE_HOUR = 20  # many sessions of one device: still bounded
DATA_TYPE = "device_proof"       # the data message's `type`
COOLDOWN_HOURS = 72              # after an unvouched push-token change


class Access(NamedTuple):
    """May this session use the protected routes right now?
    reason: None (yes) · "not_proven" · "cooldown" (until `available_at`, UTC)."""
    ok: bool
    reason: Optional[str] = None
    available_at: Optional[str] = None


class ProofError(Exception):
    """A start/complete that cannot succeed. `code` is the stable error code
    the app branches on; `reason` (complete only) says why, for logs."""

    def __init__(self, status: int, code: str, reason: Optional[str] = None):
        super().__init__(code)
        self.status = status
        self.code = code
        self.reason = reason


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _current_push_token(conn: sqlite3.Connection, device_id: str) -> Optional[str]:
    row = conn.execute(
        "SELECT token FROM push_tokens WHERE device_id = ?", (device_id,)
    ).fetchone()
    return row["token"] if row is not None and row["token"] else None


# ── Reading ───────────────────────────────────────────────────────────────


def session_proof(device_id: Optional[str], token: Optional[str]) -> Optional[str]:
    """When this session proved itself — or None if it is not proven now.

    Proven = it completed a challenge AND the push token the code went to is
    still the device's current one. Never raises: a guard that cannot read the
    database refuses, it does not grant.
    """
    if not device_id or not token:
        return None
    try:
        conn = get_conn()
        try:
            row = conn.execute(
                "SELECT s.push_token_hash, s.proven_at, p.token AS push_token "
                "FROM device_proof_sessions s "
                "JOIN push_tokens p ON p.device_id = s.device_id "
                "WHERE s.token_hash = ? AND s.device_id = ?",
                (hash_token(token), device_id),
            ).fetchone()
        finally:
            conn.close()
    except sqlite3.Error:
        logger.warning("device proof: could not read the proof", exc_info=True)
        return None
    if row is None or not row["push_token"]:
        return None
    if not hmac.compare_digest(row["push_token_hash"], _sha(row["push_token"])):
        return None
    return row["proven_at"]


def is_proven(device_id: Optional[str], token: Optional[str]) -> bool:
    return session_proof(device_id, token) is not None


def cooldown_until(conn: sqlite3.Connection, device_id: str,
                   irreversible: bool = False) -> Optional[str]:
    """When the protected routes open again ('YYYY-MM-DD HH:MM:SS', UTC), or
    None if they are not paused. An unvouched change pauses them all; the first
    token of an established device pauses only the `irreversible` ones."""
    row = conn.execute(
        "SELECT datetime(token_since, ?) AS until, "
        "       datetime(token_since, ?) > datetime('now') AS cooling, "
        "       token_vouched, token_first "
        "FROM push_tokens WHERE device_id = ?",
        (f"+{COOLDOWN_HOURS} hours", f"+{COOLDOWN_HOURS} hours", device_id),
    ).fetchone()
    if row is None or row["until"] is None or not row["cooling"]:
        return None
    if not row["token_vouched"]:
        return row["until"]
    if irreversible and row["token_first"]:
        return row["until"]
    return None


def established(conn: sqlite3.Connection, device_id: str) -> bool:
    """Has this device anything older than the cooldown — a session or a child?
    (api_tokens and chat_sessions are never purged, and a newcomer cannot make
    an old device look new.)"""
    for table in ("api_tokens", "chat_sessions", "child_profiles"):
        if conn.execute(
            f"SELECT 1 FROM {table} WHERE device_id = ? "
            "AND created_at < datetime('now', ?) LIMIT 1",
            (device_id, f"-{COOLDOWN_HOURS} hours"),
        ).fetchone() is not None:
            return True
    return False


def access(device_id: Optional[str], token: Optional[str],
           irreversible: bool = False) -> Access:
    """Proven on the device's current push token, and that token is not in a
    cooldown that covers this route. Fails closed: an unreadable database
    grants nothing."""
    if session_proof(device_id, token) is None:
        return Access(False, "not_proven")
    try:
        conn = get_conn()
        try:
            until = cooldown_until(conn, device_id, irreversible=irreversible)
        finally:
            conn.close()
    except sqlite3.Error:
        logger.warning("device proof: could not read the cooldown", exc_info=True)
        return Access(False, "not_proven")
    if until is not None:
        return Access(False, "cooldown", until)
    return Access(True)


def vouches_for(conn: sqlite3.Connection, device_id: str, session_token: Optional[str],
                old_token: str, new_token: str) -> bool:
    """Is this push-token change made by a session with a clean proof of the
    token being replaced, or of the new one? (Module docstring.)"""
    if not session_token:
        return False
    row = conn.execute(
        "SELECT push_token_hash, clean FROM device_proof_sessions "
        "WHERE token_hash = ? AND device_id = ?",
        (hash_token(session_token), device_id),
    ).fetchone()
    if row is None:
        return False
    if hmac.compare_digest(row["push_token_hash"], _sha(old_token)):
        # A rotation by the install that proved the current token: clean, or
        # proven on a token whose cooldown — of either kind — has run out.
        return bool(row["clean"]) or cooldown_until(conn, device_id, irreversible=True) is None
    if hmac.compare_digest(row["push_token_hash"], _sha(new_token)):
        return bool(row["clean"])          # taking back a token it proved, cleanly
    return False


def ever_proven(device_id: Optional[str]) -> bool:
    """Has any session of this device ever completed a challenge? From then
    on its destructive child routes need a proof too (core/proof.py). Fails
    closed: an unreadable table counts as enrolled."""
    if not device_id:
        return False
    try:
        conn = get_conn()
        try:
            return conn.execute(
                "SELECT 1 FROM device_proofs WHERE device_id = ?", (device_id,)
            ).fetchone() is not None
        finally:
            conn.close()
    except sqlite3.Error:
        logger.warning("device proof: could not read enrolment", exc_info=True)
        return True


def required_for_every_device() -> bool:
    """True once the forced-update floor (MINIMUM_BUILD_NUMBER) has reached the
    build that can answer a challenge (CHILD_MEMORY_MIN_BUILD): from then on no
    supported client is unable to prove, and the destructive child routes stop
    exempting devices that never did."""
    from app.services.child_memory import memory_min_build

    min_build = memory_min_build()
    try:
        floor = int(os.environ.get("MINIMUM_BUILD_NUMBER", "0") or 0)
    except ValueError:
        floor = 0
    return min_build is not None and floor >= min_build


def status(device_id: str, token: str) -> dict:
    proven_at = session_proof(device_id, token)
    conn = get_conn()
    try:
        push = _current_push_token(conn, device_id)
        until = cooldown_until(conn, device_id)
        deletions = cooldown_until(conn, device_id, irreversible=True)
    finally:
        conn.close()
    return {
        "proven": proven_at is not None,
        "proven_at": proven_at,
        "push_registered": push is not None,
        # Every protected route paused until then (UTC): an unvouched change.
        "cooldown_until": until,
        # Account and child deletion paused until then (UTC): either kind.
        "deletion_paused_until": deletions,
    }


# ── Start ─────────────────────────────────────────────────────────────────


def start(device_id: str, token: str) -> dict:
    """Make a code, send it to the device's current push token, return the id.

    Raises ProofError: 409 `no_push_token` (nothing registered, or FCM says the
    registered token is dead), 429 `proof_rate_limited`, 503 `push_unavailable`.
    """
    from app.services import push_sender

    token_hash = hash_token(token)
    code = secrets.token_urlsafe(24)
    conn = get_conn()
    try:
        conn.execute("BEGIN IMMEDIATE")
        push_token = _current_push_token(conn, device_id)
        if push_token is None:
            conn.rollback()
            raise ProofError(409, "no_push_token")
        # Housekeeping: nothing older than a day is worth keeping.
        conn.execute("DELETE FROM device_proof_challenges "
                     "WHERE created_at < datetime('now', '-1 day')")
        mine, everyone = conn.execute(
            "SELECT COALESCE(SUM(token_hash = ?), 0), COUNT(*) FROM device_proof_challenges "
            "WHERE device_id = ? AND created_at >= datetime('now', '-1 hour')",
            (token_hash, device_id),
        ).fetchone()
        if mine >= MAX_STARTS_PER_SESSION_HOUR or everyone >= MAX_STARTS_PER_DEVICE_HOUR:
            conn.commit()
            raise ProofError(429, "proof_rate_limited")
        # One live code per session: a new start retires the previous one.
        conn.execute(
            "UPDATE device_proof_challenges SET used_at = datetime('now') "
            "WHERE device_id = ? AND token_hash = ? AND used_at IS NULL",
            (device_id, token_hash),
        )
        cur = conn.execute(
            "INSERT INTO device_proof_challenges "
            "(device_id, token_hash, code_hash, push_token_hash, expires_at) "
            "VALUES (?, ?, ?, ?, datetime('now', ?))",
            (device_id, token_hash, _sha(code), _sha(push_token), f"+{CODE_TTL_S} seconds"),
        )
        challenge_id = cur.lastrowid
        conn.commit()
    except ProofError:
        raise
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    sent = push_sender.send_data_message(
        push_token,
        {"type": DATA_TYPE, "challenge_id": str(challenge_id), "code": code},
        ttl_seconds=CODE_TTL_S,
    )
    if sent.get("sent"):
        return {"challenge_id": challenge_id, "expires_in": CODE_TTL_S}
    _burn(challenge_id)
    if sent.get("reason") == "unregistered":
        # The registered token is dead: forget it, so the app's next launch
        # registers a live one, and say so instead of waiting for a code
        # that can never arrive.
        push_sender.remove_token_if_current(device_id, push_token)
        raise ProofError(409, "no_push_token")
    logger.warning("device proof: send failed for %s (%s)", device_tag(device_id),
                   sent.get("error"))
    raise ProofError(503, "push_unavailable")


def _burn(challenge_id: int) -> None:
    conn = get_conn()
    try:
        conn.execute("UPDATE device_proof_challenges SET used_at = datetime('now') "
                     "WHERE id = ? AND used_at IS NULL", (challenge_id,))
        conn.commit()
    finally:
        conn.close()


# ── Complete ──────────────────────────────────────────────────────────────


def complete(device_id: str, token: str, challenge_id: int, code: str) -> dict:
    """Check the code and prove this session. Raises ProofError
    (`proof_failed`, with a reason) — the app's answer to any of them is to
    start again."""
    token_hash = hash_token(token)
    conn = get_conn()
    failure: Optional[ProofError] = None
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT *, expires_at <= datetime('now') AS expired "
            "FROM device_proof_challenges WHERE id = ? AND device_id = ?",
            (challenge_id, device_id),
        ).fetchone()
        burn = False
        if row is None:
            failure = ProofError(404, "proof_failed", "not_found")
        elif row["used_at"] is not None:
            failure = ProofError(409, "proof_failed", "used")
        elif row["expired"]:
            failure, burn = ProofError(409, "proof_failed", "expired"), True
        elif not hmac.compare_digest(row["token_hash"], token_hash):
            # Only the session that asked may answer. Otherwise the owner's app,
            # posting back a code it received, would prove a stranger's session
            # that started the challenge. The code reached the wrong session:
            # it is spent either way.
            failure, burn = ProofError(409, "proof_failed", "other_session"), True
        elif not hmac.compare_digest(row["code_hash"], _sha(code or "")):
            attempts = int(row["attempts"]) + 1
            conn.execute("UPDATE device_proof_challenges SET attempts = ? WHERE id = ?",
                         (attempts, challenge_id))
            failure, burn = ProofError(409, "proof_failed", "wrong_code"), attempts >= MAX_ATTEMPTS
        else:
            push = _current_push_token(conn, device_id)
            if push is None or not hmac.compare_digest(row["push_token_hash"], _sha(push)):
                # The code went to a push token this device no longer has —
                # whoever holds that token now is not this device.
                failure, burn = ProofError(409, "proof_failed", "push_token_changed"), True
        if failure is not None:
            if burn:
                conn.execute("UPDATE device_proof_challenges SET used_at = datetime('now') "
                             "WHERE id = ?", (challenge_id,))
            conn.commit()
            raise failure

        push_hash = row["push_token_hash"]
        # A proof made during a cooldown of either kind proves this session
        # (usable once the cooldown ends) but is not clean: it cannot vouch for
        # a token change while that token is still cooling (vouches_for).
        clean = cooldown_until(conn, device_id, irreversible=True) is None
        conn.execute("UPDATE device_proof_challenges SET used_at = datetime('now') "
                     "WHERE id = ?", (challenge_id,))
        conn.execute(
            "INSERT INTO device_proof_sessions "
            "(token_hash, device_id, push_token_hash, proven_at, clean) "
            "VALUES (?, ?, ?, datetime('now'), ?) "
            "ON CONFLICT(token_hash) DO UPDATE SET device_id = excluded.device_id, "
            "push_token_hash = excluded.push_token_hash, proven_at = excluded.proven_at, "
            "clean = excluded.clean",
            (token_hash, device_id, push_hash, 1 if clean else 0),
        )
        # Enrolment only ever adds a requirement (a proof for child deletion),
        # so every completed proof enrols the device.
        conn.execute(
            "INSERT INTO device_proofs (device_id, push_token_hash, proven_at, "
            "first_proven_at) VALUES (?, ?, datetime('now'), datetime('now')) "
            "ON CONFLICT(device_id) DO UPDATE SET "
            "push_token_hash = excluded.push_token_hash, proven_at = excluded.proven_at",
            (device_id, push_hash),
        )
        # Sessions that no longer exist keep nothing behind.
        conn.execute(
            "DELETE FROM device_proof_sessions WHERE device_id = ? AND token_hash NOT IN "
            "(SELECT token FROM api_tokens WHERE device_id = ?)",
            (device_id, device_id),
        )
        proven_at = conn.execute(
            "SELECT proven_at FROM device_proof_sessions WHERE token_hash = ?", (token_hash,)
        ).fetchone()["proven_at"]
        conn.commit()
    except ProofError:
        raise
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    logger.info("device proof: session proven for %s", device_tag(device_id))
    return {"proven": True, "proven_at": proven_at}
