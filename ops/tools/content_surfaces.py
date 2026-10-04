#!/usr/bin/env python3
"""Every text the app ships to a parent or a child — as the scripture guards see it.

Why one enumerator
------------------
Until 2026-10-04 the Qur'an and hadith guards looked at exactly one file, the
notification pack, plus the English/Arabic attribution parity of KB units. A
lesson *summary* quoting «الراحمون يرحمهم الرحمن» — Abu Dawud and al-Tirmidhi,
not the Sahihayn — went out to every parent of a 7-9 year old with nothing
looking at it. Each guard used to carry its own idea of "where content lives";
a new surface then escaped all of them at once. This module is the one list,
and [main] prints it so a missing surface is visible.

Two kinds of thing come out:

* ``Text``  — a free string (a lesson summary, a story line, an ARB string, a
  push-notification literal…). The free-text scanner looks inside it for quoted
  scripture.
* ``Card``  — a structured citation: a dict carrying the text AND its own
  ``source`` (an adhkar item, a program evidence card). Checked whole, against
  its declared citation, never as free text.

What is deliberately NOT here — each with the reason:

* ``knowledge_base/units/*`` → ``text_original``: the raw extraction of a source
  book (often PDF mojibake). Never served — retrieval embeds and the assistant
  reads ``text_simplified`` only (backend/app/models/knowledge.py). Rewriting it
  would falsify the provenance record. ``title`` and ``text_simplified`` ARE here.
* ``knowledge_base/raw_sources``, ``*_backup*``, ``knowledge_base_markdown/``,
  ``docs/*_assets.md`` and ``docs/lesson_*_flashcards.json`` (pre-index drafts),
  ``reviews/``, ``plans/``: not shipped, or shipped but never served (not in
  ``docs/lesson_index.json``).
* Lesson ``.md`` twins: unserved mirrors of the ``.json`` (curriculum_loader
  reads ``*.json`` only).
"""
from __future__ import annotations

import ast
import csv
import io
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

ROOT = Path(__file__).resolve().parents[2]

_ARABIC = re.compile(r"[ء-ي]")
_CITE_HINT = re.compile(r"صحيح\s+(?:البخاري|مسلم)\s*[—\-–]\s*حديث")

# Keys that never carry prose (ids, enums, timestamps, file paths, review metadata).
_SKIP_KEYS = {
    "id", "path_id", "unit_id", "unit_ids", "lesson_id", "domain", "age_group", "time_of_day",
    "day_of_week", "version", "created_at", "updated_at", "approved_by", "language",
    "source_language", "translation", "file", "files", "image", "image_url", "audio", "icon",
    "color", "provenance", "tags", "labels", "keywords", "schema", "kind", "topic", "slug",
    "type", "category", "difficulty", "order", "estimated_minutes", "is_published",
    "needs_professional_followup", "source_file", "source_meta", "reference_type",
    "behavior_type", "intervention_type", "severity", "jurisdiction", "embedding",
}


@dataclass(frozen=True)
class Text:
    surface: str
    path: str
    where: str
    text: str


@dataclass(frozen=True)
class Card:
    surface: str
    path: str
    where: str
    text: str
    source: str
    provenance: dict | None


def _rel(p: Path) -> str:
    return str(p.relative_to(ROOT))


def _walk_json(obj, where: str = "") -> Iterator[tuple[str, object]]:
    if isinstance(obj, dict):
        yield where, obj
        for k, v in obj.items():
            if k in _SKIP_KEYS:
                continue
            yield from _walk_json(v, f"{where}.{k}" if where else k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            # an item with an id is located by it, so the Arabic and English
            # twins pair up even when one list is shorter (14 vs 19 stories)
            key = v.get("id") if isinstance(v, dict) and isinstance(v.get("id"), str) else i
            yield from _walk_json(v, f"{where}[{key}]")
    else:
        yield where, obj


def _card_of(d: dict) -> tuple[str, str] | None:
    """A dict that carries scripture together with its own citation."""
    src = d.get("source")
    if not isinstance(src, str):
        return None
    text = d.get("text_ar") if isinstance(d.get("text_ar"), str) else d.get("text")
    if not isinstance(text, str):
        return None
    kind = d.get("kind")
    if kind == "hadith" or (kind is None and _CITE_HINT.search(src)):
        return text, src
    return None   # a tip or a verse that names its source is a message, not a hadith card


def _json_items(surface: str, path: Path, fields: tuple[str, ...] | None = None):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    if fields is not None:  # explicit allow-list (KB units)
        for f in fields:
            v = data.get(f) if isinstance(data, dict) else None
            if isinstance(v, str) and v.strip():
                yield Text(surface, _rel(path), f, v)
        return
    handled: set[str] = set()   # dict paths whose text/source were emitted as one unit
    for where, node in _walk_json(data):
        if isinstance(node, dict):
            c = _card_of(node)
            if c:
                yield Card(surface, _rel(path), where, c[0], c[1], node.get("provenance"))
                handled.add(where)
            elif isinstance(node.get("text"), str) and isinstance(node.get("source"), str):
                # A tip and its attribution are one message — the app shows
                # `text\n— source` — so a citation in `source` covers a quote in `text`.
                yield Text(surface, _rel(path), where, f"{node['text']}\n— {node['source']}")
                handled.add(where)
        elif isinstance(node, str) and node.strip():
            parent = where.rsplit(".", 1)[0] if "." in where else ""
            if parent in handled and where.rsplit(".", 1)[-1] in ("text", "text_ar", "source"):
                continue  # already emitted with its sibling
            yield Text(surface, _rel(path), where, node)


def _csv_items(surface: str, path: Path):
    try:
        rows = list(csv.reader(io.StringIO(path.read_text(encoding="utf-8"))))
    except (OSError, csv.Error):
        return
    for r, row in enumerate(rows):
        for c, cell in enumerate(row):
            if cell.strip():
                yield Text(surface, _rel(path), f"r{r}c{c}", cell)


def _md_items(surface: str, path: Path):
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    # paragraph-wise: a quote rarely spans paragraphs, and a line locator is useful
    buf, start = [], 0
    for i, line in enumerate(lines + [""]):
        if line.strip():
            if not buf:
                start = i + 1
            buf.append(line)
        elif buf:
            yield Text(surface, _rel(path), f"L{start}", "\n".join(buf))
            buf = []


def _py_items(surface: str, path: Path):
    """Arabic string literals in Python source: push texts, prompts, quiz banks."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant):
                docstrings.add(id(body[0].value))
    for node in ast.walk(tree):
        if (isinstance(node, ast.Constant) and isinstance(node.value, str)
                and id(node) not in docstrings and len(_ARABIC.findall(node.value)) >= 6):
            yield Text(surface, _rel(path), f"L{node.lineno}", node.value)


_DART_STR = re.compile(r"'''(.*?)'''|\"\"\"(.*?)\"\"\"|'((?:[^'\\\n]|\\.)*)'|\"((?:[^\"\\\n]|\\.)*)\"", re.S)


def _dart_items(surface: str, path: Path):
    try:
        src = path.read_text(encoding="utf-8")
    except OSError:
        return
    code = "\n".join(re.sub(r"^\s*///?.*$", "", ln) for ln in src.splitlines())  # drop comment lines
    for m in _DART_STR.finditer(code):
        s = next(g for g in m.groups() if g is not None)
        if len(_ARABIC.findall(s)) >= 6:
            yield Text(surface, _rel(path), f"L{code.count(chr(10), 0, m.start()) + 1}", s)


def _arb_items(surface: str, path: Path):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    for k, v in data.items():
        if not k.startswith("@") and isinstance(v, str) and v.strip():
            yield Text(surface, _rel(path), k, v)


def _html_items(surface: str, path: Path):
    """The visible text of a page as one string: a citation sits in its own tag,
    away from the quote it belongs to (the landing page's «صحيح مسلم (2594)»)."""
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return
    raw = re.sub(r"<(script|style)\b.*?</\1>", " ", raw, flags=re.S | re.I)
    page = " ".join(" ".join(re.split(r"<[^>]+>", raw)).split())
    if len(_ARABIC.findall(page)) >= 6:
        yield Text(surface, _rel(path), "page", page)


def _served_lesson_assets() -> set[str]:
    try:
        idx = json.loads((ROOT / "docs/lesson_index.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    out = set()
    for lesson in idx.get("lessons", []):
        for entries in (lesson.get("assets") or {}).values():
            for e in entries or []:
                if isinstance(e, dict) and e.get("file"):
                    out.add(e["file"])
    return out


# (surface, glob, reader[, json field allow-list])
_SPECS = [
    ("lesson", "knowledge_base/curriculum/lessons/*.json", "json"),
    ("lesson.en", "knowledge_base/curriculum/i18n/en/lessons/*.json", "json"),
    ("daily_tip", "knowledge_base/curriculum/daily_tips/*.json", "json"),
    ("daily_tip.en", "knowledge_base/curriculum/i18n/en/daily_tips/*.json", "json"),
    ("path", "knowledge_base/curriculum/paths/*.json", "json"),
    ("path.en", "knowledge_base/curriculum/i18n/en/paths/*.json", "json"),
    ("mission", "knowledge_base/curriculum/missions/*.json", "json"),
    ("mission.en", "knowledge_base/curriculum/i18n/en/missions/*.json", "json"),
    ("agreement", "knowledge_base/curriculum/agreements/*.json", "json"),
    ("agreement.en", "knowledge_base/curriculum/i18n/en/agreements/*.json", "json"),
    ("license", "knowledge_base/curriculum/license/*.json", "json"),
    ("license.en", "knowledge_base/curriculum/i18n/en/license/*.json", "json"),
    ("program", "knowledge_base/curriculum/programs/*.json", "json"),
    ("program.en", "knowledge_base/curriculum/i18n/en/programs/*.json", "json"),
    ("adhkar", "mobile/assets/content/adhkar/*.json", "json"),
    ("game", "mobile/assets/content/games/*.json", "json"),
    ("journey", "mobile/assets/content/journey/*.json", "json"),
    ("story", "mobile/assets/data/stories*.json", "json"),
    ("story", "docs/stories*.json", "json"),
    ("offscreen", "mobile/assets/data/offscreen_activities*.json", "json"),
    ("arb", "mobile/lib/l10n/app_*.arb", "arb"),
    ("dart_literal", "mobile/lib/**/*.dart", "dart"),
    ("py_literal", "backend/app/**/*.py", "py"),
    ("py_literal", "ops/scripts/*.py", "py"),
    ("guardrail_policy", "backend/guardrails/*.yaml", "md"),
    ("frontend", "frontend/*.html", "html"),
    ("frontend", "frontend/*.js", "dart"),          # same literal syntax
    ("child_web", "backend/static/**/*.html", "html"),
]


def iter_items() -> Iterator[Text | Card]:
    for surface, pattern, reader in _SPECS:
        for p in sorted(ROOT.glob(pattern)):
            if "/l10n/app_localizations" in str(p):
                continue  # generated from the ARB files scanned above
            yield from {"json": _json_items, "arb": _arb_items, "dart": _dart_items,
                        "py": _py_items, "md": _md_items, "html": _html_items}[reader](surface, p)
    # KB units: served fields only (see module docstring)
    for p in sorted((ROOT / "knowledge_base/units").glob("*.json")):
        surface = "kb_unit.en" if p.name.endswith("__en.json") else "kb_unit"
        yield from _json_items(surface, p, fields=("title", "text_simplified"))
    # Lesson assets: only what docs/lesson_index.json serves
    served = _served_lesson_assets()
    for rel in sorted(served):
        p = ROOT / rel
        if not rel.startswith("docs/lesson_assets/") or not p.exists():
            continue
        kind = rel.split("/")[2]
        if p.suffix == ".json":
            yield from _json_items(f"asset.{kind}", p)
        elif p.suffix == ".csv":
            yield from _csv_items(f"asset.{kind}", p)
        elif p.suffix == ".md":
            yield from _md_items(f"asset.{kind}", p)


_EN_TWINS = [
    ("knowledge_base/curriculum/i18n/en/", "knowledge_base/curriculum/"),
    ("mobile/assets/data/stories_en.json", "mobile/assets/data/stories.json"),
    ("docs/stories.en.json", "docs/stories.json"),
    ("mobile/lib/l10n/app_en.arb", "mobile/lib/l10n/app_ar.arb"),
    ("mobile/assets/content/adhkar/family_adhkar.en.json", "mobile/assets/content/adhkar/family_adhkar.ar.json"),
]


def arabic_twin(path: str) -> str | None:
    """The Arabic source an English file was translated from, if there is one."""
    if path.endswith("__en.json"):
        return path[: -len("__en.json")] + ".json"
    for en, ar in _EN_TWINS:
        if path.startswith(en):
            return ar + path[len(en):] if en.endswith("/") else ar
    return None


def main() -> int:
    from collections import Counter
    texts, cards, files = Counter(), Counter(), {}
    for it in iter_items():
        (cards if isinstance(it, Card) else texts)[it.surface] += 1
        files.setdefault(it.surface, set()).add(it.path)
    print(f"{'surface':<20} {'files':>6} {'texts':>7} {'cards':>6}")
    for s in sorted(set(texts) | set(cards)):
        print(f"{s:<20} {len(files[s]):>6} {texts[s]:>7} {cards[s]:>6}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
