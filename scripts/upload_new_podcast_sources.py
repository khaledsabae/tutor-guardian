#!/usr/bin/env python3
"""Efficient one-shot upload of the 48 new lesson md sources to NotebookLM.

Unlike add_new_lesson_podcasts.py this lists sources ONCE up front and ONCE at
the end (instead of re-listing after every upload — which was O(n^2) and timed
out). Writes source_to_lesson.json so the generators can map source->lesson.
"""
import glob
import json
import os
import subprocess

BASE = "/home/khalednew/projects/tutor-guardian"
CLI = f"{BASE}/notebooklm_env/bin/notebooklm"
NB = "94f191e6-cfbc-4655-a0d7-c8f7ad0f2287"
ENV = {**os.environ, "HOME": "/home/khalednew"}
NEW_PATHS = {"16-18_islamic_parenting_adult_faith", "16-18_development_adult_readiness",
 "4-6_cyber_early_screens", "4-6_medical_healthy_growth", "2-3_medical_early_wellbeing",
 "7-9_cyber_digital_basics", "10-12_development_pre_teen", "0-3_islamic_parenting_fitrah",
 "2-3_islamic_first_words", "7-9_islamic_parenting_akhlaq", "10-12_islamic_parenting_worship_love",
 "13-15_islamic_parenting_steadfast"}
os.chdir(BASE)


def sh(*c, t=180):
    return subprocess.run(list(c), capture_output=True, text=True, env=ENV, timeout=t)


def list_titles():
    r = sh(CLI, "source", "list", "-n", NB, "--json", t=120)
    return {s["title"]: s["id"] for s in json.loads(r.stdout).get("sources", [])}


def lesson_meta(lid):
    d = json.load(open(f"knowledge_base/curriculum/lessons/{lid}.json"))
    age = d["age_group"]
    return age, d["path_id"].replace(f"path_{age}_", "", 1)


def main():
    have = list_titles()
    srcs = []
    for f in sorted(glob.glob("knowledge_base/notebooklm/age_*/lesson_*.md")):
        lid = os.path.basename(f)[:-3]
        if not any(p in lid for p in NEW_PATHS):
            continue
        srcs.append((lid, f))
    print(f"{len(srcs)} new lesson sources to ensure uploaded.")
    for i, (lid, f) in enumerate(srcs, 1):
        if lid in have:
            print(f"[{i}/{len(srcs)}] skip (exists) {lid}")
            continue
        r = sh(CLI, "source", "add", f, "-n", NB, "--type", "file", "--title", lid)
        print(f"[{i}/{len(srcs)}] {'up' if r.returncode == 0 else 'FAIL'} {lid}")
    have = list_titles()
    smap = json.loads(open("source_to_lesson.json").read()) if os.path.exists("source_to_lesson.json") else {}
    n = 0
    for lid, _ in srcs:
        sid = have.get(lid)
        if sid:
            age, topic = lesson_meta(lid)
            smap[sid] = [age, topic, lid]
            n += 1
    open("source_to_lesson.json", "w").write(json.dumps(smap, ensure_ascii=False, indent=2))
    print(f"\nmapped {n}/{len(srcs)} new lesson sources -> source_to_lesson.json")


if __name__ == "__main__":
    main()
