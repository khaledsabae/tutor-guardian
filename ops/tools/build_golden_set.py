#!/usr/bin/env python3
"""Build the golden evaluation set for answer-quality benchmarking.

Generates realistic parent questions from KB units via Azure DeepSeek
(free tier), mixes in hand-written abstention / multi-turn items, and
writes candidates for human curation.

Composition (~100 items):
  in_kb 60 · cross_unit_synthesis 15 · colloquial_paraphrase 10 ·
  out_of_kb_abstain 10 · multi_turn 5

Usage:
  export AZURE_OPENAI_API_KEY=... AZURE_OPENAI_ENDPOINT=... \
         AZURE_OPENAI_API_VERSION=... AZURE_OPENAI_DEPLOYMENT=...
  python ops/tools/build_golden_set.py            # → ops/eval/golden_candidates.jsonl
  # review/curate, then copy to ops/eval/golden_set.jsonl
"""
from __future__ import annotations

import json
import os
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
UNITS_DIR = ROOT / "knowledge_base" / "units"
OUT = ROOT / "ops" / "eval" / "golden_candidates.jsonl"

random.seed(42)  # reproducible sampling

# Per-domain quotas for generated (in_kb + colloquial + synthesis) items.
DOMAIN_QUOTAS = {
    "islamic_parenting": 26,
    "medical": 26,
    "cyber": 17,
    "development": 16,
}
SEVERITY_CYCLE = ["خفيف", "خفيف", "متوسط", "خفيف", "متوسط", "شديد"]


def _azure_client():
    from openai import AzureOpenAI

    return AzureOpenAI(
        api_key=os.environ["AZURE_OPENAI_API_KEY"],
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-12-01-preview"),
    )


def _chat(client, prompt: str, max_tokens: int = 1800, retries: int = 4) -> str:
    model = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "DeepSeek-V4-Flash")
    for attempt in range(retries):
        try:
            r = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=0.7,
            )
            return r.choices[0].message.content or ""
        except Exception as exc:  # noqa: BLE001 — backoff on 429/5xx alike
            wait = 2**attempt * 3
            print(f"  azure error ({exc.__class__.__name__}), retry in {wait}s", file=sys.stderr)
            time.sleep(wait)
    raise RuntimeError("Azure generation failed after retries")


def _load_units() -> list[dict]:
    units = []
    for p in sorted(UNITS_DIR.glob("*.json")):
        u = json.loads(p.read_text())
        u["_unit_id"] = u.get("id") or p.stem
        if (u.get("text_simplified") or "").strip():
            units.append(u)
    return units


def _extract_json_array(text: str) -> list[dict]:
    start, end = text.find("["), text.rfind("]")
    if start == -1 or end == -1:
        raise ValueError(f"no JSON array in response: {text[:200]}")
    return json.loads(text[start : end + 1])


GEN_PROMPT = """أنت تبني مجموعة اختبار لمساعد تربوي عربي للأهل.
لكل وحدة معرفية أدناه، اكتب سؤالاً واحداً واقعياً كما يكتبه والد/والدة فعلاً في تطبيق (قلق حقيقي، تفاصيل صغيرة، بدون ذكر اسم الوحدة).
{style_rule}

أعد JSON array فقط، عنصر لكل وحدة بنفس الترتيب:
[{{"unit_index": 0, "question": "...", "severity": "خفيف|متوسط|شديد"}}, ...]
اختر الشدة المنطقية للسؤال نفسه.

الوحدات:
{units_block}"""

STYLE_FUSHA = "اكتب بعربية فصحى ميسرة (كما يكتب أب متعلم)."
STYLE_COLLOQUIAL = "اكتب بعامية مصرية أو خليجية حقيقية (زي ما الناس بتكتب في الواتس)، مع أخطاء إملائية خفيفة مقبولة."

SYNTH_PROMPT = """أنت تبني مجموعة اختبار لمساعد تربوي عربي.
لكل زوج وحدتين معرفيتين أدناه (من نفس المجال)، اكتب سؤال والد واحد لا يمكن الإجابة عليه جيداً إلا بالجمع بين الوحدتين معاً.
أعد JSON array فقط:
[{{"pair_index": 0, "question": "...", "severity": "خفيف|متوسط|شديد"}}, ...]

الأزواج:
{pairs_block}"""

# Hand-written: questions whose correct answer is honest abstention
# (topics intentionally absent from the 292-unit KB).
ABSTAIN_ITEMS = [
    ("طفلي عنده حساسية قمح شديدة، إيه أفضل نظام غذائي خالي من الجلوتين لسنه؟", "7-9", "متوسط"),
    ("ابني بيلعب شطرنج منافسات، إزاي أجهزه نفسياً لبطولة دولية؟", "10-12", "خفيف"),
    ("بنتي عايزة تبدأ استثمار مصروفها في الأسهم، إيه أفضل منصة تداول للقاصرين؟", "16-18", "خفيف"),
    ("طفلي مصاب بمرض السكري النوع الأول، كم وحدة أنسولين أعطيه قبل الغداء؟", "4-6", "شديد"),
    ("إزاي أعلم ابني قيادة الدراجة النارية بأمان وهو عنده ١٤ سنة؟", "13-15", "متوسط"),
    ("بنتي موهوبة في الباليه، هل أسجلها في أكاديمية روسية متخصصة؟", "7-9", "خفيف"),
    ("ما حكم زكاة أموال طفلي اليتيم المستثمرة في صناديق المؤشرات؟", "10-12", "متوسط"),
    ("ابني يريد الالتحاق بمعسكر فضاء ناسا، ما إجراءات التقديم؟", "13-15", "خفيف"),
    ("طفلي الرضيع عنده ارتجاع مريئي صامت، إيه الجرعة المناسبة من دواء الحموضة؟", "0-3", "شديد"),
    ("إزاي أظبط إعدادات راوتر MikroTik عشان أحجب مواقع معينة بالـ DNS؟", "13-15", "خفيف"),
]

# Hand-written multi-turn items (history + follow-up question).
MULTI_TURN_ITEMS = [
    {
        "question": "طيب وإذا رفض وعيّط، أجبره ولا أسيبه؟",
        "age_group": "4-6",
        "severity": "خفيف",
        "expected_domains": ["islamic_parenting"],
        "history": [
            {"role": "user", "content": "إزاي أعوّد ابني ٥ سنين على الصلاة؟"},
            {"role": "assistant", "content": "عوّده بالتدريج والقدوة: اصطحبه للمسجد، واجعل الصلاة وقتاً ممتعاً مشتركاً، وامدحه عند المشاركة دون إجبار في هذا السن."},
        ],
    },
    {
        "question": "جربت الحوار اللي قلت عليه ومفيش فايدة، وبقى بيكسر حاجات في البيت. أعمل إيه؟",
        "age_group": "7-9",
        "severity": "متوسط",
        "expected_domains": ["development", "medical"],
        "history": [
            {"role": "user", "content": "ابني ٨ سنين عصبي جداً وبيصرخ على إخواته"},
            {"role": "assistant", "content": "جرّب الحوار الهادئ وقت الهدوء، وحدد قواعد واضحة للتعبير عن الغضب، وعلّمه بدائل مثل التنفس العميق."},
        ],
    },
    {
        "question": "هي قالت إن كل صحابها عندهم تيك توك وإني ظالماها. أرد عليها إزاي؟",
        "age_group": "10-12",
        "severity": "خفيف",
        "expected_domains": ["cyber"],
        "history": [
            {"role": "user", "content": "بنتي ١١ سنة عايزة تنزل تيك توك وأنا رافض"},
            {"role": "assistant", "content": "رفضك مفهوم — السن الأدنى للمنصة ١٣ عاماً. اشرح لها السبب بهدوء واعرض بدائل مناسبة لعمرها مع متابعة مشتركة."},
        ],
    },
    {
        "question": "بدأت أحضنه قبل النوم زي ما اتفقنا، بس لسه بيعمل كوابيس. في حاجة تانية؟",
        "age_group": "4-6",
        "severity": "متوسط",
        "expected_domains": ["medical", "development"],
        "history": [
            {"role": "user", "content": "طفلي ٥ سنين بيصحى بالليل خايف وبيعيط"},
            {"role": "assistant", "content": "الكوابيس شائعة في هذا العمر. ثبّت روتين نوم هادئ، وطمئنه باحتضان قصير، وتجنب الشاشات قبل النوم بساعة."},
        ],
    },
    {
        "question": "طيب هو سألني ليه ربنا خلق الشر؟ مش عارف أجاوبه إزاي بما يناسب سنه",
        "age_group": "7-9",
        "severity": "خفيف",
        "expected_domains": ["islamic_parenting"],
        "history": [
            {"role": "user", "content": "ابني ٩ سنين بدأ يسأل أسئلة كتير عن الدين"},
            {"role": "assistant", "content": "هذه علامة صحية على نمو تفكيره. رحّب بأسئلته دائماً وأجب بصدق وبساطة، ولا تُشعره أن السؤال عيب."},
        ],
    },
]


def main() -> None:
    units = _load_units()
    by_domain: dict[str, list[dict]] = {}
    for u in units:
        by_domain.setdefault(u.get("domain", "unknown"), []).append(u)

    client = _azure_client()
    items: list[dict] = []
    gid = 0

    def add(question, age_group, severity, domains, unit_ids, category, history=None):
        nonlocal gid
        gid += 1
        items.append(
            {
                "id": f"g-{gid:03d}",
                "question": question.strip(),
                "age_group": age_group,
                "severity": severity,
                "expected_domains": domains,
                "expected_unit_ids": unit_ids,
                "category": category,
                "conversation_history": history or [],
            }
        )

    # ── in_kb + colloquial (generated per sampled unit) ────────────────
    for domain, quota in DOMAIN_QUOTAS.items():
        pool = [u for u in by_domain.get(domain, [])]
        sampled = random.sample(pool, min(quota, len(pool)))
        # last ~3 of every domain quota are colloquial paraphrases
        colloquial_count = 3 if domain in ("islamic_parenting", "medical") else 2
        for batch_start in range(0, len(sampled), 10):
            batch = sampled[batch_start : batch_start + 10]
            style = STYLE_COLLOQUIAL if batch_start + 10 >= len(sampled) else STYLE_FUSHA
            units_block = "\n\n".join(
                f"[{i}] (عمر {u.get('age_group')}) {u.get('title') or ''}\n{u['text_simplified'][:400]}"
                for i, u in enumerate(batch)
            )
            print(f"generating {domain} batch {batch_start//10 + 1} ({len(batch)} units, "
                  f"{'colloquial' if style is STYLE_COLLOQUIAL else 'fusha'})…")
            raw = _chat(client, GEN_PROMPT.format(style_rule=style, units_block=units_block))
            for row in _extract_json_array(raw):
                u = batch[row["unit_index"]]
                is_colloquial = style is STYLE_COLLOQUIAL
                age = u.get("age_group") or "unspecified"
                add(
                    row["question"],
                    age if age != "unspecified" else "7-9",
                    row.get("severity", random.choice(SEVERITY_CYCLE)),
                    [domain],
                    [u["_unit_id"]],
                    "colloquial_paraphrase" if is_colloquial else "in_kb",
                )
            time.sleep(1)
        _ = colloquial_count  # composition governed by batch split above

    # ── cross-unit synthesis (15 pairs) ────────────────────────────────
    pairs = []
    for domain, n in (("islamic_parenting", 5), ("medical", 5), ("cyber", 3), ("development", 2)):
        pool = by_domain.get(domain, [])
        for _ in range(n):
            a, b = random.sample(pool, 2)
            pairs.append((domain, a, b))
    pairs_block = "\n\n".join(
        f"[{i}] المجال {d}\nوحدة أ: {a['text_simplified'][:300]}\nوحدة ب: {b['text_simplified'][:300]}"
        for i, (d, a, b) in enumerate(pairs)
    )
    print("generating cross-unit synthesis…")
    raw = _chat(client, SYNTH_PROMPT.format(pairs_block=pairs_block), max_tokens=2500)
    for row in _extract_json_array(raw):
        d, a, b = pairs[row["pair_index"]]
        age = a.get("age_group") if a.get("age_group") != "unspecified" else b.get("age_group")
        add(
            row["question"],
            age if age and age != "unspecified" else "7-9",
            row.get("severity", "متوسط"),
            [d],
            [a["_unit_id"], b["_unit_id"]],
            "cross_unit_synthesis",
        )

    # ── hand-written abstention + multi-turn ───────────────────────────
    for q, age, sev in ABSTAIN_ITEMS:
        add(q, age, sev, [], [], "out_of_kb_abstain")
    for mt in MULTI_TURN_ITEMS:
        add(mt["question"], mt["age_group"], mt["severity"],
            mt["expected_domains"], [], "multi_turn", history=mt["history"])

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")
    print(f"\nwrote {len(items)} candidates → {OUT}")
    from collections import Counter
    print("by category:", dict(Counter(i["category"] for i in items)))
    print("by domain:", dict(Counter(d for i in items for d in (i["expected_domains"] or ["-"]))))


if __name__ == "__main__":
    main()
