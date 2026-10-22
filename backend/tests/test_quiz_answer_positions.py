"""The correct answer must not sit in a predictable slot.

The app renders quiz options in file order and never shuffles them
(mobile/lib/features/program/models/quiz_deck.dart). On 2026-10-21 a Play
review pointed out what the data confirmed: the correct option was first in
330 of 392 lesson-quiz questions (84%), so a parent could score full marks
without reading. The fix lives in the served data
(ops/tools/balance_quiz_answer_positions.py); this keeps it fixed — a
regenerated quiz written correct-first (scripts/gen_flashcards_quizzes.py
and friends still do that) fails here.
"""
from __future__ import annotations

import collections
import json
from pathlib import Path

import pytest

from app.quiz_data import QUESTIONS

ROOT = Path(__file__).resolve().parents[2]
QUIZ_DIR = ROOT / "docs" / "lesson_assets" / "quizzes"
LICENSE_DIR = ROOT / "knowledge_base" / "curriculum" / "license"
LICENSE_EN_DIR = ROOT / "knowledge_base" / "curriculum" / "i18n" / "en" / "license"
GAMES_DIR = ROOT / "mobile" / "assets" / "content" / "games"
MAX_SHARE_AT_INDEX_0 = 0.40


def _lesson_questions():
    files = sorted(QUIZ_DIR.glob("*.json"))
    if not files:
        # Bare candidate image: .dockerignore strips docs/lesson_assets.
        pytest.skip("docs/lesson_assets/quizzes not present in this checkout")
    for f in files:
        data = json.loads(f.read_text(encoding="utf-8"))
        for i, q in enumerate(data.get("questions", [])):
            yield f.name, i, q


def test_every_lesson_quiz_question_has_exactly_one_correct_answer():
    bad = []
    for name, i, q in _lesson_questions():
        opts = q.get("answerOptions") or []
        n = sum(1 for o in opts if o.get("isCorrect") is True)
        if n != 1 or len(opts) < 2:
            bad.append(f"{name} q{i}: {n} correct of {len(opts)}")
    assert not bad, bad


def test_lesson_quiz_correct_answer_is_not_mostly_first():
    pos = collections.Counter()
    for _, _, q in _lesson_questions():
        opts = q["answerOptions"]
        pos[next(i for i, o in enumerate(opts) if o.get("isCorrect") is True)] += 1
    total = sum(pos.values())
    assert total > 0
    share = pos[0] / total
    assert share <= MAX_SHARE_AT_INDEX_0, (
        f"correct answer at index 0 in {pos[0]}/{total} ({share:.0%}); "
        f"distribution {dict(sorted(pos.items()))}. "
        "Run: python3 ops/tools/balance_quiz_answer_positions.py --write"
    )


def test_no_multi_question_lesson_quiz_always_uses_one_slot():
    per_file = collections.defaultdict(list)
    for name, _, q in _lesson_questions():
        opts = q["answerOptions"]
        per_file[name].append(
            next(i for i, o in enumerate(opts) if o.get("isCorrect") is True))
    mono = {f: p for f, p in per_file.items() if len(p) >= 3 and len(set(p)) == 1}
    assert not mono, mono


def test_program_quiz_bank_answers_are_valid_and_spread():
    pos = collections.Counter()
    for q in QUESTIONS:
        assert 0 <= q["answer"] < len(q["choices"]), q["id"]
        assert len(set(q["choices"])) == len(q["choices"]), q["id"]
        pos[q["answer"]] += 1
    top_share = max(pos.values()) / len(QUESTIONS)
    assert top_share <= MAX_SHARE_AT_INDEX_0, dict(sorted(pos.items()))


# ── child licence scenarios ────────────────────────────────────────────────
# Until 2026-10-21 the `safe` choice was last in 10 of 10 scenarios, so a
# child learned "the long answer at the bottom" rather than the judgement.
# The app renders choices in served order and scores by `key`.

def _license_banks():
    files = sorted(LICENSE_DIR.glob("scenarios_*.json"))
    assert files, "licence banks missing"
    return [(f, json.loads(f.read_text(encoding="utf-8"))) for f in files]


def _safe_slot(scenario):
    slots = [i for i, c in enumerate(scenario["choices"]) if c.get("outcome") == "safe"]
    assert len(slots) == 1, scenario["key"]
    return slots[0]


def test_licence_safe_choice_has_no_favourite_slot():
    pos = collections.Counter()
    n_choices = set()
    for _, bank in _license_banks():
        for s in bank["scenarios"]:
            pos[_safe_slot(s)] += 1
            n_choices.add(len(s["choices"]))
    total = sum(pos.values())
    # With three choices a fair split is a third each; half is the ceiling.
    assert max(pos.values()) / total <= 0.5, dict(sorted(pos.items()))
    last = min(n_choices) - 1
    assert pos[last] / total <= 0.5, f"safe last in {pos[last]}/{total}"


def test_no_licence_bank_always_puts_safe_in_one_slot():
    mono = {}
    for f, bank in _license_banks():
        slots = [_safe_slot(s) for s in bank["scenarios"]]
        if len(slots) >= 3 and len(set(slots)) == 1:
            mono[f.name] = slots
    assert not mono, mono


def test_licence_translation_serves_choices_in_the_arabic_order():
    """The English bank is served wholesale (content_lang.localised), so it
    must carry the same order — else the two languages disagree on where the
    safe answer sits, and one of them drifts back to always-last."""
    for f, bank in _license_banks():
        en_path = LICENSE_EN_DIR / f.name
        if not en_path.exists():
            continue
        en = {s["key"]: s for s in json.loads(en_path.read_text(encoding="utf-8"))["scenarios"]}
        for s in bank["scenarios"]:
            if s["key"] in en:
                assert [c["key"] for c in en[s["key"]]["choices"]] == \
                       [c["key"] for c in s["choices"]], (f.name, s["key"])


# ── app-bundled game packs ─────────────────────────────────────────────────
# First in 200 of 200 until 2026-10-21. Levels are five questions played in
# fixed order with no shuffle, so a level that keeps one slot is a tell too.

def _game_levels():
    files = sorted(GAMES_DIR.glob("*.json"))
    if not files:
        pytest.skip("mobile/assets/content/games not present in this checkout")
    for f in files:
        pack = json.loads(f.read_text(encoding="utf-8"))
        for lv in pack.get("levels", []):
            yield f.name, lv["level"], [
                [i for i, o in enumerate(q["options"]) if o.get("is_correct") is True]
                for q in lv["questions"]]


def test_every_game_question_has_exactly_one_correct_answer():
    bad = [(f, lv, i) for f, lv, qs in _game_levels()
           for i, ok in enumerate(qs) if len(ok) != 1]
    assert not bad, bad


def test_game_correct_answer_has_no_favourite_slot():
    pos = collections.Counter(ok[0] for _, _, qs in _game_levels() for ok in qs)
    total = sum(pos.values())
    assert total > 0
    worst = max(pos.values()) / total
    assert worst <= MAX_SHARE_AT_INDEX_0, (
        f"distribution {dict(sorted(pos.items()))} of {total}. "
        "Run: python3 ops/tools/balance_quiz_answer_positions.py --write")


def test_no_game_level_uses_one_slot_throughout():
    mono = {(f, lv): [ok[0] for ok in qs] for f, lv, qs in _game_levels()
            if len(qs) >= 3 and len({ok[0] for ok in qs}) == 1}
    assert not mono, mono


def test_balancer_is_a_no_op_on_the_committed_data():
    """The committed files are exactly what the balancer writes — so a
    generator that calls balance_quiz() and this tool cannot disagree."""
    import subprocess
    import sys
    tool = ROOT / "ops" / "tools" / "balance_quiz_answer_positions.py"
    if not tool.exists() or not QUIZ_DIR.exists():
        pytest.skip("ops/tools or docs/lesson_assets not in this checkout")
    out = subprocess.run([sys.executable, str(tool)], capture_output=True,
                         text=True, check=False)
    assert out.returncode == 0, out.stdout + out.stderr
    assert "files that would change: 0" in out.stdout, out.stdout
