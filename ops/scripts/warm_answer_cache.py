#!/usr/bin/env python3
"""Warm the answer cache with pre-computed answers for top pain-point questions.

Usage (VPS cron, daily at 3:00 UTC after story pregen):
    docker exec -w /app tg_backend python ops/scripts/warm_answer_cache.py

Generates answers for the top ~50 pain-point questions across 7 age groups
via the real pipeline, storing them in the answer cache for high hit-rate
from day one.

Requires: Ollama on tg-home + answer_cache.py in the backend.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path

# Add backend root to path
_backend_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_backend_root))


# Top pain-point questions × age groups (from _TOPIC_SEEDS in coach_service.py)
_QUESTIONS = [
    # Sleep
    "طفلي يرفض النوم ويستيقظ كثيرًا بالليل",
    "طفلي خايف من الظلام وعايز ينام معايا",
    # Stubbornness / Tantrums
    "ابني كثير العناد ونوبات الغضب",
    "كيف أتعامل مع نوبات الغضب؟",
    # Eating
    "طفلي يرفض الأكل — أعمل إيه؟",
    "طفلي بياكل أكل قليل جدًا",
    # Prayer
    "ابني 5 سنين بيرفض الصلاة، أعمل إيه؟",
    "كيف أعوّد طفلي على الصلاة بانتظام؟",
    # Screen time
    "طفلي لا يترك التابلت والشاشات",
    "ابني مشغول بالألعاب الإلكترونية طوال اليوم",
    # Lying
    "ابني يكذب أحيانًا — كيف أتصرف؟",
    # Homework
    "ابني يماطل في واجباته المدرسية",
    # Speech delay
    "طفلي تأخر في الكلام — متى أقلق؟",
    # Study
    "طفلي لا يحب المذاكرة",
    # Online safety
    "كيف أحمي طفلي على الإنترنت؟",
    # Teen defiant
    "ابني المراهق يعاند ولا يسمع الكلام",
    # Social media
    "ابنتي مشغولة بالسوشيال ميديا والمقارنات",
    # Teen prayer
    "كيف أحافظ على صلاة ابني المراهق؟",
    # Talking to older
    "كيف أحاور ابني الكبير دون صدام؟",
    # Friends
    "كيف أناقش ابني في اختيار أصحابه؟",
]

_AGE_GROUPS = [
    "prenatal-1",
    "2-3",
    "4-6",
    "7-9",
    "10-12",
    "13-15",
    "16-18",
]


async def _generate_answer(question: str, age_group: str) -> tuple[str, str, str] | None:
    """Generate an answer via the real AI pipeline.
    
    Returns: (answer, domain, severity) or None if generation fails.
    """
    try:
        from app.services.ai_gateway import AIGateway
        from app.services.retrieval import retrieve_relevant_units

        # Try islamic_parenting first (most relevant for parenting questions)
        domains = ["islamic_parenting", "aqeedah", "medical", "development", "cyber"]
        
        for domain in domains:
            units = retrieve_relevant_units(question, domain=domain, age_group=age_group, top_k=3)
            if units:
                # Build context from units
                context_parts = []
                for u in units[:3]:
                    content = u.get("document", "")
                    metadata = u.get("metadata", {})
                    source = metadata.get("reference_info", "")
                    context_parts.append(f"الوحدة: {content}\nالمصدر: {source}")

                context = "\n\n".join(context_parts)

                # Generate answer using AI Gateway (async)
                prompt = f"""أنت المربي الذكي — مساعد تربوي إسلامي. أجب على سؤال الوالد بناءً على الوحدات المعرفية التالية فقط.

السؤال: {question}
عمر الطفل: {age_group}

الوحدات المعرفية:
{context}

أجب بإجابة عملية مختصرة مناسبة لعمر الطفل، واذكر المصدر في سطر يبدأ بـ 📚 المصدر:"""

                gateway = AIGateway()
                result = await gateway.generate(prompt)
                answer = result.text if hasattr(result, 'text') else str(result)
                
                # Determine severity from the question
                severity = "خفيف"  # Default
                if " refuses " in question.lower() or "يرفض" in question:
                    severity = "خفيف"
                elif "عناد" in question or "غضب" in question:
                    severity = "متوسط"
                
                return (answer, domain, severity)
        
        return None
    except Exception as e:
        print(f"  Error generating answer for '{question[:30]}...' ({age_group}): {e}", file=sys.stderr)
        return None


def _store_in_cache(question: str, age_group: str, domain: str, severity: str, answer: str) -> bool:
    """Store the generated answer in the answer cache."""
    try:
        from app.services.answer_cache import store
        store(question, age_group, domain, severity, answer)
        return True
    except Exception as e:
        print(f"  Error storing in cache: {e}", file=sys.stderr)
        return False


async def _main():
    """Warm the answer cache with pre-computed answers."""
    print(f"Starting cache warming: {len(_QUESTIONS)} questions × {len(_AGE_GROUPS)} age groups")
    print(f"Maximum possible entries: {len(_QUESTIONS) * len(_AGE_GROUPS)}")

    warmed = 0
    errors = 0

    for question in _QUESTIONS:
        for age_group in _AGE_GROUPS:
            print(f"  Processing: '{question[:40]}...' ({age_group})")

            result = await _generate_answer(question, age_group)
            if result:
                answer, domain, severity = result
                if _store_in_cache(question, age_group, domain, severity, answer):
                    warmed += 1
                    print(f"    ✓ Cached")
                else:
                    errors += 1
                    print(f"    ✗ Storage failed")
            else:
                errors += 1
                print(f"    ✗ No answer generated")

            # Small delay to avoid overwhelming the pipeline
            await asyncio.sleep(0.5)

    print(f"\nCache warming complete: {warmed} entries cached, {errors} errors")
    return 0 if errors == 0 else 1


def main():
    """Synchronous entry point."""
    return asyncio.run(_main())


if __name__ == "__main__":
    sys.exit(main())
