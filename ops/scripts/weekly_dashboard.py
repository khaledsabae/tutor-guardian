#!/usr/bin/env python3
"""Weekly metrics dashboard — sends a formatted summary to Telegram.

Usage (VPS cron, every Sunday 8:00 UTC):
    docker exec -w /app tg_backend python ops/scripts/weekly_dashboard.py

Collects:
  - ops-llm metrics (p95, cache hit rate, token usage, DeepSeek valve)
  - community stats (total users, active users, new users)
  - DB metrics (chat sessions, lessons completed, active children)
  - D1/D7 retention estimates from daily_login_streaks

Requires: TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID in environment
(or passed via --token / --chat-id flags).
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import urllib.request
import urllib.parse
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Add backend root to path
_backend_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_backend_root))

_DB = Path(os.environ.get(
    "SESSIONS_DB",
    str(Path(__file__).resolve().parents[2] / "ops" / "sessions.db"),
))


def _query_db(sql: str, params: tuple = ()) -> list[dict]:
    """Run a query against sessions.db and return list of dicts."""
    conn = sqlite3.connect(str(_DB))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def _fetch_ops_metrics() -> dict:
    """Fetch from /api/stats/ops-llm using the ops token."""
    base = os.environ.get("TG_API_BASE", "https://tg-api.alsaba.cloud")
    token = os.environ.get("TG_OPS_METRICS_TOKEN", "")
    if not token:
        return {"error": "no token"}
    try:
        req = urllib.request.Request(
            f"{base}/api/stats/ops-llm",
            headers={"X-Ops-Token": token},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {"error": str(e)}


def _compute_retention() -> dict:
    """Estimate D1/D7 retention from daily_login_streaks."""
    today = datetime.now(timezone.utc).date()
    d1_date = (today - timedelta(days=1)).isoformat()
    d7_date = (today - timedelta(days=7)).isoformat()

    # D1: users who logged in yesterday and also the day before
    d1_rows = _query_db(
        "SELECT DISTINCT device_id FROM daily_login_streaks WHERE date = ?",
        (d1_date,),
    )
    d1_prev_rows = _query_db(
        "SELECT DISTINCT device_id FROM daily_login_streaks WHERE date = ?",
        ((today - timedelta(days=2)).isoformat(),),
    )
    d1_users = {r["device_id"] for r in d1_rows}
    d1_prev_users = {r["device_id"] for r in d1_prev_rows}
    d1_retained = len(d1_users & d1_prev_users)
    d1_rate = (d1_retained / len(d1_prev_users) * 100) if d1_prev_users else 0

    # D7: users active in last 7 days who were also active 7-14 days ago
    d7_active = _query_db(
        "SELECT DISTINCT device_id FROM daily_login_streaks WHERE date >= ?",
        (d7_date,),
    )
    d7_prev_start = (today - timedelta(days=14)).isoformat()
    d7_prev_end = (today - timedelta(days=8)).isoformat()
    d7_prev_active = _query_db(
        "SELECT DISTINCT device_id FROM daily_login_streaks WHERE date >= ? AND date <= ?",
        (d7_prev_start, d7_prev_end),
    )
    d7_users = {r["device_id"] for r in d7_active}
    d7_prev_users = {r["device_id"] for r in d7_prev_active}
    d7_retained = len(d7_users & d7_prev_users)
    d7_rate = (d7_retained / len(d7_prev_users) * 100) if d7_prev_users else 0

    return {
        "d1_rate": round(d1_rate, 1),
        "d1_users": d1_retained,
        "d7_rate": round(d7_rate, 1),
        "d7_users": d7_retained,
        "total_active_7d": len(d7_users),
    }


def _db_stats() -> dict:
    """Key database statistics."""
    stats = {}

    # Total chat sessions
    rows = _query_db("SELECT COUNT(*) as cnt FROM chat_sessions")
    stats["total_sessions"] = rows[0]["cnt"] if rows else 0

    # Sessions in last 7 days
    week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    rows = _query_db(
        "SELECT COUNT(*) as cnt FROM chat_sessions WHERE created_at >= ?",
        (week_ago,),
    )
    stats["sessions_7d"] = rows[0]["cnt"] if rows else 0

    # Unique active children (7d)
    rows = _query_db(
        "SELECT COUNT(DISTINCT device_id || '-' || child_id) as cnt "
        "FROM lesson_progress WHERE updated_at >= ?",
        (week_ago,),
    )
    stats["active_children_7d"] = rows[0]["cnt"] if rows else 0

    # Lessons completed (7d)
    rows = _query_db(
        "SELECT COUNT(*) as cnt FROM lesson_progress "
        "WHERE status = 'completed' AND updated_at >= ?",
        (week_ago,),
    )
    stats["lessons_completed_7d"] = rows[0]["cnt"] if rows else 0

    # Total children registered
    rows = _query_db("SELECT COUNT(*) as cnt FROM child_profiles")
    stats["total_children"] = rows[0]["cnt"] if rows else 0

    # Daily logins today
    today = datetime.now(timezone.utc).date().isoformat()
    rows = _query_db(
        "SELECT COUNT(DISTINCT device_id) as cnt FROM daily_login_streaks WHERE date = ?",
        (today,),
    )
    stats["logins_today"] = rows[0]["cnt"] if rows else 0

    return stats


def _format_report(ops: dict, retention: dict, db: dict) -> str:
    """Format the weekly report as a Telegram-friendly message."""
    now = datetime.now(timezone.utc)
    week_start = (now - timedelta(days=7)).strftime("%Y-%m-%d")
    week_end = now.strftime("%Y-%m-%d")

    lines = [
        f"📊 تقرير المربي الأسبوعي",
        f"📅 {week_start} → {week_end}",
        "",
    ]

    # LLM Metrics
    if "error" not in ops:
        lines.append("🤖 مقاييس الذكاء الاصطناعي:")
        lines.append(f"  • p95 latency: {ops.get('p95_ms', 'N/A')}ms")
        lines.append(f"  • Cache hit rate: {ops.get('cache_hit_rate', 'N/A')}%")
        lines.append(f"  • Total calls (7d): {ops.get('calls_7d', 'N/A')}")
        lines.append(f"  • Token usage (month): {ops.get('tokens_month', 'N/A')}")
        lines.append(f"  • DeepSeek valve: {ops.get('valve_usage_pct', 'N/A')}%")
        lines.append("")
    else:
        lines.append(f"🤖 مقاييس LLM: ⚠️ {ops['error']}")
        lines.append("")

    # Retention
    lines.append("📈 الاحتفاظ:")
    lines.append(f"  • D1 retention: {retention['d1_rate']}% ({retention['d1_users']} مستخدم)")
    lines.append(f"  • D7 retention: {retention['d7_rate']}% ({retention['d7_users']} مستخدم)")
    lines.append(f"  • نشطون (7 أيام): {retention['total_active_7d']}")
    lines.append("")

    # DB Stats
    lines.append("📱 إحصائيات التطبيق:")
    lines.append(f"  • جلسات محادثة (7 أيام): {db['sessions_7d']}")
    lines.append(f"  • دروس مكتملة (7 أيام): {db['lessons_completed_7d']}")
    lines.append(f"  • أطفال نشطون (7 أيام): {db['active_children_7d']}")
    lines.append(f"  • إجمالي أطفال مسجلين: {db['total_children']}")
    lines.append(f"  • تسجيلات دخول اليوم: {db['logins_today']}")
    lines.append("")

    lines.append("— المربّي الذكي · مجاني لوجه الله 🤍")

    return "\n".join(lines)


def _send_telegram(token: str, chat_id: str, text: str) -> bool:
    """Send a message via Telegram Bot API."""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
    }).encode()
    try:
        req = urllib.request.Request(url, data=data, method="POST")
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read())
            return result.get("ok", False)
    except Exception as e:
        print(f"Telegram send failed: {e}", file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(description="Weekly dashboard report")
    parser.add_argument("--token", help="Telegram bot token (or env TELEGRAM_BOT_TOKEN)")
    parser.add_argument("--chat-id", help="Telegram chat ID (or env TELEGRAM_CHAT_ID)")
    parser.add_argument("--dry-run", action="store_true", help="Print report without sending")
    args = parser.parse_args()

    token = args.token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = args.chat_id or os.environ.get("TELEGRAM_CHAT_ID", "")

    # Collect metrics
    print("Fetching ops metrics...")
    ops = _fetch_ops_metrics()

    print("Computing retention...")
    retention = _compute_retention()

    print("Collecting DB stats...")
    db = _db_stats()

    # Format report
    report = _format_report(ops, retention, db)

    if args.dry_run:
        print(report)
        return

    # Send to Telegram
    if not token or not chat_id:
        print("Warning: no Telegram credentials, printing report only", file=sys.stderr)
        print(report)
        return

    ok = _send_telegram(token, chat_id, report)
    if ok:
        print("Report sent to Telegram successfully")
    else:
        print("Failed to send report", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
