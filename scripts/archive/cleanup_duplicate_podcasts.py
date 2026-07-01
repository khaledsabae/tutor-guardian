import os
import hashlib
import json

def md5(fname):
    hash_md5 = hashlib.md5()
    try:
        with open(fname, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except Exception:
        return None

DUPLICATE_HASH = "b9507bd90892b6b4ba882df307617a5f"
INDEX_PATH = "docs/lesson_index.json"
DOCS_DIR = "docs"

# 1. Identify files to delete
files_to_delete = []
for f in os.listdir(DOCS_DIR):
    if f.endswith(".mp3"):
        filepath = os.path.join(DOCS_DIR, f)
        if md5(filepath) == DUPLICATE_HASH:
            files_to_delete.append(filepath)

print(f"Found {len(files_to_delete)} duplicate podcasts to delete.")

# 2. Delete the files
for filepath in files_to_delete:
    os.remove(filepath)
    print(f"Deleted {filepath}")

# 3. Remove references from lesson_index.json
with open(INDEX_PATH, "r") as f:
    index_data = json.load(f)

removed_count = 0
for lesson in index_data.get("lessons", []):
    assets = lesson.get("assets", {})
    podcasts = assets.get("podcasts", [])
    if podcasts:
        new_podcasts = []
        for p in podcasts:
            file_ref = p.get("file", "")
            if os.path.exists(file_ref):
                new_podcasts.append(p)
            else:
                print(f"Removing invalid reference: {file_ref} from {lesson.get('lesson_id')}")
                removed_count += 1
        assets["podcasts"] = new_podcasts

with open(INDEX_PATH, "w") as f:
    json.dump(index_data, f, indent=2)

print(f"Removed {removed_count} invalid podcast references from {INDEX_PATH}.")
