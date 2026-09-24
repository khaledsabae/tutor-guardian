import sqlite3
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

import ops.scripts.cron_push_triggers as cpt


@pytest.fixture
def mock_db(tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    conn = sqlite3.connect(db_file)
    conn.execute(
        """
        CREATE TABLE child_profiles (
            id TEXT PRIMARY KEY,
            device_id TEXT NOT NULL,
            name TEXT,
            age_group TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE push_tokens (
            device_id TEXT PRIMARY KEY,
            token TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE lesson_progress (
            id TEXT PRIMARY KEY,
            device_id TEXT NOT NULL,
            lesson_id TEXT NOT NULL,
            completed_at TEXT
        )
        """
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr(cpt, "DB_PATH", db_file)
    return db_file


def test_first_lesson_activation_targeting(mock_db):
    now = datetime.utcnow()
    t_1h_ago = (now - timedelta(hours=1)).isoformat()
    t_5h_ago = (now - timedelta(hours=5)).isoformat()
    t_40h_ago = (now - timedelta(hours=40)).isoformat()

    conn = sqlite3.connect(mock_db)
    # Dev1: Registered 5h ago, has token, NO lesson progress -> SHOULD RECEIVE
    conn.execute("INSERT INTO push_tokens VALUES ('dev1', 'tok1')")
    conn.execute("INSERT INTO child_profiles VALUES ('c1', 'dev1', 'عمر', '4-6', ?, ?)", (t_5h_ago, t_5h_ago))

    # Dev2: Registered 1h ago (<2h) -> SHOULD NOT RECEIVE YET
    conn.execute("INSERT INTO push_tokens VALUES ('dev2', 'tok2')")
    conn.execute("INSERT INTO child_profiles VALUES ('c2', 'dev2', 'سارة', '2-3', ?, ?)", (t_1h_ago, t_1h_ago))

    # Dev3: Registered 40h ago (>36h) -> SHOULD NOT RECEIVE (streak_at_risk will handle)
    conn.execute("INSERT INTO push_tokens VALUES ('dev3', 'tok3')")
    conn.execute("INSERT INTO child_profiles VALUES ('c3', 'dev3', 'زين', '7-9', ?, ?)", (t_40h_ago, t_40h_ago))

    # Dev4: Registered 5h ago, but HAS lesson progress -> SHOULD NOT RECEIVE
    conn.execute("INSERT INTO push_tokens VALUES ('dev4', 'tok4')")
    conn.execute("INSERT INTO child_profiles VALUES ('c4', 'dev4', 'كريم', '4-6', ?, ?)", (t_5h_ago, t_5h_ago))
    conn.execute("INSERT INTO lesson_progress VALUES ('lp1', 'dev4', 'lesson_1', ?)", (t_5h_ago,))

    # Dev5: Registered 5h ago, no push token -> SHOULD NOT RECEIVE
    conn.execute("INSERT INTO child_profiles VALUES ('c5', 'dev5', 'يوسف', '4-6', ?, ?)", (t_5h_ago, t_5h_ago))

    conn.commit()
    conn.close()

    sent_pushes = []

    def mock_send(device_id, title, body, data):
        sent_pushes.append({"device_id": device_id, "title": title, "body": body, "data": data})
        return {"ok": True}

    with patch.object(cpt, "_send", side_effect=mock_send):
        # Test normal call
        sent_set = cpt.first_lesson_activation()
        assert sent_set == {"dev1"}
        assert len(sent_pushes) == 1
        push = sent_pushes[0]
        assert push["device_id"] == "dev1"
        assert "عمر" in push["body"]
        assert push["data"]["type"] == "first_lesson_activation"
        assert push["data"]["link"] == "/p/path_4-6_islamic_parenting_bond"

        # Test skip set respects frequency cap
        sent_pushes.clear()
        sent_set_skipped = cpt.first_lesson_activation(skip={"dev1"})
        assert sent_set_skipped == set()
        assert len(sent_pushes) == 0
