"""No text the app serves tells a parent to hit a child.

Until 2026-10-04 served knowledge units said «يمكن ضرب الأطفال على ترك الصلاة
بعد سن العاشرة كآخر وسيلة تأديبية» and «الضرب للتأديب مسموح به» — retrieval hands
`text_simplified` to the assistant, so the model was being *grounded* in it.
Where the scholarly position is needed it is now described with its conditions
(light, harmless, last resort, never the face, never in anger; many discouraged
it), followed by the app's stance and alternatives — never as an instruction.

`text_original` (the raw source extraction, never served) is out of scope by
design; see ops/tools/content_surfaces.py.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

_MARKS = re.compile(r"[ً-ٰٟـ]")


def _norm(t: str) -> str:
    t = _MARKS.sub("", t)
    for a in "أإآٱ":
        t = t.replace(a, "ا")
    return t.replace("ى", "ي").replace("ة", "ه")


# Instructions or permissions to hit — the shapes that actually shipped.
ENDORSE = re.compile(
    r"يمكن\s+(?:لل\S+\s+)?ضرب|ويمكن\s+ضرب|ضرب\S*\s+بلطف|(?:ال)?ضرب\s+(?:ال)?خفيف\S*\s+(?:غير\s+المؤذي\s+)?(?:جائز|مسموح|مباح)"
    r"|(?:ال)?ضرب\s+لل?تاديب\s+(?:مسموح|جائز|مباح)|اضطررت\s+(?:الي|لل)ضرب|وضرب(?:هم|ه|ها)\s+عليها"
    r"|جعل\s+(?:ال)?تاديب\s+بالضرب|اليد\s+علي\s+الوجه\s+ممنوعه"
    r"|may (?:discipline|hit|strike|spank) (?:them|him|her) gently|(?:striking|hitting|spanking) for discipline is permitted"
    r"|if you must resort to it|non-severe striking permissible|disciplined for it at ten",
    re.I,
)


def _served_texts():
    units = ROOT / "knowledge_base" / "units"
    for f in sorted(units.glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        for k in ("title", "text_simplified"):
            if isinstance(d.get(k), str):
                yield f"{f.name}:{k}", d[k]
    for pattern in ("knowledge_base/curriculum/**/*.json", "docs/lesson_assets/flashcards/*.json",
                    "docs/lesson_assets/quizzes/*.json", "mobile/assets/data/stories*.json",
                    "mobile/assets/content/adhkar/*.json"):
        for f in sorted(ROOT.glob(pattern)):
            yield f.name, f.read_text(encoding="utf-8")
    for f in sorted(ROOT.glob("docs/lesson_assets/reports/*.md")):
        yield f.name, f.read_text(encoding="utf-8")


def test_no_served_text_endorses_hitting():
    hits = [(where, m.group(0)) for where, text in _served_texts()
            for m in [ENDORSE.search(_norm(text))] if m]
    assert not hits, f"{len(hits)} served texts endorse hitting: {hits[:5]}"


@pytest.mark.parametrize("game", sorted(p.name for p in (ROOT / "mobile/assets/content/games").glob("*.json")))
def test_no_game_rewards_hitting(game):
    """Games may offer hitting as a WRONG option; it must never be the right one."""
    data = json.loads((ROOT / "mobile/assets/content/games" / game).read_text(encoding="utf-8"))
    bad = []

    def walk(o):
        if isinstance(o, dict):
            for op in o.get("options", []) or []:
                if isinstance(op, dict) and op.get("is_correct") and re.search(r"ضرب|hit|spank|smack", op.get("text", ""), re.I):
                    bad.append(op.get("text"))
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(data)
    assert not bad, bad


def test_the_pattern_still_bites():
    # Regression fixtures — the exact sentences that shipped must be caught.
    for shipped in ("يمكن ضرب الأطفال على ترك الصلاة بعد سن العاشرة كآخر وسيلة تأديبية.",
                    "الضرب للتأديب مسموح به بشرط ألا يسبب أذى أو ضرراً.",
                    "تجنب الضرب الشديد، وإذا اضطررت للضرب فليكن خفيفاً وبعدد محدود",
                    "Parents may discipline them gently if they do not adhere to it by the age of ten."):
        assert ENDORSE.search(_norm(shipped)), shipped
    # …and the accurate description that replaced them must pass.
    for sound in ("وقد اشترط العلماء لأي ضرب أن يكون خفيفًا غير مؤذٍ، وآخرَ وسيلة، بعيدًا عن الوجه، "
                  "ولا يكون في حال غضب، وكرهه كثير منهم. و«المربّي» لا يوصي بالضرب أبدًا.",
                  "Scholars conditioned any striking on being light and harmless, a last resort."):
        assert not ENDORSE.search(_norm(sound)), sound
