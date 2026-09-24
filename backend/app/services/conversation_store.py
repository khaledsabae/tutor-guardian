"""
Conversation store — حفظ واسترجاع جلسات ورسائل المحادثة (server-side)
=====================================================================
Replaces the old client-only conversation history (lost on refresh, and
trusted blindly from the client). The mobile/web client now sends just a
session_id; the server owns the truth.

v2: Added token-based auth — create_session returns a Bearer token validated
    by middleware/auth.py.
"""
import json
import secrets
import uuid

from app.db.init_db import get_conn, hash_token, token_ttl_days
from app.models.api import ConversationTurn


# ── Token Management ─────────────────────────────────────────────────────────
#
# Only sha256(token) is stored (audit H5): a copy of the database, a backup or
# a log of SQL no longer hands out working credentials. Every token expires
# TOKEN_TTL_DAYS after it was last renewed; validation slides the expiry
# forward once less than half of it is left, so an app in regular use never
# sees it, and one that has been idle longer gets a 401 and mints a new
# session (proving continuity with the expired token, see token_device).

def generate_token() -> str:
    """Generate a cryptographically secure opaque token."""
    return "tg_" + secrets.token_hex(32)


def create_token(device_id: str, session_id: str) -> str:
    """Store a new auth token for the given device + session."""
    token = generate_token()
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO api_tokens (token, device_id, session_id, expires_at) "
            "VALUES (?, ?, ?, datetime('now', ?))",
            (hash_token(token), device_id, session_id, _ttl_modifier()),
        )
        conn.commit()
    finally:
        conn.close()
    return token


def validate_token(token: str) -> dict | None:
    """Check a token is valid. Returns {device_id, session_id} or None.

    Renews the expiry when less than half of the TTL remains.
    """
    if not token:
        return None
    digest = hash_token(token)
    conn = get_conn()
    try:
        row = conn.execute(
            """SELECT device_id, session_id,
                      expires_at < datetime('now', ?) AS due_for_renewal
               FROM api_tokens
               WHERE token = ?
                 AND (expires_at IS NULL OR expires_at > datetime('now'))""",
            (_half_ttl_modifier(), digest),
        ).fetchone()
        if not row:
            return None
        if row["due_for_renewal"]:
            conn.execute(
                "UPDATE api_tokens SET expires_at = datetime('now', ?) WHERE token = ?",
                (_ttl_modifier(), digest),
            )
            conn.commit()
        return {"device_id": row["device_id"], "session_id": row["session_id"]}
    finally:
        conn.close()


def token_device(token: str) -> str | None:
    """The device a token was issued to, whether or not it has expired.

    Only for proving continuity when minting a new session: holding a token
    this server issued to a device — even a lapsed one — is proof of that
    device, and an expired token must not lock its own install out once
    SESSION_MINT_ENFORCE is on. It is never an API credential.
    """
    if not token:
        return None
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT device_id FROM api_tokens WHERE token = ?", (hash_token(token),)
        ).fetchone()
        return row["device_id"] if row else None
    finally:
        conn.close()


def device_has_tokens(device_id: str) -> bool:
    """True once any token was ever issued for this device id."""
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT 1 FROM api_tokens WHERE device_id = ? LIMIT 1", (device_id,)
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def get_device_id(token: str) -> str | None:
    """Extract device_id from a valid token (for rate-limiting)."""
    info = validate_token(token)
    return info["device_id"] if info else None


def _ttl_modifier() -> str:
    return f"+{token_ttl_days()} days"


def _half_ttl_modifier() -> str:
    return f"+{token_ttl_days() * 12} hours"


# ── Session Management ───────────────────────────────────────────────────────

def create_session(device_id: str | None = None, metadata: dict | None = None) -> str:
    sid = str(uuid.uuid4())
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO chat_sessions (id, device_id, metadata) VALUES (?, ?, ?)",
            (sid, device_id, json.dumps(metadata or {}, ensure_ascii=False)),
        )
        conn.commit()
    finally:
        conn.close()
    return sid


def create_session_with_token(device_id: str | None = None, metadata: dict | None = None) -> tuple[str, str]:
    """Create a session and return (session_id, auth_token)."""
    # Normalize device_id
    if not device_id:
        device_id = f"device_{uuid.uuid4().hex[:12]}"
    sid = create_session(device_id, metadata)
    token = create_token(device_id, sid)
    return sid, token


def session_exists(session_id: str) -> bool:
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT 1 FROM chat_sessions WHERE id = ?", (session_id,)
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def session_owner(session_id: str) -> tuple[bool, str | None]:
    """(exists, device_id) for a session — the ownership check's one read.

    device_id is None for a session created without one (legacy rows).
    """
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT device_id FROM chat_sessions WHERE id = ?", (session_id,)
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return False, None
    return True, row["device_id"]


def add_message(
    session_id: str,
    role: str,
    content: str,
    *,
    domain: str | None = None,
    severity: str | None = None,
    mode: str | None = None,
    needs_human_review: bool = False,
) -> int:
    """Insert one message and return its rowid.

    The rowid matters for user messages: they are written *before* the
    classifier has run (so the question survives a failed answer), which
    leaves domain/severity NULL. The caller backfills them through
    `update_classification` once classification completes.
    """
    conn = get_conn()
    try:
        cur = conn.execute(
            """INSERT INTO chat_messages
               (session_id, role, content, domain, severity, mode, needs_human_review)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (session_id, role, content, domain, severity, mode, int(needs_human_review)),
        )
        message_id = cur.lastrowid
        conn.execute(
            "UPDATE chat_sessions SET updated_at = datetime('now') WHERE id = ?",
            (session_id,),
        )
        conn.commit()
    finally:
        conn.close()
    return message_id


def update_classification(
    message_id: int,
    *,
    domain: str | None = None,
    severity: str | None = None,
    needs_human_review: bool | None = None,
) -> None:
    """Backfill the classification of an already-written message.

    Every question is classified on the way in and the result was thrown
    away for user rows, which is why `coach_service.recent_parent_topic`
    (`WHERE role='user' AND domain IS NOT NULL`) could never match a row.
    Deliberately does not touch `chat_sessions.updated_at` — this is a
    late annotation of an existing turn, not new activity.
    """
    sets, params = [], []
    if domain is not None:
        sets.append("domain = ?")
        params.append(domain)
    if severity is not None:
        sets.append("severity = ?")
        params.append(severity)
    if needs_human_review is not None:
        sets.append("needs_human_review = ?")
        params.append(int(needs_human_review))
    if not sets:
        return
    params.append(message_id)
    conn = get_conn()
    try:
        conn.execute(
            f"UPDATE chat_messages SET {', '.join(sets)} WHERE id = ?", params
        )
        conn.commit()
    finally:
        conn.close()


def get_history(session_id: str, limit: int = 20) -> list[ConversationTurn]:
    """Return the last `limit` turns (chronological) as ConversationTurn objects."""
    conn = get_conn()
    try:
        # mode='error' rows carry a placeholder ("تعذّر توليد الرد…"), not an
        # answer. They are stored so a failed turn is countable instead of
        # silent — but feeding one back as prior assistant context would put
        # the apology into the next prompt. mode='interrupted' rows DO stay:
        # that text is a real partial answer the parent actually read.
        rows = conn.execute(
            """SELECT role, content FROM chat_messages
               WHERE session_id = ?
                 AND (mode IS NULL OR mode != 'error')
               ORDER BY id DESC LIMIT ?""",
            (session_id, limit),
        ).fetchall()
    finally:
        conn.close()
    rows = list(reversed(rows))
    return [ConversationTurn(role=r["role"], content=r["content"]) for r in rows]


def get_session(session_id: str) -> dict | None:
    """Full session with messages, or None if it doesn't exist."""
    conn = get_conn()
    try:
        s = conn.execute(
            "SELECT id, device_id, created_at, updated_at, metadata "
            "FROM chat_sessions WHERE id = ?",
            (session_id,),
        ).fetchone()
        if s is None:
            return None
        msgs = conn.execute(
            """SELECT role, content, domain, severity, mode, needs_human_review, created_at
               FROM chat_messages WHERE session_id = ? ORDER BY id ASC""",
            (session_id,),
        ).fetchall()
    finally:
        conn.close()
    return {
        "id": s["id"],
        "device_id": s["device_id"],
        "created_at": s["created_at"],
        "updated_at": s["updated_at"],
        "metadata": json.loads(s["metadata"] or "{}"),
        "messages": [
            {
                "role": m["role"],
                "content": m["content"],
                "domain": m["domain"],
                "severity": m["severity"],
                "mode": m["mode"],
                "needs_human_review": bool(m["needs_human_review"]),
                "created_at": m["created_at"],
            }
            for m in msgs
        ],
    }


def list_sessions(device_id: str, limit: int = 50) -> list[dict]:
    """Sessions belonging to a device, newest first, each with a title
    (its first user message) and a message count. Empty sessions are
    skipped so the history list only shows real conversations.

    The returned dict includes `metadata` so callers (e.g. proactive coach)
    can filter sessions by child_id without an extra round-trip.
    """
    conn = get_conn()
    try:
        rows = conn.execute(
            """
            SELECT s.id AS id,
                   s.updated_at AS updated_at,
                   s.metadata AS metadata,
                   (SELECT content FROM chat_messages
                     WHERE session_id = s.id AND role = 'user'
                     ORDER BY id ASC LIMIT 1) AS first_user,
                   (SELECT COUNT(*) FROM chat_messages
                     WHERE session_id = s.id) AS msg_count
            FROM chat_sessions s
            WHERE s.device_id = ?
            ORDER BY s.updated_at DESC
            LIMIT ?
            """,
            (device_id, limit),
        ).fetchall()
    finally:
        conn.close()
    out = []
    for r in rows:
        if not r["first_user"]:
            continue  # no real conversation yet
        title = r["first_user"].strip().replace("\n", " ")
        out.append({
            "id": r["id"],
            "title": title[:80],
            "message_count": r["msg_count"],
            "updated_at": r["updated_at"],
            "metadata": json.loads(r["metadata"] or "{}"),
        })
    return out
