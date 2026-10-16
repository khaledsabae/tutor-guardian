#!/usr/bin/env python3
"""Render the preacher-package infographics (paper-cut style, 1080x1350 PNG).

Text comes from infographics.json (every line traced to app content in its
`source`). Art is the app's own paper-cut SVGs (mobile/assets/svg). The page is
laid out as HTML + inline SVG and photographed by headless Chrome, which shapes
Arabic correctly (rsvg/cairo do not here).

    python3 docs/marketing/2026-10-noor-launch/_build/render_infographics.py \
        --out-dir /tmp/infographics [topic ...]

Writes <out-dir>/<topic>.png. The package folders get copies (see 00_README.md).
"""
from __future__ import annotations

import argparse
import html
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
SVG = ROOT / "mobile/assets/svg"
FONTS = ROOT / "mobile/assets/google_fonts"
CAIRO_REGULAR = ROOT / "ops/tools/fonts/Cairo-Regular.ttf"

W, H = 1080, 1350

C = {
    "bg": "#0F6B5C", "hill2": "#12806D", "hill3": "#0D6A5A", "shadow": "#094A40",
    "star": "#13806C", "ivory": "#FBF1DE", "ivory2": "#EADBC0", "ivory3": "#D9C7A7",
    "coral": "#F4A492", "gold": "#F7C548", "ink": "#0F3D36",
}


def star(cx: float, cy: float, r: float, fill: str, shadow: str | None = None) -> str:
    """Eight-pointed geometric star (the app's star), optional paper shadow."""
    import math
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
    return (f'<svg class="bg" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg">'
            f'<rect width="{W}" height="{H}" fill="{C["bg"]}"/>{stars}{hills}</svg>')


def inline_svg(rel: str) -> str:
    text = (SVG / rel).read_text(encoding="utf-8")
    return text.replace("<svg ", '<svg width="100%" height="100%" ', 1)


def art(kind: str) -> str:
    if kind == "lanterns":
        lan = inline_svg("icons/lantern.svg")
        noor = inline_svg("noor/noor_happy.svg")
        return (f'<div class="art lanterns"><div class="l l1">{lan}</div>'
                f'<div class="noor">{noor}</div><div class="l l2">{lan}</div></div>')
    return f'<div class="art single">{inline_svg("art/" + kind + ".svg")}</div>'


CSS = """
@font-face { font-family: Cairo; font-weight: 300; src: url('FONTS/Cairo-Light.ttf'); }
@font-face { font-family: Cairo; font-weight: 400; src: url('CAIRO_REGULAR'); }
@font-face { font-family: Cairo; font-weight: 600; src: url('FONTS/Cairo-SemiBold.ttf'); }
@font-face { font-family: Cairo; font-weight: 700; src: url('FONTS/Cairo-Bold.ttf'); }
* { box-sizing: border-box; margin: 0; padding: 0; }
html, body { width: 1080px; height: 1350px; overflow: hidden; }
body { font-family: Cairo, sans-serif; direction: rtl; color: #FBF1DE; position: relative; }
.bg { position: absolute; inset: 0; width: 1080px; height: 1350px; z-index: 0; }
.page { position: absolute; top: 0; left: 0; right: 0; height: 1125px; z-index: 1; padding: 46px 64px 0; display: flex; flex-direction: column; }
.head { display: flex; align-items: center; gap: 24px; min-height: 190px; flex: none; }
.art.single { width: 190px; height: 190px; flex: none; }
.art.lanterns { width: 300px; height: 190px; flex: none; position: relative; }
.art.lanterns .noor { position: absolute; width: 190px; height: 190px; left: 55px; top: 0; }
.art.lanterns .l { position: absolute; width: 110px; height: 110px; }
.art.lanterns .l1 { right: -10px; top: 0; } .art.lanterns .l2 { left: -10px; top: 80px; }
.titles { flex: 1; }
.kicker { font-size: 25px; font-weight: 600; color: #F4A492; margin-bottom: 4px; }
h1 { font-size: TITLEpx; font-weight: 700; line-height: 1.25; color: #FBF1DE;
     text-shadow: 4px 5px 0 #094A40; }
.sub { font-size: 29px; font-weight: 600; color: #EADBC0; margin-top: 8px; line-height: 1.4; }
.card { background: #FBF1DE; color: #0F3D36; border-radius: 30px; margin-top: 26px;
        box-shadow: 12px 14px 0 #094A40; padding: 22px 36px; flex: 1;
        display: flex; flex-direction: column; justify-content: space-evenly; }
.item { display: flex; gap: 18px; align-items: flex-start; padding: ITEMPADpx 0;
        border-bottom: 3px dashed #EADBC0; }
.item:last-child { border-bottom: none; }
.dot { flex: none; width: 22px; height: 22px; margin-top: 15px; position: relative; }
.dot svg { width: 22px; height: 22px; }
.it { font-size: ITEMFONTpx; line-height: 1.5; font-weight: 400; }
.it b { font-weight: 700; color: #0F6B5C; }
.try { background: #F4A492; color: #0F3D36; border-radius: 26px; margin-top: 26px;
       box-shadow: 10px 12px 0 #094A40; padding: 20px 34px; }
.try .lbl { font-size: 25px; font-weight: 700; color: #094A40; }
.try .tx { font-size: 29px; line-height: 1.5; font-weight: 600; }
.fn { font-size: 23px; color: #EADBC0; text-align: center; margin-top: 18px; font-weight: 600; }
.foot { position: absolute; bottom: 30px; left: 64px; right: 64px; z-index: 2;
        display: flex; align-items: center; gap: 20px; }
.logo { width: 92px; height: 92px; flex: none; filter: none; }
.ft1 { font-size: 31px; font-weight: 700; color: #FBF1DE; }
.ft2 { font-size: 24px; font-weight: 600; color: #F7C548; }
"""


def page(t: dict) -> str:
    n = len(t["items"])
    item_font = 31 if n >= 6 else 34
    item_pad = 8 if n >= 6 else 12
    title_px = 56 if len(t["title"]) > 26 else (62 if len(t["title"]) > 18 else 68)
    css = (CSS.replace("FONTS", FONTS.as_uri()).replace("CAIRO_REGULAR", CAIRO_REGULAR.as_uri())
           .replace("TITLE", str(title_px)).replace("ITEMFONT", str(item_font))
           .replace("ITEMPAD", str(item_pad)))
    dot = (f'<svg viewBox="0 0 22 22">{star(10, 10, 9.5, C["gold"], C["shadow"])}</svg>')
    items = "".join(
        f'<div class="item"><div class="dot">{dot}</div><div class="it"><b>{html.escape(i["lead"])}{"" if i["lead"][-1] in "?؟" else ":"}</b> '
        f'{html.escape(i["text"])}</div></div>' for i in t["items"])
    fn = f'<div class="fn">{html.escape(t["footnote"])}</div>' if t.get("footnote") else ""
    logo = inline_svg("art/logo_mark.svg")
    en = t.get("lang") == "en"
    if en:
        css = (css.replace("direction: rtl;", "direction: ltr;")
               .replace(f"font-size: {item_font}px", f"font-size: {item_font - 3}px")
               .replace(f"font-size: {title_px}px", "font-size: 54px")
               .replace(".ft1 { font-size: 31px", ".ft1 { font-size: 26px")
               .replace(".ft2 { font-size: 24px", ".ft2 { font-size: 21px")
               .replace(".try .tx { font-size: 29px", ".try .tx { font-size: 27px"))
        foot1 = "Al-Morabbi — an Islamic parenting companion, pregnancy to 18"
        foot2 = "100% free — no ads, no subscriptions • Android, on Google Play"
    else:
        foot1 = "تطبيق المربّي الذكي — رفيق تربوي من الحمل حتى ١٨ سنة"
        foot2 = "مجاني بالكامل — بلا إعلانات ولا اشتراكات • على Google Play"
    lang, dirn = ("en", "ltr") if en else ("ar", "rtl")
    return f"""<!doctype html><html lang="{lang}" dir="{dirn}"><head><meta charset="utf-8">
<style>{css}</style></head><body>{background()}
<div class="page">
  <div class="head">{art(t["art"])}<div class="titles">
    <div class="kicker">{html.escape(t["kicker"])}</div>
    <h1>{html.escape(t["title"])}</h1><div class="sub">{html.escape(t["subtitle"])}</div></div></div>
  <div class="card">{items}</div>
  <div class="try"><div class="lbl">{html.escape(t["try"]["label"])}</div>
    <div class="tx">{html.escape(t["try"]["text"])}</div></div>
  {fn}
</div>
<div class="foot"><div class="logo">{logo}</div><div>
  <div class="ft1">{foot1}</div>
  <div class="ft2">{foot2}</div></div></div>
</body></html>"""


def chrome() -> str:
    for name in ("google-chrome", "chromium", "chromium-browser"):
        path = shutil.which(name)
        if path:
            return path
    sys.exit("headless Chrome not found")


def render(topic: str, t: dict, out: Path, browser: str) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / f"{topic}.html"
        src.write_text(page(t), encoding="utf-8")
        subprocess.run([browser, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                        "--force-device-scale-factor=1", f"--window-size={W},{H}",
                        "--allow-file-access-from-files", "--virtual-time-budget=3000",
                        f"--screenshot={out}", src.as_uri()],
                       check=True, capture_output=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("topics", nargs="*")
    a = ap.parse_args()
    data = json.loads((HERE / "infographics.json").read_text(encoding="utf-8"))["topics"]
    a.out_dir.mkdir(parents=True, exist_ok=True)
    browser = chrome()
    for topic in a.topics or list(data):
        out = a.out_dir / f"{topic}.png"
        render(topic, data[topic], out, browser)
        print(out, out.stat().st_size)


if __name__ == "__main__":
    main()
