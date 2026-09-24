#!/usr/bin/env python3
"""Weekly Funnel & Retention Report — measures activation, drop-offs, genuine questions,
and engagement from production SQLite database and reports to Telegram.

Usage (VPS cron, weekly):
    docker exec -w /app tg_backend python ops/scripts/weekly_funnel_report.py

Guarantees:
  1. Privacy: Aggregates only. Zero raw parent question text leaves the server.
  2. Safety: Opens SQLite in read-only mode (?mode=ro).
  3. Real data: Excludes canned suggestions (chatQ_*) and noise (<12 chars).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

_DB = Path(os.environ.get(
    "CONVERSATIONS_DB", str(_ROOT / "ops" / "conversations.db"),
))
_ARB = _ROOT / "mobile" / "lib" / "l10n" / "app_ar.arb"

_TG_LIMIT = 3800
_MIN_CHARS = 12
_TIP_PREFIX = "بخصوص نصيحة اليوم"


def _query(db_path: Path, sql: str, params: tuple = ()) -> list[dict]:
    """Execute read-only SQL query."""
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def _has_table(db_path: Path, table_name: str) -> bool:
    """Check if table exists in database."""
    res = _query(
        db_path,
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?",
        (table_name,),
    )
    return bool(res)


def _normalize(text: str) -> str:
    """Normalize text: strip tatweel, diacritics, and normalize whitespace."""
    t = re.sub(r"[ـً-ْ]", "", text or "")
    return " ".join(t.split()).strip()


def load_suggested_questions(arb_path: Path) -> set[str]:
    """Load normalized chatQ_* strings from Arabic arb file."""
    if not arb_path.exists():
        return set()
    try:
        with open(arb_path, encoding="utf-8") as fh:
            arb = json.load(fh)
        return {
            _normalize(v) for k, v in arb.items()
            if k.startswith("chatQ") and isinstance(v, str)
        }
    except Exception:
        return set()


def get_funnel_metrics(db_path: Path, days: int, suggested: set[str]) -> dict:
    """Measure the weekly cohort funnel progression by device_id."""
    window_param = f"-{days} days"

    # Cohort: devices whose first child profile was created in this window
    cohort_rows = _query(
        db_path,
        """WITH cohort AS (
             SELECT device_id, MIN(created_at) AS first_created
             FROM child_profiles
             GROUP BY device_id
             HAVING first_created >= datetime('now', ?)
           )
           SELECT device_id, first_created FROM cohort""",
        (window_param,),
    )
    cohort_devices = {r["device_id"] for r in cohort_rows}
    cohort_size = len(cohort_devices)

    if not cohort_devices:
        return {
            "cohort_size": 0,
            "started_lesson": 0,
            "completed_lesson": 0,
            "asked_question": 0,
            "started_pct": 0.0,
            "completed_pct": 0.0,
            "asked_pct": 0.0,
        }

    placeholders = ",".join("?" for _ in cohort_devices)
    dev_params = tuple(cohort_devices)

    # 1. Started a lesson
    started_rows = _query(
        db_path,
        f"""SELECT DISTINCT device_id FROM lesson_progress
            WHERE device_id IN ({placeholders})
              AND (status IN ('in_progress', 'completed') OR started_at IS NOT NULL)""",
        dev_params,
    )
    started_devices = {r["device_id"] for r in started_rows}

    # 2. Completed a lesson
    completed_rows = _query(
        db_path,
        f"""SELECT DISTINCT device_id FROM lesson_progress
            WHERE device_id IN ({placeholders})
              AND (status = 'completed' OR completed_at IS NOT NULL)""",
        dev_params,
    )
    completed_devices = {r["device_id"] for r in completed_rows}

    # 3. Asked a genuine question
    msg_rows = _query(
        db_path,
        f"""SELECT cs.device_id, cm.content
            FROM chat_sessions cs
            JOIN chat_messages cm ON cm.session_id = cs.id
            WHERE cs.device_id IN ({placeholders})
              AND cm.role = 'user'""",
        dev_params,
    )
    asked_devices = set()
    for r in msg_rows:
        norm = _normalize(r["content"])
        if norm not in suggested and len(norm) >= _MIN_CHARS:
            asked_devices.add(r["device_id"])

    return {
        "cohort_size": cohort_size,
        "started_lesson": len(started_devices),
        "completed_lesson": len(completed_devices),
        "asked_question": len(asked_devices),
        "started_pct": (len(started_devices) / cohort_size * 100) if cohort_size else 0.0,
        "completed_pct": (len(completed_devices) / cohort_size * 100) if cohort_size else 0.0,
        "asked_pct": (len(asked_devices) / cohort_size * 100) if cohort_size else 0.0,
    }


def get_retention_metrics(db_path: Path) -> dict:
    """Measure Day-7 retention for cohort from [now - 14d, now - 7d]."""
    prev_cohort_rows = _query(
        db_path,
        """WITH cohort_prev AS (
             SELECT device_id, MIN(created_at) AS first_created
             FROM child_profiles
             GROUP BY device_id
             HAVING first_created >= datetime('now', '-14 days')
                AND first_created < datetime('now', '-7 days')
           )
           SELECT device_id, first_created FROM cohort_prev""",
    )
    cohort_size = len(prev_cohort_rows)
    if not cohort_size:
        return {"prev_cohort_size": 0, "returned_d7": 0, "d7_retention_pct": 0.0}

    returned_d7 = 0
    has_streaks = _has_table(db_path, "daily_login_streaks")
    streak_clause = "SELECT 1 FROM daily_login_streaks WHERE device_id = ? AND date >= date(?, '+7 days')" if has_streaks else "SELECT 0 WHERE 1=0"

    for r in prev_cohort_rows:
        dev_id = r["device_id"]
        fc = r["first_created"]
        # Check activity >= 7 days after first creation
        params = [dev_id, fc] if has_streaks else []
        params.extend([dev_id, fc, dev_id, fc, fc])
        active = _query(
            db_path,
            f"""SELECT 1 WHERE EXISTS (
                 {streak_clause}
               ) OR EXISTS (
                 SELECT 1 FROM chat_sessions cs
                 JOIN chat_messages cm ON cm.session_id = cs.id
                 WHERE cs.device_id = ? AND cm.created_at >= datetime(?, '+7 days')
               ) OR EXISTS (
                 SELECT 1 FROM lesson_progress
                 WHERE device_id = ?
                   AND (updated_at >= datetime(?, '+7 days') OR completed_at >= datetime(?, '+7 days'))
               )""",
            tuple(params),
        )
        if active:
            returned_d7 += 1

    return {
        "prev_cohort_size": cohort_size,
        "returned_d7": returned_d7,
        "d7_retention_pct": (returned_d7 / cohort_size * 100) if cohort_size else 0.0,
    }


def get_questions_and_quality(db_path: Path, days: int, suggested: set[str]) -> dict:
    """Analyze real parent questions, domains, and unanswered rate."""
    window = f"-{days} days"

    # All user messages in window
    raw_msgs = _query(
        db_path,
        """SELECT id, session_id, content, domain, created_at
           FROM chat_messages
           WHERE role = 'user' AND created_at >= datetime('now', ?)
           ORDER BY id""",
        (window,),
    )

    n_total = len(raw_msgs)
    n_suggested = 0
    n_short = 0
    n_tip_initiated = 0
    genuine = []

    for m in raw_msgs:
        content = m["content"] or ""
        norm = _normalize(content)
        if norm.startswith(_TIP_PREFIX):
            n_tip_initiated += 1
        if norm in suggested:
            n_suggested += 1
            continue
        if len(norm) < _MIN_CHARS:
            n_short += 1
            continue
        genuine.append(m)

    # Unanswered stats (orphans + degraded)
    orphans_row = _query(
        db_path,
        """WITH m AS (
             SELECT id, session_id, role, created_at,
                    LEAD(role) OVER (PARTITION BY session_id ORDER BY id) AS next_role
             FROM chat_messages
             WHERE created_at >= datetime('now', ?)
           )
           SELECT COUNT(*) n FROM m
           WHERE role='user' AND (next_role IS NULL OR next_role='user')""",
        (window,),
    )
    orphans = orphans_row[0]["n"] if orphans_row else 0

    modes = _query(
        db_path,
        """SELECT mode, COUNT(*) n FROM chat_messages
           WHERE role = 'assistant' AND created_at >= datetime('now', ?)
           GROUP BY mode""",
        (window,),
    )
    degraded = sum(m["n"] for m in modes if m["mode"] in ("error", "interrupted"))
    unanswered_rate = ((orphans + degraded) / n_total * 100) if n_total else 0.0

    domain_counts = Counter(m["domain"] or "عام" for m in genuine)

    return {
        "total_user_messages": n_total,
        "suggested_dropped": n_suggested,
        "short_dropped": n_short,
        "genuine_questions": len(genuine),
        "tip_initiated_count": n_tip_initiated,
        "orphans": orphans,
        "degraded": degraded,
        "unanswered_rate": unanswered_rate,
        "top_domains": domain_counts.most_common(5),
    }


def get_coach_tips_metrics(db_path: Path, days: int) -> dict:
    """Measure coach tips engagement."""
    if not _has_table(db_path, "coach_tips"):
        return {"tips_generated": 0, "tips_shown": 0, "tips_tapped": 0, "tips_ctr": 0.0}

    window = f"-{days} days"
    rows = _query(
        db_path,
        """SELECT COUNT(*) AS total,
                  COUNT(shown_at) AS shown,
                  COUNT(tapped_at) AS tapped
           FROM coach_tips
           WHERE created_at >= datetime('now', ?)""",
        (window,),
    )
    r = rows[0] if rows else {"total": 0, "shown": 0, "tapped": 0}
    total = r["total"] or 0
    shown = r["shown"] or 0
    tapped = r["tapped"] or 0
    ctr = (tapped / shown * 100) if shown else 0.0

    return {
        "tips_generated": total,
        "tips_shown": shown,
        "tips_tapped": tapped,
        "tips_ctr": ctr,
    }


def get_feedback_metrics(db_path: Path, days: int) -> dict:
    """Gather user feedback & app feedback counts in lookback window."""
    window = f"-{days} days"
    ratings = {}
    if _has_table(db_path, "user_feedback"):
        uf_rows = _query(
            db_path,
            """SELECT rating, COUNT(*) n
               FROM user_feedback
               WHERE created_at >= datetime('now', ?)
               GROUP BY rating""",
            (window,),
        )
        ratings = {r["rating"]: r["n"] for r in uf_rows}

    total_af = 0
    voice_notes = 0
    if _has_table(db_path, "app_feedback"):
        af_rows = _query(
            db_path,
            """SELECT COUNT(*) total,
                      COUNT(audio_file) AS voice_notes
               FROM app_feedback
               WHERE created_at >= datetime('now', ?)""",
            (window,),
        )
        if af_rows:
            total_af = af_rows[0]["total"] or 0
            voice_notes = af_rows[0]["voice_notes"] or 0

    return {
        "ratings": ratings,
        "total_app_feedback": total_af,
        "voice_notes": voice_notes,
    }


def format_report(days: int, funnel: dict, ret: dict, qm: dict, tips: dict, fb: dict) -> str:
    """Format metrics into a concise, readable HTML Telegram message."""
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    lines = [
        f"📊 <b>تقرير مسار التفعيل والأداء الأسبوعي — المربّي</b>",
        f"📅 <i>آخر {days} أيام (تاريخ التقرير: {now_str})</i>",
        "",
        "🎯 <b>مسار التفعيل (Activation Funnel لكوهورت الأسبوع):</b>",
        f"  1️⃣ تثبيت وتسجيل طفل: <b>{funnel['cohort_size']}</b> جهاز (100%)",
        f"  2️⃣ بدأ أول درس: <b>{funnel['started_lesson']}</b> جهاز ({funnel['started_pct']:.1f}%)",
        f"  3️⃣ أتمّ درساً كاملاً: <b>{funnel['completed_lesson']}</b> جهاز ({funnel['completed_pct']:.1f}%)",
        f"  4️⃣ سأل سؤالاً حقيقياً: <b>{funnel['asked_question']}</b> جهاز ({funnel['asked_pct']:.1f}%)",
    ]

    # Leakage analysis
    if funnel["cohort_size"] > 0:
        c0 = funnel["cohort_size"]
        c1 = funnel["started_lesson"]
        drop_install_lesson = ((c0 - c1) / c0 * 100) if c0 else 0
        lines.append(f"  ⚠️ <i>تسريب التهيئة ← أول درس: {drop_install_lesson:.1f}%</i>")

    lines.extend([
        "",
        "🔄 <b>الاحتفاظ باليوم السابع (D7 Retention — كوهورت الأسبوع السابق):</b>",
        f"  • أجهزة الكوهورت السابق: <b>{ret['prev_cohort_size']}</b>",
        f"  • عادت بعد 7 أيام: <b>{ret['returned_d7']}</b> ({ret['d7_retention_pct']:.1f}%)",
        "",
        "💬 <b>الأسئلة الحقيقية للأهالي:</b>",
        f"  • إجمالي رسائل المستخدمين: {qm['total_user_messages']}",
        f"  • مستبعد (أزرار جاهزة): {qm['suggested_dropped']} | نقر عشوائي/تحية: {qm['short_dropped']}",
        f"  • <b>الأسئلة الحقيقية: {qm['genuine_questions']}</b>",
        f"  • أسئلة انطلقت من نصيحة اليوم: {qm['tip_initiated_count']}",
        f"  • نسبة الأسئلة غير المخدومة: <b>{qm['unanswered_rate']:.1f}%</b> ({qm['orphans']} معلّقة + {qm['degraded']} تعثر)",
    ])

    if qm["top_domains"]:
        lines.append("  • أبرز المجالات: " + " · ".join(f"{d} ({n})" for d, n in qm["top_domains"]))

    lines.extend([
        "",
        "💡 <b>تفاعل نصيحة اليوم (Coach Tips):</b>",
        f"  • عُرضت في التطبيق: {tips['tips_shown']} | نُقرت: {tips['tips_tapped']}",
        f"  • معدل النقر (CTR): <b>{tips['tips_ctr']:.1f}%</b>",
        "",
        "📝 <b>آراء الأهالي وملاحظاتهم (Feedback):</b>",
    ])

    if fb["ratings"]:
        ratings_str = " · ".join(f"{k}: {v}" for k, v in fb["ratings"].items())
        lines.append(f"  • تقييمات الإجابات: {ratings_str}")
    else:
        lines.append("  • تقييمات الإجابات: لا يوجد تقييمات مسجلة")

    lines.append(f"  • شكاوى التطبيق: {fb['total_app_feedback']} (منها {fb['voice_notes']} رسائل صوتية)")
    lines.append("")
    lines.append("<i>مخرجات تجميعية فقط — بيانات الأهالي لا تغادر السيرفر.</i>")

    return "\n".join(lines)


def _chunk(text: str, limit: int = _TG_LIMIT) -> list[str]:
    chunks, cur = [], ""
    for line in text.split("\n"):
        if len(cur) + len(line) + 1 > limit:
            chunks.append(cur.rstrip())
            cur = ""
        cur += line + "\n"
    if cur.strip():
        chunks.append(cur.rstrip())
    return chunks or [""]


def send_telegram(token: str, chat_id: str, text: str) -> bool:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    ok_all = True
    for part in _chunk(text):
        data = urllib.parse.urlencode({
            "chat_id": chat_id, "text": part, "parse_mode": "HTML",
        }).encode()
        try:
            req = urllib.request.Request(url, data=data, method="POST")
            with urllib.request.urlopen(req, timeout=15) as resp:
                body = json.loads(resp.read())
            if body.get("ok"):
                mid = (body.get("result") or {}).get("message_id")
                print(f"  tg_message_id={mid}")
            else:
                print(f"  Telegram rejected: {body.get('description')}", file=sys.stderr)
                ok_all = False
        except Exception as e:
            print(f"Telegram send failed: {e}", file=sys.stderr)
            ok_all = False
    return ok_all


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Weekly Funnel & Retention Report")
    ap.add_argument("--days", type=int, default=7, help="Lookback window in days (default: 7)")
    ap.add_argument("--db", default=str(_DB), help="Path to conversations.db")
    ap.add_argument("--arb", default=str(_ARB), help="Path to app_ar.arb")
    ap.add_argument("--token", help="Telegram bot token (or env TELEGRAM_BOT_TOKEN)")
    ap.add_argument("--chat-id", help="Telegram chat ID (or env TELEGRAM_CHAT_ID)")
    ap.add_argument("--dry-run", action="store_true", help="Print report to stdout without sending")
    args = ap.parse_args(argv)

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"Error: Database file {db_path} does not exist", file=sys.stderr)
        return 1

    arb_path = Path(args.arb)
    suggested = load_suggested_questions(arb_path)
    print(f"Loaded {len(suggested)} suggested questions for filtering.")

    print(f"Analyzing weekly funnel (last {args.days} days)...")
    funnel = get_funnel_metrics(db_path, args.days, suggested)
    ret = get_retention_metrics(db_path)
    qm = get_questions_and_quality(db_path, args.days, suggested)
    tips = get_coach_tips_metrics(db_path, args.days)
    fb = get_feedback_metrics(db_path, args.days)

    report = format_report(args.days, funnel, ret, qm, tips, fb)

    if args.dry_run:
        print("\n" + report)
        return 0

    token = args.token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = args.chat_id or os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        print("Warning: No Telegram credentials found, printing report to stdout", file=sys.stderr)
        print("\n" + report)
        return 0

    if send_telegram(token, chat_id, report):
        print("Weekly funnel report sent to Telegram successfully.")
        return 0
    print("Failed to send report to Telegram.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
