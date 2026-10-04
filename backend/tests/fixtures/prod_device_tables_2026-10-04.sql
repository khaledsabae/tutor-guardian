-- Production schema of every table that names a device, plus parent_identities
-- (identity_links' FK target). Copied 2026-10-04 from tg_backend, read-only:
--   sqlite3.connect('file:/app/ops/conversations.db?mode=ro', uri=True)
--   SELECT sql FROM sqlite_master WHERE type IN ('table','index') AND tbl_name = ?
-- for each table with a device_id column (PRAGMA table_info); schema_version 29.
-- referrals (referrer_device / referred_device) and push_tokens' extra columns
-- are here because production has them. Schema only, no rows. Regenerate the
-- same way; do not hand-edit (project note fixtures-must-be-copied-not-written).
CREATE TABLE api_tokens (
            token       TEXT PRIMARY KEY,
            device_id   TEXT NOT NULL,
            session_id  TEXT NOT NULL
                         REFERENCES chat_sessions(id) ON DELETE CASCADE,
            created_at  TEXT NOT NULL DEFAULT (datetime('now')),
            expires_at  TEXT  -- NULL = no expiry (first-party mobile)
        );
CREATE INDEX ix_api_tokens_device
            ON api_tokens (device_id);
CREATE INDEX ix_api_tokens_session
            ON api_tokens (session_id);
CREATE TABLE app_feedback (
            id TEXT PRIMARY KEY,
            message TEXT,
            contact TEXT,
            audio_file TEXT,
            device_id TEXT,
            app_version TEXT,
            created_at TEXT
        , audio_b64 TEXT, tg_message_id INTEGER);
CREATE TABLE chat_sessions (
            id          TEXT PRIMARY KEY,
            device_id   TEXT,
            created_at  TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at  TEXT NOT NULL DEFAULT (datetime('now')),
            metadata    TEXT
        );
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
CREATE TABLE child_daily_routines (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id    TEXT NOT NULL,
    child_id     INTEGER NOT NULL,
    routine_date TEXT NOT NULL,
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at   TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(device_id, child_id, routine_date),
    FOREIGN KEY (child_id) REFERENCES child_profiles(id) ON DELETE CASCADE
);
CREATE INDEX ix_daily_routines_date
    ON child_daily_routines (routine_date);
CREATE INDEX ix_daily_routines_device_child_date
    ON child_daily_routines (device_id, child_id, routine_date);
CREATE TABLE child_licences (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id     TEXT NOT NULL,
    child_id      INTEGER NOT NULL,
    -- stranger | signal | contact | footprint | public
    level_key     TEXT NOT NULL,
    -- practising | awaiting_talk | granted
    status        TEXT NOT NULL DEFAULT 'practising',
    granted_at    TEXT,
    talked_at     TEXT,
    next_review_date TEXT,
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (child_id, level_key)
);
CREATE INDEX ix_licences_child
    ON child_licences (child_id, status);
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
    parent_note   TEXT,
    UNIQUE (child_id, local_date, mission_key)
);
CREATE INDEX ix_missions_child_date
    ON child_missions (child_id, local_date);
CREATE INDEX ix_missions_child_key
    ON child_missions (child_id, mission_key, local_date);
CREATE INDEX ix_missions_pending
    ON child_missions (device_id, status);
CREATE TABLE child_profiles (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id   TEXT NOT NULL,
            name        TEXT NOT NULL,
            age_group   TEXT NOT NULL,  -- enum from CANONICAL_AGE_GROUPS
            gender      TEXT,
            created_at  TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
        , avatar_emoji TEXT);
CREATE INDEX ix_child_profiles_device
            ON child_profiles (device_id);
CREATE TABLE child_scenario_answers (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id     TEXT NOT NULL,
    child_id      INTEGER NOT NULL,
    scenario_key  TEXT NOT NULL,
    level_key     TEXT NOT NULL,
    choice_key    TEXT NOT NULL,
    -- safe | unsafe | critical, copied from the bank at answer time. Read
    -- back from the bank instead and editing a classification would rewrite
    -- history; the log has to stay what it was.
    outcome       TEXT NOT NULL,
    attempt       INTEGER NOT NULL DEFAULT 1,
    answered_at   TEXT NOT NULL DEFAULT (datetime('now')),
    parent_alerted_at TEXT
);
CREATE INDEX ix_scenarios_child
    ON child_scenario_answers (child_id, level_key);
CREATE INDEX ix_scenarios_repeat
    ON child_scenario_answers (child_id, scenario_key, answered_at);
CREATE TABLE child_screen_sessions (
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
CREATE INDEX ix_css_child_date
    ON child_screen_sessions (child_id, local_date);
CREATE INDEX ix_css_open
    ON child_screen_sessions (child_id, ended_at);
CREATE INDEX ix_css_started
    ON child_screen_sessions (child_id, started_at);
CREATE TABLE child_web_claims (
            code_hash   TEXT PRIMARY KEY,
            device_id   TEXT NOT NULL,
            child_id    INTEGER NOT NULL,
            ttl_seconds INTEGER NOT NULL,
            expires_at  REAL NOT NULL,
            used_at     REAL
        );
CREATE INDEX ix_child_web_claims_expires
            ON child_web_claims (expires_at);
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
CREATE TABLE family_agreements (
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
CREATE INDEX ix_agreements_child
    ON family_agreements (child_id, status);
CREATE TABLE feedback_replies (
    id           TEXT PRIMARY KEY,
    feedback_id  TEXT NOT NULL,
    device_id    TEXT,
    reply_text   TEXT NOT NULL,
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    delivered_at TEXT,
    read_at      TEXT
);
CREATE INDEX ix_feedback_replies_device
    ON feedback_replies (device_id, read_at);
CREATE INDEX ix_feedback_replies_feedback
    ON feedback_replies (feedback_id);
CREATE TABLE habit_templates (
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
CREATE INDEX ix_habit_templates_device_child_active
    ON habit_templates (device_id, child_id, is_active);
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
CREATE TABLE identity_links (
    device_id   TEXT PRIMARY KEY,
    google_id   TEXT NOT NULL,
    linked_at   TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (google_id) REFERENCES parent_identities(google_id)
);
CREATE INDEX ix_identity_links_google
    ON identity_links (google_id);
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
CREATE TABLE parent_identities (
    google_id    TEXT PRIMARY KEY,
    email        TEXT,
    display_name TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE push_sends (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id   TEXT NOT NULL,
    kind        TEXT NOT NULL,
    sent_at     TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX ix_push_sends_device_time
    ON push_sends (device_id, sent_at);
CREATE TABLE push_tokens (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id   TEXT NOT NULL UNIQUE,
    token       TEXT NOT NULL,
    platform    TEXT NOT NULL DEFAULT 'android',
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
, app_version TEXT, build_number INTEGER);
CREATE INDEX ix_push_tokens_device
    ON push_tokens (device_id);
CREATE TABLE referral_codes (
    device_id  TEXT PRIMARY KEY,
    code       TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE user_backups (
    device_id   TEXT PRIMARY KEY,
    google_id   TEXT,
    salt        TEXT NOT NULL,
    nonce       TEXT NOT NULL,
    payload     TEXT NOT NULL,
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX ix_user_backups_google
    ON user_backups (google_id);
CREATE TABLE referrals (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    referrer_device TEXT NOT NULL,
    referred_device TEXT NOT NULL UNIQUE,  -- a device can be referred only once
    code            TEXT NOT NULL,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX ix_referrals_referrer
    ON referrals (referrer_device);
