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

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "mobile" / "assets" / "images" / "generated"
FAL_MODEL = "https://fal.run/fal-ai/flux/schnell"
COST_PER_IMAGE = 0.003  # USD, FLUX schnell @ ~1MP

# الأسلوب الموحّد — يُلصق بنهاية كل prompt لضمان هوية بصرية واحدة محتشمة.
STYLE = (
    "flat vector children's-book illustration, warm teal (#01696F) and cream "
    "(#FAF7F2) palette, soft rounded shapes, gentle shadows, modest and calm, "
    "no realistic faces, subtle Islamic geometric motifs, spiritual warm tone, "
    "clean minimal background, high quality, centered composition"
)

# أولوية: أصول النمو (الكروت + المتجر) أولًا، ثم onboarding، ثم الفن العام.
ASSETS: dict[str, str] = {
    # — خلفيات/زينة كروت المشاركة ومتجر Play (أعلى أثر على النمو) —
    "share_bg_celebration": "a soft decorative background with a glowing "
        "crescent moon, a small lantern, and scattered light particles",
    "store_hero_family": "a warm scene of a parent's hand and a child's hand "
        "reaching together toward an open book and a small plant sprout",
    # — تميمة «نور» الفانوس (أوضاع) —
    "mascot_wave": "a friendly glowing lantern character named Noor, waving "
        "warmly, big kind eyes, cheerful",
    "mascot_celebrate": "a friendly glowing lantern character named Noor, "
        "celebrating with sparkles and confetti, joyful",
    "mascot_reading": "a friendly glowing lantern character named Noor next to "
        "an open Quran, calm and reverent",
    # — فن المحطات (رحلة الطفل) —
    "milestone_first_prayer": "a small prayer rug and a glowing crescent, "
        "symbolizing a child's first prayer, warm and spiritual",
    "milestone_first_surah": "an open Quran with soft light rays and a small "
        "star, symbolizing memorizing the first surah",
    # — onboarding / حالات فارغة —
    "onboarding_welcome": "a cozy reading nook with a lantern, a plant, and a "
        "stack of books, inviting and warm",
    "empty_journey": "a gentle winding path with small milestone flags leading "
        "toward a glowing horizon, hopeful",
}


def _generate(client: httpx.Client, key: str, prompt: str) -> bytes:
    resp = client.post(
        FAL_MODEL,
        headers={"Authorization": f"Key {key}"},
        json={
            "prompt": f"{prompt}. {STYLE}",
            "image_size": "square_hd",
            "num_inference_steps": 4,
            "num_images": 1,
            "enable_safety_checker": True,
        },
        timeout=120,
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
        if not (OUT_DIR / f"{name}.png").exists()
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
                (OUT_DIR / f"{name}.png").write_bytes(data)
                print(f"  ✅ {name}.png ({len(data) // 1024} KB)")
            except Exception as exc:  # noqa: BLE001
                print(f"  ❌ {name}: {exc}")
    print(f"\n💾 saved to {OUT_DIR.relative_to(ROOT)} — declare new files in "
          "pubspec.yaml assets, then use them in the app.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
