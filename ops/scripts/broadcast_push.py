#!/usr/bin/env python3
"""
broadcast_push.py — send a notification to every device with a stored FCM token.

Runs inside the backend container (it has the DB + Firebase service account).
Usage (from the VPS):
    docker exec tg_backend python3 /app/ops/scripts/broadcast_push.py         --title "عنوان" --body "نص الرسالة"
"""
import argparse
import os
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, "/app")

from app.services.push_sender import send_to_device

DB_PATH = Path(os.environ.get("CONVERSATIONS_DB", "/app/ops/conversations.db"))


def all_device_ids() -> list[str]:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT DISTINCT device_id FROM push_tokens "
            "WHERE token IS NOT NULL AND token != ''"
        ).fetchall()
        return [row["device_id"] for row in rows if row["device_id"]]
    finally:
        conn.close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--title", required=True)
    ap.add_argument("--body", required=True)
    ap.add_argument("--data", default="", help="optional key=value,key=value payload")
    args = ap.parse_args()

    data = {}
    if args.data:
        for pair in args.data.split(","):
            if "=" in pair:
                k, v = pair.split("=", 1)
                data[k.strip()] = v.strip()

    device_ids = all_device_ids()
    print(f"Broadcasting to {len(device_ids)} devices...")
    success = failed = no_token = unregistered = 0
    for device_id in device_ids:
        result = send_to_device(
            device_id=device_id,
            title=args.title,
            body=args.body,
            data=data,
        )
        if result.get("ok") and result.get("sent"):
            success += 1
            print(f"  ✓ {device_id[:16]}...")
        elif result.get("reason") == "unregistered":
            unregistered += 1
            print(f"  ✗ {device_id[:16]}... unregistered")
        elif result.get("reason") == "no_token":
            no_token += 1
        else:
            failed += 1
            print(f"  ✗ {device_id[:16]}...: {result}")

    print(
        f"\nDone: {success} sent, {no_token} no token, "
        f"{unregistered} unregistered, {failed} failed, {len(device_ids)} total"
    )
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
