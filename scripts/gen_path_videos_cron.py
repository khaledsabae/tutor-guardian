#!/usr/bin/env python3
"""Cron-safe path-video generator (NotebookLM, ar_eg).

Designed to be invoked repeatedly by cron over several days until every path
in the mapping owns a real video. Unlike generate_missing_path_videos.py this
NEVER blocks forever on a rate limit and persists in-flight task ids across
runs, so the daily NotebookLM quota is drained without re-spending it:

  each run →
    1. poll previously-triggered tasks; download the completed ones
    2. for paths with no video AND no in-flight task: trigger ONE generation
       (skip silently on rate limit — the next cron run retries)
    3. exit

Idempotent: a path whose mp4 already exists (>5 MB) is skipped. Once all are
done this is a no-op.

State:
  scratch/path_source_mapping_new.json  (input: [{path_id,title,source_id}])
  scratch/path_video_tasks.json         (in-flight {path_id: task_id})
"""
import asyncio
import json
import os
import re
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
CLI = str(BASE / "notebooklm_env" / "bin" / "notebooklm")
VIDEOS_DIR = BASE / "docs" / "path_videos"
MAP_FILE = BASE / "scratch" / "path_source_mapping_new.json"
STATE_FILE = BASE / "scratch" / "path_video_tasks.json"
MIN_SIZE = 5 * 1024 * 1024
POLL_BUDGET_SEC = 22 * 60  # bounded polling per run; cron retries the rest
ENV = {**os.environ, "HOME": "/home/khalednew"}

PROMPT = (
    "أنشئ فيديو تعريفي قصير وممتع (~5 دقائق) باللهجة المصرية كعرض تمهيدي لمسار '{title}'. "
    "اشرح للأمهات والآباء بأسلوب دافئ وعملي أهم الأهداف التربوية لهذا المسار، والخطوات العملية "
    "الرئيسية التي سيتعلمونها، ورسالة تربوية أو لفتة إيمانية تدعم المنهج. اجعل النبرة ودودة "
    "ومقنعة كأنك صديق عائلي ينصحهم بلطف."
)


async def _run(*cmd, timeout=180):
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, env=ENV
    )
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        return 1, "", "timeout"
    return proc.returncode, out.decode(), err.decode()


def _vid_path(path_id):
    return VIDEOS_DIR / f"{path_id}_ar_eg.mp4"


def _has_video(path_id):
    f = _vid_path(path_id)
    return f.exists() and f.stat().st_size > MIN_SIZE


def _load(p, default):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


async def trigger(source_id, title):
    code, out, err = await _run(
        CLI, "generate", "video", "--language", "ar_eg", "-s", source_id, PROMPT.format(title=title)
    )
    blob = out + err
    if "RateLimit" in blob or "quota" in blob.lower():
        return "RATELIMIT"
    m = re.search(r"(?:Task|Started):\s*([a-fA-F0-9\-]+)", blob)
    return m.group(1) if m else None


async def poll(task_id):
    code, out, err = await _run(CLI, "artifact", "poll", task_id, "--json", timeout=90)
    if code != 0:
        return "error"
    try:
        return json.loads(out).get("status", "error")
    except Exception:
        return "error"


async def download(task_id, out_path):
    code, _, _ = await _run(CLI, "download", "video", "--artifact", task_id, str(out_path), "--force")
    return out_path.exists() and out_path.stat().st_size > MIN_SIZE


async def main():
    VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
    mapping = _load(MAP_FILE, [])
    state = _load(STATE_FILE, {})  # path_id -> task_id (in flight)

    # 1) resolve in-flight tasks
    for path_id, task_id in list(state.items()):
        if _has_video(path_id):
            state.pop(path_id, None)
            continue
        st = await poll(task_id)
        print(f"[poll] {path_id}: {st}")
        if st == "completed":
            if await download(task_id, _vid_path(path_id)):
                print(f"  ✓ downloaded {path_id}")
                state.pop(path_id, None)
        elif st == "failed":
            state.pop(path_id, None)  # genuine failure — allow re-trigger
        # "error"/auth-expiry: keep the task and retry next run (do NOT drop)  # let it be re-triggered next run

    # 2) trigger paths that have no video and no in-flight task
    for t in mapping:
        pid = t["path_id"]
        if _has_video(pid) or pid in state:
            continue
        tid = await trigger(t["source_id"], t["title"])
        if tid == "RATELIMIT":
            print(f"[trigger] {pid}: rate-limited — will retry next run")
            break  # quota likely exhausted; stop triggering this run
        if tid:
            print(f"[trigger] {pid}: task {tid}")
            state[pid] = tid
            await asyncio.sleep(5)
        else:
            print(f"[trigger] {pid}: no task id")

    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    # 3) bounded poll of freshly-triggered tasks (download any that finish fast)
    deadline = time.time() + POLL_BUDGET_SEC
    while state and time.time() < deadline:
        await asyncio.sleep(45)
        for path_id, task_id in list(state.items()):
            st = await poll(task_id)
            if st == "completed" and await download(task_id, _vid_path(path_id)):
                print(f"  ✓ downloaded {path_id}")
                state.pop(path_id, None)
            elif st in ("failed", "error"):
                state.pop(path_id, None)
        STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    done = sum(1 for t in mapping if _has_video(t["path_id"]))
    print(f"\n[summary] videos done: {done}/{len(mapping)} | in-flight: {len(state)}")


if __name__ == "__main__":
    asyncio.run(main())
