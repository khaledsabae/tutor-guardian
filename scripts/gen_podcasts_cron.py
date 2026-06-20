#!/usr/bin/env python3
"""Cron-safe podcast generator for the 48 new lessons (NotebookLM audio).

Mirror of gen_path_videos_cron.py but for audio overviews. Idempotent (skips
lessons whose *_podcast.mp3 already exists), persists in-flight task ids across
runs, and never infinite-loops on the daily quota — so cron drains the backlog
over a few days, then the wrapper self-disables.

Input : source_to_lesson.json  ({source_id: [age, topic, lesson_id]})
State : scratch/podcast_tasks.json  ({lesson_id: task_id})
"""
import asyncio
import json
import os
import re
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
CLI = str(BASE / "notebooklm_env" / "bin" / "notebooklm")
DOCS = BASE / "docs"
MAP_FILE = BASE / "source_to_lesson.json"
STATE_FILE = BASE / "scratch" / "podcast_tasks.json"
MIN_SIZE = 500 * 1024
POLL_BUDGET_SEC = 22 * 60
ENV = {**os.environ, "HOME": "/home/khalednew"}
NEW_PATHS = ("16-18_islamic_parenting_adult_faith", "16-18_development_adult_readiness",
 "4-6_cyber_early_screens", "4-6_medical_healthy_growth", "2-3_medical_early_wellbeing",
 "7-9_cyber_digital_basics", "10-12_development_pre_teen", "0-3_islamic_parenting_fitrah",
 "2-3_islamic_first_words", "7-9_islamic_parenting_akhlaq", "10-12_islamic_parenting_worship_love",
 "13-15_islamic_parenting_steadfast")


async def _run(*cmd, timeout=180):
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, env=ENV)
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        return 1, "", "timeout"
    return proc.returncode, out.decode(), err.decode()


def _pod_path(lesson_id):
    return DOCS / f"{lesson_id}_podcast.mp3"


def _has_pod(lesson_id):
    f = _pod_path(lesson_id)
    return f.exists() and f.stat().st_size > MIN_SIZE


def _load(p, default):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def _targets():
    smap = _load(MAP_FILE, {})
    out = []
    for sid, meta in smap.items():
        lid = meta[2] if isinstance(meta, list) and len(meta) >= 3 else None
        if lid and any(p in lid for p in NEW_PATHS):
            out.append((lid, sid))
    return out


async def trigger(source_id):
    code, out, err = await _run(CLI, "generate", "audio", "--language", "ar_001", "-s", source_id)
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
    await _run(CLI, "download", "audio", "--artifact", task_id, str(out_path), "--force")
    return out_path.exists() and out_path.stat().st_size > MIN_SIZE


async def main():
    targets = _targets()
    state = _load(STATE_FILE, {})

    # 1) resolve in-flight tasks
    for lid, tid in list(state.items()):
        if _has_pod(lid):
            state.pop(lid, None)
            continue
        st = await poll(tid)
        print(f"[poll] {lid}: {st}")
        if st == "completed":
            if await download(tid, _pod_path(lid)):
                print(f"  ✓ downloaded {lid}")
                state.pop(lid, None)
        elif st == "failed":
            state.pop(lid, None)
        # "error"/auth-expiry: keep for next run

    # 2) trigger pending (one rate-limit stops this run; cron resumes)
    for lid, sid in targets:
        if _has_pod(lid) or lid in state:
            continue
        tid = await trigger(sid)
        if tid == "RATELIMIT":
            print(f"[trigger] {lid}: rate-limited — retry next run")
            break
        if tid:
            print(f"[trigger] {lid}: task {tid}")
            state[lid] = tid
            await asyncio.sleep(5)
        else:
            print(f"[trigger] {lid}: no task id")

    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    # 3) bounded poll of freshly-triggered tasks
    deadline = time.time() + POLL_BUDGET_SEC
    while state and time.time() < deadline:
        await asyncio.sleep(45)
        for lid, tid in list(state.items()):
            st = await poll(tid)
            if st == "completed" and await download(tid, _pod_path(lid)):
                print(f"  ✓ downloaded {lid}")
                state.pop(lid, None)
            elif st == "failed":
                state.pop(lid, None)
        STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    done = sum(1 for lid, _ in targets if _has_pod(lid))
    print(f"\n[summary] podcasts done: {done}/{len(targets)} | in-flight: {len(state)}")


if __name__ == "__main__":
    asyncio.run(main())
