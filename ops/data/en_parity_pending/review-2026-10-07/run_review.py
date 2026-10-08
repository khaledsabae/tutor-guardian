"""Thin recorder around the canonical ops/tools/review_en_parity.py `run`.

It changes no logic: it wraps `post` to keep every raw model response (model,
time, usage, outcome) as evidence, then calls the tool's own `main()`.
Usage: python3 run_review.py <proof-json> -- <review_en_parity args...>
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "ops" / "tools"))
import review_en_parity as R  # noqa: E402

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
