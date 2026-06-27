#!/usr/bin/env python3
"""
gen_visuals — توليد المحتوى البصري المخصّص لـ«المربّي» بأسلوب موحّد محتشم.

الموديل الافتراضي: Recraft V3 (~$0.04/صورة). جُرّب الترقية لـFlux 2 Pro على كل
الأصول ورُفضت بصرياً — مهما كانت الأسبقية على الورق (سعر/حداثة)، أعطى نتائج
أوحش من Recraft لهوية البراند المسطّحة الفيكتورية دي تحديداً. سجل الموديلات في
fal_common.py لسه موجود لو احتجت تجرّب موديل تاني على أصل واحد بـ --model.
fal.ai بيمنح $10 كريديت مجاني لا ينتهي.

التشغيل:
    export FAL_KEY="مفتاحك من fal.ai"
    python ops/tools/gen_visuals.py              # يولّد المتبقّي فقط (idempotent)
    python ops/tools/gen_visuals.py --only badge_first_dua
    python ops/tools/gen_visuals.py --only mascot_serene --model nano_banana_pro --force
    python ops/tools/gen_visuals.py --dry-run    # خطة + تكلفة بلا توليد

كل أصل = AssetSpec(prompt, size, model) ويُدمج مع STYLE الثابت لضمان الاتساق
البصري. المخرجات → mobile/assets/images/generated/
"""
import argparse
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import httpx

from fal_common import MODEL_REGISTRY, estimate_cost, generate, get_fal_key

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "mobile" / "assets" / "images" / "generated"
DEFAULT_MODEL = "recraft_v3"


@dataclass(frozen=True)
class AssetSpec:
    prompt: str
    size: str
    model: str = DEFAULT_MODEL


# Recraft sizes: square_hd (1024×1024), landscape_4_3, portrait_4_3,
# landscape_16_9, portrait_16_9 — Flux 2 Pro accepts the same enum.
ASSETS: dict[str, AssetSpec] = {
    # — هوية/ماسكوت —
    "mascot_serene": AssetSpec(
        "a single serene crescent moon with a calm closed-eyes "
        "face profile, friendly and welcoming, warm and gentle",
        "square_hd",
    ),
    "mascot_celebrate": AssetSpec(
        "a serene crescent moon with a calm closed-eyes face "
        "profile surrounded by small stars and sparkles, joyful",
        "square_hd",
    ),
    "mascot_reading": AssetSpec(
        "a serene crescent moon with a calm closed-eyes face "
        "profile beside an open book with a small plant sprout, reverent",
        "square_hd",
    ),
    # — كروت مشاركة + متجر —
    "share_bg_celebration": AssetSpec(
        "a soft decorative frame for a greeting card: a "
        "crescent moon in a corner, scattered small stars and gentle light, "
        "mostly empty calm center, plenty of negative space for text",
        "square_hd",
    ),
    "store_hero": AssetSpec(
        "a warm hero scene: a crescent moon and a star above an open "
        "book from which a small plant sprout grows, symbolizing nurturing a "
        "child's growth and faith",
        "square_hd",
    ),
    # — فن المحطات —
    "milestone_first_prayer": AssetSpec(
        "a small prayer rug under a crescent moon and a "
        "star, symbolizing a child's first prayer",
        "square_hd",
    ),
    "milestone_first_surah": AssetSpec(
        "an open book with soft light rays and a star "
        "above it, symbolizing memorizing the first surah",
        "square_hd",
    ),
    "milestone_first_fast": AssetSpec(
        "a crescent moon with a small lantern and a star, "
        "symbolizing a child's first fast in Ramadan",
        "square_hd",
    ),
    # — شارات المحطات القديمة (تستبدل PNGs غير الموحّدة) —
    "badge_first_dua": AssetSpec(
        "a small serene crescent moon with closed eyes above praying hands, "
        "symbolizing a child's first dua, simple badge icon",
        "square_hd",
    ),
    "badge_good_manner": AssetSpec(
        "a small open book with a heart above it and a crescent moon, "
        "symbolizing good manners and akhlaq, simple badge icon",
        "square_hd",
    ),
    "badge_helped_others": AssetSpec(
        "two small hands reaching toward each other under a crescent moon "
        "and star, symbolizing helping others, simple badge icon",
        "square_hd",
    ),
    "badge_keeps_prayer": AssetSpec(
        "a small prayer rug with a crescent moon and a star above it, "
        "symbolizing keeping prayer, simple badge icon",
        "square_hd",
    ),
    "badge_quran_khatma": AssetSpec(
        "an open book with light rays and a crescent moon above it, "
        "symbolizing completing Quran khatma, simple badge icon",
        "square_hd",
    ),
    "badge_shahada": AssetSpec(
        "a bright guiding star above an open book, symbolizing the shahada "
        "and faith declaration, simple badge icon",
        "square_hd",
    ),
    # — onboarding / empty states —
    "onboarding_welcome": AssetSpec(
        "a cozy warm scene with a large crescent moon, an "
        "open book, a growing plant, and a few stars, inviting and gentle",
        "square_hd",
    ),
    "empty_journey": AssetSpec(
        "a gentle winding path marked with small stars leading "
        "toward a glowing crescent moon on the horizon, hopeful",
        "square_hd",
    ),
    "empty_children": AssetSpec(
        "a small plant sprout in soft soil under a crescent moon, "
        "inviting to start, calm",
        "square_hd",
    ),
    "empty_search": AssetSpec(
        "a simple magnifying glass with a small star inside, in the "
        "brand line-art style, calm and minimal",
        "square_hd",
    ),
    # — domain illustrations —
    "domain_islamic_parenting": AssetSpec(
        "a warm scene of a parent and child sitting "
        "together reading an open book under a crescent moon and a star, "
        "symbolizing Islamic upbringing",
        "square_hd",
    ),
    "domain_aqeedah": AssetSpec(
        "a serene crescent moon and a bright guiding star above an "
        "open book radiating gentle light from its pages, symbolizing the "
        "foundations of faith and belief, reverent and luminous",
        "square_hd",
    ),
    "domain_development": AssetSpec(
        "a small plant sprout growing from an open book, "
        "with a crescent moon and a star watching over it, symbolizing child "
        "development and growth",
        "square_hd",
    ),
    "domain_cyber": AssetSpec(
        "a serene crescent moon and a star above an open book with "
        "a small shield icon, symbolizing online safety and digital ethics",
        "square_hd",
    ),
    "domain_health": AssetSpec(
        "a small plant sprout with a crescent moon and a star "
        "above it, symbolizing health and wellness, calm and natural",
        "square_hd",
    ),
    # — banners —
    "banner": AssetSpec(
        "a wide warm banner: crescent moon, open book, growing plant, "
        "and stars, with plenty of calm center space, suitable for an app "
        "banner",
        "landscape_16_9",
    ),
    # — Play Store / app icon —
    "feature_graphic": AssetSpec(
        "a wide Play Store feature graphic: serene crescent moon with closed "
        "eyes, open book, small plant sprout and stars, solid teal background, "
        "plenty of calm left space for app name text, premium and spiritual",
        "landscape_16_9",
    ),
    "app_icon": AssetSpec(
        "a clean app icon: serene crescent moon doubling as a calm closed-eyes "
        "face profile, open book below it, small plant sprout and a star, "
        "compact centered composition, solid teal background",
        "square_hd",
    ),
}


def _backup_existing() -> None:
    if not OUT_DIR.exists() or not any(OUT_DIR.iterdir()):
        return
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_dir = OUT_DIR.parent / f"generated_backup_{ts}"
    shutil.copytree(OUT_DIR, backup_dir)
    print(f"🗄️  backed up existing assets → {backup_dir.relative_to(ROOT)}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="generate a single asset by name")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true", help="regenerate even if exists")
    ap.add_argument(
        "--model",
        choices=sorted(MODEL_REGISTRY),
        help="override the model for this run (does not change ASSETS defaults)",
    )
    ap.add_argument(
        "--no-backup", action="store_true", help="skip backing up existing assets before --force"
    )
    args = ap.parse_args()

    if args.only and args.only not in ASSETS:
        print(f"❌ unknown asset '{args.only}'. Known: {', '.join(ASSETS)}")
        return 1

    targets = {args.only: ASSETS[args.only]} if args.only else dict(ASSETS)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pending: dict[str, AssetSpec] = {}
    for name, spec in targets.items():
        if args.force or not (OUT_DIR / f"{name}.webp").exists():
            pending[name] = spec

    total_cost = 0.0
    for name, spec in pending.items():
        model_key = args.model or spec.model
        total_cost += estimate_cost(MODEL_REGISTRY[model_key], spec.size)

    print(f"📦 {len(targets)} asset(s) | {len(pending)} pending | "
          f"est. cost ${total_cost:.3f} (fal.ai gives $10 free credit)")
    if args.dry_run:
        for name, spec in pending.items():
            model_key = args.model or spec.model
            cost = estimate_cost(MODEL_REGISTRY[model_key], spec.size)
            print(f"  • {name} ({spec.size}, {model_key}, ${cost:.3f})")
        return 0

    key = get_fal_key()
    if not key:
        print("❌ set FAL_KEY (free signup at fal.ai → $10 credit auto-applied)")
        return 1

    if args.force and not args.no_backup:
        _backup_existing()

    with httpx.Client() as client:
        for name, spec in pending.items():
            model_key = args.model or spec.model
            model_spec = MODEL_REGISTRY[model_key]
            try:
                data = generate(client, key, model_spec, spec.prompt, spec.size)
                out_path = OUT_DIR / f"{name}.webp"
                out_path.write_bytes(data)
                print(f"  ✅ {out_path.name} ({len(data) // 1024} KB, {model_key})")
            except Exception as exc:  # noqa: BLE001
                print(f"  ❌ {name}: {exc}")
    print(f"\n💾 saved to {OUT_DIR.relative_to(ROOT)} — declare new files in "
          "pubspec.yaml assets, then use them in the app.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
