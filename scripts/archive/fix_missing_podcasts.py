#!/usr/bin/env python3
import json, glob, os, re, subprocess, sys, time
from pathlib import Path

ROOT = Path("/home/khalednew/projects/tutor-guardian")
NOTEBOOK_ID = "94f191e6-cfbc-4655-a0d7-c8f7ad0f2287"
CLI = ROOT / "notebooklm_env/bin/notebooklm"
AUDIO_PROMPT = ROOT / "scripts/prompts/audio_prompt.txt"

source_map = json.load(open(ROOT / "scripts/podcast_source_map.json"))

with open(ROOT / "docs/lesson_index.json") as f:
    idx = json.load(f)
lessons = {l["lesson_id"]: l for l in idx["lessons"]}

existing_podcasts = set()
for p in glob.glob(str(ROOT / "docs/lesson_*_podcast.mp3")):
    m = re.search(r'lesson_(.+?)_podcast\.mp3$', os.path.basename(p))
    if m:
        existing_podcasts.add("lesson_" + m.group(1))

# broader filename catch
for p in glob.glob(str(ROOT / "docs/lesson_*_podcast*.mp3")):
    m = re.search(r'lesson_(.+?)_podcast', os.path.basename(p))
    if m:
        existing_podcasts.add("lesson_" + m.group(1))

missing = sorted(set(lessons.keys()) - existing_podcasts)
print(f"Missing podcasts: {len(missing)}")

# match source IDs: try direct keys + fuzzy matching
plan = []
for lid in missing:
    src = None
    # direct
    if lid in source_map:
        src = source_map[lid]
    else:
        base = re.sub(r'(_\d+)$', '', lid)
        candidates = [k for k in source_map if base in k or k in lid]
        if candidates:
            src = source_map[candidates[0]]
    title = lessons[lid].get("title", lid)
    plan.append((lid, src, title))

mapped = [(l,s,t) for l,s,t in plan if s]
needs_manual = [(l,s,t) for l,s,t in plan if not s]
print(f"Mapped to source: {len(mapped)}")
print(f"Need manual lookup: {len(needs_manual)}")

for l,s,t in needs_manual[:10]:
    print(f"  MISSING SRC: {l} -> {t[:60]}")

if not mapped:
    print("Nothing to generate.")
    sys.exit(0)

print("\nFirst 5 mapped examples:")
for l,s,t in mapped[:5]:
    print(f"  {l[:50]} -> {s} | {t[:50]}")
