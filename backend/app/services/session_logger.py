import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[3] / "ops" / "sessions.db"


def _get_conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            ts TEXT,
            domain TEXT,
            behavior_type TEXT,
            age_group TEXT,
            severity TEXT,
            mode TEXT,
            needs_human_review INTEGER,
            reply_length INTEGER,
            retrieved_count INTEGER,
            flag TEXT
        )
    """)
    conn.commit()
    return conn


def log_session(
    domain: str,
    behavior_type: str,
    age_group: str,
    severity: str,
    mode: str,
    needs_human_review: bool,
    reply_length: int,
    retrieved_count: int,
    flag: str = "",
):
    conn = _get_conn()
    conn.execute(
        """INSERT INTO sessions VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (
            str(uuid.uuid4()),
            datetime.now(timezone.utc).isoformat(),
            domain, behavior_type, age_group, severity,
            mode,
            int(needs_human_review),
            reply_length,
            retrieved_count,
            flag,
        ),
    )
    conn.commit()
    conn.close()
