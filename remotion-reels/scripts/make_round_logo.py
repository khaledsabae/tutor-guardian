#!/usr/bin/env python3
"""
make_round_logo — the real app logo, cut to a circle for the teaser.

Source: mobile/assets/images/logo.png (512², teal square, white ring). Its
bottom-right corner carries a small generator mark (✦ at about (452, 452)),
so the logo is cut to a circle of radius 228 around the centre: that keeps a
teal margin round the white ring and leaves the mark (≥ 260 px from the
centre) outside the cut, so it can never appear. Anti-aliased edge (4×
supersampled mask). Writes public/noor/app_logo_round.png (456², RGBA).

Usage: python3 scripts/make_round_logo.py   (run from remotion-reels/)
"""
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parents[1]
SRC = HERE.parent / "mobile" / "assets" / "images" / "logo.png"
OUT = HERE / "public" / "noor" / "app_logo_round.png"
CX = CY = 256
R = 228
SS = 4

src = Image.open(SRC).convert("RGBA")
assert src.size == (512, 512), src.size
box = (CX - R, CY - R, CX + R, CY + R)
crop = src.crop(box)
mask_big = Image.new("L", (2 * R * SS, 2 * R * SS), 0)
ImageDraw.Draw(mask_big).ellipse((0, 0, 2 * R * SS - 1, 2 * R * SS - 1), fill=255)
mask = mask_big.resize((2 * R, 2 * R), Image.LANCZOS)
crop.putalpha(mask)
crop.save(OUT, optimize=True)

# The generator mark must be fully outside the circle.
mark = (452 - (CX - R), 452 - (CY - R))
for dx in range(-14, 15):
    for dy in range(-14, 15):
        x, y = mark[0] + dx, mark[1] + dy
        if 0 <= x < 2 * R and 0 <= y < 2 * R:
            assert crop.getpixel((x, y))[3] == 0, ("mark visible at", x, y)
print(f"wrote {OUT} {crop.size}, mark region transparent")
