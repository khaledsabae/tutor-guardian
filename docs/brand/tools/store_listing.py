#!/usr/bin/env python3
"""Play store-listing set for a release — framed screenshots + icon + feature graphic.

  python3 docs/brand/tools/store_listing.py build \\
      --listing docs/brand/store/listing_1.0.73 \\
      --captures <run_id>=<dir with the run's artifacts> [--captures …]

The listing folder's manifest.json is the recipe: for each of the 8 slots, which
CI run / artifact / file the real capture comes from, which paper-cut frame, and
the Arabic and English headline. Captures are never committed (they are CI
artifacts); manifest.json records each one's sha256 so the set can be rebuilt
and checked. Output, per language folder (ar/, en/):

  phone_0N_<slot>.png   1080x1920 (9:16), 24-bit
  icon.png              512x512, 32-bit (Play wants alpha-capable PNG)
  feature_graphic.png   1024x500, 24-bit

`contact` writes one review sheet of everything (both languages + icon + feature
graphic) — e.g. to scratch/, which git ignores.

The only change ever made to a capture is a crop (`keep_top`): the system
keyboard is cut away and the cut is filled with the app's own background colour
taken from beside the input bar, just above the cut. Nothing inside the app's UI is retouched.
"""
import argparse
import hashlib
import json
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import brand_build as bb  # noqa: E402  (sets up the private fontconfig + Cairo/Pango)
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

LANGS = {'ar': 'ar', 'en': 'en'}
FEATURE_EN = {'المربّي': 'Al-Morabbi', 'رفيقك في تربية طفلك': 'Your parenting companion'}


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _capture(captures, src, check=True):
    root = captures.get(str(src['run']))
    if root is None:
        raise SystemExit(f'no --captures given for run {src["run"]}')
    path = Path(root) / src['artifact'] / src['file']
    if not path.exists():
        raise SystemExit(f'missing capture: {path}')
    if check and src.get('sha256') and sha256(path) != src['sha256']:
        raise SystemExit(f'capture changed since the manifest was written: {path}')
    return path


def _prepared(path, src, tmp):
    """Apply the manifest's crop (if any) and return the image path to frame."""
    keep = src.get('keep_top')
    if not keep:
        return path
    img = Image.open(path).convert('RGB')
    bg = img.getpixel((img.width - 20, keep - 12))  # the chat background beside the input bar
    out = Image.new('RGB', img.size, bg)
    out.paste(img.crop((0, 0, img.width, keep)), (0, 0))
    p = Path(tmp) / f'crop_{path.name}'
    out.save(p)
    return p


def _feature_graphic(lang, out):
    svg = (bb.STORE_DIR / 'feature_graphic.svg').read_text(encoding='utf-8')
    if lang == 'en':
        for ar, en in FEATURE_EN.items():
            svg = svg.replace(f'>{ar}<', f'>{en}<')
        # Latin set in Cairo runs wider than the Arabic word mark; keep it clear of the moon.
        svg = svg.replace('font-size="124" fill="#FBF1DE">Al-Morabbi', 'font-size="86" fill="#FBF1DE">Al-Morabbi')
        svg = svg.replace('font-size="40" fill="#A8E6C4">Your parenting', 'font-size="36" fill="#A8E6C4">Your parenting')
    bb.surface_to_pil(bb.svg_surface(svg, 1024, 500)).convert('RGB').save(out, optimize=True)


def build(listing, captures, refresh_hashes=False):
    manifest_path = listing / 'manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    with tempfile.TemporaryDirectory(prefix='tg-store-') as tmp:
        for sub in LANGS:
            d = listing / sub
            d.mkdir(parents=True, exist_ok=True)
            for old in d.glob('phone_*.png'):
                old.unlink()
            for i, slot in enumerate(manifest['slots'], 1):
                src = slot['source'][sub]
                path = _capture(captures, src, check=not refresh_hashes)
                if refresh_hashes:
                    src['sha256'] = sha256(path)
                text = slot['text'][sub]
                out = d / f'phone_{i:02d}_{slot["id"]}.png'
                bb.fill_frame(slot['frame'], _prepared(path, src, tmp), text['title'], text['subtitle'], out)
            bb.surface_to_pil(bb.icon_surface(bb.RECOMMENDED, 512)).convert('RGBA').save(d / 'icon.png', optimize=True)
            _feature_graphic(sub, d / 'feature_graphic.png')
    if refresh_hashes:
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('  listing set written to', listing)


def contact(listing, out):
    """One sheet: icon + feature graphic per language, then the 8 screenshots per language."""
    W = 270
    font_path = next(bb.FONTS.glob('Cairo*.ttf'), None)
    font = ImageFont.truetype(str(font_path), 22) if font_path else ImageFont.load_default()
    rows = []
    for sub in LANGS:
        d = listing / sub
        shots = sorted(d.glob('phone_*.png'))
        rows.append((sub, [d / 'icon.png', d / 'feature_graphic.png'], shots))
    shot_h = int(1920 * W / 1080)
    width = 8 * (W + 12) + 12
    height = sum(40 + 250 + 40 + shot_h + 50 for _ in rows) + 20
    sheet = Image.new('RGB', (width, height), '#FBF1DE')
    draw = ImageDraw.Draw(sheet)
    y = 10
    for sub, art, shots in rows:
        draw.text((12, y), f'{sub}  —  icon 512 · feature graphic 1024x500 · {len(shots)} phone screenshots 1080x1920',
                  fill='#0F3D36', font=font)
        y += 40
        icon = Image.open(art[0]).convert('RGBA').resize((240, 240))
        sheet.paste(icon, (12, y), icon)
        fg = Image.open(art[1]).convert('RGB').resize((512, 250))
        sheet.paste(fg, (270, y))
        y += 250 + 40
        for i, s in enumerate(shots):
            im = Image.open(s).convert('RGB').resize((W, shot_h))
            x = 12 + i * (W + 12)
            sheet.paste(im, (x, y))
            draw.text((x, y + shot_h + 6), re.sub(r'^phone_', '', s.stem), fill='#0F3D36', font=font)
        y += shot_h + 50
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out, optimize=True)
    print('  contact sheet', out, sheet.size)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    b = sub.add_parser('build')
    b.add_argument('--listing', type=Path, required=True)
    b.add_argument('--captures', action='append', default=[], metavar='RUN_ID=DIR')
    b.add_argument('--refresh-hashes', action='store_true',
                   help='record the captures\' sha256 in manifest.json (after choosing new runs)')
    c = sub.add_parser('contact')
    c.add_argument('--listing', type=Path, required=True)
    c.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    if args.cmd == 'build':
        caps = dict(x.split('=', 1) for x in args.captures)
        build(args.listing, caps, args.refresh_hashes)
    else:
        contact(args.listing, args.out)


if __name__ == '__main__':
    main()
