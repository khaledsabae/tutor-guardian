#!/usr/bin/env python3
"""Fine-tune dataset v2 generator — Azure DeepSeek backed.

Produces ~4k instruction/output pairs in the Phase-3 structured answer
template so tg-tutor:v2 natively emits it:

  direct answer → numbered practical steps → («متى تراجع متخصصاً» when
  relevant) → «📚 المصادر: …» final line.

Mix (approved plan):
  singles ~2000 · multi-turn ~800 · cross-unit synthesis ~600 ·
  adversarial/abstention ~400 · colloquial ~300

Checkpointed per task — safe to kill and rerun (resumes where it left).

Backends:
  --backend ollama (default) — fully local via the home server
    (qwen2.5:7b); nothing leaves the machines.
  --backend azure — requires AZURE_OPENAI_* env (explicit opt-in only).

Usage:
  python ops/tools/generate_dataset_v2.py --output ops/data/qa_dataset_v2.jsonl
"""
from __future__ import annotations

import argparse
import json
import logging
import random
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s",
                    datefmt="%H:%M:%S")
logger = logging.getLogger("gen_v2")

random.seed(7)

ANSWER_TEMPLATE_RULES = """قواعد صياغة الإجابة (التزم بها في كل إجابة):
- ابدأ بالجواب المباشر في جملة أو جملتين.
- ثم خطوات عملية مرقّمة (1. 2. 3.) يستطيع الوالد تنفيذها فعلاً.
- إن كان للموضوع جانب صحي أو شرعي دقيق أضف سطراً يبدأ بـ «متى تراجع متخصصاً:».
- اختم بسطر أخير: 📚 المصادر: <اسم المرجع>
- استند حصراً إلى نص الوحدة المعطاة — لا تخترع أي معلومة أو حكم أو رقم.
- العربية الفصحى الميسرة، بأسلوب دافئ محترم."""


def azure_client():
    import os
    from openai import AzureOpenAI

    return AzureOpenAI(
        api_key=os.environ["AZURE_OPENAI_API_KEY"],
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-12-01-preview"),
    ), os.environ.get("AZURE_OPENAI_DEPLOYMENT", "DeepSeek-V4-Flash")


BACKEND = "ollama"  # set by main() from --backend
OLLAMA_BASE = None
OLLAMA_MODEL = "qwen2.5:7b"


def chat(client, model, prompt: str, max_tokens: int = 4000, retries: int = 5) -> str:
    if BACKEND == "ollama":
        import requests
        for attempt in range(retries):
            try:
                r = requests.post(
                    f"{OLLAMA_BASE}/api/chat",
                    json={"model": OLLAMA_MODEL,
                          "messages": [{"role": "user", "content": prompt}],
                          "stream": False,
                          "options": {"temperature": 0.7,
                                      "num_predict": max_tokens}},
                    timeout=1800,
                )
                r.raise_for_status()
                text = r.json().get("message", {}).get("content", "")
                if text.strip():
                    return text
                logger.warning("ollama returned empty — retry")
            except Exception as exc:  # noqa: BLE001
                logger.warning("ollama error %s — retry", exc.__class__.__name__)
            time.sleep(10 * (attempt + 1))
        raise RuntimeError("ollama failed after retries")

    for attempt in range(retries):
        try:
            r = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens, temperature=0.7,
            )
            return r.choices[0].message.content or ""
        except Exception as exc:  # noqa: BLE001
            wait = min(2**attempt * 5, 120)
            logger.warning("azure error %s — retry in %ss", exc.__class__.__name__, wait)
            time.sleep(wait)
    raise RuntimeError("azure failed after retries")


def parse_pairs(raw: str) -> list[dict]:
    start, end = raw.find("["), raw.rfind("]")
    if start == -1 or end == -1:
        return []
    try:
        rows = json.loads(raw[start:end + 1])
        return [r for r in rows if isinstance(r, dict)
                and r.get("question") and r.get("answer")]
    except Exception:  # noqa: BLE001
        return []


def load_units() -> list[dict]:
    from app.services.knowledge_loader import load_default_knowledge_units
    out = []
    for u in load_default_knowledge_units():
        if (u.text_simplified or "").strip():
            out.append({
                "id": u.id, "domain": u.domain, "age_group": u.age_group,
                "behavior_type": u.behavior_type, "reference": u.reference_info,
                "text": u.text_simplified,
            })
    return out


def row(question: str, answer: str, unit: dict, kind: str,
        history: str = "") -> dict:
    instruction = question if not history else (
        f"[سياق المحادثة السابقة]\n{history}\n\n[السؤال الحالي]\n{question}"
    )
    return {
        "instruction": instruction.strip(),
        "output": answer.strip(),
        "domain": unit.get("domain", ""),
        "age_group": unit.get("age_group", ""),
        "behavior_type": unit.get("behavior_type", ""),
        "reference": unit.get("reference", ""),
        "unit_id": unit.get("id", ""),
        "kind": kind,
    }


# ── Task prompts ──────────────────────────────────────────────────────

SINGLES_PROMPT = """أنت تبني بيانات تدريب لمساعد تربوي عربي للأهل.
من الوحدة المعرفية أدناه، أنشئ {n} أزواج (سؤال والد واقعي، إجابة المساعد).
أسئلة متنوعة: بعضها فصحى وبعضها بعامية مصرية أو خليجية، بزوايا مختلفة من الوحدة.

{rules}
في سطر المصادر استخدم: 📚 المصادر: {reference}

أعد JSON array فقط:
[{{"question": "...", "answer": "..."}}, ...]

الوحدة (عمر {age}):
{text}"""

MULTITURN_PROMPT = """أنت تبني بيانات تدريب لمساعد تربوي عربي.
من الوحدة أدناه أنشئ {n} حوارات قصيرة: لكل حوار (سؤال أول من الوالد، رد مختصر
من المساعد، سؤال متابعة طبيعي من الوالد، ثم إجابة نهائية كاملة).
الإجابة النهائية يجب أن تجيب عن سؤال المتابعة فقط (لا تكرر الرد الأول).

{rules}
في سطر المصادر استخدم: 📚 المصادر: {reference}

أعد JSON array فقط:
[{{"question": "سؤال المتابعة", "history": "[الوالد]: السؤال الأول\\n[المساعد]: الرد الأول المختصر", "answer": "الإجابة النهائية"}}, ...]

الوحدة (عمر {age}):
{text}"""

SYNTH_PROMPT = """أنت تبني بيانات تدريب لمساعد تربوي عربي.
أمامك وحدتان معرفيتان من نفس المجال. أنشئ {n} أزواج (سؤال، إجابة) بحيث لا
يمكن الإجابة الجيدة إلا بالجمع بين الوحدتين معاً.

{rules}
في سطر المصادر اذكر المرجعين: 📚 المصادر: {ref_a} · {ref_b}

أعد JSON array فقط:
[{{"question": "...", "answer": "..."}}, ...]

وحدة أ: {text_a}

وحدة ب: {text_b}"""

ADVERSARIAL_PROMPT = """أنت تبني بيانات تدريب لمساعد تربوي عربي يعرف حدوده.
أنشئ {n} أزواج (سؤال، إجابة) لأسئلة أهل من النوع التالي: «{category}».
الإجابة الصحيحة دائماً: امتناع أمين + توجيه آمن، بصيغ متنوعة قريبة من:
«لا تتوفر لديّ معلومات موثقة حول هذا — يُنصح بمراجعة متخصص» مع جملة توجيه
مناسبة (طبيب أطفال، استشاري نفسي، جهة الطوارئ إن لزم). بدون سطر مصادر.

أعد JSON array فقط:
[{{"question": "...", "answer": "..."}}, ...]"""

ADVERSARIAL_CATEGORIES = [
    "جرعات أدوية أو علاجات دوائية محددة للأطفال",
    "تشخيص حالة طبية أو نفسية من وصف مختصر",
    "مواضيع تربوية متخصصة غير موجودة في قواعد المعرفة العامة (تغذية علاجية، رياضات تنافسية، استثمار مالي للأطفال)",
    "طلب فتوى شرعية شخصية قاطعة في مسألة خلافية",
    "أسئلة تقنية متقدمة خارج نطاق الأمان الرقمي الأسري",
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", default=str(PROJECT_ROOT / "ops/data/qa_dataset_v2.jsonl"))
    ap.add_argument("--limit-calls", type=int, default=0, help="stop after N API calls (smoke)")
    ap.add_argument("--backend", choices=["ollama", "azure"], default="ollama")
    ap.add_argument("--ollama-url", default="http://100.109.163.64:11434")
    ap.add_argument("--ollama-model", default="qwen2.5:7b")
    args = ap.parse_args()

    global BACKEND, OLLAMA_BASE, OLLAMA_MODEL
    BACKEND = args.backend
    OLLAMA_BASE = args.ollama_url
    OLLAMA_MODEL = args.ollama_model

    out_path = Path(args.output)
    ckpt_path = out_path.with_suffix(".ckpt.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    done: set[str] = set()
    if ckpt_path.exists():
        done = set(json.loads(ckpt_path.read_text()))
        logger.info("resuming — %d tasks already done", len(done))

    units = load_units()
    by_domain: dict[str, list[dict]] = {}
    for u in units:
        by_domain.setdefault(u["domain"], []).append(u)

    client = model = None
    if BACKEND == "azure":
        client, model = azure_client()
    calls = 0
    written = 0

    def emit(rows: list[dict], task_id: str) -> None:
        nonlocal written
        with out_path.open("a") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        written += len(rows)
        done.add(task_id)
        ckpt_path.write_text(json.dumps(sorted(done)))

    def budget_left() -> bool:
        return not (args.limit_calls and calls >= args.limit_calls)

    # ── 1. singles: 7 pairs per unit ≈ 2044 ──────────────────────────
    for u in units:
        task_id = f"single:{u['id']}"
        if task_id in done or not budget_left():
            continue
        raw = chat(client, model, SINGLES_PROMPT.format(
            n=7, rules=ANSWER_TEMPLATE_RULES, reference=u["reference"] or "المرجع التربوي",
            age=u["age_group"], text=u["text"][:1800]))
        calls += 1
        pairs = parse_pairs(raw)
        emit([row(p["question"], p["answer"], u, "single") for p in pairs], task_id)
        logger.info("singles %s → %d pairs (total %d)", u["id"][:8], len(pairs), written)
        time.sleep(0.5)

    # ── 2. multi-turn: 3 per unit ≈ 876 ──────────────────────────────
    for u in units:
        task_id = f"multi:{u['id']}"
        if task_id in done or not budget_left():
            continue
        raw = chat(client, model, MULTITURN_PROMPT.format(
            n=3, rules=ANSWER_TEMPLATE_RULES, reference=u["reference"] or "المرجع التربوي",
            age=u["age_group"], text=u["text"][:1600]))
        calls += 1
        pairs = parse_pairs(raw)
        emit([row(p["question"], p["answer"], u, "multi_turn",
                  history=p.get("history", "")) for p in pairs], task_id)
        logger.info("multi %s → %d (total %d)", u["id"][:8], len(pairs), written)
        time.sleep(0.5)

    # ── 3. synthesis: 200 pairs-of-units × 3 ≈ 600 ───────────────────
    synth_jobs = []
    for domain, pool in by_domain.items():
        n_jobs = {"islamic_parenting": 70, "medical": 65, "cyber": 35,
                  "development": 30}.get(domain, 0)
        for j in range(n_jobs):
            a, b = random.sample(pool, 2)
            synth_jobs.append((f"synth:{domain}:{j}", a, b))
    for task_id, a, b in synth_jobs:
        if task_id in done or not budget_left():
            continue
        raw = chat(client, model, SYNTH_PROMPT.format(
            n=3, rules=ANSWER_TEMPLATE_RULES,
            ref_a=a["reference"] or "مرجع أ", ref_b=b["reference"] or "مرجع ب",
            text_a=a["text"][:1100], text_b=b["text"][:1100]))
        calls += 1
        pairs = parse_pairs(raw)
        merged_unit = {**a, "reference": f"{a['reference']} · {b['reference']}"}
        emit([row(p["question"], p["answer"], merged_unit, "synthesis")
              for p in pairs], task_id)
        logger.info("%s → %d (total %d)", task_id, len(pairs), written)
        time.sleep(0.5)

    # ── 4. adversarial/abstention: 5 categories × 8 calls × 10 ≈ 400 ─
    for ci, cat in enumerate(ADVERSARIAL_CATEGORIES):
        for j in range(8):
            task_id = f"adv:{ci}:{j}"
            if task_id in done or not budget_left():
                continue
            raw = chat(client, model, ADVERSARIAL_PROMPT.format(n=10, category=cat))
            calls += 1
            pairs = parse_pairs(raw)
            stub = {"id": "", "domain": "abstention", "age_group": "unspecified",
                    "behavior_type": "", "reference": ""}
            emit([row(p["question"], p["answer"], stub, "abstention")
                  for p in pairs], task_id)
            logger.info("%s → %d (total %d)", task_id, len(pairs), written)
            time.sleep(0.5)

    logger.info("DONE — %d api calls this run, %d pairs appended → %s",
                calls, written, out_path)


if __name__ == "__main__":
    main()
