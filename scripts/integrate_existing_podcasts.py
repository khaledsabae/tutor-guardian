#!/usr/bin/env python3
import os
import re
import json
from pathlib import Path

BASE = Path("/home/khalednew/projects/tutor-guardian")
INDEX_PATH = BASE / "docs/lesson_index.json"

def main():
    if not INDEX_PATH.exists():
        print(f"Error: {INDEX_PATH} not found.")
        return

    with open(INDEX_PATH, 'r', encoding='utf-8') as f:
        index = json.load(f)

    lessons = index.get("lessons", [])
    lessons_by_key = {}
    for l in lessons:
        # Create a matching key: (age_group, topic_path, order)
        # Convert age group like "10-12" to "10_12" to match filename structure
        age_key = l["age_group"].replace("-", "_")
        topic_key = l["topic_path"]
        
        # Get order/number suffix from lesson_id (e.g., "lesson_10-12_cyber_01" -> 1)
        match = re.search(r'_(\d+)$', l["lesson_id"])
        order = int(match.group(1)) if match else l.get("order", 1)
        
        key = (age_key, topic_key, order)
        lessons_by_key[key] = l

    # Special manual mapping for lesson_01_podcast.mp3 and renamed topics
    special_mappings = {
        "lesson_01_podcast.mp3": ("10_12", "cyber_digital_citizenship", 1),
        "lesson_demo_podcast.mp3": ("10_12", "cyber_digital_citizenship", 1),
        "lesson_16_18_medical_adulthood_01_podcast.mp3": ("16_18", "medical_adult_transition", 1),
        "lesson_16_18_medical_adulthood_02_podcast.mp3": ("16_18", "medical_adult_transition", 2),
        "lesson_16_18_medical_adulthood_03_podcast.mp3": ("16_18", "medical_adult_transition", 3),
    }

    docs_dir = BASE / "docs"
    integrated_count = 0

    for file_path in sorted(docs_dir.glob("*.mp3")):
        fname = file_path.name
        
        # Skip age 0-3 podcasts since they are already integrated and are Arabic
        if "lesson_0-3" in fname:
            continue

        target_key = None
        if fname in special_mappings:
            target_key = special_mappings[fname]
        else:
            # Parse typical name like: lesson_10_12_cyber_digital_citizenship_02_podcast.mp3
            # Pattern: lesson_{age}_{topic}_{order}_podcast.mp3
            match = re.search(r'lesson_(\d+_\d+)_(.+)_(\d+)_podcast\.mp3', fname)
            if match:
                age_str = match.group(1)
                topic_str = match.group(2)
                order_val = int(match.group(3))
                target_key = (age_str, topic_str, order_val)
        
        if target_key and target_key in lessons_by_key:
            lesson = lessons_by_key[target_key]
            size_bytes = file_path.stat().st_size
            
            # Update podcasts list
            if "podcasts" not in lesson["assets"]:
                lesson["assets"]["podcasts"] = []
            
            # Avoid duplicate entries
            existing_files = {p.get("file") for p in lesson["assets"]["podcasts"]}
            rel_path = f"docs/{fname}"
            if rel_path not in existing_files:
                lesson["assets"]["podcasts"].append({
                    "file": rel_path,
                    "size_bytes": size_bytes
                })
                print(f"Mapped {fname} -> {lesson['lesson_id']}")
                integrated_count += 1
        else:
            print(f"Could not map file: {fname} (key: {target_key})")

    # Save index
    with open(INDEX_PATH, 'w', encoding='utf-8') as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    print(f"\nSuccessfully integrated {integrated_count} existing podcasts into lesson_index.json")

if __name__ == "__main__":
    main()
