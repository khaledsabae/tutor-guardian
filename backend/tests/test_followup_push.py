"""The follow-up push (cron_push_triggers.followup_due) — schema v30.

Runs against the real init_db schema (the conftest temp DB), not a hand-made
fixture: the trigger joins four tables, and a fixture written from memory is
exactly how a column that production does not have gets past a test.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

import ops.scripts.cron_push_triggers as cpt
from app.db.init_db import db_path, get_conn
from app.services import push_sender


@pytest.fixture
def sent(monkeypatch):
    calls: list[dict] = []

    def fake_send(device_id, title, body, data):
        calls.append({"device": device_id, "title": title, "body": body, "data": data})
        push_sender._record_send(device_id, data.get("type", "unknown"))
        return {"ok": True, "sent": True}

    monkeypatch.setattr(cpt, "DB_PATH", db_path())
    monkeypatch.setattr(cpt, "DRY_RUN", False)
    monkeypatch.setattr(cpt, "send_to_device", fake_send)
    monkeypatch.setenv("CHILD_MEMORY_MIN_BUILD", "112")
    return calls


def _device(device: str, *, build: int | None = 120, name: str = "يوسف") -> int:
    conn = get_conn()
    cid = conn.execute(
        "INSERT INTO child_profiles (device_id, name, age_group) VALUES (?, ?, '4-6')",
        (device, name),
    ).lastrowid
    conn.execute(
        "INSERT INTO push_tokens (device_id, token, build_number) VALUES (?, 'tok', ?)",
        (device, build),
    )
    conn.commit()
    conn.close()
    return cid


def _followup(device: str, cid: int, *, hours_ago: float = 2, lang: str = "ar",
              strategy: str = "روتين نوم ثابت مع قصة") -> int:
    due = (datetime.utcnow() - timedelta(hours=hours_ago)).strftime("%Y-%m-%d %H:%M:%S")
    conn = get_conn()
    fid = conn.execute(
        "INSERT INTO followups (device_id, child_id, strategy, topic, lang, due_at) "
        "VALUES (?, ?, ?, 'sleep', ?, ?)", (device, cid, strategy, lang, due),
    ).lastrowid
    conn.commit()
    conn.close()
    return fid


def _pushed_at(fid: int):
    conn = get_conn()
    v = conn.execute("SELECT pushed_at FROM followups WHERE id = ?", (fid,)).fetchone()[0]
    conn.close()
    return v


def test_off_until_the_memory_build_is_named(sent, monkeypatch):
    monkeypatch.delenv("CHILD_MEMORY_MIN_BUILD")
    cid = _device("dev-a")
    _followup("dev-a", cid)
    assert cpt.followup_due() == set()
    assert sent == []


def test_due_followup_is_pushed_once_with_its_deep_link(sent):
    cid = _device("dev-a")
    fid = _followup("dev-a", cid)
    assert cpt.followup_due() == {"dev-a"}
    assert len(sent) == 1
    push = sent[0]
    assert push["data"] == {"type": "followup_due", "link": f"/followup/{fid}",
                            "followup_id": str(fid), "child_id": str(cid)}
    assert "روتين نوم ثابت مع قصة" in push["body"]
    assert "يوسف" not in push["title"] + push["body"]   # no child name to FCM
    assert _pushed_at(fid) is not None
    # Same follow-up, next evening: never twice.
    assert cpt.followup_due() == set()
    assert len(sent) == 1


def test_at_most_one_followup_push_per_device_per_week(sent):
    cid = _device("dev-a")
    _followup("dev-a", cid, hours_ago=5)
    second = _followup("dev-a", cid, hours_ago=3, strategy="ركن هدوء")
    cpt.followup_due()
    assert len(sent) == 1            # one per run, the oldest
    cpt.followup_due()
    assert len(sent) == 1            # and nothing more this week
    assert _pushed_at(second) is None


def test_not_due_old_build_unknown_build_memory_off_or_capped(sent):
    a = _device("dev-future")
    _followup("dev-future", a, hours_ago=-24)           # due tomorrow
    b = _device("dev-old", build=100)
    _followup("dev-old", b)
    c = _device("dev-unknown", build=None)
    _followup("dev-unknown", c)
    d = _device("dev-off")
    _followup("dev-off", d)
    conn = get_conn()
    conn.execute("INSERT INTO child_memory_settings (device_id, enabled) VALUES ('dev-off', 0)")
    conn.commit()
    conn.close()
    e = _device("dev-capped")
    _followup("dev-capped", e)
    assert cpt.followup_due(skip={"dev-capped"}) == set()
    assert sent == []


def test_answered_followups_are_not_pushed(sent):
    cid = _device("dev-a")
    fid = _followup("dev-a", cid)
    conn = get_conn()
    conn.execute("UPDATE followups SET status = 'answered' WHERE id = ?", (fid,))
    conn.commit()
    conn.close()
    assert cpt.followup_due() == set()


def test_english_followup_gets_english_copy(sent):
    cid = _device("dev-en")
    _followup("dev-en", cid, lang="en", strategy="a fixed bedtime routine")
    cpt.followup_due()
    assert sent[0]["title"].startswith("Did the advice help")
    assert "a fixed bedtime routine" in sent[0]["body"]


def test_dry_run_marks_nothing(sent, monkeypatch):
    monkeypatch.setattr(cpt, "DRY_RUN", True)
    cid = _device("dev-a")
    fid = _followup("dev-a", cid)
    cpt.followup_due()
    assert sent == [] and _pushed_at(fid) is None


def test_evening_run_puts_the_followup_first_and_dedupes_the_rest(sent, monkeypatch):
    """Whoever gets a follow-up tonight gets nothing else from this run."""
    cid = _device("dev-a")
    _followup("dev-a", cid)
    skips: dict[str, set] = {}

    def recorder(name, returns=frozenset()):
        def fn(skip=None):
            skips[name] = set(skip or ())
            return set(returns)
        return fn

    monkeypatch.setattr(cpt, "_recently_pushed", lambda: {"dev-capped"})
    monkeypatch.setattr(cpt, "first_lesson_activation", recorder("activation"))
    monkeypatch.setattr(cpt, "streak_at_risk", recorder("streak"))
    monkeypatch.setattr(cpt, "win_back", recorder("win_back"))
    cpt.evening_run()
    assert [p["device"] for p in sent] == ["dev-a"]
    for name in ("activation", "streak", "win_back"):
        assert {"dev-a", "dev-capped"} <= skips[name], name
