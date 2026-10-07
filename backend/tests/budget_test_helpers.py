"""Explicit simulated cutover evidence for paid-wire tests; never production data."""
import sqlite3
from datetime import timezone

from app.services.cloud_budget import PAID_ALIASES


def activate(ledger, *, wallets=('wallet',), opening=0):
    with sqlite3.connect(ledger.path) as conn:
        conn.execute('CREATE TABLE IF NOT EXISTS llm_calls ('
                     'ts TEXT, provider TEXT, prompt_tokens INTEGER, completion_tokens INTEGER)')
    now = ledger.clock().astimezone(timezone.utc)
    for wallet in wallets:
        ledger.bootstrap({
            'db_identity': 'simulated-test-db', 'wallet': wallet,
            'month': now.strftime('%Y-%m'), 'opening_tokens': opening,
            'reconciled_through': now.isoformat(), 'legacy_aliases': list(PAID_ALIASES),
            'evidence_reference': 'test-only-reconciliation', 'unreserved_writers_drained': True,
        })
    return ledger
