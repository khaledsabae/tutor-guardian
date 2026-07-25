"""Migration v20: create feedback_replies table.

Closes the loop on in-app feedback. Until now a user could report a problem
but never hear back, which teaches people that reporting is pointless. Khaled
replies from Telegram; the reply lands here and is delivered to the device
that sent the original feedback.

No foreign key to app_feedback: that table is created lazily by the feedback
router rather than by init_db, so it may not exist when this runs. The
relationship is enforced in the route, which only ever inserts a feedback_id
it just looked up.
"""
from __future__ import annotations

MIGRATION_SQL = """
CREATE TABLE IF NOT EXISTS feedback_replies (
    id           TEXT PRIMARY KEY,
    feedback_id  TEXT NOT NULL,
    device_id    TEXT,
    reply_text   TEXT NOT NULL,
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    delivered_at TEXT,
    read_at      TEXT
);
-- The device polls "anything new for me?" on launch; this is that query.
CREATE INDEX IF NOT EXISTS ix_feedback_replies_device
    ON feedback_replies (device_id, read_at);
CREATE INDEX IF NOT EXISTS ix_feedback_replies_feedback
    ON feedback_replies (feedback_id);
"""


def migrate(conn) -> None:
    """Apply the v20 migration to an open sqlite3 connection."""
    conn.executescript(MIGRATION_SQL)
    conn.execute("UPDATE schema_version SET version = 20")
    conn.commit()


if __name__ == "__main__":
    # Stand-alone run for ops/maintenance.
    import os
    import sqlite3

    db = os.environ.get("CONVERSATIONS_DB", "ops/conversations.db")
    c = sqlite3.connect(db)
    c.execute("PRAGMA foreign_keys = ON")
    migrate(c)
    c.close()
    print(f"Applied v20 migration to {db}")
