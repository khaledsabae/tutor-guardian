#!/usr/bin/env python3
"""Generate the NotebookLM episode for every lesson whose index entry has none.

Reads docs/lesson_index.json, finds lessons with an empty `podcasts` list, maps
each to its uploaded NotebookLM source id (--map), generates Arabic audio with
the house prompt (scripts/podcast_prompt.txt), downloads it to
docs/<lesson_id>_podcast.mp3, and links it back into the index.

A real episode is 18-46 MB. Anything under MIN_BYTES is the short 48kbps clip
that the 2026-08 audit classified BAD and purged, so a small file is refused
rather than linked — an index that promises audio nobody can listen to is worse
than an index that admits the gap.

    python scripts/generate_missing_podcasts.py --map /tmp/podcast_map.json
    python scripts/generate_missing_podcasts.py --map ... --only lesson_x
"""
import argparse
import json
import re
import subprocess
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
CLI = str(BASE / "notebooklm_env" / "bin" / "notebooklm")
INDEX = BASE / "docs" / "lesson_index.json"
DOCS = BASE / "docs"
PROMPT = (BASE / "scripts" / "podcast_prompt.txt").read_text(encoding="utf-8")
LANG = "ar_001"
MIN_BYTES = 2 * 1024 * 1024
UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


def run(args, timeout=300):
    r = subprocess.run([CLI, *args], capture_output=True, text=True, timeout=timeout)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def generate(notebook, source_id):
    """Trigger one episode; returns the artifact id."""
    rc, out = run(["generate", "audio", PROMPT, "-n", notebook, "-s", source_id,
                   "--language", LANG, "--no-wait"], timeout=300)
    ids = [u for u in UUID.findall(out) if u != source_id and u != notebook]
    if not ids:
        raise RuntimeError(f"no artifact id in output (rc={rc}): {out[:300]}")
    return ids[0]


def wait_ready(notebook, artifact_id, timeout=1800, interval=20):
    deadline = time.time() + timeout
    while time.time() < deadline:
        rc, out = run(["artifact", "poll", artifact_id, "-n", notebook, "--json"],
                      timeout=120)
        try:
            status = (json.loads(out) or {}).get("status", "")
        except json.JSONDecodeError:
            status = out.strip()[:60]
        if str(status).lower() in {"ready", "completed", "complete", "success"}:
            return True
        if str(status).lower() in {"failed", "error"}:
            raise RuntimeError(f"generation failed: {out[:200]}")
        time.sleep(interval)
    raise TimeoutError(f"artifact {artifact_id} not ready after {timeout}s")


def download(notebook, artifact_id, lesson_id):
    out_path = DOCS / f"{lesson_id}_podcast.mp3"
    rc, out = run(["download", "audio", str(out_path), "-n", notebook,
                   "--artifact", artifact_id, "--force"], timeout=900)
    size = out_path.stat().st_size if out_path.exists() else 0
    if size < MIN_BYTES:
        raise RuntimeError(
            f"downloaded {size} bytes (< {MIN_BYTES}) — refusing to link a clip; "
            f"cli said: {out[:200]}")
    return out_path, size


def link(lesson_id, filename, source_id, size):
    data = json.loads(INDEX.read_text(encoding="utf-8"))
    for lesson in data["lessons"]:
        if lesson.get("lesson_id") != lesson_id:
            continue
        lesson.setdefault("assets", {})["podcasts"] = [{
            "id": f"{lesson_id}_podcast",
            "file": f"docs/{filename}",
            "language": "ar",
            "size_bytes": size,
        }]
        lesson.setdefault("source_id", source_id)
        break
    INDEX.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                     encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--map", required=True, help="JSON: {lesson_id: source_id}")
    ap.add_argument("--notebook", required=True)
    ap.add_argument("--only")
    args = ap.parse_args()

    mapping = json.loads(Path(args.map).read_text(encoding="utf-8"))
    lessons = json.loads(INDEX.read_text(encoding="utf-8"))["lessons"]
    todo = [l["lesson_id"] for l in lessons
            if not (l.get("assets") or {}).get("podcasts")
            and l["lesson_id"] in mapping
            and (not args.only or l["lesson_id"] == args.only)]

    print(f"{len(todo)} lesson(s) to generate", flush=True)
    for i, lid in enumerate(todo, 1):
        src = mapping[lid]
        print(f"[{i}/{len(todo)}] {lid} (source {src[:8]})", flush=True)
        try:
            art = generate(args.notebook, src)
            print(f"    artifact {art} — waiting", flush=True)
            wait_ready(args.notebook, art)
            path, size = download(args.notebook, art, lid)
            link(lid, path.name, src, size)
            print(f"    ✅ {path.name} — {size // (1024 * 1024)} MB, linked", flush=True)
        except Exception as e:  # keep going: one bad episode must not stop the rest
            print(f"    ❌ {type(e).__name__}: {e}", flush=True)


if __name__ == "__main__":
    main()
