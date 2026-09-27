#!/usr/bin/env python3
"""Nudge devices on an old build to update — a push, not a forced update.

Only devices that need it: those whose last launch reported a build below
--below (or no build at all, which means a build from before the census,
~1.0.56) and that were seen in the last --active-days. The old version sent
to every token ever registered, so people already on the new build were told
to update, and an install abandoned months ago got the same message.

Nothing is sent without --send. The default run prints who would receive it,
per build, so the audience can be checked against `min_build.sh census`.
--limit sends to the most recently active N first: a small batch, a look at
Android vitals and Crashlytics, then the rest. The push only brings people to
an update Play already serves — send it after the target build has been clean
in vitals for a few days (docs/OPS_RUNBOOK.md §10.1), not on release day.

A tap opens the app (builds before the target have no store deep link), so
the text itself has to say "update from Google Play".

Usage (on the VPS, inside the backend container or with the backend env):
  python3 ops/scripts/send_update_push.py --below 111 \\
      --title "..." --body "..."                     # dry run: audience only
  python3 ops/scripts/send_update_push.py --below 111 \\
      --title "..." --body "..." --send --limit 100  # first batch
"""

import argparse
import sys
from pathlib import Path

# Ensure the backend package is importable.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.core.log_safety import device_tag  # noqa: E402
from app.db.init_db import get_conn  # noqa: E402
from app.services import push_sender  # noqa: E402

PUSH_TYPE = "app_update"


def target_devices(below: int, active_days: int, limit: int | None = None):
    """(device_id, build_number) for devices below `below`, most recent first."""
    conn = get_conn()
    try:
        sql = (
            "SELECT device_id, build_number FROM push_tokens "
            "WHERE (build_number IS NULL OR build_number < ?) "
            "AND updated_at >= datetime('now', ?) "
            "ORDER BY updated_at DESC"
        )
        params: list = [below, f"-{active_days} days"]
        if limit:
            sql += " LIMIT ?"
            params.append(limit)
        return [(r[0], r[1]) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def summarize(rows) -> str:
    counts: dict = {}
    for _, build in rows:
        counts[build] = counts.get(build, 0) + 1
    ordered = sorted(counts.items(), key=lambda kv: (kv[0] is None, -(kv[0] or 0)))
    return ", ".join(f"{'unknown' if b is None else b}×{n}" for b, n in ordered) or "none"


def send(rows, title: str, body: str) -> dict:
    tally = {"sent": 0, "no_token": 0, "unregistered": 0, "failed": 0}
    for device_id, _ in rows:
        result = push_sender.send_to_device(
            device_id, title=title, body=body, data={"type": PUSH_TYPE},
        )
        if result.get("sent"):
            tally["sent"] += 1
        elif result.get("ok"):
            reason = result.get("reason", "no_token")
            tally[reason if reason in tally else "no_token"] += 1
        else:
            tally["failed"] += 1
            print(f"  failed {device_tag(device_id)}: {result.get('error', 'unknown')}")
    return tally


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--below", type=int, required=True,
                        help="target builds below this (the build Play now serves)")
    parser.add_argument("--title", required=True)
    parser.add_argument("--body", required=True)
    parser.add_argument("--active-days", type=int, default=30)
    parser.add_argument("--limit", type=int, default=None,
                        help="send to the most recently active N only")
    parser.add_argument("--send", action="store_true",
                        help="actually send; without it this is a dry run")
    args = parser.parse_args(argv)

    rows = target_devices(args.below, args.active_days, args.limit)
    print(f"audience: {len(rows)} device(s) below {args.below}, active in the last "
          f"{args.active_days} days" + (f", limited to {args.limit}" if args.limit else ""))
    print(f"  by build: {summarize(rows)}")
    if not args.send:
        print("dry run — nothing sent. Add --send to send.")
        return 0
    if not push_sender._ensure_app():
        print("Firebase credentials not configured on this machine.")
        return 1

    tally = send(rows, args.title, args.body)
    print(f"sent {tally['sent']}, no token {tally['no_token']}, "
          f"unregistered (removed) {tally['unregistered']}, failed {tally['failed']}")
    return 1 if tally["failed"] and not tally["sent"] else 0


if __name__ == "__main__":
    sys.exit(main())
