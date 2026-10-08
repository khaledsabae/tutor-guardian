"""Numbered migrations are immutable once written: their checksums are pinned.

The runner records each migration's SHA-256 in schema_migrations and refuses a
database whose ledger names a different checksum. Changing an applied
migration therefore disables its owner in production. This guard catches the
edit here instead. Changing a pin is only legitimate for a migration that has
never been applied anywhere; anything else gets a new, higher number.
"""
from __future__ import annotations

import hashlib
import importlib
from pathlib import Path

MIGRATIONS = Path(__file__).resolve().parents[1] / "app" / "db" / "migrations"

# file -> (namespace, number, registered name, sha256 of the file)
PINNED = {
    "telemetry_0001_llm_calls.py": (
        "llm_telemetry", 1, "llm_calls",
        "83c9b23721f7cdaf2a23aa5dca3e62645c0128bbb1e15defa321754e4ecf212e"),
    "telemetry_0002_usage_estimated.py": (
        "llm_telemetry", 2, "usage_estimated",
        "772d8c7769aa5c71b8a59dff1d25976fe9c217ae283d4bc09cbfdcbea4f1ca8f"),
    "sessions_0001_baseline.py": (
        "sessions", 1, "sessions_baseline",
        "fb81bf51570d65725d4ae2672033b11ba04ba28cad3b33891764e64812a5907b"),
    "tafsir_cache_0001_baseline.py": (
        "tafsir_cache", 1, "tafsir_cache_baseline",
        "bd1c4cf69d64190e0a8b540f5625235ef93195e29b3993146c31ddcf2978f988"),
    "bahouth_cache_0001_baseline.py": (
        "bahouth_cache", 1, "bahouth_cache_baseline",
        "2e8a504ae33c1bc1871eb200c3b669c6ec855573acbd02b317dd8df52a3fd973"),
    "query_rewrites_0001_baseline.py": (
        "query_rewrites", 1, "query_rewrites_baseline",
        "ac7d070b82e4d1d8e6558c8748f27955435d9414efe7075a1bb40773c9d3f570"),
}


def numbered_files() -> list[Path]:
    return sorted(MIGRATIONS.glob("*_[0-9][0-9][0-9][0-9]_*.py"))


def test_every_numbered_migration_is_pinned():
    found = {p.name for p in numbered_files()}
    assert found == set(PINNED), (
        "a numbered migration was added or removed: pin its checksum here "
        "(new file) or restore it (removed file)")


def test_no_pinned_migration_was_edited():
    for path in numbered_files():
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        assert digest == PINNED[path.name][3], (
            f"{path.name} changed after its checksum was pinned. An applied migration "
            "is immutable: add the change as a new, higher-numbered migration")


def test_registered_migration_matches_its_pin():
    for name, (_namespace, number, registered, digest) in PINNED.items():
        migration = importlib.import_module(f"app.db.migrations.{name[:-3]}").MIGRATION
        assert (migration.number, migration.name, migration.checksum) == (number, registered, digest)


def test_numbers_are_consecutive_per_namespace():
    by_namespace: dict[str, list[int]] = {}
    for namespace, number, _name, _digest in PINNED.values():
        by_namespace.setdefault(namespace, []).append(number)
    for namespace, numbers in by_namespace.items():
        assert sorted(numbers) == list(range(1, len(numbers) + 1)), namespace
