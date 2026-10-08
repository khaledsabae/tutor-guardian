"""Immutable telemetry migration 2: llm_calls.usage_estimated.

1 = the token counts on the row were NOT reported by the provider but
estimated by the gateway (a stream cut before its usage chunk, a timeout, a
host that ignores include_usage) — or are an explicit zero for a request the
provider refused. 0 = reported by the provider, or a row written before this
column existed. Existing rows keep their values: an old NULL stays "unknown".
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from .runner import Migration, MigrationContext, MigrationError

_COLUMN = "usage_estimated"


def _column(context: MigrationContext):
    for row in context.execute("PRAGMA main.table_xinfo(llm_calls)"):
        if row[1] == _COLUMN:
            return row
    return None


def _apply(context: MigrationContext) -> None:
    if _column(context) is None:
        context.execute(
            f"ALTER TABLE main.llm_calls ADD COLUMN {_COLUMN} INTEGER NOT NULL DEFAULT 0"
        )


def _validate(context: MigrationContext) -> None:
    row = _column(context)
    # (cid, name, type, notnull, dflt_value, pk, hidden)
    if (row is None or row[2].upper() != "INTEGER" or row[3] != 1
            or str(row[4]) != "0" or row[6] != 0):
        raise MigrationError("llm_calls.usage_estimated has an incompatible shape")


MIGRATION = Migration(
    number=2,
    name="usage_estimated",
    checksum=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    apply=_apply,
    validate=_validate,
)
