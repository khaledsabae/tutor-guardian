#!/usr/bin/env python3
"""Render the Ramadan wave-2 preacher infographics: one standalone SVG + one
1080x1350 PNG per package, in the «ورق مقصوص» paper-cut style.

Text comes from topics.json (every line traced to the app's «رمضان العائلة»
program in its `source`). Art is the app's own paper-cut SVGs
(mobile/assets/svg), nested as-is. The SVG is self-contained: the Cairo
weights it uses are subset to its own characters and embedded, so it renders
the same in any browser. Lines are wrapped here, measured with the same font
through Pillow's raqm layout (Arabic shaping), because SVG <text> does not wrap.

The PNG is the SVG photographed by headless Chrome at 1080x1350.

    python3 docs/marketing/2027-01-ramadan-preachers/_build/render.py [FOLDER ...]

With no argument, every package in packages.json is rendered into its folder.
"""
from __future__ import annotations

import base64
import html
import io
import json
import math
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont
from PIL import Image, ImageFont

HERE = Path(__file__).resolve().parent
KIT = HERE.parent
ROOT = HERE.parents[3]
SVG = ROOT / "mobile/assets/svg"
FONT_FILES = {
    400: ROOT / "ops/tools/fonts/Cairo-Regular.ttf",
    600: ROOT / "mobile/assets/google_fonts/Cairo-SemiBold.ttf",
    700: ROOT / "mobile/assets/google_fonts/Cairo-Bold.ttf",
}

W, H = 1080, 1350
PAD = 64
CONTENT_BOTTOM = 1112  # the hills and the footer live below this line

C = {
    "bg": "#0F6B5C", "hill2": "#12806D", "hill3": "#0D6A5A", "shadow": "#094A40",
    "star": "#13806C", "ivory": "#FBF1DE", "ivory2": "#EADBC0", "ivory3": "#D9C7A7",
    "coral": "#F4A492", "gold": "#F7C548", "ink": "#0F3D36",
}

_fonts: dict[tuple[int, int], ImageFont.FreeTypeFont] = {}


def font(weight: int, size: int) -> ImageFont.FreeTypeFont:
    key = (weight, size)
    if key not in _fonts:
        _fonts[key] = ImageFont.truetype(str(FONT_FILES[weight]), size,
                                         layout_engine=ImageFont.Layout.RAQM)
    return _fonts[key]


def width(text: str, weight: int, size: int, rtl: bool) -> float:
    return font(weight, size).getlength(text, direction="rtl" if rtl else "ltr")


def wrap(runs: list[tuple[str, int]], max_w: float, size: int, rtl: bool) -> list[list[tuple[str, int]]]:
    """Greedy word wrap over (text, weight) runs. Returns lines of runs."""
    words: list[tuple[str, int]] = []
    for text, wt in runs:
        words += [(w, wt) for w in text.split()]
    lines: list[list[tuple[str, int]]] = []
    cur: list[tuple[str, int]] = []
    space = width(" ", 400, size, rtl)

    def line_w(ws):
        return sum(width(w, wt, size, rtl) for w, wt in ws) + space * max(0, len(ws) - 1)

    for w in words:
        if cur and line_w(cur + [w]) > max_w:
            lines.append(cur)
            cur = [w]
        else:
            cur.append(w)
    if cur:
        lines.append(cur)
    # No one-word last line: pull a word down from the line above when it still fits.
    if len(lines) >= 2 and len(lines[-1]) == 1 and len(lines[-2]) >= 3:
        moved = [lines[-2][-1]] + lines[-1]
        if line_w(moved) <= max_w:
            lines[-2] = lines[-2][:-1]
            lines[-1] = moved
    out = []
    for ln in lines:  # merge consecutive words of the same weight into runs
        merged: list[tuple[str, int]] = []
        for w, wt in ln:
            if merged and merged[-1][1] == wt:
                merged[-1] = (merged[-1][0] + " " + w, wt)
            else:
                merged.append((w, wt))
        out.append(merged)
    return out


def star(cx: float, cy: float, r: float, fill: str, shadow: str | None = None) -> str:
    pts = []
    for i in range(16):
        rad = r if i % 2 == 0 else r * 0.62
        a = math.pi / 8 * i - math.pi / 2
        pts.append(f"{cx + rad * math.cos(a):.1f},{cy + rad * math.sin(a):.1f}")
    p = " ".join(pts)
    out = ""
    if shadow:
        out += f'<polygon points="{p}" fill="{shadow}" transform="translate({r*0.12:.1f},{r*0.15:.1f})"/>'
    return out + f'<polygon points="{p}" fill="{fill}"/>'


def background() -> str:
    stars = "".join(star(x, y, r, C["star"]) for x, y, r in [
        (90, 120, 22), (990, 90, 18), (60, 520, 14), (1030, 430, 20), (980, 760, 12),
        (40, 900, 16), (540, 40, 10), (300, 70, 8), (800, 200, 9)])
    hills = (
        f'<path d="M0 1180 Q270 1090 540 1150 T1080 1120 V1350 H0Z" fill="{C["shadow"]}" transform="translate(0,10)"/>'
        f'<path d="M0 1180 Q270 1090 540 1150 T1080 1120 V1350 H0Z" fill="{C["hill2"]}"/>'
        f'<path d="M0 1250 Q300 1190 620 1240 T1080 1215 V1350 H0Z" fill="{C["shadow"]}" transform="translate(0,10)"/>'
        f'<path d="M0 1250 Q300 1190 620 1240 T1080 1215 V1350 H0Z" fill="{C["hill3"]}"/>'
    )
    return f'<rect width="{W}" height="{H}" fill="{C["bg"]}"/>{stars}{hills}'


def nested(rel: str, x: float, y: float, w: float, h: float) -> str:
    """An app SVG placed as a nested <svg> (they carry no ids, so nothing clashes)."""
    text = (SVG / rel).read_text(encoding="utf-8").strip()
    return text.replace("<svg ", f'<svg x="{x:.0f}" y="{y:.0f}" width="{w:.0f}" height="{h:.0f}" ', 1)


def art(kind: str, x: float, y: float, rtl: bool) -> tuple[str, float]:
    """Header art at (x, y) = its top-left; returns (svg, width)."""
    if kind == "lanterns":
        w = 300
        lan_a = (x + w - 100, y) if rtl else (x - 10, y)
        lan_b = (x - 10, y + 80) if rtl else (x + w - 100, y + 80)
        return (nested("icons/lantern.svg", *lan_a, 110, 110)
                + nested("noor/noor_happy.svg", x + 55, y, 190, 190)
                + nested("icons/lantern.svg", *lan_b, 110, 110)), w
    return nested(kind + ".svg", x, y, 190, 190), 190


def text_line(runs, x: float, y: float, size: int, fill: str, rtl: bool, anchor: str = "start",
              bold_fill: str | None = None, shadow: str | None = None) -> str:
    def body(dx=0.0, dy=0.0, colour=None):
        spans = []
        for i, (t, wt) in enumerate(runs):
            sep = " " if i else ""
            f = colour or (bold_fill if (bold_fill and wt == 700) else fill)
            spans.append(f'<tspan font-weight="{wt}" fill="{f}">{html.escape(sep + t)}</tspan>')
        d = ' direction="rtl"' if rtl else ""
        return (f'<text x="{x + dx:.1f}" y="{y + dy:.1f}" font-size="{size}"{d} '
                f'text-anchor="{anchor}">{"".join(spans)}</text>')
    out = body(4, 5, shadow) if shadow else ""
    return out + body()


def baseline(top: float, lh: float, size: int) -> float:
    # Cairo: ascent 1.303em, descent 0.571em; centre the em box in the line box.
    return top + (lh - size * 1.874) / 2 + size * 1.303


def layout(t: dict, item_size: int, extra_gap: float = 0.0):
    """Lay out the page; returns (svg body, bottom y of the content)."""
    rtl = t.get("lang", "ar") != "en"
    out: list[str] = []
    y = 46.0
    # Header: art on the reading-start side, titles beside it.
    art_x = 0.0
    art_svg, art_w = art(t["art"], 0, 0, rtl)
    art_x = (W - PAD - art_w) if rtl else PAD
    art_svg, _ = art(t["art"], art_x, y, rtl)
    tx_w = W - 2 * PAD - art_w - 26
    tx_edge = (art_x - 26) if rtl else (PAD + art_w + 26)
    title_size = 64 if width(t["title"], 700, 64, rtl) <= tx_w * 1.05 else 54
    if not rtl:
        title_size = 50
    head: list[tuple[str, list, int, int, str]] = []
    for text, wt, size, colour in [(t["kicker"], 600, 25, C["coral"]),
                                   (t["title"], 700, title_size, C["ivory"]),
                                   (t["subtitle"], 600, 29, C["ivory2"])]:
        for ln in wrap([(text, wt)], tx_w, size, rtl):
            head.append((text, ln, size, wt, colour))
    lh_of = {25: 40, 29: 44, 50: 62, 54: 68, 64: 78}
    block_h = sum(lh_of[s] for _, _, s, _, _ in head)
    ty = y + max(0, (190 - block_h) / 2)
    for _, ln, size, wt, colour in head:
        lh = lh_of[size]
        shadow = C["shadow"] if wt == 700 else None
        out.append(text_line(ln, tx_edge, baseline(ty, lh, size), size, colour, rtl, shadow=shadow))
        ty += lh
    y = max(y + 190, ty) + 26
    out.insert(0, art_svg)

    # Card of items.
    card_top = y
    inner_w = W - 2 * PAD - 2 * 36 - 40  # card padding, bullet column
    lh = round(item_size * (1.5 if rtl else 1.38))
    items = []
    for it in t["items"]:
        lead = it["lead"] + ("" if it["lead"][-1] in "?؟" else ":")
        items.append(wrap([(lead, 700), (it["text"], 400)], inner_w, item_size, rtl))
    pad_v = 10 + extra_gap
    card_h = 22 * 2 + sum(len(ls) * lh + 2 * pad_v for ls in items)
    card = [f'<rect x="{PAD + 12}" y="{card_top + 14:.1f}" width="{W - 2 * PAD}" height="{card_h:.1f}" rx="30" fill="{C["shadow"]}"/>',
            f'<rect x="{PAD}" y="{card_top:.1f}" width="{W - 2 * PAD}" height="{card_h:.1f}" rx="30" fill="{C["ivory"]}"/>']
    iy = card_top + 22
    text_edge = (W - PAD - 36 - 40) if rtl else (PAD + 36 + 40)
    dot_x = (W - PAD - 36 - 13) if rtl else (PAD + 36 + 13)
    for n, ls in enumerate(items):
        iy += pad_v
        card.append(star(dot_x, iy + lh / 2, 11, C["gold"], C["shadow"]))
        for ln in ls:
            card.append(text_line(ln, text_edge, baseline(iy, lh, item_size), item_size,
                                  C["ink"], rtl, bold_fill=C["bg"]))
            iy += lh
        iy += pad_v
        if n < len(items) - 1:
            card.append(f'<line x1="{PAD + 36}" y1="{iy:.1f}" x2="{W - PAD - 36}" y2="{iy:.1f}" '
                        f'stroke="{C["ivory2"]}" stroke-width="3" stroke-dasharray="9 7"/>')
    out += card
    y = card_top + card_h + 26

    # The «try» slip.
    tw = W - 2 * PAD - 2 * 34
    lbl = wrap([(t["try"]["label"], 700)], tw, 25, rtl)
    txl = wrap([(t["try"]["text"], 600)], tw, 29, rtl)
    try_h = 20 * 2 + len(lbl) * 40 + len(txl) * 44
    out.append(f'<rect x="{PAD + 10}" y="{y + 12:.1f}" width="{W - 2 * PAD}" height="{try_h}" rx="26" fill="{C["shadow"]}"/>')
    out.append(f'<rect x="{PAD}" y="{y:.1f}" width="{W - 2 * PAD}" height="{try_h}" rx="26" fill="{C["coral"]}"/>')
    edge = (W - PAD - 34) if rtl else (PAD + 34)
    ty = y + 20
    for ln in lbl:
        out.append(text_line(ln, edge, baseline(ty, 40, 25), 25, C["shadow"], rtl))
        ty += 40
    for ln in txl:
        out.append(text_line(ln, edge, baseline(ty, 44, 29), 29, C["ink"], rtl))
        ty += 44
    y += try_h + 12
    if t.get("footnote"):
        for ln in wrap([(t["footnote"], 600)], W - 2 * PAD, 23, rtl):
            y += 6
            out.append(text_line(ln, W / 2, baseline(y, 36, 23), 23, C["ivory2"], rtl, anchor="middle"))
            y += 36
    return out, y


def footer(rtl: bool) -> str:
    if rtl:
        l1 = "تطبيق المربّي الذكي — رفيق تربوي من الحمل حتى ١٨ سنة"
        l2 = "مجاني بالكامل — بلا إعلانات ولا اشتراكات • على Google Play"
        s1, s2 = 31, 24
    else:
        l1 = "Al-Morabbi — an Islamic parenting companion, pregnancy to 18"
        l2 = "100% free — no ads, no subscriptions • Android, on Google Play"
        s1, s2 = 26, 21
    top = H - 30 - 92
    logo_x = (W - PAD - 92) if rtl else PAD
    edge = (logo_x - 20) if rtl else (PAD + 92 + 20)
    return (nested("art/logo_mark.svg", logo_x, top, 92, 92)
            + text_line([(l1, 700)], edge, top + 40, s1, C["ivory"], rtl)
            + text_line([(l2, 600)], edge, top + 80, s2, C["gold"], rtl))


def embedded_fonts(chars: str) -> str:
    rules = []
    for wt, path in FONT_FILES.items():
        opts = subset.Options()
        opts.layout_features = ["*"]
        opts.flavor = "woff"
        opts.name_IDs = ["*"]
        opts.notdef_outline = True
        f = TTFont(str(path))
        s = subset.Subsetter(opts)
        s.populate(text=chars)
        s.subset(f)
        buf = io.BytesIO()
        f.flavor = "woff"
        f.save(buf)
        b64 = base64.b64encode(buf.getvalue()).decode()
        rules.append(f"@font-face{{font-family:'CairoKit';font-weight:{wt};"
                     f"src:url(data:font/woff;base64,{b64}) format('woff');}}")
    return "".join(rules)


def build_svg(t: dict) -> str:
    rtl = t.get("lang", "ar") != "en"
    best = None
    for size in (34, 33, 32, 31, 30, 29, 28, 27, 26):
        body, bottom = layout(t, size)
        if bottom <= CONTENT_BOTTOM:
            best = (size, body, bottom)
            break
    if best is None:
        sys.exit(f"topic does not fit even at 26px: {t['title']}")
    size, body, bottom = best
    # Spend the slack: more breathing room between items, as the HTML version's space-evenly did.
    n = len(t["items"])
    gap = min(14.0, (CONTENT_BOTTOM - bottom) / (2 * n)) if n else 0
    body, _ = layout(t, size, gap)
    inner = background() + "".join(body) + footer(rtl)
    chars = "".join(sorted(set(html.unescape(inner)))) + " :—•"
    style = embedded_fonts(chars)
    lang = "ar" if rtl else "en"
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
            f'lang="{lang}" font-family="CairoKit, Cairo, sans-serif">'
            f'<title>{html.escape(t["title"])}</title><style>{style}</style>{inner}</svg>')


def chrome() -> str:
    for name in ("google-chrome", "chromium", "chromium-browser"):
        p = shutil.which(name)
        if p:
            return p
    sys.exit("headless Chrome not found")


def to_png(svg_path: Path, png_path: Path, browser: str) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        shot = Path(tmp) / "shot.png"
        subprocess.run([browser, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                        "--force-device-scale-factor=1", f"--window-size={W},{H}",
                        "--virtual-time-budget=3000", f"--screenshot={shot}", svg_path.as_uri()],
                       check=True, capture_output=True)
        im = Image.open(shot).convert("RGB")
        if im.size != (W, H):
            sys.exit(f"{png_path}: Chrome gave {im.size}, not {(W, H)}")
        im.save(png_path, optimize=True)


def main() -> None:
    topics = json.loads((HERE / "topics.json").read_text(encoding="utf-8"))["topics"]
    packages = json.loads((HERE / "packages.json").read_text(encoding="utf-8"))["packages"]
    want = set(sys.argv[1:])
    browser = chrome()
    for p in packages:
        if want and p["folder"] not in want:
            continue
        for g in p["infographics"]:
            folder = KIT / p["folder"]
            folder.mkdir(parents=True, exist_ok=True)
            svg_path = folder / f"{g['name']}.svg"
            svg_path.write_text(build_svg(topics[g["topic"]]), encoding="utf-8")
            png_path = folder / f"{g['name']}.png"
            to_png(svg_path, png_path, browser)
            print(f"{p['folder']}/{g['name']}  svg {svg_path.stat().st_size // 1024}KB  "
                  f"png {png_path.stat().st_size // 1024}KB")


if __name__ == "__main__":
    main()
