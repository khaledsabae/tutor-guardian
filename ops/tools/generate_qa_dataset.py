"""
Generate QA dataset for Tutor Guardian fine-tuning.
Reads knowledge units from the KB and uses an LLM to generate realistic
parent questions + answers, saving as a JSONL fine-tuning dataset.

Usage:
    python ops/tools/generate_qa_dataset.py \\
        --model gemma4:e4b \\
        --questions-per-unit 3 \\
        --output ops/data/qa_dataset.jsonl

The script can resume from a checkpoint file and skips units that already have
questions written. Run overnight (4-6h for 292 units).
"""
import argparse
import json
import logging
import os
import random
import sys
import time
from pathlib import Path

# ── Project path setup ────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("gen_qa")

# ── Ollama API ────────────────────────────────────────────────────────
import requests as http_requests


def _call_ollama(prompt: str, model: str, base_url: str = "http://localhost:11434",
                 timeout: int = 180) -> str:
    """Call Ollama /api/generate and return the response text."""
    resp = http_requests.post(
        f"{base_url}/api/generate",
        json={"model": model, "prompt": prompt, "stream": False, "options": {"temperature": 0.6}},
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json().get("response", "").strip()


# ── Knowledge unit loader ─────────────────────────────────────────────
def load_all_units() -> list[dict]:
    """Load knowledge units from the KB schema JSON files."""
    from app.services.knowledge_loader import load_default_knowledge_units
    raw = load_default_knowledge_units()
    units = []
    for u in raw:
        units.append({
            "id": u.id,
            "domain": u.domain,
            "age_group": u.age_group,
            "behavior_type": u.behavior_type,
            "severity": u.severity,
            "text_simplified": u.text_simplified,
            "reference_info": u.reference_info,
        })
    return units


# ── Question generation prompt ────────────────────────────────────────
GENERATION_PROMPT_TEMPLATE = """أنت خبير تربوي عربي. لديك نص من قاعدة المعرفة التربوية.

مهمتك: توليد {num_questions} أسئلة واقعية يطرحها أهل عرب على مختص تربوي، بحيث تكون إجابة كل سؤال موجودة في النص أدناه.

قواعد:
1. كل سؤال يجب أن يكون طبيعياً كما يسأله أحد الوالدين حرفياً.
2. تنوع الأسئلة: بعضها مباشر (كيف) وبعضها وصفي (ماذا أفعل) وبعضها استفساري (هل...).
3. لا تختلق معلومات — الإجابة الحقيقية موجودة في النص.
4. أخرج الأسئلة فقط، سؤال واحد في كل سطر، بدون ترقيم أو مقدمة.
5. اكتب بالعربية الفصحى الميسّرة (لغة مفهومة للوالد العادي).

نص قاعدة المعرفة:
---
{context}
---

الأسئلة:"""

ANSWER_PROMPT_TEMPLATE = """أنت مساعد تربوي. أجب على سؤال الوالد/الوالدة التالي بناءً على النص المقدم فقط.

السؤال: {question}

النص المرجعي:
---
{context}
---

تعليمات الرد:
- الرد 4-6 جمل، بالعربية الفصحى الميسرة
- استند إلى النص أعلاه فقط
- لا تختلق معلومات
- لا تكرر الأفكار
- اختم بـ: 📚 المصدر: {reference}

الرد:"""


# ── Main generation loop ──────────────────────────────────────────────
def generate_questions_for_unit(unit: dict, model: str, num: int = 3,
                                base_url: str = "http://localhost:11434") -> list[str]:
    """Generate realistic parent questions from a knowledge unit."""
    context = unit["text_simplified"]
    # Truncate very long contexts
    if len(context) > 2000:
        context = context[:2000] + "..."
    prompt = GENERATION_PROMPT_TEMPLATE.format(context=context, num_questions=num)
    try:
        raw = _call_ollama(prompt, model, base_url)
        questions = [q.strip().strip("0123456789.-) ") for q in raw.split("\n") if q.strip()]
        # Filter out lines that look like headings or empty
        questions = [q for q in questions if len(q) > 10 and "سؤال" not in q[:8] and "النص" not in q]
        random.shuffle(questions)
        return questions[:num]
    except Exception as e:
        logger.warning("  Failed to generate questions: %s", e)
        return []


def generate_answer_for_question(question: str, unit: dict, model: str,
                                 base_url: str = "http://localhost:11434") -> str:
    """Generate a reference answer using the knowledge unit as context."""
    context = unit["text_simplified"]
    if len(context) > 2000:
        context = context[:2000] + "..."
    prompt = ANSWER_PROMPT_TEMPLATE.format(
        question=question, context=context,
        reference=unit.get("reference_info", "مصدر غير مذكور"),
    )
    try:
        return _call_ollama(prompt, model, base_url)
    except Exception as e:
        logger.warning("  Answer generation failed: %s", e)
        return ""


def main():
    parser = argparse.ArgumentParser(description="Generate QA dataset from KB units")
    parser.add_argument("--model", default="gemma4:e4b",
                        help="Ollama model for generation")
    parser.add_argument("--questions-per-unit", type=int, default=3,
                        help="Number of questions per unit (default: 3)")
    parser.add_argument("--output", default=str(PROJECT_ROOT / "ops" / "data" / "qa_dataset.jsonl"),
                        help="Output JSONL path")
    parser.add_argument("--ollama-url", default="http://localhost:11434",
                        help="Ollama base URL")
    parser.add_argument("--checkpoint", default=str(PROJECT_ROOT / "ops" / "data" / "qa_checkpoint.json"),
                        help="Checkpoint file (resume support)")
    parser.add_argument("--max-units", type=int, default=0,
                        help="Max units to process (0 = all)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Only list units, don't generate")
    args = parser.parse_args()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    checkpoint_path = Path(args.checkpoint)
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)

    # ── Load units ────────────────────────────────────────────────────
    logger.info("Loading knowledge units...")
    all_units = load_all_units()
    logger.info("Loaded %d units", len(all_units))

    if args.dry_run:
        domains = set(u["domain"] for u in all_units)
        ages = set(u["age_group"] for u in all_units)
        logger.info("Domains: %s", domains)
        logger.info("Age groups: %s", ages)
        print(f"\nWould generate ~{len(all_units) * args.questions_per_unit} Q&A pairs")
        return

    # ── Load checkpoint ───────────────────────────────────────────────
    processed_ids = set()
    if checkpoint_path.exists():
        with open(checkpoint_path) as f:
            processed_ids = set(json.load(f))
        logger.info("Checkpoint loaded: %d units already processed", len(processed_ids))

    # ── Load existing output ──────────────────────────────────────────
    existing_lines = []
    if output_path.exists():
        with open(output_path, encoding="utf-8") as f:
            existing_lines = f.readlines()
        logger.info("Existing output: %d Q&A pairs", len(existing_lines))

    max_count = args.max_units or len(all_units)
    to_process = [u for u in all_units if u["id"] not in processed_ids][:max_count]
    logger.info("Units to process: %d (skipping %d done)", len(to_process), len(processed_ids))

    # ── Generation loop ───────────────────────────────────────────────
    total_generated = len(existing_lines)
    start_time = time.time()

    for idx, unit in enumerate(to_process):
        unit_start = time.time()
        logger.info("[%d/%d] Processing unit: %s (domain=%s, age=%s)",
                     idx + 1, len(to_process), unit["id"], unit["domain"], unit["age_group"])

        # Generate questions
        questions = generate_questions_for_unit(
            unit, args.model, args.questions_per_unit, args.ollama_url
        )
        if not questions:
            logger.warning("  No questions generated, skipping")
            processed_ids.add(unit["id"])
            continue

        # Generate answers and write
        new_records = 0
        for q in questions:
            answer = generate_answer_for_question(q, unit, args.model, args.ollama_url)
            if not answer:
                continue
            record = {
                "instruction": q,
                "output": answer,
                "domain": unit["domain"],
                "age_group": unit["age_group"],
                "behavior_type": unit.get("behavior_type", ""),
                "reference": unit.get("reference_info", "مصدر غير مذكور"),
            }
            with open(output_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
            total_generated += 1
            new_records += 1

        # Mark processed
        processed_ids.add(unit["id"])
        with open(checkpoint_path, "w") as f:
            json.dump(list(processed_ids), f)

        elapsed = time.time() - unit_start
        rate = (idx + 1) / (time.time() - start_time) * 60  # units/hour
        logger.info("  Generated %d Q&A pairs in %.1fs (rate: ~%.0f units/hr)",
                     new_records, elapsed, rate)

        # Brief delay between units to avoid rate-limiting
        if args.questions_per_unit >= 3:
            time.sleep(1)

    # ── Summary ───────────────────────────────────────────────────────
    total_time = time.time() - start_time
    logger.info("=" * 50)
    logger.info("Done! Generated %d total Q&A pairs", total_generated)
    logger.info("Processed %d units in %.1f min", len(processed_ids), total_time / 60)
    logger.info("Output: %s", output_path.resolve())
    logger.info("Checkpoint: %s", checkpoint_path.resolve())

    if os.path.exists(output_path):
        line_count = sum(1 for _ in open(output_path))
        logger.info("File line count: %d", line_count)


if __name__ == "__main__":
    main()
