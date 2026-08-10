#!/usr/bin/env python3
"""
generate_all_podcasts_v2.py
Upload missing lesson markdown files to NotebookLM, then trigger + poll + download podcasts.
Handles both lessons with existing source_id and lessons needing upload.
"""

import json, os, subprocess, time, sys, glob
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
DOCS_DIR = BASE_DIR / "docs"
INDEX_FILE = DOCS_DIR / "lesson_index.json"
NOTEBOOKLM = str(BASE_DIR / "notebooklm_env/bin/notebooklm")
NOTEBOOK_ID = "94f191e6-cfbc-4655-a0d7-c8f7ad0f2287"

AGE_MAP = {
    "0-3": "age_0_3", "2-3": "age_2_3", "4-6": "age_4_6", "7-9": "age_7_9",
    "10-12": "age_10_12", "13-15": "age_13_15", "16-18": "age_16_18"
}

def run(cmd, timeout=60):
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return r.stdout.strip(), r.returncode

def upload_source(md_path, lesson_id):
    """Upload a markdown file to NotebookLM and return its source_id."""
    print(f"  [upload] {lesson_id}")
    out, rc = run([NOTEBOOKLM, "source", "add", md_path, "-n", NOTEBOOK_ID], timeout=90)
    if rc != 0:
        print(f"    -> Upload FAILED: {out}")
        return None
    # Parse source_id from output
    for line in out.splitlines():
        if "source_id" in line.lower() or "id:" in line.lower():
            parts = line.split()
            for p in parts:
                if len(p) == 36 and p.count("-") == 4:
                    return p
        # Try UUID pattern directly
        import re
        m = re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", line)
        if m:
            return m.group()
    print(f"    -> Could not parse source_id from: {out[:200]}")
    return None

def trigger_podcast(source_id, lesson_id):
    """Trigger podcast generation and return task_id."""
    out, rc = run([NOTEBOOKLM, "generate", "audio", "--language", "ar_001", "-s", source_id], timeout=60)
    import re
    m = re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", out)
    if m:
        task_id = m.group()
        print(f"  [trigger] {lesson_id} -> {task_id}")
        return task_id
    print(f"  [trigger] {lesson_id} -> FAILED: {out[:100]}")
    return None

def poll_task(task_id):
    """Poll a task and return (status, url)."""
    out, rc = run([NOTEBOOKLM, "artifact", "poll", task_id, "--json"], timeout=30)
    try:
        d = json.loads(out)
        return d.get("status"), d.get("url")
    except:
        return None, None

def download_podcast(task_id, lesson_id, source_id):
    """Download podcast mp3 to docs/."""
    out_path = DOCS_DIR / f"{lesson_id}_podcast.mp3"
    out, rc = run([NOTEBOOKLM, "download", "audio", "--artifact", source_id, str(out_path), "--force"], timeout=120)
    if rc == 0 and out_path.exists() and out_path.stat().st_size > 10000:
        print(f"  -> Downloaded! ({out_path.stat().st_size // 1024} KB)")
        return str(out_path.relative_to(BASE_DIR))
    # Try task_id fallback
    out2, rc2 = run([NOTEBOOKLM, "download", "audio", "--artifact", task_id, str(out_path), "--force"], timeout=120)
    if rc2 == 0 and out_path.exists() and out_path.stat().st_size > 10000:
        print(f"  -> Downloaded via task_id! ({out_path.stat().st_size // 1024} KB)")
        return str(out_path.relative_to(BASE_DIR))
    print(f"  -> Download FAILED (rc={rc}, size={out_path.stat().st_size if out_path.exists() else 0})")
    return None

def find_md(lesson_id):
    parts = lesson_id.split("_")
    age = parts[1]
    age_folder = AGE_MAP.get(age, "")
    base = BASE_DIR / "knowledge_base/notebooklm" / age_folder
    # Exact match
    exact = base / f"{lesson_id}.md"
    if exact.exists():
        return str(exact)
    # Glob
    matches = list(base.glob(f"{lesson_id}*.md"))
    if matches:
        return str(matches[0])
    return None

def update_index(lesson_id, file_path, source_id):
    """Update lesson_index.json with podcast info."""
    with open(INDEX_FILE) as f:
        data = json.load(f)
    base_url = "https://tg-api.alsaba.cloud/docs"
    filename = Path(file_path).name
    podcast_url = f"{base_url}/{filename}"
    for lesson in data["lessons"]:
        if lesson.get("lesson_id") == lesson_id:
            lesson.setdefault("assets", {})["podcasts"] = [{
                "id": f"{lesson_id}_podcast",
                "url": podcast_url,
                "file": f"docs/{filename}",
                "language": "ar",
                "duration_estimate": "medium"
            }]
            if source_id:
                lesson["source_id"] = source_id
            break
    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def main():
    with open(INDEX_FILE) as f:
        data = json.load(f)

    # Collect missing lessons
    to_process = []
    for l in data["lessons"]:
        lid = l.get("lesson_id", "")
        if not l.get("assets", {}).get("podcasts"):
            to_process.append({
                "id": lid,
                "source_id": l.get("source_id", ""),
                "age": l.get("age_group", ""),
            })

    print(f"Found {len(to_process)} lessons missing podcasts")

    # Phase 1: Upload those without source_id
    needs_upload = [t for t in to_process if not t["source_id"]]
    has_source   = [t for t in to_process if t["source_id"]]

    print(f"\n=== Phase 1: Uploading {len(needs_upload)} lessons ===")
    for i, lesson in enumerate(needs_upload, 1):
        lid = lesson["id"]
        md_path = find_md(lid)
        if not md_path:
            print(f"  [{i}/{len(needs_upload)}] SKIP {lid} — no markdown found")
            continue
        print(f"  [{i}/{len(needs_upload)}] {lid}")
        source_id = upload_source(md_path, lid)
        if source_id:
            lesson["source_id"] = source_id
            print(f"    -> source_id: {source_id}")
        time.sleep(1)

    # Phase 2: Trigger all
    all_ready = has_source + [t for t in needs_upload if t.get("source_id")]
    print(f"\n=== Phase 2: Triggering {len(all_ready)} podcasts ===")
    tasks = {}
    for i, lesson in enumerate(all_ready, 1):
        lid = lesson["id"]
        source_id = lesson["source_id"]
        print(f"  [{i}/{len(all_ready)}] {lid}")
        task_id = trigger_podcast(source_id, lid)
        if task_id:
            tasks[lid] = {"task_id": task_id, "source_id": source_id}
        time.sleep(0.5)

    # Phase 3: Poll and download
    print(f"\n=== Phase 3: Polling {len(tasks)} tasks ===")
    remaining = dict(tasks)
    downloaded = 0
    failed = []
    max_polls = 30
    poll_count = 0

    while remaining and poll_count < max_polls:
        poll_count += 1
        print(f"\nPolling {len(remaining)} tasks (round {poll_count})...")
        time.sleep(60 if poll_count > 1 else 10)

        done_this_round = []
        for lid, info in remaining.items():
            task_id = info["task_id"]
            source_id = info["source_id"]
            status, url = poll_task(task_id)
            if status in ("pending", "complete") and url:
                print(f"  Downloading {lid}...")
                file_path = download_podcast(task_id, lid, source_id)
                if file_path:
                    update_index(lid, file_path, source_id)
                    downloaded += 1
                    done_this_round.append(lid)
                else:
                    failed.append(lid)
                    done_this_round.append(lid)
            elif status == "failed":
                print(f"  FAILED: {lid}")
                failed.append(lid)
                done_this_round.append(lid)
            # else still in_progress, keep waiting

        for lid in done_this_round:
            remaining.pop(lid, None)

    print(f"\n=== Done ===")
    print(f"Downloaded: {downloaded}")
    print(f"Failed: {len(failed)}: {failed}")
    print(f"Still pending: {list(remaining.keys())}")

if __name__ == "__main__":
    main()
