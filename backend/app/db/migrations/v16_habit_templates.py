"""Migration v16: create habit_templates table.

Parent-defined custom habits for the «ميزان العادات» feature.
Soft-delete via is_active; unique constraint on (child_id, custom_name).
"""
from __future__ import annotations

MIGRATION_SQL = """
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


def migrate(conn) -> None:
    """Apply the v16 migration to an open sqlite3 connection."""
    conn.executescript(MIGRATION_SQL)
    conn.execute("UPDATE schema_version SET version = 16")
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
    print(f"Applied v16 migration to {db}")