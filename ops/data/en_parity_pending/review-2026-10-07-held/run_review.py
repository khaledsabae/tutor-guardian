"""Thin recorder around the canonical ops/tools/review_en_parity.py `run`.

Same as ../review-2026-10-07/run_review.py (wraps `post` to keep every raw model
response as evidence, then calls the tool's own `main()`), with two operator
settings and no change to the review logic, prompt, gate or stamp:

  * FRESH_CACHE=<path> — read/write the review cache at <path> instead of
    ops/data/en_parity_cache.jsonl, so every verdict in this proof is a new
    model call and none is replayed from an earlier run;
  * any HTTP 429 stops the run (raised as the tool's own UsageCapError, which
    `run` already handles by stopping with a partial report) instead of the
    tool's cool-down-and-retry — the operator asked to stop on 429/quota.

Usage: FRESH_CACHE=/tmp/x.jsonl python3 run_review.py <proof-json> -- <review_en_parity args...>
"""
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "ops" / "tools"))
import review_en_parity as R  # noqa: E402

if os.environ.get("FRESH_CACHE"):
    R.CACHE = Path(os.environ["FRESH_CACHE"])


def _stop_on_429(seconds):  # replaces the cool-down the tool applies on a 429
    R._capped.set()
    raise R.UsageCapError("HTTP 429 — operator policy: stop on the first 429, do not retry")


R._cooldown = _stop_on_429

proof = Path(sys.argv[1])
args = sys.argv[sys.argv.index("--") + 1:]
calls: list[dict] = []
_orig = R.post


def _flush() -> None:
    proof.write_text(json.dumps(calls, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def recorded_post(model, system, user, timeout=None):
    rec = {"n": len(calls) + 1, "model": model, "started": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
           "request_user": user}
    t0 = time.time()
    try:
        content, usage = _orig(model, system, user, timeout)
        rec.update(outcome="ok", seconds=round(time.time() - t0, 1), usage=usage, response=content)
        return content, usage
    except BaseException as e:  # noqa: BLE001 — recorded, then re-raised unchanged
        rec.update(outcome=type(e).__name__, seconds=round(time.time() - t0, 1), error=str(e)[:500])
        raise
    finally:
        calls.append(rec)
        _flush()


R.post = recorded_post
rc = R.main(args)
_flush()
sys.exit(rc)
