"""
SQLite app database — جلسات ورسائل المحادثة
=============================================
Holds server-side conversation state (chat_sessions, chat_messages) so the
future mobile client only sends a session_id + new message, and history
survives app restarts / device changes.

Migration discipline (a lightweight echo of analytics-platform's Alembic
lesson): every table is created with `IF NOT EXISTS`, and a `schema_version`
row lets future versions run ordered, idempotent migration steps instead of
silently diverging.

DB path is env-overridable (CONVERSATIONS_DB) for Docker / tests.
"""
import os
import sqlite3
from pathlib import Path

_DEFAULT = Path(__file__).resolve().parents[3] / "ops" / "conversations.db"
DB_PATH = Path(os.environ.get("CONVERSATIONS_DB", str(_DEFAULT)))

SCHEMA_VERSION = 1


def get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    """Create tables if missing and stamp schema_version. Idempotent."""
    conn = get_conn()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS chat_sessions (
            id          TEXT PRIMARY KEY,
            device_id   TEXT,
            created_at  TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at  TEXT NOT NULL DEFAULT (datetime('now')),
            metadata    TEXT
        );

        CREATE TABLE IF NOT EXISTS chat_messages (
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id         TEXT NOT NULL
                                 REFERENCES chat_sessions(id) ON DELETE CASCADE,
            role               TEXT NOT NULL,          -- 'user' | 'assistant'
            content            TEXT NOT NULL,
            domain             TEXT,
            severity           TEXT,
            mode               TEXT,
            needs_human_review INTEGER NOT NULL DEFAULT 0,
            created_at         TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS ix_chat_messages_session
            ON chat_messages (session_id);
        """
    )
    row = conn.execute("SELECT version FROM schema_version LIMIT 1").fetchone()
    if row is None:
        conn.execute("INSERT INTO schema_version (version) VALUES (?)", (SCHEMA_VERSION,))
    conn.commit()
    conn.close()


def current_version() -> int:
    conn = get_conn()
    try:
        row = conn.execute("SELECT version FROM schema_version LIMIT 1").fetchone()
        return row["version"] if row else 0
    finally:
        conn.close()
