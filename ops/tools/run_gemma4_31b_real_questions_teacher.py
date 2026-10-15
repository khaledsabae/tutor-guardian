#!/usr/bin/env python3
"""run_gemma4_31b_real_questions_teacher.py — Runs `gemma4:31b` on Ollama Cloud
(pure HTTP API, zero local models) over real parent questions to:

  1. Answer all unanswered real parent questions (`unanswered=True`) and complex
     colloquial parent questions with Gold-Standard Grounded Answers.
  2. Score (question, candidate_unit) relevance (`1.0`, `0.5`, `0.0`) to produce
     Teacher-labeled Cross-Encoder Reranker training pairs.
  3. Discover and rank true Knowledge Base gaps (`has_kb_gap=True`) with
     suggested new unit titles and domains.
  4. Build SFT (`distilled_real_parents_sft.jsonl`) and DPO
     (`distilled_real_parents_dpo.jsonl`) datasets, merge them into
     `tg_train_ultra_v6.jsonl`, and repackage `tg_colab_ultra_bundle.zip`.
"""
from __future__ import annotations

import argparse
import collections
import concurrent.futures
import json
import os
import random
import re
import sys
import threading
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

OUT_DIR = PROJECT_ROOT / "ops" / "data" / "kaggle_upload_ultra"
QUESTIONS_PATH = OUT_DIR / "real_parent_questions.jsonl"
CHECKPOINT_PATH = OUT_DIR / "teacher_gemma4_31b.ckpt.jsonl"

SYSTEM_PROMPT_V6 = (
    "أنت «المربّي»، مساعد تربوي عربي للأهل متخصص في التربية الإسلامية ونمو الطفل "
    "وصحته وأمانه الرقمي. أجب بالعربية الفصحى بوضوح وتعاطف، وقدّم خطوات عملية قابلة "
    "للتنفيذ مستندة إلى مصادر موثوقة. لا تعطِ تشخيصاً طبياً ملزماً ولا جرعات أدوية ولا "
    "فتوى شخصية قاطعة، وأحِل إلى المتخصص عند الحاجة."
)

TEACHER_PROMPT = """أنت «المربّي»، كبير الخبراء التربويين والأطباء والشرعيين في تطبيق تربية الأطفال.
أمامك سؤال حقيقي طرحه أب أو أم، وأقرب الوحدات المسترجعة من قاعدة المعرفة الحالية.

[سؤال الوالد/الوالدة]
{question}
(الفئة العمرية للطفل: {age_group} | اللغة: {lang})

[الوحدات المرشحة من قاعدة المعرفة]
{units_text}

المطلوب منك إخراج كائن JSON صالح فقط (بدون أي شرح خارجه) يطابق هذا الهيكل:
{{
  "is_valid_parenting_query": true,
  "primary_domain": "development | medical | islamic_parenting | cyber | aqeedah | app_help",
  "unit_relevance": [1.0, 0.5, 0.0, 0.0],
  "has_kb_gap": true,
  "suggested_new_unit_topic": "عنوان موجز للوحدة المعرفية المطلوب إضافتها لسد الفجوة (أو فارغ إذا كانت الوحدات كافية)",
  "gold_answer": "إجابة تربوية نموذجية كاملة (بالعربية الفصحى الميسرة إذا كان السؤال بالعربية، أو بالإنجليزية إذا كان بالإنجليزية): تبدأ بجملة تعاطف وجواب مباشر عملي، ثم 3 إلى 4 خطوات عملية مرقمة (1. 2. 3.) قابلة للتنفيذ اليوم، ولا تحيل لمتخصص إلا عند وجود خطر طبي أو نفسي حقيقي أو فتوى شرعية معقدة، وتختم بسطر أخير: 📚 المصادر: <اذكر المرجع من الوحدات المرشحة إن كانت ذات صلة، أو اكتب: الإرشادات التربوية المعتمدة — AAP / منظمة الصحة العالمية / منهج المربّي>"
}}"""


def resolve_ollama_api_key() -> str:
    key = os.environ.get("OLLAMA_API_KEY", "").strip()
    if key:
        return key
    for rc in (Path.home() / ".bashrc", Path.home() / ".profile", PROJECT_ROOT / ".env"):
        if rc.exists():
            m = re.search(r"OLLAMA_API_KEY=[\"\x27]?([^\s\"\x27#]+)", rc.read_text(errors="ignore"))
            if m:
                return m.group(1).strip()
    raise RuntimeError("OLLAMA_API_KEY not found in environment or ~/.bashrc")


def call_gemma4_31b(api_key: str, prompt: str, model: str = "gemma4:31b", retries: int = 4) -> dict | None:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "max_tokens": 900,
    }
    data_bytes = json.dumps(payload).encode("utf-8")
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                "https://ollama.com/v1/chat/completions",
                data=data_bytes,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "User-Agent": "TutorGuardian-TeacherDistill/1.0",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                content = (body.get("choices") or [{}])[0].get("message", {}).get("content", "")
                s, e = content.find("{"), content.rfind("}") + 1
                if s >= 0 and e > s:
                    return json.loads(content[s:e])
        except Exception as exc:
            wait = min(2 ** attempt * 1.5, 15)
            if attempt == retries - 1:
                return None
            time.sleep(wait)
    return None


_NOISE_OR_SYNTH_PATTERNS = re.compile(
    r"(رواية ورش|رواية حفص|في هذا التطبيق|هذا التطبيق يقرأ|بتعرف ميتا|"
    r"الرد السابق|بلغة مناسبة لسنه|أعطني مثالاً عمليًا|اعطني مثالا عمليا|"
    r"اريد بأن أقرأها|قول لي اعمل ايه|ممكن تلخص لي|"
    r"عاوز اعمل بيتزا|طريقة عمل بيتزا|"
    r"حالة حماية طبية طارئة وحرجة|رقم ملف محذوف|"
    r"فضول قوي جدا لتجربة علاقة شاذة|فضول قوي تجربة علاقة شاذة|"
    r"ماما تدخلني الله|كيف يا أستاذة علم اهلنا|كيف أبدأ بأول طفل|"
    r"والبرنامج مقدم للطفل حتى وهو في بطن)",
    re.I,
)


def is_clean_standalone_parent_question(question: str, domain: str = "") -> bool:
    q = (question or "").strip()
    if len(q) < 16:
        return False
    if domain == "app_help":
        return False
    if _NOISE_OR_SYNTH_PATTERNS.search(q):
        return False
    return True


def clean_gold_answer(text: str) -> str:
    t = re.sub(r"\s*\[[1-9]\]", "", (text or "").strip())
    return re.sub(r"[ \t]{2,}", " ", t).strip()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--max-questions", type=int, default=400)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--model", default="gemma4:31b")
    args = ap.parse_args()

    api_key = resolve_ollama_api_key()
    from app.services.bm25_index import get_bm25
    bm25 = get_bm25()

    all_turns = [
        json.loads(line)
        for line in QUESTIONS_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    # Deduplicate by question_hash, keeping unanswered or negative-feedback turns first
    by_hash: dict[str, dict] = {}
    for t in all_turns:
        if t["category"] not in ("organic_parent_question", "daily_tip_card"):
            continue
        if not is_clean_standalone_parent_question(t.get("question", "")):
            continue
        qh = t["question_hash"]
        if qh not in by_hash:
            by_hash[qh] = t
        else:
            if t["unanswered"]:
                by_hash[qh]["had_unanswered"] = True
            if not by_hash[qh].get("assistant_reply") and t.get("assistant_reply"):
                by_hash[qh]["assistant_reply"] = t["assistant_reply"]
            if t.get("feedback_rating"):
                by_hash[qh]["feedback_rating"] = t["feedback_rating"]

    for t in by_hash.values():
        if t["unanswered"]:
            t["had_unanswered"] = True

    candidates = list(by_hash.values())

    def priority_key(t: dict) -> tuple:
        is_org = 0 if t["category"] == "organic_parent_question" else 1
        is_neg = 0 if t.get("feedback_rating") in ("down", "negative", "👎", "-1") else 1
        is_unans = 0 if t.get("had_unanswered") else 1
        is_miss = 0 if not t.get("fast_path") else 1
        return (is_neg, is_org, is_unans, is_miss, -len(t.get("question") or ""))

    candidates.sort(key=priority_key)
    selected = candidates[: args.max_questions]

    # Load existing checkpoint
    done_map: dict[str, dict] = {}
    if CHECKPOINT_PATH.exists():
        for line in CHECKPOINT_PATH.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    row = json.loads(line)
                    done_map[row["question_hash"]] = row
                except Exception:
                    pass

    todo = [t for t in selected if t["question_hash"] not in done_map]
    print(f"🎯 Selected {len(selected)} clean priority real parent questions ({len(done_map)} in checkpoint, {len(todo)} new to run via {args.model})...")

    ckpt_lock = threading.Lock()
    t0 = time.time()
    completed_now = 0

    def process_one(item: dict) -> dict | None:
        nonlocal completed_now
        q_text = item["question"]
        hits = bm25.search(q_text, domain=None, top_k=4)
        units_compact = []
        for h in hits:
            meta = h.get("metadata") or {}
            units_compact.append({
                "unit_id": h.get("unit_id") or meta.get("unit_id") or "",
                "title": meta.get("behavior_type") or meta.get("title") or "",
                "domain": meta.get("domain") or "",
                "age_group": meta.get("age_group") or "",
                "reference": meta.get("reference_info") or "",
                "bm25_score": round(float(h.get("bm25_score", 0.0)), 3),
                "text": (h.get("document") or "").removeprefix("passage: ")[:550],
            })
        units_text = "\n\n".join(
            f"[{i+1}] ({u['title']} | المجال: {u['domain']} | العمر: {u['age_group']} | المرجع: {u['reference']}):\n{u['text']}"
            for i, u in enumerate(units_compact)
        ) or "(لم يتم العثور على وحدات مطابقة لفظياً)"

        prompt = TEACHER_PROMPT.format(
            question=q_text,
            age_group=item["age_group"],
            lang=item["lang"],
            units_text=units_text,
        )
        parsed = call_gemma4_31b(api_key, prompt, model=args.model)
        if not parsed or not isinstance(parsed, dict):
            return None

        record = {
            "question_hash": item["question_hash"],
            "question": q_text,
            "age_group": item["age_group"],
            "lang": item["lang"],
            "category": item["category"],
            "had_unanswered": bool(item.get("had_unanswered")),
            "old_assistant_reply": item.get("assistant_reply") or "",
            "feedback_rating": item.get("feedback_rating") or "",
            "candidate_units": units_compact,
            "teacher": parsed,
        }
        with ckpt_lock:
            with CHECKPOINT_PATH.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")
            done_map[item["question_hash"]] = record
            completed_now += 1
            if completed_now % 20 == 0 or completed_now == len(todo):
                elapsed = time.time() - t0
                rate = completed_now / max(elapsed, 0.001)
                print(f"   [{completed_now}/{len(todo)}] ({rate:.2f} q/s, elapsed {elapsed:.1f}s)")
        return record

    if todo:
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
            list(pool.map(process_one, todo))

    # Aggregate all checkpointed teacher results with strict hygiene filtering
    all_judged = list(done_map.values())
    distilled_sft = []
    distilled_dpo = []
    reranker_pairs = []
    kb_gaps = []
    filtered_out_count = 0

    for r in all_judged:
        t_out = r.get("teacher") or {}
        domain = (t_out.get("primary_domain") or "development").strip()
        if not t_out.get("is_valid_parenting_query", True):
            filtered_out_count += 1
            continue
        if not is_clean_standalone_parent_question(r.get("question", ""), domain=domain):
            filtered_out_count += 1
            continue

        gold = clean_gold_answer(t_out.get("gold_answer") or "")
        if "رواية ورش" in gold or "إعدادات التطبيق" in gold or "قسم الإعدادات" in gold:
            filtered_out_count += 1
            continue

        rels = t_out.get("unit_relevance") or []
        units = r.get("candidate_units") or []

        if isinstance(rels, list):
            for u, rel_val in zip(units, rels):
                try:
                    score_f = float(rel_val)
                except (TypeError, ValueError):
                    score_f = 0.0
                reranker_pairs.append({
                    "question": r["question"],
                    "age_group": r["age_group"],
                    "unit_id": u["unit_id"],
                    "unit_title": u["title"],
                    "passage": u["text"],
                    "label": max(0.0, min(1.0, score_f)),
                })

        if t_out.get("has_kb_gap") and t_out.get("suggested_new_unit_topic"):
            kb_gaps.append({
                "question": r["question"],
                "age_group": r["age_group"],
                "domain": domain,
                "suggested_topic": t_out.get("suggested_new_unit_topic"),
                "had_unanswered": r.get("had_unanswered", False),
            })

        if len(gold) >= 80:
            distilled_sft.append({
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT_V6},
                    {"role": "user", "content": r["question"]},
                    {"role": "assistant", "content": gold},
                ],
                "question_hash": r["question_hash"],
                "domain": domain,
            })
            old_reply = (r.get("old_assistant_reply") or "").strip()
            if old_reply and old_reply != gold:
                distilled_dpo.append({
                    "prompt": r["question"],
                    "chosen": gold,
                    "rejected": old_reply,
                    "age_group": r["age_group"],
                })

    # Also add gold SFT examples from the 12 newly authored gap KB units
    gap_units_dir = OUT_DIR / "new_kb_gap_units"
    if gap_units_dir.exists():
        for gfile in sorted(gap_units_dir.glob("*.json")):
            gdata = json.loads(gfile.read_text(encoding="utf-8"))
            q_prompt = f"طفلي في الفئة العمرية ({gdata['age_group']}) وأحتاج إرشاداً عملياً حول: {gdata['title']}"
            a_gold = f"{gdata['text_simplified']}\n\n📚 المصادر: {gdata['reference_info']}"
            distilled_sft.append({
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT_V6},
                    {"role": "user", "content": q_prompt},
                    {"role": "assistant", "content": a_gold},
                ],
                "question_hash": gdata["id"],
                "domain": gdata["domain"],
            })

    # Write distilled files
    sft_path = OUT_DIR / "distilled_real_parents_sft.jsonl"
    dpo_path = OUT_DIR / "distilled_real_parents_dpo.jsonl"
    rerank_path = OUT_DIR / "reranker_teacher_pairs.jsonl"
    gaps_json_path = OUT_DIR / "real_kb_gaps_discovered.json"
    gaps_md_path = OUT_DIR / "real_kb_gaps_report.md"

    with sft_path.open("w", encoding="utf-8") as fh:
        for item in distilled_sft:
            fh.write(json.dumps({"messages": item["messages"]}, ensure_ascii=False) + "\n")

    with dpo_path.open("w", encoding="utf-8") as fh:
        for item in distilled_dpo:
            fh.write(json.dumps(item, ensure_ascii=False) + "\n")

    with rerank_path.open("w", encoding="utf-8") as fh:
        for item in reranker_pairs:
            fh.write(json.dumps(item, ensure_ascii=False) + "\n")

    gaps_json_path.write_text(json.dumps(kb_gaps, ensure_ascii=False, indent=2), encoding="utf-8")

    # Build KB Gaps Markdown Report
    gap_by_domain = collections.Counter(g["domain"] for g in kb_gaps)
    gap_by_age = collections.Counter(g["age_group"] for g in kb_gaps)
    md_lines = [
        "# تقرير الفجوات المعرفية والإجابات الذهبية المحكّمة بواسطة `Gemma 4 31B`",
        "",
        f"- **النموذج المحكّم والمُقطّر (Teacher):** `gemma4:31b`",
        f"- **إجمالي أسئلة الآباء والأمهات الحقيقية التي تم تحكيمها:** `{len(all_judged)}` (تم استبعاد `{filtered_out_count}` رسائل غير مكتملة السياق أو خاصة بإعدادات واجهة التطبيق)",
        f"- **أزواج التدريب الذهبية المولّدة والمنقّاة (`distilled_real_parents_sft.jsonl`):** `{len(distilled_sft)}`",
        f"- **أزواج التفضيل المباشر (`distilled_real_parents_dpo.jsonl`):** `{len(distilled_dpo)}`",
        f"- **أزواج تدريب الـ Reranker المحكّمة (`reranker_teacher_pairs.jsonl`):** `{len(reranker_pairs)}`",
        f"- **الفجوات المعرفية الحقيقية المكتشفة (`has_kb_gap=true`):** `{len(kb_gaps)}`",
        "",
        "## 1. توزيع الفجوات المعرفية المكتشفة حسب المجال والفئة العمرية",
        "",
        "- **حسب المجال:** " + " · ".join(f"`{k}`: {v}" for k, v in gap_by_domain.most_common()),
        "- **حسب العمر:** " + " · ".join(f"`{k}`: {v}" for k, v in gap_by_age.most_common()),
        "",
        "## 2. أهم المواضيع الجديدة المقترحة لإضافتها كوحدات معرفية (من أسئلة الأهالي الفعلية)",
        "",
        "| # | المجال | العمر | عنوان الوحدة المقترحة | سؤال الأب/الأم الحقيقي (بعد التعمية) |",
        "|---:|---|---|---|---|",
    ]
    for idx, g in enumerate(kb_gaps[:40], 1):
        q_short = g["question"].replace("\n", " ")[:85]
        topic = (g["suggested_topic"] or "").replace("|", "/")[:65]
        md_lines.append(f"| {idx} | `{g['domain']}` | `{g['age_group']}` | **{topic}** | {q_short} |")

    gaps_md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    # Idempotently merge distilled gold answers (weighted 3x) onto tg_train_base_v6.jsonl -> tg_train_ultra_v6.jsonl
    train_base_path = OUT_DIR / "tg_train_base_v6.jsonl"
    train_out = OUT_DIR / "tg_train_ultra_v6.jsonl"
    source_train_path = train_base_path if train_base_path.exists() else train_out
    base_train = [
        json.loads(line)
        for line in source_train_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    for item in distilled_sft:
        for _ in range(3):
            base_train.append({"messages": item["messages"]})
    random.Random(42).shuffle(base_train)
    with train_out.open("w", encoding="utf-8") as fh:
        for r in base_train:
            fh.write(json.dumps({"messages": r["messages"]}, ensure_ascii=False) + "\n")

    # Repackage tg_colab_ultra_bundle.zip with all new distilled artifacts
    zip_path = OUT_DIR / "tg_colab_ultra_bundle.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for fn in (
            "real_parent_questions.jsonl",
            "kb_units_full.jsonl",
            "tg_train_ultra_v6.jsonl",
            "tg_val_ultra_v6.jsonl",
            "distilled_real_parents_sft.jsonl",
            "distilled_real_parents_dpo.jsonl",
            "reranker_teacher_pairs.jsonl",
            "real_kb_gaps_discovered.json",
            "real_kb_gaps_report.md",
            "real_questions_diagnostic_report.md",
        ):
            p = OUT_DIR / fn
            if p.exists():
                zf.write(p, arcname=fn)

    print(f"✅ Complete! Clean SFT: {len(distilled_sft)} (filtered {filtered_out_count} noisy) | DPO: {len(distilled_dpo)} | Reranker pairs: {len(reranker_pairs)} | KB Gaps: {len(kb_gaps)}")
    print(f"📦 Updated bundle: {zip_path} ({zip_path.stat().st_size / (1024*1024):.2f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
