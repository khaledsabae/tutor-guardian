#!/usr/bin/env python3
"""
trigger_and_download_podcasts.py
Trigger audio generation for all lessons that have source_id but no podcast.
Then poll and download. Skips upload phase entirely.
"""

import json, subprocess, time, re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
DOCS_DIR = BASE_DIR / "docs"
INDEX_FILE = DOCS_DIR / "lesson_index.json"
NOTEBOOKLM = str(BASE_DIR / "notebooklm_env/bin/notebooklm")

def run(cmd, timeout=60):
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return r.stdout.strip() + r.stderr.strip(), r.returncode

def trigger_podcast(source_id, lesson_id):
    out, rc = run([NOTEBOOKLM, "generate", "audio", "--language", "ar_001", "-s", source_id], timeout=60)
    m = re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", out)
    if m:
        task_id = m.group()
        print(f"  ✅ {lesson_id} -> {task_id}")
        return task_id
    print(f"  ❌ {lesson_id} -> FAILED: {out[:120]}")
    return None

def poll_task(task_id):
    out, rc = run([NOTEBOOKLM, "artifact", "poll", task_id, "--json"], timeout=30)
    try:
        d = json.loads(out)
        return d.get("status"), d.get("url")
    except:
        return None, None

def download_podcast(source_id, lesson_id):
    out_path = DOCS_DIR / f"{lesson_id}_podcast.mp3"
    out, rc = run([NOTEBOOKLM, "download", "audio", "--artifact", source_id, str(out_path), "--force"], timeout=120)
    if rc == 0 and out_path.exists() and out_path.stat().st_size > 10000:
        size_kb = out_path.stat().st_size // 1024
        print(f"    -> Downloaded! ({size_kb} KB)")
        return f"docs/{out_path.name}"
    return None

def update_index(lesson_id, file_path):
    with open(INDEX_FILE) as f:
        data = json.load(f)
    base_url = "https://tg-api.alsaba.cloud/static/docs"
    filename = Path(file_path).name
    for lesson in data["lessons"]:
        if lesson.get("lesson_id") == lesson_id:
            lesson.setdefault("assets", {})["podcasts"] = [{
                "id": f"{lesson_id}_podcast",
                "url": f"{base_url}/{filename}",
                "file": f"docs/{filename}",
                "language": "ar",
                "duration_estimate": "medium"
            }]
            break
    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def main():
    with open(INDEX_FILE) as f:
        data = json.load(f)

    # Find lessons with source_id but no podcast
    to_process = []
    for l in data["lessons"]:
        lid = l.get("lesson_id", "")
        source_id = l.get("source_id", "")
        podcasts = l.get("assets", {}).get("podcasts", [])
        if source_id and not podcasts:
            to_process.append({"id": lid, "source_id": source_id})

    print(f"Found {len(to_process)} lessons ready for generation (have source_id, no podcast)")

    # Phase 1: Trigger all
    print(f"\n=== Triggering {len(to_process)} podcasts ===")
    tasks = {}
    for i, lesson in enumerate(to_process, 1):
        lid = lesson["id"]
        source_id = lesson["source_id"]
        print(f"  [{i}/{len(to_process)}] {lid}")
        task_id = trigger_podcast(source_id, lid)
        if task_id:
            tasks[lid] = {"task_id": task_id, "source_id": source_id}
        time.sleep(0.3)

    print(f"\nTriggered: {len(tasks)}/{len(to_process)}")

    if not tasks:
        print("No tasks triggered — quota may still be limited. Try again later.")
        return

    # Phase 2: Poll and download
    print(f"\n=== Polling {len(tasks)} tasks ===")
    remaining = dict(tasks)
    downloaded = 0
    failed = []
    max_polls = 40

    for poll_count in range(1, max_polls + 1):
        wait = 10 if poll_count == 1 else 60
        print(f"\nWaiting {wait}s... (round {poll_count}, {len(remaining)} remaining)")
        time.sleep(wait)

        done_this_round = []
        for lid, info in list(remaining.items()):
            task_id = info["task_id"]
            source_id = info["source_id"]
            status, url = poll_task(task_id)
            if status in ("pending", "complete") and url:
                print(f"  [{lid}] Ready! Downloading...")
                file_path = download_podcast(source_id, lid)
                if file_path:
                    update_index(lid, file_path)
                    downloaded += 1
                    done_this_round.append(lid)
                else:
                    failed.append(lid)
                    done_this_round.append(lid)
            elif status == "failed":
                print(f"  [{lid}] FAILED")
                failed.append(lid)
                done_this_round.append(lid)
            else:
                print(f"  [{lid}] status={status} (waiting...)")

        for lid in done_this_round:
            remaining.pop(lid, None)

        if not remaining:
            break

    print(f"\n=== Final Summary ===")
    print(f"Downloaded: {downloaded}")
    print(f"Failed: {len(failed)}: {failed}")
    print(f"Still pending: {list(remaining.keys())}")

    if downloaded > 0:
        print("\nCommitting updates to git...")
        import os
        os.system("cd /home/khalednew/projects/tutor-guardian && git add docs/lesson_index.json && git commit -m f'feat: add podcasts for {downloaded} lessons' && git push origin main")

if __name__ == "__main__":
    main()
