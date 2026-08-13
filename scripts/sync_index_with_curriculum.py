#!/usr/bin/env python3
"""Add published curriculum lessons that docs/lesson_index.json does not know.

The index is what the API turns into lesson assets (curriculum_loader keys it by
both the short id and `lesson_{age}_{topic}_{order}`). A lesson added to
knowledge_base/curriculum/lessons/ after the last index build has no entry, so
`GET /api/program/lesson-assets/<id>` returns 404 and the app hides the whole
asset row — podcast, flashcards, quiz, infographic — not just the missing one.

That is how `path_2-3_aqeedah_first_name` (4 lessons) shipped silent: the path
was written after the 2026-06-09 index build and nothing cross-checked the two.

New entries carry empty asset lists. They exist so the endpoint answers 200 and
so a generated podcast/video has somewhere to be attached; they do not invent
assets. Run with --dry-run to see what would change.

    python scripts/sync_index_with_curriculum.py --dry-run
    python scripts/sync_index_with_curriculum.py
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
INDEX = BASE / "docs" / "lesson_index.json"
LESSONS_DIR = BASE / "knowledge_base" / "curriculum" / "lessons"

ASSET_KINDS = ("flashcards", "quizzes", "reports", "data_tables", "infographics",
               "podcasts", "videos")


def index_keys(entries):
    """Every id the API can resolve to an entry — short id and long id alike."""
    keys = set()
    for e in entries:
        short = e.get("lesson_id")
        age, topic = e.get("age_group"), e.get("topic_path")
        if short:
            keys.add(short)
            if age and topic:
                keys.add(f"lesson_{age}_{topic}_{short.split('_')[-1]}")
    return keys


def topic_path_for(lesson):
    """`path_2-3_aqeedah_first_name` → `aqeedah_first_name`.

    curriculum_loader rebuilds the long id as lesson_{age}_{topic}_{order}, so
    the topic must be the path id with its `path_{age}_` prefix removed for that
    id to match the lesson's own id.
    """
    path_id = lesson.get("path_id") or ""
    prefix = f"path_{lesson.get('age_group')}_"
    return path_id[len(prefix):] if path_id.startswith(prefix) else path_id


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    data = json.loads(INDEX.read_text(encoding="utf-8"))
    entries = data["lessons"]
    known = index_keys(entries)

    added = []
    for f in sorted(LESSONS_DIR.glob("*.json")):
        lesson = json.loads(f.read_text(encoding="utf-8"))
        lid = lesson.get("id")
        if not lid or not lesson.get("is_published", True) or lid in known:
            continue
        added.append({
            "lesson_id": lid,
            "age_group": lesson.get("age_group", ""),
            "topic_path": topic_path_for(lesson),
            "title_ar": lesson.get("title", ""),
            "assets": {kind: [] for kind in ASSET_KINDS},
        })

    for entry in added:
        print(f"+ {entry['lesson_id']}  ({entry['title_ar']})")
    if not added:
        print("index already covers every published lesson — refreshing counts")

    entries.extend(added)
    total = len(entries)
    by_age = {}
    for e in entries:
        by_age[e.get("age_group", "")] = by_age.get(e.get("age_group", ""), 0) + 1
    data["metadata"]["total_lessons"] = total
    data["metadata"]["lessons_by_age"] = dict(sorted(by_age.items()))
    data["metadata"]["coverage"] = {
        kind: f"{sum(1 for e in entries if (e.get('assets') or {}).get(kind))}/{total}"
        for kind in ASSET_KINDS
    }
    data["metadata"]["updated_at"] = datetime.now(timezone.utc).isoformat()

    if args.dry_run:
        print(f"\n(dry run) {len(added)} entries would be added — total {total}")
        return

    INDEX.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                     encoding="utf-8")
    print(f"\n{len(added)} entries added — {INDEX.relative_to(BASE)} now lists {total}")


if __name__ == "__main__":
    main()
