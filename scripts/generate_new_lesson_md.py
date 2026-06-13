#!/usr/bin/env python3
"""Generate NotebookLM markdown source files for the 25 newly-authored lessons
(ids ending in _bNN) so the existing podcast pipeline can upload them as
sources and generate audio. Matches the existing md format/location exactly.
"""
import json
import pathlib

BASE = pathlib.Path(__file__).resolve().parent.parent
LESSONS_DIR = BASE / "knowledge_base" / "curriculum" / "lessons"
PATHS_DIR = BASE / "knowledge_base" / "curriculum" / "paths"
NB_DIR = BASE / "knowledge_base" / "notebooklm"

# Cache path titles
_path_titles = {}
for pf in PATHS_DIR.glob("*.json"):
    d = json.loads(pf.read_text(encoding="utf-8"))
    _path_titles[d["id"]] = d.get("title", "")


def md_for(lesson: dict) -> str:
    age = lesson["age_group"]
    path_title = _path_titles.get(lesson.get("path_id"), "")
    objectives = "- فهم والتعامل مع %s\n" % lesson["title"]
    reflections = "\n".join("- %s" % r for r in lesson.get("reflection_prompts", []))
    return (
        "---\n"
        "# %s\n"
        "**الفئة العمرية:** %s\n"
        "**المسار:** %s\n"
        "**المدة المقدرة:** %s دقيقة\n"
        "---\n"
        "## الأهداف\n"
        "%s\n"
        "## المحتوى\n"
        "### %s\n\n"
        "%s\n\n\n"
        "## جرّب هذا\n"
        "- %s\n\n"
        "## للتأمل\n"
        "%s\n"
        "---\n"
        % (
            lesson["title"], age, path_title, lesson.get("estimated_minutes", 5),
            objectives, lesson["title"], lesson["summary"],
            lesson["try_this"], reflections,
        )
    )


def main():
    written = 0
    for lf in sorted(LESSONS_DIR.glob("*.json")):
        lesson = json.loads(lf.read_text(encoding="utf-8"))
        # Only the new hand-authored lessons (id like ..._bNN)
        lid = lesson["id"]
        if "_b" not in lid or not lid.rsplit("_", 1)[-1].startswith("b"):
            continue
        age_folder = NB_DIR / ("age_" + lesson["age_group"].replace("-", "_"))
        age_folder.mkdir(parents=True, exist_ok=True)
        (age_folder / f"{lid}.md").write_text(md_for(lesson), encoding="utf-8")
        written += 1
    print(f"Wrote {written} NotebookLM markdown sources under {NB_DIR}")


if __name__ == "__main__":
    main()
