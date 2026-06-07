"""
Process collected real-world parent questions through the RAG pipeline.

Reads collected_questions.json, generates RAG-grounded answers for each question,
and writes to qa_collected.jsonl (separate from the KB-generated dataset).

Usage:
    python ops/tools/process_collected_questions.py \\
        --input ops/data/collected_questions.json \\
        --output ops/data/qa_collected.jsonl \\
        --ollama-url http://100.109.163.64:11434 \\
        --model gemma4:e4b
"""
import argparse
import json
import logging
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("process_q")

import requests as http_requests


def call_ollama(prompt: str, model: str, base_url: str, timeout: int = 240) -> str:
    resp = http_requests.post(
        f"{base_url}/api/generate",
        json={"model": model, "prompt": prompt, "stream": False, "options": {"temperature": 0.5}},
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json().get("response", "").strip()


def get_retrieved_context(question: str, domain: str, age_group: str) -> list[dict]:
    """Run ChromaDB retrieval for the question."""
    from app.services.retrieval import retrieve_multi_domain, _ensure_index
    from app.services.domain_classifier import classify_domains

    _ensure_index()
    detected_domains = classify_domains(question)
    if domain and domain not in detected_domains:
        detected_domains = [domain] + detected_domains

    results = retrieve_multi_domain(
        query_text=question,
        domains=detected_domains[:2],
        age_group=age_group or "unspecified",
        top_k_per_domain=2,
        behavior_type="",
    )
    return [r for r in results if r.get("distance", 1.0) < 0.90]


ANSWER_PROMPT = """أنت مساعد تربوي ذكي للأهل العرب المسلمين. تقدم إجابات عملية وآمنة.
أجب دائماً على السؤال الأخير فقط. لا تعيد الإجابة على أسئلة سابقة.

[سؤال الوالد/الوالدة — أجب على هذا فقط]
{question}
الفئة العمرية: {age_group}

[مصادر ومعلومات موثقة]
{context}

[REFERENCE_INFO]
{source_line}

تعليمات الرد:
- أجب على السؤال أعلاه فقط.
- استند إلى المصادر المذكورة فقط.
- الرد 4-6 جمل عملية، بالعربية الفصحى الميسرة.
- لا تكرر الأفكار.
- اختم بـ: 📚 المصدر: {source_line}
- إن كان السياق غير كافٍ: «لا تتوفر لديّ معلومات موثقة حول هذا — يُنصح بمراجعة متخصص»
"""

NO_CONTEXT_PROMPT = """أنت مساعد تربوي ذكي للأهل العرب المسلمين. تقدم إجابات عملية وآمنة.

[سؤال الوالد/الوالدة]
{question}
الفئة العمرية: {age_group}
المجال: {domain}

تعليمات الرد:
- أجب بـ 4-5 جمل عملية مبنية على المعرفة التربوية العامة.
- بالعربية الفصحى الميسرة.
- لا تشخّص طبياً ولا تُفتِ دينياً.
- إن كانت الحالة تستوجب متخصصاً، أشر إلى ذلك.
- اختم بـ: 💡 ملاحظة: لا تتوفر مصادر موثقة بشكل مباشر — يُنصح بمراجعة متخصص للحالات المعقدة.
"""


def generate_answer(question: dict, model: str, base_url: str) -> str:
    q_text = question["question"]
    domain = question.get("domain", "medical")
    age_group = question.get("age_group", "unspecified")

    try:
        units = get_retrieved_context(q_text, domain, age_group)
    except Exception as e:
        logger.warning("Retrieval failed: %s — using no-context prompt", e)
        units = []

    if units:
        parts = []
        sources = []
        for u in units:
            doc = u.get("document", "") or u.get("metadata", {}).get("text_simplified", "")
            ref = u.get("metadata", {}).get("reference_info", "")
            parts.append(doc[:600])
            if ref and ref not in sources:
                sources.append(ref)
        context = "\n---\n".join(parts)
        source_line = " · ".join(sources[:2]) if sources else "مصدر غير مذكور"
        prompt = ANSWER_PROMPT.format(
            question=q_text, age_group=age_group,
            context=context, source_line=source_line,
        )
    else:
        prompt = NO_CONTEXT_PROMPT.format(
            question=q_text, age_group=age_group, domain=domain,
        )

    return call_ollama(prompt, model, base_url)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default=str(PROJECT_ROOT / "ops" / "data" / "collected_questions.json"))
    parser.add_argument("--output", default=str(PROJECT_ROOT / "ops" / "data" / "qa_collected.jsonl"))
    parser.add_argument("--checkpoint", default=str(PROJECT_ROOT / "ops" / "data" / "qa_collected_checkpoint.json"))
    parser.add_argument("--ollama-url", default="http://100.109.163.64:11434")
    parser.add_argument("--model", default="gemma4:e4b")
    parser.add_argument("--skip-low-quality", action="store_true",
                        help="Skip questions without real source_url (template-generated)")
    args = parser.parse_args()

    with open(args.input, encoding="utf-8") as f:
        questions = json.load(f)

    if args.skip_low_quality:
        questions = [q for q in questions if q.get("source_url", "").startswith("http")]
        logger.info("Filtered to %d high-quality questions (with real URLs)", len(questions))

    checkpoint_path = Path(args.checkpoint)
    done_indices = set()
    if checkpoint_path.exists():
        with open(checkpoint_path) as f:
            done_indices = set(json.load(f))
        logger.info("Resuming: %d already done", len(done_indices))

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    total = len(questions)
    start = time.time()

    for idx, q in enumerate(questions):
        if idx in done_indices:
            continue

        logger.info("[%d/%d] %s (%s, %s)", idx + 1, total,
                    q["question"][:60] + "...", q.get("domain"), q.get("age_group"))

        try:
            answer = generate_answer(q, args.model, args.ollama_url)
            if not answer or len(answer) < 20:
                logger.warning("  Short/empty answer, skipping")
                done_indices.add(idx)
                continue

            record = {
                "instruction": q["question"],
                "output": answer,
                "domain": q.get("domain", "medical"),
                "age_group": q.get("age_group", "unspecified"),
                "behavior_type": "",
                "reference": q.get("source", "مصدر غير مذكور"),
                "source_type": "real" if q.get("source_url", "").startswith("http") else "template",
            }
            with open(output_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

            done_indices.add(idx)
            with open(checkpoint_path, "w") as f:
                json.dump(list(done_indices), f)

            elapsed = time.time() - start
            rate = len(done_indices) / elapsed * 60
            logger.info("  Done in %.0fs | Rate: %.1f/min", time.time() - start, rate)

        except Exception as e:
            logger.warning("  Failed: %s", e)
            time.sleep(5)

    logger.info("=" * 50)
    logger.info("Finished. Output: %s", output_path)
    if output_path.exists():
        count = sum(1 for _ in open(output_path))
        logger.info("Total Q&A pairs written: %d", count)


if __name__ == "__main__":
    main()
