"""Judge each (question, retrieved unit) pair for topical relevance.

The judge applies a narrow rubric. A model judging a model's retrieval is only
as good as the spot-check that follows, so every verdict is written out with its
reasoning for manual review.

    python ops/tools/kb_gap_judge.py --in /tmp/retrieval_pairs.json \
        --out /tmp/retrieval_judged.json --max-pairs 400 --concurrency 5

Scale matters here: one call per (question, unit) pair means the default probe
is ~120 calls, but the 1,616 stored production questions would be ~6,500. That
is why --max-pairs is a hard stop rather than advice, and why the weekly loop
samples the tail instead of re-judging everything.

That same scale is why the judge no longer sits on DeepSeek's API by default.
DEEPSEEK_API_KEY is the app's live cloud fallback for real parents mid-chat; a
600-call batch run competes with them for the same key and the same monthly
token cap. --provider ollama moves the batch onto Ollama Cloud (a separate key,
a separate quota) and leaves the user path alone.

The default is --provider auto, which picks ollama only where OLLAMA_API_KEY
exists. That key is on the laptop and NOT in the production container, so the
weekly VPS cron still resolves to deepseek and is unchanged by this. See
ops/scripts/weekly_kb_gap_report.py for what to add to the VPS .env to move it.
"""
import argparse
import collections
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from openai import OpenAI

# Both endpoints speak the OpenAI chat-completions protocol, so only the key and
# the base URL change. The Ollama Cloud URL and OLLAMA_API_KEY are exactly the
# ones ops/tools/check_quoted_texts.py already uses.
PROVIDERS = {
    "ollama": {
        "key_env": "OLLAMA_API_KEY",
        "base_url": "https://ollama.com/v1",
        # Picked by bake-off against the cloud's other Arabic-capable models
        # (2026-08-13; hand-labelled Arabic pairs, 3 repeats each):
        #
        #   * Reliable. 12/12 parseable JSON, and identical grades on all three
        #     repeats. deepseek-v4-flash — the tempting pick, same family as the
        #     outgoing deepseek-chat — managed only 10/12: it intermittently
        #     decides to reason, spends the whole budget in the `reasoning`
        #     field and returns empty `content`. That lands here as grade "?".
        #     Raising max_tokens to 800 fixed it but cost 2.5x the latency.
        #     qwen3.5:397b reasons *every* time and scored 0/12.
        #   * It actually uses the middle grade. On four pairs built to be
        #     partially relevant it answered جزئية/جزئية/جزئية/لا صلة, all
        #     correct; gemma4:31b (the cheap alternative, equally reliable and
        #     equally deterministic) called two of them صلة. This is the whole
        #     ballgame: the weekly report exists to find gaps, so a judge that
        #     rounds "vaguely related" up to "relevant" reports coverage the
        #     knowledge base does not have.
        #   * Fastest of the three anyway — ~1.7s/call, so a 600-pair run at
        #     concurrency 5 is ~3.5 minutes.
        #
        # Also already trusted for Arabic elsewhere in ops/: it is the finder
        # model in check_quoted_texts.py, over religious text, where a mistake
        # is far more expensive than here.
        #
        # Cost note: this is a 675B model judging a ~40-token answer. If the
        # bill ever matters more than the جزئية/صلة boundary, gemma4:31b is the
        # drop-in — `--model gemma4:31b` — with the over-grading above accepted.
        "model": "mistral-large-3:675b",
    },
    "deepseek": {
        "key_env": "DEEPSEEK_API_KEY",
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-chat",
    },
}


class ProviderUnavailable(RuntimeError):
    """The chosen provider has no API key — see resolve_provider."""


def resolve_provider(choice: str) -> tuple[str, str, str, str]:
    """(provider, key, base_url, default_model), or raise.

    Raises rather than degrading. A judge that runs without a key answers "?"
    for every pair, and "?" is not a neutral outcome: the weekly report would
    print a plausible-looking gap table built on nothing at all.
    """
    if choice == "auto":
        choice = "ollama" if os.environ.get("OLLAMA_API_KEY") else "deepseek"
    spec = PROVIDERS[choice]
    key = os.environ.get(spec["key_env"])
    if not key:
        other = "deepseek" if choice == "ollama" else "ollama"
        raise ProviderUnavailable(
            f"{spec['key_env']} غير مضبوط — لا يمكن الحكم عبر «{choice}». "
            f"اضبط المفتاح، أو مرّر --provider {other} إن كان مفتاحه متاحًا."
        )
    base = spec["base_url"]
    if choice == "deepseek":
        base = os.environ.get("DEEPSEEK_BASE_URL", base)
    return choice, key, base, spec["model"]

RUBRIC = """أنت محكّم لجودة استرجاع في تطبيق تربية أطفال.
أمامك سؤال من أب/أم، ونص وحدة معرفية استرجعها النظام كمرجع للإجابة.

قيّم صلة الوحدة بالسؤال بدرجة واحدة فقط:
- "صلة" : الوحدة تعالج نفس الموضوع وتفيد في الإجابة مباشرة.
- "جزئية" : الوحدة في نفس المجال العام لكنها لا تعالج السؤال تحديدًا (مثال: سؤال عن الخجل ووحدة عن التربية العامة).
- "لا صلة" : الوحدة عن موضوع مختلف تمامًا (مثال: سؤال عن الخجل ووحدة عن التغذية).

أجب بـ JSON فقط: {"درجة": "...", "سبب": "جملة قصيرة"}

السؤال: {q}
عمر الطفل: {age}

نص الوحدة:
{text}
"""

_progress_lock = threading.Lock()
_done = 0


def _judge_one(cl, model, row, unit, quiet):
    """One verdict. Never raises: a dead judge degrades to grade '?'."""
    global _done
    prompt = (RUBRIC.replace("{q}", row["question"])
                    .replace("{age}", row.get("age_group") or "unspecified")
                    .replace("{text}", unit["text"]))
    grade, why = "?", ""
    for attempt in range(3):
        try:
            r = cl.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                # Headroom, not a fix for an observed bug: 120 did not truncate
                # on the probe pairs, but Arabic costs more tokens per character
                # than the rubric's English suggests, and a سبب that runs off the
                # end is unparseable JSON — which lands here as grade "?", a
                # judge failure wearing a retrieval finding's clothes. The model
                # stops at the closing brace, so the extra ceiling is unbilled.
                temperature=0, max_tokens=200)
            raw = r.choices[0].message.content or ""
            j = json.loads(raw[raw.find("{"):raw.rfind("}") + 1])
            grade, why = j.get("درجة", "?"), j.get("سبب", "")
            break
        except Exception as exc:  # noqa: BLE001
            if attempt == 2:
                why = f"judge-failed: {type(exc).__name__}"
            else:
                time.sleep(1.5)
    with _progress_lock:
        _done += 1
        if not quiet and _done % 20 == 0:
            print(f"  حُكم {_done} زوج…", flush=True)
    return {
        "question": row["question"], "age": row.get("age_group") or "",
        "domains": row.get("domains") or [], "unit_domain": unit["domain"],
        "reference": unit["reference"], "rerank": unit["rerank"],
        "grade": grade, "why": why, "text": unit["text"][:200],
    }


def summarize(results: list[dict]) -> dict:
    """Grade distribution + per-question cleanliness, as data not print()."""
    total = len(results)
    counts = collections.Counter(r["grade"] for r in results)
    per_q = collections.defaultdict(list)
    for r in results:
        per_q[r["question"]].append(r["grade"])
    # A question is "unserved" when retrieval found nothing that addresses it —
    # this is the signal the weekly report is actually built on.
    unserved = [q for q, gs in per_q.items() if "صلة" not in gs]
    clean = sum(1 for gs in per_q.values() if "لا صلة" not in gs)
    return {
        "pairs": total,
        "questions": len(per_q),
        "counts": dict(counts),
        "clean_questions": clean,
        "unserved_questions": unserved,
    }


def _preflight(cl, model: str) -> None:
    """One live call before spending hundreds.

    Without it a wrong model name or a dead key costs a full run of retries
    before surfacing, and surfaces as 600 pairs graded "?" — which reads like a
    knowledge-base finding and is not one.
    """
    cl.chat.completions.create(
        model=model, messages=[{"role": "user", "content": "رد بكلمة واحدة: تم"}],
        temperature=0, max_tokens=16)


def main(argv: list[str] | None = None):
    ap = argparse.ArgumentParser(
        description="Judge retrieval pairs with an LLM (Ollama Cloud by default).")
    ap.add_argument("--in", dest="inp", default="/tmp/retrieval_pairs.json")
    ap.add_argument("--out", default="/tmp/retrieval_judged.json")
    ap.add_argument("--max-pairs", type=int, default=600,
                    help="hard ceiling on judge calls (cost guard)")
    ap.add_argument("--concurrency", type=int, default=5)
    ap.add_argument("--provider", choices=("auto", "ollama", "deepseek"),
                    default="auto",
                    help="auto = ollama when OLLAMA_API_KEY is set, else deepseek. "
                         "The VPS container has no OLLAMA_API_KEY, so the weekly "
                         "cron stays on deepseek unless that key is added there.")
    ap.add_argument("--model", default=None,
                    help="override the provider's default judge model")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    with open(args.inp, encoding="utf-8") as fh:
        rows = json.load(fh)

    jobs = [(row, u) for row in rows for u in row.get("units", [])]
    if len(jobs) > args.max_pairs:
        # Never silently truncate: a capped run that reads as a full one is how
        # "we covered everything" becomes false.
        print(f"⚠️  {len(jobs)} زوجًا يتجاوز السقف {args.max_pairs} — "
              f"سيُحكم على {args.max_pairs} فقط، والباقي غير مفحوص.")
        jobs = jobs[:args.max_pairs]

    if not jobs:
        print("لا أزواج للحكم.")
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump([], fh, ensure_ascii=False)
        return 0

    try:
        provider, key, base_url, default_model = resolve_provider(args.provider)
    except ProviderUnavailable as exc:
        print(f"🚨 {exc}", file=sys.stderr)
        return 2
    model = args.model or default_model
    cl = OpenAI(api_key=key, base_url=base_url)
    # Printed even under --quiet: the cron log is the only place a week-old run
    # can be checked against which provider actually paid for it.
    print(f"المحكّم: {provider} · {model}", flush=True)
    try:
        _preflight(cl, model)
    except Exception as exc:  # noqa: BLE001
        print(f"🚨 المحكّم «{provider}/{model}» لا يستجيب "
              f"({type(exc).__name__}: {exc}) — أُلغي الحكم قبل صرف أي طلب.",
              file=sys.stderr)
        return 2

    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        results = list(pool.map(
            lambda j: _judge_one(cl, model, j[0], j[1], args.quiet), jobs
        ))

    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(results, fh, ensure_ascii=False, indent=1)

    s = summarize(results)
    print(f"\nالمجموع: {s['pairs']} زوج · {s['questions']} سؤال")
    for g in ("صلة", "جزئية", "لا صلة", "?"):
        if s["counts"].get(g):
            print(f"  {g:8s} {s['counts'][g]:4d}  ({100*s['counts'][g]/s['pairs']:.1f}%)")
    print(f"\nأسئلة بلا أي وحدة خارج الموضوع: {s['clean_questions']}/{s['questions']}")
    print(f"أسئلة لم يخدمها الاسترجاع إطلاقًا: {len(s['unserved_questions'])}/{s['questions']}")

    # "?" is a broken judge, not a verdict. All-"?" is reported as a failure so
    # the weekly report prints «الحكم فشل» instead of a gap table built on air.
    unknown = s["counts"].get("?", 0)
    if unknown == s["pairs"]:
        print(f"\n🚨 كل الأزواج ({s['pairs']}) رجعت بدرجة «؟» — "
              f"المحكّم «{provider}/{model}» فشل، والنتيجة ليست قراءة عن قاعدة "
              f"المعرفة. راجع المفتاح واسم النموذج.", file=sys.stderr)
        return 3
    if unknown > s["pairs"] * 0.1:
        print(f"\n⚠️  {unknown} من {s['pairs']} بلا درجة — "
              f"النسب أعلاه محسوبة على عيّنة منقوصة.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
