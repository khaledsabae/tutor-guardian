import json, os, subprocess, re, glob

CLI = "/home/khalednew/projects/tutor-guardian/notebooklm_env/bin/notebooklm"
NOTEBOOK = "94f191e6-cfbc-4655-a0d7-c8f7ad0f2287"
DOCS = "/home/khalednew/projects/tutor-guardian/docs"
ENV = {**os.environ, "HOME": "/home/khalednew"}

# Load missing lessons
with open("docs/lesson_index.json") as f:
    idx = json.load(f)

existing = set()
for p in glob.glob(f"{DOCS}/lesson_*_podcast*") + glob.glob(f"{DOCS}/podcast_*"):
    if os.path.getsize(p) < 100000:
        continue
    bn = os.path.basename(p)
    # normalize age separators
    norm = re.sub(r'lesson_(\d+)_(\d+)_', r'lesson_\1-\2_', bn)
    m = re.search(r'lesson_(.+?)_podcast', norm)
    if m:
        existing.add("lesson_" + m.group(1))

all_ids = {l["lesson_id"] for l in idx["lessons"]}
missing = sorted(all_ids - existing)
lessons = {l["lesson_id"]: l for l in idx["lessons"]}

print(f"Missing podcasts: {len(missing)}")
for m in missing:
    print(f"  {m} | {lessons[m].get('title','')[:50]}")
print()

# Now download these
downloaded = 0
skipped = 0
failed = 0

for lid in missing:
    title = lessons[lid].get("title", lid)
    
    # Try to find matching artifact by searching for lesson ID in artifact title
    cmd_find = [CLI, "artifact", "list", "-n", NOTEBOOK, "--json"]
    res = subprocess.run(cmd_find, capture_output=True, text=True, timeout=30, env=ENV)
    
    if res.returncode != 0:
        print(f"[ERR] Cannot list artifacts: {res.stderr[:80]}")
        failed += 1
        continue
    
    data = json.loads(res.stdout)
    artifacts = data.get("artifacts", [])
    audios = [a for a in artifacts if "audio" in a.get("type", "").lower() 
              and a.get("status", a.get("state","")) == "completed"
              and lid.replace("-", "_") in a.get("title", "").replace("-", "_")]
    
    if not audios:
        print(f"[NO ARTIFACT] {title[:50]}")
        failed += 1
        continue
    
    aid = audios[0]["id"]
    safe = re.sub(r'[^\w\s-]', '', title).strip()
    safe = re.sub(r'[\s-]+', '_', safe)
    fname = f"lesson_{safe[:55]}_{aid[:8]}.mp3"
    fpath = os.path.join(DOCS, fname)
    
    if os.path.exists(fpath) and os.path.getsize(fpath) > 100000:
        skipped += 1
        continue
    
    cmd_dl = [CLI, "download", "audio", "-a", aid, fpath, "--force"]
    res2 = subprocess.run(cmd_dl, capture_output=True, text=True, timeout=180, env=ENV)
    if res2.returncode == 0 and os.path.exists(fpath) and os.path.getsize(fpath) > 100000:
        print(f"  [OK] {title[:50]} ({os.path.getsize(fpath)//1024//1024} MB)")
        downloaded += 1
    else:
        print(f"  [FAIL] {title[:50]} | {res2.stderr.strip()[:80]}")
        failed += 1

print(f"\n=== PODCAST DOWNLOAD FINISHED ===")
print(f"Downloaded: {downloaded}")
print(f"Skipped: {skipped}")
print(f"Failed/No artifact: {failed}")
final = len([p for p in glob.glob(f"{DOCS}/lesson_*_podcast*") + glob.glob(f"{DOCS}/podcast_*") if os.path.getsize(p) > 100000])
print(f"Total valid podcast files now: {final}")
