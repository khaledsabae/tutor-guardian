#!/usr/bin/env python3
"""Carry out an emailed deletion request — the path for people without the app.

The privacy policy and /delete-account promise: email support@alsaba.cloud and
the account is deleted within 30 days. This is how. It runs the exact deletion
the in-app button runs (routers/privacy.py erase_account), so the two paths
cannot drift apart.

Run inside the backend container (it reads CONVERSATIONS_DB from there):

    # signed in with Google: the request came from that account's address
    docker exec -w /app tg_backend python ops/scripts/delete_account.py --email someone@example.com
    # anything else that pins one device (e.g. found from the details they gave)
    docker exec -w /app tg_backend python ops/scripts/delete_account.py --device-id <id>

Dry run by default: it prints how many rows each table holds for the account.
Add --yes to delete. Prints counts only — never the data itself.

Same rule as the in-app button (PR #26 final review): the deletion follows only
Google links that a session proven to hold its phone made. A phone linked
without that proof is listed but not included — the address proves who owns
the Google account, not who owns every phone someone linked to it. Check such a
phone separately and delete it with --device-id. With --email and no confirmed
phone at all, only the Google account itself goes (its record, backups and
links); no phone's data.
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

# ruff: noqa: E402
from app.db.init_db import get_conn
from app.routers.privacy import (
    DEPENDENT_TABLES, _table_columns, account_devices, erase_account, erase_identity,
)


def links_for_email(email: str) -> list[tuple[str, str, bool]]:
    """(device_id, google_id, confirmed) for every phone linked to the Google
    account with this address."""
    conn = get_conn()
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(identity_links)")}
        flag = "l.confirmed" if "confirmed" in cols else "NULL"
        return [(r[0], r[1], bool(r[2])) for r in conn.execute(
            f"SELECT l.device_id, l.google_id, {flag} FROM identity_links l "
            "JOIN parent_identities p ON p.google_id = l.google_id "
            "WHERE lower(p.email) = lower(?)", (email.strip(),))]
    finally:
        conn.close()


def devices_for_email(email: str) -> list[str]:
    return [d for d, _, _ in links_for_email(email)]


def preview(device_id: str) -> dict:
    """Rows the deletion would remove, per table (device-scoped + dependents)."""
    conn = get_conn()
    try:
        tables = _table_columns(conn)
        devices, google_ids = account_devices(conn, device_id, tables)
        marks = ",".join("?" * len(devices))
        counts: dict[str, int] = {}
        for table, column, parent, pcol in DEPENDENT_TABLES:
            if table in tables and "device_id" in tables.get(parent, set()):
                counts[table] = conn.execute(
                    f"SELECT COUNT(*) FROM {table} WHERE {column} IN "
                    f"(SELECT {pcol} FROM {parent} WHERE device_id IN ({marks}))",
                    devices).fetchone()[0]
        for table, cols in tables.items():
            if "device_id" in cols:
                counts[table] = conn.execute(
                    f"SELECT COUNT(*) FROM {table} WHERE device_id IN ({marks})",
                    devices).fetchone()[0]
        return {"devices": len(devices), "signed_in": bool(google_ids),
                "rows": {t: n for t, n in sorted(counts.items()) if n}}
    finally:
        conn.close()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    who = ap.add_mutually_exclusive_group(required=True)
    who.add_argument("--email", help="the Google account's email address")
    who.add_argument("--device-id", help="one device of the account")
    ap.add_argument("--yes", action="store_true", help="delete (default: dry run)")
    args = ap.parse_args(argv)

    if args.email:
        links = links_for_email(args.email)
        if not links:
            print("no Google-linked account with that email — nothing to delete")
            return 2
        unconfirmed = [d for d, _, ok in links if not ok]
        if unconfirmed:
            print(f"{len(unconfirmed)} phone(s) linked WITHOUT a confirmed session — "
                  "not included; verify each and use --device-id")
        confirmed = [d for d, _, ok in links if ok]
        if not confirmed:
            google_ids = sorted({g for _, g, _ in links})
            print(f"no confirmed phone: only the Google account itself "
                  f"({len(google_ids)} identity) — record, backups, links")
            if not args.yes:
                print("dry run — add --yes to delete")
                return 0
            result = erase_identity(google_ids)
            print(f"deleted {sum(result.values())} identity rows across {len(result)} tables")
            return 0
        device = confirmed[0]   # erase_account expands to every confirmed-linked device
    else:
        device = args.device_id

    try:
        found = preview(device)
    except sqlite3.Error as exc:
        print(f"database error: {exc}")
        return 1
    print(f"account: {found['devices']} device(s), signed_in={found['signed_in']}, "
          f"{sum(found['rows'].values())} rows")
    for table, n in found["rows"].items():
        print(f"  {table}: {n}")
    if not found["rows"]:
        print("nothing stored for this account")
        return 0
    if not args.yes:
        print("dry run — add --yes to delete")
        return 0
    result = erase_account(device)
    print(f"deleted {sum(result['deleted'].values())} rows "
          f"across {len(result['deleted'])} tables")
    return 0


if __name__ == "__main__":
    sys.exit(main())
