"""
Conversation store — حفظ واسترجاع جلسات ورسائل المحادثة (server-side)
=====================================================================
Replaces the old client-only conversation history (lost on refresh, and
trusted blindly from the client). The mobile/web client now sends just a
session_id; the server owns the truth.
"""
import json
import uuid

from app.db.init_db import get_conn
from app.models.api import ConversationTurn


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
