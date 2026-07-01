import json, os, subprocess, re, glob

CLI = "/home/khalednew/projects/tutor-guardian/notebooklm_env/bin/notebooklm"
NOTEBOOK = "94f191e6-cfbc-4655-a0d7-c8f7ad0f2287"
DOCS = "/home/khalednew/projects/tutor-guardian/docs"

with open("/tmp/artifacts.json") as f:
    data = json.load(f)
artifacts = data.get("artifacts", [])
audios = [a for a in artifacts if "audio" in a.get("type", "").lower() and a.get("status", a.get("state","")) == "completed"]
print(f"Total completed audio artifacts: {len(audios)}")

existing = set()
for p in glob.glob(f"{DOCS}/lesson_*_podcast.mp3"):
    existing.add(os.path.basename(p))
for p in glob.glob(f"{DOCS}/lesson_*_podcast*.mp3"):
    existing.add(os.path.basename(p))
print(f"Existing podcast files in docs/: {len(existing)}")

downloaded = 0
skipped = 0
failed = 0
for a in audios:
    title = a.get("title", "podcast").strip()
    aid = a.get("id", "")
    safe = re.sub(r'[^\w\s-]', '', title).strip()
    safe = re.sub(r'[\s-]+', '_', safe)
    fname = f"lesson_{safe[:55]}_{aid[:8]}.mp3"
    fpath = os.path.join(DOCS, fname)

    if os.path.exists(fpath) and os.path.getsize(fpath) > 100000:
        skipped += 1
        continue

    cmd = [CLI, "download", "audio", aid, "-n", NOTEBOOK, fpath, "--force"]
    env = {**os.environ, "HOME": "/home/khalednew"}
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=120, env=env)
        if res.returncode == 0 and os.path.exists(fpath) and os.path.getsize(fpath) > 100000:
            print(f"  [OK] {title[:50]} ({os.path.getsize(fpath)//1024//1024} MB)")
            downloaded += 1
        else:
            print(f"  [FAIL] {title[:50]} | {res.stderr.strip()[:80]}")
            failed += 1
    except Exception as e:
        print(f"  [ERR] {title[:50]} | {str(e)[:80]}")
        failed += 1

print(f"\n=== FINAL ===")
print(f"Downloaded: {downloaded}")
print(f"Skipped (already there): {skipped}")
print(f"Failed: {failed}")
print(f"Total in docs/: {len(glob.glob(f'{DOCS}/lesson_*_podcast.mp3')) + len(glob.glob(f'{DOCS}/lesson_*_podcast*.mp3'))}")
