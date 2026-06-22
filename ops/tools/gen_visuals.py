#!/usr/bin/env python3
"""
gen_visuals — توليد المحتوى البصري المخصّص لـ«المربّي» بأسلوب موحّد محتشم.

يستخدم fal.ai → Recraft V3 (متخصص في الفيكتور/اللوجوهات، جودة أعلى من FLUX schnell).
~$0.04/صورة؛ fal.ai بيمنح $10 كريديت مجاني لا ينتهي.

التشغيل:
    export FAL_KEY="مفتاحك من fal.ai"
    python ops/tools/gen_visuals.py              # يولّد المتبقّي فقط (idempotent)
    python ops/tools/gen_visuals.py --only badge_first_dua
    python ops/tools/gen_visuals.py --dry-run    # خطة + تكلفة بلا توليد

كل أصل = (filename, prompt, size) ويُدمج مع STYLE الثابت لضمان الاتساق البصري.
المخرجات → mobile/assets/images/generated/
"""
import argparse
import os
import sys
import urllib.request
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "mobile" / "assets" / "images" / "generated"
FAL_MODEL = "https://fal.run/fal-ai/recraft-v3"
RECRAFT_STYLE = "digital_illustration"
COST_PER_IMAGE = 0.04  # USD, Recraft V3

# الهوية البصرية الموحّدة — هلال بوجه هادئ + كتاب + نبتة + نجمة، أبيض على تركواز عميق.
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

# (key, prompt, size). Recraft sizes: square_hd (1024×1024), landscape_4_3,
# portrait_4_3, landscape_16_9, portrait_16_9. Default = square_hd.
ASSETS: dict[str, tuple[str, str]] = {
    # — هوية/ماسكوت —
    "mascot_serene": (
        "a single serene crescent moon with a calm closed-eyes "
        "face profile, friendly and welcoming, warm and gentle",
        "square_hd",
    ),
    "mascot_celebrate": (
        "a serene crescent moon with a calm closed-eyes face "
        "profile surrounded by small stars and sparkles, joyful",
        "square_hd",
    ),
    "mascot_reading": (
        "a serene crescent moon with a calm closed-eyes face "
        "profile beside an open book with a small plant sprout, reverent",
        "square_hd",
    ),
    # — كروت مشاركة + متجر —
    "share_bg_celebration": (
        "a soft decorative frame for a greeting card: a "
        "crescent moon in a corner, scattered small stars and gentle light, "
        "mostly empty calm center, plenty of negative space for text",
        "square_hd",
    ),
    "store_hero": (
        "a warm hero scene: a crescent moon and a star above an open "
        "book from which a small plant sprout grows, symbolizing nurturing a "
        "child's growth and faith",
        "square_hd",
    ),
    # — فن المحطات —
    "milestone_first_prayer": (
        "a small prayer rug under a crescent moon and a "
        "star, symbolizing a child's first prayer",
        "square_hd",
    ),
    "milestone_first_surah": (
        "an open book with soft light rays and a star "
        "above it, symbolizing memorizing the first surah",
        "square_hd",
    ),
    "milestone_first_fast": (
        "a crescent moon with a small lantern and a star, "
        "symbolizing a child's first fast in Ramadan",
        "square_hd",
    ),
    # — شارات المحطات القديمة (تستبدل PNGs غير الموحّدة) —
    "badge_first_dua": (
        "a small serene crescent moon with closed eyes above praying hands, "
        "symbolizing a child's first dua, simple badge icon",
        "square_hd",
    ),
    "badge_good_manner": (
        "a small open book with a heart above it and a crescent moon, "
        "symbolizing good manners and akhlaq, simple badge icon",
        "square_hd",
    ),
    "badge_helped_others": (
        "two small hands reaching toward each other under a crescent moon "
        "and star, symbolizing helping others, simple badge icon",
        "square_hd",
    ),
    "badge_keeps_prayer": (
        "a small prayer rug with a crescent moon and a star above it, "
        "symbolizing keeping prayer, simple badge icon",
        "square_hd",
    ),
    "badge_quran_khatma": (
        "an open book with light rays and a crescent moon above it, "
        "symbolizing completing Quran khatma, simple badge icon",
        "square_hd",
    ),
    "badge_shahada": (
        "a bright guiding star above an open book, symbolizing the shahada "
        "and faith declaration, simple badge icon",
        "square_hd",
    ),
    # — onboarding / empty states —
    "onboarding_welcome": (
        "a cozy warm scene with a large crescent moon, an "
        "open book, a growing plant, and a few stars, inviting and gentle",
        "square_hd",
    ),
    "empty_journey": (
        "a gentle winding path marked with small stars leading "
        "toward a glowing crescent moon on the horizon, hopeful",
        "square_hd",
    ),
    "empty_children": (
        "a small plant sprout in soft soil under a crescent moon, "
        "inviting to start, calm",
        "square_hd",
    ),
    "empty_search": (
        "a simple magnifying glass with a small star inside, in the "
        "brand line-art style, calm and minimal",
        "square_hd",
    ),
    # — domain illustrations —
    "domain_islamic_parenting": (
        "a warm scene of a parent and child sitting "
        "together reading an open book under a crescent moon and a star, "
        "symbolizing Islamic upbringing",
        "square_hd",
    ),
    "domain_development": (
        "a small plant sprout growing from an open book, "
        "with a crescent moon and a star watching over it, symbolizing child "
        "development and growth",
        "square_hd",
    ),
    "domain_cyber": (
        "a serene crescent moon and a star above an open book with "
        "a small shield icon, symbolizing online safety and digital ethics",
        "square_hd",
    ),
    "domain_health": (
        "a small plant sprout with a crescent moon and a star "
        "above it, symbolizing health and wellness, calm and natural",
        "square_hd",
    ),
    # — banners —
    "banner": (
        "a wide warm banner: crescent moon, open book, growing plant, "
        "and stars, with plenty of calm center space, suitable for an app "
        "banner",
        "landscape_16_9",
    ),
    # — Play Store / app icon —
    "feature_graphic": (
        "a wide Play Store feature graphic: serene crescent moon with closed "
        "eyes, open book, small plant sprout and stars, solid teal background, "
        "plenty of calm left space for app name text, premium and spiritual",
        "landscape_16_9",
    ),
    "app_icon": (
        "a clean app icon: serene crescent moon doubling as a calm closed-eyes "
        "face profile, open book below it, small plant sprout and a star, "
        "compact centered composition, solid teal background",
        "square_hd",
    ),
}


def _generate(client: httpx.Client, key: str, prompt: str, size: str) -> bytes:
    resp = client.post(
        FAL_MODEL,
        headers={"Authorization": f"Key {key}"},
        json={
            "prompt": f"{prompt}. {STYLE}",
            "style": RECRAFT_STYLE,
            "image_size": size,
        },
        timeout=180,
    )
    resp.raise_for_status()
    url = resp.json()["images"][0]["url"]
    with urllib.request.urlopen(url, timeout=60) as r:  # noqa: S310
        return r.read()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="generate a single asset by name")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true", help="regenerate even if exists")
    args = ap.parse_args()

    targets = {args.only: ASSETS[args.only]} if args.only else dict(ASSETS)
    if args.only and args.only not in ASSETS:
        print(f"❌ unknown asset '{args.only}'. Known: {', '.join(ASSETS)}")
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pending: dict[str, tuple[str, str]] = {}
    for name, (prompt, size) in targets.items():
        if args.force or not (OUT_DIR / f"{name}.webp").exists():
            pending[name] = (prompt, size)

    print(f"📦 {len(targets)} asset(s) | {len(pending)} pending | "
          f"est. cost ${len(pending) * COST_PER_IMAGE:.3f} "
          f"(fal.ai gives $10 free credit)")
    if args.dry_run:
        for name in pending:
            print(f"  • {name} ({pending[name][1]})")
        return 0

    key = os.environ.get("FAL_KEY", "").strip()
    if not key:
        print("❌ set FAL_KEY (free signup at fal.ai → $10 credit auto-applied)")
        return 1

    with httpx.Client() as client:
        for name, (prompt, size) in pending.items():
            try:
                data = _generate(client, key, prompt, size)
                out_path = OUT_DIR / f"{name}.webp"
                out_path.write_bytes(data)
                print(f"  ✅ {out_path.name} ({len(data) // 1024} KB)")
            except Exception as exc:  # noqa: BLE001
                print(f"  ❌ {name}: {exc}")
    print(f"\n💾 saved to {OUT_DIR.relative_to(ROOT)} — declare new files in "
          "pubspec.yaml assets, then use them in the app.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
