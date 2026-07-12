#!/usr/bin/env python3
"""
Cleanup curriculum assets:
1. Strips LLM preamble and "Answer:" block from Markdown reports.
2. Translates English domain/topic names to Arabic in report headers, metadata, and docs/lesson_index.json.
"""

import os
import json
import re
from pathlib import Path

BASE_DIR = Path("/home/khalednew/projects/tutor-guardian")
REPORTS_DIR = BASE_DIR / "docs/lesson_assets/reports"
INDEX_PATH = BASE_DIR / "docs/lesson_index.json"

# Complete 39 domain translation map
DOMAIN_MAP = {
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

# Normalize DOMAIN_MAP keys to plain text with spaces for matching English strings in Markdown
NORMALIZED_MAP = {}
for k, v in DOMAIN_MAP.items():
    NORMALIZED_MAP[k.replace("_", " ").lower()] = v


def translate_domain(topic_path: str) -> str:
    """Translate raw topic_path slug to Arabic name."""
    if not topic_path:
        return ""
    normalized = topic_path.replace("_", " ").strip().lower()
    return NORMALIZED_MAP.get(normalized, topic_path.replace("_", " ").title())


def clean_report_content(content: str) -> str:
    """Strip LLM preamble/Answer block and translate English domains."""
    # 1. Strip raw "Answer:" and any preceding/following greeting text up to the first header
    lines = content.splitlines()
    cleaned_lines = []
    skip_intro = False
    
    for line in lines:
        if line.strip().lower() == "answer:":
            skip_intro = True
            continue
        if skip_intro:
            # Stop skipping when we hit the first section header "### 1" or similar
            if line.strip().startswith("### 1"):
                skip_intro = False
            else:
                continue
        cleaned_lines.append(line)
        
    cleaned_content = "\n".join(cleaned_lines).strip()
    
    # Clean double linebreaks around hr divider if created by the stripping
    cleaned_content = re.sub(r'---\n\n\n+', '---\n\n', cleaned_content)

    # 2. Translate English domain name inside headers and fields
    for eng_name, ar_name in sorted(NORMALIZED_MAP.items(), key=lambda x: len(x[0]), reverse=True):
        # Match case-insensitive space-separated version
        pattern_space = re.compile(re.escape(eng_name), re.IGNORECASE)
        cleaned_content = pattern_space.sub(ar_name, cleaned_content)
        
        # Match case-insensitive underscore version
        pattern_underscore = re.compile(re.escape(eng_name.replace(" ", "_")), re.IGNORECASE)
        cleaned_content = pattern_underscore.sub(ar_name, cleaned_content)
        
    return cleaned_content


def main():
    print("🧹 Cleaning up reports in docs/lesson_assets/reports/...")
    
    markdown_files = list(REPORTS_DIR.glob("*.md"))
    print(f"Found {len(markdown_files)} reports to clean.")
    
    cleaned_count = 0
    for fp in markdown_files:
        content = fp.read_text(encoding="utf-8")
        
        cleaned = clean_report_content(content)
        
        if cleaned != content:
            fp.write_text(cleaned, encoding="utf-8")
            cleaned_count += 1
            
    print(f"✓ Cleaned and translated {cleaned_count} Markdown reports.")

    # 3. Translate titles in docs/lesson_index.json
    if INDEX_PATH.exists():
        print(f"🧹 Translating reports/data-tables titles in {INDEX_PATH.name}...")
        with open(INDEX_PATH, "r", encoding="utf-8") as f:
            index = json.load(f)
            
        modified = False
        for lesson in index.get("lessons", []):
            topic_path = lesson.get("topic_path", "")
            age_group = lesson.get("age_group", "")
            translated = translate_domain(topic_path)
            
            assets = lesson.get("assets", {})
            if assets:
                if "reports" in assets:
                    for r in assets["reports"]:
                        new_title = f"تقرير {translated} ({age_group})"
                        if r.get("title") != new_title:
                            r["title"] = new_title
                            modified = True
                if "data_tables" in assets:
                    for t in assets["data_tables"]:
                        new_title = f"جدول بيانات {translated} ({age_group})"
                        if t.get("title") != new_title:
                            t["title"] = new_title
                            modified = True
                            
        if modified:
            with open(INDEX_PATH, "w", encoding="utf-8") as f:
                json.dump(index, f, ensure_ascii=False, indent=2)
            print("✓ Updated docs/lesson_index.json successfully.")
        else:
            print("✓ docs/lesson_index.json is already fully translated.")


if __name__ == "__main__":
    main()
