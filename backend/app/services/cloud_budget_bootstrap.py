"""Offline operator cutover CLI; no default DB, environment/config or provider reads."""
import argparse
import json
from datetime import datetime, timedelta, timezone
import sqlite3
import sys
from pathlib import Path

from app.services.cloud_budget import PAID_ALIASES, BudgetDenied, CloudBudget


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', required=True, type=Path, help='Verified existing persistent telemetry SQLite file')
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--receipt', type=Path, help='Explicit wallet/month reconciliation JSON')
    action.add_argument('--list-unknown-rows', metavar='YYYY-MM',
                        help='Read-only: print the paid llm_calls rows of that month with unknown '
                             'usage, for the receipt\'s unknown_usage_rows_covered')
    action.add_argument('--settle-orphans', action='store_true',
                        help='Settle reservations whose process died (audited); needs '
                             '--older-than-minutes and --evidence')
    parser.add_argument('--older-than-minutes', type=float)
    parser.add_argument('--evidence', help='Why these attempts are orphans (stored in the audit row)')
    parser.add_argument('--policy', choices=('request-bound', 'full'), default='request-bound')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--now', help='ISO time to measure age from (default: now, UTC)')
    args = parser.parse_args(argv)
    if args.settle_orphans:
        if not args.older_than_minutes or args.older_than_minutes <= 0 or not (args.evidence or '').strip():
            print('--settle-orphans needs --older-than-minutes > 0 and --evidence', file=sys.stderr)
            return 2
        try:
            now = datetime.fromisoformat(args.now) if args.now else datetime.now(timezone.utc)
            ids = CloudBudget(args.db, clock=lambda: now).settle_orphans(
                older_than=timedelta(minutes=args.older_than_minutes), evidence=args.evidence,
                now=now, policy=args.policy, dry_run=args.dry_run)
        except (BudgetDenied, OSError, ValueError, sqlite3.Error) as exc:
            print(f'Orphan settlement refused: {exc}', file=sys.stderr)
            return 2
        print(json.dumps({'dry_run': args.dry_run, 'policy': args.policy, 'orphans': ids}, indent=1))
        return 0
    if args.list_unknown_rows:
        try:
            rows = CloudBudget(args.db).list_unknown_usage_rows(args.list_unknown_rows)
        except (BudgetDenied, OSError, ValueError, sqlite3.Error) as exc:
            print(f'Cannot list unknown-usage rows: {exc}', file=sys.stderr)
            return 2
        print(json.dumps({'month': args.list_unknown_rows, 'aliases': list(PAID_ALIASES),
                          'unknown_usage_rows': [r['id'] for r in rows], 'rows': rows}, indent=1))
        return 0
    try:
        receipt = json.loads(args.receipt.read_text())
        CloudBudget(args.db).bootstrap(receipt)
    except (BudgetDenied, OSError, ValueError) as exc:
        print(f'Cloud budget activation refused: {exc}', file=sys.stderr)
        return 2
    print('Cloud budget activation verified or identical receipt already applied.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
