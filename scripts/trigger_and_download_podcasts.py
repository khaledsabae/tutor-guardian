#!/usr/bin/env python3
"""
trigger_and_download_podcasts.py
Trigger audio generation for all lessons that have source_id but no podcast,
then poll and download. Skips upload phase entirely.

Rate-limit aware:
  - Writes a small state file so we do not hammer NotebookLM after a rate limit.
  - If we hit a rate limit, we stop immediately and skip the next N hours.
  - Exponential backoff between trigger requests to spread load.
"""

import json
import os
import subprocess
import time
import re
from pathlib import Path
from datetime import datetime, timezone

BASE_DIR = Path(__file__).resolve().parents[1]
DOCS_DIR = BASE_DIR / "docs"
INDEX_FILE = DOCS_DIR / "lesson_index.json"
NOTEBOOKLM = str(BASE_DIR / "notebooklm_env/bin/notebooklm")
STATE_FILE = BASE_DIR / "logs" / "notebooklm_state.json"

# Cooldown after a rate-limit event (seconds). NotebookLM audio quota regenerates ~daily.
RATE_LIMIT_COOLDOWN_HOURS = float(os.environ.get("NOTEBOOKLM_COOLDOWN_HOURS", "3"))
MAX_TRIGGER_PER_RUN = int(os.environ.get("PODCAST_MAX_TRIGGER_PER_RUN", "0"))  # 0 = unlimited
MIN_DELAY = float(os.environ.get("PODCAST_MIN_DELAY", "1.0"))
MAX_DELAY = float(os.environ.get("PODCAST_MAX_DELAY", "30.0"))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {
        "last_rate_limit_at": None,
        "pending_podcast_tasks": {},
        "last_run_at": None,
        "last_run_triggered": 0,
        "last_run_downloaded": 0,
    }


def save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def run(cmd, timeout=60):
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return r.stdout.strip() + r.stderr.strip(), r.returncode


def looks_like_rate_limit(out: str) -> bool:
    lower = out.lower()
    return any(x in lower for x in ["ratelimit", "rate limit", "quota", "try again later", "too many requests"])


def trigger_podcast(source_id, lesson_id, notebook_id=None):
    cmd = [NOTEBOOKLM, "generate", "audio", "--language", "ar_001", "-s", source_id]
    if notebook_id:
        cmd.extend(["-n", notebook_id])
    out, rc = run(cmd, timeout=60)

    if looks_like_rate_limit(out):
        return "RATELIMIT"

    m = re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", out)
    if m:
        task_id = m.group()
        print(f"  ✅ {lesson_id} -> {task_id}")
        return task_id
    print(f"  ❌ {lesson_id} -> FAILED: {out[:160]}")
    return None


def poll_task(task_id):
    out, rc = run([NOTEBOOKLM, "artifact", "poll", task_id, "--json"], timeout=30)
    try:
        d = json.loads(out)
        return d.get("status"), d.get("url")
    except Exception:
        return None, None


def download_podcast(source_id, lesson_id, task_id):
    # Prefer downloading by artifact task id if the CLI supports it; fallback to source_id.
    out_path = DOCS_DIR / f"{lesson_id}_podcast.mp3"
    cmd = [NOTEBOOKLM, "download", "audio", "--artifact", source_id, str(out_path), "--force"]
    out, rc = run(cmd, timeout=120)
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


def commit_and_sync(downloaded):
    if downloaded == 0:
        return
    print("\nCommitting updates to git...")
    os.system(
        f"cd /home/khalednew/projects/tutor-guardian "
        f"&& git add docs/lesson_index.json "
        f"&& git commit -q -m 'feat: add podcasts for {downloaded} lessons' "
        f"&& git push origin main"
    )

    print("\nSyncing MP3 files to VPS...")
    os.system(
        "rsync -a --include='*.mp3' --exclude='*' "
        "/home/khalednew/projects/tutor-guardian/docs/ "
        "root@72.62.44.131:/root/tutor-guardian/docs/"
    )


def exponential_delay(consecutive_rate_limits: int) -> float:
    """Return a delay that grows quickly after repeated rate limits."""
    return min(MIN_DELAY * (2 ** consecutive_rate_limits), MAX_DELAY)


def main():
    state = load_state()
    state["last_run_at"] = _now()
    state["last_run_triggered"] = 0
    state["last_run_downloaded"] = 0

    now = datetime.now(timezone.utc)
    last_rl = state.get("last_rate_limit_at")
    if last_rl:
        try:
            last_rl_dt = datetime.fromisoformat(last_rl)
            elapsed = (now - last_rl_dt).total_seconds()
            cooldown = RATE_LIMIT_COOLDOWN_HOURS * 3600
            if elapsed < cooldown:
                remaining = int(cooldown - elapsed)
                print(
                    f"⏳ NotebookLM rate-limit cooldown active. "
                    f"Retry in {remaining // 3600}h {(remaining % 3600) // 60}m. Skipping run."
                )
                return
        except Exception:
            pass

    with open(INDEX_FILE) as f:
        data = json.load(f)

    notebook_id = data.get("metadata", {}).get("notebook_id")

    # Find lessons with source_id but no podcast
    to_process = []
    for l in data["lessons"]:
        lid = l.get("lesson_id", "")
        source_id = l.get("source_id", "")
        podcasts = l.get("assets", {}).get("podcasts", [])
        if source_id and not podcasts:
            to_process.append({"id": lid, "source_id": source_id})

    print(f"Found {len(to_process)} lessons ready for generation (have source_id, no podcast)")

    if MAX_TRIGGER_PER_RUN and len(to_process) > MAX_TRIGGER_PER_RUN:
        print(f"  (limiting this run to first {MAX_TRIGGER_PER_RUN} lessons)")
        to_process = to_process[:MAX_TRIGGER_PER_RUN]

    # Phase 1: Trigger with backoff and immediate stop on rate limit
    print(f"\n=== Triggering {len(to_process)} podcasts ===")
    tasks = {}
    consecutive_rl = 0
    rate_limited_now = False

    for i, lesson in enumerate(to_process, 1):
        lid = lesson["id"]
        source_id = lesson["source_id"]
        print(f"  [{i}/{len(to_process)}] {lid}")
        task_id = trigger_podcast(source_id, lid, notebook_id)

        if task_id == "RATELIMIT":
            consecutive_rl += 1
            state["last_rate_limit_at"] = _now()
            print(
                f"  [!] Rate limit hit ({consecutive_rl}x). "
                f"Stopping trigger phase to prevent error spam."
            )
            if consecutive_rl >= 2:
                rate_limited_now = True
                break
        elif task_id:
            tasks[lid] = {"task_id": task_id, "source_id": source_id}
            consecutive_rl = max(0, consecutive_rl - 1)
        else:
            # Other failure; keep going but cool down a bit.
            pass

        # Backoff: longer after rate limits, short otherwise.
        delay = exponential_delay(consecutive_rl)
        time.sleep(delay)

    print(f"\nTriggered: {len(tasks)}/{len(to_process)}")
    state["last_run_triggered"] = len(tasks)

    # Resume any previously pending tasks from state
    pending = state.get("pending_podcast_tasks", {})
    if pending and not rate_limited_now:
        print(f"  (also polling {len(pending)} tasks from a previous run)")
        tasks.update(pending)

    if not tasks:
        print("No tasks triggered — quota may still be limited. Try again later.")
        save_state(state)
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
                file_path = download_podcast(source_id, lid, task_id)
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

        # Persist remaining pending tasks so we can resume after a crash/reboot.
        state["pending_podcast_tasks"] = remaining
        save_state(state)

        if not remaining:
            break

    print(f"\n=== Final Summary ===")
    print(f"Downloaded: {downloaded}")
    print(f"Failed: {len(failed)}: {failed}")
    print(f"Still pending: {list(remaining.keys())}")

    state["last_run_downloaded"] = downloaded
    state["pending_podcast_tasks"] = remaining
    save_state(state)

    commit_and_sync(downloaded)


if __name__ == "__main__":
    main()
