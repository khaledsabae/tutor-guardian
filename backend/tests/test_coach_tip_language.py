"""The Home tab's most prominent card, in the reader's language.

Seen on an emulator set to English, running 1.0.52: every label on the Home tab
was English and the «Smart Parenting Insights» card body was Arabic —
«راجع ألعاب طفلك: احذف أي لعبة فيها عنف/دم…». `getCoachTip` was the one content
read in the client that never carried `?lang=`, and the endpoint had no such
parameter to carry it to.

That is the same omission that left 170 translated lessons unread until
2026-08-13, surviving in the one place the sweep missed.

The personalised tip stays Arabic-only on purpose: it is validated by
`_is_core_ok` and `_pronoun_consistent`, both Arabic-language heuristics, and an
English reader is better served by a translated daily tip than by generated text
nothing checked.
"""
import asyncio

import pytest

from app.db.init_db import get_conn, init_db
from app.services import coach_service

DEVICE = "tip-lang-device"


@pytest.fixture
def child(tmp_path, monkeypatch):
    monkeypatch.setenv("CONVERSATIONS_DB", str(tmp_path / "tips.db"))
    init_db()
    conn = get_conn()
    try:
        cur = conn.execute(
            "INSERT INTO child_profiles (device_id, name, age_group, gender) "
            "VALUES (?, ?, ?, ?)",
            (DEVICE, "Adam", "7-9", "male"),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def _has_arabic(text: str) -> bool:
    return any("؀" <= ch <= "ۿ" for ch in text)


def test_an_english_reader_gets_a_tip_with_no_arabic_in_it(child):
    tip = asyncio.run(coach_service.get_proactive_tip(DEVICE, child, lang="en"))
    assert tip["text"]
    assert not _has_arabic(tip["text"]), tip["text"]


def test_an_arabic_reader_still_gets_arabic(child):
    tip = asyncio.run(coach_service.get_proactive_tip(DEVICE, child, lang="ar"))
    assert _has_arabic(tip["text"]), tip["text"]


def test_no_language_asked_for_is_still_arabic(child):
    """Every build already on Play sends no `lang`. They must keep the exact
    behaviour they have today."""
    tip = asyncio.run(coach_service.get_proactive_tip(DEVICE, child))
    assert _has_arabic(tip["text"]), tip["text"]


def test_the_cache_does_not_serve_one_language_to_the_other(child):
    """One row per device/child/day meant the first reader's language won the
    whole day: a household reading in English got the Arabic tip its
    Arabic-reading parent had opened that morning, fixed until midnight."""
    arabic = asyncio.run(coach_service.get_proactive_tip(DEVICE, child, lang="ar"))
    english = asyncio.run(coach_service.get_proactive_tip(DEVICE, child, lang="en"))

    assert _has_arabic(arabic["text"])
    assert not _has_arabic(english["text"])

    # And back again, from the rewritten row.
    again = asyncio.run(coach_service.get_proactive_tip(DEVICE, child, lang="ar"))
    assert _has_arabic(again["text"])


def test_the_same_day_is_stable_within_one_language(child):
    """The tip must not reroll on every open — the property the daily hash
    exists to guarantee, which the language key must not break."""
    first = asyncio.run(coach_service.get_proactive_tip(DEVICE, child, lang="en"))
    second = asyncio.run(coach_service.get_proactive_tip(DEVICE, child, lang="en"))
    assert first["text"] == second["text"]


# No pytest-asyncio in this repo — these are the first async paths under test,
# and `asyncio.run` keeps that true rather than adding a plugin for five cases.
