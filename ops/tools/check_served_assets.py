#!/usr/bin/env python3
"""Verify that what lesson_index.json promises is what this host can serve.

Two production incidents motivate this, both invisible until a human noticed:

  * One byte-identical MP3 was listed under three lessons across two age groups
    and two domains, so children heard a lesson about someone else's topic.
  * The 0-3 -> prenatal-1 age-band migration rewrote video filenames from the
    age_group + topic_path pair instead of the lesson's curriculum path_id,
    naming 7 files nobody had generated. 18 lessons served those paths and the
    API passed them straight through to the app.

Media is gitignored and reaches production by rsync, so neither problem is
visible to any check that only reads the repo. This has to run where the files
actually are: the VPS deploy path, after the checkout, before the container is
recreated.

Path videos are deliberately shared by every lesson on the same path, so only
podcasts are checked for byte-collisions.

Exit codes: 0 clean (or nothing to check), 1 problems found. --warn-only always
exits 0 while still printing everything, for a grace period after rollout.
"""
import argparse
import hashlib
import json
import os
import sys
from collections import defaultdict

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# The API derives a file's language the same way. Importing rather than
# re-deriving is the point: the two disagreeing is the defect this check exists
# to catch, so it must not carry its own second opinion.
sys.path.insert(0, os.path.join(REPO_ROOT, "backend"))
from app.media_naming import language_of_filename  # noqa: E402


def _md5(path, chunk=1 << 20):
    h = hashlib.md5()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def _references(lessons):
    """Yield (lesson_id, kind, relative_path) for every media reference."""
    for lesson in lessons:
        lid = lesson.get("lesson_id")
        assets = lesson.get("assets") or {}
        for kind in ("podcasts", "videos"):
            for entry in assets.get(kind) or []:
                ref = entry.get("file")
                if ref:
                    yield lid, kind, ref


def _language_claims(lessons):
    """Yield (lesson_id, kind, relative_path, declared_language)."""
    for lesson in lessons:
        lid = lesson.get("lesson_id")
        assets = lesson.get("assets") or {}
        for kind in ("podcasts", "videos"):
            for entry in assets.get(kind) or []:
                if entry.get("file"):
                    yield (lid, kind, entry["file"],
                           (entry.get("language") or "").strip().lower())


def _base_lang(code):
    """'ar_eg' → 'ar', 'en-US' → 'en'.

    Podcast entries declare `ar` and video entries declare `ar_eg`; both mean
    Arabic. Comparing the raw strings flags all 102 video entries as defects,
    which on a blocking deploy gate would stop every deploy over a naming
    convention that was never wrong.
    """
    return (code or "").strip().lower().replace("-", "_").split("_")[0]


def find_language_mismatches(claims):
    """Entries whose declared `language` disagrees with their filename tag.

    This is the check that would have caught `docs/lesson_01_podcast.mp3` —
    37.8 MB of Arabic with no language key, which the loader's old heuristic
    read as English and served to English users. The index and the filename are
    two sources of truth for the same fact; nothing compared them.
    """
    out = []
    for lid, kind, ref, declared in claims:
        from_name = language_of_filename(ref)
        if not declared:
            out.append((lid, kind, ref, "(none)", from_name))
        elif _base_lang(declared) != _base_lang(from_name):
            out.append((lid, kind, ref, declared, from_name))
    return out


def find_duplicate_languages(lessons):
    """A lesson claiming the same language twice for one kind.

    A writer that appended where it should have replaced. The reverse mistake —
    `assets["podcasts"] = [...]`, which regen_podcasts.py does — silently drops
    the other language instead, and shows up as a coverage gap rather than here.
    """
    out = []
    for lesson in lessons:
        lid = lesson.get("lesson_id")
        assets = lesson.get("assets") or {}
        for kind in ("podcasts", "videos"):
            seen = defaultdict(list)
            for entry in assets.get(kind) or []:
                if entry.get("file"):
                    seen[language_of_filename(entry["file"])].append(entry["file"])
            for lang, files in seen.items():
                if len(files) > 1:
                    out.append((lid, kind, lang, sorted(files)))
    return out


def find_missing(root, refs):
    by_file = defaultdict(list)
    for lid, _kind, ref in refs:
        if not os.path.exists(os.path.join(root, ref)):
            by_file[ref].append(lid)
    return by_file


def find_podcast_collisions(root, refs):
    """Podcasts that are byte-identical but belong to different lessons.

    Files are grouped by size first — different sizes cannot collide — so a
    clean run hashes almost nothing even though the corpus is several GB.
    """
    owners = defaultdict(set)
    for lid, kind, ref in refs:
        if kind == "podcasts":
            owners[ref].add(lid)

    by_size = defaultdict(list)
    for ref in owners:
        path = os.path.join(root, ref)
        if os.path.exists(path):
            by_size[os.path.getsize(path)].append(ref)

    collisions = []
    for refs_same_size in by_size.values():
        if len(refs_same_size) < 2:
            continue
        by_hash = defaultdict(list)
        for ref in refs_same_size:
            by_hash[_md5(os.path.join(root, ref))].append(ref)
        for digest, group in by_hash.items():
            lessons = set()
            for ref in group:
                lessons |= owners[ref]
            if len(lessons) > 1:
                collisions.append((digest, sorted(group), sorted(lessons)))
    return collisions


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=REPO_ROOT, help="repo root holding docs/")
    parser.add_argument(
        "--warn-only", action="store_true", help="report problems but exit 0"
    )
    args = parser.parse_args()

    index_path = os.path.join(args.root, "docs", "lesson_index.json")
    if not os.path.exists(index_path):
        print(f"SKIP: no lesson index at {index_path}")
        return 0

    lessons = json.load(open(index_path, encoding="utf-8"))["lessons"]
    refs = list(_references(lessons))

    present = sum(1 for _l, _k, r in refs if os.path.exists(os.path.join(args.root, r)))

    print("=" * 68)
    print("  SERVED ASSETS CHECK — فحص الملفات التي يقدّمها الخادم فعليًا")
    print("=" * 68)
    print(f"  root: {args.root}")
    print(f"  references: {len(refs)}  present: {present}")

    problems = 0

    # ── Index-only checks ──
    # These run on every host, including one whose media was stripped by
    # .dockerignore — a mislabelled entry is a data defect, and the container
    # that would serve it is exactly the host that cannot see the file.
    mismatches = find_language_mismatches(_language_claims(lessons))
    if mismatches:
        problems += len(mismatches)
        print(f"\n  ❌ DECLARED LANGUAGE ≠ FILENAME — {len(mismatches)} entry(ies)")
        for lid, kind, ref, declared, from_name in mismatches:
            print(f"     {lid} · {kind} · declared={declared} filename={from_name}")
            print(f"        {ref}")
    else:
        print("\n  ✅ every entry's language matches its filename")

    dupes = find_duplicate_languages(lessons)
    if dupes:
        problems += len(dupes)
        print(f"  ❌ SAME LANGUAGE CLAIMED TWICE — {len(dupes)} case(s)")
        for lid, kind, lang, files in dupes:
            print(f"     {lid} · {kind} · {lang}: {', '.join(files)}")
    else:
        print("  ✅ no lesson claims one language twice")

    # ── On-disk checks ──
    if present == 0:
        # A container image built with .dockerignore stripping media, or a bare
        # clone. The remaining invariants need the files themselves.
        print("\n  ⏭  no media present — skipping on-disk checks")
        print()
        if problems and not args.warn_only:
            print(f"  ❌ {problems} problem(s) — blocking")
            return 1
        if problems:
            print(f"  🟡 {problems} problem(s) — warn-only, not blocking")
        return 0

    missing = find_missing(args.root, refs)
    if missing:
        problems += len(missing)
        print(f"\n  ❌ REFERENCED BUT MISSING — {len(missing)} file(s)")
        for ref, lids in sorted(missing.items()):
            print(f"     {ref}")
            print(f"        ← {len(lids)} lesson(s): {', '.join(lids)}")
    else:
        print("\n  ✅ every referenced file is on this host")

    collisions = find_podcast_collisions(args.root, refs)
    if collisions:
        problems += len(collisions)
        print(f"\n  ❌ ONE PODCAST SERVED TO SEVERAL LESSONS — {len(collisions)} group(s)")
        for digest, group, lessons_hit in collisions:
            print(f"     md5 {digest[:12]} → {', '.join(lessons_hit)}")
            for ref in group:
                print(f"        {ref}")
    else:
        print("  ✅ no podcast is shared between lessons")

    print()
    if problems and not args.warn_only:
        print(f"  ❌ {problems} problem(s) — blocking")
        return 1
    if problems:
        print(f"  🟡 {problems} problem(s) — warn-only, not blocking")
        return 0
    print("  ✅ SERVED ASSETS OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
