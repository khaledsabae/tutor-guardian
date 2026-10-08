"""Explicit cutover authority; fresh/restored telemetry is not spend authority."""
import shutil
import sqlite3
import importlib.util
import json
from datetime import datetime, timezone
import pytest
from app.services.cloud_budget import CloudBudget, BudgetDenied

NOW = datetime(2026, 10, 7, tzinfo=timezone.utc)
ALIASES = ('azure_deepseek', 'deepseek', 'deepseek_aux', 'deepseek_fallback')


def receipt(opening=0):
    return {'db_identity': 'independent-test-database', 'wallet': 'wallet',
            'month': '2026-10', 'opening_tokens': opening,
            'reconciled_through': NOW.isoformat(), 'legacy_aliases': list(ALIASES),
            'evidence_reference': 'simulated-provider-test-reconciliation',
            'unreserved_writers_drained': True}


def ledger(tmp_path):
    return CloudBudget(tmp_path / 'sessions.db', clock=lambda: NOW)


def existing_history(l):
    with sqlite3.connect(l.path) as c:
        c.execute('CREATE TABLE llm_calls(ts TEXT,provider TEXT,prompt_tokens INTEGER,completion_tokens INTEGER)')
    return l


def test_missing_volume_refuses_without_creating_database(tmp_path):
    l = ledger(tmp_path)
    with pytest.raises(BudgetDenied, match='cutover|seed|unknown'):
        l.reserve('wallet', 100, 100, legacy_aliases=ALIASES)
    assert not l.path.exists()


def test_fresh_telemetry_table_is_not_cutover_authority(tmp_path):
    l = ledger(tmp_path)
    with sqlite3.connect(l.path) as c:
        c.execute('CREATE TABLE llm_calls(ts TEXT,provider TEXT,prompt_tokens INTEGER,completion_tokens INTEGER)')
    with pytest.raises(BudgetDenied):
        l.reserve('wallet', 100, 100, legacy_aliases=ALIASES)


def test_bootstrap_imports_all_legacy_aliases_and_is_idempotent(tmp_path):
    l = ledger(tmp_path)
    with sqlite3.connect(l.path) as c:
        c.execute('CREATE TABLE llm_calls(ts TEXT,provider TEXT,prompt_tokens INTEGER,completion_tokens INTEGER)')
        c.executemany('INSERT INTO llm_calls VALUES(?,?,?,?)',
            [(NOW.isoformat(), a, 6, 4) for a in ALIASES])
    l.bootstrap(receipt(40))
    l.reserve('wallet', 100, 60, legacy_aliases=ALIASES)
    l.bootstrap(receipt(40))
    with pytest.raises(BudgetDenied):
        l.reserve('wallet', 100, 1, legacy_aliases=ALIASES)
    with pytest.raises(BudgetDenied):
        l.bootstrap(receipt(0))


def test_restored_database_cannot_reset_live_spend(tmp_path):
    l = existing_history(ledger(tmp_path))
    l.bootstrap(receipt())
    snapshot = tmp_path / 'old.db'
    shutil.copyfile(l.path, snapshot)
    l.reserve('wallet', 100, 100, legacy_aliases=ALIASES)
    shutil.copyfile(snapshot, l.path)
    with pytest.raises(BudgetDenied, match='continuity|restore|identity'):
        l.reserve('wallet', 100, 1, legacy_aliases=ALIASES)
    with pytest.raises(BudgetDenied):
        l.bootstrap(receipt())


def test_deleted_database_or_anchor_requires_reconciliation(tmp_path):
    l = existing_history(ledger(tmp_path))
    l.bootstrap(receipt())
    l.path.unlink()
    with pytest.raises(BudgetDenied):
        l.bootstrap(receipt())
    with pytest.raises(BudgetDenied):
        l.reserve('wallet', 100, 1, legacy_aliases=ALIASES)


def test_bootstrap_requires_specific_evidence_and_drained_writers(tmp_path):
    for change in [{'evidence_reference': ''}, {'opening_tokens': None},
                   {'unreserved_writers_drained': False}, {'reconciled_through': 'invalid'}]:
        with pytest.raises(BudgetDenied):
            ledger(tmp_path).bootstrap({**receipt(), **change})


def test_bootstrap_cannot_create_missing_history(tmp_path):
    l = ledger(tmp_path)
    with pytest.raises(BudgetDenied):
        l.bootstrap(receipt())
    assert not l.path.exists()


@pytest.mark.parametrize('table', ['llm_calls', 'cloud_budget_months',
    'cloud_budget_attempts', 'cloud_budget_carry', 'cloud_budget_activation', 'cloud_budget_identity'])
def test_lost_schema_is_never_recreated_by_admission(tmp_path, table):
    l = existing_history(ledger(tmp_path))
    l.bootstrap(receipt())
    with sqlite3.connect(l.path) as c:
        c.execute(f'DROP TABLE {table}')
    with pytest.raises(BudgetDenied):
        l.reserve('wallet', 100, 1, legacy_aliases=ALIASES)
    with pytest.raises(BudgetDenied):
        l.bootstrap(receipt())
    with sqlite3.connect(l.path) as c:
        assert not c.execute('SELECT 1 FROM sqlite_master WHERE name=?', (table,)).fetchone()


def test_reseed_never_reduces_settled_or_pending_charges(tmp_path):
    l = existing_history(ledger(tmp_path))
    l.bootstrap(receipt(20))
    settled = l.reserve('wallet', 100, 40, legacy_aliases=ALIASES)
    l.settle(settled, 15, 5)
    l.reserve('wallet', 100, 60, legacy_aliases=ALIASES)
    l.bootstrap(receipt(20))
    with pytest.raises(BudgetDenied):
        l.reserve('wallet', 100, 1, legacy_aliases=ALIASES)
    with pytest.raises(BudgetDenied):
        l.bootstrap(receipt(0))


def test_wrong_wallet_identity_or_aliases_cannot_authorize(tmp_path):
    l = existing_history(ledger(tmp_path))
    l.bootstrap(receipt())
    with pytest.raises(BudgetDenied):
        l.reserve('different-wallet', 100, 1, legacy_aliases=ALIASES)
    with pytest.raises(BudgetDenied):
        l.bootstrap({**receipt(), 'db_identity': 'other-database'})
    with pytest.raises(BudgetDenied):
        l.reserve('wallet', 100, 1, legacy_aliases=(*ALIASES, 'new-paid-alias'))


@pytest.mark.parametrize('change', [
    {'legacy_aliases': ['deepseek']}, {'opening_tokens': True},
    {'opening_tokens': -1}, {'db_identity': ''}, {'wallet': ''},
    {'month': '2026-09'}, {'reconciled_through': '2026-10-08T00:00:00+00:00'},
    {'reconciled_through': '2026-10-07T00:00:00'},
])
def test_incomplete_or_future_cutover_evidence_denies(tmp_path, change):
    l = existing_history(ledger(tmp_path))
    with pytest.raises(BudgetDenied):
        l.bootstrap({**receipt(), **change})


def test_opening_below_known_spend_or_cutoff_before_legacy_denies(tmp_path):
    l = existing_history(ledger(tmp_path))
    with sqlite3.connect(l.path) as c:
        c.execute('INSERT INTO llm_calls VALUES(?,?,?,?)',
                  (NOW.isoformat(), 'deepseek_aux', 60, 40))
    with pytest.raises(BudgetDenied):
        l.bootstrap(receipt(99))
    with pytest.raises(BudgetDenied):
        l.bootstrap({**receipt(100), 'reconciled_through': '2026-10-06T00:00:00+00:00'})


def test_rollover_requires_new_reconciliation_and_carries_unknown_spend(tmp_path):
    l = existing_history(ledger(tmp_path))
    l.bootstrap(receipt())
    l.reserve('wallet', 100, 100, legacy_aliases=ALIASES)
    later = datetime(2026, 11, 1, tzinfo=timezone.utc)
    l.clock = lambda: later
    with pytest.raises(BudgetDenied):
        l.reserve('wallet', 100, 1, legacy_aliases=ALIASES)
    l.bootstrap({**receipt(), 'month': '2026-11', 'reconciled_through': later.isoformat()})
    with pytest.raises(BudgetDenied):
        l.reserve('wallet', 100, 1, legacy_aliases=ALIASES)


def test_anchor_loss_and_corruption_never_allow_rebootstrap(tmp_path):
    l = existing_history(ledger(tmp_path))
    l.bootstrap(receipt())
    l.anchor_path.unlink()
    with pytest.raises(BudgetDenied):
        l.bootstrap(receipt())
    l.anchor_path.write_text('[]')
    with pytest.raises(BudgetDenied):
        l.reserve('wallet', 100, 1, legacy_aliases=ALIASES)


def test_committed_charge_survives_failed_anchor_write(tmp_path, monkeypatch):
    l = existing_history(ledger(tmp_path))
    l.bootstrap(receipt())
    def fail(*args):
        raise OSError('simulated durable witness failure')
    monkeypatch.setattr(l, '_write_anchor', fail)
    with pytest.raises(BudgetDenied):
        l.reserve('wallet', 100, 100, legacy_aliases=ALIASES)
    with sqlite3.connect(l.path) as conn:
        assert conn.execute('SELECT charged_tokens FROM cloud_budget_attempts').fetchone() == (100,)
    monkeypatch.undo()
    with pytest.raises(BudgetDenied):
        l.reserve('wallet', 100, 1, legacy_aliases=ALIASES)
    with pytest.raises(BudgetDenied):
        l.bootstrap(receipt())


def test_bootstrap_cli_uses_explicit_existing_db_and_receipt(tmp_path, monkeypatch):
    assert importlib.util.find_spec('app.services.cloud_budget_bootstrap'), 'operational bootstrap CLI missing'
    from app.services import cloud_budget_bootstrap as cli
    l = existing_history(ledger(tmp_path))
    monkeypatch.setattr(cli, 'CloudBudget', lambda path: l)
    evidence = tmp_path / 'receipt.json'
    evidence.write_text(json.dumps(receipt(100)))
    assert cli.main(['--db', str(l.path), '--receipt', str(evidence)]) == 0
    assert cli.main(['--db', str(l.path), '--receipt', str(evidence)]) == 0
    with pytest.raises(BudgetDenied):
        l.reserve('wallet', 100, 1, legacy_aliases=ALIASES)
    evidence.write_text(json.dumps(receipt(0)))
    assert cli.main(['--db', str(l.path), '--receipt', str(evidence)]) != 0


def test_explicit_bootstrap_requires_existing_telemetry_schema(tmp_path):
    l = ledger(tmp_path)
    with sqlite3.connect(l.path):
        pass
    with pytest.raises(BudgetDenied):
        l.bootstrap(receipt())
    with sqlite3.connect(l.path) as conn:
        assert not conn.execute("SELECT 1 FROM sqlite_master WHERE name LIKE 'cloud_budget_%'").fetchone()


def test_pre_activation_ledger_adoption_preserves_charges_and_pending(tmp_path):
    l = existing_history(ledger(tmp_path))
    # Simulate f59 schema, before explicit activation existed.
    with sqlite3.connect(l.path) as conn:
        conn.executescript('''
            CREATE TABLE cloud_budget_months(wallet TEXT,month TEXT,opening_tokens INTEGER,blocked INTEGER,
                PRIMARY KEY(wallet,month));
            CREATE TABLE cloud_budget_attempts(id TEXT PRIMARY KEY,wallet TEXT,month TEXT,
                bound INTEGER,charged_tokens INTEGER,settled INTEGER);
            CREATE TABLE cloud_budget_carry(wallet TEXT,month TEXT,attempt_id TEXT,charged_tokens INTEGER,
                PRIMARY KEY(wallet,month,attempt_id));
            INSERT INTO cloud_budget_months VALUES('wallet','2026-10',20,0);
            INSERT INTO cloud_budget_attempts VALUES('settled','wallet','2026-10',60,20,1);
            INSERT INTO cloud_budget_attempts VALUES('pending','wallet','2026-10',60,60,0);
        ''')
    l.bootstrap(receipt(20))
    l.bootstrap(receipt(20))
    with pytest.raises(BudgetDenied):
        l.reserve('wallet', 100, 1, legacy_aliases=ALIASES)
    with sqlite3.connect(l.path) as conn:
        assert conn.execute('SELECT SUM(charged_tokens),SUM(settled) FROM cloud_budget_attempts').fetchone() == (80, 1)


def test_restored_snapshot_without_witness_cannot_be_reseeded_at_new_path(tmp_path):
    l = existing_history(ledger(tmp_path))
    l.bootstrap(receipt())
    snapshot = tmp_path / 'old.db'
    shutil.copyfile(l.path, snapshot)
    l.reserve('wallet', 100, 100, legacy_aliases=ALIASES)
    restored = CloudBudget(snapshot, clock=lambda: NOW)
    with pytest.raises(BudgetDenied):
        restored.bootstrap(receipt())
    with pytest.raises(BudgetDenied):
        restored.reserve('wallet', 100, 1, legacy_aliases=ALIASES)
