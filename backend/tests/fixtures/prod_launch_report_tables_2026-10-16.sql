-- Production schema of the tables ops/scripts/launch_weekly_report.py reads
-- (it reuses ops/scripts/campaign_report.py's reader). Copied 2026-10-16 from
-- tg_backend, read-only:
--   sqlite3.connect('file:/app/ops/conversations.db?mode=ro', uri=True)
--   SELECT sql FROM sqlite_master WHERE type IN ('table','index')
--     AND tbl_name = ? AND sql IS NOT NULL ORDER BY type DESC, name
-- for each table below; schema_version 36. Schema only, no rows. Regenerate
-- the same way; do not hand-edit (project note fixtures-must-be-copied-not-written).
CREATE TABLE chat_sessions (
            id          TEXT PRIMARY KEY,
            device_id   TEXT,
            created_at  TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at  TEXT NOT NULL DEFAULT (datetime('now')),
            metadata    TEXT
        );
CREATE TABLE chat_messages (
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
CREATE INDEX ix_chat_messages_session
            ON chat_messages (session_id);
CREATE TABLE child_profiles (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id   TEXT NOT NULL,
            name        TEXT NOT NULL,
            age_group   TEXT NOT NULL,  -- enum from CANONICAL_AGE_GROUPS
            gender      TEXT,
            created_at  TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
        , avatar_emoji TEXT, birth_month TEXT);
CREATE INDEX ix_child_profiles_device
            ON child_profiles (device_id);
CREATE TABLE "lesson_progress" (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id      TEXT NOT NULL,
                child_id       INTEGER NOT NULL DEFAULT 0,
                path_id        TEXT NOT NULL,
                lesson_id      TEXT NOT NULL,
                status         TEXT NOT NULL DEFAULT 'not_started',
                started_at     TEXT,
                completed_at   TEXT,
                score          INTEGER,
                updated_at     TEXT,
                UNIQUE (device_id, child_id, lesson_id)
            );
CREATE INDEX ix_lesson_progress_device ON lesson_progress (device_id);
CREATE INDEX ix_lesson_progress_device_child ON lesson_progress (device_id, child_id, path_id);
CREATE INDEX ix_lesson_progress_path_device ON lesson_progress (device_id, path_id);
CREATE TABLE habits_value_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id   TEXT NOT NULL,
    child_id    INTEGER NOT NULL,
    category    TEXT NOT NULL,
    habit_name  TEXT NOT NULL,
    status      TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now')), submitted_by TEXT NOT NULL DEFAULT 'parent', device_timestamp TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (child_id) REFERENCES child_profiles(id) ON DELETE CASCADE
);
CREATE INDEX ix_habits_value_events_device_child_date
    ON habits_value_events (device_id, child_id, created_at);
CREATE TABLE child_missions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id     TEXT NOT NULL,
    child_id      INTEGER NOT NULL,
    mission_key   TEXT NOT NULL,
    local_date    TEXT NOT NULL,
    -- assigned | claimed | confirmed | not_done | expired
    status        TEXT NOT NULL DEFAULT 'assigned',
    assigned_at   TEXT NOT NULL DEFAULT (datetime('now')),
    claimed_at    TEXT,
    confirmed_at  TEXT,
    parent_note   TEXT, source TEXT,
    UNIQUE (child_id, local_date, mission_key)
);
CREATE INDEX ix_missions_child_date
    ON child_missions (child_id, local_date);
CREATE INDEX ix_missions_child_key
    ON child_missions (child_id, mission_key, local_date);
CREATE INDEX ix_missions_pending
    ON child_missions (device_id, status);
CREATE TABLE child_challenges (
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
CREATE INDEX ix_child_challenges_active
    ON child_challenges (device_id, child_id, status);
CREATE UNIQUE INDEX ux_child_challenges_active ON child_challenges (device_id, child_id) WHERE status = 'active';
CREATE TABLE referrals (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    referrer_device TEXT NOT NULL,
    referred_device TEXT NOT NULL UNIQUE,  -- a device can be referred only once
    code            TEXT NOT NULL,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
, via TEXT);
CREATE INDEX ix_referrals_referrer
    ON referrals (referrer_device);
CREATE TABLE referral_clicks (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    ip         TEXT NOT NULL,
    user_agent TEXT,
    code       TEXT NOT NULL,
    clicked_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX ix_referral_clicks_ip
    ON referral_clicks (ip, clicked_at);
CREATE INDEX ix_referral_clicks_time
            ON referral_clicks (clicked_at);
CREATE TABLE referral_click_days (
            day    TEXT NOT NULL,
            code   TEXT NOT NULL,
            clicks INTEGER NOT NULL,
            PRIMARY KEY (day, code)
        );
CREATE TABLE coach_tips (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id    TEXT NOT NULL,
    child_id     INTEGER NOT NULL,
    date         TEXT NOT NULL,
    domain       TEXT,
    text         TEXT NOT NULL,
    source       TEXT NOT NULL DEFAULT 'fallback',
    shown_at     TEXT,
    tapped_at    TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now')), lang TEXT,
    UNIQUE (device_id, child_id, date)
);
CREATE INDEX ix_coach_tips_device_date
    ON coach_tips (device_id, child_id, date);
CREATE TABLE daily_login_streaks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id   TEXT NOT NULL,
    child_id    INTEGER NOT NULL,
    date        TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(device_id, child_id, date)
);
CREATE INDEX ix_daily_login_streaks_date
    ON daily_login_streaks (date);
CREATE INDEX ix_daily_login_streaks_device_child
    ON daily_login_streaks (device_id, child_id, date);
CREATE TABLE push_tokens (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id   TEXT NOT NULL UNIQUE,
    token       TEXT NOT NULL,
    platform    TEXT NOT NULL DEFAULT 'android',
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
, app_version TEXT, build_number INTEGER, token_since TEXT, token_vouched INTEGER, token_first INTEGER);
CREATE INDEX ix_push_tokens_device
    ON push_tokens (device_id);
CREATE TABLE device_aliases (
        device_id        TEXT PRIMARY KEY,   -- the folded-away twin
        canonical_device TEXT NOT NULL,      -- the family device that absorbed it
        folded_at        TEXT NOT NULL DEFAULT (datetime('now'))
    );
CREATE INDEX ix_device_aliases_canonical ON device_aliases (canonical_device);
