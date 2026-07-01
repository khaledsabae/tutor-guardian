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
Migration v8: added referral_codes + referrals tables for the Phase 0
              viral growth loop (device-based invites + attribution).
Migration v9: added push_tokens + parent_identities tables for Phase 1:
              server-side push notifications and optional Google Sign-In
              identity that survives app reinstall.
Migration v10: added daily_login_streaks table. Stores one row per
               (device_id, child_id, date). The progress endpoint uses it
               to compute a "consecutive days the child was engaged" streak
               that is independent from lesson completions, so opening the
               app daily counts toward the streak even when no lesson is
               completed.
"""
import os
import sqlite3
from pathlib import Path

_DEFAULT = Path(__file__).resolve().parents[3] / "ops" / "conversations.db"

_CREATE_PUSH_TOKENS: str = """
CREATE TABLE IF NOT EXISTS push_tokens (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id   TEXT NOT NULL UNIQUE,
    token       TEXT NOT NULL,
    platform    TEXT NOT NULL DEFAULT 'android',
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_push_tokens_device
    ON push_tokens (device_id);
"""

_CREATE_PARENT_IDENTITIES: str = """
CREATE TABLE IF NOT EXISTS parent_identities (
    google_id    TEXT PRIMARY KEY,
    email        TEXT,
    display_name TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS identity_links (
    device_id   TEXT PRIMARY KEY,
    google_id   TEXT NOT NULL,
    linked_at   TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (google_id) REFERENCES parent_identities(google_id)
);
CREATE INDEX IF NOT EXISTS ix_identity_links_google
    ON identity_links (google_id);
"""

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
    UNIQUE(device_id, child_id, date)
);
CREATE INDEX IF NOT EXISTS ix_coach_tips_device_child_date
    ON coach_tips (device_id, child_id, date);
CREATE INDEX IF NOT EXISTS ix_coach_tips_date
    ON coach_tips (date);
"""

_CREATE_CHILD_CHALLENGES: str = """
CREATE TABLE IF NOT EXISTS child_challenges (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id       TEXT NOT NULL,
    child_id        INTEGER NOT NULL,
    challenge_key   TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'active',
    notes           TEXT,
    started_at      TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at    TEXT,
    UNIQUE(device_id, child_id, status)
);
CREATE INDEX IF NOT EXISTS ix_child_challenges_device_child
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

SCHEMA_VERSION = 10


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
            created_at         TEXT NOT NULL DEFAULT (datetime('now')),
            model              TEXT,
            guardrail_version  TEXT
        );
        CREATE INDEX IF NOT EXISTS ix_chat_messages_session
            ON chat_messages (session_id, created_at);

        CREATE TABLE IF NOT EXISTS api_tokens (
            token       TEXT PRIMARY KEY,
            device_id   TEXT NOT NULL,
            created_at  TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS ix_api_tokens_device
            ON api_tokens (device_id);

        CREATE TABLE IF NOT EXISTS user_feedback (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id  TEXT NOT NULL,
            message_id  INTEGER NOT NULL,
            rating      TEXT NOT NULL,
            comment     TEXT,
            created_at  TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS child_profiles (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id   TEXT NOT NULL,
            name        TEXT NOT NULL,
            age_group   TEXT NOT NULL,
            gender      TEXT,
            avatar_emoji TEXT,
            created_at  TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS ix_child_profiles_device
            ON child_profiles (device_id);

        CREATE TABLE IF NOT EXISTS lesson_progress (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id      TEXT NOT NULL,
            child_id       INTEGER NOT NULL,
            path_id        TEXT NOT NULL,
            lesson_id      TEXT NOT NULL,
            status         TEXT NOT NULL DEFAULT 'not_started',
            started_at     TEXT,
            completed_at   TEXT,
            score          INTEGER,
            updated_at     TEXT,
            UNIQUE(device_id, child_id, path_id, lesson_id)
        );
    """
    )

    # Defensive (prod hotfix): an older prod lesson_progress table can predate
    # the child_id column (its CREATE TABLE IF NOT EXISTS was a no-op). The old
    # indexes never referenced child_id so the gap stayed hidden; the new
    # child_id index crashed startup with "no such column: child_id". Ensure
    # the column exists (idempotent — no-op when present) BEFORE the index.
    # lesson_progress is created in the executescript above, so it exists here.
    _ensure_column(
        conn, table="lesson_progress", column="child_id",
        ddl="ALTER TABLE lesson_progress ADD COLUMN child_id INTEGER",
    )
    _ensure_column(
        conn,
        table="lesson_progress",
        column="updated_at",
        ddl="ALTER TABLE lesson_progress ADD COLUMN updated_at TEXT",
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_lesson_progress_device_child "
        "ON lesson_progress (device_id, child_id, path_id)"
    )

    _ensure_column(
        conn,
        table="child_profiles",
        column="age_group",
        ddl="ALTER TABLE child_profiles ADD COLUMN age_group TEXT NOT NULL DEFAULT ''",
    )
    _ensure_column(
        conn,
        table="child_profiles",
        column="avatar_emoji",
        ddl="ALTER TABLE child_profiles ADD COLUMN avatar_emoji TEXT",
    )

    _ensure_coach_tips_table(conn)
    _ensure_child_challenges_table(conn)
    _ensure_referrals_table(conn)
    _ensure_push_tokens_table(conn)
    _ensure_parent_identities_table(conn)
    _ensure_daily_login_streaks_table(conn)

    row = conn.execute("SELECT version FROM schema_version LIMIT 1").fetchone()
    if row is None:
        conn.execute("INSERT INTO schema_version (version) VALUES (?)", (SCHEMA_VERSION,))
    elif row["version"] < SCHEMA_VERSION:
        conn.execute("UPDATE schema_version SET version = ?", (SCHEMA_VERSION,))
    conn.commit()
    conn.close()


_CREATE_DAILY_LOGIN_STREAKS: str = """
CREATE TABLE IF NOT EXISTS daily_login_streaks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id   TEXT NOT NULL,
    child_id    INTEGER NOT NULL,
    date        TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(device_id, child_id, date)
);
CREATE INDEX IF NOT EXISTS ix_daily_login_streaks_device_child
    ON daily_login_streaks (device_id, child_id, date);
CREATE INDEX IF NOT EXISTS ix_daily_login_streaks_date
    ON daily_login_streaks (date);
"""


def _ensure_daily_login_streaks_table(conn: sqlite3.Connection) -> None:
    """Idempotent migration helper for the v10 daily_login_streaks table."""
    try:
        cur = conn.execute("PRAGMA table_info(daily_login_streaks)")
        names = {row[1] for row in cur.fetchall()}
    except sqlite3.Error:
        names = set()
    if not names:
        conn.executescript(_CREATE_DAILY_LOGIN_STREAKS)


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
    """Add a column to an existing table if it is missing."""
    try:
        cur = conn.execute(f"PRAGMA table_info({table})")
        names = {row[1] for row in cur.fetchall()}
    except sqlite3.Error:
        names = set()
    if names and column not in names:
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
        cur = conn.execute("PRAGMA table_info(referral_codes)")
        names = {row[1] for row in cur.fetchall()}
    except sqlite3.Error:
        names = set()
    if not names:
        conn.executescript(_CREATE_REFERRALS)


def _ensure_push_tokens_table(conn: sqlite3.Connection) -> None:
    """Idempotent migration helper for the v9 push_tokens table."""
    try:
        cur = conn.execute("PRAGMA table_info(push_tokens)")
        names = {row[1] for row in cur.fetchall()}
    except sqlite3.Error:
        names = set()
    if not names:
        conn.executescript(_CREATE_PUSH_TOKENS)


def _ensure_parent_identities_table(conn: sqlite3.Connection) -> None:
    """Idempotent migration helper for the v9 identity tables."""
    try:
        cur = conn.execute("PRAGMA table_info(parent_identities)")
        names = {row[1] for row in cur.fetchall()}
    except sqlite3.Error:
        names = set()
    if not names:
        conn.executescript(_CREATE_PARENT_IDENTITIES)
