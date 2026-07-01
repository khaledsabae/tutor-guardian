#!/usr/bin/env python3
"""
Idempotent podcast generator for tutor-guardian.

Reads production_registry.md to find sources that need podcasts.
Checks audio_registry.json to avoid duplicate generation.
Downloads existing artifact if available, otherwise generates new audio.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

REPO = Path("/home/khalednew/projects/tutor-guardian")
REGISTRY_PATH = REPO / "docs" / "production_registry.md"
AUDIO_REGISTRY_PATH = REPO / "docs" / "audio_registry.json"
NOTEBOOK_ID = "94f191e6-cfbc-4655-a0d7-c8f7ad0f2287"


def load_audio_registry():
    if AUDIO_REGISTRY_PATH.exists():
        with open(AUDIO_REGISTRY_PATH) as f:
            return json.load(f)
    return {"notebook_id": NOTEBOOK_ID, "last_updated": "", "sources": {}}


def save_audio_registry(reg):
    reg["last_updated"] = datetime.now().isoformat()
    with open(AUDIO_REGISTRY_PATH, "w") as f:
        json.dump(reg, f, ensure_ascii=False, indent=2)


def run_notebooklm(args: list[str], timeout: int = 600) -> dict:
    env = os.environ.copy()
    env["HOME"] = "/home/khalednew"
    cmd = [str(REPO / "notebooklm_env" / "bin" / "notebooklm")] + args + ["--json"]
    result = subprocess.run(
        cmd, cwd=REPO, capture_output=True, text=True, env=env, timeout=timeout
    )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"error": True, "stdout": result.stdout, "stderr": result.stderr}


def extract_lesson_id(text: str) -> str | None:
    match = re.search(r"lesson_(\d+-\d+_[\w_]+?)(?:\s*$|\s*\|)", text)
    if match:
        return "lesson_" + match.group(1)
    return None


def parse_registry():
    with open(REGISTRY_PATH) as f:
        content = f.read()
    rows = [r for r in content.split("\n") if "| age_" in r or "| demo" in r.lower()]

    sources = {}  # sid -> list of lesson_ids
    for row in rows:
        cols = [c.strip() for c in row.split("|")]
        if len(cols) < 6:
            continue
        lesson_full = cols[1]
        lesson_id = extract_lesson_id(lesson_full)
        if not lesson_id:
            continue
        source_match = re.search(r"`([a-f0-9-]{36})`", row)
        if not source_match:
            continue
        sid = source_match.group(1)
        exact = REPO / "docs" / f"{lesson_id}_podcast.mp3"
        base = lesson_id.rsplit("_", 1)[0]
        variant = REPO / "docs" / f"{base}_b04_podcast.mp3"
        if not exact.exists() and not variant.exists():
            sources.setdefault(sid, []).append(lesson_id)
    return sources


def generate_audio(sid: str) -> dict | None:
    print(f"Generating audio for source {sid}...")
    result = run_notebooklm([
        "generate", "audio",
        "-n", NOTEBOOK_ID,
        "-s", sid,
        "--prompt-file", "prompts/audio_prompt.txt",
        "--language", "ar_eg",
        "--wait",
    ], timeout=600)

    if result.get("status") == "completed":
        print(f"  Generated: {result.get('url', 'N/A')[:60]}...")
        return result

    print(f"  Generation failed: {result}")
    return None


def get_latest_artifact_for_source(sid: str) -> dict | None:
    """Find the most recent audio artifact that was generated from this source.
    We use the generation task_id as the artifact_id."""
    result = run_notebooklm(["artifact", "list", "-n", NOTEBOOK_ID], timeout=60)
    artifacts = result.get("artifacts", [])
    audio = [a for a in artifacts if a.get("type_id") == "audio"]

    # Get generation output to find task_id
    gen_file = Path(f"/tmp/gen_{sid}.json")
    if gen_file.exists():
        with open(gen_file) as f:
            gen = json.load(f)
        task_id = gen.get("task_id")
        if task_id:
            for a in audio:
                if a.get("id") == task_id:
                    return a

    # Fallback: newest artifact
    if audio:
        return audio[0]
    return None


def download_artifact(artifact_id: str, sid: str) -> Path | None:
    dest = REPO / "docs" / f"source_{sid}_podcast.mp3"
    print(f"Downloading artifact {artifact_id} to {dest.name}...")
    result = run_notebooklm([
        "download", "audio",
        "-n", NOTEBOOK_ID,
        "--artifact", artifact_id,
        "--force",
        str(dest),
    ], timeout=120)

    if result.get("status") == "downloaded" or dest.exists():
        return dest
    print(f"  Download failed: {result}")
    return None


def copy_to_lessons(source_file: Path, lesson_ids: list[str]):
    for lesson_id in lesson_ids:
        dest = REPO / "docs" / f"{lesson_id}_podcast.mp3"
        shutil.copy2(source_file, dest)
        print(f"  Copied to {dest.name}")


def process_source(sid: str, lesson_ids: list[str], audio_reg: dict) -> bool:
    if sid in audio_reg["sources"]:
        entry = audio_reg["sources"][sid]
        artifact_id = entry.get("artifact_id")
        if not artifact_id:
            print(f"Source {sid} registered but missing artifact_id. Regenerating...")
        else:
            print(f"Source {sid} already registered with artifact {artifact_id}. Downloading...")
            source_file = download_artifact(artifact_id, sid)
            if source_file:
                copy_to_lessons(source_file, lesson_ids)
                entry["lessons"] = [{"lesson_id": lid, "file": f"docs/{lid}_podcast.mp3"} for lid in lesson_ids]
                return True
            print("Download failed, trying to regenerate...")

    # Generate new audio
    gen_result = generate_audio(sid)
    if not gen_result:
        return False

    # Determine artifact
    artifact = get_latest_artifact_for_source(sid)
    if not artifact:
        print("Could not find artifact for generated audio.")
        return False

    artifact_id = artifact.get("id")
    if not artifact_id:
        print("Artifact has no id.")
        return False

    title = artifact.get("title", "")
    created_at = artifact.get("created_at", "")

    # Download the specific artifact
    source_file = download_artifact(artifact_id, sid)
    if not source_file:
        return False

    copy_to_lessons(source_file, lesson_ids)

    # Update audio registry
    audio_reg["sources"][sid] = {
        "artifact_id": artifact_id,
        "title": title,
        "created_at": created_at,
        "downloaded": True,
        "file": f"docs/source_{sid}_podcast.mp3",
        "lessons": [{"lesson_id": lid, "file": f"docs/{lid}_podcast.mp3"} for lid in lesson_ids],
    }
    return True


def main():
    parser = argparse.ArgumentParser(description="Idempotent podcast generator")
    parser.add_argument("--source", help="Generate only this source ID")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    args = parser.parse_args()

    audio_reg = load_audio_registry()
    pending_sources = parse_registry()

    if not pending_sources:
        print("No pending podcasts.")
        return 0

    print(f"Found {len(pending_sources)} sources needing podcasts.")
    for sid, lesson_ids in pending_sources.items():
        print(f"  {sid}: {len(lesson_ids)} lessons")

    if args.dry_run:
        return 0

    if args.source:
        if args.source not in pending_sources:
            print(f"Source {args.source} does not need a podcast or is not in registry.")
            return 1
        sources_to_process = {args.source: pending_sources[args.source]}
    else:
        sources_to_process = pending_sources

    success = 0
    failed = 0
    for sid, lesson_ids in sources_to_process.items():
        print(f"\n{'='*60}")
        print(f"Processing source: {sid}")
        print(f"{'='*60}")
        if process_source(sid, lesson_ids, audio_reg):
            save_audio_registry(audio_reg)
            success += 1
        else:
            failed += 1
            print("Stopping due to failure.")
            break

    print(f"\nDone. Success: {success}, Failed: {failed}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
