#!/usr/bin/env python3
"""
فاحص النصوص الشرعية المقتبسة — بلاغ لا تصحيح
=============================================

الاستخدام:
  python3 ops/tools/check_quoted_texts.py --limit 200
  python3 ops/tools/check_quoted_texts.py            # الكل
  python3 ops/tools/check_quoted_texts.py --out report.json

لماذا وُجدت هذه الأداة
----------------------
أثناء ترجمة مسار واحد (٥ ملفات) ظهر أن
`lesson_4-6_islamic_parenting_bond_03` يقتبس «الكلمة **الطبية** صدقة» بدل
«الكلمة **الطيبة** صدقة» — ياء واحدة ناقصة تحوّل حديثًا متفقًا عليه إلى
عبارة بلا معنى، وظلّ يُعرض على المستخدمين منذ الإطلاق. وُجد بالمصادفة، في
٠٫٣٪ من المنهج. فالسؤال الذي تجيب عنه هذه الأداة: **كم مثله في الباقي؟**

⚠️ **لا تعدّل هذه الأداة أي ملف، ولن تفعل.**
نموذج لغوي لا يملك سلطة تصحيح نص شرعي؛ يملك فقط أن يقول «هذه العبارة تبدو
مخالفة للمحفوظ، فلينظر فيها إنسان». الناتج قائمة مرشّحين للمراجعة البشرية،
ودرجة الثقة فيها ليست إذنًا بالتعديل.

**نموذجان من عائلتين مختلفتين**: الأول يرشّح والثاني يؤكّد، ولا يُبلَّغ عن
عبارة إلا إذا اتفقا. نموذج واحد يرشّح وحده يغرق القائمة بإنذارات كاذبة —
واختلاف الرواية والاختصار المشروع كلاهما يبدو «خطأً» لعينٍ واحدة.
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
API_URL = "https://ollama.com/v1/chat/completions"
FINDER_MODEL = "mistral-large-3:675b"
CONFIRMER_MODEL = "deepseek-v4-pro"
BATCH = 12

# المنهج أولى بالفحص من الوحدات: نصّه يُعرض للوالد **حرفيًا** كما هو، بينما
# الوحدات تمرّ عبر RAG الذي يقدّم `text_simplified` وحده — و`text_original`
# (حيث كل التشويه الآتي من استخراج PDF، ٥٢ وحدة) لا يُضمَّن ولا يُعرض.
SCOPES = {
    "curriculum": ("knowledge_base/curriculum",),
    "units": ("knowledge_base/units",),
    "all": ("knowledge_base/curriculum", "knowledge_base/units"),
}
SCAN_DIRS = SCOPES["curriculum"]
FIELDS = ("title", "summary", "try_this", "description",
          "reflection_prompts", "text_simplified", "text_original")

QUOTED = re.compile(r"['\"«»“”]\s*([؀-ۿ][^'\"«»“”]{10,160})\s*['\"«»“”]")

SYSTEM = """You audit Arabic quotations in an Islamic parenting curriculum for \
textual accuracy. For each numbered quotation decide:

1. Is it a hadith, a Qur'anic verse, or an athar (a saying of a companion or \
early scholar)? Ordinary Arabic prose, a modern author's sentence, a question to \
a parent, or a made-up example is NOT — mark those kind: "not_religious".
2. If it is religious text, is the wording faithful to the established transmitted \
text? Report a problem ONLY for a genuine corruption: a wrong word, a dropped or \
added word that changes meaning, a mangled letter. Do NOT report:
   - a legitimate variant narration (رواية أخرى)
   - a partial quotation that is accurate as far as it goes
   - differences in diacritics or punctuation

Be conservative. This list will be read by a human scholar, and a long list of \
false alarms trains them to skim past the real ones.

Return JSON only:
{"results": [{"n": 1, "kind": "hadith"|"quran"|"athar"|"not_religious", \
"status": "ok"|"suspect", "correct": "the established wording, if suspect", \
"why": "what is wrong, briefly", "confidence": "high"|"medium"|"low"}]}

Include an entry for every number given, in order."""


def _post(model, system, user, timeout=300):
    key = os.environ.get("OLLAMA_API_KEY")
    if not key:
        sys.exit("❌ OLLAMA_API_KEY غير مضبوط")
    body = json.dumps({
        "model": model,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
        "temperature": 0.1,
    }).encode()
    last = None
    for attempt in range(3):
        req = urllib.request.Request(
            API_URL, data=body,
            headers={"Authorization": f"Bearer {key}",
                     "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.load(r)["choices"][0]["message"]["content"]
        except urllib.error.HTTPError as e:
            if e.code in (401, 402, 403):
                raise RuntimeError(f"{model}: HTTP {e.code} — غير متاح") from e
            last = e
            time.sleep(2 ** attempt * 3)
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last = e
            time.sleep(2 ** attempt * 3)
    raise RuntimeError(f"{model}: فشل بعد ٣ محاولات: {last}")


def _parse(text):
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```(?:json)?\s*", "", t)
        t = re.sub(r"\s*```$", "", t)
    s, e = t.find("{"), t.rfind("}")
    return json.loads(t[s:e + 1] if s != -1 and e > s else t)


def harvest(scan_dirs=SCAN_DIRS):
    """كل عبارة عربية مقتبسة، مع كل الملفات التي وردت فيها."""
    seen: dict[str, set] = {}
    for base in scan_dirs:
        for f in (ROOT / base).rglob("*.json"):
            if "/i18n/" in str(f):
                continue
            try:
                d = json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                continue
            if not isinstance(d, dict):
                continue
            blob = json.dumps({k: d[k] for k in FIELDS if d.get(k)},
                              ensure_ascii=False)
            for m in QUOTED.finditer(blob):
                q = " ".join(m.group(1).split())
                if len(q) >= 12:
                    seen.setdefault(q, set()).add(
                        str(f.relative_to(ROOT)))
    return seen


def audit(batch, model):
    listing = "\n".join(f"{i + 1}. {q}" for i, (q, _) in enumerate(batch))
    try:
        return {r["n"]: r for r in _parse(_post(model, SYSTEM, listing))
                .get("results", []) if isinstance(r, dict) and "n" in r}
    except Exception:
        return {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--scope", choices=sorted(SCOPES), default="curriculum")
    ap.add_argument("--out", default="ops/reports/quoted_texts_audit.json")
    args = ap.parse_args()

    seen = harvest(SCOPES[args.scope])
    items = sorted(seen.items())[:args.limit] if args.limit else sorted(seen.items())
    print(f"📖 {len(items)} عبارة مقتبسة فريدة")
    print(f"   مرشِّح : {FINDER_MODEL}")
    print(f"   مؤكِّد : {CONFIRMER_MODEL}\n")

    batches = [items[i:i + BATCH] for i in range(0, len(items), BATCH)]
    t0 = time.time()
    flagged = []

    def run(batch):
        found = audit(batch, FINDER_MODEL)
        sus = [(i, batch[i - 1]) for i, r in found.items()
               if r.get("status") == "suspect"
               and r.get("kind") != "not_religious"
               and 1 <= i <= len(batch)]
        if not sus:
            return []
        # لا يُبلَّغ عن شيء إلا إذا أكّده نموذج من عائلة أخرى.
        sub = [b for _, b in sus]
        conf = audit(sub, CONFIRMER_MODEL)
        out = []
        for j, (q, files) in enumerate(sub, start=1):
            c = conf.get(j, {})
            if c.get("status") == "suspect" and c.get("kind") != "not_religious":
                a = found[sus[j - 1][0]]
                out.append({
                    "quote": q,
                    "files": sorted(files),
                    "kind": c.get("kind"),
                    "finder_why": a.get("why"),
                    "confirmer_why": c.get("why"),
                    "suggested": c.get("correct") or a.get("correct"),
                    "confidence": c.get("confidence", "low"),
                })
        return out

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        for res in ex.map(run, batches):
            flagged.extend(res)

    out_path = ROOT / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps({"checked": len(items), "flagged": flagged},
                   ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("═" * 62)
    print(f"  مفحوص  : {len(items)}")
    print(f"  🚩 مشتبه (اتفق عليه نموذجان): {len(flagged)}")
    print(f"  الزمن   : {time.time() - t0:.0f} ثانية")
    print(f"  التقرير : {args.out}")
    print("═" * 62)

    for f in sorted(flagged, key=lambda x: {"high": 0, "medium": 1}.get(
            x["confidence"], 2)):
        icon = {"high": "🔴", "medium": "🟡"}.get(f["confidence"], "⚪")
        print(f"\n{icon} [{f['kind']}] «{f['quote'][:70]}»")
        print(f"   المقترح : {f.get('suggested') or '—'}")
        print(f"   السبب   : {f.get('confirmer_why')}")
        for p in f["files"][:3]:
            print(f"   📄 {p}")

    if flagged:
        print("\n⚠️  هذه قائمة مرشّحين لمراجعة بشرية متخصصة، لا قائمة تصحيحات. "
              "لم يُعدَّل أي ملف.")


if __name__ == "__main__":
    main()
