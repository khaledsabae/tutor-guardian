"""«سماوات المواسم» — Rajab, Sha'ban and the first days of Dhu al-Hijjah.

The sky on «اليوم» carries one quiet paper touch in these three seasons (as
it carries a lantern string in Ramadan). This module only says *which* season
a family's day falls in; it writes no text, and nothing here is a reminder,
a count or a reward.

**One calendar, not two.** The months are worked out from the Ramadan season
the server already holds (`ramadan_program.family_seasons` — announced or
estimated, with the family's own sighting applied), so the sky and the
Ramadan street can never disagree about where the year is:

  * Rajab starts 59 days before the first day of Ramadan (Rajab + Sha'ban
    ≈ 59.06 days), Sha'ban 29 days before. Both run up to the next month.
  * Dhu al-Hijjah starts 59 days after Eid al-Fitr (Shawwal + Dhu al-Qa'dah
    ≈ 59.06 days), and the sky marks its first thirteen days only — the ten
    days, the day of Eid and the days after it — not the quiet rest.

A derived start can be a day off a sighted one. That only moves a paper
decoration by a day, and an announced start (`RAJAB_START_1448=YYYY-MM-DD`,
`SHABAN_START_…`, `DHUL_HIJJAH_START_…`) wins over the derivation, read per
call like `RAMADAN_START_<year>`.
"""
from __future__ import annotations

import logging
import os
from datetime import date, timedelta
from typing import Any, Optional

from app.services import ramadan_program as rp

logger = logging.getLogger(__name__)

RAJAB = "rajab"
SHABAN = "shaban"
DHUL_HIJJAH = "dhul_hijjah"

RAJAB_BEFORE_RAMADAN = 59
SHABAN_BEFORE_RAMADAN = 29
DHUL_HIJJAH_AFTER_EID = 59
DHUL_HIJJAH_DAYS_SHOWN = 13

_ENV = {RAJAB: "RAJAB_START_{}", SHABAN: "SHABAN_START_{}",
        DHUL_HIJJAH: "DHUL_HIJJAH_START_{}"}


def _announced(month: str, year: int) -> Optional[date]:
    name = _ENV[month].format(year)
    raw = os.environ.get(name, "").strip()
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        logger.warning("%s=%r is not YYYY-MM-DD — ignored", name, raw)
        return None


def _windows(season: rp.Season) -> list[tuple[str, date, date, str]]:
    """(month, first day, last day inclusive, start_source) for one season."""

    def start(month: str, derived: date) -> tuple[date, str]:
        announced = _announced(month, season.hijri_year)
        return (announced, "configured") if announced else (derived, "derived")

    rajab, rajab_src = start(RAJAB, season.start - timedelta(days=RAJAB_BEFORE_RAMADAN))
    shaban, shaban_src = start(SHABAN, season.start - timedelta(days=SHABAN_BEFORE_RAMADAN))
    hijjah, hijjah_src = start(DHUL_HIJJAH, season.eid + timedelta(days=DHUL_HIJJAH_AFTER_EID))
    return [
        (RAJAB, rajab, shaban - timedelta(days=1), rajab_src),
        (SHABAN, shaban, season.start - timedelta(days=1), shaban_src),
        (DHUL_HIJJAH, hijjah, hijjah + timedelta(days=DHUL_HIJJAH_DAYS_SHOWN - 1), hijjah_src),
    ]


def locate(today: date, seasons: list[rp.Season]) -> Optional[dict[str, Any]]:
    """The season `today` falls in, or None on every other day.

    `{month, hijri_year, day, starts_on, ends_on, start_source}` — `day` is
    the day of the Hijri month (1-based), `ends_on` the last day the sky
    marks, `start_source` is `derived` or `configured`."""
    for season in seasons:
        for month, first, last, source in _windows(season):
            if first <= today <= last:
                return {"month": month, "hijri_year": season.hijri_year,
                        "day": (today - first).days + 1,
                        "starts_on": first.isoformat(), "ends_on": last.isoformat(),
                        "start_source": source}
    return None
