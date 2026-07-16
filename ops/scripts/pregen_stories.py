"""Nightly story pre-generation batch — growth plan §5.1.

Fills the story_cache up to VARIANTS_PER_KEY variants for every
(theme × age_group × gender) combination, generating at most --max stories per
run so a single night never hammers the local model. Uses the canonical hero
names (سالم/سارة) — see story_service for the privacy rationale.

Run inside the backend container (has the models + DB):
    docker exec -w /app tg_backend python ops/scripts/pregen_stories.py --max 20
Suggested VPS crontab (host):
    30 2 * * * docker exec -w /app tg_backend python ops/scripts/pregen_stories.py --max 20 >> /var/log/tg-story-pregen.log 2>&1
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("pregen_stories")

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.routers.program import _VALID_AGE_GROUPS, STORY_THEMES  # noqa: E402
from app.services import story_service  # noqa: E402
from app.services.ai_gateway import get_gateway  # noqa: E402

_GENDER_WORD = {"male": "ولد", "female": "بنت"}


def _prompt(hero: str, gender: str, value: str) -> str:
    return (
        "أنت كاتب قصص أطفال عربي. اكتب قصة قصيرة (٣ إلى ٥ فقرات) بالعربية "
        "الفصحى الميسرة، آمنة تماماً ومناسبة للأطفال، خالية من العنف أو الخوف "
        "المبالغ فيه، ومنسجمة مع القيم الإسلامية.\n"
        f"بطل القصة {_GENDER_WORD[gender]} اسمه «{hero}». القصة تعلّم قيمة: {value}.\n"
        f"استخدم اسم «{hero}» كما هو في كل مرة دون تصغير أو تحريف.\n"
        "اجعل لها عنواناً جذاباً في أول سطر، ثم القصة، واختمها بدرس مستفاد "
        "في جملة واحدة تبدأ بـ «الدرس المستفاد:». لا تكتب أي شيء خارج القصة."
    )


async def main(max_generations: int, dry_run: bool) -> None:
    generated = failed = 0
    for theme, value in STORY_THEMES.items():
        for age_group in sorted(_VALID_AGE_GROUPS):
            for gender, hero in story_service.HERO_NAMES.items():
                if generated + failed >= max_generations:
                    logger.info("run budget reached (%d), stopping", max_generations)
                    logger.info("done: %d stored, %d failed", generated, failed)
                    return
                have = story_service.variants_count(theme, age_group, gender)
                missing = story_service.VARIANTS_PER_KEY - have
                for _ in range(max(0, missing)):
                    if generated + failed >= max_generations:
                        break
                    if dry_run:
                        logger.info("[dry-run] would generate %s/%s/%s", theme, age_group, gender)
                        generated += 1
                        continue
                    try:
                        result = await get_gateway().generate(
                            _prompt(hero, gender, value),
                            options={"temperature": 0.8},
                            route_reason="story_pregen",
                        )
                        story = (result.text or "").strip()
                        if story_service.store_pregen_story(
                            theme, age_group, gender, hero, story
                        ):
                            generated += 1
                            logger.info("stored %s/%s/%s (%d chars)", theme, age_group, gender, len(story))
                        else:
                            failed += 1
                            logger.warning("rejected %s/%s/%s (validation)", theme, age_group, gender)
                    except Exception as exc:  # noqa: BLE001
                        failed += 1
                        logger.warning("generation failed %s/%s/%s: %s", theme, age_group, gender, exc)
    logger.info("done: %d stored, %d failed", generated, failed)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", type=int, default=20, help="max generations this run")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    asyncio.run(main(args.max, args.dry_run))
