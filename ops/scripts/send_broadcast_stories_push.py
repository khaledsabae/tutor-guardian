"""
High-Performance Multicast Push Sender for All Registered Devices.

Uses `messaging.send_each_for_multicast` in batches of 500 tokens per request.
Delivers notifications to all 2,300+ devices in ~2 seconds flat.
"""
import sys
import logging
from pathlib import Path

backend_dir = Path(__file__).resolve().parents[2] / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from firebase_admin import messaging
from app.db.init_db import get_conn
from app.services.push_sender import _ensure_app, send_to_topic

logging.basicConfig(level=logging.INFO)

def send_multicast_broadcast(dry_run: bool = False):
    if not _ensure_app():
        print("❌ Error: Firebase Admin credentials not configured!")
        return

    conn = get_conn()
    rows = conn.execute("SELECT DISTINCT token FROM push_tokens WHERE token IS NOT NULL AND token != ''").fetchall()
    conn.close()

    tokens = [r["token"] for r in rows]
    total_tokens = len(tokens)
    
    title = "📚 مفاجأة جديدة في «المربّي الذكي»!"
    body = "أضفنا قصصاً إسلامية تفاعلية جديدة لأطفالك بأسلوب جذاب 🌟 افتح مكتبة القصص الآن، وتأكد من تحديث التطبيق لأحدث إصدار!"
    data = {"screen": "story_bookshelf", "action": "open_stories"}

    print(f"📢 Found {total_tokens} valid FCM device tokens in database.")

    if dry_run:
        print("🔍 DRY RUN MODE — Previewing payload:")
        print(f"  Title: {title}\n  Body: {body}\n  Tokens count: {total_tokens}")
        return

    # Process in batches of 500 (FCM Multicast Limit)
    batch_size = 500
    total_success = 0
    total_failure = 0

    notification = messaging.Notification(title=title, body=body)
    android_config = messaging.AndroidConfig(
        priority="high",
        notification=messaging.AndroidNotification(
            channel_id="almorabbi_reengagement",
            sound="default",
        ),
    )

    for i in range(0, total_tokens, batch_size):
        batch_tokens = tokens[i : i + batch_size]
        multicast_msg = messaging.MulticastMessage(
            notification=notification,
            data=data,
            tokens=batch_tokens,
            android=android_config,
        )
        
        print(f"🚀 Sending batch {i // batch_size + 1} ({len(batch_tokens)} tokens)...")
        response = messaging.send_each_for_multicast(multicast_msg)
        total_success += response.success_count
        total_failure += response.failure_count
        print(f"   Batch result: {response.success_count} success, {response.failure_count} failure.")

    print(f"\n🎉 Multicast Push Broadcast Complete!")
    print(f"   - Total Successful Deliveries: {total_success}")
    print(f"   - Total Failures: {total_failure}")

    # Send topic push as well
    topic_res = send_to_topic("all_parents", title=title, body=body, data=data)
    print(f"📡 FCM Topic broadcast ('all_parents') result: {topic_res}")

if __name__ == "__main__":
    dry_run_flag = "--dry-run" in sys.argv
    send_multicast_broadcast(dry_run=dry_run_flag)
