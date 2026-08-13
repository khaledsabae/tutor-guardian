#!/usr/bin/env python3
"""Move the app's hard-coded Arabic content out of Dart and into JSON assets.

Why this exists as a tool rather than a one-off edit
---------------------------------------------------
~3,000 Arabic strings live inside Dart `const` literals. Copying them out by
hand — or by a model — is exactly the kind of work that loses a character
nobody notices until it goes out as a daily notification. So the move is done
by a parser, and the parser is checked by running it backwards:

    extract   Dart literals  →  JSON
    verify    JSON  →  Dart literals  →  **byte-compare** with the Dart source

`verify` regenerates the exact source region the extractor consumed and asserts
it is byte-for-byte what was there. A pass means the JSON holds everything the
Dart held, down to the escaping. That is the evidence — and the precondition —
for deleting the Dart data.

After the Dart data is deleted the working tree no longer has anything to
compare against, so `verify` also accepts `--rev <git-rev>`: it reads the Dart
sources with `git show <rev>:<path>`. The proof stays re-runnable forever.

`b9c8608` is the last revision that still holds all six Dart data blocks:

    ops/tools/extract_app_content.py verify --rev b9c8608
    → 7/7 regions byte-identical — 200,962 bytes

Provenance (`family_adhkar`)
----------------------------
Verses and hadith carry structured provenance — numeric surah/ayah, book/number
— derived **mechanically** from the `source:` string using the very regexes the
pre-commit guards use (`check_quran_citations._CITATION` + `SURAHS`,
`check_hadith_citations._CITE`). Nothing here is typed by hand: a wrong ayah
number does not surface as a lint warning, it surfaces as scripture misquoted
in a notification. If a citation cannot be parsed, this tool stops and names it
rather than guessing.

Usage
    ops/tools/extract_app_content.py extract          # write the JSON assets
    ops/tools/extract_app_content.py verify           # round-trip vs worktree
    ops/tools/extract_app_content.py verify --rev X   # round-trip vs git rev

Exit: 0 ok · 1 mismatch/unparsed citation · 2 the tool itself is broken
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOLS = Path(__file__).resolve().parent


# ── the guards' own regexes, imported rather than copied ──────────────────────
# Single source of truth on purpose: if the citation format ever changes, the
# guard and the extractor must move together or provenance drifts from what is
# actually checked.
def _load_tool(name: str):
    spec = importlib.util.spec_from_file_location(name, TOOLS / f"{name}.py")
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise RuntimeError(f"cannot load {name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_quran = _load_tool("check_quran_citations")
_hadith = _load_tool("check_hadith_citations")

SURAHS = _quran.SURAHS
ALIAS = _quran.ALIAS
CITATION = _quran._CITATION
HADITH_CITE = _hadith._CITE
AR_DIGITS = _quran._AR_DIGITS


# ── sources ──────────────────────────────────────────────────────────────────
GAME_SOURCES = {
    "data_defender": "mobile/lib/features/games/data_defender/data_defender_game.dart",
    "tree_of_deeds": "mobile/lib/features/games/tree_of_deeds/tree_of_deeds_game.dart",
    "emotion_maze": "mobile/lib/features/games/emotion_maze/emotion_maze_game.dart",
    "healthy_hero": "mobile/lib/features/games/healthy_hero/healthy_hero_game.dart",
}
ADHKAR_SOURCE = "mobile/lib/features/adhkar/data/family_adhkar.dart"
JOURNEY_SOURCE = "mobile/lib/features/journey/data/journey_milestones.dart"

ASSETS = ROOT / "mobile/assets/content"
GAME_ASSET = "games/{game}.ar.json"
ADHKAR_ASSET = "adhkar/family_adhkar.ar.json"
JOURNEY_ASSET = "journey/milestones.ar.json"

OPTION_KEYS = ("a", "b", "c", "d")


class ExtractError(Exception):
    """A shape this tool refuses to guess about."""


# ── Dart string literals ─────────────────────────────────────────────────────
_ESCAPES = {"\\": "\\", "'": "'", "n": "\n", "t": "\t", "$": "$", '"': '"'}


def dart_unescape(raw: str) -> str:
    out, i = [], 0
    while i < len(raw):
        c = raw[i]
        if c != "\\":
            out.append(c)
            i += 1
            continue
        if i + 1 >= len(raw):
            raise ExtractError(f"trailing backslash in literal: {raw!r}")
        nxt = raw[i + 1]
        if nxt not in _ESCAPES:
            raise ExtractError(f"unsupported escape \\{nxt} in literal: {raw!r}")
        out.append(_ESCAPES[nxt])
        i += 2
    return "".join(out)


def dart_escape(value: str) -> str:
    """Inverse of [dart_unescape] for the escapes this content actually uses.

    `$` is escaped because Dart would otherwise read it as interpolation. No
    content string contains one today; the assertion in `_check_roundtrip`
    keeps it that way rather than trusting the comment.
    """
    return (
        value.replace("\\", "\\\\")
        .replace("'", "\\'")
        .replace("$", "\\$")
        .replace("\n", "\\n")
        .replace("\t", "\\t")
    )


_LITERAL = r"((?:[^'\\\n]|\\.)*)"


def _field(indent: str, name: str) -> re.Pattern[str]:
    return re.compile(f"{indent}{name}: '{_LITERAL}',\n")


# ── a strict sequential scanner ──────────────────────────────────────────────
class Scanner:
    """Consumes a source region left to right. Anything unexpected is an error.

    A tolerant parser is the failure mode here: it would silently skip an item
    whose shape it did not recognise, and the count would still look plausible.
    """

    def __init__(self, text: str, where: str):
        self.text, self.pos, self.where = text, 0, where

    def eat(self, literal: str) -> None:
        if not self.text.startswith(literal, self.pos):
            got = self.text[self.pos : self.pos + 90]
            raise ExtractError(f"{self.where}: expected {literal!r} but found {got!r}")
        self.pos += len(literal)

    def at(self, literal: str) -> bool:
        return self.text.startswith(literal, self.pos)

    def match(self, pattern: re.Pattern[str]) -> re.Match[str]:
        m = pattern.match(self.text, self.pos)
        if m is None:
            got = self.text[self.pos : self.pos + 90]
            raise ExtractError(f"{self.where}: expected {pattern.pattern!r}, found {got!r}")
        self.pos = m.end()
        return m

    def field(self, indent: str, name: str) -> str:
        return dart_unescape(self.match(_field(indent, name)).group(1))

    def done_soft(self) -> bool:
        return self.pos >= len(self.text)

    def done(self) -> None:
        if self.pos != len(self.text):
            rest = self.text[self.pos : self.pos + 120]
            raise ExtractError(f"{self.where}: {len(self.text) - self.pos} bytes unconsumed: {rest!r}")


# ── region extraction ────────────────────────────────────────────────────────
def region(src: str, start_marker: str, end_marker: str, where: str) -> str:
    i = src.find(start_marker)
    if i < 0:
        raise ExtractError(
            f"{where}: start marker not found: {start_marker!r}\n"
            "  The Dart data is gone from this revision — that is the point of "
            "the move.\n  Re-run the proof against the commit before it:\n"
            "      ops/tools/extract_app_content.py verify --rev <commit>"
        )
    i += len(start_marker)
    j = src.find(end_marker, i)
    if j < 0:
        raise ExtractError(f"{where}: end marker not found: {end_marker!r}")
    return src[i:j]


GAME_REGION = ("    switch (level) {\n", "      default:\n")
ADHKAR_REGION = ("const List<ParentingContent> familyAdhkar = [\n", "];\n")
SPIRITUAL_REGION = ("const List<JourneyMilestone> spiritualMilestones = [\n", "];\n")
DEVELOPMENTAL_REGION = (
    "const Map<String, List<JourneyMilestone>> _developmentalByAge = {\n",
    "};\n",
)


# ── games ────────────────────────────────────────────────────────────────────
_CASE = re.compile(r"      case (\d+):\n        return const \[\n")
_OPTION = re.compile(
    f"        EduOption\\(text: '{_LITERAL}', isCorrect: (true|false), "
    f"rationale: '{_LITERAL}'\\),\n"
)


def parse_game(src: str, game: str) -> dict:
    body = region(src, *GAME_REGION, where=game)
    sc = Scanner(body, game)
    levels = []
    while not sc.done_soft():
        m = sc.match(_CASE)
        level = int(m.group(1))
        questions = []
        while sc.at("    EduQuestion(\n"):
            sc.eat("    EduQuestion(\n")
            qid = sc.field("      ", "id")
            question = sc.field("      ", "question")
            emoji = sc.field("      ", "emoji")
            category = sc.field("      ", "category")
            context = sc.field("      ", "context")
            sc.eat("      options: [\n")
            options = []
            while sc.at("        EduOption("):
                om = sc.match(_OPTION)
                options.append(
                    {
                        "key": None,  # assigned below, positional-once
                        "text": dart_unescape(om.group(1)),
                        "is_correct": om.group(2) == "true",
                        "rationale": dart_unescape(om.group(3)),
                    }
                )
            sc.eat("      ],\n")
            sc.eat("    ),\n")
            if len(options) > len(OPTION_KEYS):
                raise ExtractError(f"{game}/{qid}: {len(options)} options, only {len(OPTION_KEYS)} keys")
            for k, opt in zip(OPTION_KEYS, options):
                opt["key"] = k
            questions.append(
                {
                    "id": f"{game}.{qid}",
                    "question": question,
                    "emoji": emoji,
                    "category": category,
                    "context": context,
                    "options": options,
                }
            )
        sc.eat("        ];\n")
        levels.append({"level": level, "questions": questions})
    sc.done()

    seen: set[str] = set()
    for lv in levels:
        for q in lv["questions"]:
            if q["id"] in seen:
                raise ExtractError(f"{game}: duplicate question id {q['id']}")
            seen.add(q["id"])
            if sum(1 for o in q["options"] if o["is_correct"]) != 1:
                raise ExtractError(f"{game}: {q['id']} does not have exactly one correct option")

    return {
        "schema": "tg.game_pack/1",
        "game": game,
        "locale": "ar",
        "levels": levels,
    }


def render_game(pack: dict) -> str:
    game = pack["game"]
    out = []
    for lv in pack["levels"]:
        out.append(f"      case {lv['level']}:\n        return const [\n")
        for q in lv["questions"]:
            qid = q["id"]
            prefix = f"{game}."
            if not qid.startswith(prefix):
                raise ExtractError(f"{game}: id {qid!r} is not namespaced to the pack")
            out.append("    EduQuestion(\n")
            out.append(f"      id: '{dart_escape(qid[len(prefix):])}',\n")
            out.append(f"      question: '{dart_escape(q['question'])}',\n")
            out.append(f"      emoji: '{dart_escape(q['emoji'])}',\n")
            out.append(f"      category: '{dart_escape(q['category'])}',\n")
            out.append(f"      context: '{dart_escape(q['context'])}',\n")
            out.append("      options: [\n")
            for o in q["options"]:
                out.append(
                    f"        EduOption(text: '{dart_escape(o['text'])}', "
                    f"isCorrect: {'true' if o['is_correct'] else 'false'}, "
                    f"rationale: '{dart_escape(o['rationale'])}'),\n"
                )
            out.append("      ],\n    ),\n")
        out.append("        ];\n")
    return "".join(out)


# ── family adhkar ────────────────────────────────────────────────────────────
def _quran_provenance(source: str, text: str) -> dict:
    m = CITATION.search(source)
    if not m:
        raise ExtractError(f"verse citation not parseable: {source!r}  ←  {text[:40]}")
    name = ALIAS.get(m.group(1).strip(), m.group(1).strip())
    if name not in SURAHS:
        raise ExtractError(f"unknown surah {name!r} in citation {source!r}")
    return {
        "type": "quran",
        "surah": SURAHS.index(name) + 1,
        "ayah": int(m.group(2).translate(AR_DIGITS)),
    }


def _hadith_provenance(source: str, text: str) -> dict:
    m = HADITH_CITE.search(source)
    if not m:
        raise ExtractError(f"hadith citation not parseable: {source!r}  ←  {text[:40]}")
    return {
        "type": "hadith",
        "book": m.group(1),
        "number": int(m.group(2).translate(AR_DIGITS)),
    }


def parse_adhkar(src: str) -> dict:
    body = region(src, *ADHKAR_REGION, where="family_adhkar")
    sc = Scanner(body, "family_adhkar")
    raw = []
    while sc.at("  ParentingContent(\n"):
        sc.eat("  ParentingContent(\n")
        text = sc.field("    ", "text")
        source = sc.field("    ", "source")
        topic = sc.field("    ", "topic")
        kind = sc.field("    ", "kind")
        sc.eat("  ),\n")
        raw.append({"kind": kind, "text": text, "source": source, "topic": topic})
    sc.done()

    seq = {"tip": 0, "hadith": 0}
    unparsed: list[str] = []
    items = []
    for it in raw:
        kind = it["kind"]
        prov = None
        if kind == "verse":
            try:
                prov = _quran_provenance(it["source"], it["text"])
            except ExtractError as e:
                unparsed.append(str(e))
                item_id = None
            else:
                item_id = f"v_{prov['surah']:03d}_{prov['ayah']:03d}"
        elif kind == "hadith":
            try:
                prov = _hadith_provenance(it["source"], it["text"])
            except ExtractError as e:
                unparsed.append(str(e))
                item_id = None
            else:
                seq["hadith"] += 1
                item_id = f"h_{seq['hadith']:03d}"
        elif kind == "tip":
            seq["tip"] += 1
            item_id = f"t_{seq['tip']:03d}"
        else:
            raise ExtractError(f"unknown kind {kind!r}")
        entry = {"id": item_id, "kind": kind, "text": it["text"],
                 "source": it["source"], "topic": it["topic"]}
        if prov is not None:
            entry["provenance"] = prov
        items.append(entry)

    if unparsed:
        raise ExtractError(
            "citations that could not be parsed mechanically — refusing to guess:\n  "
            + "\n  ".join(unparsed)
        )

    # A verse id is surah+ayah, so two entries quoting the same ayah collide.
    # Disambiguate by 1-based occurrence, never by list position: inserting an
    # item above must not renumber the ones below it.
    counts: dict[str, int] = {}
    for it in items:
        counts[it["id"]] = counts.get(it["id"], 0) + 1
    running: dict[str, int] = {}
    for it in items:
        if counts[it["id"]] > 1:
            running[it["id"]] = running.get(it["id"], 0) + 1
            it["id"] = f"{it['id']}_{running[it['id']]}"

    ids = [it["id"] for it in items]
    if len(set(ids)) != len(ids):
        raise ExtractError("duplicate ids after disambiguation")

    return {"schema": "tg.parenting_content/1", "locale": "ar", "items": items}


def render_adhkar(pack: dict) -> str:
    out = []
    for it in pack["items"]:
        out.append("  ParentingContent(\n")
        out.append(f"    text: '{dart_escape(it['text'])}',\n")
        out.append(f"    source: '{dart_escape(it['source'])}',\n")
        out.append(f"    topic: '{dart_escape(it['topic'])}',\n")
        out.append(f"    kind: '{dart_escape(it['kind'])}',\n")
        out.append("  ),\n")
    return "".join(out)


# ── journey milestones ───────────────────────────────────────────────────────
def _parse_milestones(sc: Scanner, indent: str) -> list[dict]:
    field_indent = indent + "  "
    items = []
    while sc.at(f"{indent}JourneyMilestone(\n"):
        sc.eat(f"{indent}JourneyMilestone(\n")
        key = sc.field(field_indent, "key")
        title = sc.field(field_indent, "title")
        description = sc.field(field_indent, "description")
        emoji = sc.field(field_indent, "emoji")
        concern = None
        if sc.at(f"{field_indent}concernNote:"):
            concern = sc.field(field_indent, "concernNote")
        sc.eat(f"{indent}),\n")
        items.append(
            {
                "key": key,
                "title": title,
                "description": description,
                "emoji": emoji,
                "concern_note": concern,
            }
        )
    return items


_BAND = re.compile(f"  '{_LITERAL}': \\[\n")


def parse_journey(src: str) -> dict:
    spiritual_body = region(src, *SPIRITUAL_REGION, where="spiritualMilestones")
    sc = Scanner(spiritual_body, "spiritualMilestones")
    spiritual = _parse_milestones(sc, "  ")
    sc.done()

    dev_body = region(src, *DEVELOPMENTAL_REGION, where="_developmentalByAge")
    sc = Scanner(dev_body, "_developmentalByAge")
    developmental: dict[str, list[dict]] = {}
    while not sc.done_soft():
        band = dart_unescape(sc.match(_BAND).group(1))
        developmental[band] = _parse_milestones(sc, "    ")
        sc.eat("  ],\n")
    sc.done()

    keys = [m["key"] for m in spiritual] + [
        m["key"] for band in developmental.values() for m in band
    ]
    if len(set(keys)) != len(keys):
        raise ExtractError("journey: duplicate milestone key")

    return {
        "schema": "tg.journey_milestones/1",
        "locale": "ar",
        "spiritual": spiritual,
        "developmental": developmental,
    }


def _render_milestones(items: list[dict], indent: str) -> str:
    field_indent = indent + "  "
    out = []
    for m in items:
        out.append(f"{indent}JourneyMilestone(\n")
        out.append(f"{field_indent}key: '{dart_escape(m['key'])}',\n")
        out.append(f"{field_indent}title: '{dart_escape(m['title'])}',\n")
        out.append(f"{field_indent}description: '{dart_escape(m['description'])}',\n")
        out.append(f"{field_indent}emoji: '{dart_escape(m['emoji'])}',\n")
        if m.get("concern_note") is not None:
            out.append(f"{field_indent}concernNote: '{dart_escape(m['concern_note'])}',\n")
        out.append(f"{indent}),\n")
    return "".join(out)


def render_journey_spiritual(pack: dict) -> str:
    return _render_milestones(pack["spiritual"], "  ")


def render_journey_developmental(pack: dict) -> str:
    out = []
    for band, items in pack["developmental"].items():
        out.append(f"  '{dart_escape(band)}': [\n")
        out.append(_render_milestones(items, "    "))
        out.append("  ],\n")
    return "".join(out)


# ── sources: worktree or a git rev ───────────────────────────────────────────
def read_source(rel: str, rev: str | None) -> str:
    if rev is None:
        return (ROOT / rel).read_text(encoding="utf-8")
    out = subprocess.run(
        ["git", "-C", str(ROOT), "show", f"{rev}:{rel}"],
        capture_output=True, check=True,
    )
    return out.stdout.decode("utf-8")


# ── the units of work ────────────────────────────────────────────────────────
def build_all(rev: str | None) -> dict[str, dict]:
    packs: dict[str, dict] = {}
    for game, rel in GAME_SOURCES.items():
        packs[GAME_ASSET.format(game=game)] = parse_game(read_source(rel, rev), game)
    packs[ADHKAR_ASSET] = parse_adhkar(read_source(ADHKAR_SOURCE, rev))
    packs[JOURNEY_ASSET] = parse_journey(read_source(JOURNEY_SOURCE, rev))
    return packs


def dumps(pack: dict) -> str:
    return json.dumps(pack, ensure_ascii=False, indent=2) + "\n"


def cmd_extract(rev: str | None) -> int:
    packs = build_all(rev)
    for rel, pack in packs.items():
        path = ASSETS / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(dumps(pack), encoding="utf-8")
        print(f"  wrote  mobile/assets/content/{rel}  ({_describe(pack)})")
    return 0


def _describe(pack: dict) -> str:
    schema = pack["schema"]
    if schema == "tg.game_pack/1":
        n = sum(len(lv["questions"]) for lv in pack["levels"])
        opts = sum(len(q["options"]) for lv in pack["levels"] for q in lv["questions"])
        return f"{len(pack['levels'])} levels · {n} questions · {opts} options"
    if schema == "tg.parenting_content/1":
        kinds: dict[str, int] = {}
        for it in pack["items"]:
            kinds[it["kind"]] = kinds.get(it["kind"], 0) + 1
        return f"{len(pack['items'])} items · " + " · ".join(
            f"{k}={v}" for k, v in sorted(kinds.items())
        )
    if schema == "tg.journey_milestones/1":
        dev = sum(len(v) for v in pack["developmental"].values())
        return f"{len(pack['spiritual'])} spiritual · {dev} developmental"
    return schema


def _load_asset(rel: str) -> dict:
    return json.loads((ASSETS / rel).read_text(encoding="utf-8"))


def _diff(where: str, expected: str, actual: str) -> None:
    print(f"\n🔴  ROUND-TRIP MISMATCH — {where}")
    print(f"    original {len(expected)} bytes · regenerated {len(actual)} bytes")
    for i, (a, b) in enumerate(zip(expected, actual)):
        if a != b:
            lo = max(0, i - 70)
            print(f"    first difference at byte {i}:")
            print(f"      original    …{expected[lo:i + 70]!r}")
            print(f"      regenerated …{actual[lo:i + 70]!r}")
            return
    print("    one is a prefix of the other; tail of the longer:")
    longer = expected if len(expected) > len(actual) else actual
    print(f"      {longer[min(len(expected), len(actual)):][:200]!r}")


def cmd_verify(rev: str | None) -> int:
    print("\n" + "=" * 67)
    print("  APP CONTENT ROUND-TRIP — JSON → Dart literals → byte-compare")
    print("=" * 67)
    where = f"git rev {rev}" if rev else "working tree"
    print(f"  Dart sources: {where}")

    failures = 0
    checks: list[tuple[str, str, str]] = []  # (label, original region, regenerated)

    for game, rel in GAME_SOURCES.items():
        src = read_source(rel, rev)
        original = region(src, *GAME_REGION, where=game)
        checks.append((rel, original, render_game(_load_asset(GAME_ASSET.format(game=game)))))

    src = read_source(ADHKAR_SOURCE, rev)
    checks.append((ADHKAR_SOURCE, region(src, *ADHKAR_REGION, where="family_adhkar"),
                   render_adhkar(_load_asset(ADHKAR_ASSET))))

    src = read_source(JOURNEY_SOURCE, rev)
    journey = _load_asset(JOURNEY_ASSET)
    checks.append((JOURNEY_SOURCE + " :: spiritualMilestones",
                   region(src, *SPIRITUAL_REGION, where="spiritualMilestones"),
                   render_journey_spiritual(journey)))
    checks.append((JOURNEY_SOURCE + " :: _developmentalByAge",
                   region(src, *DEVELOPMENTAL_REGION, where="_developmentalByAge"),
                   render_journey_developmental(journey)))

    for label, original, regenerated in checks:
        ok = original == regenerated
        mark = "✅" if ok else "❌"
        print(f"  {mark}  {len(original):>7,} bytes  {label}")
        if not ok:
            failures += 1
            _diff(label, original, regenerated)

    # No content string may contain `$`: Dart would read it as interpolation,
    # and the round-trip above cannot catch what was never in the source.
    for rel, pack in ((k, _load_asset(k)) for k in
                      [GAME_ASSET.format(game=g) for g in GAME_SOURCES]
                      + [ADHKAR_ASSET, JOURNEY_ASSET]):
        for s in _all_strings(pack):
            if "$" in s or "\\" in s:
                print(f"\n🔴  {rel}: literal needs escaping review: {s[:60]!r}")
                failures += 1

    print("\n" + "=" * 67)
    if failures:
        print(f"  ❌  {failures} region(s) did not round-trip — do NOT delete the Dart data.")
        print("=" * 67 + "\n")
        return 1
    total = sum(len(o) for _, o, _ in checks)
    print(f"  ✅  {len(checks)}/{len(checks)} regions byte-identical — {total:,} bytes")
    print("=" * 67 + "\n")
    return 0


def _all_strings(node) -> list[str]:
    if isinstance(node, str):
        return [node]
    if isinstance(node, dict):
        return [s for v in node.values() for s in _all_strings(v)]
    if isinstance(node, list):
        return [s for v in node for s in _all_strings(v)]
    return []


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("mode", choices=["extract", "verify"])
    ap.add_argument("--rev", default=None,
                    help="read the Dart sources from this git rev instead of the worktree")
    args = ap.parse_args()
    try:
        if args.mode == "extract":
            return cmd_extract(args.rev)
        return cmd_verify(args.rev)
    except ExtractError as e:
        print(f"\n🔴  {e}\n", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
