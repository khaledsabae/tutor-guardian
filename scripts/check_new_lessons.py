import json, glob, os, re

with open("docs/lesson_index.json") as f:
    idx = json.load(f)
lesson_ids = {l["lesson_id"] for l in idx["lessons"]}

existing_assets = set()
for p in glob.glob("docs/lesson_*_assets.md"):
    m = re.search(r'lesson_(.+?)_assets\.md$', os.path.basename(p))
    if m:
        existing_assets.add("lesson_" + m.group(1))

new_only = sorted(lesson_ids - existing_assets)
print(f"Total lessons in index: {len(lesson_ids)}")
print(f"Lessons WITH assets md (old): {len(existing_assets)}")
print(f"Lessons WITHOUT assets md (NEW): {len(new_only)}")
print("\nNew lessons:")
for x in new_only:
    print(f"  {x}")
