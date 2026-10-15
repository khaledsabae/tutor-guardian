#!/usr/bin/env python3
"""Direct (no pipeline, no retrieval) head-to-head — the July v3/v4/v5 method.

Each question goes to Ollama /api/generate as-is, with the model's own
Modelfile system prompt, the format the fine-tunes were trained on. Rows match
eval_ollama_models.py, so eval_ollama_compare.py judges them unchanged (the
judge sees "no sources"; read groundedness accordingly).

  python ops/tools/eval_ollama_direct.py --models tg-tutor:v4 tg-tutor:v6-dpo \
      --label direct_v4_vs_v6dpo --ids g-001,g-004 [--num-predict 700]
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="+", required=True)
    ap.add_argument("--label", required=True)
    ap.add_argument("--ids", required=True)
    ap.add_argument("--set", default=str(ROOT / "ops/eval/golden_set.jsonl"))
    ap.add_argument("--url", default="http://100.109.163.64:11434")
    ap.add_argument("--num-predict", type=int, default=700)
    args = ap.parse_args()

    rows = {json.loads(l)["id"]: json.loads(l) for l in Path(args.set).open() if l.strip()}
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
    out = ROOT / "ops/eval/runs" / f"{args.label}_{ts}.jsonl"
    with out.open("w") as fh:
        for i, qid in enumerate(args.ids.split(","), 1):
            g = rows[qid]
            order = args.models if i % 2 else list(reversed(args.models))
            for m in order:
                t0 = time.time()
                row = {**g, "model": m, "mode": "llm_generated", "retrieved_chunks": []}
                try:
                    r = requests.post(f"{args.url}/api/generate", timeout=1200, json={
                        "model": m, "prompt": g["question"], "stream": False,
                        "options": {"num_predict": args.num_predict}})
                    r.raise_for_status()
                    d = r.json()
                    row["reply_text"] = d.get("response", "")
                    row["latency_s"] = round(time.time() - t0, 2)
                    row["llm_calls"] = [{
                        "model": m, "done_reason": d.get("done_reason"),
                        "eval_count": d.get("eval_count"),
                        "prompt_eval_count": d.get("prompt_eval_count"),
                        "wall_s": row["latency_s"],
                        "tok_s": round(d["eval_count"] / (d["eval_duration"] / 1e9), 2)
                        if d.get("eval_count") and d.get("eval_duration") else None}]
                except Exception as exc:  # noqa: BLE001
                    row["error"] = str(exc)
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
                fh.flush()
                c = (row.get("llm_calls") or [{}])[0]
                print(f"[{i}] {qid} {m} {row.get('latency_s')}s done={c.get('done_reason')} "
                      f"toks={c.get('eval_count')} err={row.get('error', '')[:80]}", flush=True)
    print(out)


if __name__ == "__main__":
    main()
