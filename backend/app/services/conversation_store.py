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

from app.db.init_db import get_conn
from app.models.api import ConversationTurn


# ── Token Management ─────────────────────────────────────────────────────────

def generate_token() -> str:
    """Generate a cryptographically secure opaque token."""
    return "tg_" + secrets.token_hex(32)


def create_token(device_id: str, session_id: str) -> str:
    """Store a new auth token for the given device + session."""
    token = generate_token()
    conn = get_conn()
    conn.execute(
        "INSERT INTO api_tokens (token, device_id, session_id) VALUES (?, ?, ?)",
        (token, device_id, session_id),
    )
    conn.commit()
    conn.close()
    return token


def validate_token(token: str) -> dict | None:
    """Check a token is valid. Returns {device_id, session_id} or None."""
    conn = get_conn()
    try:
        row = conn.execute(
            """SELECT token, device_id, session_id
               FROM api_tokens
               WHERE token = ?
                 AND (expires_at IS NULL OR expires_at > datetime('now'))""",
            (token,),
        ).fetchone()
        if row:
            return {"device_id": row["device_id"], "session_id": row["session_id"]}
        return None
    finally:
        conn.close()


def get_device_id(token: str) -> str | None:
    """Extract device_id from a valid token (for rate-limiting)."""
    info = validate_token(token)
    return info["device_id"] if info else None


# ── Session Management ───────────────────────────────────────────────────────

def create_session(device_id: str | None = None, metadata: dict | None = None) -> str:
    sid = str(uuid.uuid4())
    conn = get_conn()
    conn.execute(
        "INSERT INTO chat_sessions (id, device_id, metadata) VALUES (?, ?, ?)",
        (sid, device_id, json.dumps(metadata or {}, ensure_ascii=False)),
    )
    conn.commit()
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


def add_message(
    session_id: str,
    role: str,
    content: str,
    *,
    domain: str | None = None,
    severity: str | None = None,
    mode: str | None = None,
    needs_human_review: bool = False,
) -> None:
    conn = get_conn()
    conn.execute(
        """INSERT INTO chat_messages
           (session_id, role, content, domain, severity, mode, needs_human_review)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (session_id, role, content, domain, severity, mode, int(needs_human_review)),
    )
    conn.execute(
        "UPDATE chat_sessions SET updated_at = datetime('now') WHERE id = ?",
        (session_id,),
    )
    conn.commit()
    conn.close()


def get_history(session_id: str, limit: int = 20) -> list[ConversationTurn]:
    """Return the last `limit` turns (chronological) as ConversationTurn objects."""
    conn = get_conn()
    try:
        rows = conn.execute(
            """SELECT role, content FROM chat_messages
               WHERE session_id = ? ORDER BY id DESC LIMIT ?""",
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
    skipped so the history list only shows real conversations."""
    conn = get_conn()
    try:
        rows = conn.execute(
            """
            SELECT s.id AS id,
                   s.updated_at AS updated_at,
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
        })
    return out
