import json, glob, os, re

with open("docs/lesson_index.json") as f:
    idx = json.load(f)
lessons = {l["lesson_id"]: l for l in idx["lessons"]}

podcasts = set()
for p in glob.glob("docs/lesson_*_podcast.mp3"):
    m = re.search(r'lesson_(.+?)_podcast\.mp3$', os.path.basename(p))
    if m:
        podcasts.add("lesson_" + m.group(1))
for p in glob.glob("docs/lesson_*_podcast*.mp3"):
    m = re.search(r'lesson_(.+?)_podcast', os.path.basename(p))
    if m:
        podcasts.add("lesson_" + m.group(1))

missing = sorted(set(lessons.keys()) - podcasts)
# Filter only the NEW lessons that actually need sources (exclude old ones that might already have artifacts but just missing file)
# Focus on lessons that don't have ANY podcast file in docs/
print(f"Total lessons: {len(lessons)}")
print(f"Have podcast: {len(podcasts)}")
print(f"Missing podcast: {len(missing)}")

# Check if any of these already have artifacts in notebook by checking source names
import subprocess
def list_sources():
    out = subprocess.check_output(
        ["/home/khalednew/projects/tutor-guardian/notebooklm_env/bin/notebooklm", "source", "list",
         "-n", "94f191e6-cfbc-4655-a0d7-c8f7ad0f2287", "--json"],
        env={**os.environ, "HOME": "/home/khalednew"}, text=True
    )
    start = out.find('{')
    end = out.rfind('}') + 1
    return json.loads(out[start:end])

data = list_sources()
sources = data.get('sources', data.get('items', []))
print(f"\nSources in notebook: {len(sources)}")

# Build lookup by title
title_to_id = {}
for s in sources:
    title = s.get('title', s.get('name', ''))
    sid = s.get('id', s.get('source_id', ''))
    if title and sid:
        title_to_id[title] = sid

# Find missing lessons that match sources
matched = {}
for lid in missing:
    title = lessons[lid].get("title", "")
    # Try exact match on lesson_id pattern in source titles
    if lid in title_to_id:
        matched[lid] = title_to_id[lid]
    else:
        # Try partial match on title
        base = re.sub(r'(_\d+)$', '', lid)
        candidates = [k for k in title_to_id if base in k]
        if candidates:
            matched[lid] = title_to_id[candidates[0]]

print(f"\nMatched to notebook sources: {len(matched)}")
print(f"Need upload first: {len(missing) - len(matched)}")

for lid, sid in matched.items():
    title = lessons[lid].get("title", lid)
    print(f"  {lid} -> {sid[:12]}... | {title[:50]}")
