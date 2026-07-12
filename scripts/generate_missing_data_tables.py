#!/usr/bin/env python3
"""
Generate missing data_table assets for lessons using NotebookLM ask.

Outputs:
- docs/lesson_assets/data_tables/<uuid>_data_table_<lesson_id>.csv
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
DATA_DIR = BASE_DIR / "docs/lesson_assets/data_tables"
INDEX_PATH = BASE_DIR / "docs/lesson_index.json"
MISSING_PATH = BASE_DIR / "scripts/missing_data_tables.json"
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

DATA_TABLE_PROMPT = '''بناءً على الدرس/المصدر المحدد فقط، قم بإنشاء "جدول بيانات تربوي" للأهل.

اكتب المخرجات بتنسيق JSON فقط داخل كتلة markdown (` ```json `).

المتطلبات:
1. قم بتوفير مصفوفة JSON باسم "data".
2. كل عنصر في المصفوفة يجب أن يكون كائنًا يحتوي على المفاتيح التالية (بالعربية):
   - "المجال"
   - "العمر"
   - "المؤشر"
   - "الإجراء"
   - "المصدر"
3. وفر 5-7 صفوف (كائنات) فقط.
4. أجب باللغة العربية الفصحى المبسطة فقط.
5. لا تكتب أي نصوص تمهيدية أو ختامية خارج كتلة JSON.

مثال:
```json
{
  "data": [
    {
      "المجال": "النوم",
      "العمر": "0-3 سنوات",
      "المؤشر": "صعوبة النوم المتقطع",
      "الإجراء": "إنشاء روتين نوم ثابت للطفل",
      "المصدر": "النوم الهادئ يعزز نمو الدماغ والذاكرة"
    }
  ]
}
```
'''


def json_to_csv(data: list) -> str:
    """Convert list of dicts to CSV string in RFC 4180 format."""
    if not data:
        return ""
    
    headers = ["مجال", "العمر", "المؤشر", "الإجراء", "المصدر"]
    
    def escape(val: str) -> str:
        val = str(val).replace('"', '""')
        return f'"{val}"'
        
    lines = []
    lines.append(",".join(headers))
    for row in data:
        row_vals = [
            row.get("المجال", ""),
            row.get("العمر", ""),
            row.get("المؤشر", ""),
            row.get("الإجراء", ""),
            row.get("المصدر", "")
        ]
        lines.append(",".join(escape(v) for v in row_vals))
    return "\n".join(lines)


def extract_json_from_markdown(text: str) -> dict | None:
    """Extract JSON object from markdown code block."""
    # Look for ```json ... ```
    match = re.search(r"```json\s*\n(.*?)\n```", text, re.DOTALL | re.IGNORECASE)
    if match:
        json_text = match.group(1).strip()
    else:
        # Fallback: look for any ``` ... ```
        match = re.search(r"```\s*\n(.*?)\n```", text, re.DOTALL)
        if match:
            json_text = match.group(1).strip()
        else:
            # Try to parse the whole text as JSON
            json_text = text.strip()
    # Remove invalid control characters
    json_text = re.sub(r'[\x00-\x1F\x7F-\x9F]', ' ', json_text)
    try:
        return json.loads(json_text)
    except json.JSONDecodeError as e:
        print(f"    ⚠️ JSON parse error: {e}")
        return None


async def run_notebooklm_ask(source_id: str) -> str:
    """Run a single NotebookLM ask query for a source."""
    cmd = [
        str(NOTEBOOKLM_BIN), "ask",
        "-n", NOTEBOOK_ID,
        "-s", source_id,
        "--new", "-y",
        DATA_TABLE_PROMPT,
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
        return f"### Error generating data_table\n{err}"

    text = stdout.decode(errors="replace").strip()
    # Strip notebooklm CLI trailing metadata lines
    lines = text.splitlines()
    cleaned = []
    for line in lines:
        if line.startswith("New conversation:"):
            break
        cleaned.append(line)
    return "\n".join(cleaned).strip()


async def generate_data_table_for_lesson(lesson: dict) -> dict | None:
    """Generate a data table for one lesson and return asset entry."""
    lesson_id = lesson["lesson_id"]
    source_id = lesson["source_id"]
    age_group = lesson["age_group"]
    topic_path = lesson["topic_path"]

    print(f"\n[{lesson_id}] asking NotebookLM source {source_id}...")

    content = await run_notebooklm_ask(source_id)
    if content.startswith("### Error"):
        return None

    parsed = extract_json_from_markdown(content)
    if not parsed or "data" not in parsed:
        print(f"    ⚠️ No valid JSON extracted")
        return None

    csv_content = json_to_csv(parsed["data"])

    if not csv_content or len(csv_content.splitlines()) < 2:
        print(f"    ⚠️ Empty CSV generated")
        return None

    artifact_id = str(uuid.uuid4())
    filename = f"{artifact_id}_data_table_{lesson_id}.csv"
    filepath = DATA_DIR / filename

    with open(filepath, "w", encoding="utf-8", newline="") as f:
        f.write(csv_content)

    print(f"    ✅ Saved: {filepath}")

    topic_ar = TITLE_MAP.get(topic_path, topic_path.replace("_", " ").title())
    return {
        "id": artifact_id,
        "file": f"docs/lesson_assets/data_tables/{filename}",
        "title": f"جدول بيانات {topic_ar} ({age_group})",
        "item_count": max(0, len(csv_content.splitlines()) - 1),
    }


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0, help="Max data_tables to generate (0 = all)")
    parser.add_argument("--delay", type=float, default=3.0, help="Delay between requests in seconds")
    args = parser.parse_args()

    if not MISSING_PATH.exists():
        print(f"Missing file: {MISSING_PATH}")
        return

    with open(MISSING_PATH, "r", encoding="utf-8") as f:
        lessons = json.load(f)

    if args.limit:
        lessons = lessons[:args.limit]

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Generating data_tables for {len(lessons)} lessons using NotebookLM ask...")
    print(f"Notebook: {NOTEBOOK_ID}")
    print(f"Output dir: {DATA_DIR}")

    with open(INDEX_PATH, "r", encoding="utf-8") as f:
        index = json.load(f)

    lesson_lookup = {l["lesson_id"]: i for i, l in enumerate(index["lessons"])}

    generated = 0
    failed = []

    for i, lesson in enumerate(lessons, 1):
        print(f"\n[{i}/{len(lessons)}] Processing {lesson['lesson_id']}...")
        try:
            asset = await generate_data_table_for_lesson(lesson)
            if asset:
                pos = lesson_lookup.get(lesson["lesson_id"])
                if pos is not None:
                    lesson_entry = index["lessons"][pos]
                    if "assets" not in lesson_entry or not isinstance(lesson_entry.get("assets"), dict):
                        lesson_entry["assets"] = {}
                    if "data_tables" not in lesson_entry["assets"]:
                        lesson_entry["assets"]["data_tables"] = []
                    lesson_entry["assets"]["data_tables"].append(asset)
                    # Deduplicate by id
                    seen = set()
                    unique = []
                    for dt in lesson_entry["assets"]["data_tables"]:
                        if dt["id"] not in seen:
                            seen.add(dt["id"])
                            unique.append(dt)
                    lesson_entry["assets"]["data_tables"] = unique
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
    index["metadata"]["coverage"]["data_tables"] = (
        f"{sum(1 for l in index['lessons'] if l['assets'].get('data_tables'))}/{total_lessons}"
    )
    index["metadata"]["updated_at"] = datetime.utcnow().isoformat() + "Z"

    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Generated {generated} data_tables")
    print(f"❌ Failed: {len(failed)} - {failed}")
    print(f"Updated {INDEX_PATH}")

    # Git commit
    print("\nCommitting changes...")
    try:
        subprocess.run(
            ["git", "add", "docs/lesson_index.json", "docs/lesson_assets/data_tables/", "source_to_lesson.json"],
            cwd=BASE_DIR,
            check=True,
        )
        commit_msg = f"chore(data-tables): generate {generated} missing NotebookLM data tables"
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
