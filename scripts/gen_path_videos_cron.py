#!/usr/bin/env python3
"""Cron-safe path-video generator (NotebookLM video overviews), any language.

    python3 scripts/gen_path_videos_cron.py               # Arabic (ar_eg)
    python3 scripts/gen_path_videos_cron.py --lang en     # English (en_us)
    python3 scripts/gen_path_videos_cron.py --lang en --dry-run

Language touches four things and all four move together: the `--language` value
passed to the CLI, the filename tag, the state/manifest key, and the prompt.
Miss the filename and an English run inspects the Arabic video, judges it
complete and skips every path; miss the key and it reads the Arabic run's
"done" as its own. Naming comes from backend/app/media_naming.py so the API
cannot disagree with what lands on disk.

Designed to be invoked repeatedly by cron over several days until every path
in the mapping owns a real video. Unlike generate_missing_path_videos.py this
NEVER blocks forever on a rate limit and persists in-flight task ids across
runs, so the daily NotebookLM quota is drained without re-spending it:

  each run →
    1. poll previously-triggered tasks; download the completed ones
    2. for paths with no video AND no in-flight task: trigger ONE generation
       (skip silently on rate limit — the next cron run retries)
    3. exit

Idempotent & duplicate-safe:
  * A path is considered DONE only when the mp4 exists (>5 MB) AND the path
    is recorded in `path_video_manifest.json`. This double gate prevents
    accidental regeneration even if `path_video_tasks.json` or
    `path_video_failures.json` become stale.
  * The script always re-syncs the manifest from disk at startup, so manual
    downloads/uploads (e.g. rsync to VPS) never confuse it.
  * Failures are counted only when the video is still missing.

State (keys are the bare path_id for Arabic, `<path_id>@<lang>` otherwise, so
the existing Arabic state files keep resolving untouched):
  scratch/path_source_mapping_new.json  (input: [{path_id,title,source_id}])
  scratch/path_video_tasks.json         (in-flight {key: task_id})
  scratch/path_video_failures.json      ({key: consecutive_failure_count})
  scratch/path_video_manifest.json      ({key: {completed_at, size_bytes, ...}})
"""
import asyncio
import json
import os
import re
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / "backend"))
from app.media_naming import (  # noqa: E402
    MIN_VIDEO_BYTES, SOURCE_LANG, VIDEO_CLI_LANG, path_video_rel,
)

CLI = str(BASE / "notebooklm_env" / "bin" / "notebooklm")

# Its own profile — see the note in gen_podcasts_cron.py. Sharing one profile
# with a concurrent audio run knocked the session out three times in a day.
PROFILE = os.environ.get("TG_NOTEBOOKLM_PROFILE", "tg-video")
CLI_BASE = [CLI, "-p", PROFILE]
VIDEOS_DIR = BASE / "docs" / "path_videos"
MAP_FILE = BASE / "scratch" / "path_source_mapping_new.json"
STATE_FILE = BASE / "scratch" / "path_video_tasks.json"
FAILS_FILE = BASE / "scratch" / "path_video_failures.json"
MANIFEST_FILE = BASE / "scratch" / "path_video_manifest.json"
MIN_SIZE = MIN_VIDEO_BYTES
MAX_FAILS = 3  # stop re-triggering a path after this many hard failures
POLL_BUDGET_SEC = 22 * 60  # bounded polling per run; cron retries the rest
ENV = {**os.environ, "HOME": "/home/khalednew"}
DRY_RUN = "--dry-run" in sys.argv


def _arg_lang() -> str:
    """`--lang en`. Defaults to Arabic, so existing cron lines are unaffected."""
    if "--lang" in sys.argv:
        value = sys.argv[sys.argv.index("--lang") + 1]
        if value not in VIDEO_CLI_LANG:
            sys.exit(f"❌ unknown --lang {value!r}; known: {sorted(VIDEO_CLI_LANG)}")
        return value
    return SOURCE_LANG


LANG = _arg_lang()

NOTEBOOK_ID = "94f191e6-cfbc-4655-a0d7-c8f7ad0f2287"

# 🚨 The English prompt is WRITTEN, not translated. The Arabic one asks for
# «اللهجة المصرية» — Egyptian dialect — and translating that instruction asks an
# English narrator to speak Egyptian. What carries over is the intent (a warm
# family friend, ~5 minutes, goals → practical steps → a faith-rooted note),
# not the words. The audience differs too: an English-reading Muslim parent
# shares the religious frame but not the dialect register.
PROMPTS = {
    "ar": (
        "أنشئ فيديو تعريفي قصير وممتع (~5 دقائق) باللهجة المصرية كعرض تمهيدي لمسار '{title}'. "
        "اشرح للأمهات والآباء بأسلوب دافئ وعملي أهم الأهداف التربوية لهذا المسار، والخطوات العملية "
        "الرئيسية التي سيتعلمونها، ورسالة تربوية أو لفتة إيمانية تدعم المنهج. اجعل النبرة ودودة "
        "ومقنعة كأنك صديق عائلي ينصحهم بلطف."
    ),
    "en": (
        "Create a short, engaging introductory video (~5 minutes) in clear English "
        "as an opening overview of the '{title}' journey. Speak to Muslim mothers "
        "and fathers who read English and share the same religious frame of "
        "reference — use Islamic vocabulary (tarbiyah, fitrah, rifq) rather than "
        "secular approximations, and keep honorifics where they belong. Cover the "
        "main parenting goals of this journey, the practical steps parents will "
        "learn, and close on a faith-rooted reflection that grounds the approach. "
        "Keep the tone warm, direct and practical — a family friend giving gentle "
        "advice, not a lecture. Never paraphrase or soften a hadith or a Qur'anic "
        "verse; if you quote one, render it faithfully and keep its attribution."
    ),
}
PROMPT = PROMPTS[LANG]


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
    return BASE / path_video_rel(path_id, LANG)


def _unkey(state_key):
    """`path_id@en` → `path_id`.

    🚨 The state dict is keyed by _key(), so iterating `state.items()` yields
    the NAMESPACED key — and passing that to _vid_path() writes
    `path_x@en_en_us.mp4`, which `path_video_candidates()` never looks for. Seven
    videos were generated this way: real files, correct size and duration, 644,
    and invisible to the app. Always unkey before building a path.
    """
    return state_key.split("@", 1)[0]


def _key(path_id):
    """State/manifest/failure key.

    Arabic keeps the bare path_id so path_video_manifest.json,
    path_video_tasks.json and path_video_failures.json keep resolving exactly
    as they do today; other languages are namespaced so an English run cannot
    read an Arabic run's "done" as its own.
    """
    return path_id if LANG == SOURCE_LANG else f"{path_id}@{LANG}"


def _has_video(path_id):
    f = _vid_path(path_id)
    return f.exists() and f.stat().st_size > MIN_SIZE


def _load(p, default):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def _load_manifest():
    return _load(MANIFEST_FILE, {})


def _save_manifest(manifest):
    MANIFEST_FILE.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def _register_done(path_id, task_id=None, source_id=None):
    """Record that a path is finished. This is the authoritative DONE gate."""
    manifest = _load_manifest()
    key = _key(path_id)
    entry = manifest.get(key, {})
    entry.update({
        "completed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "language": LANG,
        "video_path": str(_vid_path(path_id)),
        "size_bytes": _vid_path(path_id).stat().st_size,
        "task_id": task_id or entry.get("task_id"),
        "source_id": source_id or entry.get("source_id"),
    })
    manifest[key] = entry
    _save_manifest(manifest)


def _is_done(path_id):
    """DONE means file exists on disk AND recorded in manifest."""
    if not _has_video(path_id):
        return False
    return _key(path_id) in _load_manifest()


def _sync_manifest_from_disk(mapping):
    """At startup, ensure any existing valid video is in the manifest.

    This protects against stale state/failures files or manual downloads.
    """
    manifest = _load_manifest()
    changed = False
    source_by_path = {t["path_id"]: t["source_id"] for t in mapping}
    for path_id in source_by_path:
        if _has_video(path_id) and _key(path_id) not in manifest:
            _register_done(path_id, task_id=None, source_id=source_by_path[path_id])
            changed = True
    return changed


async def trigger(source_id, title, path_id):
    if DRY_RUN:
        print(f"[trigger] {path_id}: DRY RUN — would trigger source {source_id}")
        return "DRYRUN"
    code, out, err = await _run(
        *CLI_BASE, "generate", "video", "-n", NOTEBOOK_ID,
        "--language", VIDEO_CLI_LANG[LANG], "-s", source_id,
        PROMPT.format(title=title)
    )
    blob = out + err
    if "RateLimit" in blob or "quota" in blob.lower():
        return "RATELIMIT"
    m = re.search(r"(?:Task|Started):\s*([a-fA-F0-9\-]+)", blob)
    return m.group(1) if m else None


async def poll(task_id):
    code, out, err = await _run(*CLI_BASE, "artifact", "poll", "-n", NOTEBOOK_ID, task_id, "--json", timeout=90)
    if code != 0:
        return "error"
    try:
        return json.loads(out).get("status", "error")
    except Exception:
        return "error"


async def download(task_id, out_path):
    code, _, _ = await _run(*CLI_BASE, "download", "video", "-n", NOTEBOOK_ID, "--artifact", task_id, str(out_path), "--force")
    if not (out_path.exists() and out_path.stat().st_size > MIN_SIZE):
        return False
    # The CLI writes 0600. The container runs as uid 10001 against a host bind
    # mount, so 0600 is unreadable in production — that is the 2026-07-27
    # outage. The podcast generator already does this; this one did not, and
    # the first English video landed 0600 and had to be fixed by hand.
    out_path.chmod(0o644)
    return True


async def main():
    VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
    mapping = _load(MAP_FILE, [])
    state = _load(STATE_FILE, {})  # path_id -> task_id (in flight)
    fails = _load(FAILS_FILE, {})  # path_id -> consecutive hard-failure count

    # Sync manifest with whatever valid videos already exist on disk.
    if _sync_manifest_from_disk(mapping):
        print("[startup] manifest synced from disk")

    # 1) resolve in-flight tasks
    for _state_key, task_id in list(state.items()):
        path_id = _unkey(_state_key)
        if _is_done(path_id):
            print(f"[poll] {path_id}: already done on disk — dropping stale in-flight task")
            state.pop(_key(path_id), None)
            fails.pop(_key(path_id), None)
            continue
        st = await poll(task_id)
        print(f"[poll] {path_id}: {st}")
        if st == "completed":
            if await download(task_id, _vid_path(path_id)):
                print(f"  ✓ downloaded {path_id}")
                source_id = next((t["source_id"] for t in mapping if t["path_id"] == path_id), None)
                _register_done(path_id, task_id=task_id, source_id=source_id)
                state.pop(_key(path_id), None)
                fails.pop(_key(path_id), None)
        elif st == "failed":
            state.pop(_key(path_id), None)  # genuine failure — allow re-trigger unless now done
            if not _is_done(path_id):
                fails[_key(path_id)] = fails.get(_key(path_id), 0) + 1
        # "error"/auth-expiry: keep the task and retry next run (do NOT drop)

    # 2) trigger paths that have no video and no in-flight task
    for t in mapping:
        path_id = t["path_id"]
        source_id = t["source_id"]
        if _is_done(path_id):
            continue
        if _key(path_id) in state:
            continue
        if fails.get(_key(path_id), 0) >= MAX_FAILS:
            print(f"[trigger] {path_id}: skipped — {fails[_key(path_id)]} hard failures; needs manual root-cause before retry")
            continue
        tid = await trigger(source_id, t["title"], path_id)
        if tid == "RATELIMIT":
            print(f"[trigger] {path_id}: rate-limited — will retry next run")
            break  # quota likely exhausted; stop triggering this run
        if tid == "DRYRUN":
            continue
        if tid:
            print(f"[trigger] {path_id}: task {tid}")
            state[_key(path_id)] = tid
            await asyncio.sleep(5)
        else:
            print(f"[trigger] {path_id}: no task id")

    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    # 3) bounded poll of freshly-triggered tasks (download any that finish fast)
    deadline = time.time() + POLL_BUDGET_SEC
    while state and time.time() < deadline:
        await asyncio.sleep(45)
        for _state_key, task_id in list(state.items()):
            path_id = _unkey(_state_key)
            st = await poll(task_id)
            if st == "completed" and await download(task_id, _vid_path(path_id)):
                print(f"  ✓ downloaded {path_id}")
                source_id = next((t["source_id"] for t in mapping if t["path_id"] == path_id), None)
                _register_done(path_id, task_id=task_id, source_id=source_id)
                state.pop(_key(path_id), None)
                fails.pop(_key(path_id), None)
            elif st == "failed":
                state.pop(_key(path_id), None)
                if _is_done(path_id):
                    print(f"  ✓ {path_id} already done on disk — ignoring stale failure")
                    fails.pop(_key(path_id), None)
                else:
                    print(f"  ✗ {path_id} permanently failed")
                    fails[_key(path_id)] = fails.get(_key(path_id), 0) + 1
            # "pending", "error" (auth expiry / transient): keep in state, retry next run
        STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    FAILS_FILE.write_text(json.dumps(fails, ensure_ascii=False, indent=2), encoding="utf-8")
    done = sum(1 for t in mapping if _is_done(t["path_id"]))
    benched = sum(1 for t in mapping if fails.get(_key(t["path_id"]), 0) >= MAX_FAILS and not _is_done(t["path_id"]))
    print(f"\n[summary] videos done: {done}/{len(mapping)} | in-flight: {len(state)} | benched (>= {MAX_FAILS} fails): {benched}")


if __name__ == "__main__":
    asyncio.run(main())
