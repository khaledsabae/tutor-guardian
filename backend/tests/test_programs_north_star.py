"""A Ramadan «تمّ» and a Prayer Journey started are parenting acts.

The weekly report's North Star counts families who did one real parenting
act in the week. The journey's tasks are child_missions rows and were already
counted; these are the two new sources (ops/scripts/weekly_funnel_report.py).
"""
from datetime import datetime, timedelta

from app.db.init_db import db_path, get_conn
from ops.scripts.weekly_funnel_report import get_action_events, get_north_star


def test_program_acts_count_toward_the_north_star():
    now = datetime(2027, 2, 12, 12, 0, 0)
    conn = get_conn()
    conn.execute("INSERT INTO ramadan_marks (device_id, child_id, hijri_year, day, mark, "
                 "created_at) VALUES ('ramadan-family', 0, 1448, 5, 'challenge_done', ?)",
                 ((now - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S"),))
    conn.execute("INSERT INTO prayer_journeys (device_id, child_id, track, stage, started_on, "
                 "stage_started_on, created_at) VALUES ('journey-family', 3, 'journey', 1, "
                 "'2027-02-09', '2027-02-09', ?)",
                 ((now - timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S"),))
    conn.commit()
    conn.close()
    devices = {d for d, _ in get_action_events(db_path(), since=now - timedelta(days=7))}
    assert devices == {"ramadan-family", "journey-family"}
    assert get_north_star(db_path(), weeks=1, now=now)[0]["families"] == 2
