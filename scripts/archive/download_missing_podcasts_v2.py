import json, os, subprocess, re, glob

CLI = "/home/khalednew/projects/tutor-guardian/notebooklm_env/bin/notebooklm"
NOTEBOOK = "94f191e6-cfbc-4655-a0d7-c8f7ad0f2287"
DOCS = "/home/khalednew/projects/tutor-guardian/docs"
ENV = {**os.environ, "HOME": "/home/khalednew"}

# Get all artifacts once
print("Fetching artifacts from NotebookLM...", flush=True)
res = subprocess.run(
    [CLI, "artifact", "list", "-n", NOTEBOOK, "--json"],
    capture_output=True, text=True, timeout=60, env=ENV
)
data = json.loads(res.stdout)
artifacts = data.get("artifacts", [])
audios = [a for a in artifacts if "audio" in a.get("type", "").lower() and a.get("status", a.get("state","")) == "completed"]
print(f"Total audio artifacts: {len(audios)}", flush=True)

# Build title->id map (normalize for matching)
title_to_id = {}
for a in audios:
    t = a.get("title", "").replace("-", "_").lower()
    title_to_id[t] = a["id"]

# Load lessons
with open("docs/lesson_index.json") as f:
    idx = json.load(f)

# Detect existing podcasts
existing = set()
for p in glob.glob(f"{DOCS}/lesson_*_podcast*") + glob.glob(f"{DOCS}/podcast_*"):
    if os.path.getsize(p) < 100000:
        continue
    bn = os.path.basename(p)
    norm = re.sub(r'lesson_(\d+)_(\d+)_', r'lesson_\1-\2_', bn)
    m = re.search(r'lesson_(.+?)_podcast', norm)
    if m:
        existing.add("lesson_" + m.group(1))

all_ids = {l["lesson_id"] for l in idx["lessons"]}
lessons = {l["lesson_id"]: l for l in idx["lessons"]}
missing = sorted(all_ids - existing)

print(f"Existing podcasts: {len(existing)}", flush=True)
print(f"Missing podcasts: {len(missing)}", flush=True)

downloaded = 0
skipped = 0
failed = 0

for lid in missing:
    title = lessons[lid].get("title", lid)
    # Try matching by lesson_id in title
    lid_norm = lid.replace("-", "_").lower()
    matched_id = None
    for t, aid in title_to_id.items():
        if lid_norm in t:
            matched_id = aid
            break
    
    if not matched_id:
        print(f"[NO MATCH] {lid} | {title[:50]}", flush=True)
        failed += 1
        continue
    
    safe = re.sub(r'[^\w\s-]', '', title).strip()
    safe = re.sub(r'[\s-]+', '_', safe)
    fname = f"lesson_{safe[:55]}_{matched_id[:8]}.mp3"
    fpath = os.path.join(DOCS, fname)
    
    if os.path.exists(fpath) and os.path.getsize(fpath) > 100000:
        skipped += 1
        continue
    
    cmd = [CLI, "download", "audio", "-a", matched_id, fpath, "--force"]
    res2 = subprocess.run(cmd, capture_output=True, text=True, timeout=180, env=ENV)
    if res2.returncode == 0 and os.path.exists(fpath) and os.path.getsize(fpath) > 100000:
        size_mb = os.path.getsize(fpath) // 1024 // 1024
        print(f"  [OK] {title[:50]} ({size_mb} MB)", flush=True)
        downloaded += 1
    else:
        print(f"  [FAIL] {title[:50]} | {res2.stderr.strip()[:80]}", flush=True)
        failed += 1

print(f"\n=== FINAL ===", flush=True)
print(f"Downloaded: {downloaded}", flush=True)
print(f"Skipped: {skipped}", flush=True)
print(f"Failed: {failed}", flush=True)
final = len([p for p in glob.glob(f"{DOCS}/lesson_*_podcast*") + glob.glob(f"{DOCS}/podcast_*") if os.path.getsize(p) > 100000])
print(f"Total valid podcast files now: {final}", flush=True)
