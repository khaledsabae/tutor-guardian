#!/usr/bin/env python3
"""Brand pipeline for المربّي — icon directions, Android adaptive icon, store art.

The SVG files under docs/brand/ are the source of truth. This script only derives
things from them:

  review            comparison boards for the three icon directions -> docs/brand/review/
  android <a|b|c>   adaptive icon (vector drawables) + legacy PNGs for one direction,
                    written under NEW names (ic_launcher_paper*) so the shipped icon
                    is untouched until the manifest is pointed at them
  store             feature graphic, empty screenshot frames, Play 512 icon,
                    example filled frames -> docs/brand/store/
  web               landing-page art from the same sources: the 1200x630 share
                    image (og:image) from the feature graphic, the PWA / favicon
                    icons from icon C -> frontend/assets/, frontend/icons/
  frame             fill one frame with a screenshot (e.g. from the CI e2e-gallery)

Needs only what the laptop already has: python3-gi (Rsvg 2, Pango), pycairo, Pillow.
Text is set in Cairo from mobile/assets/google_fonts/ (wired in through a private
fontconfig file, nothing is installed system-wide).

Icon sources (docs/brand/icon/icon_*.svg) have three top-level groups:
  background / foreground / monochrome (display="none")
in a 0 0 240 240 space that equals the 72dp *visible* part of a 108dp adaptive
icon. The adaptive safe zone (66dp circle) is therefore radius 110 around (120,120).
Only presentation attributes and translate()/scale() transforms are allowed, so the
same file converts exactly to an Android VectorDrawable.
"""
import argparse
import io
import math
import os
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BRAND = ROOT / 'docs' / 'brand'
ICON_DIR = BRAND / 'icon'
STORE_DIR = BRAND / 'store'
REVIEW_DIR = BRAND / 'review'
RES = ROOT / 'mobile' / 'android' / 'app' / 'src' / 'main' / 'res'
FONTS = ROOT / 'mobile' / 'assets' / 'google_fonts'


def _private_fontconfig():
    cache = Path.home() / '.cache' / 'tg-brand-fontconfig'
    cache.mkdir(parents=True, exist_ok=True)
    conf = cache / 'fonts.conf'
    conf.write_text(
        '<?xml version="1.0"?><!DOCTYPE fontconfig SYSTEM "fonts.dtd"><fontconfig>'
        '<include ignore_missing="yes">/etc/fonts/fonts.conf</include>'
        f'<dir>{FONTS}</dir><cachedir>{cache}</cachedir></fontconfig>')
    os.environ['FONTCONFIG_FILE'] = str(conf)


_private_fontconfig()  # must happen before Pango/Rsvg load fontconfig

import gi  # noqa: E402
gi.require_version('Rsvg', '2.0')
gi.require_version('Pango', '1.0')
gi.require_version('PangoCairo', '1.0')
from gi.repository import Pango, PangoCairo, Rsvg  # noqa: E402
import cairo  # noqa: E402
from PIL import Image, ImageChops  # noqa: E402

SVG_NS = 'http://www.w3.org/2000/svg'
ET.register_namespace('', SVG_NS)
LAYERS = ('background', 'foreground', 'monochrome')

DIRECTIONS = {
    'a': ('icon_a_seal.svg', 'A «الختم»', 'حلقة + هلال + كتاب — الأقرب للحالية'),
    'b': ('icon_b_noor.svg', 'B «نور»', 'من غير حلقة — العناصر أكبر'),
    'c': ('icon_c_hills.svg', 'C «الطبقات»', 'نور طالع ورا تلال ورقية'),
}
RECOMMENDED = 'c'  # خالد اختار C «الطبقات» 2026-10-15

PALETTE = dict(E='#0F6B5C', E2='#12806D', E3='#0D6A5A', SH='#094A40', DECO='#13806C', IV='#FBF1DE',
               IV2='#EADBC0', IV3='#D9C7A7', CORAL='#F4A492', GOLD='#F7C548', G1='#7ED3A6', G2='#A8E6C4',
               INK='#0F3D36')
CURRENT_BG = '#01696F'  # values/colors.xml ic_launcher_background (the shipped icon)


# ---------------------------------------------------------------- rendering

def _rgb(hexcol):
    h = hexcol.lstrip('#')
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def svg_surface(svg_text, w, h=None, viewport=None):
    h = h or w
    handle = Rsvg.Handle.new_from_data(svg_text.encode('utf-8'))
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
    ctx = cairo.Context(surf)
    r = Rsvg.Rectangle()
    r.x, r.y, r.width, r.height = viewport or (0, 0, w, h)
    handle.render_document(ctx, r)
    surf.flush()
    return surf


def surface_to_pil(surf):
    buf = io.BytesIO()
    surf.write_to_png(buf)
    buf.seek(0)
    return Image.open(buf).convert('RGBA')


def pil_to_surface(img):
    buf = io.BytesIO()
    img.save(buf, 'PNG')
    buf.seek(0)
    return cairo.ImageSurface.create_from_png(buf)


def layer_svg(path, layers):
    """The icon source with only `layers` visible."""
    root = ET.parse(path).getroot()
    for g in root.findall(f'{{{SVG_NS}}}g'):
        if g.get('id') in LAYERS:
            if g.get('id') in layers:
                g.attrib.pop('display', None)
            else:
                g.set('display', 'none')
    return ET.tostring(root, encoding='unicode')


def icon_surface(direction, px, layers=('background', 'foreground')):
    return svg_surface(layer_svg(ICON_DIR / DIRECTIONS[direction][0], layers), px)


def current_icon_surface(px):
    """The shipped adaptive icon, rebuilt the way the launcher draws it.

    mipmap-anydpi-v26/ic_launcher.xml = colour #01696F + ic_launcher_foreground.png
    inset 16%. In the 72dp visible window that drawable spans -1%..101%.
    """
    fg = Image.open(RES / 'drawable-xxxhdpi' / 'ic_launcher_foreground.png').convert('RGBA')
    size = round(px * 73.44 / 72)
    off = round(px * (17.28 - 18) / 72)
    img = Image.new('RGBA', (px, px), CURRENT_BG)
    fg = fg.resize((size, size), Image.LANCZOS)
    img.alpha_composite(fg, (max(off, 0), max(off, 0)), (max(-off, 0), max(-off, 0)))
    return pil_to_surface(img)


def mask_path(ctx, kind, x, y, s):
    ctx.new_path()
    if kind == 'circle':
        ctx.arc(x + s / 2, y + s / 2, s / 2, 0, 2 * math.pi)
    elif kind == 'rounded':  # rounded square (Play listing, many OEM launchers)
        r = 0.22 * s
        ctx.move_to(x + r, y)
        ctx.arc(x + s - r, y + r, r, -math.pi / 2, 0)
        ctx.arc(x + s - r, y + s - r, r, 0, math.pi / 2)
        ctx.arc(x + r, y + s - r, r, math.pi / 2, math.pi)
        ctx.arc(x + r, y + r, r, math.pi, 1.5 * math.pi)
        ctx.close_path()
    elif kind == 'squircle':  # superellipse n=4 (One UI / OxygenOS style)
        n = 4.0
        for i in range(361):
            t = 2 * math.pi * i / 360
            ct, st = math.cos(t), math.sin(t)
            px_ = math.copysign(abs(ct) ** (2 / n), ct)
            py_ = math.copysign(abs(st) ** (2 / n), st)
            (ctx.move_to if i == 0 else ctx.line_to)(x + s / 2 + px_ * s / 2, y + s / 2 + py_ * s / 2)
        ctx.close_path()
    elif kind == 'square':
        ctx.rectangle(x, y, s, s)
    else:
        raise ValueError(kind)


def draw_masked(ctx, surf, x, y, s, kind):
    ctx.save()
    mask_path(ctx, kind, x, y, s)
    ctx.clip()
    ctx.set_source_surface(surf, x, y)
    ctx.paint()
    ctx.restore()


def text(ctx, s, x, y, size, color, weight='Bold', anchor='middle', alpha=1.0):
    """Draw text with its top at y. anchor: middle / right / left (x is that edge)."""
    layout = PangoCairo.create_layout(ctx)
    fd = Pango.FontDescription.from_string(f'Cairo {weight}')
    fd.set_absolute_size(size * Pango.SCALE)
    layout.set_font_description(fd)
    layout.set_text('\u200f' + s, -1)  # RLM: an Arabic paragraph even when it opens with Latin («B …»)
    w = layout.get_pixel_extents()[1].width
    dx = {'middle': -w / 2, 'right': -w, 'left': 0}[anchor]
    ctx.save()
    ctx.set_source_rgba(*_rgb(color), alpha)
    ctx.move_to(x + dx, y)
    PangoCairo.show_layout(ctx, layout)
    ctx.restore()
    return w


def wallpaper(ctx, x, y, w, h):
    """A busy, photo-like wallpaper (review board only) — the hard case for icons."""
    ctx.save()
    ctx.rectangle(x, y, w, h)
    ctx.clip()
    g = cairo.LinearGradient(x, y, x + w, y + h)
    for stop, col in ((0, '#2E4A7A'), (0.45, '#B86B77'), (0.75, '#E9A76B'), (1, '#F3D9A4')):
        g.add_color_stop_rgb(stop, *_rgb(col))
    ctx.set_source(g)
    ctx.paint()
    for cx, cy, r, col, a in ((0.2, 0.15, 0.35, '#6FB7C9', 0.55), (0.75, 0.35, 0.3, '#F4E3B2', 0.5),
                              (0.4, 0.8, 0.4, '#3C7F6B', 0.55), (0.9, 0.9, 0.25, '#FFFFFF', 0.35)):
        rg = cairo.RadialGradient(x + cx * w, y + cy * h, 0, x + cx * w, y + cy * h, r * max(w, h))
        rg.add_color_stop_rgba(0, *_rgb(col), a)
        rg.add_color_stop_rgba(1, *_rgb(col), 0)
        ctx.set_source(rg)
        ctx.paint()
    ctx.restore()


# ---------------------------------------------------------------- review boards

ROWS = [('current', 'الحالية', 'على Play دلوقتي')] + [(k, v[1], v[2]) for k, v in DIRECTIONS.items()]


def _row_icon(key, px, layers=('background', 'foreground')):
    return current_icon_surface(px) if key == 'current' else icon_surface(key, px, layers)


def _row_label(ctx, key, title, sub, x_right, y_mid):
    rec = key == RECOMMENDED
    text(ctx, title + ('  ★ المُوصى به' if rec else ''), x_right, y_mid - 34, 26,
         '#B7791F' if rec else '#1F2D2A', 'Bold', 'right')
    text(ctx, sub, x_right, y_mid + 6, 17, '#5B6B66', 'Medium', 'right')


def board_sizes(out):
    sizes = (192, 96, 48)
    pad, gap = 28, 26
    group_w = pad * 2 + sum(sizes) + gap * (len(sizes) - 1)
    label_w, margin, head, row_h, foot = 300, 24, 150, 250, 70
    groups = [('خلفية فاتحة', 'light'), ('خلفية داكنة', 'dark'), ('ورق حائط', 'wall')]
    W = margin * 2 + label_w + group_w * len(groups)
    H = head + row_h * len(ROWS) + foot
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    ctx = cairo.Context(surf)
    ctx.set_source_rgb(*_rgb('#FFFFFF'))
    ctx.paint()
    text(ctx, 'أيقونة المربّي بالورق المقصوص — ٣ اتجاهات للمراجعة', W - margin, 22, 34, '#0F3D36', 'Bold', 'right')
    text(ctx, 'كل أيقونة بحجمها الحقيقي بالبكسل (١:١) وبقناع الدايرة بتاع Pixel — 192 / 96 / 48', W - margin, 74, 19,
         '#5B6B66', 'Medium', 'right')
    for gi_, (gname, kind) in enumerate(groups):
        gx = W - margin - label_w - group_w * (gi_ + 1)
        gy = head - 10
        if kind == 'light':
            ctx.set_source_rgb(*_rgb('#F1F3F1'))
            ctx.rectangle(gx, gy, group_w, row_h * len(ROWS))
            ctx.fill()
        elif kind == 'dark':
            ctx.set_source_rgb(*_rgb('#121413'))
            ctx.rectangle(gx, gy, group_w, row_h * len(ROWS))
            ctx.fill()
        else:
            wallpaper(ctx, gx, gy, group_w, row_h * len(ROWS))
        text(ctx, gname, gx + group_w / 2, head - 46, 20, '#1F2D2A', 'Bold')
        for ri, (key, _, _) in enumerate(ROWS):
            y0 = head + ri * row_h
            x = gx + group_w - pad
            for s in sizes:
                x -= s
                draw_masked(ctx, _row_icon(key, s), x, y0 + (row_h - 20 - s) / 2, s, 'circle')
                if ri == len(ROWS) - 1:
                    text(ctx, f'{s}px', x + s / 2, head + row_h * len(ROWS) - 4, 15, '#5B6B66', 'SemiBold')
                x -= gap
    for ri, (key, title, sub) in enumerate(ROWS):
        y_mid = head + ri * row_h + (row_h - 20) / 2
        _row_label(ctx, key, title, sub, W - margin, y_mid)
        if ri:
            ctx.set_source_rgba(0, 0, 0, 0.08)
            ctx.rectangle(margin, head + ri * row_h - 10, W - 2 * margin, 1)
            ctx.fill()
    text(ctx, 'الأحجام دي بالبكسل مش dp: 48px ≈ أيقونة المتجر في القوايم، 192px ≈ الأيقونة على شاشة xxxhdpi.',
         W - margin, H - foot + 24, 16, '#5B6B66', 'Medium', 'right')
    surf.write_to_png(str(out))


def board_masks(out):
    s, cell, label_w, margin, head, foot = 160, 216, 300, 24, 170, 80
    cols = [('دايرة', 'circle', None), ('مربّع مدوّر', 'rounded', None), ('squircle', 'squircle', None),
            ('Android 13 themed — فاتح', 'circle', ('#DCEBE4', '#1C4A3F')),
            ('Android 13 themed — داكن', 'circle', ('#22302B', '#B9E4D2'))]
    W = margin * 2 + label_w + cell * len(cols)
    H = head + cell * len(ROWS) + foot
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    ctx = cairo.Context(surf)
    ctx.set_source_rgb(1, 1, 1)
    ctx.paint()
    text(ctx, 'نفس الأيقونات تحت أقنعة Android المختلفة + الأيقونة أحادية اللون (Android 13)', W - margin, 22, 30,
         '#0F3D36', 'Bold', 'right')
    text(ctx, 'المشغّل هو اللي بيقصّ الشكل — الأيقونة لازم تفضل مفهومة في كله. الحجم 160px.', W - margin, 70, 19,
         '#5B6B66', 'Medium', 'right')
    ctx.set_source_rgb(*_rgb('#F1F3F1'))
    ctx.rectangle(margin, head - 20, W - 2 * margin - label_w, cell * len(ROWS))
    ctx.fill()
    for ci, (cname, kind, themed) in enumerate(cols):
        cx = W - margin - label_w - cell * (ci + 1)
        text(ctx, cname, cx + cell / 2, head - 62, 17, '#1F2D2A', 'Bold')
        for ri, (key, _, _) in enumerate(ROWS):
            x, y = cx + (cell - s) / 2, head + ri * cell + (cell - 40 - s) / 2
            if themed is None:
                draw_masked(ctx, _row_icon(key, s), x, y, s, kind)
            elif key == 'current':
                draw_masked(ctx, _row_icon(key, s), x, y, s, kind)
                text(ctx, 'مافيش أحادية — بتفضل ملوّنة', cx + cell / 2, y + s + 2, 13, '#9A3B2E', 'SemiBold')
            else:
                bg, fgc = themed
                ctx.save()
                mask_path(ctx, 'circle', x, y, s)
                ctx.clip()
                ctx.set_source_rgb(*_rgb(bg))
                ctx.paint()
                ctx.set_source_rgb(*_rgb(fgc))
                ctx.mask_surface(icon_surface(key, s, ('monochrome',)), x, y)
                ctx.restore()
    for ri, (key, title, sub) in enumerate(ROWS):
        _row_label(ctx, key, title, sub, W - margin, head + ri * cell + (cell - 40) / 2)
    text(ctx, 'الأحادية بتتلوّن من ألوان خلفية الموبايل؛ اللونين هنا مثال بس.', W - margin, H - foot + 26, 16,
         '#5B6B66', 'Medium', 'right')
    surf.write_to_png(str(out))


def board_home(out):
    """Recommended vs current, on a home screen at real launcher scale (xxhdpi, 60dp ≈ 144px... shown at 1/2)."""
    W, H = 1240, 1010
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    ctx = cairo.Context(surf)
    ctx.set_source_rgb(1, 1, 1)
    ctx.paint()
    text(ctx, 'على الشاشة الرئيسية — الحالية يمين، المُوصى به شمال', W - 24, 20, 30, '#0F3D36', 'Bold', 'right')
    phones = [('current', 'الحالية'), (RECOMMENDED, DIRECTIONS[RECOMMENDED][1])]
    others = ['#4285F4', '#34A853', '#FBBC05', '#EA4335', '#7E57C2', '#26A69A', '#EC407A', '#8D6E63',
              '#5C6BC0', '#29B6F6', '#FF7043', '#9CCC65', '#78909C', '#AB47BC', '#FFCA28']
    for pi, (key, name) in enumerate(phones):
        px0 = W - 24 - 580 - pi * 610
        py0 = 80
        pw, ph = 560, 860
        ctx.save()
        ctx.new_path()
        r = 44
        ctx.arc(px0 + pw - r, py0 + r, r, -math.pi / 2, 0)
        ctx.arc(px0 + pw - r, py0 + ph - r, r, 0, math.pi / 2)
        ctx.arc(px0 + r, py0 + ph - r, r, math.pi / 2, math.pi)
        ctx.arc(px0 + r, py0 + r, r, math.pi, 1.5 * math.pi)
        ctx.close_path()
        ctx.clip()
        wallpaper(ctx, px0, py0, pw, ph)
        icon = 96
        colw = pw / 4
        k = 0
        for row in range(4):
            for col in range(4):
                cx = px0 + pw - colw * (col + 0.5)
                cy = py0 + 150 + row * 170
                if row == 1 and col == 1:
                    draw_masked(ctx, _row_icon(key, icon), cx - icon / 2, cy - icon / 2, icon, 'circle')
                    text(ctx, 'المربي الذكي', cx, cy + icon / 2 + 8, 17, '#FFFFFF', 'SemiBold')
                else:
                    ctx.set_source_rgb(*_rgb(others[k % len(others)]))
                    ctx.arc(cx, cy, icon / 2, 0, 2 * math.pi)
                    ctx.fill()
                    ctx.set_source_rgba(1, 1, 1, 0.85)
                    ctx.rectangle(cx - 30, cy + icon / 2 + 16, 60, 8)
                    ctx.fill()
                    k += 1
        ctx.restore()
        text(ctx, name, px0 + pw / 2, py0 + ph + 12, 22, '#1F2D2A', 'Bold')
    surf.write_to_png(str(out))


# ---------------------------------------------------------------- SVG -> VectorDrawable

PRESENTATION = ('fill', 'stroke', 'stroke-width', 'stroke-linecap', 'stroke-linejoin', 'fill-rule')
SHAPES = ('path', 'rect', 'circle', 'ellipse', 'polygon', 'polyline', 'line')


def _n(v):
    s = ('%.3f' % v).rstrip('0').rstrip('.')
    return '0' if s in ('-0', '') else s


def parse_transform(t):
    """translate()/scale() chain -> (s, tx, ty) with p' = s*p + t. Anything else is refused."""
    s, tx, ty = 1.0, 0.0, 0.0
    if not t:
        return s, tx, ty
    for fn, args in re.findall(r'(\w+)\s*\(([^)]*)\)', t):
        nums = [float(v) for v in re.split(r'[\s,]+', args.strip()) if v]
        if fn == 'translate':
            tx += s * nums[0]
            ty += s * (nums[1] if len(nums) > 1 else 0.0)
        elif fn == 'scale':
            if len(nums) > 1 and abs(nums[1] - nums[0]) > 1e-9:
                raise ValueError(f'non-uniform scale not supported: {t}')
            s *= nums[0]
        else:
            raise ValueError(f'transform {fn} not supported (only translate/scale): {t}')
    return s, tx, ty


def shape_to_d(el):
    tag = el.tag.split('}')[-1]
    g = lambda k, d=0.0: float(el.get(k, d))  # noqa: E731
    if tag == 'path':
        return el.get('d')
    if tag == 'circle':
        cx, cy, r = g('cx'), g('cy'), g('r')
        return f'M{_n(cx - r)} {_n(cy)} A{_n(r)} {_n(r)} 0 1 0 {_n(cx + r)} {_n(cy)} A{_n(r)} {_n(r)} 0 1 0 {_n(cx - r)} {_n(cy)} Z'
    if tag == 'ellipse':
        cx, cy, rx, ry = g('cx'), g('cy'), g('rx'), g('ry')
        return f'M{_n(cx - rx)} {_n(cy)} A{_n(rx)} {_n(ry)} 0 1 0 {_n(cx + rx)} {_n(cy)} A{_n(rx)} {_n(ry)} 0 1 0 {_n(cx - rx)} {_n(cy)} Z'
    if tag == 'rect':
        x, y, w, h = g('x'), g('y'), g('width'), g('height')
        rx = float(el.get('rx', el.get('ry', 0)))
        ry = float(el.get('ry', rx))
        if not rx:
            return f'M{_n(x)} {_n(y)} H{_n(x + w)} V{_n(y + h)} H{_n(x)} Z'
        return (f'M{_n(x + rx)} {_n(y)} H{_n(x + w - rx)} A{_n(rx)} {_n(ry)} 0 0 1 {_n(x + w)} {_n(y + ry)} '
                f'V{_n(y + h - ry)} A{_n(rx)} {_n(ry)} 0 0 1 {_n(x + w - rx)} {_n(y + h)} H{_n(x + rx)} '
                f'A{_n(rx)} {_n(ry)} 0 0 1 {_n(x)} {_n(y + h - ry)} V{_n(y + ry)} A{_n(rx)} {_n(ry)} 0 0 1 {_n(x + rx)} {_n(y)} Z')
    if tag in ('polygon', 'polyline'):
        nums = [v for v in re.split(r'[\s,]+', el.get('points').strip()) if v]
        pts = [f'{nums[i]} {nums[i + 1]}' for i in range(0, len(nums), 2)]
        return 'M' + ' L'.join(pts) + (' Z' if tag == 'polygon' else '')
    if tag == 'line':
        return f'M{el.get("x1")} {el.get("y1")} L{el.get("x2")} {el.get("y2")}'
    raise ValueError(tag)


def _vd_path(d, st, indent):
    attrs = [f'android:pathData="{d}"']
    fill = st.get('fill', '#000000')
    if fill != 'none':
        attrs.append(f'android:fillColor="{fill.upper()}"')
        if st.get('fill-rule') == 'evenodd':
            attrs.append('android:fillType="evenOdd"')
    stroke = st.get('stroke', 'none')
    if stroke != 'none':
        attrs.append(f'android:strokeColor="{stroke.upper()}"')
        attrs.append(f'android:strokeWidth="{st.get("stroke-width", "1")}"')
        if st.get('stroke-linecap', 'butt') != 'butt':
            attrs.append(f'android:strokeLineCap="{st["stroke-linecap"]}"')
        if st.get('stroke-linejoin', 'miter') != 'miter':
            attrs.append(f'android:strokeLineJoin="{st["stroke-linejoin"]}"')
    pad = ' ' * indent
    return f'{pad}<path\n' + ''.join(f'{pad}    {a}\n' for a in attrs[:-1]) + f'{pad}    {attrs[-1]} />\n'


def _vd_walk(el, style, indent, out):
    for child in el:
        if not isinstance(child.tag, str):
            continue
        tag = child.tag.split('}')[-1]
        if child.get('display') == 'none':
            continue
        if child.get('opacity') not in (None, '1'):
            raise ValueError('opacity is not supported in icon sources (VectorDrawable groups have no alpha)')
        st = dict(style)
        for k in PRESENTATION:
            if child.get(k) is not None:
                st[k] = child.get(k)
        s, tx, ty = parse_transform(child.get('transform'))
        wrap = (s, tx, ty) != (1.0, 0.0, 0.0)
        pad = ' ' * indent
        inner = indent + 4 if wrap else indent
        if wrap:
            out.append(f'{pad}<group android:translateX="{_n(tx)}" android:translateY="{_n(ty)}"'
                       f' android:scaleX="{_n(s)}" android:scaleY="{_n(s)}">\n')
        if tag == 'g':
            _vd_walk(child, st, inner, out)
        elif tag in SHAPES:
            out.append(_vd_path(shape_to_d(child), st, inner))
        else:
            raise ValueError(f'<{tag}> not allowed in icon sources')
        if wrap:
            out.append(f'{pad}</group>\n')


def layer_to_vd(direction, layer, comment):
    root = ET.parse(ICON_DIR / DIRECTIONS[direction][0]).getroot()
    g = next(x for x in root.findall(f'{{{SVG_NS}}}g') if x.get('id') == layer)
    g = ET.fromstring(ET.tostring(g))
    g.attrib.pop('display', None)
    body = []
    _vd_walk(g, {}, 8, body)
    # 240-unit design space = the 72dp visible window -> centred in the 108dp layer.
    return ('<?xml version="1.0" encoding="utf-8"?>\n'
            f'<!-- {comment}\n'
            f'     Generated by docs/brand/tools/brand_build.py from docs/brand/icon/{DIRECTIONS[direction][0]}\n'
            '     (layer "' + layer + '"). Edit the SVG and regenerate; do not hand-edit. -->\n'
            '<vector xmlns:android="http://schemas.android.com/apk/res/android"\n'
            '    android:width="108dp"\n    android:height="108dp"\n'
            '    android:viewportWidth="108"\n    android:viewportHeight="108">\n'
            '    <group android:translateX="18" android:translateY="18" android:scaleX="0.3" android:scaleY="0.3">\n'
            + ''.join(body) +
            '    </group>\n</vector>\n')


ANDROID_NS = '{http://schemas.android.com/apk/res/android}'


def vd_to_svg(vd_xml):
    """Inverse conversion, used only to verify the VectorDrawable draws what the SVG draws."""
    root = ET.fromstring(vd_xml)
    vw, vh = root.get(ANDROID_NS + 'viewportWidth'), root.get(ANDROID_NS + 'viewportHeight')

    def walk(el):
        out = ''
        for c in el:
            if c.tag == 'group':
                a = lambda k, d: c.get(ANDROID_NS + k, d)  # noqa: E731
                out += (f'<g transform="translate({a("translateX", "0")} {a("translateY", "0")}) '
                        f'scale({a("scaleX", "1")} {a("scaleY", "1")})">' + walk(c) + '</g>')
            elif c.tag == 'path':
                a = lambda k, d=None: c.get(ANDROID_NS + k, d)  # noqa: E731
                attrs = f'd="{a("pathData")}" fill="{a("fillColor", "none")}"'
                if a('fillType') == 'evenOdd':
                    attrs += ' fill-rule="evenodd"'
                if a('strokeColor'):
                    attrs += (f' stroke="{a("strokeColor")}" stroke-width="{a("strokeWidth", "1")}"'
                              f' stroke-linecap="{a("strokeLineCap", "butt")}" stroke-linejoin="{a("strokeLineJoin", "miter")}"')
                out += f'<path {attrs}/>'
        return out
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {vw} {vh}">{walk(root)}</svg>'


def _layer_in_108(direction, layer):
    root = ET.parse(ICON_DIR / DIRECTIONS[direction][0]).getroot()
    g = next(x for x in root.findall(f'{{{SVG_NS}}}g') if x.get('id') == layer)
    g.attrib.pop('display', None)
    inner = ET.tostring(g, encoding='unicode')
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 108 108">'
            f'<g transform="translate(18 18) scale(0.3)">{inner}</g></svg>')


def android(direction, verify_only=False):
    name = 'ic_launcher_paper'
    label = DIRECTIONS[direction][1]
    files = {}
    for layer in LAYERS:
        files[f'drawable/{name}_{layer}.xml'] = layer_to_vd(
            direction, layer, f'المربّي launcher icon, paper-cut direction {label} — {layer} layer.')
    adaptive = ('<?xml version="1.0" encoding="utf-8"?>\n'
                '<!-- Paper-cut launcher icon (docs/brand/). Android 13+ tints the monochrome layer\n'
                '     for themed icons. Generated by docs/brand/tools/brand_build.py. -->\n'
                '<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">\n'
                f'    <background android:drawable="@drawable/{name}_background" />\n'
                f'    <foreground android:drawable="@drawable/{name}_foreground" />\n'
                f'    <monochrome android:drawable="@drawable/{name}_monochrome" />\n'
                '</adaptive-icon>\n')
    files[f'mipmap-anydpi-v26/{name}.xml'] = adaptive
    files[f'mipmap-anydpi-v26/{name}_round.xml'] = adaptive

    # Verification 1: each VectorDrawable, drawn back, matches its SVG layer pixel for pixel.
    worst = 0
    for layer in LAYERS:
        a = surface_to_pil(svg_surface(_layer_in_108(direction, layer), 432))
        b = surface_to_pil(svg_surface(vd_to_svg(files[f'drawable/{name}_{layer}.xml']), 432))
        diff = ImageChops.difference(a, b)
        mx = max(hi for _, hi in diff.getextrema())
        changed = sum(1 for p in diff.getdata() if max(p) > 16)
        worst = max(worst, changed)
        print(f'  verify {layer:<10} VD vs SVG: max channel diff {mx}, pixels off by >16: {changed}')
    if worst > 40:
        sys.exit('VectorDrawable does not match its SVG source — not writing anything')

    # Verification 2: aapt2 accepts every XML (compile only — no APK is linked).
    aapt2 = sorted((Path.home() / 'Android' / 'Sdk' / 'build-tools').glob('*/aapt2'))
    with tempfile.TemporaryDirectory() as tmp:
        for rel, body in files.items():
            p = Path(tmp) / 'res' / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(body, encoding='utf-8')
        if aapt2:
            for rel in files:
                r = subprocess.run([str(aapt2[-1]), 'compile', str(Path(tmp) / 'res' / rel), '-o', tmp],
                                   capture_output=True, text=True)
                if r.returncode != 0:
                    sys.exit(f'aapt2 compile rejected {rel}:\n{r.stderr}')
            print(f'  aapt2 compile ({aapt2[-1].parent.name}): {len(files)} XML files OK')
        else:
            print('  aapt2 not found — skipped the resource compile check')
    if verify_only:
        return

    for rel, body in files.items():
        (RES / rel).parent.mkdir(parents=True, exist_ok=True)
        (RES / rel).write_text(body, encoding='utf-8')
    # Legacy (API 24–25) launcher PNGs: rounded square + circle, full bleed.
    for dens, px in (('mdpi', 48), ('hdpi', 72), ('xhdpi', 96), ('xxhdpi', 144), ('xxxhdpi', 192)):
        full = icon_surface(direction, px)
        for suffix, kind in (('', 'rounded'), ('_round', 'circle')):
            s = cairo.ImageSurface(cairo.FORMAT_ARGB32, px, px)
            draw_masked(cairo.Context(s), full, 0, 0, px, kind)
            surface_to_pil(s).save(RES / f'mipmap-{dens}' / f'{name}{suffix}.png', optimize=True)
    print(f'  wrote {len(files)} XML + 10 PNG under {RES.relative_to(ROOT)}')


# ---------------------------------------------------------------- store art

FRAMES = ('frame_1_rising', 'frame_2_ivory', 'frame_3_bubble')
EXAMPLES = [  # (frame, screenshot, title, subtitle) — screenshots from docs/marketing (June UI) only show the fit
    ('frame_1_rising', 'docs/marketing/screenshots/raw/01_home.png', 'يومك مع طفلك', 'خطوة صغيرة كل يوم'),
    ('frame_2_ivory', 'docs/marketing/screenshots/raw/04_journey.png', 'رحلة طفلك', 'سجّل محطاته الإيمانية'),
    ('frame_3_bubble', 'docs/marketing/screenshots/raw/06_assistant.png', 'اسأل عن تربية طفلك', 'اكتب سؤالك كما يخطر لك'),
]


WEIGHTS = {'500': Pango.Weight.MEDIUM, '600': Pango.Weight.SEMIBOLD, '700': Pango.Weight.BOLD,
           '800': Pango.Weight.ULTRABOLD, '900': Pango.Weight.HEAVY}


def _fit_text(t):
    """Shrink a caption until it fits its data-max-width (a long title must not run off the frame)."""
    size = float(t.get('font-size'))
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 8, 8)
    layout = PangoCairo.create_layout(cairo.Context(surf))
    fd = Pango.FontDescription.from_string('Cairo')
    fd.set_weight(WEIGHTS.get(t.get('font-weight', '700'), Pango.Weight.BOLD))
    fd.set_absolute_size(size * Pango.SCALE)
    layout.set_font_description(fd)
    layout.set_text(t.text, -1)
    width = layout.get_pixel_extents()[1].width
    limit = float(t.get('data-max-width'))
    if width > limit:
        t.set('font-size', _n(size * limit / width))


def _frame_parts(svg_path, title=None, subtitle=None):
    root = ET.parse(svg_path).getroot()
    slot = root.find(f'.//{{{SVG_NS}}}rect[@id="slot"]')
    geo = tuple(float(slot.get(k)) for k in ('x', 'y', 'width', 'height', 'rx'))
    for t in root.iter(f'{{{SVG_NS}}}text'):
        if t.get('id') == 'title' and title is not None:
            t.text = title
        if t.get('id') == 'subtitle' and subtitle is not None:
            t.text = subtitle
        if t.get('data-max-width') and t.text:
            _fit_text(t)

    def only(keep):
        r = ET.fromstring(ET.tostring(root))
        for g in r.findall(f'{{{SVG_NS}}}g'):
            if g.get('id') in ('under', 'placeholder', 'over'):
                if g.get('id') in keep:
                    g.attrib.pop('display', None)
                else:
                    g.set('display', 'none')
        return ET.tostring(r, encoding='unicode')
    w, h = int(float(root.get('width'))), int(float(root.get('height')))
    return only, geo, (w, h)


def fill_frame(frame, shot, title, subtitle, out):
    only, (sx, sy, sw, sh, srx), (W, H) = _frame_parts(STORE_DIR / f'{frame}.svg', title, subtitle)
    surf = svg_surface(only(('under',)), W, H)
    ctx = cairo.Context(surf)
    img = Image.open(shot).convert('RGBA')
    scale = sw / img.width
    img = img.resize((round(img.width * scale), round(img.height * scale)), Image.LANCZOS)
    ctx.save()
    ctx.new_path()
    r = srx
    ctx.arc(sx + sw - r, sy + r, r, -math.pi / 2, 0)
    ctx.arc(sx + sw - r, sy + sh - r, r, 0, math.pi / 2)
    ctx.arc(sx + r, sy + sh - r, r, math.pi / 2, math.pi)
    ctx.arc(sx + r, sy + r, r, math.pi, 1.5 * math.pi)
    ctx.close_path()
    ctx.clip()
    ctx.set_source_surface(pil_to_surface(img), sx, sy)
    ctx.paint()
    ctx.restore()
    ctx.set_source_surface(svg_surface(only(('over',)), W, H), 0, 0)
    ctx.paint()
    surface_to_pil(surf).convert('RGB').save(out, optimize=True)


def store():
    fg = STORE_DIR / 'feature_graphic.svg'
    surface_to_pil(svg_surface(fg.read_text(), 1024, 500)).convert('RGB').save(
        STORE_DIR / 'feature_graphic.png', optimize=True)
    for f in FRAMES:
        only, _, (W, H) = _frame_parts(STORE_DIR / f'{f}.svg')
        surface_to_pil(svg_surface(only(('under', 'placeholder', 'over')), W, H)).convert('RGB').save(
            STORE_DIR / f'{f}.png', optimize=True)
    for f, shot, t, s in EXAMPLES:
        fill_frame(f, ROOT / shot, t, s, STORE_DIR / f'example_{f}.png')
    # Play hi-res icon: full square, Play applies its own rounded mask.
    surface_to_pil(icon_surface(RECOMMENDED, 512)).convert('RGB').save(STORE_DIR / 'play_icon_512.png', optimize=True)
    print('  store art written to', STORE_DIR.relative_to(ROOT))


FRONTEND = ROOT / 'frontend'
OG_IMAGE = FRONTEND / 'assets' / 'og_noor.png'
OG_SIZE = (1200, 630)
# name -> (px, maskable). Maskable icons get their art inside the 80% safe zone.
WEB_ICONS = {
    'icon-192.png': (192, False),
    'icon-512.png': (512, False),
    'icon-maskable-512.png': (512, True),
    'apple-touch-icon.png': (180, False),
    'favicon-32.png': (32, False),
}


def web():
    """og:image + PWA icons for the landing (frontend/), all from docs/brand/ SVG."""
    # The feature graphic is 1024x500 (2.05:1); og:image wants 1200x630 (1.9:1).
    # Fill the height and trim the sky at both sides — the crescent, the title and
    # the icon tile all sit inside the middle 1200 px.
    w, h = OG_SIZE
    fg = (STORE_DIR / 'feature_graphic.svg').read_text()
    full_w = 1024 * h / 500
    surf = svg_surface(fg, w, h, viewport=(-(full_w - w) / 2, 0, full_w, h))
    surface_to_pil(surf).convert('RGB').save(OG_IMAGE, optimize=True)
    icons = FRONTEND / 'icons'
    src = layer_svg(ICON_DIR / DIRECTIONS[RECOMMENDED][0], ('background', 'foreground'))
    for name, (px, maskable) in WEB_ICONS.items():
        if maskable:
            # The background layer overhangs the 240 box by 60 on every side, so a
            # wider viewBox shows more sky and hill, not a border: art at 80%.
            img = surface_to_pil(svg_surface(src.replace('viewBox="0 0 240 240"', 'viewBox="-30 -30 300 300"', 1), px))
        else:
            img = surface_to_pil(svg_surface(src, px))
        img.convert('RGB').save(icons / name, optimize=True)
    print('  web art written to', OG_IMAGE.relative_to(ROOT), 'and', icons.relative_to(ROOT))


# ---------------------------------------------------------------- cli

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('review')
    a = sub.add_parser('android')
    a.add_argument('direction', choices=sorted(DIRECTIONS))
    a.add_argument('--verify-only', action='store_true')
    sub.add_parser('store')
    sub.add_parser('web')
    fr = sub.add_parser('frame')
    fr.add_argument('--frame', choices=FRAMES, required=True)
    fr.add_argument('--shot', required=True, help='screenshot PNG, e.g. from the CI e2e-gallery artifact')
    fr.add_argument('--title', required=True)
    fr.add_argument('--subtitle', default='')
    fr.add_argument('--out', required=True)
    args = ap.parse_args()
    if args.cmd == 'review':
        REVIEW_DIR.mkdir(parents=True, exist_ok=True)
        board_sizes(REVIEW_DIR / 'icon_compare_sizes.png')
        board_masks(REVIEW_DIR / 'icon_compare_masks.png')
        board_home(REVIEW_DIR / 'icon_home_screen.png')
        print('  boards written to', REVIEW_DIR.relative_to(ROOT))
    elif args.cmd == 'android':
        android(args.direction, args.verify_only)
    elif args.cmd == 'store':
        store()
    elif args.cmd == 'web':
        web()
    elif args.cmd == 'frame':
        fill_frame(args.frame, args.shot, args.title, args.subtitle, args.out)
        print('  wrote', args.out)


if __name__ == '__main__':
    main()
