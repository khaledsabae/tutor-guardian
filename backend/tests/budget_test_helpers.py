"""Explicit simulated cutover evidence for paid-wire tests; never production data."""
import sqlite3
from datetime import timezone

from app.services.cloud_budget import PAID_ALIASES


def activate(ledger, *, wallets=('wallet',), opening=0):
    conn = sqlite3.connect(ledger.path)
    try:
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='llm_calls'").fetchone():
            # The real telemetry schema (numbered migrations), so gateway rows land.
            from app.services.ai_gateway import _ensure_telemetry_schema
            _ensure_telemetry_schema(conn)
            conn.commit()
    finally:
        conn.close()
    now = ledger.clock().astimezone(timezone.utc)
    for wallet in wallets:
        ledger.bootstrap({
            'db_identity': 'simulated-test-db', 'wallet': wallet,
            'month': now.strftime('%Y-%m'), 'opening_tokens': opening,
            'reconciled_through': now.isoformat(), 'legacy_aliases': list(PAID_ALIASES),
            'evidence_reference': 'test-only-reconciliation', 'unreserved_writers_drained': True,
        })
    return ledger
