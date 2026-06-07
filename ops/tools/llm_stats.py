#!/usr/bin/env python3
"""
LLM Call Stats — تقرير من sessions.db

Reads the ops/sessions.db (llm_calls table) and prints summary stats.
Useful for monitoring fallback rates, latency, and error rates.

Usage:
    python ops/tools/llm_stats.py
    python ops/tools/llm_stats.py --days 7
    python ops/tools/llm_stats.py --json
"""
import argparse
import json
import sqlite3
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = PROJECT_ROOT / "ops" / "sessions.db"
DEFAULT_CONV_DB = PROJECT_ROOT / "ops" / "conversations.db"


def format_duration(seconds: float) -> str:
    if seconds < 1:
        return f"{seconds * 1000:.0f}ms"
    if seconds < 60:
        return f"{seconds:.1f}s"
    return f"{seconds / 60:.1f}m"


def _where(days: int | None) -> tuple[str, str, str, str]:
    """Build WHERE clauses for total/ok/fail queries."""
    if days:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        base = f"WHERE created_at >= '{cutoff}'"
        return base, f"{base} AND ok=1", f"{base} AND ok=0", base
    return "", "WHERE ok=1", "WHERE ok=0", ""


def load_stats(db_path: Path, days: int | None = None) -> dict:
    """Load and aggregate LLM call stats from sessions.db."""
    if not db_path.exists():
        return {"error": f"DB not found: {db_path}"}

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='llm_calls'"
    ).fetchall()
    if not tables:
        conn.close()
        return {"error": "No llm_calls table in DB — no LLM calls recorded yet."}

    try:
        total_where, ok_where, fail_where, model_where = _where(days)

        # Total stats
        total = conn.execute(f"SELECT COUNT(*) as c FROM llm_calls {total_where}").fetchone()["c"]
        ok_count = conn.execute(f"SELECT COUNT(*) as c FROM llm_calls {ok_where}").fetchone()["c"]
        fail_count = conn.execute(f"SELECT COUNT(*) as c FROM llm_calls {fail_where}").fetchone()["c"]

        # Latency stats (successful calls only)
        latencies = conn.execute(
            f"SELECT latency_ms FROM llm_calls {ok_where}"
        ).fetchall()
        lat_vals = [r["latency_ms"] for r in latencies if r["latency_ms"] is not None]

        # Model usage
        models = conn.execute(
            f"SELECT model, COUNT(*) as c FROM llm_calls {model_where} GROUP BY model ORDER BY c DESC"
        ).fetchall()

        # Error count (by provider)
        errors_raw = conn.execute(
            f"SELECT provider, COUNT(*) as c FROM llm_calls {fail_where} GROUP BY provider ORDER BY c DESC"
        ).fetchall()

        conn.close()

        avg_lat = sum(lat_vals) / len(lat_vals) if lat_vals else 0
        max_lat = max(lat_vals) if lat_vals else 0
        p95 = sorted(lat_vals)[int(len(lat_vals) * 0.95)] if len(lat_vals) >= 20 else max_lat

        return {
            "total_calls": total,
            "ok": ok_count,
            "failed": fail_count,
            "success_rate": f"{ok_count / total * 100:.1f}%" if total > 0 else "N/A",
            "avg_latency_ms": round(avg_lat, 1),
            "p95_latency_ms": round(p95, 1) if lat_vals else 0,
            "max_latency_ms": round(max_lat, 1) if lat_vals else 0,
            "models": {r["model"]: r["c"] for r in models},
            "fallback_rate": f"{(fail_count / total * 100):.1f}%" if total > 0 else "N/A",
            "errors": {r["provider"]: r["c"] for r in errors_raw},
        }
    except Exception as e:
        conn.close()
        return {"error": str(e)}


def load_feedback_stats(db_path: Path, days: int | None = None) -> dict:
    """Load 👍/👎 feedback stats from conversations.db."""
    if not db_path.exists():
        return {"error": f"DB not found: {db_path}"}

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='user_feedback'"
    ).fetchall()
    if not tables:
        conn.close()
        return {"error": "No user_feedback table yet — no feedback submitted."}

    try:
        where = ""
        if days:
            cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
            where = f"WHERE created_at >= '{cutoff}'"

        total = conn.execute(f"SELECT COUNT(*) as c FROM user_feedback {where}").fetchone()["c"]
        up = conn.execute(f"SELECT COUNT(*) as c FROM user_feedback {where} {'AND' if where else 'WHERE'} rating='up'").fetchone()["c"]
        down = total - up
        comments = conn.execute(
            f"SELECT comment FROM user_feedback {where} {'AND' if where else 'WHERE'} comment IS NOT NULL AND comment != '' ORDER BY id DESC LIMIT 10"
        ).fetchall()
        conn.close()
        return {
            "total": total,
            "up": up,
            "down": down,
            "satisfaction": f"{up / total * 100:.1f}%" if total > 0 else "N/A",
            "recent_comments": [r["comment"] for r in comments],
        }
    except Exception as e:
        conn.close()
        return {"error": str(e)}


def main():
    parser = argparse.ArgumentParser(description="LLM call stats from sessions.db")
    parser.add_argument("--db", default=str(DEFAULT_DB), help=f"Path to sessions.db (default: {DEFAULT_DB})")
    parser.add_argument("--conv-db", default=str(DEFAULT_CONV_DB), help=f"Path to conversations.db for feedback (default: {DEFAULT_CONV_DB})")
    parser.add_argument("--days", type=int, help="Filter to last N days")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    stats = load_stats(Path(args.db), args.days)
    feedback = load_feedback_stats(Path(args.conv_db), args.days)

    if args.json:
        print(json.dumps({"llm": stats, "feedback": feedback}, ensure_ascii=False, indent=2))
        return

    if "error" in stats:
        print(f"❌ LLM stats: {stats['error']}")
    else:
        print("=" * 60)
        print(f"  📊  LLM Call Statistics{' (last ' + str(args.days) + ' days)' if args.days else ' (all time)'}")
        print("=" * 60)
        print(f"  Total calls : {stats['total_calls']}")
        print(f"  ✅ Success  : {stats['ok']}  ({stats['success_rate']})")
        print(f"  ❌ Failed   : {stats['failed']}  (fallback rate: {stats['fallback_rate']})")
        print()
        print(f"  ⏱  Latency (successful calls):")
        print(f"      Average : {format_duration(stats['avg_latency_ms'] / 1000)}")
        print(f"      P95     : {format_duration(stats['p95_latency_ms'] / 1000)}")
        print(f"      Max     : {format_duration(stats['max_latency_ms'] / 1000)}")
        print()
        print(f"  🏷  Models used:")
        for model, count in stats["models"].items():
            print(f"      {model}: {count}")
        print()
        if stats["errors"]:
            print(f"  ⚠️  Errors:")
            for err, count in stats["errors"].items():
                print(f"      {err}: {count}")

    print()
    if "error" in feedback:
        print(f"  💬 Feedback: {feedback['error']}")
    else:
        print("=" * 60)
        print(f"  💬  User Feedback{' (last ' + str(args.days) + ' days)' if args.days else ' (all time)'}")
        print("=" * 60)
        print(f"  Total ratings : {feedback['total']}")
        print(f"  👍 Up         : {feedback['up']}")
        print(f"  👎 Down       : {feedback['down']}")
        print(f"  Satisfaction  : {feedback['satisfaction']}")
        if feedback["recent_comments"]:
            print()
            print("  Recent comments:")
            for c in feedback["recent_comments"]:
                print(f"    - {c}")


if __name__ == "__main__":
    main()
