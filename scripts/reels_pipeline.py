#!/usr/bin/env python3
"""tutor_reels: generate reels. Publishing is a separate, deliberate step.

It used to generate and publish in one run, which meant the first time anyone
saw a reel was after the audience had. Twenty-one went out that way. Generation
is safe to schedule; publishing is not, so it now needs --publish.

  scripts/reels_pipeline.py               # ولّد فقط — آمن للجدولة
  scripts/reels_pipeline.py --publish     # انشر أقدم ريل غير منشور بعد مراجعته
"""
import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REELS_DIR = ROOT / "docs" / "marketing" / "reels_v2"


def run(cmd):
    print(f"\n>>> {' '.join(cmd)}")
    r = subprocess.run(cmd, cwd=str(ROOT), check=False)
    if r.returncode != 0:
        print(f"FAIL: exit {r.returncode}")
        return False
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--count", type=int, default=3, help="كم ريلًا يُولَّد في التشغيلة")
    ap.add_argument("--publish", action="store_true",
                    help="انشر ريلًا واحدًا على Buffer — لا يحدث بدون هذا الخيار")
    args = ap.parse_args()

    ok = run([str(ROOT / "scripts" / "reel"),
              "--batch", str(args.count), "--montage", "6", "--duration", "30"])

    if not args.publish:
        print(f"\nلم يُنشر شيء. راجع {REELS_DIR.relative_to(ROOT)} ثم:"
              f"\n  scripts/reels_pipeline.py --publish")
        return 0 if ok else 1

    pub = run(["/usr/bin/python3", "scripts/publish_reels_to_buffer.py",
               "--dir", str(REELS_DIR), "--limit", "1"])
    return 0 if (ok and pub) else 1


if __name__ == "__main__":
    sys.exit(main())
