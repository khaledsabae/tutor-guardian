#!/usr/bin/env python3
"""
infographic_prompts_lib — استخراج بلوكات البرومبت لكل درس من
scripts/infographic_prompts.md، وحساب الدروس الناقصة فيها إنفوجرافيك.

لا يتصل بـ NotebookLM — مجرد تحليل ملفات. يُستخدم من مولّد الإنفوجرافيك.
"""
import json
import sys
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


_BACKEND = str(Path(__file__).resolve().parents[1] / "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)
from app.core.taxonomy import age_equivalents  # noqa: E402

_REAL_LESSONS = {
    p.stem for p in
    (Path(__file__).resolve().parents[1] / "knowledge_base" / "curriculum"
     / "lessons").glob("*.json")
}


def _base_lang(code) -> str:
    """'ar_eg' → 'ar'. Entries declare locales; one language, several spellings."""
    return (code or "").strip().lower().replace("-", "_").split("_")[0] or "ar"


def missing_infographic_lessons(lang: str = "ar") -> list[dict]:
    """الدروس التي لا تملك أصل infographic **بهذه اللغة** بعد.

    🚨 كان يسأل «هل للدرس إنفوجراف؟» لا «هل له إنفوجراف إنجليزي؟» — فأي درس
    يملك النسخة العربية يُعدّ مكتملًا، ويرجّع تشغيلُ الإنجليزية **صفر هدف**
    وتخرج بنجاح. نفس عطب مُسنِد التخطّي الذي جعل تشغيلة صوت إنجليزية تفحص
    الملف العربي وتتخطّى كل الدروس ثم تخرج بـ0.
    """
    idx = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    want = _base_lang(lang)
    out = []
    # 🚨 45 index entries carry the OLD short id (`lesson_10-12_cyber_01`). They
    # are not dead: curriculum_loader resolves each to `lesson_<age>_<topic>_<n>`
    # and caches the assets under both. Reporting them as "no prompt" made the
    # backlog look 45 lessons larger than it is, and deleting them would have
    # broken 45 lessons in production. Resolve the id the same way the loader
    # does, so the count describes the curriculum rather than the index's shape.
    for l in idx["lessons"]:
        sid = l.get("lesson_id", "")
        age, topic = l.get("age_group"), l.get("topic_path")
        if age and topic and sid:
            order = sid.split("_")[-1]
            # `prenatal-1` and `0-3` are the same band — the index writes the
            # first, the curriculum files the second. Reuse the backend's
            # taxonomy rather than hard-coding the alias, so a future band split
            # cannot leave this resolver quietly behind.
            for band in age_equivalents(age):
                candidate = f"lesson_{band}_{topic}_{order}"
                if candidate in _REAL_LESSONS:
                    l = {**l, "lesson_id": candidate}
                    break
            else:
                l = {**l, "lesson_id": f"lesson_{age}_{topic}_{order}"}
        assets = l.get("assets", {}) or {}
        have = [e for e in (assets.get("infographics") or [])
                if _base_lang(e.get("language")) == want]
        if not have:
            out.append(
                {
                    "lesson_id": l["lesson_id"],
                    "age_group": l.get("age_group", ""),
                    "topic_path": l.get("topic_path", ""),
                    "title": l.get("title", l.get("title_ar", "")),
                }
            )
    return out


def buildable_targets(lang: str = "ar") -> tuple[list[dict], list[str]]:
    """(جاهز: دروس ناقصة بهذه اللغة ولها برومبت)، (بلا برومبت: lesson_ids)."""
    prompts = parse_prompt_blocks()
    missing = missing_infographic_lessons(lang)
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
