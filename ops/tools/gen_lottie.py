#!/usr/bin/env python3
"""
gen_lottie — generate lightweight, brand-aligned Lottie animations for
Tutor Guardian celebrations.

Outputs open JSON files (Lottie v5.5.2 format) that can be rendered with the
`lottie` Flutter package. All motion uses brand colors:
  - warm teal #01696F (primary)
  - white #FFFFFF
  - amber #F59E0B (accent)
  - soft gold #FCD34D

Generated files are intentionally simple (small JSONs) and cover the most
common celebration surfaces:
  - celebration_stars: gentle falling/rising stars and sparkles.
  - success_check: a checkmark that draws itself in with a subtle burst.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "mobile" / "assets" / "animations"

BRAND: dict[str, list[float]] = {
    "teal": [0.004, 0.412, 0.435, 1.0],      # #01696F
    "white": [1.0, 1.0, 1.0, 1.0],
    "amber": [0.961, 0.616, 0.043, 1.0],     # #F59E0B
    "gold": [0.988, 0.827, 0.302, 1.0],      # #FCD34D
}


def _hex_to_normalized(hex_color: str) -> list[float]:
    h = hex_color.lstrip("#")
    return [int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)] + [1.0]


def _layer(stars: list[dict[str, Any]], name: str) -> dict[str, Any]:
    return {
        "ddd": 0,
        "ind": 1,
        "ty": 4,
        "nm": name,
        "sr": 1,
        "ks": {
            "o": {"a": 0, "k": 100},
            "r": {"a": 0, "k": 0},
            "p": {"a": 0, "k": [0, 0, 0]},
            "a": {"a": 0, "k": [0, 0, 0]},
            "s": {"a": 0, "k": [100, 100, 100]},
        },
        "shapes": stars,
        "ip": 0,
        "op": 90,
        "st": 0,
    }


def _star_shape(
    x: float,
    y: float,
    radius: float,
    color_key: str,
    start_frame: int,
    end_frame: int,
    rotation_speed: float,
) -> dict[str, Any]:
    # Simple 4-point star polygon.
    points = []
    for i in range(8):
        angle = math.pi / 2 + i * math.pi / 4
        r = radius if i % 2 == 0 else radius * 0.4
        points.append([round(x + r * math.cos(angle), 2), round(y + r * math.sin(angle), 2)])

    # Animate opacity 0 -> 1 -> 0 and a gentle scale.
    return {
        "ty": "gr",
        "nm": f"star_{x}_{y}",
        "it": [
            {
                "ty": "sh",
                "ks": {
                    "a": 0,
                    "k": {
                        "i": [[0, 0]] * 7,
                        "o": [[0, 0]] * 7,
                        "v": points,
                        "c": True,
                    },
                },
            },
            {
                "ty": "fl",
                "c": {"a": 0, "k": BRAND[color_key]},
                "o": {"a": 1, "k": [
                    {"i": {"x": [0.833], "y": [0.833]}, "o": {"x": [0.167], "y": [0.167]}, "t": start_frame, "s": [0]},
                    {"i": {"x": [0.833], "y": [0.833]}, "o": {"x": [0.167], "y": [0.167]}, "t": start_frame + 10, "s": [100]},
                    {"i": {"x": [0.833], "y": [0.833]}, "o": {"x": [0.167], "y": [0.167]}, "t": end_frame - 10, "s": [100]},
                    {"t": end_frame, "s": [0]},
                ]},
            },
            {
                "ty": "tr",
                "p": {"a": 0, "k": [0, 0]},
                "a": {"a": 0, "k": [x, y]},
                "s": {"a": 1, "k": [
                    {"i": {"x": [0.667, 0.667], "y": [1, 1]}, "o": {"x": [0.333, 0.333], "y": [0, 0]}, "t": start_frame, "s": [0, 0]},
                    {"i": {"x": [0.667, 0.667], "y": [1, 1]}, "o": {"x": [0.333, 0.333], "y": [0, 0]}, "t": start_frame + 15, "s": [100, 100]},
                    {"t": end_frame, "s": [120 + int(rotation_speed * 10), 120 + int(rotation_speed * 10)]},
                ]},
                "r": {"a": 1, "k": [
                    {"t": start_frame, "s": [0]},
                    {"t": end_frame, "s": [rotation_speed * 90]},
                ]},
                "o": {"a": 0, "k": 0},
            },
        ],
    }


def build_celebration_stars() -> dict[str, Any]:
    width, height = 360, 360
    frames = 90
    stars: list[dict[str, Any]] = []

    specs = [
        (180, 80, 18, "white", 0, 70, 1.2),
        (120, 140, 12, "gold", 5, 75, -0.8),
        (240, 130, 14, "amber", 8, 80, 1.0),
        (80, 210, 10, "white", 12, 70, -1.1),
        (280, 200, 16, "gold", 15, 85, 0.9),
        (150, 260, 11, "amber", 18, 78, -0.7),
        (210, 280, 13, "white", 22, 82, 1.3),
        (300, 110, 9, "gold", 25, 72, -0.9),
        (60, 120, 10, "amber", 28, 76, 1.0),
        (180, 180, 20, "white", 32, 90, 0.6),
        (100, 300, 8, "gold", 36, 80, -1.2),
        (250, 300, 9, "amber", 40, 84, 1.1),
    ]

    for x, y, r, c, sf, ef, rs in specs:
        stars.append(_star_shape(x, y, r, c, sf, ef, rs))

    return {
        "v": "5.5.2",
        "fr": 30,
        "ip": 0,
        "op": frames,
        "w": width,
        "h": height,
        "nm": "celebration_stars",
        "ddd": 0,
        "assets": [],
        "layers": [_layer(stars, "celebration_stars")],
    }


def build_success_check() -> dict[str, Any]:
    width, height = 240, 240
    frames = 60

    # Circle background
    circle = {
        "ty": "gr",
        "it": [
            {
                "ty": "el",
                "d": 1,
                "s": {"a": 0, "k": [200, 200]},
                "p": {"a": 0, "k": [0, 0]},
            },
            {
                "ty": "fl",
                "c": {"a": 0, "k": BRAND["teal"]},
                "o": {"a": 0, "k": 100},
            },
            {
                "ty": "tr",
                "p": {"a": 0, "k": [120, 120]},
                "a": {"a": 0, "k": [0, 0]},
                "s": {"a": 1, "k": [
                    {"t": 0, "s": [0, 0]},
                    {"i": {"x": [0.667, 0.667], "y": [1, 1]}, "o": {"x": [0.333, 0.333], "y": [0, 0]}, "t": 15, "s": [100, 100]},
                    {"t": 60, "s": [100, 100]},
                ]},
                "r": {"a": 0, "k": 0},
                "o": {"a": 0, "k": 0},
            },
        ],
    }

    # Checkmark path
    check_points = [[45, 125], [95, 175], [180, 75]]
    check = {
        "ty": "gr",
        "it": [
            {
                "ty": "sh",
                "ks": {
                    "a": 0,
                    "k": {
                        "i": [[0, 0], [0, 0], [0, 0]],
                        "o": [[0, 0], [0, 0], [0, 0]],
                        "v": check_points,
                        "c": False,
                    },
                },
            },
            {
                "ty": "st",
                "c": {"a": 0, "k": BRAND["white"]},
                "o": {"a": 0, "k": 100},
                "w": {"a": 0, "k": 18},
                "lc": 2,
                "lj": 2,
            },
            {
                "ty": "tr",
                "p": {"a": 0, "k": [0, 0]},
                "a": {"a": 0, "k": [0, 0]},
                "s": {"a": 0, "k": [100, 100]},
                "r": {"a": 0, "k": 0},
                "o": {"a": 0, "k": 0},
            },
            {
                "ty": "tm",
                "s": {"a": 1, "k": [
                    {"t": 10, "s": [0]},
                    {"i": {"x": [0.833], "y": [0.833]}, "o": {"x": [0.167], "y": [0.167]}, "t": 10, "s": [0]},
                    {"t": 35, "s": [0]},
                    {"t": 55, "s": [100]},
                ]},
                "e": {"a": 0, "k": 100},
                "o": {"a": 0, "k": 0},
                "m": 1,
            },
        ],
    }

    return {
        "v": "5.5.2",
        "fr": 30,
        "ip": 0,
        "op": frames,
        "w": width,
        "h": height,
        "nm": "success_check",
        "ddd": 0,
        "assets": [],
        "layers": [_layer([circle, check], "success_check")],
    }


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    anims = {
        "celebration_stars": build_celebration_stars(),
        "success_check": build_success_check(),
    }
    for name, data in anims.items():
        out = OUT_DIR / f"{name}.json"
        out.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
        print(f"✅ {out.name} ({out.stat().st_size // 1024} KB)")
    print(f"\n💾 saved to {OUT_DIR.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
