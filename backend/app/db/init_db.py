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
Migration v11: added session_id + expires_at columns to api_tokens to match
               the token contract used by conversation_store.py and auth.py.
Migration v12: aligned child_challenges schema with children.py router:
               added topic, domain, note, resolved_at; removed notes, completed_at.
Migration v13: aligned chat_messages schema with conversation_store.py:
               added domain, severity, mode, needs_human_review.
Migration v14: added child_daily_routines + routine_events tables for
               «حِساب اليوم» daily routine tracker (sleep/feed/diaper).
Migration v15: added habits_value_events table for «ميزان العادات» —
               age-dynamic habit/value tracking for children 7–18.
Migration v16: added habit_templates table for custom parent-defined habits
               with soft-delete via is_active and unique (child_id, custom_name).
Migration v17: added submitted_by + device_timestamp columns to
               habits_value_events to track entry source and device time.
Migration v20: added feedback_replies table so a reply written in Telegram can
               be delivered back to the device that sent the feedback.
Migration v21: added child_screen_sessions table — the server-side time budget
               behind the child surface. local_date is derived on the server
               from a client-supplied UTC offset rather than taken as a date
               string, and every read of the day's usage is floored by a
               rolling 24-hour window, so changing the device timezone cannot
               hand a child a second daily allowance.
Migration v22: added family_agreements + agreement_clauses — the two-sided
               media agreement between a parent and a child. Clauses carry
               `applies_to`, because an agreement whose every rule points at
               the child is a list of orders, and the research this feature
               rests on is about an agreement.
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

# One row per push actually handed to FCM.
#
# There was no send log at all, so no sender could ask "have we already
# bothered this device?". streak_at_risk fires for any device idle >36h and
# win_back for any idle >5 days, which meant the same permanently-lapsed device
# got the identical message every single evening, forever. Halving the daily
# volume does not fix that; a frequency cap does.
#
# Deliberately not unique on (device_id, kind): the history is the point, and a
# cap is a question about the recent past, not a constraint on the table.
_CREATE_PUSH_SENDS: str = """
CREATE TABLE IF NOT EXISTS push_sends (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id   TEXT NOT NULL,
    kind        TEXT NOT NULL,
    sent_at     TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_push_sends_device_time
    ON push_sends (device_id, sent_at);
"""

_CREATE_USER_BACKUPS: str = """
CREATE TABLE IF NOT EXISTS user_backups (
    device_id   TEXT PRIMARY KEY,
    google_id   TEXT,
    salt        TEXT NOT NULL,
    nonce       TEXT NOT NULL,
    payload     TEXT NOT NULL,
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_user_backups_google
    ON user_backups (google_id);
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
    topic           TEXT NOT NULL,
    domain          TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'active',
    note            TEXT,
    started_at      TEXT NOT NULL DEFAULT (datetime('now')),
    resolved_at     TEXT,
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

SCHEMA_VERSION = 22


def db_path() -> Path:
    """Resolve the DB path at call time (so tests can override via env)."""
    return Path(os.environ.get("CONVERSATIONS_DB", str(_DEFAULT)))


def get_conn() -> sqlite3.Connection:
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    # Handlers run concurrently in the threadpool: WAL lets readers proceed
    # during a write, and busy_timeout retries instead of instantly raising
    # "database is locked" (which used to 500 fully-generated replies).
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
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
            created_at         TEXT NOT NULL DEFAULT (datetime('now')),
            model              TEXT,
            guardrail_version  TEXT
        );
        CREATE INDEX IF NOT EXISTS ix_chat_messages_session
            ON chat_messages (session_id, created_at);

        CREATE TABLE IF NOT EXISTS api_tokens (
            token       TEXT PRIMARY KEY,
            device_id   TEXT NOT NULL,
            session_id  TEXT NOT NULL,
            expires_at  TEXT,
            created_at  TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS ix_api_tokens_device
            ON api_tokens (device_id);
        CREATE INDEX IF NOT EXISTS ix_api_tokens_session
            ON api_tokens (session_id);

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
    _ensure_push_sends_table(conn)
    _ensure_parent_identities_table(conn)
    _ensure_daily_login_streaks_table(conn)
    _ensure_api_tokens_columns(conn)
    _ensure_chat_messages_columns(conn)
    _ensure_daily_routines_table(conn)
    _ensure_habits_value_table(conn)
    _ensure_habit_templates_table(conn)
    _ensure_habits_value_audit_columns(conn)
    _ensure_user_backups_table(conn)
    _ensure_referral_clicks_table(conn)
    _ensure_feedback_replies_table(conn)
    _ensure_child_screen_sessions_table(conn)
    _ensure_family_agreements_tables(conn)

    row = conn.execute("SELECT version FROM schema_version LIMIT 1").fetchone()
    if row is None:
        conn.execute("INSERT INTO schema_version (version) VALUES (?)", (SCHEMA_VERSION,))
    elif row["version"] < SCHEMA_VERSION:
        conn.execute("UPDATE schema_version SET version = ?", (SCHEMA_VERSION,))
    conn.commit()
    conn.close()


_CREATE_DAILY_ROUTINES: str = """
CREATE TABLE IF NOT EXISTS child_daily_routines (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id    TEXT NOT NULL,
    child_id     INTEGER NOT NULL,
    routine_date TEXT NOT NULL,
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at   TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(device_id, child_id, routine_date),
    FOREIGN KEY (child_id) REFERENCES child_profiles(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_daily_routines_device_child_date
    ON child_daily_routines (device_id, child_id, routine_date);
CREATE INDEX IF NOT EXISTS ix_daily_routines_date
    ON child_daily_routines (routine_date);

CREATE TABLE IF NOT EXISTS routine_events (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    routine_id   INTEGER NOT NULL,
    event_type   TEXT NOT NULL,
    started_at   TEXT NOT NULL,
    ended_at     TEXT,
    feed_type    TEXT,
    amount_ml    INTEGER,
    side         TEXT,
    diaper_type  TEXT,
    notes        TEXT,
    source       TEXT NOT NULL DEFAULT 'manual',
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at   TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (routine_id) REFERENCES child_daily_routines(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_routine_events_routine
    ON routine_events (routine_id, event_type, started_at);
"""

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


_CREATE_HABITS_VALUE_EVENTS: str = """
CREATE TABLE IF NOT EXISTS habits_value_events (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id        TEXT NOT NULL,
    child_id         INTEGER NOT NULL,
    category         TEXT NOT NULL,
    habit_name       TEXT NOT NULL,
    status           TEXT NOT NULL,
    submitted_by     TEXT NOT NULL DEFAULT 'parent',
    device_timestamp TEXT NOT NULL DEFAULT (datetime('now')),
    created_at       TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at       TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (child_id) REFERENCES child_profiles(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_habits_value_events_device_child_date
    ON habits_value_events (device_id, child_id, created_at);
"""

_CREATE_HABIT_TEMPLATES: str = """
CREATE TABLE IF NOT EXISTS habit_templates (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id   TEXT NOT NULL,
    child_id    INTEGER NOT NULL,
    category    TEXT NOT NULL,
    custom_name TEXT NOT NULL,
    is_active   INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(child_id, custom_name),
    FOREIGN KEY (child_id) REFERENCES child_profiles(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_habit_templates_device_child_active
    ON habit_templates (device_id, child_id, is_active);
"""

# No foreign key to app_feedback: that table is created lazily by the feedback
# router rather than here, so it may not exist yet. The route is the only
# writer and only ever inserts a feedback_id it has just looked up.
_CREATE_CHILD_SCREEN_SESSIONS: str = """
CREATE TABLE IF NOT EXISTS child_screen_sessions (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id         TEXT NOT NULL,
    child_id          INTEGER NOT NULL,
    surface           TEXT NOT NULL,
    -- Derived on the server from tz_offset_minutes, never taken from the
    -- client as a string. A client that picks its own date picks its own
    -- daily budget.
    local_date        TEXT NOT NULL,
    tz_offset_minutes INTEGER NOT NULL,
    started_at        TEXT NOT NULL,
    last_heartbeat_at TEXT NOT NULL,
    ended_at          TEXT,
    -- completed | budget_exhausted | timeout | parent_exit | superseded
    ended_reason      TEXT,
    counted_seconds   INTEGER NOT NULL DEFAULT 0,
    created_at        TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_css_child_date
    ON child_screen_sessions (child_id, local_date);
CREATE INDEX IF NOT EXISTS ix_css_open
    ON child_screen_sessions (child_id, ended_at);
-- The rolling-24h floor scans by start time across all children.
CREATE INDEX IF NOT EXISTS ix_css_started
    ON child_screen_sessions (child_id, started_at);
"""

_CREATE_FAMILY_AGREEMENTS: str = """
CREATE TABLE IF NOT EXISTS family_agreements (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id           TEXT NOT NULL,
    child_id            INTEGER NOT NULL,
    version             INTEGER NOT NULL DEFAULT 1,
    -- draft | active | archived. Only one active row per child; superseding
    -- one archives it rather than deleting, so a family can see what they
    -- agreed to last month and what changed.
    status              TEXT NOT NULL DEFAULT 'draft',
    signed_by_parent_at TEXT,
    signed_by_child_at  TEXT,
    next_review_date    TEXT,
    created_at          TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS agreement_clauses (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    agreement_id  INTEGER NOT NULL,
    -- child | parent | both. The column that makes this an agreement.
    applies_to    TEXT NOT NULL,
    clause_key    TEXT,
    text_ar       TEXT NOT NULL,
    is_custom     INTEGER NOT NULL DEFAULT 0,
    sort_order    INTEGER NOT NULL DEFAULT 0,
    -- Set when the child ticks "I understand" on this clause specifically.
    -- One OK for the whole page is a signature on something unread.
    acknowledged_at TEXT
);
CREATE INDEX IF NOT EXISTS ix_agreements_child
    ON family_agreements (child_id, status);
CREATE INDEX IF NOT EXISTS ix_clauses_agreement
    ON agreement_clauses (agreement_id, sort_order);
"""

_CREATE_FEEDBACK_REPLIES: str = """
CREATE TABLE IF NOT EXISTS feedback_replies (
    id           TEXT PRIMARY KEY,
    feedback_id  TEXT NOT NULL,
    device_id    TEXT,
    reply_text   TEXT NOT NULL,
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    delivered_at TEXT,
    read_at      TEXT
);
CREATE INDEX IF NOT EXISTS ix_feedback_replies_device
    ON feedback_replies (device_id, read_at);
CREATE INDEX IF NOT EXISTS ix_feedback_replies_feedback
    ON feedback_replies (feedback_id);
"""


def _ensure_daily_routines_table(conn: sqlite3.Connection) -> None:
    """Idempotent migration helper for the v14 daily routines tables."""
    try:
        cur = conn.execute("PRAGMA table_info(child_daily_routines)")
        names = {row[1] for row in cur.fetchall()}
    except sqlite3.Error:
        names = set()
    if not names:
        conn.executescript(_CREATE_DAILY_ROUTINES)


def _ensure_daily_login_streaks_table(conn: sqlite3.Connection) -> None:
    """Idempotent migration helper for the v10 daily_login_streaks table."""
    try:
        cur = conn.execute("PRAGMA table_info(daily_login_streaks)")
        names = {row[1] for row in cur.fetchall()}
    except sqlite3.Error:
        names = set()
    if not names:
        conn.executescript(_CREATE_DAILY_LOGIN_STREAKS)


def _ensure_habits_value_table(conn: sqlite3.Connection) -> None:
    """Idempotent migration helper for the v15 habits_value_events table."""
    try:
        cur = conn.execute("PRAGMA table_info(habits_value_events)")
        names = {row[1] for row in cur.fetchall()}
    except sqlite3.Error:
        names = set()
    if not names:
        conn.executescript(_CREATE_HABITS_VALUE_EVENTS)


def _ensure_habit_templates_table(conn: sqlite3.Connection) -> None:
    """Idempotent migration helper for the v16 habit_templates table."""
    try:
        cur = conn.execute("PRAGMA table_info(habit_templates)")
        names = {row[1] for row in cur.fetchall()}
    except sqlite3.Error:
        names = set()
    if not names:
        conn.executescript(_CREATE_HABIT_TEMPLATES)


def _ensure_family_agreements_tables(conn: sqlite3.Connection) -> None:
    """Idempotent migration helper for the v22 agreement tables."""
    try:
        cur = conn.execute("PRAGMA table_info(family_agreements)")
        names = {row[1] for row in cur.fetchall()}
    except sqlite3.Error:
        names = set()
    if not names:
        conn.executescript(_CREATE_FAMILY_AGREEMENTS)


def _ensure_child_screen_sessions_table(conn: sqlite3.Connection) -> None:
    """Idempotent migration helper for the v21 child_screen_sessions table."""
    try:
        cur = conn.execute("PRAGMA table_info(child_screen_sessions)")
        names = {row[1] for row in cur.fetchall()}
    except sqlite3.Error:
        names = set()
    if not names:
        conn.executescript(_CREATE_CHILD_SCREEN_SESSIONS)


def _ensure_feedback_replies_table(conn: sqlite3.Connection) -> None:
    """Idempotent migration helper for the v20 feedback_replies table."""
    try:
        cur = conn.execute("PRAGMA table_info(feedback_replies)")
        names = {row[1] for row in cur.fetchall()}
    except sqlite3.Error:
        names = set()
    if not names:
        conn.executescript(_CREATE_FEEDBACK_REPLIES)


def _ensure_habits_value_audit_columns(conn: sqlite3.Connection) -> None:
    """Idempotent migration helper for the v17 audit columns on habits_value_events."""
    _ensure_column(
        conn,
        table="habits_value_events",
        column="submitted_by",
        ddl="ALTER TABLE habits_value_events ADD COLUMN submitted_by TEXT NOT NULL DEFAULT 'parent'",
    )
    _ensure_column(
        conn,
        table="habits_value_events",
        column="device_timestamp",
        ddl="ALTER TABLE habits_value_events ADD COLUMN device_timestamp TEXT NOT NULL DEFAULT (datetime('now'))",
    )


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
    """Idempotent migration helper for the v7+ child_challenges table.

    v12: aligned schema with children.py router (topic, domain, note,
    resolved_at). Existing rows are dropped because this is dev/test data;
    production migration should back up first.
    """
    try:
        cur = conn.execute("PRAGMA table_info(child_challenges)")
        names = {row[1] for row in cur.fetchall()}
    except sqlite3.Error:
        names = set()
    if not names:
        conn.executescript(_CREATE_CHILD_CHALLENGES)
        return
    # Migrate old v7/v10 schema to v12 if needed.
    required = {"topic", "domain", "note", "resolved_at"}
    if not required.issubset(names):
        conn.executescript(
            """
            ALTER TABLE child_challenges RENAME TO child_challenges_old;
            """
            + _CREATE_CHILD_CHALLENGES
            + """
            INSERT INTO child_challenges (
                id, device_id, child_id, challenge_key, topic, domain,
                status, note, started_at, resolved_at
            )
            SELECT
                id, device_id, child_id, challenge_key, challenge_key,
                'islamic_parenting', status, notes, started_at, completed_at
            FROM child_challenges_old
            WHERE status = 'active' OR resolved_at IS NOT NULL;
            DROP TABLE child_challenges_old;
            """
        )


_CREATE_REFERRAL_CLICKS: str = """
CREATE TABLE IF NOT EXISTS referral_clicks (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    ip         TEXT NOT NULL,
    user_agent TEXT,
    code       TEXT NOT NULL,
    clicked_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_referral_clicks_ip
    ON referral_clicks (ip, clicked_at);
"""


def _ensure_referral_clicks_table(conn: sqlite3.Connection) -> None:
    """Idempotent migration helper for the referral_clicks table."""
    try:
        cur = conn.execute("PRAGMA table_info(referral_clicks)")
        names = {row[1] for row in cur.fetchall()}
    except sqlite3.Error:
        names = set()
    if not names:
        conn.executescript(_CREATE_REFERRAL_CLICKS)


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


def _ensure_push_sends_table(conn: sqlite3.Connection) -> None:
    """Idempotent migration helper for the push_sends frequency log."""
    try:
        cur = conn.execute("PRAGMA table_info(push_sends)")
        names = {row[1] for row in cur.fetchall()}
    except sqlite3.Error:
        names = set()
    if not names:
        conn.executescript(_CREATE_PUSH_SENDS)


def _ensure_parent_identities_table(conn: sqlite3.Connection) -> None:
    """Idempotent migration helper for the v9 identity tables."""
    try:
        cur = conn.execute("PRAGMA table_info(parent_identities)")
        names = {row[1] for row in cur.fetchall()}
    except sqlite3.Error:
        names = set()
    if not names:
        conn.executescript(_CREATE_PARENT_IDENTITIES)


def _ensure_api_tokens_columns(conn: sqlite3.Connection) -> None:
    """Idempotent migration helper for the v11 api_tokens schema drift.

    conversation_store.py expects session_id + expires_at; older tables
    created with the v10 schema lack both columns. Add them without
    touching existing rows.
    """
    try:
        cur = conn.execute("PRAGMA table_info(api_tokens)")
        names = {row[1] for row in cur.fetchall()}
    except sqlite3.Error:
        names = set()
    if names:
        if "session_id" not in names:
            conn.execute("ALTER TABLE api_tokens ADD COLUMN session_id TEXT NOT NULL DEFAULT ''")
        if "expires_at" not in names:
            conn.execute("ALTER TABLE api_tokens ADD COLUMN expires_at TEXT")


def _ensure_chat_messages_columns(conn: sqlite3.Connection) -> None:
    """Idempotent migration helper for the v13 chat_messages schema drift.

    conversation_store.py expects domain, severity, mode, needs_human_review;
    older tables created with the v10 schema lack these columns.
    """
    try:
        cur = conn.execute("PRAGMA table_info(chat_messages)")
        names = {row[1] for row in cur.fetchall()}
    except sqlite3.Error:
        names = set()
    if names:
        for col, ddl in [
            ("domain", "ALTER TABLE chat_messages ADD COLUMN domain TEXT"),
            ("severity", "ALTER TABLE chat_messages ADD COLUMN severity TEXT"),
            ("mode", "ALTER TABLE chat_messages ADD COLUMN mode TEXT"),
            ("needs_human_review", "ALTER TABLE chat_messages ADD COLUMN needs_human_review INTEGER NOT NULL DEFAULT 0"),
        ]:
            if col not in names:
                conn.execute(ddl)


def _ensure_user_backups_table(conn: sqlite3.Connection) -> None:
    """Idempotent migration helper for the user_backups table."""
    try:
        cur = conn.execute("PRAGMA table_info(user_backups)")
        names = {row[1] for row in cur.fetchall()}
    except sqlite3.Error:
        names = set()
    if not names:
        conn.executescript(_CREATE_USER_BACKUPS)
