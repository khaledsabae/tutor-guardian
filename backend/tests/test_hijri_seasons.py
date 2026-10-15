"""«سماوات المواسم» — the three quiet months the sky on «اليوم» marks.

Rajab, Sha'ban and the first days of Dhu al-Hijjah are worked out from the
Ramadan season the server already knows (announced or estimated, and with the
family's own sighting applied), so there is one calendar, not two. An
announced first day (`RAJAB_START_1448=…`) wins over the estimate.

Additive: `/api/programs` gains `hijri_season` (null outside the three) and
`/api/app-config` gains the «على الأفق» strip's kill switch.
"""
from datetime import date

import pytest

from app.services import hijri_seasons as hs
from app.services import ramadan_program as rp
from tests.programs_support import add_child, client, freeze

S1448 = rp.Season(1448, date(2027, 2, 8), 30, "estimate", False)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for name in ("RAMADAN_START_1448", "RAMADAN_DAYS_1448", "RAMADAN_START_1449",
                 "RAMADAN_DAYS_1449", "PROGRAMS_AS_OF_ENABLED", "RAJAB_START_1448",
                 "SHABAN_START_1448", "DHUL_HIJJAH_START_1448", "HORIZON_STRIP_ENABLED"):
        monkeypatch.delenv(name, raising=False)


# ── The service ────────────────────────────────────────────────────────────

def test_rajab_is_two_months_before_ramadan():
    where = hs.locate(date(2026, 12, 11), [S1448])
    assert where == {"month": "rajab", "hijri_year": 1448, "day": 1,
                     "starts_on": "2026-12-11", "ends_on": "2027-01-09",
                     "start_source": "derived"}


def test_shaban_runs_up_to_the_first_night_of_ramadan():
    assert hs.locate(date(2027, 1, 10), [S1448])["month"] == "shaban"
    assert hs.locate(date(2027, 2, 7), [S1448])["month"] == "shaban"
    assert hs.locate(date(2027, 2, 7), [S1448])["day"] == 29
    # The month itself has its own skin (the lantern string): not a season here.
    assert hs.locate(date(2027, 2, 8), [S1448]) is None


def test_dhul_hijjah_is_its_first_thirteen_days_only():
    # Eid al-Fitr 2027-03-10; Shawwal and Dhu al-Qa'dah ≈ 59 days.
    first = hs.locate(date(2027, 5, 8), [S1448])
    assert first["month"] == "dhul_hijjah" and first["day"] == 1
    assert hs.locate(date(2027, 5, 20), [S1448])["day"] == 13
    assert hs.locate(date(2027, 5, 21), [S1448]) is None
    assert hs.locate(date(2027, 5, 7), [S1448]) is None


def test_quiet_days_have_no_season():
    for day in (date(2026, 10, 15), date(2026, 12, 10), date(2027, 3, 1),
                date(2027, 4, 20)):
        assert hs.locate(day, [S1448]) is None, day
    assert hs.locate(date(2026, 12, 20), []) is None


def test_the_family_sighting_moves_the_derived_months_with_ramadan():
    shifted = rp.Season(1448, date(2027, 2, 9), 30, "estimate", False, shift_days=1)
    assert hs.locate(date(2026, 12, 11), [shifted]) is None
    assert hs.locate(date(2026, 12, 12), [shifted])["day"] == 1


def test_an_announced_first_day_wins(monkeypatch):
    monkeypatch.setenv("RAJAB_START_1448", "2026-12-12")
    assert hs.locate(date(2026, 12, 11), [S1448]) is None
    where = hs.locate(date(2026, 12, 12), [S1448])
    assert where["day"] == 1 and where["start_source"] == "configured"
    monkeypatch.setenv("DHUL_HIJJAH_START_1448", "2027-05-07")
    assert hs.locate(date(2027, 5, 7), [S1448])["month"] == "dhul_hijjah"


def test_a_malformed_setting_is_ignored(monkeypatch):
    monkeypatch.setenv("SHABAN_START_1448", "soon")
    assert hs.locate(date(2027, 1, 10), [S1448])["start_source"] == "derived"


# ── /api/programs ──────────────────────────────────────────────────────────

def test_programs_reports_the_season(monkeypatch):
    c = client()
    add_child(c)
    freeze(monkeypatch, "2026-12-15T09:00:00")
    body = c.get("/api/programs", params={"tz_offset_minutes": 180}).json()
    assert body["hijri_season"]["month"] == "rajab"
    assert body["hijri_season"]["day"] == 5
    # Additive: every field an older build reads is still there.
    assert body["ramadan"]["state"] == "upcoming"


def test_programs_season_is_null_on_a_quiet_day(monkeypatch):
    c = client()
    add_child(c)
    freeze(monkeypatch, "2026-10-15T09:00:00")
    body = c.get("/api/programs", params={"tz_offset_minutes": 180}).json()
    assert "hijri_season" in body and body["hijri_season"] is None


def test_programs_season_follows_the_familys_own_sighting(monkeypatch):
    c = client()
    add_child(c)
    freeze(monkeypatch, "2026-12-11T09:00:00")
    r = c.put("/api/programs/ramadan/settings", params={"tz_offset_minutes": 0},
              json={"start_shift_days": 1})
    assert r.status_code == 200, r.text
    body = c.get("/api/programs", params={"tz_offset_minutes": 0}).json()
    assert body["hijri_season"] is None


def test_programs_season_without_the_ramadan_file_is_null(monkeypatch):
    from app.services import programs_common as pc

    real = pc.load_program

    def no_ramadan(name, lang=None):
        if name == rp.PROGRAM:
            raise pc.ProgramUnavailable(name)
        return real(name, lang)

    monkeypatch.setattr(pc, "load_program", no_ramadan)
    c = client()
    add_child(c)
    freeze(monkeypatch, "2026-12-15T09:00:00")
    body = c.get("/api/programs", params={"tz_offset_minutes": 0}).json()
    assert body["hijri_season"] is None


# ── /api/app-config ────────────────────────────────────────────────────────

def test_app_config_carries_the_horizon_strip_kill_switch(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.routers.health import router

    app = FastAPI()
    app.include_router(router)
    c = TestClient(app)
    assert c.get("/api/app-config").json()["horizon_strip_enabled"] is True
    for off in ("0", "false", "OFF", "no"):
        monkeypatch.setenv("HORIZON_STRIP_ENABLED", off)
        assert c.get("/api/app-config").json()["horizon_strip_enabled"] is False
    monkeypatch.setenv("HORIZON_STRIP_ENABLED", "1")
    assert c.get("/api/app-config").json()["horizon_strip_enabled"] is True
