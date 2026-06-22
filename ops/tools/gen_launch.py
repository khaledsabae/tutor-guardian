#!/usr/bin/env python3
"""
gen_launch — أصول إطلاق + هيرو صفحة الهبوط (نفس هوية gen_visuals، بلا نص).

يولّد رسومات على-العلامة (Recraft V3) لصفحة `/go` والإطلاق الاجتماعي
(WhatsApp status / IG / تويتر). بلا نص — الكابشن العربي يُضاف فوقها لاحقًا.

التشغيل:
    export FAL_KEY="..."        # المفتاح الحالي (يُحرَق بالـrotate بعدها)
    python ops/tools/gen_launch.py [--dry-run]

المخرجات → docs/marketing/launch_graphics/  (والهيرو يُنسخ للباكند static يدويًا).
"""
import argparse
import os
import sys
import urllib.request
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "docs" / "marketing" / "launch_graphics"
FAL_MODEL = "https://fal.run/fal-ai/recraft-v3"
RECRAFT_STYLE = "digital_illustration"
COST_PER_IMAGE = 0.04

# نفس STYLE الموحّد المحتشم بتاع gen_visuals (هوية واحدة).
STYLE = (
    "elegant minimal flat vector illustration, crisp clean white line-art and "
    "white silhouettes on a solid deep teal #01696F background, refined and "
    "calm and contemplative mood evoking inner peace and growth through "
    "knowledge, smooth balanced geometric composition; recurring motifs of a "
    "serene crescent moon doubling as a peaceful closed-eyes face, an open "
    "book, a small plant sprout growing upward from knowledge, and a bright "
    "guiding star; modest, spiritual, polished, premium, no detailed realistic "
    "faces, centered and well-spaced, cohesive single brand identity. "
    "ABSOLUTELY NO TEXT, no words, no letters, no captions, no wordmark"
)

# (key, prompt, size)
ASSETS: dict[str, tuple[str, str]] = {
    "landing_hero": (
        "a warm welcoming hero banner: a large crescent moon with a serene "
        "calm face beside an open book with a growing sprout and stars, soft "
        "glow, plenty of calm empty space",
        "landscape_16_9",
    ),
    "social_announce_square": (
        "a centered celebratory brand emblem: crescent moon, open book, plant "
        "sprout and a bright star with gentle radiating light, balanced for a "
        "social post",
        "square_hd",
    ),
    "social_announce_wide": (
        "a wide gentle scene of a crescent moon and stars over an open book "
        "with a sprout, calm spiritual horizon, room for a headline",
        "landscape_16_9",
    ),
    "social_feature_ai": (
        "a soft speech bubble next to an open book and a crescent moon, "
        "symbolizing a wise gentle assistant answering questions",
        "square_hd",
    ),
    "social_feature_journey": (
        "a gentle winding path marked with small stars and milestone flags "
        "leading toward a glowing crescent moon, symbolizing a child's growth "
        "journey",
        "square_hd",
    ),
}


def _generate(client: httpx.Client, key: str, prompt: str, size: str) -> bytes:
    resp = client.post(
        FAL_MODEL,
        headers={"Authorization": f"Key {key}"},
        json={"prompt": f"{prompt}. {STYLE}", "style": RECRAFT_STYLE,
              "image_size": size},
        timeout=180,
    )
    resp.raise_for_status()
    url = resp.json()["images"][0]["url"]
    with urllib.request.urlopen(url, timeout=60) as r:  # noqa: S310
        return r.read()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pending = {k: v for k, v in ASSETS.items()
               if not (OUT_DIR / f"{k}.webp").exists()}
    print(f"📦 {len(ASSETS)} assets | {len(pending)} pending | "
          f"est ${len(pending) * COST_PER_IMAGE:.2f}")
    if args.dry_run:
        for k, (_, s) in pending.items():
            print(f"  • {k} ({s})")
        return 0

    key = os.environ.get("FAL_KEY", "")
    if not key:
        print("❌ set FAL_KEY")
        return 1
    with httpx.Client() as client:
        for name, (prompt, size) in pending.items():
            try:
                data = _generate(client, key, prompt, size)
                (OUT_DIR / f"{name}.webp").write_bytes(data)
                print(f"  ✅ {name}.webp ({len(data) // 1024} KB)")
            except Exception as exc:  # noqa: BLE001
                print(f"  ❌ {name}: {exc}")
    print(f"\n💾 {OUT_DIR.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
