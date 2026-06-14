#!/usr/bin/env python3
"""Regenerate REAL NotebookLM audio for lessons whose local docs/ file is an
edge-tts placeholder, then download + place it at the correct path.

Generalises generate_arabic_podcasts.py: works for ALL age bands, derives the
output filename directly from lesson_id (no hardcoded "0-3"), and only touches
lessons whose current file is < 2MB (placeholder/broken). Real episodes are
skipped so re-runs are safe.

Source map: lesson_id -> NotebookLM source_id, read from --map (default
/tmp/regen_map.json, built by the cross-reference step).

Usage:
    python scripts/regen_podcasts.py --dry-run        # show what would run
    python scripts/regen_podcasts.py                  # generate + download
    python scripts/regen_podcasts.py --only lesson_2-3_islamic_attachment_b01
"""
import argparse
import asyncio
import json
import os
import re

CLI = "./notebooklm_env/bin/notebooklm"
INDEX_PATH = "docs/lesson_index.json"
REAL_MIN = 2 * 1024 * 1024  # >=2MB == already a real episode


async def run(cmd):
    p = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    out, err = await p.communicate()
    return p.returncode, out.decode(), err.decode()


async def trigger(source_id):
    code, out, err = await run([CLI, "generate", "audio", "--language", "ar_001", "-s", source_id])
    if code != 0:
        print(f"   trigger rc={code}: {err.strip()[:200]}")
    m = re.search(r"(?:Task|Started):\s*([a-fA-F0-9\-]+)", out + err)
    return m.group(1) if m else None


async def poll(task_id):
    code, out, err = await run([CLI, "artifact", "poll", task_id, "--json"])
    if code == 0:
        try:
            d = json.loads(out)
            return d.get("status"), d.get("error")
        except Exception as e:
            return "error", str(e)
    return "error", err.strip()


async def download(task_id, path):
    code, out, err = await run([CLI, "download", "audio", "--artifact", task_id, path, "--force"])
    ok = code == 0 and os.path.exists(path) and os.path.getsize(path) > REAL_MIN
    if not ok:
        print(f"   download failed: {err.strip()[:200]}")
    return ok


def load_index():
    with open(INDEX_PATH) as f:
        data = json.load(f)
    return data, {l["lesson_id"]: l for l in data["lessons"]}


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--map", default="/tmp/regen_map.json")
    ap.add_argument("--only", default="")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    src_map = json.load(open(args.map))
    if args.only:
        src_map = {k: v for k, v in src_map.items() if k == args.only}

    # only the ones still needing a real episode
    todo = {}
    for lid, sid in src_map.items():
        path = f"docs/{lid}_podcast.mp3"
        if os.path.exists(path) and os.path.getsize(path) >= REAL_MIN:
            print(f"skip (already real): {lid}")
            continue
        todo[lid] = sid

    print(f"\n{len(todo)} lesson(s) to regenerate.")
    if args.dry_run:
        for lid, sid in todo.items():
            print(f"  would generate {lid}  <- source {sid}")
        return

    data, by_id = load_index()
    active = []
    for i, (lid, sid) in enumerate(todo.items(), 1):
        print(f"\n[{i}/{len(todo)}] trigger {lid} (source {sid})")
        tid = await trigger(sid)
        if tid:
            print(f"   task {tid}")
            active.append((lid, tid, f"docs/{lid}_podcast.mp3"))
            await asyncio.sleep(4)
        else:
            print("   FAILED to trigger")

    print(f"\nPolling {len(active)} tasks...")
    while active:
        still = []
        for lid, tid, path in active:
            status, err = await poll(tid)
            print(f"  {lid}: {status}")
            if status == "completed":
                if await download(tid, path):
                    sz = os.path.getsize(path)
                    by_id.setdefault(lid, {}).setdefault("assets", {})["podcasts"] = [
                        {"file": path, "size_bytes": sz, "language": "ar"}]
                    json.dump(data, open(INDEX_PATH, "w"), ensure_ascii=False, indent=2)
                    print(f"   ✓ saved {sz // 1024}KB + index updated")
                else:
                    still.append((lid, tid, path))
            elif status in ("failed", "error"):
                print(f"   ✗ {err}")
            else:
                still.append((lid, tid, path))
        active = still
        if active:
            await asyncio.sleep(20)
    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())
