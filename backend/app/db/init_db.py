"""
SQLite app database — جلسات ورسائل المحادثة + tokens + feedback
================================================================
Migration v2: added api_tokens table for device authentication.
Migration v3: added user_feedback table for 👍/👎 ratings.
Migration v4: added child_profiles + lesson_progress tables for the
              program layer (Phase 2). Endpoints that mutate these
              (POST /api/program/progress, POST /api/program/children)
              are not yet implemented — they land in a later phase.
"""
import os
import sqlite3
from pathlib import Path

_DEFAULT = Path(__file__).resolve().parents[3] / "ops" / "conversations.db"

SCHEMA_VERSION = 4


def db_path() -> Path:
    """Resolve the DB path at call time (so tests can override via env)."""
    return Path(os.environ.get("CONVERSATIONS_DB", str(_DEFAULT)))


def get_conn() -> sqlite3.Connection:
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
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
            role               TEXT NOT NULL,
            content            TEXT NOT NULL,
            domain             TEXT,
            severity           TEXT,
            mode               TEXT,
            needs_human_review INTEGER NOT NULL DEFAULT 0,
            created_at         TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS ix_chat_messages_session
            ON chat_messages (session_id);

        -- Migration v2: API tokens for mobile auth
        CREATE TABLE IF NOT EXISTS api_tokens (
            token       TEXT PRIMARY KEY,
            device_id   TEXT NOT NULL,
            session_id  TEXT NOT NULL
                         REFERENCES chat_sessions(id) ON DELETE CASCADE,
            created_at  TEXT NOT NULL DEFAULT (datetime('now')),
            expires_at  TEXT  -- NULL = no expiry (first-party mobile)
        );

        CREATE INDEX IF NOT EXISTS ix_api_tokens_device
            ON api_tokens (device_id);

        -- Migration v3: user feedback (👍/👎) per session
        CREATE TABLE IF NOT EXISTS user_feedback (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            rating     TEXT NOT NULL,    -- 'up' | 'down'
            comment    TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS ix_user_feedback_session
            ON user_feedback (session_id);

        -- Migration v4: program layer (curriculum tracking)
        -- child_profiles: one or more per device; tagged with the canonical
        -- age_group so the curriculum can filter paths/lessons/tips.
        CREATE TABLE IF NOT EXISTS child_profiles (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id   TEXT NOT NULL,
            name        TEXT NOT NULL,
            age_group   TEXT NOT NULL,  -- enum from CANONICAL_AGE_GROUPS
            gender      TEXT,
            created_at  TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS ix_child_profiles_device
            ON child_profiles (device_id);

        -- lesson_progress: a row per (device_id, lesson_id) — idempotent
        -- upserts. status flows not_started → in_progress → completed.
        -- completed_at drives streak calculation in Phase 6.
        CREATE TABLE IF NOT EXISTS lesson_progress (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id    TEXT NOT NULL,
            lesson_id    TEXT NOT NULL,
            path_id      TEXT NOT NULL,
            status       TEXT NOT NULL DEFAULT 'not_started',
                                      -- not_started | in_progress | completed
            started_at   TEXT,
            completed_at TEXT,
            updated_at   TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE (device_id, lesson_id)
        );

        CREATE INDEX IF NOT EXISTS ix_lesson_progress_device
            ON lesson_progress (device_id);

        CREATE INDEX IF NOT EXISTS ix_lesson_progress_path_device
            ON lesson_progress (device_id, path_id);
        """
    )
    row = conn.execute("SELECT version FROM schema_version LIMIT 1").fetchone()
    if row is None:
        conn.execute("INSERT INTO schema_version (version) VALUES (?)", (SCHEMA_VERSION,))
    elif row["version"] < SCHEMA_VERSION:
        conn.execute("UPDATE schema_version SET version = ?", (SCHEMA_VERSION,))
    conn.commit()
    conn.close()


def current_version() -> int:
    conn = get_conn()
    try:
        row = conn.execute("SELECT version FROM schema_version LIMIT 1").fetchone()
        return row["version"] if row else 0
    finally:
        conn.close()
