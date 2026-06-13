#!/usr/bin/env python3
import json
import os
import re

INDEX_PATH = "docs/lesson_index.json"

def main():
    if not os.path.exists(INDEX_PATH):
        print(f"Error: {INDEX_PATH} not found.")
        return

    with open(INDEX_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    changed = 0
    for lesson in data.get("lessons", []):
        if lesson.get("age_group") == "0-3":
            lesson["age_group"] = "prenatal-1"
            
            # Optionally update the lesson_id if it contains _0_3_
            # This is risky if hardcoded elsewhere, but for consistency we could leave lesson_id alone, 
            # or rename it to `lesson_prenatal_1_...`
            # For safety, we just update the age_group which controls filtering.
            # Let's also update the id to maintain convention:
            if "0_3" in lesson["lesson_id"]:
                lesson["lesson_id"] = lesson["lesson_id"].replace("0_3", "prenatal_1")
            
            changed += 1

    if changed > 0:
        with open(INDEX_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"Migration completed. Updated {changed} lessons from 0-3 to prenatal-1.")
    else:
        print("No lessons found with age_group '0-3'.")

if __name__ == "__main__":
    main()
