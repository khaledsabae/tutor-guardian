#!/usr/bin/env python3
"""Send a push notification to every registered FCM token.

Usage:
  python3 ops/scripts/send_update_push.py \\
    --title "تحديث رئيسي في المربي الذكي! 🆕" \\
    --body "شارك ميزان العادات مع أبنائك المراهقين عبر الويب، وفعّل وضع الطفل للصغار ليقيموا أنفسهم بأنفسهم. حدّث التطبيق الآن!"
"""

import argparse
import sys
from pathlib import Path

# Ensure the backend package is importable.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.db.init_db import get_conn
from app.services.push_sender import _ensure_app, send_to_device

def all_tokens():
    conn = get_conn()
    rows = conn.execute(
        "SELECT device_id, token FROM push_tokens ORDER BY updated_at DESC"
    ).fetchall()
    conn.close()
    return rows

def main():
    parser = argparse.ArgumentParser(description="Send push to all users")
    parser.add_argument("--title", default="تحديث رئيسي في المربي الذكي! 🆕")
    parser.add_argument("--body", default="شارك ميزان العادات مع أبنائك المراهقين عبر الويب، وفعّل وضع الطفل للصغار ليقيموا أنفسهم بأنفسهم. حدّث التطبيق الآن!")
    args = parser.parse_args()

    if not _ensure_app():
        print("❌ Firebase credentials not configured on this machine.")
        sys.exit(1)

    rows = all_tokens()
    print(f"📱 Found {len(rows)} registered device(s).")

    sent = 0
    failed = 0
    for device_id, token in rows:
        result = send_to_device(device_id, title=args.title, body=args.body)
        if result.get("sent"):
            sent += 1
        elif result.get("ok"):
            reason = result.get("reason", "unknown")
            print(f"  ⚠️  {device_id[:12]}… → {reason}")
        else:
            failed += 1
            print(f"  ❌ {device_id[:12]}… → {result.get('error', 'unknown')}")

    print(f"\n✅ Sent to {sent} device(s). {failed} error(s).")

if __name__ == "__main__":
    main()
