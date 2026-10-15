#!/usr/bin/env python3
"""
make_campaign_sheet — a contact sheet of the campaign reels, pulled from the
rendered MP4s themselves (not from the source), so it shows what ships.

One row per reel, one column per moment (seconds). Frames are decoded with
ffmpeg, scaled to 1/4 (270×480) and labelled «file @ time».

Usage:
  python3 scripts/make_campaign_sheet.py OUT.png DIR v1_remember:1.2,4,7,11,13,17 v2_road:...
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

TW, TH = 270, 480
GAP, LABEL = 10, 26


def grab(mp4: Path, t: float, out: Path) -> None:
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", str(mp4), "-frames:v", "1",
         "-vf", f"scale={TW}:{TH}", str(out)],
        check=True,
    )


def main() -> int:
    out, src = Path(sys.argv[1]), Path(sys.argv[2])
    rows = []
    for spec in sys.argv[3:]:
        name, times = spec.split(":")
        rows.append((name, [float(t) for t in times.split(",")]))
    cols = max(len(t) for _, t in rows)
    sheet = Image.new("RGB", (cols * (TW + GAP) + GAP, len(rows) * (TH + LABEL + GAP) + GAP), "white")
    draw = ImageDraw.Draw(sheet)
    with tempfile.TemporaryDirectory() as tmp:
        for r, (name, times) in enumerate(rows):
            for c, t in enumerate(times):
                png = Path(tmp) / f"{name}_{c}.png"
                grab(src / f"{name}.mp4", t, png)
                x = GAP + c * (TW + GAP)
                y = GAP + r * (TH + LABEL + GAP)
                sheet.paste(Image.open(png).convert("RGB"), (x, y))
                draw.text((x + 2, y + TH + 6), f"{name} @ {t:.1f}s", fill="black")
    sheet.save(out)
    print(f"{out}  {sheet.size[0]}x{sheet.size[1]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
