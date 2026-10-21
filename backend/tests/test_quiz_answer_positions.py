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

QUIZ_DIR = Path(__file__).resolve().parents[2] / "docs" / "lesson_assets" / "quizzes"
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
