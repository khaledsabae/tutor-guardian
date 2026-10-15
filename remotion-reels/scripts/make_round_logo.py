#!/usr/bin/env python3
"""
make_round_logo — the app icon, cut to a circle, for the teaser and the
campaign reels (end card + small corner mark).

Source: public/noor/brand/icon_c_hills.svg — the paper-cut icon C «الطبقات»
(Noor rising behind paper hills) that Khaled chose on 2026-10-15. It is a
verbatim copy of docs/brand/icon/icon_c_hills.svg from the brand PR #121
(branch noor/brand-paper @ 01e9257d); copy it again if that file changes.

The SVG's 0 0 240 240 box is the visible part of the adaptive icon, and a
round launcher mask is the circle inscribed in it, so the whole box is
rendered (background + foreground; the monochrome layer stays hidden) at
SIZE px with Rsvg/cairo and cut to that circle with an anti-aliased edge
(4× supersampled mask). Writes public/noor/app_logo_round.png (RGBA).

Needs python3-gi (Rsvg 2.0), pycairo, Pillow.
Usage: python3 scripts/make_round_logo.py   (run from remotion-reels/)
"""
import io
from pathlib import Path

import cairo
import gi
from PIL import Image, ImageDraw

gi.require_version("Rsvg", "2.0")
from gi.repository import Rsvg  # noqa: E402

HERE = Path(__file__).resolve().parents[1]
SRC = HERE / "public" / "noor" / "brand" / "icon_c_hills.svg"
OUT = HERE / "public" / "noor" / "app_logo_round.png"
SIZE = 912  # ≥ 3× the largest on-screen logo (300 px in the teaser)
SS = 4

handle = Rsvg.Handle.new_from_data(SRC.read_bytes())
surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, SIZE, SIZE)
rect = Rsvg.Rectangle()
rect.x, rect.y, rect.width, rect.height = 0, 0, SIZE, SIZE
handle.render_document(cairo.Context(surf), rect)
surf.flush()
buf = io.BytesIO()
surf.write_to_png(buf)
buf.seek(0)
icon = Image.open(buf).convert("RGBA")

mask_big = Image.new("L", (SIZE * SS, SIZE * SS), 0)
ImageDraw.Draw(mask_big).ellipse((0, 0, SIZE * SS - 1, SIZE * SS - 1), fill=255)
icon.putalpha(mask_big.resize((SIZE, SIZE), Image.LANCZOS))

# sanity: opaque inside (the paper icon has no holes), clear in the corners
assert icon.getpixel((SIZE // 2, SIZE // 2))[3] == 255
assert icon.getpixel((2, 2))[3] == 0 and icon.getpixel((SIZE - 3, SIZE - 3))[3] == 0
icon.save(OUT, optimize=True)
print(f"wrote {OUT} {icon.size} from {SRC.name}")
