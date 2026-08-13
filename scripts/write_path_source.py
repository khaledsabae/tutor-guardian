#!/usr/bin/env python3
"""Write the NotebookLM path source a path video is generated from.

Path videos (docs/path_videos/<path_id>_ar_eg.mp4) are NotebookLM video
overviews built from one markdown source per path — the path's own intro plus a
digest of its lessons. A path with no such source can never get a video, which
is why `path_2-3_aqeedah_first_name` had none while the other 39 paths did.

Format matches knowledge_base/notebooklm/path_sources/*.md exactly.

    python scripts/write_path_source.py path_2-3_aqeedah_first_name
"""
import argparse
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
PATHS_DIR = BASE / "knowledge_base" / "curriculum" / "paths"
LESSONS_DIR = BASE / "knowledge_base" / "curriculum" / "lessons"
OUT_DIR = BASE / "knowledge_base" / "notebooklm" / "path_sources"

FOOTER = "*منهج «المربّي» — إطار 7-7-7 النبوي. مصدر لإنتاج فيديو تعريفي للمسار.*"


def build(path_id):
    path = json.loads((PATHS_DIR / f"{path_id}.json").read_text(encoding="utf-8"))
    parts = [
        f"# {path['title']}",
        f"**الفئة العمرية:** {path['age_group']}",
        "",
        "## عن المسار",
        path.get("description", ""),
        "",
        "## دروس المسار",
        "",
    ]
    for n, lid in enumerate(path.get("lesson_ids") or [], 1):
        lesson = json.loads((LESSONS_DIR / f"{lid}.json").read_text(encoding="utf-8"))
        parts += [
            f"### {n}. {lesson['title']}",
            lesson.get("summary", ""),
            "",
            f"**طبّق هذا الأسبوع:** {lesson.get('try_this', '')}",
            "",
        ]
    parts += ["---", FOOTER, ""]
    return "\n".join(parts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path_id")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    out = OUT_DIR / f"{args.path_id}.md"
    if out.exists() and not args.force:
        print(f"{out.relative_to(BASE)} already exists — use --force to overwrite")
        return
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build(args.path_id), encoding="utf-8")
    print(f"wrote {out.relative_to(BASE)}")


if __name__ == "__main__":
    main()
