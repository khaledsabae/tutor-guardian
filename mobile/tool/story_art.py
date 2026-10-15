#!/usr/bin/env python3
"""«ورق مقصوص» — the story scenes' cut-paper pieces, written as SVG.

Run from mobile/:  python3 tool/story_art.py
Writes assets/svg/stories/bg_*.svg (360×240 backdrops) and assets/svg/stories/
*.svg (240×240 props). The reader composes a page from one backdrop and a few
props (lib/features/stories/scene/story_scene_catalog.dart) and moves them as
separate paper layers — which is why they are pieces and not finished pictures.

Rules are assets/svg/STYLE.md's: flat palette colours only, a solid offset
paper shadow (never blur), no text, no gradients, no <use>/<clipPath>/<filter>,
humans without facial features beyond closed-eye arcs, modest dress.

The shadow under a free-standing prop falls on whatever backdrop it is placed
over — ivory by day, emerald by night — so it is the ink at low opacity rather
than either surface's own shadow colour: it darkens both grounds the same way.
"""
from __future__ import annotations

import math
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "assets" / "svg" / "stories"

# STYLE.md palette — nothing else.
EMERALD = "#0F6B5C"
HILL = "#12806D"
HILL_DEEP = "#0D6A5A"
SHADOW_EM = "#094A40"
STAR_EM = "#13806C"
IVORY = "#FBF1DE"
IVORY_D = "#EADBC0"
IVORY_S = "#D9C7A7"
CORAL = "#F4A492"
GOLD = "#F7C548"
LEAF = "#7ED3A6"
LEAF_L = "#A8E6C4"
INK = "#0F3D36"

SKIN = CORAL


def f(v: float) -> str:
    s = f"{v:.1f}"
    return s[:-2] if s.endswith(".0") else s


# ── primitives: each returns an SVG fragment string ─────────────────────────
def rect(x, y, w, h, fill, rx=0, extra=""):
    r = f' rx="{f(rx)}"' if rx else ""
    return f'<rect x="{f(x)}" y="{f(y)}" width="{f(w)}" height="{f(h)}"{r} fill="{fill}"{extra}/>'


def circle(cx, cy, r, fill, extra=""):
    return f'<circle cx="{f(cx)}" cy="{f(cy)}" r="{f(r)}" fill="{fill}"{extra}/>'


def ellipse(cx, cy, rx, ry, fill, extra=""):
    return f'<ellipse cx="{f(cx)}" cy="{f(cy)}" rx="{f(rx)}" ry="{f(ry)}" fill="{fill}"{extra}/>'


def path(d, fill, extra=""):
    return f'<path d="{d}" fill="{fill}"{extra}/>'


def poly(points, fill, extra=""):
    pts = " ".join(f"{f(x)},{f(y)}" for x, y in points)
    return f'<polygon points="{pts}" fill="{fill}"{extra}/>'


def stroke(d, color=INK, width=2.6):
    return (f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{f(width)}" '
            f'stroke-linecap="round" stroke-linejoin="round"/>')


def line(x1, y1, x2, y2, color=INK, width=2.6):
    return (f'<line x1="{f(x1)}" y1="{f(y1)}" x2="{f(x2)}" y2="{f(y2)}" stroke="{color}" '
            f'stroke-width="{f(width)}" stroke-linecap="round"/>')


def star8(cx, cy, r, fill, inner=0.45):
    pts = []
    for i in range(16):
        a = -math.pi / 2 + i * math.pi / 8
        rr = r if i % 2 == 0 else r * inner
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    return poly(pts, fill)


def crescent(cx, cy, r, fill, cut=0.82, dx=0.42, dy=-0.30):
    """A crescent as one path: outer circle minus an offset inner circle."""
    r2 = r * cut
    ox, oy = cx + r * dx, cy + r * dy
    # Intersections of the two circles.
    d = math.hypot(ox - cx, oy - cy)
    a = (r * r - r2 * r2 + d * d) / (2 * d)
    h = math.sqrt(max(r * r - a * a, 0))
    mx, my = cx + a * (ox - cx) / d, cy + a * (oy - cy) / d
    p1 = (mx + h * (oy - cy) / d, my - h * (ox - cx) / d)
    p2 = (mx - h * (oy - cy) / d, my + h * (ox - cx) / d)
    dd = (f"M{f(p1[0])} {f(p1[1])} A{f(r)} {f(r)} 0 1 0 {f(p2[0])} {f(p2[1])} "
          f"A{f(r2)} {f(r2)} 0 0 1 {f(p1[0])} {f(p1[1])} Z")
    return path(dd, fill)


def shadow(*frags, dx=4, dy=5, color=INK, opacity=0.22):
    """The paper shadow: the same silhouette, offset, as one translucent sheet
    (group opacity, so overlapping pieces do not darken twice)."""
    inner = "".join(frags)
    # Re-colour every fill in the silhouette to the shadow colour.
    import re
    inner = re.sub(r'fill="#[0-9A-Fa-f]{6}"', f'fill="{color}"', inner)
    inner = re.sub(r'stroke="#[0-9A-Fa-f]{6}"', f'stroke="{color}"', inner)
    return f'<g transform="translate({f(dx)} {f(dy)})" opacity="{opacity}">{inner}</g>'


def solid_shadow(color, *frags, dx=4, dy=5):
    """A solid paper shadow in a palette colour (for pieces on a known ground)."""
    import re
    inner = "".join(frags)
    inner = re.sub(r'fill="#[0-9A-Fa-f]{6}"', f'fill="{color}"', inner)
    return f'<g transform="translate({f(dx)} {f(dy)})">{inner}</g>'


def piece(*frags):
    """A free-standing prop: translucent shadow, then the paper."""
    return shadow(*frags) + "".join(frags)


def svg(body: str, w=240, h=240) -> str:
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}">{body}</svg>'


# ── people ──────────────────────────────────────────────────────────────────
def eyes(cx, cy, spread=7.0, size=4.2, width=2.4):
    return (stroke(f"M{f(cx - spread - size)} {f(cy)} Q{f(cx - spread)} {f(cy - size * 1.3)} "
                   f"{f(cx - spread + size)} {f(cy)}", INK, width)
            + stroke(f"M{f(cx + spread - size)} {f(cy)} Q{f(cx + spread)} {f(cy - size * 1.3)} "
                     f"{f(cx + spread + size)} {f(cy)}", INK, width))


def robe(cx, top, bottom, shoulder, hem, fill):
    """A long garment: rounded shoulders, gently flared hem."""
    return path(
        f"M{f(cx - shoulder)} {f(top + 10)} Q{f(cx - shoulder)} {f(top)} {f(cx - shoulder + 10)} {f(top)} "
        f"L{f(cx + shoulder - 10)} {f(top)} Q{f(cx + shoulder)} {f(top)} {f(cx + shoulder)} {f(top + 10)} "
        f"L{f(cx + hem)} {f(bottom)} Q{f(cx)} {f(bottom + 5)} {f(cx - hem)} {f(bottom)} Z", fill)


def arm(x_sh, y_sh, x_hand, y_hand, fill, w=9.0):
    """An arm as a thick rounded segment (polygon + round ends)."""
    ang = math.atan2(y_hand - y_sh, x_hand - x_sh)
    nx, ny = -math.sin(ang) * w / 2, math.cos(ang) * w / 2
    return (poly([(x_sh + nx, y_sh + ny), (x_hand + nx, y_hand + ny),
                  (x_hand - nx, y_hand - ny), (x_sh - nx, y_sh - ny)], fill)
            + circle(x_sh, y_sh, w / 2, fill))


def person(kind: str, cloth: str, cloth2: str, head_cover: str | None = None,
           beard: bool = False, hair: bool = False, kufi: str | None = None,
           arms: str = "down", cane: bool = False):
    """kind: child|adult. arms: down|out|up|hold|wave."""
    if kind == "child":
        cx, head_y, head_r, top, bottom, sh, hem, arm_len = 120, 104, 19, 128, 228, 22, 27, 52
    else:
        cx, head_y, head_r, top, bottom, sh, hem, arm_len = 120, 50, 22, 78, 228, 27, 33, 74
    parts = []
    # feet
    parts.append(ellipse(cx - 10, bottom + 2, 9, 4.5, SHADOW_EM))
    parts.append(ellipse(cx + 10, bottom + 2, 9, 4.5, SHADOW_EM))
    # arms (behind the body when down)
    ys = top + 9
    if arms == "down":
        hands = [(cx - sh - 4, ys + arm_len * .78), (cx + sh + 4, ys + arm_len * .78)]
    elif arms == "out":
        hands = [(cx - sh - 26, ys + arm_len * .55), (cx + sh + 26, ys + arm_len * .55)]
    elif arms == "up":
        hands = [(cx - sh - 16, ys - arm_len * .55), (cx + sh + 16, ys - arm_len * .55)]
    elif arms == "hold":
        hands = [(cx - 12, ys + arm_len * .52), (cx + 12, ys + arm_len * .52)]
    elif arms == "wave":
        hands = [(cx - sh - 4, ys + arm_len * .78), (cx + sh + 18, ys - arm_len * .5)]
    else:
        raise ValueError(arms)
    arm_parts = []
    for (hx, hy), side in zip(hands, (-1, 1)):
        arm_parts.append(arm(cx + side * (sh - 6), ys, hx, hy, cloth2 if cloth2 else cloth, 10))
        arm_parts.append(circle(hx, hy, 5.6, SKIN))
    if arms in ("down", "out", "up", "wave"):
        parts.extend(arm_parts)
    parts.append(robe(cx, top, bottom, sh, hem, cloth))
    if cane:
        parts.append(rect(cx + sh + 14, ys + 30, 4, bottom - ys - 28, IVORY_S, 2))
        parts.append(path(f"M{f(cx + sh + 16)} {f(ys + 32)} q0 -10 -9 -10", "none",
                          f' stroke="{IVORY_S}" stroke-width="4" stroke-linecap="round"'))
    if arms == "hold":
        parts.extend(arm_parts)
    # neck + head
    parts.append(rect(cx - 5, head_y + head_r - 4, 10, top - head_y - head_r + 6, SKIN))
    if head_cover:
        # khimar: an oval hood around the face, falling to the shoulders.
        hr = head_r + 7
        parts.append(path(
            f"M{f(cx - hr)} {f(head_y)} A{f(hr)} {f(hr)} 0 0 1 {f(cx + hr)} {f(head_y)} "
            f"L{f(cx + sh + 2)} {f(top + 22)} Q{f(cx)} {f(top + 30)} {f(cx - sh - 2)} {f(top + 22)} Z",
            head_cover))
    parts.append(circle(cx, head_y, head_r, SKIN))
    if hair:
        parts.append(path(f"M{f(cx - head_r)} {f(head_y - 2)} A{f(head_r)} {f(head_r)} 0 0 1 "
                          f"{f(cx + head_r)} {f(head_y - 2)} Q{f(cx + 6)} {f(head_y - head_r * .55)} "
                          f"{f(cx - head_r)} {f(head_y - 2)} Z", INK))
    if kufi:
        parts.append(path(f"M{f(cx - head_r * .92)} {f(head_y - head_r * .38)} A{f(head_r * .95)} "
                          f"{f(head_r * .8)} 0 0 1 {f(cx + head_r * .92)} {f(head_y - head_r * .38)} Z", kufi))
    if beard:
        parts.append(path(f"M{f(cx - head_r)} {f(head_y + 2)} Q{f(cx - head_r + 2)} {f(head_y + head_r + 12)} "
                          f"{f(cx)} {f(head_y + head_r + 14)} Q{f(cx + head_r - 2)} {f(head_y + head_r + 12)} "
                          f"{f(cx + head_r)} {f(head_y + 2)} Q{f(cx)} {f(head_y + head_r - 2)} "
                          f"{f(cx - head_r)} {f(head_y + 2)} Z", INK))
    body = "".join(parts)
    face = eyes(cx, head_y + (2 if not beard else -1), spread=head_r * .36, size=head_r * .2,
                width=2.4 if kind == "child" else 2.6)
    if head_cover:
        # The hood's own inner fold, a shade deeper, so the face sits inside it.
        pass
    return shadow(body) + body + face


PEOPLE = {
    "boy": lambda: person("child", IVORY, IVORY_D, kufi=HILL_DEEP),
    "boy_wave": lambda: person("child", IVORY, IVORY_D, kufi=HILL_DEEP, arms="wave"),
    "boy_hold": lambda: person("child", IVORY, IVORY_D, kufi=HILL_DEEP, arms="hold"),
    "boy_up": lambda: person("child", IVORY, IVORY_D, kufi=HILL_DEEP, arms="up"),
    "boy_friend": lambda: person("child", LEAF, HILL, hair=True),
    "boy_friend_out": lambda: person("child", LEAF, HILL, hair=True, arms="out"),
    "boy_friend2": lambda: person("child", IVORY_D, IVORY_S, hair=True),
    "girl": lambda: person("child", HILL, HILL_DEEP, head_cover=IVORY),
    "girl_wave": lambda: person("child", HILL, HILL_DEEP, head_cover=IVORY, arms="wave"),
    "girl_hold": lambda: person("child", HILL, HILL_DEEP, head_cover=IVORY, arms="hold"),
    "girl_up": lambda: person("child", HILL, HILL_DEEP, head_cover=IVORY, arms="up"),
    "girl_friend": lambda: person("child", IVORY, IVORY_D, head_cover=LEAF_L),
    "girl_friend_hold": lambda: person("child", IVORY, IVORY_D, head_cover=LEAF_L, arms="hold"),
    "mother": lambda: person("adult", HILL_DEEP, SHADOW_EM, head_cover=IVORY_D),
    "mother_out": lambda: person("adult", HILL_DEEP, SHADOW_EM, head_cover=IVORY_D, arms="out"),
    "father": lambda: person("adult", IVORY, IVORY_D, beard=True, kufi=IVORY_D),
    "father_out": lambda: person("adult", IVORY, IVORY_D, beard=True, kufi=IVORY_D, arms="out"),
    "grandma": lambda: person("adult", SHADOW_EM, HILL_DEEP, head_cover=IVORY, cane=True),
    "man": lambda: person("adult", LEAF_L, HILL, hair=True, beard=True),
    "teacher": lambda: person("adult", HILL, HILL_DEEP, head_cover=LEAF_L),
}


# ── animals & nature ────────────────────────────────────────────────────────
def kitten():
    """A small ginger cat, sitting — coral so it reads on ivory and emerald."""
    b = [
        path("M78 206 Q70 150 112 146 Q156 146 160 204 Q160 222 120 222 Q80 222 78 206 Z", CORAL),
        path("M150 200 Q190 196 186 160 Q184 150 176 156 Q178 186 148 188 Z", CORAL),  # tail
        circle(122, 128, 30, CORAL),
        poly([(96, 116), (98, 86), (116, 104)], CORAL),
        poly([(148, 116), (146, 86), (128, 104)], CORAL),
        poly([(101, 110), (102, 95), (111, 104)], IVORY),
        poly([(143, 110), (142, 95), (133, 104)], IVORY),
        path("M100 182 Q120 170 140 182 L140 214 Q120 220 100 214 Z", IVORY),  # chest
        path("M112 104 L118 98 L126 98 L132 104 Q122 100 112 104 Z", IVORY_D),
        path("M150 168 Q160 166 164 174 L160 178 Q156 172 150 174 Z", IVORY_D),
        ellipse(104, 220, 11, 6, IVORY), ellipse(136, 220, 11, 6, IVORY),
    ]
    face = (eyes(122, 128, spread=10, size=4.5) + circle(122, 137, 2.6, INK)
            + stroke("M108 140 L94 137", INK, 1.6) + stroke("M136 140 L150 137", INK, 1.6))
    return piece(*b) + face


def bird():
    b = [
        ellipse(118, 130, 34, 26, LEAF),
        path("M92 130 L60 118 L70 138 Z", LEAF),  # tail
        circle(146, 112, 18, LEAF),
        poly([(162, 110), (180, 115), (162, 120)], CORAL),
        path("M100 126 Q122 104 140 128 Q122 140 100 126 Z", HILL),  # wing
        rect(112, 154, 3, 14, SHADOW_EM), rect(124, 154, 3, 14, SHADOW_EM),
    ]
    return piece(*b) + stroke("M144 110 Q148 106 152 110", INK, 2.4)


def ant():
    b = [
        ellipse(92, 160, 16, 12, INK), circle(116, 156, 9, INK), circle(134, 150, 10, INK),
        circle(150, 126, 20, GOLD),  # the grain, bigger than the ant
        path("M140 142 Q148 138 150 132", "none", f' stroke="{INK}" stroke-width="3" stroke-linecap="round"'),
    ]
    legs = "".join(stroke(f"M{x} 160 l{dx} 16", INK, 2.6) for x, dx in ((88, -8), (100, -2), (114, 6), (120, 10)))
    return piece(*b) + legs


def tree(fill=HILL, fill2=LEAF, nest=False):
    b = [rect(110, 130, 20, 100, IVORY_S, 4), circle(120, 96, 56, fill),
         circle(84, 118, 34, fill), circle(156, 118, 34, fill), circle(108, 80, 30, fill2)]
    out = piece(*b)
    for cx, cy in ((92, 104), (146, 92), (132, 128)):
        out += circle(cx, cy, 5, LEAF_L)
    if nest:
        n = [path("M138 74 Q156 92 174 74 Z", IVORY_S), rect(136, 70, 40, 6, IVORY_D, 3)]
        out += piece(*n)
    return out


def bush():
    b = [circle(90, 190, 30, HILL), circle(130, 180, 38, HILL), circle(168, 196, 26, HILL),
         rect(66, 196, 128, 32, HILL, 14)]
    return piece(*b) + circle(122, 168, 6, CORAL) + circle(152, 186, 5, IVORY) + circle(96, 182, 5, CORAL)


def flower(color=CORAL):
    stem = stroke("M120 228 Q118 180 120 128", HILL, 5)
    leaves = [path("M120 190 Q96 176 92 158 Q114 164 120 186 Z", LEAF),
              path("M120 172 Q146 160 150 140 Q126 146 120 168 Z", LEAF)]
    petals = [circle(120 + 18 * math.cos(a), 112 + 18 * math.sin(a), 14, color)
              for a in [i * math.pi * 2 / 6 for i in range(6)]]
    return shadow(*leaves, *petals) + stem + "".join(leaves) + "".join(petals) + circle(120, 112, 11, GOLD)


def sprout(stage: int):
    soil = [ellipse(120, 214, 62, 18, IVORY_S), path("M58 214 Q120 186 182 214 Z", IVORY_D)]
    out = piece(*soil)
    if stage == 0:  # the golden seed
        out += piece(ellipse(120, 200, 11, 8, GOLD))
    elif stage == 1:
        out += stroke("M120 204 Q120 186 120 172", HILL, 5)
        out += piece(path("M120 176 Q100 160 92 168 Q102 184 120 178 Z", LEAF),
                     path("M120 174 Q140 156 150 164 Q140 182 120 176 Z", LEAF))
    else:
        out += stroke("M120 206 Q116 160 120 104", HILL, 6)
        lv = []
        for y, side in ((176, -1), (156, 1), (136, -1), (116, 1)):
            lv.append(path(f"M120 {y} Q{120 + side * 26} {y - 20} {120 + side * 40} {y - 10} "
                           f"Q{120 + side * 26} {y + 8} 120 {y + 4} Z", LEAF))
        out += piece(*lv) + piece(circle(120, 98, 10, LEAF_L))
    return out


def basil(wilted: bool):
    pot = [path("M84 170 L156 170 L146 226 L94 226 Z", CORAL), rect(78, 162, 84, 14, CORAL, 4)]
    out = piece(*pot) + rect(78, 162, 84, 5, IVORY_D, 2)
    if wilted:
        stems = stroke("M120 164 Q118 140 104 128", HILL_DEEP, 5) + stroke("M122 164 Q130 142 146 136", HILL_DEEP, 5)
        lv = [path("M104 128 Q92 136 88 150 Q102 146 106 132 Z", IVORY_S),
              path("M146 136 Q158 146 160 160 Q146 154 144 140 Z", IVORY_S),
              path("M112 146 Q100 150 96 162 Q110 158 114 150 Z", IVORY_S)]
        return out + stems + piece(*lv)
    stems = stroke("M120 164 Q118 120 120 92", HILL, 5)
    lv = []
    for y, side in ((150, -1), (136, 1), (120, -1), (106, 1), (94, -1)):
        lv.append(ellipse(120 + side * 16, y, 16, 9, LEAF, f' transform="rotate({side * -24} {120 + side * 16} {y})"'))
    return out + stems + piece(*lv)


def cloud():
    b = [circle(92, 132, 24, IVORY), circle(124, 118, 32, IVORY), circle(158, 134, 22, IVORY),
         rect(70, 130, 110, 26, IVORY, 13)]
    return solid_shadow(IVORY_S, *b) + "".join(b)


def sun():
    rays = "".join(poly([(120 + 60 * math.cos(a - .12), 120 + 60 * math.sin(a - .12)),
                         (120 + 82 * math.cos(a), 120 + 82 * math.sin(a)),
                         (120 + 60 * math.cos(a + .12), 120 + 60 * math.sin(a + .12))], GOLD)
                   for a in [i * math.pi / 6 for i in range(12)])
    return rays + solid_shadow(IVORY_S, circle(120, 120, 48, GOLD), dx=3, dy=4) + circle(120, 120, 48, GOLD)


def moon():
    return solid_shadow(SHADOW_EM, crescent(120, 120, 70, IVORY)) + crescent(120, 120, 70, IVORY)


def star():
    return solid_shadow(SHADOW_EM, star8(120, 120, 70, GOLD, .5), dx=3, dy=4) + star8(120, 120, 70, GOLD, .5)


def heart():
    d = "M120 196 C60 150 70 90 104 90 C116 90 120 100 120 108 C120 100 124 90 136 90 C170 90 180 150 120 196 Z"
    return piece(path(d, CORAL))


# ── objects ─────────────────────────────────────────────────────────────────
def water_bowl():
    b = [path("M70 180 L170 180 Q166 222 120 222 Q74 222 70 180 Z", HILL), ellipse(120, 180, 50, 10, LEAF_L)]
    return piece(*b) + ellipse(120, 180, 40, 6, IVORY, ' opacity="0.6"')


def wallet(motif=False):
    b = [rect(66, 140, 108, 72, HILL_DEEP, 10), path("M66 160 L174 160 L174 178 L120 186 L66 178 Z", HILL)]
    out = piece(*b) + circle(150, 176, 5, GOLD)
    if motif:  # a little rocket on the flap
        out += poly([(96, 150), (104, 132), (112, 150)], IVORY) + rect(100, 150, 8, 6, CORAL)
    return out


def toy_car(broken=False):
    b = [path("M58 186 L72 156 L150 152 L176 172 L186 186 Z", CORAL), rect(52, 182, 140, 20, CORAL, 8),
         path("M84 158 L100 136 L140 136 L152 156 Z", CORAL)]
    out = piece(*b) + path("M90 156 L102 142 L118 142 L118 156 Z", IVORY) + path("M124 156 L124 142 L138 142 L146 156 Z", IVORY)
    wheels = [(84, 204), (160, 204)]
    if broken:
        out += piece(circle(84, 204, 14, INK)) + circle(84, 204, 6, IVORY_S)
        out += piece(circle(194, 222, 14, INK)) + circle(194, 222, 6, IVORY_S)  # the wheel that came off
        return out
    for x, y in wheels:
        out += piece(circle(x, y, 14, INK)) + circle(x, y, 6, IVORY_S)
    return out


BLOCK_COLORS = [CORAL, LEAF, IVORY_D, HILL, GOLD, LEAF_L]


def blocks(tower=True):
    out = ""
    if tower:
        y = 206
        for i, w in enumerate((56, 50, 44, 40, 34, 30)):
            c = BLOCK_COLORS[i % len(BLOCK_COLORS)]
            x = 120 - w / 2 + (3 if i % 2 else -3)
            out += piece(rect(x, y - 22 * i, w, 22, c, 3))
        return out
    spots = [(64, 196, 12), (100, 210, -8), (138, 200, 20), (170, 214, -14), (86, 176, 30), (150, 180, -24)]
    for i, (x, y, r) in enumerate(spots):
        c = BLOCK_COLORS[i % len(BLOCK_COLORS)]
        out += piece(rect(x - 14, y - 11, 28, 22, c, 3, f' transform="rotate({r} {x} {y})"'))
    return out


def toy_chest(open_=False):
    b = [rect(56, 150, 128, 74, CORAL, 8), rect(56, 150, 128, 14, IVORY_D, 4)]
    out = piece(*b) + rect(112, 160, 16, 14, GOLD, 3)
    if open_:
        out = piece(path("M56 150 L72 112 L184 112 L184 150 Z", IVORY_D)) + out
        for i, (x, c) in enumerate(((84, LEAF), (110, GOLD), (138, HILL), (160, LEAF_L))):
            out += piece(circle(x, 144, 12, c)) if i % 2 else piece(rect(x - 11, 132, 22, 22, c, 4))
        out += piece(rect(56, 160, 128, 64, CORAL, 8)) + rect(112, 168, 16, 14, GOLD, 3)
    return out


def pencils():
    out = piece(rect(60, 150, 120, 66, IVORY_D, 8))
    for i, c in enumerate((CORAL, LEAF, HILL, GOLD, LEAF_L, HILL_DEEP)):
        x = 70 + i * 18
        out += piece(rect(x, 112, 12, 60, c, 2), poly([(x, 112), (x + 6, 98), (x + 12, 112)], IVORY_S))
    out += piece(rect(60, 160, 120, 56, IVORY_D, 8))
    return out


def canvas(spill=False):
    legs = stroke("M88 228 L104 80", IVORY_S, 7) + stroke("M152 228 L136 80", IVORY_S, 7) + stroke("M120 228 L120 150", IVORY_S, 6)
    board = [rect(66, 70, 108, 90, IVORY, 6)]
    art = (path("M76 150 Q100 110 120 136 Q140 104 164 150 Z", LEAF) + circle(146, 96, 12, GOLD)
           + path("M80 150 Q100 132 112 150 Z", HILL))
    out = legs + piece(*board) + art
    if spill:
        out += path("M96 92 Q120 76 140 96 Q154 112 136 124 Q122 140 104 126 Q84 114 96 92 Z", CORAL, ' opacity="0.85"')
        out += circle(150, 132, 6, CORAL, ' opacity="0.85"') + circle(86, 136, 4, CORAL, ' opacity="0.85"')
    return out


def juice_cup(tipped=False):
    if tipped:
        b = [path("M70 196 L150 176 L156 200 L76 220 Z", IVORY_D)]
        return piece(*b) + path("M156 188 Q190 196 198 214 Q170 220 156 200 Z", CORAL)
    b = [path("M92 120 L148 120 L140 220 L100 220 Z", IVORY_D)]
    return piece(*b) + path("M95 150 L145 150 L140 216 L100 216 Z", CORAL) + stroke("M132 120 L146 84", LEAF, 5)


def soup_pot():
    b = [rect(60, 140, 120, 80, HILL_DEEP, 12), rect(50, 134, 140, 16, HILL, 8),
         rect(40, 156, 22, 10, HILL_DEEP, 5), rect(178, 156, 22, 10, HILL_DEEP, 5)]
    steam = "".join(stroke(f"M{x} 124 q-8 -14 0 -26 q8 -12 0 -24", IVORY_D, 4) for x in (96, 120, 144))
    return steam + piece(*b)


def soup_bowl():
    b = [path("M60 160 L180 160 Q176 214 120 214 Q64 214 60 160 Z", IVORY), ellipse(120, 160, 60, 12, CORAL)]
    steam = "".join(stroke(f"M{x} 144 q-6 -12 0 -22 q6 -10 0 -20", IVORY_D, 4) for x in (104, 136))
    return steam + piece(*b) + rect(100, 196, 40, 6, IVORY_D, 3)


def fruit_plate():
    out = piece(ellipse(120, 196, 72, 18, IVORY))
    for x, y, r, c in ((96, 178, 18, CORAL), (126, 172, 20, GOLD), (152, 182, 16, LEAF), (112, 160, 14, LEAF_L)):
        out += piece(circle(x, y, r, c))
    return out + stroke("M126 152 L130 142", HILL, 3)


def sweets():
    out = piece(ellipse(120, 200, 60, 14, IVORY))
    for x, c in ((92, CORAL), (120, LEAF), (148, GOLD)):
        out += piece(rect(x - 12, 172, 24, 24, c, 6))
    return out


def table(with_food=False):
    b = [rect(30, 140, 180, 16, IVORY_S, 4), rect(44, 156, 12, 70, IVORY_S, 3), rect(184, 156, 12, 70, IVORY_S, 3)]
    out = piece(*b) + rect(30, 140, 180, 5, IVORY_D, 2)
    if with_food:
        out += piece(ellipse(80, 136, 26, 7, IVORY), ellipse(160, 136, 26, 7, IVORY))
        out += piece(circle(72, 128, 9, CORAL), circle(86, 126, 8, GOLD), circle(160, 126, 10, LEAF))
        out += piece(rect(114, 108, 14, 28, LEAF_L, 3))
    return out


def door(open_=False):
    frame = [rect(62, 30, 116, 200, IVORY_S, 6)]
    out = piece(*frame)
    if open_:
        out += rect(70, 38, 100, 192, INK, 4)
        out += piece(path("M70 38 L104 50 L104 226 L70 230 Z", CORAL))
        out += circle(98, 140, 4, GOLD)
        return out
    out += rect(70, 38, 100, 192, CORAL, 4)
    out += rect(82, 52, 76, 70, CORAL, 4, f' stroke="{IVORY_D}" stroke-width="3"')
    out += rect(82, 136, 76, 80, CORAL, 4, f' stroke="{IVORY_D}" stroke-width="3"')
    out += circle(152, 132, 5, GOLD)
    return out


def bench():
    b = [rect(36, 150, 168, 14, IVORY_S, 4), rect(36, 126, 168, 12, IVORY_S, 4),
         rect(50, 164, 10, 60, SHADOW_EM, 3), rect(180, 164, 10, 60, SHADOW_EM, 3)]
    return piece(*b)


def sign():
    b = [rect(114, 120, 12, 108, IVORY_S, 3), rect(56, 70, 128, 66, IVORY_D, 8)]
    out = piece(*b)
    # Strokes, not letters: STYLE.md forbids text, so the sign reads as "written on".
    for y, w in ((90, 88), (104, 70), (118, 80)):
        out += line(120 - w / 2, y, 120 + w / 2, y, HILL, 4)
    return out


def litter():
    out = ""
    for x, y, r, c in ((60, 214, 10, IVORY), (110, 220, -16, IVORY_D), (170, 212, 24, IVORY)):
        out += piece(rect(x - 14, y - 9, 28, 18, c, 3, f' transform="rotate({r} {x} {y})"'))
    out += piece(rect(130, 196, 14, 26, LEAF_L, 3, ' transform="rotate(70 137 209)"'))
    return out


def trash_bag():
    b = [path("M80 226 Q60 170 104 150 L136 150 Q180 170 160 226 Z", HILL_DEEP),
         path("M104 150 L112 132 L120 146 L128 132 L136 150 Z", HILL_DEEP)]
    return piece(*b) + stroke("M100 196 Q120 186 140 196", SHADOW_EM, 3)


def watering_can():
    b = [rect(74, 140, 80, 70, HILL, 10), path("M154 160 L196 128 L202 136 L158 176 Z", HILL),
         path("M88 140 Q114 104 140 140", "none", f' stroke="{HILL}" stroke-width="10" stroke-linecap="round"')]
    return piece(*b) + rect(74, 160, 80, 8, LEAF, 3)


def prayer_rug():
    b = [path("M40 196 L200 196 L216 226 L24 226 Z", CORAL)]
    out = piece(*b)
    out += path("M60 200 L180 200 L190 222 L50 222 Z", "none", f' stroke="{IVORY}" stroke-width="3"')
    out += path("M104 222 L104 210 Q120 198 136 210 L136 222", "none", f' stroke="{IVORY}" stroke-width="3"')
    return out


def water_tap():
    b = [rect(60, 70, 120, 150, IVORY_D, 8), rect(60, 70, 120, 18, IVORY_S, 6)]
    out = piece(*b)
    for x in (92, 148):
        out += piece(rect(x - 12, 100, 24, 10, HILL_DEEP, 4), rect(x - 4, 108, 8, 14, HILL_DEEP, 2))
        out += stroke(f"M{x} 126 L{x} 168", LEAF_L, 4) + circle(x, 174, 4, LEAF_L)
    out += rect(70, 186, 100, 12, HILL, 4)
    return out


def sofa():
    b = [rect(30, 140, 180, 60, CORAL, 14), rect(30, 116, 180, 40, CORAL, 14),
         rect(20, 140, 30, 66, CORAL, 10), rect(190, 140, 30, 66, CORAL, 10),
         rect(48, 200, 10, 22, SHADOW_EM, 3), rect(182, 200, 10, 22, SHADOW_EM, 3)]
    return piece(*b) + rect(54, 156, 132, 6, IVORY_D, 3)


def water_glass():
    return piece(path("M96 120 L144 120 L138 216 L102 216 Z", LEAF_L)) + path("M99 150 L141 150 L138 212 L102 212 Z", HILL, ' opacity="0.45"')


def shield():
    d = "M120 70 L176 92 Q176 170 120 210 Q64 170 64 92 Z"
    return piece(path(d, HILL)) + path("M120 88 L160 104 Q160 160 120 190 Q80 160 80 104 Z", IVORY_D) + star8(120, 140, 22, GOLD)


def volcano():
    b = [path("M40 226 L104 110 L136 110 L200 226 Z", IVORY_S), path("M104 110 L136 110 L128 128 L112 128 Z", CORAL)]
    lava = path("M96 110 Q104 74 120 92 Q132 64 146 108 Z", CORAL) + path("M108 108 Q114 88 120 100 Q128 84 134 108 Z", GOLD)
    return piece(*b) + lava + path("M104 110 Q116 140 112 170 L124 170 Q120 140 136 110 Z", CORAL)


def gift():
    b = [rect(66, 130, 108, 90, CORAL, 6), rect(58, 112, 124, 26, CORAL, 6)]
    out = piece(*b) + rect(112, 112, 16, 108, GOLD)
    out += path("M120 112 Q96 82 92 100 Q92 112 120 112 Z", GOLD) + path("M120 112 Q144 82 148 100 Q148 112 120 112 Z", GOLD)
    return out


def bed_girl():
    """A bed with a girl tucked in — head in her khimar on the pillow."""
    b = [rect(24, 150, 192, 56, IVORY_S, 10), rect(16, 112, 22, 112, IVORY_S, 6), rect(206, 132, 18, 92, IVORY_S, 6)]
    out = piece(*b)
    out += piece(ellipse(70, 146, 34, 16, IVORY))  # pillow
    out += piece(circle(76, 136, 21, IVORY), circle(76, 136, 14, SKIN))
    out += eyes(76, 137, spread=5, size=3, width=2.2)
    out += piece(path("M88 146 Q150 128 210 142 L210 190 L40 190 Q46 160 88 146 Z", HILL))  # blanket
    for x in (120, 160, 196):
        out += star8(x, 168, 6, LEAF_L)
    return out


def minaret():
    b = [rect(100, 70, 40, 160, IVORY_D, 4), rect(92, 100, 56, 12, IVORY_S, 4),
         path("M100 70 Q120 30 140 70 Z", HILL)]
    return piece(*b) + crescent(120, 26, 9, GOLD) + rect(114, 130, 12, 24, HILL_DEEP, 6)


def lantern():
    b = [path("M92 96 L148 96 L156 186 L84 186 Z", IVORY), rect(84, 186, 72, 12, HILL_DEEP, 4),
         path("M92 96 Q120 60 148 96 Z", HILL_DEEP)]
    return (stroke("M120 30 L120 64", IVORY_S, 3) + piece(*b)
            + path("M108 176 Q102 150 120 128 Q138 150 132 176 Z", GOLD))


def boy_sujood():
    """A child in sujood on a rug — ruku'/sujood drawn correctly (STYLE.md)."""
    out = prayer_rug()
    body = [path("M70 196 Q74 150 120 150 Q160 152 168 196 Z", IVORY), circle(176, 190, 14, SKIN),
            path("M164 184 A14 12 0 0 1 190 184 Z", HILL_DEEP),
            ellipse(64, 198, 12, 6, SHADOW_EM)]
    return out + piece(*body)


PROPS = {
    "kitten": kitten, "bird": bird, "ant": ant,
    "tree": lambda: tree(), "tree_nest": lambda: tree(nest=True), "tree_olive": lambda: tree(HILL_DEEP, HILL),
    "bush": bush, "flower": lambda: flower(), "rose": lambda: flower(CORAL),
    "seed": lambda: sprout(0), "sprout": lambda: sprout(1), "plant": lambda: sprout(2),
    "basil_wilted": lambda: basil(True), "basil": lambda: basil(False),
    "cloud": cloud, "sun": sun, "moon": moon, "star": star, "heart": heart,
    "water_bowl": water_bowl, "wallet": lambda: wallet(), "wallet_rocket": lambda: wallet(True),
    "toy_car": lambda: toy_car(), "toy_car_broken": lambda: toy_car(True),
    "blocks": lambda: blocks(True), "blocks_fallen": lambda: blocks(False),
    "toy_chest": lambda: toy_chest(), "toy_chest_open": lambda: toy_chest(True),
    "pencils": pencils, "canvas": lambda: canvas(), "canvas_spilled": lambda: canvas(True),
    "juice": lambda: juice_cup(), "juice_tipped": lambda: juice_cup(True),
    "soup_pot": soup_pot, "soup_bowl": soup_bowl, "fruit_plate": fruit_plate, "sweets": sweets,
    "table": lambda: table(), "table_food": lambda: table(True),
    "door": lambda: door(), "door_open": lambda: door(True),
    "bench": bench, "sign": sign, "litter": litter, "trash_bag": trash_bag,
    "watering_can": watering_can, "prayer_rug": prayer_rug, "water_tap": water_tap,
    "sofa": sofa, "water_glass": water_glass, "shield": shield, "volcano": volcano,
    "gift": gift, "bed_girl": bed_girl, "minaret": minaret, "lantern": lantern,
    "sujood": boy_sujood,
}


# ── backdrops (360×240) ─────────────────────────────────────────────────────
def hills(base=172, colors=(HILL, HILL_DEEP, SHADOW_EM)):
    out = ""
    for i, c in enumerate(colors):
        y = base + i * 18
        out += path(f"M0 {y} Q90 {y - 34 + i * 6} 180 {y - 6} Q270 {y + 22 - i * 8} 360 {y - 16} L360 240 L0 240 Z", c)
    return out


def stars_scatter(points, color=STAR_EM, r=6):
    return "".join(star8(x, y, r, color) for x, y in points)


def window(x, y, w, h, night: bool):
    out = rect(x + 4, y + 5, w, h, SHADOW_EM if night else IVORY_S, 10)
    out += rect(x, y, w, h, IVORY_D if not night else HILL_DEEP, 10)
    inner = SHADOW_EM if night else IVORY
    out += rect(x + 8, y + 8, w - 16, h - 16, inner, 6)
    if night:
        out += crescent(x + w * .66, y + h * .36, h * .16, IVORY)
        out += star8(x + w * .3, y + h * .3, 4, GOLD) + star8(x + w * .42, y + h * .64, 3, GOLD)
    else:
        out += circle(x + w * .68, y + h * .38, h * .14, GOLD)
        out += cloud_small(x + w * .34, y + h * .62, w * .16)
    out += rect(x + w / 2 - 2, y + 8, 4, h - 16, IVORY_D if not night else HILL_DEEP)
    out += rect(x + 8, y + h / 2 - 2, w - 16, 4, IVORY_D if not night else HILL_DEEP)
    return out


def cloud_small(cx, cy, w):
    return (circle(cx - w * .3, cy, w * .28, IVORY_D) + circle(cx + w * .05, cy - w * .14, w * .36, IVORY_D)
            + circle(cx + w * .38, cy, w * .24, IVORY_D))


def bg_garden_day():
    out = rect(0, 0, 360, 240, IVORY)
    out += solid_shadow(IVORY_S, circle(292, 54, 26, GOLD), dx=3, dy=4) + circle(292, 54, 26, GOLD)
    out += cloud_small(80, 52, 60) + cloud_small(200, 34, 44)
    out += hills(150, (LEAF_L, LEAF, HILL))
    out += rect(0, 206, 360, 34, HILL)
    return out


def bg_garden_evening():
    out = rect(0, 0, 360, 240, IVORY_D)
    out += solid_shadow(IVORY_S, circle(84, 92, 30, CORAL), dx=3, dy=4) + circle(84, 92, 30, CORAL)
    out += hills(150, (LEAF, HILL, HILL_DEEP))
    out += rect(0, 210, 360, 30, HILL_DEEP)
    return out


def bg_night_sky():
    out = rect(0, 0, 360, 240, EMERALD)
    out += stars_scatter([(40, 40), (120, 26), (196, 60), (300, 34), (250, 96), (70, 110), (330, 120)])
    out += star8(160, 104, 5, GOLD) + star8(286, 70, 4, GOLD)
    out += hills(176, (HILL, HILL_DEEP, SHADOW_EM))
    return out


def bg_room(night: bool):
    wall = HILL_DEEP if night else IVORY
    floor = SHADOW_EM if night else IVORY_S
    out = rect(0, 0, 360, 240, wall)
    if night:
        out += stars_scatter([(30, 30), (330, 40), (300, 150)], STAR_EM, 5)
    else:
        # A soft wallpaper of eight-point stars.
        out += stars_scatter([(34, 30), (330, 36), (34, 150), (326, 140)], IVORY_D, 6)
    out += window(214, 34, 104, 92, night)
    out += rect(0, 196, 360, 44, floor)
    out += rect(0, 192, 360, 6, SHADOW_EM if night else IVORY_D)
    out += path("M60 222 L300 222 L286 236 L74 236 Z", CORAL if not night else HILL)  # rug
    return out


def bg_classroom():
    out = rect(0, 0, 360, 240, IVORY)
    out += rect(64, 30, 236, 104, IVORY_S, 8) + rect(60, 26, 236, 104, HILL_DEEP, 8)
    out += line(84, 60, 180, 60, HILL, 4) + line(84, 82, 220, 82, HILL, 4) + line(84, 104, 150, 104, HILL, 4)
    out += star8(260, 64, 9, GOLD)
    out += rect(0, 196, 360, 44, IVORY_S) + rect(0, 192, 360, 6, IVORY_D)
    return out


def bg_hallway():
    out = rect(0, 0, 360, 240, IVORY)
    for x in (30, 150, 270):
        out += rect(x + 4, 69, 60, 128, IVORY_S, 4) + rect(x, 64, 60, 128, LEAF, 4) + circle(x + 48, 130, 3, GOLD)
    out += path("M0 196 L360 196 L360 240 L0 240 Z", IVORY_S)
    out += path("M150 196 L210 196 L250 240 L110 240 Z", IVORY_D)
    return out


def bg_mosque():
    out = rect(0, 0, 360, 240, EMERALD)
    out += stars_scatter([(40, 30), (320, 26), (290, 80)], STAR_EM, 6)
    for x in (40, 150, 260):
        out += path(f"M{x + 4} 205 L{x + 4} 95 Q{x + 34} 52 {x + 64} 95 L{x + 64} 205 Z", SHADOW_EM)
        out += path(f"M{x} 200 L{x} 90 Q{x + 30} 48 {x + 60} 90 L{x + 60} 200 Z", HILL_DEEP)
        out += lantern_small(x + 30, 112)
    out += rect(0, 200, 360, 40, CORAL)
    for x in range(0, 360, 60):
        out += path(f"M{x + 12} 240 L{x + 12} 222 Q{x + 30} 206 {x + 48} 222 L{x + 48} 240", "none",
                    f' stroke="{IVORY}" stroke-width="2.5"')
    return out


def lantern_small(cx, cy):
    return (line(cx, cy - 34, cx, cy - 14, IVORY_S, 2) + path(f"M{cx - 9} {cy - 14} L{cx + 9} {cy - 14} L{cx + 12} {cy + 12} L{cx - 12} {cy + 12} Z", IVORY)
            + path(f"M{cx - 4} {cy + 8} Q{cx - 6} {cy} {cx} {cy - 8} Q{cx + 6} {cy} {cx + 4} {cy + 8} Z", GOLD))


def bg_kitchen():
    out = rect(0, 0, 360, 240, IVORY)
    out += window(40, 34, 96, 80, False)
    out += rect(164, 50, 160, 54, IVORY_S, 6) + rect(160, 46, 160, 54, IVORY_D, 6)
    out += line(240, 52, 240, 94, IVORY_S, 3)
    out += rect(0, 150, 360, 90, HILL_DEEP) + rect(0, 144, 360, 12, IVORY_S)
    for x in range(20, 360, 80):
        out += rect(x, 168, 56, 54, HILL, 6)
    return out


def bg_street():
    out = rect(0, 0, 360, 240, IVORY)
    out += cloud_small(70, 40, 50) + solid_shadow(IVORY_S, circle(310, 40, 18, GOLD), dx=3, dy=4) + circle(310, 40, 18, GOLD)
    for x, w, h, c in ((10, 90, 110, IVORY_D), (110, 100, 130, LEAF_L), (220, 120, 100, IVORY_D)):
        out += rect(x + 4, 205 - h, w, h, IVORY_S, 4) + rect(x, 200 - h, w, h, c, 4)
        out += rect(x + 16, 220 - h, 20, 22, HILL_DEEP, 3) + rect(x + w - 36, 220 - h, 20, 22, HILL_DEEP, 3)
    out += rect(0, 200, 360, 40, IVORY_S) + rect(0, 214, 360, 6, IVORY_D)
    return out


def bg_playground():
    out = bg_garden_day()
    return out + rect(0, 214, 360, 26, IVORY_S)


BACKDROPS = {
    "bg_garden_day": bg_garden_day, "bg_garden_evening": bg_garden_evening, "bg_night_sky": bg_night_sky,
    "bg_room_day": lambda: bg_room(False), "bg_room_night": lambda: bg_room(True),
    "bg_classroom": bg_classroom, "bg_hallway": bg_hallway, "bg_mosque": bg_mosque,
    "bg_kitchen": bg_kitchen, "bg_street": bg_street, "bg_playground": bg_playground,
}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    written = set()
    for name, fn in {**PEOPLE, **PROPS}.items():
        (OUT / f"{name}.svg").write_text(svg(fn()), encoding="utf-8")
        written.add(f"{name}.svg")
    for name, fn in BACKDROPS.items():
        (OUT / f"{name}.svg").write_text(svg(fn(), 360, 240), encoding="utf-8")
        written.add(f"{name}.svg")
    for stale in OUT.glob("*.svg"):
        if stale.name not in written:
            stale.unlink()
    big = [(p.name, p.stat().st_size) for p in OUT.glob("*.svg") if p.stat().st_size > 12_000]
    print(f"wrote {len(written)} files to {OUT}")
    if big:
        print("over 12KB:", big)


if __name__ == "__main__":
    main()
