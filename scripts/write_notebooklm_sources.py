#!/usr/bin/env python3
"""Write the NotebookLM markdown source for lessons that have none.

The podcast pipeline is: curriculum lesson JSON → markdown source under
knowledge_base/notebooklm/age_<band>/ → uploaded as a NotebookLM source →
`notebooklm generate audio` → mp3 into docs/. A lesson with no markdown source
can never get an episode, which is why `path_2-3_aqeedah_first_name` has none.

Format matches the existing sources exactly (see
knowledge_base/notebooklm/age_2_3/lesson_2-3_islamic_first_words_01.md) — the
podcast voice follows the source layout, so a different shape means a different
sounding episode.

    python scripts/write_notebooklm_sources.py --dry-run
    python scripts/write_notebooklm_sources.py --only lesson_2-3_aqeedah_first_name_01
"""
import argparse
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
LESSONS_DIR = BASE / "knowledge_base" / "curriculum" / "lessons"
PATHS_DIR = BASE / "knowledge_base" / "curriculum" / "paths"
NB_DIR = BASE / "knowledge_base" / "notebooklm"

DOMAIN_AR = {
    "aqeedah": "العقيدة",
    "islamic_parenting": "التربية الإسلامية",
    "development": "تطور الطفل",
    "medical": "الصحة والنمو",
    "cyber": "الأمان الرقمي",
}

FOOTER = '*مصدر تربوي موجّه للوالدين — منهج «المربّي» (إطار 7-7-7 النبوي).*'


def path_titles():
    return {
        d["id"]: d.get("title", "")
        for d in (json.loads(f.read_text(encoding="utf-8"))
                  for f in PATHS_DIR.glob("*.json"))
    }


def markdown(lesson, path_title):
    reflections = "\n".join(f"- {r}" for r in lesson.get("reflection_prompts") or [])
    return (
        f"# {lesson['title']}\n"
        f"**الفئة العمرية:** {lesson['age_group']}\n"
        f"**المسار:** {path_title}\n"
        f"**المجال:** {DOMAIN_AR.get(lesson.get('domain'), lesson.get('domain', ''))}\n"
        f"**المدة المقدرة:** {lesson.get('estimated_minutes', 5)} دقيقة\n"
        "---\n\n"
        "## الفكرة الأساسية\n"
        f"{lesson.get('summary', '')}\n\n"
        "## التطبيق العملي (جرّب هذا الأسبوع)\n"
        f"{lesson.get('try_this', '')}\n\n\n"
        "## نقاط للتأمّل والنقاش\n"
        f"{reflections}\n\n"
        "---\n"
        f"{FOOTER}\n"
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--only", help="write this lesson id only")
    args = ap.parse_args()

    titles = path_titles()
    written = 0
    for f in sorted(LESSONS_DIR.glob("*.json")):
        lesson = json.loads(f.read_text(encoding="utf-8"))
        lid = lesson.get("id")
        if not lid or not lesson.get("is_published", True):
            continue
        if args.only and lid != args.only:
            continue
        band = "age_" + lesson["age_group"].replace("-", "_")
        out = NB_DIR / band / f"{lid}.md"
        if out.exists():
            continue
        print(f"+ {out.relative_to(BASE)}")
        if not args.dry_run:
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(markdown(lesson, titles.get(lesson.get("path_id"), "")),
                           encoding="utf-8")
        written += 1

    verb = "would write" if args.dry_run else "wrote"
    print(f"\n{verb} {written} source file(s)" if written
          else "\nevery published lesson already has a markdown source")


if __name__ == "__main__":
    main()
