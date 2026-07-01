#!/usr/bin/env python3
"""
infographic_prompts_lib — استخراج بلوكات البرومبت لكل درس من
scripts/infographic_prompts.md، وحساب الدروس الناقصة فيها إنفوجرافيك.

لا يتصل بـ NotebookLM — مجرد تحليل ملفات. يُستخدم من مولّد الإنفوجرافيك.
"""
import json
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
PROMPTS_MD = BASE_DIR / "scripts" / "infographic_prompts.md"
INDEX_PATH = BASE_DIR / "docs" / "lesson_index.json"

# كل بلوك يبدأ بـ:  #### N. `lesson_id`  وبعده **Title:** ... و**Sections:** ...
_BLOCK_RE = re.compile(
    r"^####\s+\d+\.\s+`(?P<lesson_id>[^`]+)`\s*\n(?P<body>.*?)(?=^####\s+\d+\.|\Z)",
    re.DOTALL | re.MULTILINE,
)
_TITLE_RE = re.compile(r"\*\*Title:\*\*\s*\"?(?P<title>[^\"\n]+)\"?")


def parse_prompt_blocks() -> dict[str, dict]:
    """ترجع {lesson_id: {"title": str, "description": str}} لكل بلوك في الـ md."""
    text = PROMPTS_MD.read_text(encoding="utf-8")
    blocks: dict[str, dict] = {}
    for m in _BLOCK_RE.finditer(text):
        lesson_id = m.group("lesson_id").strip()
        body = m.group("body").strip()
        tm = _TITLE_RE.search(body)
        title = tm.group("title").strip() if tm else ""
        # الوصف الكامل = العنوان + الأقسام كما هي (موجّه لتوليد إنفوجرافيك)
        description = body
        blocks[lesson_id] = {"title": title, "description": description}
    return blocks


def missing_infographic_lessons() -> list[dict]:
    """الدروس في الفهرس التي لا تملك أصل infographic بعد."""
    idx = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    out = []
    for l in idx["lessons"]:
        assets = l.get("assets", {}) or {}
        if not assets.get("infographics"):
            out.append(
                {
                    "lesson_id": l["lesson_id"],
                    "age_group": l.get("age_group", ""),
                    "topic_path": l.get("topic_path", ""),
                    "title": l.get("title", l.get("title_ar", "")),
                }
            )
    return out


def buildable_targets() -> tuple[list[dict], list[str]]:
    """(جاهز: دروس ناقصة ولها برومبت)، (بلا برومبت: lesson_ids)."""
    prompts = parse_prompt_blocks()
    missing = missing_infographic_lessons()
    ready, no_prompt = [], []
    for m in missing:
        p = prompts.get(m["lesson_id"])
        if p and p["description"]:
            ready.append({**m, **p})
        else:
            no_prompt.append(m["lesson_id"])
    return ready, no_prompt


if __name__ == "__main__":
    prompts = parse_prompt_blocks()
    missing = missing_infographic_lessons()
    ready, no_prompt = buildable_targets()
    print(f"prompt blocks parsed:   {len(prompts)}")
    print(f"missing infographics:   {len(missing)}")
    print(f"  buildable (has prompt): {len(ready)}")
    print(f"  no prompt:              {len(no_prompt)}")
    if no_prompt:
        print("  -> " + ", ".join(no_prompt[:10]) + (" ..." if len(no_prompt) > 10 else ""))
    if ready:
        s = ready[0]
        print("\n--- sample target ---")
        print("lesson_id:", s["lesson_id"])
        print("title:", s["title"])
        print("description (first 200):", s["description"][:200].replace("\n", " "))
