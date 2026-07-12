#!/usr/bin/env python3
"""
Generate missing report assets for lessons using NotebookLM ask.

Reads scripts/missing_reports_full.json (output with source_id, lesson_id, age_group, topic_path)
and generates a structured markdown report per source using NotebookLM ask.

Outputs:
- docs/lesson_assets/reports/<artifact_id>_<title>.md
- Updated docs/lesson_index.json
- Git commit + push
"""

import os
import json
import re
import subprocess
import asyncio
import argparse
from pathlib import Path
from datetime import datetime
import uuid

BASE_DIR = Path("/home/khalednew/projects/tutor-guardian")
REPORTS_DIR = BASE_DIR / "docs/lesson_assets/reports"
INDEX_PATH = BASE_DIR / "docs/lesson_index.json"
MISSING_PATH = BASE_DIR / "scripts/missing_reports_full.json"
NOTEBOOK_ID = "94f191e6-cfbc-4655-a0d7-c8f7ad0f2287"
NOTEBOOKLM_BIN = BASE_DIR / "notebooklm_env/bin/notebooklm"

TITLE_MAP = {
    "cyber_digital_citizenship": "المواطنة الرقمية",
    "cyber_digital_maturity": "النضج الرقمي",
    "cyber_digital_professional": "المهنية الرقمية",
    "cyber_routine": "الروتين الرقمي",
    "cyber_screen_foundations": "أساسيات الشاشات",
    "development_brain_identity": "الدماغ والهوية",
    "development_positive_parenting": "التربية الإيجابية",
    "development_digital_wellbeing": "الرفاه الرقمي",
    "development_growth": "النمو",
    "development_early_moments": "اللحظات الأولى",
    "development_independence": "الاستقلالية",
    "development_language": "تطور اللغة",
    "islamic_parenting_identity": "الهوية الإسلامية",
    "islamic_parenting_teen_identity": "هوية المراهق الإسلامية",
    "islamic_parenting_worship": "التربية على العبادة",
    "islamic_parenting_bond": "العلاقة مع الطفل",
    "islamic_parenting_adab": "الأدب والأخلاق",
    "islamic_attachment": "الارتباط الإسلامي",
    "islamic_tantrums": "التعامل مع النوبات",
    "medical_puberty_wellbeing": "البلوغ والرفاه",
    "medical_mental_health": "الصحة النفسية",
    "medical_emotional_health": "الصحة العاطفية",
    "medical_adult_transition": "الانتقال للرشد",
    "medical_early_milestones": "المراحل الأولى",
    "aqeedah_growth": "نمو العقيدة",
    "aqeedah_conviction": "قناعة العقيدة",
    "aqeedah_seeds": "بذور العقيدة",
    "aqeedah_fundamentals": "أسس العقيدة",
    "aqeedah_certainty": "يقين العقيدة",
    "islamic_parenting_worship_love": "التربية على حب العبادة",
    "islamic_parenting_fitrah": "غرس الفطرة الإسلامية",
    "development_pre_teen": "مرحلة ما قبل المراهقة",
    "islamic_parenting_steadfast": "التربية على الثبات",
    "islamic_parenting_attachment": "الارتباط التربوي الإسلامي",
    "cyber_digital_basics": "أساسيات العالم الرقمي",
    "islamic_parenting_adult_faith": "تربية الرشد والإيمان",
    "medical_healthy_growth": "النمو الصحي الطبي",
    "medical_early_wellbeing": "الرفاهية الطبية المبكرة",
    "development_adult_readiness": "الاستعداد للرشد",
    "cyber_early_screens": "الشاشات المبكرة",
    "islamic_first_words": "الكلمات الأولى الإسلامية",
    "islamic_parenting_akhlaq": "التربية على الأخلاق الإسلامية",
}

# Shared prompts
REPORT_PROMPT = '''قم بإعداد "تقرير تربوي عملي" للأهل بالاعتماد الكامل على الدرس/المصدر المحدد فقط.

اكتب التقرير باللغة العربية الفصحى المبسطة، بالهيكل التالي بدقة:

### 1. لمحة الدرس (Lesson Overview)
- الفكرة المركزية للدرس في جملة واحدة.
- الفئة العمرية المستهدفة.
- الهدف التربوي الأساسي.

### 2. ما يجب أن يلاحظه الأهل (Parental Cues)
- 3-5 علامات أو سلوكيات يجب أن ينتبه لها الأب/الأم في الطفل.

### 3. خطة العمل العملية (Action Plan)
- 5 خطوات عملية يمكن تطبيقها هذا الأسبوع.
- كل خطوة في سطر واحد واضح.

### 4. الأنشطة المقترحة (Suggested Activities)
- نشاط واحد للحوار العائلي (مدته 10-15 دقيقة).
- نشاط واحد عملي/حركي (مدته 5-10 دقائق).

### 5. مقتطفات وشواهد (Key Takeaways)
- 3-4 نقاط أو اقتباسات جوهرية من الدرس تؤكد الرسالة.

### 6. نصيحة ختامية (Closing Tip)
- نصيحة واحدة قصيرة ومركزة للأهل.

شروط صارمة:
- لا تضف أي معلومة خارجية أو نصيحة عامة غير موجودة في المصدر.
- لا تذكر أنك "نموذج لغوي" أو "AI".
- اكتب بأسلوب دافئ ومهني موجه للأب والأم.
'''


def slugify_arabic(text: str) -> str:
    """Convert any title into a safe filename component."""
    text = re.sub(r"[^\w\s\-]", "", text, flags=re.UNICODE)
    text = re.sub(r"\s+", "_", text.strip())
    return text[:60]


async def run_notebooklm_ask(source_id: str) -> str:
    """Run a single NotebookLM ask query for a source."""
    cmd = [
        str(NOTEBOOKLM_BIN), "ask",
        "-n", NOTEBOOK_ID,
        "-s", source_id,
        "--new", "-y",
        REPORT_PROMPT,
    ]

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    stdout, stderr = await proc.communicate()

    if proc.returncode != 0:
        err = stderr.decode(errors="replace").strip()
        print(f"    ❌ Error: {err[:200]}")
        return f"### Error generating report\n{err}"

    text = stdout.decode(errors="replace").strip()
    # Strip notebooklm CLI trailing metadata lines
    lines = text.splitlines()
    cleaned = []
    for line in lines:
        if line.startswith("New conversation:"):
            break
        cleaned.append(line)
    return "\n".join(cleaned).strip()


def build_report_markdown(lesson_id: str, age_group: str, topic_path: str, content: str) -> str:
    """Wrap raw NotebookLM response into a consistent report markdown."""
    topic_ar = TITLE_MAP.get(topic_path, topic_path.replace("_", " ").title())

    header_lines = [
        f"# تقرير تربوي عملي: {topic_ar} ({age_group})",
        "",
        f"**الدرس:** `{lesson_id}`  ",
        f"**المجال:** {topic_ar}  ",
        f"**الفئة العمرية:** {age_group}  ",
        "",
        "تم إعداد هذا التقرير بالاعتماد الصارم على مصدر الدرس.",
        "",
        "---",
        "",
    ]
    return "\n".join(header_lines) + content


async def generate_report_for_lesson(lesson: dict) -> dict | None:
    """Generate a report for one lesson and return asset entry."""
    lesson_id = lesson["lesson_id"]
    source_id = lesson["source_id"]
    age_group = lesson["age_group"]
    topic_path = lesson["topic_path"]

    print(f"\n[{lesson_id}] asking NotebookLM source {source_id}...")

    content = await run_notebooklm_ask(source_id)
    if content.startswith("### Error"):
        return None

    # Strip LLM Answer prefix and preamble
    lines = content.splitlines()
    cleaned_lines = []
    skip_intro = False
    for line in lines:
        if line.strip().lower() == "answer:":
            skip_intro = True
            continue
        if skip_intro:
            if line.strip().startswith("### 1"):
                skip_intro = False
            else:
                continue
        cleaned_lines.append(line)
    content = "\n".join(cleaned_lines).strip()

    artifact_id = str(uuid.uuid4())
    filename = f"{artifact_id}_report_{lesson_id}.md"
    filepath = REPORTS_DIR / filename

    markdown = build_report_markdown(lesson_id, age_group, topic_path, content)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(markdown)

    print(f"    ✅ Saved: {filepath}")

    topic_ar = TITLE_MAP.get(topic_path, topic_path.replace("_", " ").title())
    return {
        "id": artifact_id,
        "file": f"docs/lesson_assets/reports/{filename}",
        "title": f"تقرير {topic_ar} ({age_group})",
        "item_count": len(markdown.splitlines()),
    }



async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0, help="Max reports to generate (0 = all)")
    parser.add_argument("--delay", type=float, default=3.0, help="Delay between requests in seconds")
    args = parser.parse_args()

    if not MISSING_PATH.exists():
        print(f"Missing file: {MISSING_PATH}")
        return

    with open(MISSING_PATH, "r", encoding="utf-8") as f:
        lessons = json.load(f)

    if args.limit:
        lessons = lessons[:args.limit]

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Generating reports for {len(lessons)} lessons using NotebookLM ask...")
    print(f"Notebook: {NOTEBOOK_ID}")
    print(f"Output dir: {REPORTS_DIR}")

    with open(INDEX_PATH, "r", encoding="utf-8") as f:
        index = json.load(f)

    # Build lookup from lesson_id to index position
    lesson_lookup = {l["lesson_id"]: i for i, l in enumerate(index["lessons"])}

    generated = 0
    failed = []

    for i, lesson in enumerate(lessons, 1):
        print(f"\n[{i}/{len(lessons)}] Processing {lesson['lesson_id']}...")
        try:
            asset = await generate_report_for_lesson(lesson)
            if asset:
                pos = lesson_lookup.get(lesson["lesson_id"])
                if pos is not None:
                    # Ensure nested keys exist
                    lesson_entry = index["lessons"][pos]
                    if "assets" not in lesson_entry or not isinstance(lesson_entry.get("assets"), dict):
                        lesson_entry["assets"] = {}
                    if "reports" not in lesson_entry["assets"]:
                        lesson_entry["assets"]["reports"] = []
                    lesson_entry["assets"]["reports"].append(asset)
                    # Deduplicate by id
                    seen = set()
                    unique = []
                    for r in lesson_entry["assets"]["reports"]:
                        if r["id"] not in seen:
                            seen.add(r["id"])
                            unique.append(r)
                    lesson_entry["assets"]["reports"] = unique
                generated += 1
            else:
                failed.append(lesson["lesson_id"])
        except Exception as e:
            print(f"    ❌ Exception: {e}")
            failed.append(lesson["lesson_id"])

        if i < len(lessons):
            await asyncio.sleep(args.delay)

    # Update metadata counts
    total_lessons = len(index["lessons"])
    index["metadata"]["coverage"]["reports"] = (
        f"{sum(1 for l in index['lessons'] if l['assets'].get('reports'))}/{total_lessons}"
    )
    index["metadata"]["updated_at"] = datetime.utcnow().isoformat() + "Z"

    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Generated {generated} reports")
    print(f"❌ Failed: {len(failed)} - {failed}")
    print(f"Updated {INDEX_PATH}")

    # Git commit
    print("\nCommitting changes...")
    try:
        subprocess.run(
            ["git", "add", "docs/lesson_index.json", "docs/lesson_assets/reports/"],
            cwd=BASE_DIR,
            check=True,
        )
        commit_msg = f"chore(reports): generate {generated} missing NotebookLM reports"
        if failed:
            commit_msg += f" (failed: {len(failed)})"
        subprocess.run(
            ["git", "commit", "-m", commit_msg],
            cwd=BASE_DIR,
            check=True,
        )
        subprocess.run(
            ["git", "push", "origin", "main"],
            cwd=BASE_DIR,
            check=True,
        )
        print("✅ Committed and pushed.")
    except subprocess.CalledProcessError as e:
        print(f"⚠️ Git operation failed: {e}")


if __name__ == "__main__":
    asyncio.run(main())
