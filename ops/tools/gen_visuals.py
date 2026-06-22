#!/usr/bin/env python3
"""
gen_visuals — توليد المحتوى البصري المخصّص لـ«المربّي» بأسلوب موحّد محتشم.

يستخدم fal.ai → FLUX.1 [schnell] (ترخيص Apache-2.0، استخدام تجاري مسموح،
~$0.003/صورة؛ fal.ai بيمنح $10 كريديت مجاني لا ينتهي → عمليًا $0 لاحتياجنا).
يتجنّب FLUX [dev] لأن رخصته غير تجارية.

التشغيل:
    export FAL_KEY="مفتاحك من fal.ai"        # تسجيل مجاني، الكريديت تلقائي
    python ops/tools/gen_visuals.py            # يولّد المتبقّي فقط (idempotent)
    python ops/tools/gen_visuals.py --only mascot_wave   # أصل واحد
    python ops/tools/gen_visuals.py --dry-run  # يطبع الخطة + التكلفة بلا توليد

كل أصل = (filename, prompt) ويُدمج مع STYLE الثابت لضمان الاتساق البصري.
المخرجات → mobile/assets/images/generated/  (PNG شفّاف 1024×1024).
"""
import argparse
import os
import sys
import urllib.request
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "mobile" / "assets" / "images" / "generated"
# Recraft V3 — vector/logo specialist (much higher quality than FLUX schnell
# for clean flat-vector brand art). ~$0.04/image; the $10 free credit covers
# the full set (~12 imgs ≈ $0.48) many times over.
FAL_MODEL = "https://fal.run/fal-ai/recraft-v3"
# digital_illustration → high-quality raster PNG (verifiable + drop-in to the
# existing Image.asset pipeline). vector_illustration returns SVG (crisper but
# needs flutter_svg) — a possible later upgrade.
RECRAFT_STYLE = "digital_illustration"
COST_PER_IMAGE = 0.04  # USD, Recraft V3

# الأسلوب الموحّد المتمحور حول اللوجو — يُلصق بنهاية كل prompt لهوية واحدة.
# اللوجو: هلال يندمج مع وجه هادئ في بروفايل + كتاب مفتوح + نبتة + نجمة، خط
# أبيض نظيف على تركواز. كل أصل يعيد توظيف نفس اللغة البصرية.
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

# متمحورة حول اللوجو، تستبدل الفانوس القديم. أولوية: النمو (كروت+متجر) ثم
# الماسكوت/الهوية ثم رحلة الطفل ثم onboarding/empty states.
ASSETS: dict[str, str] = {
    # — هوية/ماسكوت (يستبدل الفانوس «نور» القديم) —
    "mascot_serene": "a single serene crescent moon with a calm closed-eyes "
        "face profile, friendly and welcoming, warm and gentle",
    "mascot_celebrate": "a serene crescent moon with a calm closed-eyes face "
        "profile surrounded by small stars and sparkles, joyful",
    "mascot_reading": "a serene crescent moon with a calm closed-eyes face "
        "profile beside an open book with a small plant sprout, reverent",
    # — خلفيات/زينة كروت المشاركة ومتجر Play (أعلى أثر على النمو) —
    "share_bg_celebration": "a soft decorative frame for a greeting card: a "
        "crescent moon in a corner, scattered small stars and gentle light, "
        "mostly empty calm center, plenty of negative space for text",
    "store_hero": "a warm hero scene: a crescent moon and a star above an open "
        "book from which a small plant sprout grows, symbolizing nurturing a "
        "child's growth and faith",
    # — فن المحطات (رحلة الطفل) —
    "milestone_first_prayer": "a small prayer rug under a crescent moon and a "
        "star, symbolizing a child's first prayer",
    "milestone_first_surah": "an open book with soft light rays and a star "
        "above it, symbolizing memorizing the first surah",
    "milestone_first_fast": "a crescent moon with a small lantern and a star, "
        "symbolizing a child's first fast in Ramadan",
    # — onboarding / حالات فارغة —
    "onboarding_welcome": "a cozy warm scene with a large crescent moon, an "
        "open book, a growing plant, and a few stars, inviting and gentle",
    "empty_journey": "a gentle winding path marked with small stars leading "
        "toward a glowing crescent moon on the horizon, hopeful",
    "empty_children": "a small plant sprout in soft soil under a crescent moon, "
        "inviting to start, calm",
    "empty_search": "a simple magnifying glass with a small star inside, in the "
        "brand line-art style, calm and minimal",
    # — domain illustrations for path detail screens —
    "domain_islamic_parenting": "a warm scene of a parent and child sitting "
        "together reading an open book under a crescent moon and a star, "
        "symbolizing Islamic upbringing",
    "domain_development": "a small plant sprout growing from an open book, "
        "with a crescent moon and a star watching over it, symbolizing child "
        "development and growth",
    "domain_cyber": "a serene crescent moon and a star above an open book with "
        "a small shield icon, symbolizing online safety and digital ethics",
    "domain_health": "a small plant sprout with a crescent moon and a star "
        "above it, symbolizing health and wellness, calm and natural",
    # — in-app banners / hero —
    "banner": "a wide warm banner: crescent moon, open book, growing plant, "
        "and stars, with plenty of calm center space, suitable for an app "
        "banner",
}


def _generate(client: httpx.Client, key: str, prompt: str) -> bytes:
    resp = client.post(
        FAL_MODEL,
        headers={"Authorization": f"Key {key}"},
        json={
            "prompt": f"{prompt}. {STYLE}",
            "style": RECRAFT_STYLE,
            "image_size": "square_hd",
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
    args = ap.parse_args()

    targets = {args.only: ASSETS[args.only]} if args.only else dict(ASSETS)
    if args.only and args.only not in ASSETS:
        print(f"❌ unknown asset '{args.only}'. Known: {', '.join(ASSETS)}")
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pending = {
        name: p for name, p in targets.items()
        if not (OUT_DIR / f"{name}.webp").exists()
    }
    print(f"📦 {len(targets)} asset(s) | {len(pending)} pending | "
          f"est. cost ${len(pending) * COST_PER_IMAGE:.3f} "
          f"(fal.ai gives $10 free credit)")
    if args.dry_run:
        for name in pending:
            print(f"  • {name}")
        return 0

    key = os.environ.get("FAL_KEY", "")
    if not key:
        print("❌ set FAL_KEY (free signup at fal.ai → $10 credit auto-applied)")
        return 1

    with httpx.Client() as client:
        for name, prompt in pending.items():
            try:
                data = _generate(client, key, prompt)
                # Recraft V3 returns WebP; save with the correct extension so the
                # Flutter asset pipeline loads it efficiently.
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
