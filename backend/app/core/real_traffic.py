"""Real traffic only: the one rule metrics use to leave test traffic out.

Two kinds of test traffic write to the production database:

  * the eval harness (ops/tools/eval_answers.py) — devices named
    `EVAL_DEVICE_PREFIX + <item id>` (app/core/eval_traffic.py);
  * the remote emulator E2E gate (.github/workflows/mobile-e2e.yml, e2e/run.sh),
    which runs a release build against https://tg-api.alsaba.cloud. Each
    install renames its onboarding child to `E2E-Maestro` seconds after
    onboarding (e2e/flows/common/mark_child.yaml) and asks one question that
    starts with "E2E test".

The E2E devices, as the workflow header documents them:

    marked = devices owning a child named LIKE 'E2E-Maestro%'
           ∪ devices that asked a question LIKE 'E2E test%'
    e2e    = marked
           ∪ devices holding the same FCM token as a marked device (push_tokens):
             the install's twin, a second id minted at first launch
             (services/device_twins.py)
           ∪ device_aliases in either direction (schema v33; skipped where the
             table does not exist yet)

The question marker is not redundant: on production (2026-10-04) one E2E
install asked its question from a childless twin whose push token was not
shared — only the question identified it.

A report finds the E2E devices ONCE per run, then keeps real devices with one
predicate per statement:

    from app.core.real_traffic import e2e_devices, real_device_sql
    e2e = e2e_devices(conn)                       # one scan, per report run
    f"... WHERE {real_device_sql('cs.device_id', e2e)}"

The set travels as one JSON literal (`json_each`), not as a subquery: inlined
in every statement, the marked-device subquery scanned chat_messages two to
four times per statement and tripled the weekly funnel report's CPU on
production (5.2 s → 15.2 s; found once per run: 6.5 s). Nor as a parameter
list, which would grow with every E2E run. A NULL device is real traffic: rows
without a device keep being counted.

Dependency-free, like eval_traffic: scripts under ops/ import it with
`backend/` on sys.path, and it must not drag the app (or a database) in. (Not
named test_*: pytest would collect it.)
"""
from __future__ import annotations

import json
import sqlite3
from typing import Iterable

from app.core.eval_traffic import EVAL_DEVICE_LIKE

# e2e/run.sh: CHILD_NAME (E2E_CHILD_NAME, default "E2E-Maestro") and QUESTION
# (E2E_QUESTION, default "E2E test how can I teach my child to be honest").
# A leftover letter from a flawed rename ("E2E-Maestroي") still matches.
E2E_CHILD_NAME_LIKE = "E2E-Maestro%"
E2E_QUESTION_LIKE = "E2E test%"

# Inlined into SQL as literals, so they must stay plain — no quote, and no `_`,
# which LIKE would read as a wildcard.
for _pattern in (EVAL_DEVICE_LIKE, E2E_CHILD_NAME_LIKE, E2E_QUESTION_LIKE):
    assert "'" not in _pattern and "_" not in _pattern, _pattern


def table_names(conn: sqlite3.Connection) -> set[str]:
    return {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def e2e_devices_sql(tables: Iterable[str]) -> str:
    """A SELECT of every E2E device id in this database, never NULL. The marked
    devices are a CTE, so chat_messages is scanned once."""
    tables = set(tables)
    marked = []
    if "child_profiles" in tables:
        marked.append("SELECT device_id FROM child_profiles "
                      f"WHERE name LIKE '{E2E_CHILD_NAME_LIKE}'")
    if {"chat_messages", "chat_sessions"} <= tables:
        marked.append("SELECT s.device_id FROM chat_messages m "
                      "JOIN chat_sessions s ON s.id = m.session_id "
                      f"WHERE m.role = 'user' AND m.content LIKE '{E2E_QUESTION_LIKE}'")
    if not marked:
        return "SELECT NULL WHERE 0"
    parts = ["SELECT device_id FROM marked"]
    if "push_tokens" in tables:
        parts.append("SELECT device_id FROM push_tokens WHERE token IN "
                     "(SELECT token FROM push_tokens WHERE device_id IN marked)")
    if "device_aliases" in tables:
        parts.append("SELECT device_id FROM device_aliases WHERE canonical_device IN marked")
        parts.append("SELECT canonical_device FROM device_aliases WHERE device_id IN marked")
    return (f"WITH marked(device_id) AS ({' UNION '.join(marked)}) "
            f"SELECT device_id FROM ({' UNION '.join(parts)}) WHERE device_id IS NOT NULL")


def e2e_devices(conn: sqlite3.Connection) -> set[str]:
    """The E2E device ids in this database (eval devices are known by prefix)."""
    return {r[0] for r in conn.execute(e2e_devices_sql(table_names(conn))) if r[0] is not None}


def _json_literal(values: Iterable[str]) -> str:
    """A SQL string literal of a JSON array: one constant however many values.
    json.dumps escapes every control character (NUL included) and non-ASCII;
    SQL needs only the quote doubled."""
    return "'" + json.dumps(sorted(v for v in values if v is not None)).replace("'", "''") + "'"


def real_device_sql(column: str, e2e: Iterable[str]) -> str:
    """SQL predicate: `column` is neither an eval-harness device nor one of
    `e2e` (= e2e_devices(conn), found once per report run)."""
    return (f"({column} IS NULL OR ({column} NOT LIKE '{EVAL_DEVICE_LIKE}' "
            f"AND {column} NOT IN (SELECT value FROM json_each({_json_literal(e2e)}))))")


def real_session_sql(column: str, e2e: Iterable[str], tables: Iterable[str]) -> str:
    """SQL predicate for rows keyed by a chat session id (chat_messages,
    user_feedback): the session does not belong to a test device."""
    if "chat_sessions" not in set(tables):
        return "1"
    return (f"({column} IS NULL OR {column} NOT IN (SELECT id FROM chat_sessions "
            f"WHERE NOT {real_device_sql('device_id', e2e)}))")
