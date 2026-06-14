#!/usr/bin/env python3
"""Guard against placeholder/broken lesson podcasts.

Real NotebookLM podcasts are multi-minute (>= ~3 min, several MB). The old
edge-tts fallback (gen_tts_podcasts.py) produced 48kbps, 40-120s summary clips
that silently filled gaps for 4 age bands. This validator flags every podcast
that is too short / too small to be a real NotebookLM episode.

Usage:
    python scripts/validate_podcasts.py            # report
    python scripts/validate_podcasts.py --strict   # exit 1 if any bad (CI gate)
"""
import argparse
import glob
import os
import pathlib
import re
import sys
from collections import defaultdict

from mutagen.mp3 import MP3

DOCS = pathlib.Path(__file__).resolve().parent.parent / "docs"

# A real NotebookLM episode is comfortably above these. Placeholders are far below.
MIN_DURATION_S = 180        # 3 minutes
MIN_SIZE_BYTES = 2 * 1024 * 1024  # 2 MB


def band(name: str) -> str:
    m = re.match(r"lesson_(\d+[-_]\d+)", name)
    return m.group(1).replace("_", "-") if m else "other"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true",
                    help="exit 1 if any placeholder/broken podcast is found")
    args = ap.parse_args()

    bad = defaultdict(list)
    good = defaultdict(int)
    for path in sorted(glob.glob(str(DOCS / "*_podcast.mp3"))):
        name = os.path.basename(path)
        size = os.path.getsize(path)
        try:
            dur = MP3(path).info.length
        except Exception:
            dur = None
        # Big file mutagen can't parse quickly == real long episode.
        is_real = (dur is None and size >= MIN_SIZE_BYTES) or \
                  (dur is not None and dur >= MIN_DURATION_S and size >= MIN_SIZE_BYTES)
        if is_real:
            good[band(name)] += 1
        else:
            bad[band(name)].append((name, size, dur or 0))

    total_good = sum(good.values())
    total_bad = sum(len(v) for v in bad.values())
    print(f"Podcasts: {total_good} real, {total_bad} placeholder/broken "
          f"(of {total_good + total_bad})\n")
    for b in sorted(set(list(good) + list(bad))):
        g, ba = good[b], len(bad[b])
        flag = "  <-- REGENERATE" if ba else ""
        print(f"  {b:<8} real={g:<3} bad={ba}{flag}")
    if total_bad:
        print("\nPlaceholder/broken files:")
        for b in sorted(bad):
            for name, size, dur in sorted(bad[b]):
                print(f"  {dur:6.0f}s  {size // 1024:6d}KB  {name}")

    if args.strict and total_bad:
        print(f"\nFAIL: {total_bad} podcast(s) below quality threshold "
              f"({MIN_DURATION_S}s / {MIN_SIZE_BYTES // 1024 // 1024}MB).")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
