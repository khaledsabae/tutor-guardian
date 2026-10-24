#!/usr/bin/env python3
"""«صورة حيّة» — month-end verdict: living pictures (motion) vs still (static).

Run on the VPS once the month is over (read-only):
    docker exec -w /app tg_backend python ops/scripts/story_motion_verdict.py --since 2026-11-20

Prints each arm's numbers, a two-proportion z-test on completion (finished /
opened) and on the 😍 share of ratings, the same completion question with the
device as the unit, and a plain verdict — including "not enough data". Then
set STORY_MOTION_MODE=motion|static in the VPS .env (no release needed).
Eval and E2E devices are left out, like every device count in the weekly
report; reduce-motion devices are left out because they saw no choice.
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_root / "backend"))

from app.core.real_traffic import e2e_devices_sql, real_device_sql  # noqa: E402
from app.services import story_experiment as se  # noqa: E402

import os  # noqa: E402

_DB = Path(os.environ.get("CONVERSATIONS_DB", str(_root / "ops" / "conversations.db")))


def load_rows(since: str, until: str | None) -> list[dict]:
    con = sqlite3.connect(str(_DB))
    con.row_factory = sqlite3.Row
    try:
        tables = {r["name"] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "story_events" not in tables:
            return []
        e2e = {r["device_id"] for r in con.execute(e2e_devices_sql(tables))}
        sql = (f"SELECT * FROM story_events WHERE created_at >= ? AND {real_device_sql('device_id', e2e)}"
               + (" AND created_at < ?" if until else ""))
        return [dict(r) for r in con.execute(sql, (since, until) if until else (since,))]
    finally:
        con.close()


def _pct(x):
    return "—" if x is None else f"{x * 100:.0f}%"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--since", required=True, help="first day of the experiment (YYYY-MM-DD)")
    ap.add_argument("--until", help="day after the last day (default: now)")
    a = ap.parse_args()
    rows = load_rows(a.since, a.until)
    v = se.verdict(rows)
    print(f"«صورة حيّة» {a.since} → {a.until or datetime.now(timezone.utc).date()}  ({len(rows)} events)")
    for arm in se.ARMS:
        s = v[arm]
        r = s["ratings"]
        print(f"  {arm:6}  devices {s['devices']:4}  opens {s['opens']:5}  finished {s['finished']:5}"
              f"  completion {_pct(s['completion'])}  😍 {_pct(s['loved_share'])}"
              f"  (😍{r[3]} 🙂{r[2]} 😐{r[1]})  listen-through {_pct(s['listen_through'])}")
    for key, label in (("completion", "completion (per open)"),
                       ("device_completion", "completion (per device)"),
                       ("loved", "😍 share")):
        t = v[key]
        if t is None:
            print(f"  {label}: not tested")
        else:
            print(f"  {label}: motion {_pct(t.p1)} (n={t.n1}) vs static {_pct(t.p2)} (n={t.n2})"
                  f"  z={t.z:+.2f}  p={t.p_value:.3f}")
    base = v["motion"]["completion"] or v["static"]["completion"]
    n = min(v["motion"]["opens"], v["static"]["opens"])
    mdd = se.min_detectable_difference(base, n) if base is not None else None
    if mdd is not None:
        print(f"  this sample can detect a completion difference of about ±{mdd * 100:.0f} points"
              " (80% power, 5% two-sided; optimistic — opens by one device are not independent)")
    print("VERDICT:", "; ".join(v["reasons"]))
    print("SET:", f"STORY_MOTION_MODE={v['mode']}" if v["mode"] else "keep STORY_MOTION_MODE=ab for now")


if __name__ == "__main__":
    main()
