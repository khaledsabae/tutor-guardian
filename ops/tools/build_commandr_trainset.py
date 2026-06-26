#!/usr/bin/env python3
"""Format the premium QA corpus into chat-messages JSONL for fine-tuning.

Model-agnostic: emits {"messages":[system,user,assistant]} so the training
notebook's tokenizer.apply_chat_template() renders the correct special tokens
for whatever base (command-r7b-arabic chosen 2026-06-26). Shuffles + splits
train/val. Input: ops/data/qa_dataset_final.jsonl (31,645, clean/verified).
"""
from __future__ import annotations
import json, random
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "qa_dataset_final.jsonl"
OUT_TRAIN = ROOT / "data" / "tg_train_commandr.jsonl"
OUT_VAL = ROOT / "data" / "tg_val_commandr.jsonl"
VAL_FRAC = 0.02
SEED = 42

SYSTEM = (
    "أنت «المربّي»، مساعد تربوي عربي للأهل متخصص في التربية الإسلامية ونمو الطفل "
    "وصحته وأمانه الرقمي. أجب بالعربية الفصحى بوضوح وتعاطف، وقدّم خطوات عملية قابلة "
    "للتنفيذ مستندة إلى مصادر موثوقة. لا تعطِ تشخيصاً طبياً ملزماً ولا جرعات أدوية ولا "
    "فتوى شخصية قاطعة، وأحِل إلى المتخصص عند الحاجة."
)


def main():
    rows = [json.loads(l) for l in SRC.read_text(encoding="utf-8").splitlines() if l.strip()]
    recs = []
    skipped = 0
    for r in rows:
        instr = (r.get("instruction") or "").strip()
        out = (r.get("output") or "").strip()
        if not instr or not out:
            skipped += 1
            continue
        recs.append({
            "messages": [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": instr},
                {"role": "assistant", "content": out},
            ],
            "domain": r.get("domain", ""),
            "kind": r.get("kind", ""),
        })

    random.Random(SEED).shuffle(recs)
    n_val = int(len(recs) * VAL_FRAC)
    val, train = recs[:n_val], recs[n_val:]

    def dump(path, items):
        with path.open("w", encoding="utf-8") as f:
            for it in items:
                # keep only messages in the training file (drop meta cols)
                f.write(json.dumps({"messages": it["messages"]}, ensure_ascii=False) + "\n")

    dump(OUT_TRAIN, train)
    dump(OUT_VAL, val)

    print(f"source records      : {len(rows)}")
    print(f"skipped (empty)     : {skipped}")
    print(f"train               : {len(train)}  → {OUT_TRAIN.name}")
    print(f"val                 : {len(val)}  → {OUT_VAL.name}")
    print(f"by domain           : " + " | ".join(f"{k} {v}" for k, v in Counter(r['domain'] for r in recs).most_common()))
    print(f"by kind             : " + " | ".join(f"{k or '(blank)'} {v}" for k, v in Counter(r['kind'] for r in recs).most_common()))
    # length sanity (chars)
    out_lens = [len(r["messages"][2]["content"]) for r in recs]
    out_lens.sort()
    print(f"assistant len chars : min {out_lens[0]} | median {out_lens[len(out_lens)//2]} | max {out_lens[-1]}")


if __name__ == "__main__":
    main()
