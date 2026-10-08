"""Put the primary-text evidence for one held finding to both reviewer families.

Uses the canonical tool's own transport (`review_en_parity.post`: Ollama Cloud,
existing key) with the same models as the gate. The agent's conclusion in the
evidence file is NOT sent — each model gets the finding and the source texts and
judges on its own. Raw requests and responses are kept as proof.

Usage: python3 evidence_consult.py <evidence.json> <proof.json>
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "ops" / "tools"))
import review_en_parity as R  # noqa: E402

R.REQUEST_TIMEOUT, R.REQUEST_ATTEMPTS = 120, 4
R.set_concurrency(1)


def _stop_on_429(seconds):
    R._capped.set()
    raise R.UsageCapError("HTTP 429 — operator policy: stop on the first 429")


R._cooldown = _stop_on_429

SYSTEM = """You verify a quoted hadith against primary text for an Islamic parenting app \
that quotes hadith only from Sahih al-Bukhari and Sahih Muslim, verbatim, with book and number. \
An earlier reviewer raised a finding on the Arabic field below. You get the field (Arabic and \
English), the finding, and the full text of the cited narration and of a parallel narration. \
Judge only from the texts given. Return JSON only:
{"quote_verbatim_in_cited_hadith": true|false, "cited_hadith_wording": "<the clause as it stands \
in the cited hadith>", "parallel_wording": "<the clause in the parallel narration>", \
"finding_correct": true|false, "english_faithful": true|false, \
"remaining_defects": [{"side": "arabic"|"english", "severity": "high"|"medium"|"low", "why": "..."}], \
"why": "<two sentences>"}"""

ev = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
out = Path(sys.argv[2])
payload = {k: ev[k] for k in ("field", "arabic", "english", "finding_under_review")}
payload["sources"] = [{k: v for k, v in s.items()} for s in ev["sources"]
                      if s["id"] in ("bukhari_2989_fawazahmed0", "muslim_1009_fawazahmed0",
                                     "bukhari_independent_dataset")]
user = json.dumps(payload, ensure_ascii=False, indent=1)
calls = []
for model in (R.REVIEWER_A, R.REVIEWER_B):
    rec = {"model": model, "started": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "system": SYSTEM,
           "request_user": user}
    t0 = time.time()
    try:
        content, usage = R.post(model, SYSTEM, user)
        rec.update(outcome="ok", seconds=round(time.time() - t0, 1), usage=usage, response=content,
                   parsed=R.parse_json(content))
    except BaseException as e:  # noqa: BLE001
        rec.update(outcome=type(e).__name__, seconds=round(time.time() - t0, 1), error=str(e)[:500])
        calls.append(rec)
        out.write_text(json.dumps(calls, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        raise
    calls.append(rec)
    out.write_text(json.dumps(calls, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
for c in calls:
    p = c.get("parsed") or {}
    print(c["model"], c["outcome"], c["seconds"], "s ·",
          {k: p.get(k) for k in ("quote_verbatim_in_cited_hadith", "finding_correct",
                                 "english_faithful", "remaining_defects")})
