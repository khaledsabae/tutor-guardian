import json
import os
import glob
from pathlib import Path

BASE_DIR = Path("/home/khalednew/projects/tutor-guardian")
DOCS_DIR = BASE_DIR / "docs"
INDEX_FILE = DOCS_DIR / "lesson_index.json"

# Find all mp3 files created in the last 3 days (these are the bad ones)
import time
now = time.time()
three_days_ago = now - (3 * 24 * 3600)

bad_mp3_files = []
for f in glob.glob(str(DOCS_DIR / "*podcast*.mp3")):
    if os.path.getmtime(f) > three_days_ago:
        bad_mp3_files.append(Path(f))

print(f"Found {len(bad_mp3_files)} bad mp3 files.")

# Load index
with open(INDEX_FILE, "r", encoding="utf-8") as f:
    data = json.load(f)

# Find lesson_ids to clear
bad_lesson_ids = set()
for p in bad_mp3_files:
    # filename like lesson_10-12_aqeedah_growth_01_podcast.mp3
    name = p.name
    if name.endswith("_podcast.mp3"):
        lesson_id = name.replace("_podcast.mp3", "")
        bad_lesson_ids.add(lesson_id)

print(f"Clearing podcasts for lessons: {bad_lesson_ids}")

# Clear them from index
cleared_count = 0
for lesson in data["lessons"]:
    if lesson.get("lesson_id") in bad_lesson_ids:
        assets = lesson.get("assets", {})
        if "podcasts" in assets:
            del assets["podcasts"]
            cleared_count += 1

# Save index
with open(INDEX_FILE, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print(f"Cleared {cleared_count} lessons from index.")

# Delete the bad mp3s
for p in bad_mp3_files:
    os.remove(p)
    print(f"Deleted {p.name}")

print("Done. Ready to re-trigger.")
