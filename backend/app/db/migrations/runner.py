"""Numbered, checksummed additive migrations within one SQLite database."""
from __future__ import annotations

from dataclasses import dataclass
import re
import sqlite3
from typing import Callable, Sequence


class MigrationError(RuntimeError):
    """Unsupported registry, ledger or live schema; refuse to guess a repair."""


class MigrationContext:
    """Small API for trusted migrations, without commit or executescript.

    Callbacks use this API rather than reaching into the underlying connection.
    Validation gets a read-only context. Neither context changes connection PRAGMAs.
    """

    def __init__(self, connection: sqlite3.Connection, *, readonly: bool = False):
        self._connection = connection
        self._readonly = readonly

    def execute(self, sql: str, parameters=()) -> sqlite3.Cursor:
        statement = sql.strip()
        read = bool(re.match(r"SELECT\b", statement, re.I)) or bool(re.fullmatch(
            r"PRAGMA\s+(?:main\.)?(?:table_(?:x)?info|index_list)\([A-Za-z_][A-Za-z_0-9]*\)\s*;?",
            statement, re.I,
        ))
        additive = bool(re.match(
            r"CREATE\s+(?:TABLE|(?:UNIQUE\s+)?INDEX)\b|ALTER\s+TABLE\s+\S+\s+ADD\s+COLUMN\b",
            statement, re.I,
        ))
        if not read and (self._readonly or not additive):
            raise MigrationError("migration context only permits introspection and additive DDL")
        # execute accepts one statement and never does executescript's implicit COMMIT.
        return self._connection.execute(sql, parameters)


@dataclass(frozen=True)
class Migration:
    number: int
    name: str
    checksum: str
    apply: Callable[[MigrationContext], None]
    validate: Callable[[MigrationContext], None]


_LEDGER_SQL = """CREATE TABLE IF NOT EXISTS main.schema_migrations (
    namespace TEXT NOT NULL,
    version INTEGER NOT NULL,
    name TEXT NOT NULL,
    checksum TEXT NOT NULL,
    applied_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY(namespace, version)
)"""


def _validate_ledger(connection: sqlite3.Connection) -> None:
    columns = {row[1]: row for row in connection.execute("PRAGMA main.table_info(schema_migrations)")}
    if sum(bool(row[5]) for row in columns.values()) != 2:
        raise MigrationError("schema_migrations requires the namespace/version primary key")
    for name, kind, key in (
        ("namespace", "TEXT", 1), ("version", "INTEGER", 2),
        ("name", "TEXT", 0), ("checksum", "TEXT", 0), ("applied_at", "TEXT", 0),
    ):
        row = columns.get(name)
        if row is None or row[2].upper() != kind or row[3] != 1 or row[5] != key:
            raise MigrationError("existing schema_migrations has an incompatible shape")


def _discard(connection: sqlite3.Connection) -> None:
    """End this module's own transaction; if that fails, drop the connection."""
    if connection.in_transaction:
        try:
            connection.execute("ROLLBACK")
        except sqlite3.Error:
            # A persistent progress callback/authorizer can deny ROLLBACK.
            # Closing rolls back uncommitted work without clearing caller
            # policy. The failed caller must discard this connection.
            connection.close()


def _already_current(
    connection: sqlite3.Connection, namespace: str, expected: list, migrations: Sequence[Migration],
) -> bool:
    """True only if the ledger is exactly complete and every live shape validates.

    Runs in a deferred transaction: under WAL, a read snapshot that takes no
    writer lock, so opening a migrated database never queues behind another
    writer. Any doubt returns False and leaves the decision (and the error)
    to the locked path. Nothing here writes: the context is read-only.
    """
    try:
        connection.execute("BEGIN")
        if connection.execute(
            "SELECT 1 FROM main.sqlite_master WHERE type='table' AND name='schema_migrations'"
        ).fetchone() is None:
            return False
        try:
            _validate_ledger(connection)
            rows = connection.execute(
                "SELECT version,name,checksum FROM main.schema_migrations "
                "WHERE namespace=? ORDER BY version", (namespace,),
            ).fetchall()
            if [tuple(row) for row in rows] != expected:
                return False
            read = MigrationContext(connection, readonly=True)
            for migration in migrations:
                migration.validate(read)
        except MigrationError:
            return False
        return True
    finally:
        _discard(connection)


def apply_migrations(
    connection: sqlite3.Connection, namespace: str, migrations: Sequence[Migration],
) -> tuple[int, ...]:
    """Apply one ordered registry atomically; return newly applied numbers.

    A database whose ledger already holds the whole registry, and whose live
    shapes all validate, is confirmed from a lock-free read snapshot.
    Otherwise the writer lock serializes concurrent processes on this
    database. Registry entries are immutable source files. Existing ledger
    entries must be its exact prefix; other namespaces are left alone. A valid
    ledger never bypasses live schema validation, on either path. Caller-owned
    transactions are neither committed nor rolled back.
    """
    if not re.fullmatch(r"[A-Za-z][A-Za-z_0-9-]*", namespace):
        raise MigrationError("invalid migration namespace")
    if (not migrations or [m.number for m in migrations] != list(range(1, len(migrations) + 1))
            or any(not m.name or not re.fullmatch(r"[a-f0-9]{64}", m.checksum) for m in migrations)):
        raise MigrationError("registry must be consecutively numbered with SHA-256 checksums")
    if connection.in_transaction:
        raise MigrationError("migration requires a connection without caller-owned work")
    expected = [(m.number, m.name, m.checksum) for m in migrations]
    # Fast path: a complete ledger whose every live shape still validates is
    # answered from a read snapshot. It skips the lock, never the validation.
    if _already_current(connection, namespace, expected, migrations):
        return ()
    try:
        # SQLite may acquire the writer lock before an interrupted BEGIN
        # raises, so acquisition needs the same cleanup as subsequent work.
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(_LEDGER_SQL)
        _validate_ledger(connection)
        rows = connection.execute(
            "SELECT version,name,checksum FROM main.schema_migrations "
            "WHERE namespace=? ORDER BY version", (namespace,),
        ).fetchall()
        if len(rows) > len(expected) or [tuple(row) for row in rows] != expected[:len(rows)]:
            raise MigrationError("migration ledger has unknown versions or changed names/checksums")
        applied = []
        read = MigrationContext(connection, readonly=True)
        write = MigrationContext(connection)
        for position, migration in enumerate(migrations):
            if position >= len(rows):
                migration.apply(write)
            migration.validate(read)
            if position >= len(rows):
                connection.execute(
                    "INSERT INTO main.schema_migrations(namespace,version,name,checksum) VALUES(?,?,?,?)",
                    (namespace, migration.number, migration.name, migration.checksum),
                )
                applied.append(migration.number)
        connection.execute("COMMIT")
        return tuple(applied)
    except BaseException:
        # Cancellation/KeyboardInterrupt also undo DDL and ledger writes.
        _discard(connection)
        raise
