"""A path may only promise what its lessons can keep.

A mother opened a path labelled «28 يومًا», found four lessons and finished
them in one sitting. The number lived in four places at once — the path badge,
the path description («لمدة ١٤ يومًا» under a 12-day badge), the onboarding
card («مسارات من ٢٨ يومًا») and the Play listing — and each had to be caught
separately. `duration_problems()` in ops/tools/check_curriculum_schema.py runs
on pre-commit; these tests pin what it must and must not flag.
"""
import importlib.util
import sys
from pathlib import Path

import pytest

_TOOL = (Path(__file__).resolve().parents[2]
         / "ops" / "tools" / "check_curriculum_schema.py")


@pytest.fixture(scope="module")
def chk():
    spec = importlib.util.spec_from_file_location("check_curriculum_schema", _TOOL)
    module = importlib.util.module_from_spec(spec)
    argv, sys.argv = sys.argv, [sys.argv[0]]
    try:
        spec.loader.exec_module(module)
    finally:
        sys.argv = argv
    return module


def _path(n_lessons=4, days=4, description="وصف المسار", pid="path_x"):
    ids = [f"lesson_x_{i:02d}" for i in range(1, n_lessons + 1)]
    return pid, {"id": pid, "title": "عنوان", "description": description,
                 "lesson_ids": ids, "estimated_days": days}


def _lessons(path):
    return {lid: {"id": lid, "path_id": path["id"]} for lid in path["lesson_ids"]}


def _run(chk, paths_ar, paths_en=None, texts=None):
    lessons = {}
    for p in paths_ar.values():
        lessons.update(_lessons(p))
    return chk.duration_problems(paths_ar, paths_en or {}, lessons, texts or {})


def test_the_current_curriculum_keeps_its_promises(chk):
    assert chk.check_durations() == []


def test_honest_path_passes(chk):
    pid, p = _path(4, 4)
    assert _run(chk, {pid: p}) == []


def test_more_days_than_lessons_is_flagged(chk):
    pid, p = _path(4, 12)
    problems = _run(chk, {pid: p})
    assert [f for _, f, _ in problems] == ["estimated_days"]


@pytest.mark.parametrize("description", [
    "رحلة تربوية لمدة 14 يوماً لبناء الثقة",
    "مسار تربوي لمدة ١٠ أيام",
    "A 14-day tarbiyah journey",
    "Four weeks of guidance: 4 weeks",
    "مسار 10 دروس قصيرة",
    "A 10-lesson pathway",
])
def test_a_description_promising_more_is_flagged(chk, description):
    pid, p = _path(4, 4, description=description)
    assert _run(chk, {pid: p}), description


@pytest.mark.parametrize("description", [
    "مسار 4 دروس قصيرة لطفل السنتين",       # true count
    "لطفل (4-6 سنوات) في سن ما قبل المدرسة",  # an age range, not a duration
    "A 4-lesson path for the two-year-old",
])
def test_a_truthful_description_is_not_flagged(chk, description):
    pid, p = _path(4, 4, description=description)
    assert _run(chk, {pid: p}) == [], description


def test_english_overlay_must_not_carry_stale_structure(chk):
    pid, p = _path(12, 12)
    en = dict(p, lesson_ids=p["lesson_ids"][:4], estimated_days=4)
    fields = sorted(f for _, f, _ in _run(chk, {pid: p}, {pid: en}))
    assert fields == ["estimated_days", "lesson_ids"]


def test_a_lesson_listed_but_missing_is_flagged(chk):
    pid, p = _path(4, 4)
    lessons = _lessons(p)
    lessons.pop(p["lesson_ids"][-1])
    problems = chk.duration_problems({pid: p}, {}, lessons, {})
    assert [f for _, f, _ in problems] == ["lesson_ids"]


@pytest.mark.parametrize("line", [
    "مسارات من ٢٨ يومًا",
    "28-Day Paths",
    "28-day learning tracks for every age group",
])
def test_app_and_store_promises_are_capped_by_the_longest_path(chk, line):
    pid, p = _path(12, 12)
    problems = _run(chk, {pid: p}, texts={"app_ar.arb": line})
    assert [f for _, f, _ in problems] == ["promise"], line


def test_unrelated_day_counts_in_app_copy_are_not_paths(chk):
    """Habit stats speak of the last 28 days; that is not a path promise."""
    pid, p = _path(4, 4)
    text = "نسبة إنجاز العادة في آخر ٢٨ يومًا\nShare of the last 28 days"
    assert _run(chk, {pid: p}, texts={"app_ar.arb": text}) == []
