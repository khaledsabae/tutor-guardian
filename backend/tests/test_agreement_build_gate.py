"""The agreement gate must not lock out a build that cannot sign.

The gate has been finished, tested and switched **off** since 2026-08-16, for
one reason: it is server-side, so it applies to every client at once, and its
only exit is a screen that older builds do not have. Turning it on would have
locked every family out of child mode with no way back in — it did not happen
on 2026-08-16 only because the deploy was cancelled with four minutes to spare.

The written unlock condition was "raise MINIMUM_BUILD_NUMBER above the build
carrying the screens", i.e. force-update thousands of devices to unlock one
flag. With a build census (schema v25) the same question is answerable per
device, so these tests pin the property that makes the flag safe to switch on:
a device is gated only when its own build can reach the signing screen.
"""
import pytest

from app.db.init_db import get_conn, init_db
from app.services.child_budget import AGREEMENT_MIN_BUILD, device_can_sign

DEVICE = "gate-device-1"


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("CONVERSATIONS_DB", str(tmp_path / "gate.db"))
    init_db()
    return tmp_path


def _register(build):
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO push_tokens (device_id, token, platform, updated_at, "
            "app_version, build_number) VALUES (?, 't', 'android', "
            "datetime('now'), ?, ?)",
            (DEVICE, "x", build),
        )
        conn.commit()
    finally:
        conn.close()


def test_a_current_build_can_be_gated(db):
    _register(AGREEMENT_MIN_BUILD)
    assert device_can_sign(DEVICE) is True


def test_the_build_before_the_screens_is_never_gated(db):
    # 86 is the last build without a reachable signing screen. Gating it is the
    # lockout this whole mechanism exists to prevent.
    _register(AGREEMENT_MIN_BUILD - 1)
    assert device_can_sign(DEVICE) is False


def test_a_much_older_build_is_never_gated(db):
    _register(74)
    assert device_can_sign(DEVICE) is False


def test_a_newer_build_is_gated(db):
    _register(96)
    assert device_can_sign(DEVICE) is True


def test_an_unknown_device_is_not_gated(db):
    """Never seen: no push registration at all. Guessing "new" costs a lockout;
    guessing "old" costs one unsigned session that the next launch corrects."""
    assert device_can_sign("never-seen-device") is False


def test_a_device_that_reported_no_build_is_not_gated(db):
    """Every build already on Play registers without a version — thousands of
    them. They must all read as "cannot sign" until they update and say so."""
    _register(None)
    assert device_can_sign(DEVICE) is False


def test_a_database_without_the_census_column_does_not_lock_anyone_out(
    tmp_path, monkeypatch
):
    """Production ran for weeks on a schema with no `build_number`. If a missing
    column raised instead of answering "no", switching the flag on would fail
    every child-mode request rather than skipping the gate."""
    monkeypatch.setenv("CONVERSATIONS_DB", str(tmp_path / "old.db"))
    conn = get_conn()
    try:
        conn.execute(
            "CREATE TABLE push_tokens (device_id TEXT PRIMARY KEY, token TEXT, "
            "platform TEXT, updated_at TEXT)"
        )
        conn.execute(
            "INSERT INTO push_tokens (device_id, token, platform, updated_at) "
            "VALUES (?, 't', 'android', datetime('now'))",
            (DEVICE,),
        )
        conn.commit()
    finally:
        conn.close()
    assert device_can_sign(DEVICE) is False


def test_the_floor_is_the_build_that_shipped_the_screens(db):
    """87 = 1.0.42+87, the first released build whose signing screens are both
    present (07c34a8b) and reachable (b92e0d40). Lowering this to 86 reopens the
    lockout; raising it needlessly delays the gate for builds that can sign."""
    assert AGREEMENT_MIN_BUILD == 87
