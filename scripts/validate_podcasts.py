#!/usr/bin/env python3
"""Guard against placeholder/broken lesson podcasts.

Real NotebookLM podcasts are multi-minute (>= ~3 min, several MB). The old
edge-tts fallback (gen_tts_podcasts.py) produced 48kbps, 40-120s summary clips
that silently filled gaps for 4 age bands. This validator flags every podcast
that is too short / too small to be a real NotebookLM episode.

Usage:
    python scripts/validate_podcasts.py                 # report, all languages
    python scripts/validate_podcasts.py --lang en       # one language
    python scripts/validate_podcasts.py --strict        # exit 1 if any bad

🚨 The duration gate in this file had never once fired
------------------------------------------------------
It read duration with `mutagen.mp3.MP3(path)`. The shipped `.mp3` files are not
MP3s — ffprobe reports `mov,mp4,m4a` containers with AAC audio for the great
majority of them, so `MP3()` raised `HeaderNotFoundError`, `dur` fell to None,
and the `dur is None and size >= MIN_SIZE` branch passed the file on size
alone. `MIN_DURATION_S = 180` has been decorative since it was written.

`mutagen.File()` is not the fix either: it identifies the container correctly
and then reports `length == 0` for these files, which would fail every episode
in a CI gate. ffprobe reads them all correctly and is already required by the
reels pipeline, so it is the primary; mutagen stays as a fallback for hosts
without ffmpeg.

This matters more for English than it ever did for Arabic: a NotebookLM run
that returns a 90-second summary instead of a full episode clears a 2 MB
size-only gate at typical bitrates, and nothing else would notice.
"""
import argparse
import glob
import json
import os
import pathlib
import re
import subprocess
import sys
from collections import defaultdict

BASE = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / "backend"))
from app.media_naming import (  # noqa: E402
    MIN_PODCAST_BYTES, PODCAST_TAG, language_of_filename,
)

DOCS = BASE / "docs"

# A real NotebookLM episode is comfortably above these. Placeholders are far below.
MIN_DURATION_S = 180        # 3 minutes
MIN_SIZE_BYTES = MIN_PODCAST_BYTES


def band(name: str) -> str:
    m = re.match(r"lesson_(\d+[-_]\d+)", name)
    return m.group(1).replace("_", "-") if m else "other"


def duration_seconds(path: str):
    """Seconds, or None if genuinely undeterminable.

    None is a *reported* state, never an automatic pass — that conflation is
    what kept this gate dormant.
    """
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "json", path],
            capture_output=True, text=True, timeout=30,
        )
        if out.returncode == 0:
            value = json.loads(out.stdout).get("format", {}).get("duration")
            if value is not None and float(value) > 0:
                return float(value)
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    try:  # hosts without ffmpeg; unreliable on MP4-in-.mp3, hence second
        import mutagen
        f = mutagen.File(path)
        if f is not None and getattr(f.info, "length", 0) > 0:
            return float(f.info.length)
    except Exception:
        pass
    return None


def podcast_files(lang: str | None) -> list[str]:
    """Every podcast on disk, or only one language's.

    The old glob was `*_podcast.mp3`, which does not match `_podcast_en.mp3` —
    so English episodes were invisible to the validator that is supposed to
    gate them.
    """
    seen = {}
    for tag in PODCAST_TAG.values():
        for p in glob.glob(str(DOCS / f"*_podcast{tag}.mp3")):
            seen[p] = language_of_filename(p)
    return sorted(p for p, code in seen.items() if lang is None or code == lang)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true",
                    help="exit 1 if any placeholder/broken podcast is found")
    ap.add_argument("--lang", choices=sorted(PODCAST_TAG),
                    help="only this language (default: all)")
    args = ap.parse_args()

    bad = defaultdict(list)
    good = defaultdict(int)
    unknown = []
    by_lang = defaultdict(int)

    for path in podcast_files(args.lang):
        name = os.path.basename(path)
        size = os.path.getsize(path)
        dur = duration_seconds(path)
        by_lang[language_of_filename(path)] += 1

        if dur is None:
            # Neither reader could measure it. Passing on size alone is exactly
            # the old bug, so say so out loud and let --strict decide.
            unknown.append((name, size))
            good[band(name)] += 1
            continue
        if dur >= MIN_DURATION_S and size >= MIN_SIZE_BYTES:
            good[band(name)] += 1
        else:
            bad[band(name)].append((name, size, dur))

    total_good = sum(good.values())
    total_bad = sum(len(v) for v in bad.values())
    scope = args.lang or "all"
    print(f"Podcasts [{scope}]: {total_good} real, {total_bad} placeholder/broken "
          f"(of {total_good + total_bad})")
    print(f"  by language: {dict(by_lang)}\n")
    for b in sorted(set(list(good) + list(bad))):
        g, ba = good[b], len(bad[b])
        flag = "  <-- REGENERATE" if ba else ""
        print(f"  {b:<8} real={g:<3} bad={ba}{flag}")
    if total_bad:
        print("\nPlaceholder/broken files:")
        for b in sorted(bad):
            for name, size, dur in sorted(bad[b]):
                print(f"  {dur:6.0f}s  {size // 1024:6d}KB  {name}")
    if unknown:
        print(f"\n⚠️  {len(unknown)} file(s) with unreadable duration "
              f"(counted as real on size alone — install ffmpeg to check):")
        for name, size in unknown[:10]:
            print(f"          {size // 1024:6d}KB  {name}")

    if args.strict and total_bad:
        print(f"\nFAIL: {total_bad} podcast(s) below quality threshold "
              f"({MIN_DURATION_S}s / {MIN_SIZE_BYTES // 1024 // 1024}MB).")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
