"""ops/scripts/send_update_push.py — nudge only the devices that need it.

The first version sent to every token ever registered: people already on the
new build were told to update, and installs abandoned months ago got it too.
It also defaulted to a stale message and sent on a bare run.
"""
import importlib.util
from pathlib import Path

import pytest

from app.db.init_db import get_conn, init_db
from app.services import push_sender

SCRIPT = Path(__file__).resolve().parents[2] / "ops" / "scripts" / "send_update_push.py"


@pytest.fixture
def mod():
    spec = importlib.util.spec_from_file_location("send_update_push", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def census():
    init_db()
    rows = [
        ("new", 111, "-1 days"),
        ("on105", 105, "-1 days"),
        ("on101", 101, "-2 days"),
        ("old", None, "-3 days"),          # before the census: below any build
        ("gone", 101, "-200 days"),        # abandoned: not nudged
    ]
    conn = get_conn()
    for dev, build, age in rows:
        conn.execute(
            "INSERT INTO push_tokens (device_id, token, platform, updated_at, build_number) "
            "VALUES (?, ?, 'android', datetime('now', ?), ?)",
            (dev, f"tok-{dev}", age, build),
        )
    conn.commit()
    conn.close()


def test_targets_only_active_devices_below_the_build(mod, census):
    got = {d for d, _ in mod.target_devices(below=111, active_days=30)}
    assert got == {"on105", "on101", "old"}


def test_limit_takes_the_most_recently_active_first(mod, census):
    got = [d for d, _ in mod.target_devices(below=111, active_days=30, limit=2)]
    assert got == ["on105", "on101"]


def test_a_bare_run_sends_nothing(mod, census, monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(push_sender, "send_to_device", lambda *a, **k: calls.append(a))
    assert mod.main(["--below", "111", "--title", "t", "--body", "b"]) == 0
    assert calls == []
    out = capsys.readouterr().out
    assert "audience: 3 device(s) below 111" in out
    assert "105×1, 101×1, unknown×1" in out
    assert "dry run" in out


def test_send_reaches_the_audience_with_a_typed_payload(mod, census, monkeypatch, capsys):
    sent = []

    def fake(device_id, **kwargs):
        sent.append((device_id, kwargs["data"]))
        return {"ok": True, "sent": True}

    monkeypatch.setattr(push_sender, "_ensure_app", lambda: True)
    monkeypatch.setattr(push_sender, "send_to_device", fake)
    assert mod.main(["--below", "111", "--title", "t", "--body", "b", "--send"]) == 0
    assert {d for d, _ in sent} == {"on105", "on101", "old"}
    assert all(data == {"type": "app_update"} for _, data in sent)
    out = capsys.readouterr().out
    assert "sent 3" in out
    assert "on101" not in out                       # device ids stay out of output


def test_title_body_and_target_are_required(mod):
    with pytest.raises(SystemExit):
        mod.main(["--send"])
