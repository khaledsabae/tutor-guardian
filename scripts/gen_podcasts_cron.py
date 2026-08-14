#!/usr/bin/env python3
"""Cron-safe podcast generator (NotebookLM audio overviews), any language.

Mirror of gen_path_videos_cron.py but for audio. Idempotent (skips lessons whose
podcast already exists **in the requested language**), persists in-flight task
ids across runs, and never infinite-loops on the daily quota — so cron drains
the backlog over days, then the wrapper self-disables.

    python3 scripts/gen_podcasts_cron.py              # Arabic (default)
    python3 scripts/gen_podcasts_cron.py --lang en
    python3 scripts/gen_podcasts_cron.py --lang en --dry-run

Input : source_to_lesson.json      ({source_id: [age, topic, lesson_id]})
State : scratch/podcast_tasks.json  ({state_key: task_id})

Two bugs this file exists to fix
--------------------------------
1. **The cron has been calling a file that does not exist.** `b704d67` moved
   this script to `scripts/archive/` and `cron_gen_podcasts.sh:25` was never
   updated. The wrapper is `set -u`, not `set -e`, so python exits 2, the log
   faithfully records `gen exit 2`, and the rsync and self-disable blocks run
   anyway — a cron that looks healthy and generates nothing. The archived copy
   is doubly broken: its `BASE = parent.parent` resolves to `scripts/` from
   inside `archive/`, so every path it builds is wrong.

2. **Language was hard-coded in ten files and never a parameter.** The skip
   predicate keyed off the Arabic filename, so an English run would inspect the
   Arabic podcast, judge it complete, skip all 170 lessons, and exit 0 having
   produced nothing.

Naming and thresholds come from `backend/app/media_naming.py` so the API and
this script cannot drift apart on where a file lives or when it is finished.
"""
import argparse
import asyncio
import json
import os
import re
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "backend"))
from app.media_naming import (  # noqa: E402
    AUDIO_CLI_LANG, MIN_PODCAST_BYTES, SOURCE_LANG, podcast_rel,
)

sys.path.insert(0, str(BASE / "ops" / "tools"))
from media_index import upsert_media  # noqa: E402

CLI = str(BASE / "notebooklm_env" / "bin" / "notebooklm")

# 🚨 Its own profile, not `default`.
#
# The notebooklm session lives in ~/.notebooklm/profiles/<profile>/
# storage_state.json, and every command rotates the cookies in it. Two
# processes on one profile overwrite each other's refreshed cookies: the
# session expired THREE times on 2026-08-14 while audio and video generation
# ran side by side, and one 54-item upload batch lost its first 9 items to it.
# Separate profiles make concurrent runs independent.
PROFILE = os.environ.get("TG_NOTEBOOKLM_PROFILE", "tg-audio")
CLI_BASE = [CLI, "-p", PROFILE]

# Every `notebooklm` subcommand used here needs the notebook context. Without
# it the CLI exits 1 with "No notebook specified" *before* any API call, the
# task-id regex matches nothing, and `trigger` returns None — which this script
# prints as "no task id" and walks past. That is why a run against all 169
# lessons finished in minutes having produced nothing: not expired auth (the
# brief's first guess, and reads were verified working), just a missing flag.
# `gen_path_videos_cron.py` passes `-n` on all three of its calls; this file
# passed it on none.
NOTEBOOK_ID = "94f191e6-cfbc-4655-a0d7-c8f7ad0f2287"
MAP_FILE = BASE / "source_to_lesson.json"
STATE_FILE = BASE / "scratch" / "podcast_tasks.json"
POLL_BUDGET_SEC = 22 * 60
ENV = {**os.environ, "HOME": os.environ.get("HOME", "/home/khalednew")}


async def _run(*cmd, timeout=180):
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, env=ENV)
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        return 1, "", "timeout"
    return proc.returncode, out.decode(), err.decode()


def _pod_path(lesson_id: str, lang: str) -> Path:
    return BASE / podcast_rel(lesson_id, lang)


def _has_pod(lesson_id: str, lang: str) -> bool:
    f = _pod_path(lesson_id, lang)
    return f.exists() and f.stat().st_size > MIN_PODCAST_BYTES


def _state_key(lesson_id: str, lang: str) -> str:
    """Arabic keeps the bare lesson id so the existing state file still resolves;
    other languages are namespaced so two runs cannot claim the same slot."""
    return lesson_id if lang == SOURCE_LANG else f"{lesson_id}@{lang}"


def _split_key(key: str) -> tuple[str, str]:
    return tuple(key.split("@", 1)) if "@" in key else (key, SOURCE_LANG)


def _load(p: Path, default):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def _targets() -> list[tuple[str, str, str]]:
    """Every source-mapped lesson as (lesson_id, source_id, notebook_id).

    The map value is [age, topic, lesson_id] and may carry a 4th element: the
    notebook the source lives on. It has to, because the main notebook is at
    299/300 sources — the lessons that did not fit were uploaded to a second
    one, and a source id is only meaningful together with its notebook.

    🚨 Passing the wrong `-n` reproduces the exact failure this pipeline just
    spent hours diagnosing: the server cannot resolve the source, answers 200
    with a null body, and the CLI reports "Audio generation is unavailable" —
    naming the feature when the fault is the argument.
    """
    out = []
    for sid, meta in _load(MAP_FILE, {}).items():
        if isinstance(meta, list) and len(meta) >= 3 and meta[2]:
            notebook = meta[3] if len(meta) >= 4 and meta[3] else NOTEBOOK_ID
            out.append((meta[2], sid, notebook))
    return out


async def trigger(source_id: str, lang: str, notebook: str = NOTEBOOK_ID):
    code, out, err = await _run(
        *CLI_BASE, "generate", "audio", "-n", notebook,
        "--language", AUDIO_CLI_LANG[lang], "-s", source_id)
    blob = out + err
    if "RateLimit" in blob or "quota" in blob.lower():
        return "RATELIMIT"
    if "generation is unavailable" in blob.lower():
        # The message names the feature; the cause is the source reference.
        return "STALE_SOURCE"
    m = re.search(r"(?:Task|Started):\s*([a-fA-F0-9\-]+)", blob)
    return m.group(1) if m else None


async def poll(task_id: str, notebook: str = NOTEBOOK_ID):
    code, out, err = await _run(
        *CLI_BASE, "artifact", "poll", "-n", notebook, task_id, "--json", timeout=90)
    if code != 0:
        return "error"
    try:
        return json.loads(out).get("status", "error")
    except Exception:
        return "error"


async def download(task_id: str, out_path: Path, notebook: str = NOTEBOOK_ID) -> bool:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    await _run(*CLI_BASE, "download", "audio", "-n", notebook,
               "--artifact", task_id, str(out_path), "--force")
    if not (out_path.exists() and out_path.stat().st_size > MIN_PODCAST_BYTES):
        return False
    # Generators create media 0600; the container runs as uid 10001 against a
    # host bind mount, so 0600 is unreadable in production — the 2026-07-27
    # outage. rsync --chmod fixes the copy; this fixes the original.
    out_path.chmod(0o644)
    return True


def register(lesson_id: str, lang: str, out_path: Path) -> None:
    """Put the file in the index. A download that is not indexed never ships.

    `/lesson-assets` reads the index, not the disk — three English episodes sat
    on disk with zero index entries, so English users kept getting Arabic.
    """
    try:
        result = upsert_media(lesson_id, "podcasts", {
            "file": str(out_path.relative_to(BASE)),
            "language": lang,
            "size_bytes": out_path.stat().st_size,
        })
        print(f"  · index: {result}")
    except Exception as e:  # never lose a generated file to a bookkeeping error
        print(f"  ⚠ index write failed for {lesson_id}: {type(e).__name__}: {e}")


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", default=SOURCE_LANG, choices=sorted(AUDIO_CLI_LANG))
    ap.add_argument("--limit", type=int, help="cap triggers this run")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    lang = args.lang

    targets = _targets()
    nb_of = {lid: nb for lid, _s, nb in targets}
    missing = [(lid, sid) for lid, sid, _nb in targets if not _has_pod(lid, lang)]
    print(f"🎙  lang={lang} ({AUDIO_CLI_LANG[lang]}) · {len(targets)} lessons · "
          f"{len(missing)} missing · min={MIN_PODCAST_BYTES // 1024}KB")

    if args.dry_run:
        for lid, sid in missing[:args.limit or len(missing)]:
            print(f"  [dry-run] {lid} → {podcast_rel(lid, lang)}  (source {sid})")
        return

    state = _load(STATE_FILE, {})

    # 1) resolve in-flight tasks — only this language's
    for key, tid in list(state.items()):
        lid, klang = _split_key(key)
        if klang != lang:
            continue
        if _has_pod(lid, lang):
            state.pop(key, None)
            continue
        st = await poll(tid, nb_of.get(lid, NOTEBOOK_ID))
        print(f"[poll] {lid}: {st}")
        if st == "completed" and await download(tid, _pod_path(lid, lang), nb_of.get(lid, NOTEBOOK_ID)):
            print(f"  ✓ downloaded {lid}")
            register(lid, lang, _pod_path(lid, lang))
            state.pop(key, None)
        elif st == "failed":
            state.pop(key, None)
        # "error"/auth-expiry: keep for next run

    # 2) trigger pending — one rate-limit ends the run; cron resumes
    #
    # `attempted`, not `triggered`: counting only successes means a run where
    # every trigger fails never reaches the cap. `--limit 3` against the
    # notebook-less CLI produced 169 invocations — the cap exists to bound a
    # run when things go wrong, which is exactly when a success-counter stops
    # counting.
    attempted = 0
    stale: list[str] = []
    for lid, sid, notebook in targets:
        if args.limit and attempted >= args.limit:
            break
        key = _state_key(lid, lang)
        if _has_pod(lid, lang) or key in state:
            continue
        attempted += 1
        tid = await trigger(sid, lang, notebook)
        if tid == "RATELIMIT":
            print(f"[trigger] {lid}: rate-limited — retry next run")
            break
        if tid:
            print(f"[trigger] {lid}: task {tid}")
            state[key] = tid
            await asyncio.sleep(5)
        elif tid == "STALE_SOURCE":
            # 🚨 Not an audio outage. NotebookLM answers "Audio generation is
            # unavailable" when -s names a source that no longer exists on the
            # notebook: it accepts CREATE_ARTIFACT, returns 200 with a null
            # body, and never creates a task row. The old branch printed
            # "no task id" and walked on, so 74 stale ids in
            # source_to_lesson.json read as "audio is down" for two weeks —
            # while video, which reads a different and still-valid mapping,
            # worked the whole time. Name the real cause.
            stale.append(lid)
            print(f"[trigger] {lid}: STALE SOURCE {sid[:8]} — not on the "
                  f"notebook. Run ops/tools/refresh_source_map.py")
        else:
            print(f"[trigger] {lid}: no task id")

    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    # 3) bounded poll of freshly-triggered tasks
    deadline = time.time() + POLL_BUDGET_SEC
    while any(_split_key(k)[1] == lang for k in state) and time.time() < deadline:
        await asyncio.sleep(45)
        for key, tid in list(state.items()):
            lid, klang = _split_key(key)
            if klang != lang:
                continue
            st = await poll(tid, nb_of.get(lid, NOTEBOOK_ID))
            if st == "completed" and await download(tid, _pod_path(lid, lang), nb_of.get(lid, NOTEBOOK_ID)):
                print(f"  ✓ downloaded {lid}")
                register(lid, lang, _pod_path(lid, lang))
                state.pop(key, None)
            elif st == "failed":
                state.pop(key, None)
        STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    if stale:
        print(f"\n🚫 {len(stale)} lesson(s) point at a source that is no longer "
              f"on the notebook — regenerate the map, not the audio:")
        print("     python3 ops/tools/refresh_source_map.py --dry-run")
        for lid in stale[:8]:
            print(f"       {lid}")

    done = sum(1 for lid, _s, _n in targets if _has_pod(lid, lang))
    inflight = sum(1 for k in state if _split_key(k)[1] == lang)
    print(f"\n[summary] {lang}: {done}/{len(targets)} done · {inflight} in-flight")


if __name__ == "__main__":
    asyncio.run(main())
