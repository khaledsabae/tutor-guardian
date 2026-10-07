"""Offline operator cutover CLI; no default DB, environment/config or provider reads."""
import argparse
import json
import sys
from pathlib import Path

from app.services.cloud_budget import BudgetDenied, CloudBudget


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', required=True, type=Path, help='Verified existing persistent telemetry SQLite file')
    parser.add_argument('--receipt', required=True, type=Path, help='Explicit wallet/month reconciliation JSON')
    args = parser.parse_args(argv)
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
