#!/usr/bin/env python3
"""
gen_launch — أصول إطلاق + هيرو صفحة الهبوط (نفس هوية gen_visuals، بلا نص).

الموديل الافتراضي: Recraft V3. (جُرّب Flux 2 Pro ونانو بنانا برو ورُفضا بصرياً
وبفشل عرض الكابشن العربي — راجع fal_common.py لو احتجت تجرّب موديل تاني
على أصل واحد بـ --model.)

التشغيل:
    export FAL_KEY="..."        # المفتاح الحالي (يُحرَق بالـrotate بعدها)
    python ops/tools/gen_launch.py [--dry-run]
    python ops/tools/gen_launch.py --only social_feature_ai --model nano_banana_pro

المخرجات → docs/marketing/launch_graphics/  (والهيرو يُنسخ للباكند static يدويًا).
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
OUT_DIR = ROOT / "docs" / "marketing" / "launch_graphics"
DEFAULT_MODEL = "recraft_v3"


@dataclass(frozen=True)
class AssetSpec:
    prompt: str
    size: str
    model: str = DEFAULT_MODEL


ASSETS: dict[str, AssetSpec] = {
    "landing_hero": AssetSpec(
        "a warm welcoming hero banner: a large crescent moon with a serene "
        "calm face beside an open book with a growing sprout and stars, soft "
        "glow, plenty of calm empty space",
        "landscape_16_9",
    ),
    "social_announce_square": AssetSpec(
        "a centered celebratory brand emblem: crescent moon, open book, plant "
        "sprout and a bright star with gentle radiating light, balanced for a "
        "social post",
        "square_hd",
    ),
    "social_announce_wide": AssetSpec(
        "a wide gentle scene of a crescent moon and stars over an open book "
        "with a sprout, calm spiritual horizon, room for a headline",
        "landscape_16_9",
    ),
    "social_feature_ai": AssetSpec(
        "a soft speech bubble next to an open book and a crescent moon, "
        "symbolizing a wise gentle assistant answering questions",
        "square_hd",
    ),
    "social_feature_journey": AssetSpec(
        "a gentle winding path marked with small stars and milestone flags "
        "leading toward a glowing crescent moon, symbolizing a child's growth "
        "journey",
        "square_hd",
    ),
}


def _backup_existing() -> None:
    if not OUT_DIR.exists() or not any(OUT_DIR.iterdir()):
        return
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_dir = OUT_DIR.parent / f"launch_graphics_backup_{ts}"
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
    pending: dict[str, AssetSpec] = {
        name: spec for name, spec in targets.items()
        if args.force or not (OUT_DIR / f"{name}.webp").exists()
    }

    total_cost = sum(
        estimate_cost(MODEL_REGISTRY[args.model or spec.model], spec.size)
        for spec in pending.values()
    )
    print(f"📦 {len(targets)} assets | {len(pending)} pending | est ${total_cost:.3f}")
    if args.dry_run:
        for name, spec in pending.items():
            model_key = args.model or spec.model
            cost = estimate_cost(MODEL_REGISTRY[model_key], spec.size)
            print(f"  • {name} ({spec.size}, {model_key}, ${cost:.3f})")
        return 0

    key = get_fal_key()
    if not key:
        print("❌ set FAL_KEY")
        return 1

    if args.force and not args.no_backup:
        _backup_existing()

    with httpx.Client() as client:
        for name, spec in pending.items():
            model_key = args.model or spec.model
            model_spec = MODEL_REGISTRY[model_key]
            try:
                data = generate(client, key, model_spec, spec.prompt, spec.size)
                (OUT_DIR / f"{name}.webp").write_bytes(data)
                print(f"  ✅ {name}.webp ({len(data) // 1024} KB, {model_key})")
            except Exception as exc:  # noqa: BLE001
                print(f"  ❌ {name}: {exc}")
    print(f"\n💾 {OUT_DIR.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
