#!/usr/bin/env python3
"""The parenting-content pack, as the three notification-content guards see it.

The pack used to be a Dart `const` list, and each guard carried its own
`ParentingContent\\(…\\)` regex to get at it. On 2026-08-13 the content moved to
`mobile/assets/content/adhkar/family_adhkar.ar.json`
(`ops/tools/extract_app_content.py`, byte-for-byte proven). One loader now
reads it, so the three guards cannot drift apart on what an "item" is.

**Refuses to return nothing.** A loader that shrugged at a missing or empty
file would turn every guard downstream into a clean run over zero items — the
worst outcome available here, because the report would say ✅. Missing file,
wrong schema, empty list, missing field, duplicate id: [load_or_die] prints why
and exits 2, which the pre-commit hook reads as "the check itself is broken".
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import NamedTuple

ROOT = Path(__file__).resolve().parents[2]
PACK = ROOT / "mobile/assets/content/adhkar/family_adhkar.ar.json"
SCHEMA = "tg.parenting_content/1"
KINDS = {"verse", "hadith", "tip"}


class Item(NamedTuple):
    id: str
    kind: str
    text: str
    source: str
    topic: str
    # Structured, machine-derived citation: {'type':'quran','surah':14,'ayah':40}
    # or {'type':'hadith','book':'البخاري','number':5027}. None for tips.
    # The guards do not trust it — they re-parse `source` and check it agrees.
    provenance: dict | None


class PackError(Exception):
    pass


def load(path: Path = PACK) -> list[Item]:
    if not path.exists():
        raise PackError(f"الحزمة غير موجودة: {path}")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise PackError(f"الحزمة ليست JSON صالحًا: {e}") from e
    if raw.get("schema") != SCHEMA:
        raise PackError(f"schema غير متوقّع: {raw.get('schema')!r} (المنتظر {SCHEMA!r})")

    items: list[Item] = []
    for n, entry in enumerate(raw.get("items", [])):
        missing = [k for k in ("id", "kind", "text", "source", "topic") if not entry.get(k)]
        if missing:
            raise PackError(f"العنصر رقم {n} ينقصه: {', '.join(missing)}")
        if entry["kind"] not in KINDS:
            raise PackError(f"العنصر {entry['id']}: kind غير معروف {entry['kind']!r}")
        items.append(
            Item(
                id=entry["id"],
                kind=entry["kind"],
                text=entry["text"],
                source=entry["source"],
                topic=entry["topic"],
                provenance=entry.get("provenance"),
            )
        )

    if not items:
        raise PackError("الحزمة فارغة — لا عناصر تُفحص")
    ids = [i.id for i in items]
    if len(set(ids)) != len(ids):
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        raise PackError(f"معرّفات مكررة: {dupes[:5]}")
    return items


def load_or_die(path: Path = PACK) -> list[Item]:
    try:
        return load(path)
    except PackError as e:
        print(f"\n🔴  {e}")
        print("    الفحص لاغٍ — نتيجة نظيفة على حزمة لم تُقرأ كذبة.\n")
        sys.exit(2)
