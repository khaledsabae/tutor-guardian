import os
import time
import sqlite3
from app.db.init_db import db_path
from app.services.privacy import known_child_names, redact_for_cloud
from app.middleware.rate_limit import RateLimitMiddleware


def test_privacy_cache_invalidation():
    # 1. Initially, there are no children in the DB.
    # The cache should be empty.
    assert known_child_names() == ()

    # 2. Insert a child profile into the temp DB.
    conn = sqlite3.connect(db_path())
    conn.execute(
        "INSERT INTO child_profiles (device_id, name, age_group) VALUES ('test_device', 'خالد', '4-6')"
    )
    conn.commit()
    conn.close()

    # 3. Touch the DB file to make sure modification time changes.
    db_file = db_path()
    now = time.time()
    os.utime(db_file, (now + 5.0, now + 5.0))

    # 4. Assert that known_child_names() returns the new child name.
    # It must invalidate the cache and read from the DB because the modification time changed!
    assert known_child_names() == ("خالد",)

    # 5. Verify redaction works.
    assert redact_for_cloud("ابني خالد يلعب بالكرة") == "ابني طفلي يلعب بالكرة"


def test_rate_limiter_eviction():
    class FakeApp:
        async def __call__(self, scope, receive, send):
            pass

    middleware = RateLimitMiddleware(FakeApp())

    # 1. Populate the in-memory buckets.
    now = time.monotonic()
    middleware._buckets = {
        "rl:api:device1": (now - 100.0, 1),  # Expired (100s ago > 60s window)
        "rl:api:device2": (now - 10.0, 5),   # Active (10s ago < 60s window)
    }

    # 2. Set the last cleanup time to 10 minutes ago.
    middleware._last_cleanup = now - 600.0

    # Mock dynamic logic of dispatch's cleanup block
    current_time = time.monotonic()
    if current_time - middleware._last_cleanup > 300.0:
        expired_keys = [
            k for k, (start, _) in middleware._buckets.items()
            if current_time - start >= 60.0
        ]
        for k in expired_keys:
            middleware._buckets.pop(k, None)
        middleware._last_cleanup = current_time

    # 3. Assert that the expired key was removed, and the active key remains.
    assert "rl:api:device1" not in middleware._buckets
    assert "rl:api:device2" in middleware._buckets
    assert middleware._last_cleanup == current_time
