#!/usr/bin/env python3
"""tutor_reels pipeline: generate 3 reels then publish the oldest unposted one to Buffer."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

def run(cmd):
    print(f"\n>>> {' '.join(cmd)}")
    r = subprocess.run(cmd, cwd=str(ROOT), check=False)
    if r.returncode != 0:
        print(f"FAIL: exit {r.returncode}")
        return False
    return True

# 1. Generate up to 3 new reels
gen_ok = run([
    "/usr/bin/python3", "scripts/podcast_to_reel.py",
    "--batch", "3", "--output", "docs/marketing/reels_output"
])

# 2. Publish one unposted reel to Buffer (limit 1)
pub_ok = run([
    "/usr/bin/python3", "scripts/publish_reels_to_buffer.py",
    "--limit", "1"
])

sys.exit(0 if (gen_ok and pub_ok) else 1)

