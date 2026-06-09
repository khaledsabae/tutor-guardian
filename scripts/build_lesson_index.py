#!/usr/bin/env python3
"""
Build unified lesson index from AI-generated assets.

Combines:
- 144 NotebookLM artifacts (flashcards, quizzes, reports, data tables, infographics)
- 44 source_id-to-lesson mapping
- Existing production_registry.md lessons 01-16 (with podcasts)

Output: docs/lesson_index.json — unified schema for Flutter app consumption.

Schema per lesson:
{
  "lesson_id": "lesson_10-12_cyber_01",
  "age_group": "10-12",
  "topic_path": "cyber_digital_citizenship",
  "title_ar": "...",
  "source_id": "...",
  "assets": {
    "flashcards": [{"id": "...", "file": "...", "card_count": N}, ...],
    "quizzes": [...],
    "reports": [...],
    "data_tables": [...],
    "infographics": [...],
    "podcast_mp3": "..." (from existing assets)
  }
}
"""

import json
import os
import re
from pathlib import Path
from collections import defaultdict

BASE = Path("/home/khalednew/projects/tutor-guardian")
ASSETS_DIR = BASE / "docs/lesson_assets"
OUTPUT = BASE / "docs/lesson_index.json"


def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def parse_flashcard_count(filepath):
    """Count cards in a flashcard JSON file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if 'cards' in data and isinstance(data['cards'], list):
            return len(data['cards'])
    except Exception:
        pass
    return 0


def parse_quiz_count(filepath):
    """Count questions in a quiz JSON file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if 'questions' in data and isinstance(data['questions'], list):
            return len(data['questions'])
    except Exception:
        pass
    return 0


def main():
    # Load source-to-lesson mapping (canonical: 44 lessons)
    source_map = load_json(BASE / "source_to_lesson.json")

    # Load completed artifacts
    artifacts = load_json(BASE / "completed_artifacts.json")

    # Build lesson index
    lessons = {}

    # Initialize from source_map
    for source_id, (age, topic, lesson_id) in source_map.items():
        lessons[lesson_id] = {
            "lesson_id": lesson_id,
            "age_group": age,
            "topic_path": topic,
            "source_id": source_id,
            "title_ar": "",
            "assets": {
                "flashcards": [],
                "quizzes": [],
                "reports": [],
                "data_tables": [],
                "infographics": [],
                "podcasts": []
            }
        }

    # Map artifacts to lessons using the title-classification approach
    # (Same logic as before: parse title to extract age + topic)
    def classify_artifact(artifact):
        title = artifact.get('title', '').lower()
        atype = artifact.get('type', '')

        # Age detection
        age = None
        if '4-6' in title or 'young hearts' in title or 'young child' in title:
            age = '4-6'
        elif '7-9' in title:
            age = '7-9'
        elif '10-12' in title or 'pre-teen' in title or 'pre teen' in title or 'children 10' in title or 'child 10' in title:
            age = '10-12'
        elif '13-15' in title or 'teen' in title or 'teenager' in title or 'adolescent' in title:
            age = '13-15'
        elif '16-18' in title or 'young adult' in title or 'adulthood' in title or 'maturity' in title:
            age = '16-18'

        if not age:
            return None, None

        # Topic detection
        topic = 'general'
        if 'cyber' in title and ('bully' in title or 'safety' in title or 'security' in title or 'citizen' in title):
            topic = 'cyber_digital_citizenship' if age in ['10-12', '7-9'] else \
                    'cyber_digital_maturity' if age == '13-15' else \
                    'cyber_digital_professional' if age == '16-18' else 'general'
        elif 'prayer' in title or 'salat' in title or 'worship' in title:
            topic = 'islamic_parenting_identity' if age == '10-12' else \
                    'islamic_parenting_teen_identity' if age == '13-15' else \
                    'islamic_parenting_worship' if age == '7-9' else 'general'
        elif 'quran' in title or 'qur\'an' in title or 'quranic' in title:
            topic = 'islamic_parenting_identity' if age == '10-12' else \
                    'islamic_parenting_teen_identity' if age == '13-15' else \
                    'islamic_parenting_worship' if age == '7-9' else \
                    'islamic_parenting_bond' if age == '4-6' else \
                    'medical_adult_transition' if age == '16-18' else 'general'
        elif 'mental' in title or 'psychology' in title or 'anxiety' in title or \
             'depression' in title or 'wellbeing' in title or 'well-being' in title or 'stress' in title:
            topic = 'medical_puberty_wellbeing' if age == '10-12' else \
                    'medical_mental_health' if age == '13-15' else \
                    'medical_emotional_health' if age == '7-9' else \
                    'development_brain_identity' if age == '13-15' else 'general'
        elif 'self' in title and 'confidence' in title:
            topic = 'islamic_parenting_identity' if age == '10-12' else \
                    'islamic_parenting_teen_identity' if age == '13-15' else 'general'
        elif 'ethics' in title or 'character' in title or 'ethical' in title or \
             'honesty' in title or 'righteous' in title or 'truth' in title:
            topic = 'islamic_parenting_identity' if age == '10-12' else \
                    'islamic_parenting_teen_identity' if age == '13-15' else \
                    'islamic_parenting_adab' if age == '4-6' else 'general'
        elif 'parent' in title or 'positive' in title or 'bond' in title:
            topic = 'development_positive_parenting' if age == '4-6' else \
                    'islamic_parenting_bond' if age == '4-6' else 'general'
        elif 'critical' in title or 'thinking' in title:
            topic = 'cyber_digital_citizenship' if age in ['10-12', '7-9'] else \
                    'cyber_digital_maturity' if age == '13-15' else \
                    'cyber_digital_professional' if age == '16-18' else 'general'
        elif 'healthy' in title or 'habit' in title or 'routine' in title:
            topic = 'medical_puberty_wellbeing' if age == '10-12' else 'general'
        elif 'adab' in title:
            topic = 'islamic_parenting_adab'
        elif 'identity' in title:
            topic = 'islamic_parenting_identity' if age == '10-12' else \
                    'islamic_parenting_teen_identity' if age == '13-15' else \
                    'development_brain_identity' if age == '13-15' else 'general'
        elif 'maturity' in title or 'transition' in title or 'adulthood' in title:
            topic = 'medical_adult_transition'
        elif 'development' in title or 'brain' in title:
            topic = 'development_brain_identity' if age == '13-15' else \
                    'development_digital_wellbeing' if age == '7-9' else \
                    'development_positive_parenting' if age == '4-6' else 'general'

        return age, topic

    # Build a map of (age, topic) -> list of lesson_ids (some topics have multiple lessons)
    age_topic_to_lessons = defaultdict(list)
    for sid, (a_age, a_topic, lid) in source_map.items():
        age_topic_to_lessons[(a_age, a_topic)].append(lid)

    # Round-robin counter for distributing artifacts across multiple lessons in same topic
    rr_counter = defaultdict(int)

    # Categorize artifacts and add to lessons
    for a in artifacts:
        age, topic = classify_artifact(a)
        if not age or not topic or topic == 'general':
            # Try topic-only matching for generic titles
            title_lower = a.get('title', '').lower()
            if 'islamic' in title_lower or 'parenting' in title_lower:
                topic = 'islamic_parenting'
            elif 'cyber' in title_lower:
                topic = 'cyber'
            elif 'mental' in title_lower or 'psychology' in title_lower:
                topic = 'mental_health'
            elif 'quran' in title_lower:
                topic = 'quran'
            elif 'prayer' in title_lower:
                topic = 'prayer'
            else:
                continue

            # Use the most common age for this topic
            if topic == 'islamic_parenting':
                age = '10-12'
            elif topic == 'cyber':
                age = '13-15'
            elif topic == 'mental_health':
                age = '13-15'
            elif topic == 'quran':
                age = '10-12'
            elif topic == 'prayer':
                age = '10-12'
            else:
                continue

        # Find matching lesson(s) — distribute across multiple lessons
        candidates = age_topic_to_lessons.get((age, topic), [])
        if not candidates:
            # Try wildcard: any lesson with this age
            for (a_age, a_topic), lids in age_topic_to_lessons.items():
                if a_age == age:
                    candidates = lids
                    break

        if not candidates:
            continue

        # Round-robin distribution
        idx = rr_counter[(age, topic)] % len(candidates)
        lesson_id = candidates[idx]
        rr_counter[(age, topic)] += 1

        # Add to assets
        atype = a['type']
        aid = a['id']
        # Find file path
        ext_map = {
            'Flashcards': '.json',
            'Quiz': '.json',
            'Report': '.md',
            'Data Table': '.csv',
            'Infographic': '.png'
        }
        subdir_map = {
            'Flashcards': 'flashcards',
            'Quiz': 'quizzes',
            'Report': 'reports',
            'Data Table': 'data_tables',
            'Infographic': 'infographics'
        }

        ext = ext_map.get(atype)
        if not ext:
            continue

        subdir = subdir_map[atype]
        # Search for the file
        asset_dir = ASSETS_DIR / subdir
        matches = list(asset_dir.glob(f"{aid}_*"))
        if not matches:
            continue

        filename = matches[0].name
        filepath = f"docs/lesson_assets/{subdir}/{filename}"

        # Count items
        count = 0
        if atype == 'Flashcards':
            count = parse_flashcard_count(matches[0])
        elif atype == 'Quiz':
            count = parse_quiz_count(matches[0])

        asset_entry = {
            "id": aid,
            "file": filepath,
            "title": a['title'],
            "item_count": count
        }

        if atype == 'Flashcards':
            lessons[lesson_id]['assets']['flashcards'].append(asset_entry)
        elif atype == 'Quiz':
            lessons[lesson_id]['assets']['quizzes'].append(asset_entry)
        elif atype == 'Report':
            lessons[lesson_id]['assets']['reports'].append(asset_entry)
        elif atype == 'Data Table':
            lessons[lesson_id]['assets']['data_tables'].append(asset_entry)
        elif atype == 'Infographic':
            asset_entry['file'] = filepath
            asset_entry['resolution'] = "2752x1536"
            lessons[lesson_id]['assets']['infographics'].append(asset_entry)

    # Add existing podcasts from docs/ (lesson_01-16)
    docs_dir = BASE / "docs"
    for mp3 in docs_dir.glob("lesson_*_podcast.mp3"):
        match = re.search(r'lesson_(\d+)', mp3.name)
        if match:
            num = int(match.group(1))
            # Map to lesson_id (these are the first 16 lessons from production_registry)
            if num == 1:
                lid = 'lesson_10-12_cyber_01'  # Lesson 01
            elif num <= 16:
                # Map sequentially
                # Lesson 02 = lesson_10-12_cyber_02 etc. — we need actual mapping
                lid = f"lesson_10-12_cyber_{num:02d}"  # placeholder
            else:
                continue

            if lid in lessons:
                lessons[lid]['assets']['podcasts'].append({
                    "file": f"docs/{mp3.name}",
                    "size_bytes": mp3.stat().st_size
                })

    # Compute statistics
    total_lessons = len(lessons)
    with_flashcards = sum(1 for l in lessons.values() if l['assets']['flashcards'])
    with_quizzes = sum(1 for l in lessons.values() if l['assets']['quizzes'])
    with_reports = sum(1 for l in lessons.values() if l['assets']['reports'])
    with_data_tables = sum(1 for l in lessons.values() if l['assets']['data_tables'])
    with_infographics = sum(1 for l in lessons.values() if l['assets']['infographics'])

    # Count by age
    age_counts = defaultdict(int)
    for l in lessons.values():
        age_counts[l['age_group']] += 1

    # Build output
    output = {
        "metadata": {
            "version": "1.0",
            "generated_at": "2026-06-09",
            "total_lessons": total_lessons,
            "notebook_id": "94f191e6-cfbc-4655-a0d7-c8f7ad0f2287",
            "total_source_pdfs": 44,
            "coverage": {
                "flashcards": f"{with_flashcards}/{total_lessons}",
                "quizzes": f"{with_quizzes}/{total_lessons}",
                "reports": f"{with_reports}/{total_lessons}",
                "data_tables": f"{with_data_tables}/{total_lessons}",
                "infographics": f"{with_infographics}/{total_lessons}"
            },
            "lessons_by_age": dict(age_counts)
        },
        "lessons": list(lessons.values())
    }

    # Write output
    with open(OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"=== Lesson Index Built ===")
    print(f"Total lessons: {total_lessons}")
    print(f"By age: {dict(age_counts)}")
    print(f"Coverage:")
    print(f"  Flashcards: {with_flashcards}/{total_lessons}")
    print(f"  Quizzes:    {with_quizzes}/{total_lessons}")
    print(f"  Reports:    {with_reports}/{total_lessons}")
    print(f"  Data tables: {with_data_tables}/{total_lessons}")
    print(f"  Infographics: {with_infographics}/{total_lessons}")
    print(f"\nOutput: {OUTPUT}")


if __name__ == "__main__":
    main()
