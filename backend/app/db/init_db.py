"""
SQLite app database — جلسات ورسائل المحادثة + tokens + feedback
================================================================
Migration v2: added api_tokens table for device authentication.
Migration v3: added user_feedback table for 👍/👎 ratings.
Migration v4: added child_profiles + lesson_progress tables for the
              program layer (Phase 2). Endpoints that mutate these
              (POST /api/program/progress, POST /api/program/children)
              are not yet implemented — they land in a later phase.
Migration v5: added avatar_emoji column to child_profiles (Phase 5
              Flutter UI requirement). Endpoints that mutate
              child_profiles + lesson_progress are implemented in
              routers/children.py and routers/program.py.
Migration v6: added coach_tips table for the proactive parenting coach.
              Stores the daily surfaced tip per (device_id, child_id, date)
              with lightweight engagement logging (shown_at, tapped_at).
              The `source` column is internal (generated|fallback).
Migration v7: added child_challenges table for «رحلة الطفل» — the parent's
              current challenge per child (sleep/lying/screens…). The active
              row feeds the proactive coach as a higher-priority signal than
              the most recent chat question (see coach_service).
"""
import os
import sqlite3
from pathlib import Path

_DEFAULT = Path(__file__).resolve().parents[3] / "ops" / "conversations.db"

_CREATE_COACH_TIPS: str = """
CREATE TABLE IF NOT EXISTS coach_tips (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id    TEXT NOT NULL,
    child_id     INTEGER NOT NULL,
    date         TEXT NOT NULL,
    domain       TEXT,
    text         TEXT NOT NULL,
    source       TEXT NOT NULL DEFAULT 'fallback',
    shown_at     TEXT,
    tapped_at    TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (device_id, child_id, date)
);
CREATE INDEX IF NOT EXISTS ix_coach_tips_device_date
    ON coach_tips (device_id, child_id, date);
"""

_CREATE_CHILD_CHALLENGES: str = """
CREATE TABLE IF NOT EXISTS child_challenges (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id     TEXT NOT NULL,
    child_id      INTEGER NOT NULL
                    REFERENCES child_profiles(id) ON DELETE CASCADE,
    challenge_key TEXT NOT NULL,
    topic         TEXT NOT NULL,
    domain        TEXT,
    status        TEXT NOT NULL DEFAULT 'active',  -- active | resolved
    note          TEXT,
    started_at    TEXT NOT NULL DEFAULT (datetime('now')),
    resolved_at   TEXT
);
CREATE INDEX IF NOT EXISTS ix_child_challenges_active
    ON child_challenges (device_id, child_id, status);
"""

_CREATE_REFERRALS: str = """
CREATE TABLE IF NOT EXISTS referral_codes (
    device_id  TEXT PRIMARY KEY,
    code       TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS referrals (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    referrer_device TEXT NOT NULL,
    referred_device TEXT NOT NULL UNIQUE,  -- a device can be referred only once
    code            TEXT NOT NULL,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_referrals_referrer
    ON referrals (referrer_device);
"""

SCHEMA_VERSION = 8


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
        f"""
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

        {_CREATE_COACH_TIPS}

        {_CREATE_CHILD_CHALLENGES}
        """
    )

    # ── Idempotent column-level migrations (added in later versions) ─────
    # Migration v5: avatar_emoji on child_profiles.
    _ensure_column(
        conn,
        table="child_profiles",
        column="avatar_emoji",
        ddl="ALTER TABLE child_profiles ADD COLUMN avatar_emoji TEXT",
    )

    _ensure_coach_tips_table(conn)
    _ensure_child_challenges_table(conn)
    _ensure_referrals_table(conn)

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


def _ensure_column(
    conn: sqlite3.Connection,
    *,
    table: str,
    column: str,
    ddl: str,
) -> None:
    """Run an ALTER TABLE ADD COLUMN only when the column is missing.

    SQLite has no `ADD COLUMN IF NOT EXISTS` (and `IF NOT EXISTS` on
    ALTER is rejected), so we look up the schema via `pragma_table_info`
    which is a cheap, in-memory metadata read.
    """
    cur = conn.execute(f"PRAGMA table_info({table})")
    names = {row[1] for row in cur.fetchall()}
    if column in names:
        return
    conn.execute(ddl)


def _ensure_coach_tips_table(conn: sqlite3.Connection) -> None:
    """Idempotent migration helper for the v6 coach_tips table."""
    try:
        cur = conn.execute("PRAGMA table_info(coach_tips)")
        names = {row[1] for row in cur.fetchall()}
    except sqlite3.Error:
        names = set()
    if not names:
        conn.executescript(_CREATE_COACH_TIPS)
        return
    for column, ddl in (
        ("domain", "ALTER TABLE coach_tips ADD COLUMN domain TEXT"),
        ("source", "ALTER TABLE coach_tips ADD COLUMN source TEXT NOT NULL DEFAULT 'fallback'"),
        ("shown_at", "ALTER TABLE coach_tips ADD COLUMN shown_at TEXT"),
        ("tapped_at", "ALTER TABLE coach_tips ADD COLUMN tapped_at TEXT"),
    ):
        if column not in names:
            conn.execute(ddl)


def _ensure_child_challenges_table(conn: sqlite3.Connection) -> None:
    """Idempotent migration helper for the v7 child_challenges table."""
    try:
        cur = conn.execute("PRAGMA table_info(child_challenges)")
        names = {row[1] for row in cur.fetchall()}
    except sqlite3.Error:
        names = set()
    if not names:
        conn.executescript(_CREATE_CHILD_CHALLENGES)


def _ensure_referrals_table(conn: sqlite3.Connection) -> None:
    """Idempotent migration helper for the v8 referral tables."""
    try:
        cur = conn.execute("PRAGMA table_info(referrals)")
        names = {row[1] for row in cur.fetchall()}
    except sqlite3.Error:
        names = set()
    if not names:
        conn.executescript(_CREATE_REFERRALS)
