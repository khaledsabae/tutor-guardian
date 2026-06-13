#!/usr/bin/env python3
"""One-shot: register the 25 newly-authored lessons in the podcast pipeline.

Uploads ONLY the new lesson markdown sources (knowledge_base/notebooklm/**/
lesson_*_bNN.md) to NotebookLM, then wires the source<->lesson mapping so the
existing generators (scripts/generate_all_podcasts.py) can produce audio for
them — without touching/duplicating the original 63 sources.

Each source is uploaded with --title = the full lesson id, so matching back to
the lesson is exact. Writes:
  - source_to_lesson.json   (source_id -> [age, topic_path, lesson_id])
  - docs/lesson_index.json  (new lesson entries so the backend links assets)
  - /tmp/lesson_source_map.json  (targets consumed by the generators)

Run:  python scripts/add_new_lesson_podcasts.py [--dry-run]
Then: python scripts/generate_all_podcasts.py   (generates + downloads audio)

NOTE: this performs real uploads to the user's NotebookLM account (rate-limited).
Don't run it concurrently with another podcast pipeline run on the same notebook.
"""
import argparse
import asyncio
import json
import pathlib

BASE = pathlib.Path(__file__).resolve().parent.parent
NB_DIR = BASE / "knowledge_base" / "notebooklm"
LESSONS_DIR = BASE / "knowledge_base" / "curriculum" / "lessons"
CLI = str(BASE / "notebooklm_env" / "bin" / "notebooklm")
NOTEBOOK = "94f191e6-cfbc-4655-a0d7-c8f7ad0f2287"
SRC_MAP_FILE = BASE / "source_to_lesson.json"
INDEX_FILE = BASE / "docs" / "lesson_index.json"
TMP_MAP = pathlib.Path("/tmp/lesson_source_map.json")


def new_md_files():
    out = []
    for f in sorted(NB_DIR.glob("**/*.md")):
        stem = f.stem
        if stem.rsplit("_", 1)[-1].startswith("b") and "_b" in stem:
            out.append(f)
    return out


def lesson_meta(lesson_id):
    lf = LESSONS_DIR / f"{lesson_id}.json"
    d = json.loads(lf.read_text(encoding="utf-8"))
    age = d["age_group"]
    topic = d["path_id"].replace(f"path_{age}_", "", 1)
    return age, topic


async def run(*args):
    proc = await asyncio.create_subprocess_exec(
        *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    out, err = await proc.communicate()
    return proc.returncode, out.decode(), err.decode()


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    files = new_md_files()
    print(f"Found {len(files)} new lesson md sources to register.")
    if args.dry_run:
        for f in files:
            print("  would upload:", f.stem)
        return

    # 1) Upload each new md with title = lesson_id (exact match later).
    for i, f in enumerate(files, 1):
        lesson_id = f.stem
        print(f"[{i}/{len(files)}] uploading {lesson_id} ...")
        code, out, err = await run(
            CLI, "source", "add", str(f), "-n", NOTEBOOK,
            "--type", "file", "--title", lesson_id)
        if code != 0:
            print(f"   upload failed: {err.strip()[:160]}")
        await asyncio.sleep(2)

    # 2) List sources -> title->id for our lessons.
    code, out, _ = await run(CLI, "source", "list", "-n", NOTEBOOK, "--json")
    sources = json.loads(out).get("sources", []) if code == 0 else []
    title_to_id = {s["title"]: s["id"] for s in sources}

    # 3) Merge mappings.
    src_map = json.loads(SRC_MAP_FILE.read_text(encoding="utf-8")) \
        if SRC_MAP_FILE.exists() else {}
    index = json.loads(INDEX_FILE.read_text(encoding="utf-8"))
    indexed = {l["lesson_id"] for l in index.get("lessons", [])}
    tmp_targets = []
    added = 0
    for f in files:
        lesson_id = f.stem
        sid = title_to_id.get(lesson_id)
        if not sid:
            print(f"   !! no source id found for {lesson_id} (upload may have failed)")
            continue
        age, topic = lesson_meta(lesson_id)
        src_map[sid] = [age, topic, lesson_id]
        tmp_targets.append({"source_id": sid, "topic_path": topic,
                            "lesson_id": lesson_id, "age_group": age})
        if lesson_id not in indexed:
            index["lessons"].append({"lesson_id": lesson_id, "age_group": age,
                                     "topic_path": topic, "assets": {}})
            added += 1

    SRC_MAP_FILE.write_text(json.dumps(src_map, ensure_ascii=False, indent=2),
                            encoding="utf-8")
    INDEX_FILE.write_text(json.dumps(index, ensure_ascii=False, indent=2),
                          encoding="utf-8")
    TMP_MAP.write_text(json.dumps(tmp_targets, ensure_ascii=False, indent=2),
                       encoding="utf-8")
    print(f"\nMapped {len(tmp_targets)} sources; added {added} to lesson_index.")
    print("Next: python scripts/generate_all_podcasts.py")


if __name__ == "__main__":
    asyncio.run(main())
