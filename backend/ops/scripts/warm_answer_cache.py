#!/usr/bin/env python3
"""Warm the answer cache with pre-generated answers for common pain-point questions.

Usage (inside Docker container on VPS):
    docker exec -w /app tg_backend python ops/scripts/warm_answer_cache.py [--max N]

Generates answers via Ollama (tg-tutor:v4) and stores them in the answer cache.
Each answer goes through the real pipeline prompt so cached responses are
indistinguishable from live-generated ones.

Safety: only stores answers that are (a) ≥80 chars, (b) generated locally,
(c) not flagged for review — same envelope as the live cache.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path

# Add backend root to path so we can import app.*
_backend_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_backend_root))

from app.config.llm_config import DEFAULT_HOME_OLLAMA_URL  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("warm_cache")

# ── Pain-point questions × age groups × domains ──────────────────────────
# Curated from _TOPIC_SEEDS + CHALLENGE_TOPICS + real parent questions.
# Each entry: (question, age_group, domain, severity)
QUESTIONS: list[tuple[str, str, str, str]] = [
    # === screens / digital ===
    ("ابني مدمن الموبايل ومش بيسيبه", "7-9", "cyber", "medium"),
    ("بنتي بتقضي كل وقتها على التيك توك", "10-12", "cyber", "medium"),
    ("طفلي ما بيركّز في المذاكرة بسبب الموبايل", "7-9", "cyber", "medium"),
    ("ولادي بيلعبوا ألعاب عنيفة على النت", "4-6", "cyber", "medium"),
    ("ابني بيتفرج على يوتيوب ساعات طويلة", "4-6", "cyber", "low"),
    ("بنتي خايفة من المحتوى اللي بتراه على السوشيال", "10-12", "cyber", "high"),
    ("طفلي بيفتح مواقع مش مناسبة لعمره", "13-15", "cyber", "high"),
    ("ابني بيلعب أونلاين مع ناس ما يعرفهم", "10-12", "cyber", "high"),

    # === behavior / tanrumts ===
    ("ابني عنيد ومش بيسمع الكلام خالص", "4-6", "development", "medium"),
    ("بنتي بتعمل نوبات غضب كبيرة في الشارع", "2-3", "development", "medium"),
    ("طفلي بيمثل مشاكل في المدرسة كل يوم", "7-9", "development", "medium"),
    ("ابني بيكذب عليا كل مرة", "4-6", "development", "medium"),
    ("بنتي بتضرب أخوها الصغير دايمًا", "4-6", "development", "medium"),
    ("طفلي مش بيسمع كلامي خالص", "7-9", "development", "medium"),
    ("ابني عنيف في اللعب مع أصحابه", "7-9", "development", "medium"),

    # === worship / islamic ===
    ("ابني مش عايز يصلي خالص", "7-9", "islamic_parenting", "medium"),
    ("بنتي مش عايز تلبس الحجاب", "13-15", "islamic_parenting", "medium"),
    ("طفلي مش مهتم بالقرآن خالص", "7-9", "islamic_parenting", "low"),
    ("ابني مش عايز يروح المسجد", "10-12", "islamic_parenting", "low"),
    ("بنتي بتسأل أسئلة عن الدين ومش لاقي أجوبة", "10-12", "aqeedah", "low"),
    ("طفلي مش فاهم ليه بنصلي", "4-6", "islamic_parenting", "low"),
    ("ابني بيستهزأ بالصلاة", "10-12", "islamic_parenting", "high"),

    # === sleep / eating ===
    ("طفلي مش عايز ينوم بدري خالص", "4-6", "development", "low"),
    ("بنتي بتخاف من الضلمة وبتبكي كل ليلة", "2-3", "development", "low"),
    ("ابني مش بيأكل غير أكلة واحدة بس", "4-6", "development", "low"),
    ("طفلي رافض الخضار تماماً", "2-3", "development", "low"),

    # === social / school ===
    ("طفلي بيتعرض للتنمر في المدرسة", "7-9", "development", "high"),
    ("ابني مخليش أصحاب في المدرسة", "7-9", "development", "medium"),
    ("بنتي خايفة تتكلم قدام الناس", "7-9", "development", "low"),
    ("طفلي مش عارف يتعامل مع زملائه", "4-6", "development", "low"),

    # === fear / anxiety ===
    ("طفلي خايف من الحيوانات", "2-3", "development", "low"),
    ("ابني خايف من الدكتور", "4-6", "development", "low"),
    ("بنتي بتبكي لما أسيبها في الحضانة", "2-3", "development", "low"),

    # === teen-specific ===
    ("ابني المراهق مش بيكلمني خالص", "13-15", "development", "medium"),
    ("بنتي المراهقة عصبية جداً وبتخاصمني", "13-15", "development", "medium"),
    ("طفلي المراهق مش مهتم بالدراسة خالص", "13-15", "development", "medium"),
    ("ابني عايز يسيب المدرسة", "16-18", "development", "high"),
    ("بنتي بتعاني من قلق المراهقة", "13-15", "development", "medium"),

    # === positive parenting ===
    ("ازاي أربي ابني على المسؤولية", "7-9", "development", "low"),
    ("ازاي أعزز ثقة طفلي بنفسه", "4-6", "development", "low"),
    ("ازاي أعلّم ابني الإيجابية", "4-6", "development", "low"),
    ("ازاي أحبب طفلي في الصلاة من غير عقاب", "4-6", "islamic_parenting", "low"),
    ("ازاي أقرب طفلي من القرآن", "7-9", "islamic_parenting", "low"),
    ("ازاي أتعامل مع عناد طفلي برفق", "4-6", "development", "low"),
]


def _system_prompt(domain: str) -> str:
    base = (
        "أنت مساعد تربوي ذكي للأهل العرب المسلمين. تقدم إجابات عملية وآمنة بدون تشخيص طبي ملزم أو فتوى شخصية.\n\n"
        "أجب دائماً على آخر سؤال في المحادثة فقط. لا تعيد الإجابة على أسئلة سابقة.\n\n"
        "عليك دائماً تكييف ومواءمة النصائح والخطوات لتناسب سن وقدرات الطفل.\n\n"
    )
    if domain in {"fiqh", "islamic_parenting", "aqeedah"}:
        return (
            "أنت مساعد تربوي إسلامي. عند أي تعارض — يُقدَّم الحكم الشرعي. "
            "لا تُفتِ في مسائل الحلال والحرام، لكن وضّح دائماً أن الإطار الإسلامي هو المرجع الأول.\n\n"
            + base
        )
    return base + "\n\nإذا تعارضت أي معلومة مع الثوابت الإسلامية، أشر إلى ذلك بوضوح وقدّم البديل الإسلامي."


def _user_prompt(question: str, age_group: str, domain: str, severity: str) -> str:
    return (
        f"العمر: {age_group} سنة\n"
        f"المجال: {domain}\n"
        f"الخطورة: {severity}\n"
        f"السؤال: {question}\n\n"
        "أجب بإجابة عملية مختصرة (٣-٥ سطور) مع خطوات واضحة. "
        "اذكر المصدر إن أمكن (حديث، آية، أو مرجع تربوي)."
    )


def _generate_one(
    base_url: str, model: str, question: str, age_group: str, domain: str, severity: str,
    timeout: int = 120,
) -> str | None:
    """Generate a single answer via Ollama."""
    import requests as req
    system = _system_prompt(domain)
    user = _user_prompt(question, age_group, domain, severity)
    full_prompt = f"{system}\n\n{user}"

    try:
        resp = req.post(
            f"{base_url}/api/generate",
            json={"model": model, "prompt": full_prompt, "stream": False,
                   "options": {"temperature": 0.3, "num_predict": 512}},
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("response", "").strip()
    except Exception as exc:
        log.warning("generate failed for %s: %s", question[:40], exc)
        return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Warm the answer cache")
    parser.add_argument("--max", type=int, default=50, help="Max questions to process")
    parser.add_argument("--dry-run", action="store_true", help="Print questions without generating")
    args = parser.parse_args()

    # Ensure cache is enabled
    os.environ.setdefault("ANSWER_CACHE_ENABLED", "true")

    import requests
    from app.services import answer_cache

    # Enable cache for this script
    answer_cache.ANSWER_CACHE_ENABLED = True

    base_url = os.environ.get("OLLAMA_BASE_URL", DEFAULT_HOME_OLLAMA_URL)
    model = os.environ.get("OLLAMA_MODEL", "tg-tutor:v4")

    log.info("Warming answer cache: model=%s, base_url=%s, max=%d", model, base_url, args.max)

    # Check Ollama is reachable
    try:
        r = requests.get(f"{base_url}/api/tags", timeout=10)
        r.raise_for_status()
        log.info("Ollama reachable, models: %s", [m["name"] for m in r.json().get("models", [])])
    except Exception as exc:
        log.error("Cannot reach Ollama at %s: %s", base_url, exc)
        sys.exit(1)

    questions = QUESTIONS[:args.max]
    stored = 0
    skipped = 0
    failed = 0

    for i, (question, age_group, domain, severity) in enumerate(questions, 1):
        log.info("[%d/%d] Q: %s (age=%s, domain=%s)", i, len(questions), question[:50], age_group, domain)

        if args.dry_run:
            continue

        # Check if already cached
        existing = answer_cache.lookup(question, age_group, domain, severity)
        if existing:
            log.info("  → already cached, skipping")
            skipped += 1
            continue

        # Generate answer
        t0 = time.monotonic()
        answer = _generate_one(base_url, model, question, age_group, domain, severity)
        elapsed = time.monotonic() - t0

        if not answer or len(answer) < 80:
            log.warning("  → answer too short or empty (%d chars), skipping", len(answer or ""))
            failed += 1
            continue

        # Store in cache
        ok = answer_cache.store(question, age_group, domain, severity, answer)
        if ok:
            log.info("  → stored (%d chars, %.1fs)", len(answer), elapsed)
            stored += 1
        else:
            log.warning("  → store failed")
            failed += 1

        # Small delay to avoid hammering Ollama
        time.sleep(0.5)

    log.info("Done: stored=%d, skipped=%d, failed=%d, total=%d", stored, skipped, failed, len(questions))

    # Print cache stats
    try:
        conn = answer_cache._conn()
        count = conn.execute("SELECT COUNT(*) FROM answer_cache").fetchone()[0]
        conn.close()
        log.info("Cache total entries: %d", count)
    except Exception:
        pass


if __name__ == "__main__":
    main()
