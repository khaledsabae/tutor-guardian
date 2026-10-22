#!/usr/bin/env python3
"""Spread the correct answer across positions in every backend-served quiz.

Why: a Play review caught it and the data confirmed it — in
docs/lesson_assets/quizzes the correct option sat first in 330 of 392
questions (84%). The app renders options in file order and never shuffles
(mobile/lib/features/program/models/quiz_deck.dart), and the app is frozen,
so the fix lives in the data the backend serves.

Sources handled:
  * docs/lesson_assets/quizzes/*.json   (GET /api/program/asset-content/{id})
  * backend/app/quiz_data.py QUESTIONS  (GET /api/program/quiz) — the
    correct choice sat second in 24 of 29.
  * knowledge_base/curriculum/license/scenarios_*.json and their
    i18n/en/license/ translations (GET /api/child-mode/license/today) — the
    `safe` choice sat last in 10 of 10. Scoring is by choice `key`
    (services/child_license._outcome_of), never by position; the English
    bank is put in the Arabic bank's order so both languages agree.

Generators import `balance_quiz()` and call it before writing a quiz, so a
freshly generated file is already in its final order (and a rerun of this
tool over it is a no-op).

Deterministic and idempotent: the output depends only on the *set* of
options, never on their current order, so a rerun is a no-op.
  * Distractor order: sorted by sha256(file|question|option text).
  * Correct position: (sha256(file) + question index) mod n_options — so
    consecutive questions in one quiz never share a position (for n>1) and
    files start at hash-spread offsets, giving a near-uniform global split.
  * Options whose meaning depends on position («كل ما سبق», "none of the
    above", «كلاهما» …) are pinned last.

Usage:
  python3 ops/tools/balance_quiz_answer_positions.py           # report only
  python3 ops/tools/balance_quiz_answer_positions.py --write   # rewrite files
"""
from __future__ import annotations

import argparse
import ast
import collections
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
QUIZ_DIR = ROOT / "docs" / "lesson_assets" / "quizzes"
QUIZ_DATA_PY = ROOT / "backend" / "app" / "quiz_data.py"
LICENSE_DIR = ROOT / "knowledge_base" / "curriculum" / "license"
LICENSE_EN_DIR = ROOT / "knowledge_base" / "curriculum" / "i18n" / "en" / "license"

# Whole-option matches only: «كلاهما» inside a sentence that names two things
# from the question is not a reference to other options.
PINNED = re.compile(
    r"^\s*(?:"
    r"(?:كل|جميع)\s+(?:ما\s+سبق|ما\s+ذُ?كِ?ر|الإجابات(?:\s+السابقة)?|الخيارات(?:\s+السابقة)?)"
    r"|(?:لا\s+شيء|ولا\s+واحد(?:ة)?|لا\s+أحد)\s+مما\s+(?:سبق|ذُ?كِ?ر)"
    r"|ليس\s+مما\s+سبق"
    r"|كلاهما(?:\s+(?:صحيح|صحيحان|خطأ))?"
    r"|كلا\s+الخيارين(?:\s+\S+)?"
    r"|(?:all|none|both)\s+of\s+the\s+above"
    r"|both"
    r")\s*[.!،]?\s*$",
    re.IGNORECASE,
)

# Text that points at an option by its slot. Temporal «الأولى» (first months,
# first hour) is everywhere in this content, so only option-anchored phrasings.
POSITIONAL = re.compile(
    r"(?:الخيار|الإجابة|الاختيار)\s*(?:الأول|الأولى|الثاني|الثانية|الثالث|الثالثة|الرابع|الرابعة|الأخير|الأخيرة|[أبجد](?![ء-ي]))"
    r"|\(\s*[أبجد]\s*\)"
    r"|\b(?:option|answer|choice)\s+(?:[a-d1-4]\b|one|two|three|four)"
    r"|\b(?:first|second|third|last)\s+(?:option|answer|choice)"
    r"|(?:of\s+the\s+)?above\b"
    r"|مما\s+سبق|ما\s+سبق|أعلاه",
    re.IGNORECASE,
)


def _h(*parts: str) -> int:
    return int(hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest(), 16)


def plan_order(seed: str, qtext: str, index: int, texts: list[str],
               correct: int) -> list[int]:
    """Return the new order as a list of old indices."""
    n = len(texts)
    pinned = [i for i in range(n) if PINNED.match(texts[i])]
    free = [i for i in range(n) if i not in pinned]
    if correct in pinned:
        # Position is meaning; leave the correct one at the tail.
        body = sorted(free, key=lambda i: _h(seed, qtext, texts[i]))
        return body + pinned
    distractors = sorted((i for i in free if i != correct),
                         key=lambda i: _h(seed, qtext, texts[i]))
    target = (_h(seed) + index) % len(free)
    return distractors[:target] + [correct] + distractors[target:] + pinned


def validate_quiz(path: Path, data: dict) -> list[str]:
    errs = []
    for qi, q in enumerate(data.get("questions", [])):
        opts = q.get("answerOptions") or []
        n_ok = sum(1 for o in opts if o.get("isCorrect") is True)
        if len(opts) < 2:
            errs.append(f"{path.name} q{qi}: {len(opts)} options")
        if n_ok != 1:
            errs.append(f"{path.name} q{qi}: {n_ok} correct options")
    return errs


def _new_report() -> dict:
    return {"before": collections.Counter(), "after": collections.Counter(),
            "py_before": collections.Counter(), "py_after": collections.Counter(),
            "lic_before": collections.Counter(), "lic_after": collections.Counter(),
            "per_file": collections.defaultdict(list), "pinned": [],
            "positional": [], "changed": 0}


def balance_quiz(name: str, data: dict, report: dict | None = None) -> list[str]:
    """Reorder `data["questions"][*]["answerOptions"]` in place.

    `name` is the quiz file's base name (`gen_x_qz.json`) — it seeds the
    order, so calling this from a generator gives exactly what a later run of
    this tool would. Returns validation errors; on error `data` is untouched.
    """
    report = report if report is not None else _new_report()
    errs = validate_quiz(Path(name), data)
    if errs:
        return errs
    orig = json.loads(json.dumps(data))
    for qi, q in enumerate(data["questions"]):
        opts = q["answerOptions"]
        texts = [o["text"] for o in opts]
        correct = next(i for i, o in enumerate(opts) if o["isCorrect"])
        report["before"][correct] += 1
        for i, t in enumerate(texts):
            if PINNED.match(t):
                report["pinned"].append(f"{name} q{qi} opt{i}: {t}")
        for label, t in [("hint", q.get("hint") or ""),
                         ("question", q["question"])] + \
                        [(f"rationale{i}", o.get("rationale") or "")
                         for i, o in enumerate(opts)]:
            if t and POSITIONAL.search(t):
                report["positional"].append(f"{name} q{qi} {label}: {t}")
        order = plan_order(name, q["question"], qi, texts, correct)
        q["answerOptions"] = [opts[i] for i in order]
        new_correct = order.index(correct)
        report["after"][new_correct] += 1
        report["per_file"][name].append(new_correct)
    errs = validate_quiz(Path(name), data)
    # Same questions, same option objects — only the order moved.
    key = lambda o: json.dumps(o, ensure_ascii=False, sort_keys=True)  # noqa: E731
    for a, b in zip(data["questions"], orig["questions"]):
        if sorted(map(key, a["answerOptions"])) != sorted(map(key, b["answerOptions"])):
            errs.append(f"{name}: option set changed")
        if {k: v for k, v in a.items() if k != "answerOptions"} != \
           {k: v for k, v in b.items() if k != "answerOptions"}:
            errs.append(f"{name}: question fields changed")
    if errs:
        data.clear()
        data.update(orig)
    return errs


def process_lesson_quizzes(write: bool, report: dict) -> int:
    errors = 0
    for path in sorted(QUIZ_DIR.glob("*.json")):
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
        errs = balance_quiz(path.name, data, report)
        if errs:
            print("\n".join(errs))
            errors += len(errs)
            continue
        out = json.dumps(data, ensure_ascii=False, indent=2)
        if raw.endswith("\n"):
            out += "\n"
        if out != raw:
            report["changed"] += 1
            if write:
                path.write_text(out, encoding="utf-8")
    return errors


# ── child licence scenarios ────────────────────────────────────────────────

_CHOICES_BLOCK = re.compile(r'("choices":\s*\[\n)(.*?)(\n[ \t]*\])', re.DOTALL)


def _rewrite_choice_lines(raw: str, orders: list[list[str]]) -> str | None:
    """Reorder the one-choice-per-line blocks of a hand-formatted bank,
    keeping every other byte. None when the file isn't laid out that way."""
    blocks = list(_CHOICES_BLOCK.finditer(raw))
    if len(blocks) != len(orders):
        return None
    out, last = [], 0
    for m, order in zip(blocks, orders):
        lines = m.group(2).split("\n")
        try:
            by_key = {json.loads(ln.rstrip().rstrip(","))["key"]: ln.rstrip().rstrip(",")
                      for ln in lines}
        except (ValueError, KeyError, TypeError):
            return None
        if sorted(by_key) != sorted(order) or len(by_key) != len(lines):
            return None
        body = ",\n".join(by_key[k] for k in order)
        out.append(raw[last:m.start(2)] + body)
        last = m.end(2)
    out.append(raw[last:])
    return "".join(out)


def _dump_bank(raw: str, data: dict, orders: list[list[str]]) -> str:
    new = _rewrite_choice_lines(raw, orders)
    if new is not None and json.loads(new) == data:
        return new
    out = json.dumps(data, ensure_ascii=False, indent=2)
    return out + "\n" if raw.endswith("\n") else out


def license_choice_order(seed: str, index: int, scenario: dict) -> list[str]:
    """Choice keys in serving order; `safe` lands at a spread position."""
    choices = scenario["choices"]
    safe = [i for i, c in enumerate(choices) if c.get("outcome") == "safe"]
    if len(safe) != 1 or len({c["key"] for c in choices}) != len(choices):
        raise ValueError(f"{seed} {scenario.get('key')}: "
                         f"{len(safe)} safe choices / duplicate keys")
    order = plan_order(seed, scenario["key"], index,
                       [c["text_ar"] for c in choices], safe[0])
    return [choices[i]["key"] for i in order]


def process_license_scenarios(write: bool, report: dict) -> int:
    errors = 0
    for path in sorted(LICENSE_DIR.glob("scenarios_*.json")):
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
        orig = json.loads(raw)
        orders: list[list[str]] = []
        try:
            for si, s in enumerate(data["scenarios"]):
                keys = [c["key"] for c in s["choices"]]
                report["lic_before"][next(i for i, c in enumerate(s["choices"])
                                          if c.get("outcome") == "safe")] += 1
                order = license_choice_order(path.name, si, s)
                by_key = {c["key"]: c for c in s["choices"]}
                s["choices"] = [by_key[k] for k in order]
                orders.append(order)
                report["lic_after"][order.index(
                    next(k for k in keys if by_key[k]["outcome"] == "safe"))] += 1
                report["per_file"][path.name].append(
                    next(i for i, c in enumerate(s["choices"]) if c["outcome"] == "safe"))
        except (ValueError, KeyError, StopIteration) as e:
            print(f"licence {path.name}: {e}")
            errors += 1
            continue
        targets = [(path, raw, data, orders)]

        # The translation follows the Arabic order, choice by choice key.
        en_path = LICENSE_EN_DIR / path.name
        if en_path.exists():
            en_raw = en_path.read_text(encoding="utf-8")
            en = json.loads(en_raw)
            en_scen = {s["key"]: s for s in en.get("scenarios", [])}
            for s, order in zip(data["scenarios"], orders):
                es = en_scen.get(s["key"])
                if es is None:
                    continue  # the loader falls back per bank; nothing to align
                ek = {c["key"]: c for c in es["choices"]}
                if sorted(ek) != sorted(order):
                    print(f"licence en/{path.name} {s['key']}: choice keys differ from ar")
                    errors += 1
                    continue
                es["choices"] = [ek[k] for k in order]
            en_orders = [[c["key"] for c in s["choices"]] for s in en["scenarios"]]
            targets.append((en_path, en_raw, en, en_orders))

        # Validate: same scenarios, same choice objects, only order moved.
        key = lambda o: json.dumps(o, ensure_ascii=False, sort_keys=True)  # noqa: E731
        for a, b in zip(data["scenarios"], orig["scenarios"]):
            if sorted(map(key, a["choices"])) != sorted(map(key, b["choices"])) or \
               {k: v for k, v in a.items() if k != "choices"} != \
               {k: v for k, v in b.items() if k != "choices"}:
                print(f"licence {path.name} {a['key']}: validation failed")
                errors += 1
        if errors:
            continue
        for p, r, d, o in targets:
            out = _dump_bank(r, d, o)
            if out != r:
                report["changed"] += 1
                if write:
                    p.write_text(out, encoding="utf-8")
    return errors


def process_quiz_data_py(write: bool, report: dict) -> int:
    """Reorder `choices` + fix `answer` in place, preserving the source text."""
    src = QUIZ_DATA_PY.read_text(encoding="utf-8")
    lines = src.splitlines(keepends=True)
    offsets = [0]
    for ln in lines:
        offsets.append(offsets[-1] + len(ln))

    def pos(lineno: int, col: int) -> int:
        # ast columns are UTF-8 byte offsets.
        line = lines[lineno - 1]
        return offsets[lineno - 1] + len(line.encode("utf-8")[:col].decode("utf-8"))

    tree = ast.parse(src)
    edits: list[tuple[int, int, str]] = []
    errors = 0
    qi = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        keys = {k.value: v for k, v in zip(node.keys, node.values)
                if isinstance(k, ast.Constant)}
        if not {"id", "choices", "answer", "question"} <= keys.keys():
            continue
        choices, answer = keys["choices"], keys["answer"]
        if not isinstance(choices, ast.List) or not isinstance(answer, ast.Constant):
            continue  # e.g. a translated view built from a QUESTIONS entry
        texts = [ast.literal_eval(e) for e in choices.elts]
        correct = ast.literal_eval(answer)
        if not (isinstance(correct, int) and 0 <= correct < len(texts)):
            print(f"quiz_data {keys['id'].value}: bad answer {correct}")
            errors += 1
            continue
        report["py_before"][correct] += 1
        qid = ast.literal_eval(keys["id"])
        for t in texts:
            if PINNED.match(t):
                report["pinned"].append(f"quiz_data.py {qid}: {t}")
        comment = keys.get("comment")
        if comment is not None:
            ctext = ast.literal_eval(comment)
            if POSITIONAL.search(ctext):
                report["positional"].append(f"quiz_data.py {qid} comment: {ctext}")
        # Seed per question id so position doesn't hinge on the file name;
        # index steps through the list so neighbours differ.
        order = plan_order("quiz_data.py", qid, qi, texts, correct)
        qi += 1
        segs = [(pos(e.lineno, e.col_offset), pos(e.end_lineno, e.end_col_offset))
                for e in choices.elts]
        seg_text = [src[a:b] for a, b in segs]
        for slot, old in enumerate(order):
            edits.append((segs[slot][0], segs[slot][1], seg_text[old]))
        new_correct = order.index(correct)
        edits.append((pos(answer.lineno, answer.col_offset),
                      pos(answer.end_lineno, answer.end_col_offset),
                      str(new_correct)))
        report["py_after"][new_correct] += 1
    new = src
    for a, b, t in sorted(edits, reverse=True):
        new = new[:a] + t + new[b:]
    # Validate: same questions, same choice sets, answer points at same text.
    old_q = _load_questions(src)
    new_q = _load_questions(new)
    for o, n in zip(old_q, new_q):
        if sorted(o["choices"]) != sorted(n["choices"]) or \
           o["choices"][o["answer"]] != n["choices"][n["answer"]] or \
           {k: v for k, v in o.items() if k not in ("choices", "answer")} != \
           {k: v for k, v in n.items() if k not in ("choices", "answer")}:
            print(f"quiz_data {o['id']}: validation failed")
            errors += 1
    if len(old_q) != len(new_q):
        errors += 1
    if not errors and new != src:
        report["changed"] += 1
        if write:
            QUIZ_DATA_PY.write_text(new, encoding="utf-8")
    return errors


def _load_questions(src: str) -> list[dict]:
    ns: dict = {}
    exec(compile(src, "quiz_data.py", "exec"), ns)  # noqa: S102 — our own file
    return ns["QUESTIONS"]


def _dist(c: collections.Counter) -> str:
    total = sum(c.values()) or 1
    return "  ".join(f"[{k}]={v} ({v * 100 / total:.0f}%)" for k, v in sorted(c.items()))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--write", action="store_true", help="rewrite files")
    args = ap.parse_args()
    report = _new_report()
    errors = process_lesson_quizzes(args.write, report)
    errors += process_quiz_data_py(args.write, report)
    errors += process_license_scenarios(args.write, report)

    print(f"lesson quizzes  before: {_dist(report['before'])}")
    print(f"lesson quizzes  after:  {_dist(report['after'])}")
    print(f"quiz_data.py    before: {_dist(report['py_before'])}")
    print(f"quiz_data.py    after:  {_dist(report['py_after'])}")
    print(f"licence safe    before: {_dist(report['lic_before'])}")
    print(f"licence safe    after:  {_dist(report['lic_after'])}")
    mono = [f for f, p in report["per_file"].items() if len(p) > 1 and len(set(p)) == 1]
    print(f"multi-question quizzes with a single correct position after: {len(mono)}")
    for f in mono:
        print("  ", f, report["per_file"][f])
    print(f"pinned options: {len(report['pinned'])}")
    for p in report["pinned"]:
        print("  ", p)
    print(f"position-referencing text: {len(report['positional'])}")
    for p in report["positional"]:
        print("  ", p)
    print(f"files {'rewritten' if args.write else 'that would change'}: {report['changed']}")
    if errors:
        print(f"ERRORS: {errors}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
