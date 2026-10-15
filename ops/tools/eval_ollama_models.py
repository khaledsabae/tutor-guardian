#!/usr/bin/env python3
"""Head-to-head of local Ollama models through the real /assistant/draft pipeline.

Every golden-set question goes through the pipeline once per model, in the
same process, so both models see the same guards, retrieval and prompt
(classification/rewriter calls are answered by one fixed auxiliary model and
memoised, so retrieval cannot drift between the two). Only the answer step —
llm_service.generate_reply / generate_general_pivot — is pointed at the model
under test. Its failover chain points at a model that does not exist, so a
failed answer is recorded as that model's failure (mode retrieval_only), never
quietly answered by another model.

The gateway sends no num_predict to Ollama (production answers on DeepSeek,
capped at 1024 tokens). A model without a working stop token would run until
the deadline, so --num-predict (default 1024, the paid path's cap) is injected
into every call to a model under test, and each answer's done_reason is kept.

Usage (from the repo root, nothing paid in the generation step):
  python ops/tools/eval_ollama_models.py --models tg-tutor:v4 tg-tutor:v6-dpo \
      --label v4_vs_v6dpo [--limit N] [--resume path.jsonl]
Judging/rule checks: ops/tools/eval_ollama_compare.py.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "ops" / "tools"))

HOME_OLLAMA = os.environ.get("EVAL_OLLAMA_URL", "http://100.109.163.64:11434")
NO_FALLBACK = "eval-no-fallback:none"  # 404 on purpose — see the docstring


def _env(aux_model: str, timeout: int) -> None:
    os.environ.update({
        "LLM_PRIMARY_PROVIDER": "ollama",
        "DEEPSEEK_API_KEY": "",
        "DEEPSEEK_FALLBACK_ENABLED": "false",
        "CLOUD_TIER_ENABLED": "false",
        "OLLAMA_BASE_URL": HOME_OLLAMA,
        "OLLAMA_LOCAL_BASE_URL": HOME_OLLAMA,
        "OLLAMA_HOME_SERVER_URL": HOME_OLLAMA,
        "OLLAMA_PRIMARY_MODEL": aux_model,
        "OLLAMA_FALLBACK_MODEL": NO_FALLBACK,
        "OLLAMA_LOCAL_FALLBACK_MODEL": NO_FALLBACK,
        "OLLAMA_LOCAL_FAST_MODEL": NO_FALLBACK,
        "OLLAMA_TIMEOUT": str(timeout),
        "OLLAMA_MAX_RETRIES": "1",
        "LLM_GENERATE_DEADLINE_S": str(timeout + 60),
        "ANSWER_CACHE_ENABLED": "false",
    })
    # Throwaway signing key for this in-process app only (its DB is a temp file).
    import secrets
    os.environ.setdefault("CHILD_MODE_SECRET", secrets.token_hex(32))
    os.environ.pop("OLLAMA_API_KEY", None)
    os.environ.pop("AZURE_OPENAI_API_KEY", None)
    os.environ.pop("AZURE_DEEPSEEK_API_KEY", None)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="+", required=True)
    ap.add_argument("--label", required=True)
    ap.add_argument("--set", default=str(ROOT / "ops/eval/golden_set.jsonl"))
    ap.add_argument("--limit", type=int)
    ap.add_argument("--ids", help="comma-separated golden ids")
    ap.add_argument("--aux-model", default="qwen2.5:3b")
    ap.add_argument("--aux-cache", default=str(ROOT / "ops/eval/runs/.aux_cache.json"))
    ap.add_argument("--num-predict", type=int, default=1024)
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--resume", help="existing output jsonl to append to")
    args = ap.parse_args()

    _env(args.aux_model, args.timeout)
    db = Path(tempfile.gettempdir()) / f"tg_eval_{args.label}_{os.getpid()}.db"
    os.environ["CONVERSATIONS_DB"] = str(db)
    os.environ["ANSWER_CACHE_DB"] = str(db) + ".cache"

    import app.services.ai_gateway as gw
    import app.services.llm_service as llm_service
    from app.core.eval_traffic import EVAL_DEVICE_PREFIX
    import eval_answers

    tested = set(args.models)
    calls: list[dict] = []  # per-answer side channel, reset per (question, model)

    orig_ollama_generate = gw.OllamaProvider.generate

    def ollama_generate(self, prompt, *, options):
        if self.model in tested:
            options = {**(options or {})}
            options.setdefault("num_predict", args.num_predict)
        t0 = time.time()
        data = orig_ollama_generate(self, prompt, options=options)
        if self.model in tested:
            calls.append({
                "model": self.model, "done_reason": data.get("done_reason"),
                "eval_count": data.get("eval_count"),
                "prompt_eval_count": data.get("prompt_eval_count"),
                "wall_s": round(time.time() - t0, 2),
                "tok_s": round(data["eval_count"] / (data["eval_duration"] / 1e9), 2)
                if data.get("eval_count") and data.get("eval_duration") else None,
            })
        return data

    gw.OllamaProvider.generate = ollama_generate

    # Auxiliary calls (classifier, rewriter, fiqh intent…) — memoised so both
    # models get byte-identical classification and therefore retrieval.
    aux_path = Path(args.aux_cache)
    aux = json.loads(aux_path.read_text()) if aux_path.exists() else {}
    orig_generate = gw.AIGateway.generate

    async def memo_generate(self, prompt, *, options=None, max_retries=None,
                            tier="local_fast", route_reason=None):
        if getattr(self, "_eval_model", None):
            return await orig_generate(self, prompt, options=options, max_retries=max_retries,
                                       tier=tier, route_reason=route_reason)
        key = hashlib.sha256(json.dumps([prompt, options, tier], ensure_ascii=False,
                                        sort_keys=True).encode()).hexdigest()
        if key in aux:
            return gw.LLMResult(**aux[key])
        r = await orig_generate(self, prompt, options=options, max_retries=max_retries,
                                tier=tier, route_reason=route_reason)
        aux[key] = {"text": r.text, "model": r.model, "latency_ms": r.latency_ms}
        aux_path.write_text(json.dumps(aux, ensure_ascii=False))
        return r

    gw.AIGateway.generate = memo_generate

    gateways = {}
    for m in args.models:
        g = gw.AIGateway(provider=gw.OllamaProvider(HOME_OLLAMA, m, args.timeout))
        g._eval_model = m
        gateways[m] = g
    current = {"model": None}
    llm_service.get_gateway = lambda: gateways[current["model"]]

    items = [json.loads(l) for l in Path(args.set).open() if l.strip()]
    if args.ids:
        want = set(args.ids.split(","))
        items = [g for g in items if g["id"] in want]
    if args.limit:
        items = items[: args.limit]

    if args.resume:
        out = Path(args.resume)
        done = {(r["id"], r["model"]) for r in map(json.loads, out.open()) if True}
    else:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
        out = ROOT / "ops/eval/runs" / f"{args.label}_{ts}.jsonl"
        done = set()
    out.parent.mkdir(parents=True, exist_ok=True)
    print(f"{len(items)} items × {args.models} → {out}", flush=True)

    from fastapi.testclient import TestClient
    from app.db.init_db import init_db
    from app.main import app

    init_db()
    with TestClient(app) as client, out.open("a") as fh:
        for i, g in enumerate(items, 1):
            # Alternate the order so neither model always runs on a warm cache.
            order = args.models if i % 2 else list(reversed(args.models))
            chunks = None
            for m in order:
                if (g["id"], m) in done:
                    continue
                current["model"] = m
                calls.clear()
                sess = client.post("/api/chat/sessions",
                                   json={"device_id": f"{EVAL_DEVICE_PREFIX}{g['id']}-{m}"})
                sess.raise_for_status()
                headers = {"Authorization": f"Bearer {sess.json()['token']}"}
                payload = {
                    "age_group": g["age_group"], "severity": g["severity"],
                    "message_text": g["question"],
                    "conversation_history": g.get("conversation_history") or [],
                }
                t0 = time.time()
                row = {**g, "model": m}
                try:
                    resp = client.post("/api/assistant/draft", json=payload, headers=headers)
                    row["latency_s"] = round(time.time() - t0, 2)
                    if resp.status_code != 200:
                        raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")
                    body = resp.json()
                    row.update({
                        "reply_text": body.get("reply_text", ""),
                        "mode": body.get("mode"),
                        "answered_domain": body.get("domain"),
                        "needs_human_review": body.get("needs_human_review"),
                    })
                except Exception as exc:  # noqa: BLE001
                    row["error"] = str(exc)
                row["llm_calls"] = list(calls)
                if chunks is None:
                    try:
                        chunks = eval_answers._retrieved_for(g["question"], g["age_group"])
                    except Exception as exc:  # noqa: BLE001
                        chunks = []
                        row["retrieval_error"] = str(exc)
                row["retrieved_chunks"] = chunks
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
                fh.flush()
                last = calls[-1] if calls else {}
                print(f"[{i}/{len(items)}] {g['id']} {m} mode={row.get('mode')} "
                      f"{row.get('latency_s')}s len={len(row.get('reply_text') or '')} "
                      f"done={last.get('done_reason')} toks={last.get('eval_count')} "
                      f"err={row.get('error', '')[:80]}", flush=True)


if __name__ == "__main__":
    main()
