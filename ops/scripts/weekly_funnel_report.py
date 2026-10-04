#!/usr/bin/env python3
"""Weekly Funnel & Retention Report — measures activation, drop-offs, genuine questions,
and engagement from production SQLite database and reports to Telegram.

Usage (VPS cron, weekly):
    docker exec -w /app tg_backend python ops/scripts/weekly_funnel_report.py

Guarantees:
  1. Privacy: Aggregates only. Zero raw parent question text leaves the server.
  2. Safety: Opens SQLite in read-only mode (?mode=ro).
  3. Real data: Excludes canned suggestions (chatQ_*) and noise (<12 chars).

What each headline number measures (2026-10-04 rework):
  • North Star — weekly active families: distinct devices with at least one
    meaningful action in a 7-day window. An action is a question to the
    assistant, a lesson started/progressed/completed, a habit check-in, a
    child-mode mission (assigned when the child opens it, claimed, confirmed)
    or a challenge started. Opening the app is NOT an action.
  • Openers — a PROXY for "opened the app": devices that fetched the daily
    coach tip (the Home screen requests it once per device/child/day). There
    is no direct app-open table: `daily_login_streaks` was meant to be one and
    had zero rows in production because its INSERT was never committed.
  • Cohort retention — cohort = week of a device's FIRST child profile. Each
    metric only counts devices old enough to be measured (eligible); a cohort
    still inside its window shows "—" rather than a fake 0.
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
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

_DB = Path(os.environ.get(
    "CONVERSATIONS_DB", str(_ROOT / "ops" / "conversations.db"),
))
# Telemetry DB written by the assistant (llm_calls, sessions). Optional: the
# report degrades to conversations.db-only numbers when it is absent.
_SESSIONS_DB = Path(os.environ.get(
    "SESSIONS_DB", str(_DB.parent / "sessions.db"),
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


def _columns(db_path: Path, table_name: str) -> set[str]:
    """Live column names — production schema can differ from init_db."""
    return {r["name"] for r in _query(db_path, f"PRAGMA table_info({table_name})")}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _parse_ts(value: str | None) -> datetime | None:
    """`datetime()`-normalised SQLite text → naive UTC datetime."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


# ── Meaningful family actions (the North Star's numerator) ──────────────
# (table, timestamp column, extra WHERE). Timestamps go through SQLite's
# datetime() because the tables disagree on format: chat rows use
# "YYYY-MM-DD HH:MM:SS", missions and feedback write ISO-8601 with a "T" and
# an offset — compared as raw strings, those sort wrongly within a day.
_ACTION_SOURCES: tuple[tuple[str, str, str], ...] = (
    ("lesson_progress", "started_at", ""),
    ("lesson_progress", "updated_at", ""),
    ("lesson_progress", "completed_at", ""),
    ("habits_value_events", "created_at", ""),
    ("child_missions", "assigned_at", ""),
    ("child_missions", "claimed_at", ""),
    ("child_missions", "confirmed_at", ""),
    ("child_challenges", "started_at", ""),
)


def get_action_events(db_path: Path, since: datetime) -> list[tuple[str, datetime]]:
    """Every meaningful action since `since` as (device_id, utc timestamp).

    A question is a user row in chat_messages joined to its session's device.
    Tables or columns missing from this database are skipped, not fatal.
    """
    cutoff = since.strftime("%Y-%m-%d %H:%M:%S")
    events: list[tuple[str, datetime]] = []

    if _has_table(db_path, "chat_messages") and _has_table(db_path, "chat_sessions"):
        for r in _query(
            db_path,
            """SELECT cs.device_id AS device_id, datetime(cm.created_at) AS ts
               FROM chat_messages cm JOIN chat_sessions cs ON cs.id = cm.session_id
               WHERE cm.role = 'user' AND cs.device_id IS NOT NULL
                 AND datetime(cm.created_at) >= ?""",
            (cutoff,),
        ):
            ts = _parse_ts(r["ts"])
            if ts is not None:
                events.append((r["device_id"], ts))

    cols_cache: dict[str, set[str]] = {}
    for table, col, extra in _ACTION_SOURCES:
        if table not in cols_cache:
            cols_cache[table] = _columns(db_path, table) if _has_table(db_path, table) else set()
        if col not in cols_cache[table] or "device_id" not in cols_cache[table]:
            continue
        for r in _query(
            db_path,
            f"""SELECT device_id, datetime({col}) AS ts FROM {table}
                WHERE {col} IS NOT NULL AND datetime({col}) >= ? {extra}""",
            (cutoff,),
        ):
            ts = _parse_ts(r["ts"])
            if ts is not None:
                events.append((r["device_id"], ts))
    return events


def _week_windows(now: datetime, weeks: int) -> list[tuple[datetime, datetime]]:
    """Rolling 7-day windows ending at `now`; index 0 is the latest week."""
    return [(now - timedelta(days=7 * (k + 1)), now - timedelta(days=7 * k))
            for k in range(weeks)]


def get_north_star(db_path: Path, weeks: int = 5, now: datetime | None = None) -> list[dict]:
    """Weekly active families for the latest `weeks` rolling weeks (newest first)."""
    now = now or _utcnow()
    windows = _week_windows(now, weeks)
    events = get_action_events(db_path, windows[-1][0])
    out = []
    for start, end in windows:
        families = {d for d, ts in events if start <= ts < end}
        out.append({"start": start.date().isoformat(),
                    "end": end.date().isoformat(),
                    "families": len(families)})
    return out


def get_openers(db_path: Path, weeks: int = 5, now: datetime | None = None) -> list[dict]:
    """PROXY for app opens: devices that fetched a daily coach tip, per week."""
    now = now or _utcnow()
    if not _has_table(db_path, "coach_tips"):
        return [{"start": s.date().isoformat(), "end": e.date().isoformat(), "devices": 0}
                for s, e in _week_windows(now, weeks)]
    today = now.date()
    out = []
    for k in range(weeks):
        # Calendar days (today-7k-6 .. today-7k]; coach_tips.date is a UTC day.
        last = today - timedelta(days=7 * k)
        first = last - timedelta(days=6)
        row = _query(
            db_path,
            "SELECT COUNT(DISTINCT device_id) AS n FROM coach_tips WHERE date BETWEEN ? AND ?",
            (first.isoformat(), last.isoformat()),
        )
        out.append({"start": first.isoformat(), "end": last.isoformat(),
                    "devices": row[0]["n"] if row else 0})
    return out


def _open_days(db_path: Path, since: date, action_events) -> dict[str, set[date]]:
    """Days each device is known to have had the app open.

    Union of: a coach tip fetched that day (Home loaded), any meaningful action
    that day, and — once it has data — a daily_login_streaks row.
    """
    days: dict[str, set[date]] = defaultdict(set)
    for table in ("coach_tips", "daily_login_streaks"):
        if not _has_table(db_path, table):
            continue
        for r in _query(
            db_path,
            f"SELECT DISTINCT device_id, date FROM {table} WHERE date >= ?",
            (since.isoformat(),),
        ):
            try:
                days[r["device_id"]].add(date.fromisoformat(r["date"]))
            except (TypeError, ValueError):
                continue
    for dev, ts in action_events:
        days[dev].add(ts.date())
    return days


# (label, first day, last day, signal) — days counted from the first child
# profile's UTC date (day 0). "open" = any open signal, "action" = a
# meaningful action only.
_COHORT_METRICS: tuple[tuple[str, int, int, str], ...] = (
    ("d1_open", 1, 1, "open"),
    ("d7_open", 7, 13, "open"),
    ("d7_action", 7, 13, "action"),
    ("d30_open", 30, 36, "open"),
)


def get_cohort_retention(db_path: Path, cohorts: int = 6,
                         now: datetime | None = None) -> list[dict]:
    """Retention per weekly signup cohort (Monday-aligned), newest first.

    Cohort = week of the device's first child profile. A device is eligible
    for a metric only once its whole window (e.g. days 7–13) is in the past,
    so a young cohort reports n/eligible honestly instead of a deflated rate.
    """
    now = now or _utcnow()
    today = now.date()
    this_monday = today - timedelta(days=today.weekday())
    oldest_monday = this_monday - timedelta(weeks=cohorts)

    if not _has_table(db_path, "child_profiles"):
        return []
    firsts = _query(
        db_path,
        """SELECT device_id, MIN(datetime(created_at)) AS first_created
           FROM child_profiles GROUP BY device_id
           HAVING MIN(datetime(created_at)) >= ? AND MIN(datetime(created_at)) < ?""",
        (oldest_monday.isoformat(), this_monday.isoformat()),
    )
    if not firsts:
        return [{"week": (oldest_monday + timedelta(weeks=i)).isoformat(), "size": 0,
                 **{m[0]: (0, 0) for m in _COHORT_METRICS}}
                for i in reversed(range(cohorts))]

    events = get_action_events(db_path, datetime.combine(oldest_monday, datetime.min.time()))
    action_days: dict[str, set[date]] = defaultdict(set)
    for dev, ts in events:
        action_days[dev].add(ts.date())
    open_days = _open_days(db_path, oldest_monday, events)

    by_week: dict[date, list[tuple[str, date]]] = defaultdict(list)
    for r in firsts:
        ts = _parse_ts(r["first_created"])
        if ts is None:
            continue
        d0 = ts.date()
        by_week[d0 - timedelta(days=d0.weekday())].append((r["device_id"], d0))

    out = []
    for i in reversed(range(cohorts)):
        monday = oldest_monday + timedelta(weeks=i)
        members = by_week.get(monday, [])
        row: dict = {"week": monday.isoformat(), "size": len(members)}
        for label, lo, hi, signal in _COHORT_METRICS:
            hit = eligible = 0
            for dev, d0 in members:
                if d0 + timedelta(days=hi) >= today:
                    continue  # window not over yet — not measurable
                eligible += 1
                pool = open_days.get(dev, set()) if signal == "open" else action_days.get(dev, set())
                if any(d0 + timedelta(days=k) in pool for k in range(lo, hi + 1)):
                    hit += 1
            row[label] = (hit, eligible)
        out.append(row)
    return out


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


def count_orphans(rows) -> int:
    """Questions left with no reply of their own.

    `rows` are (session_id, role) in message order within each session. A
    reply answers the oldest still-unanswered question of its session, so a
    parent who asks again before the first answer is saved — Q1, Q2, A1, A2 —
    leaves no orphan. The old rule ("the next row is not a reply") counted Q1
    as unanswered; with answers now finished after the reader leaves, that
    ordering is routine, not rare.
    """
    pending: Counter = Counter()
    for row in rows:
        session_id, role = (row["session_id"], row["role"]) if isinstance(row, dict) else row
        if role == "user":
            pending[session_id] += 1
        elif role == "assistant" and pending[session_id]:
            pending[session_id] -= 1
    return sum(pending.values())


def get_questions_and_quality(db_path: Path, days: int, suggested: set[str],
                              sessions_db: Path | None = None) -> dict:
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
    orphans = count_orphans(_query(
        db_path,
        """SELECT session_id, role FROM chat_messages
           WHERE created_at >= datetime('now', ?)
           ORDER BY session_id, id""",
        (window,),
    ))

    modes = _query(
        db_path,
        """SELECT mode, COUNT(*) n FROM chat_messages
           WHERE role = 'assistant' AND created_at >= datetime('now', ?)
           GROUP BY mode""",
        (window,),
    )
    by_mode = {m["mode"]: m["n"] for m in modes}
    # Three different failures, reported apart because they have different
    # owners: `interrupted` = the stream was cut after the parent saw part of
    # the answer (the app left/stopped — client side); `error` = the server
    # gave up (timeout, provider down, pipeline exception); an orphan = no
    # reply row at all (the parent left before the first word, or a stall).
    interrupted = by_mode.get("interrupted", 0)
    errors = by_mode.get("error", 0)
    degraded = interrupted + errors
    unanswered_rate = ((orphans + degraded) / n_total * 100) if n_total else 0.0

    domain_counts = Counter(m["domain"] or "عام" for m in genuine)

    return {
        "total_user_messages": n_total,
        "suggested_dropped": n_suggested,
        "short_dropped": n_short,
        "genuine_questions": len(genuine),
        "tip_initiated_count": n_tip_initiated,
        "orphans": orphans,
        "interrupted": interrupted,
        "errors": errors,
        "degraded": degraded,
        "unanswered_rate": unanswered_rate,
        "stream_outcomes": get_stream_outcomes(sessions_db, days) if sessions_db else {},
        "top_domains": domain_counts.most_common(5),
    }


# Flags the assistant writes to sessions.db (`sessions.flag`) for turns that
# end without an answer — see assistant._OUTCOME_FLAGS.
_OUTCOME_FLAGS = (
    "client_left_before_first_token",
    "first_token_timeout",
    "stream_stalled",
    "stream_error",
    "pipeline_error",
    # Not a failure: the parent left mid-answer and the server finished and
    # stored it anyway — the app shows it when the conversation is reopened.
    "completed_after_disconnect",
)


def get_stream_outcomes(sessions_db: Path, days: int) -> dict[str, int]:
    """Counts of unanswered-turn causes recorded by the assistant itself.

    Only the SSE path writes these flags (cron jobs that call the pipeline do
    not), so they describe parents' questions. Empty before the 2026-10 deploy.
    """
    if not sessions_db.exists() or not _has_table(sessions_db, "sessions"):
        return {}
    rows = _query(
        sessions_db,
        """SELECT flag, COUNT(*) AS n FROM sessions
           WHERE datetime(ts) >= datetime('now', ?) AND flag IS NOT NULL AND flag != ''
           GROUP BY flag""",
        (f"-{days} days",),
    )
    out = {f: 0 for f in _OUTCOME_FLAGS}
    for r in rows:
        key = (r["flag"] or "").split(":", 1)[0]
        if key in out:
            out[key] += r["n"]
    return out


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
               WHERE datetime(created_at) >= datetime('now', ?)
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
               WHERE datetime(created_at) >= datetime('now', ?)""",
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


def _pct(hit: int, eligible: int) -> str:
    return f"{hit / eligible * 100:.0f}%" if eligible else "—"


def format_report(days: int, north: list[dict], openers: list[dict], cohorts: list[dict],
                  funnel: dict, qm: dict, tips: dict, fb: dict) -> str:
    """Format metrics into a concise, readable HTML Telegram message."""
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    lines = [
        f"📊 <b>تقرير مسار التفعيل والأداء الأسبوعي — المربّي</b>",
        f"📅 <i>آخر {days} أيام (تاريخ التقرير: {now_str})</i>",
        "",
    ]

    if north:
        prev = " · ".join(str(w["families"]) for w in north[1:])
        lines.extend([
            "⭐ <b>النجم الشمالي — أسر نشطة أسبوعيًا:</b>",
            f"  • هذا الأسبوع: <b>{north[0]['families']}</b> أسرة"
            + (f" | الأسابيع السابقة (الأحدث أولًا): {prev}" if prev else ""),
            "  <i>أسرة = جهاز عمل فعلًا تربويًا واحدًا على الأقل خلال 7 أيام: سؤال للمربّي، "
            "درس بدأ/تقدّم/اكتمل، تسجيل عادة، مهمة طفل (فُتحت/أُنجزت/ثُبّتت)، أو تحدٍّ بدأ. "
            "فتح التطبيق وحده لا يُحسب.</i>",
        ])
    if openers:
        prev = " · ".join(str(w["devices"]) for w in openers[1:])
        lines.extend([
            f"  📱 أجهزة فتحت الرئيسية: <b>{openers[0]['devices']}</b>"
            + (f" | سابقًا: {prev}" if prev else ""),
            "  <i>تقريبي: يُعدّ الجهاز إذا جلبت الرئيسية «نصيحة اليوم» — لا يوجد سجل فتح مباشر.</i>",
        ])
    lines.append("")

    lines.extend([
        "🎯 <b>مسار التفعيل (Activation Funnel لكوهورت الأسبوع):</b>",
        f"  1️⃣ تثبيت وتسجيل طفل: <b>{funnel['cohort_size']}</b> جهاز (100%)",
        f"  2️⃣ بدأ أول درس: <b>{funnel['started_lesson']}</b> جهاز ({funnel['started_pct']:.1f}%)",
        f"  3️⃣ أتمّ درساً كاملاً: <b>{funnel['completed_lesson']}</b> جهاز ({funnel['completed_pct']:.1f}%)",
        f"  4️⃣ سأل سؤالاً حقيقياً: <b>{funnel['asked_question']}</b> جهاز ({funnel['asked_pct']:.1f}%)",
    ])

    # Leakage analysis
    if funnel["cohort_size"] > 0:
        c0 = funnel["cohort_size"]
        c1 = funnel["started_lesson"]
        drop_install_lesson = ((c0 - c1) / c0 * 100) if c0 else 0
        lines.append(f"  ⚠️ <i>تسريب التهيئة ← أول درس: {drop_install_lesson:.1f}%</i>")

    if cohorts:
        lines.extend([
            "",
            "🔄 <b>الاحتفاظ حسب أسبوع التسجيل (أول طفل مسجَّل):</b>",
            "  <i>D1 فتح = اليوم التالي · D7 = الأيام 7–13 · D30 = الأيام 30–36. "
            "«فتح» = نصيحة اليوم أو أي فعل؛ «فعل» = فعل تربوي فقط. "
            "— = النافذة لم تكتمل بعد.</i>",
        ])
        for c in cohorts:
            if not c["size"]:
                lines.append(f"  • {c['week']}: لا تسجيلات")
                continue
            lines.append(
                f"  • {c['week']} (n={c['size']}): "
                f"D1 فتح {_pct(*c['d1_open'])} · D7 فتح {_pct(*c['d7_open'])} · "
                f"D7 فعل {_pct(*c['d7_action'])} · D30 فتح {_pct(*c['d30_open'])}"
            )

    lines.extend([
        "",
        "💬 <b>الأسئلة الحقيقية للأهالي:</b>",
        f"  • إجمالي رسائل المستخدمين: {qm['total_user_messages']}",
        f"  • مستبعد (أزرار جاهزة): {qm['suggested_dropped']} | نقر عشوائي/تحية: {qm['short_dropped']}",
        f"  • <b>الأسئلة الحقيقية: {qm['genuine_questions']}</b>",
        f"  • أسئلة انطلقت من نصيحة اليوم: {qm['tip_initiated_count']}",
        f"  • نسبة الأسئلة غير المخدومة: <b>{qm['unanswered_rate']:.1f}%</b> من كل الرسائل، وتفصيلها:",
        f"    – بلا أي رد محفوظ (غادر قبل أول كلمة أو تعطّل الخادم): {qm['orphans']}",
        f"    – انقطع البث بعد أن ظهر جزء من الرد (خروج من التطبيق/إيقاف): {qm['interrupted']}",
        f"    – فشل من الخادم ورُدّ باعتذار (مهلة/مزوّد/خطأ): {qm['errors']}",
    ])
    outcomes = qm.get("stream_outcomes") or {}
    if any(outcomes.values()):
        lines.append(
            "    <i>سجل المساعد: غادر قبل أول كلمة "
            f"{outcomes.get('client_left_before_first_token', 0)} · "
            f"مهلة أول كلمة {outcomes.get('first_token_timeout', 0)} · "
            f"توقف أثناء البث {outcomes.get('stream_stalled', 0)} · "
            f"خطأ المزوّد أثناء البث {outcomes.get('stream_error', 0)} · "
            f"خطأ قبل البث {outcomes.get('pipeline_error', 0)}</i>"
        )
        if outcomes.get("completed_after_disconnect"):
            lines.append(
                "    <i>اكتمل بعد مغادرة الأب وحُفظ (يظهر عند إعادة فتح المحادثة): "
                f"{outcomes['completed_after_disconnect']} — محسوب ضمن المُجاب</i>"
            )

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
    ap.add_argument("--sessions-db", default=str(_SESSIONS_DB),
                    help="Path to the assistant telemetry sessions.db (optional)")
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
    north = get_north_star(db_path)
    openers = get_openers(db_path)
    cohorts = get_cohort_retention(db_path)
    funnel = get_funnel_metrics(db_path, args.days, suggested)
    qm = get_questions_and_quality(db_path, args.days, suggested, Path(args.sessions_db))
    tips = get_coach_tips_metrics(db_path, args.days)
    fb = get_feedback_metrics(db_path, args.days)

    report = format_report(args.days, north, openers, cohorts, funnel, qm, tips, fb)

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
