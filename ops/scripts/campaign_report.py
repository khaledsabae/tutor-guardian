#!/usr/bin/env python3
"""Campaign report — which channel brings families who stay.

One block per campaign code (DA01, WAAR, KT001 … — the scheme lives in
backend/app/services/attribution.py), then the same numbers for personal
invites and for every new device, as the yardstick:

  clicks    landing-page visits carrying the code (referral_clicks; the same
            IP and code within 10 minutes count once; link-preview fetchers
            such as facebookexternalhit are not visits and are left out)
  installs  claims (referrals). `new` = the claim came with the first launch;
            `already` = the app was installed before and a tap on the link
            opened it (App Links), so it is re-engagement, not acquisition.
            Every rate below is over `new` only.
  child     new installs that added a child (ever)
  lesson    … that started a lesson (ever)
  D7        … with a family action in days 7–13 after the claim, over the
            claims at least 14 days old. Action = a parent chat message,
            lesson progress, a habit event, a child mission or a child
            challenge.

Read-only: the database is opened with mode=ro. Aggregates only — no device
ids, IPs or text leave the database.

Usage (inside the backend container, like weekly_funnel_report.py):
    docker exec -w /app tg_backend python ops/scripts/campaign_report.py --dry-run
    docker exec -w /app tg_backend python ops/scripts/campaign_report.py   # → Telegram

Without --dry-run the report goes to Telegram (TELEGRAM_BOT_TOKEN and
TELEGRAM_CHAT_ID from the environment); --dry-run only prints it.
"""
from __future__ import annotations

import argparse
import bisect
import json
import os
import re
import sqlite3
import sys
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

_HERE = Path(globals().get("__file__", "")).resolve()
# Piped to `python -` (a read-only check on a host that predates the script)
# there is no file to resolve from; the container's working dir is /app.
_ROOT = _HERE.parents[2] if _HERE.is_file() else Path.cwd()
_DB = Path(os.environ.get("CONVERSATIONS_DB", str(_ROOT / "ops" / "conversations.db")))

# Mirror of CAMPAIGN_CHANNELS in backend/app/services/attribution.py, copied so
# this script runs on its own (and on a host whose backend predates it).
# backend/tests/test_campaign_report.py fails if the two drift.
CAMPAIGN_CHANNELS: dict[str, tuple[str, str]] = {
    "DA": ("preacher_ar", "social"),
    "EN": ("preacher_en", "social"),
    "WA": ("whatsapp", "social"),
    "KT": ("kuttab", "offline"),
    "CM": ("community", "social"),
    "PD": ("paid", "paid"),
    "OT": ("other", "referral"),
}
CAMPAIGN_RE = re.compile(r"^(?:" + "|".join(CAMPAIGN_CHANNELS) + r")[A-Z0-9]{2,14}$")
# A six-character code from the device alphabet is a person's invite, even
# one that starts like a campaign (production has `EN…` device codes).
DEVICE_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
DEVICE_CODE_LEN = 6
# Link-preview fetchers (a share in a chat fetches the preview) were 15% of
# production clicks before the landing pages stopped recording them; this
# keeps the older rows out of the count too. Mirror of PREVIEW_FETCHER_RE.
PREVIEW_FETCHER_RE = re.compile(
    r"facebookexternalhit|Facebot|WhatsApp/|TelegramBot|Twitterbot|Slackbot|"
    r"Discordbot|LinkedInBot|Googlebot|bingbot|Applebot|SkypeUriPreview",
    re.IGNORECASE,
)

_TS = "%Y-%m-%d %H:%M:%S"
_NEW_INSTALL_SLACK = timedelta(days=1)   # first session at most this long before the claim
_D7_FROM, _D7_TO = timedelta(days=7), timedelta(days=14)
_MAX_CODES_LISTED = 30
_TG_LIMIT = 3800

# (table, timestamp column) pairs that count as a family action. Columns are
# wrapped in datetime() when read: production stores three formats
# ('2026-10-01 10:00:00', '…T10:00:00Z', '…T10:00:00+00:00') and only the
# normalised form compares correctly as text.
_ACTION_COLUMNS = (
    ("lesson_progress", "started_at"), ("lesson_progress", "updated_at"),
    ("lesson_progress", "completed_at"),
    ("habits_value_events", "created_at"), ("habits_value_events", "updated_at"),
    ("child_missions", "assigned_at"), ("child_missions", "claimed_at"),
    ("child_missions", "confirmed_at"),
    ("child_challenges", "started_at"), ("child_challenges", "resolved_at"),
)


def is_campaign_code(code: str | None) -> bool:
    if not code or not CAMPAIGN_RE.match(code):
        return False
    return not (len(code) == DEVICE_CODE_LEN and set(code) <= set(DEVICE_CODE_ALPHABET))


def channel_of(code: str) -> str:
    return CAMPAIGN_CHANNELS[code[:2]][0]


def _connect_ro(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _parse(ts: str) -> datetime:
    return datetime.strptime(ts, _TS)


@dataclass
class Cohort:
    """Funnel numbers for one group of devices, each with its own start time."""
    clicks: int = 0
    first_seen: str | None = None
    already: int = 0
    new: int = 0
    child: int = 0
    lesson: int = 0
    d7_eligible: int = 0
    d7_active: int = 0
    members: list[tuple[str, str]] = field(default_factory=list, repr=False)


@dataclass
class Facts:
    """Per-device facts, read once from the database."""
    now: datetime
    since: str
    first_session: dict[str, str]
    with_child: set[str]
    with_lesson: set[str]
    actions: dict[str, list[str]]
    claims: list[tuple[str, str, str]]     # (code, device_id, claimed_at)
    clicks: dict[str, tuple[int, str]]     # code → (clicks, first click)


def load_facts(conn: sqlite3.Connection, days: int, now: datetime) -> Facts:
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    since = (now - timedelta(days=days)).strftime(_TS)

    def rows(sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        return conn.execute(sql, params).fetchall()

    first_session = {r[0]: r[1] for r in rows(
        "SELECT device_id, MIN(datetime(created_at)) FROM chat_sessions "
        "WHERE device_id IS NOT NULL GROUP BY device_id")} if "chat_sessions" in tables else {}
    with_child = {r[0] for r in rows("SELECT DISTINCT device_id FROM child_profiles")} \
        if "child_profiles" in tables else set()
    with_lesson = {r[0] for r in rows(
        "SELECT DISTINCT device_id FROM lesson_progress "
        "WHERE status IN ('in_progress', 'completed') OR started_at IS NOT NULL")} \
        if "lesson_progress" in tables else set()

    actions: dict[str, list[str]] = {}
    if {"chat_sessions", "chat_messages"} <= tables:
        for r in rows("SELECT cs.device_id, datetime(cm.created_at) FROM chat_messages cm "
                      "JOIN chat_sessions cs ON cs.id = cm.session_id WHERE cm.role = 'user'"):
            if r[1]:
                actions.setdefault(r[0], []).append(r[1])
    for table, column in _ACTION_COLUMNS:
        if table not in tables:
            continue
        cols = {c[1] for c in conn.execute(f"PRAGMA table_info({table})")}
        if column not in cols:
            continue
        for r in rows(f"SELECT device_id, datetime({column}) FROM {table} "
                      f"WHERE {column} IS NOT NULL"):
            if r[1]:
                actions.setdefault(r[0], []).append(r[1])
    for stamps in actions.values():
        stamps.sort()

    claims = [(r[0], r[1], r[2]) for r in rows(
        "SELECT code, referred_device, datetime(created_at) FROM referrals "
        "WHERE datetime(created_at) >= ? ORDER BY created_at", (since,))] \
        if "referrals" in tables else []
    clicks: dict[str, tuple[int, str]] = {}
    if "referral_clicks" in tables:
        for code, user_agent, at in rows(
                "SELECT code, user_agent, datetime(clicked_at) FROM referral_clicks "
                "WHERE datetime(clicked_at) >= ?", (since,)):
            if PREVIEW_FETCHER_RE.search(user_agent or ""):
                continue
            n, first = clicks.get(code, (0, at))
            clicks[code] = (n + 1, min(first, at))
    return Facts(now=now, since=since, first_session=first_session, with_child=with_child,
                 with_lesson=with_lesson, actions=actions, claims=claims, clicks=clicks)


def _acted_between(stamps: list[str], start: datetime, end: datetime) -> bool:
    i = bisect.bisect_left(stamps, start.strftime(_TS))
    return i < len(stamps) and stamps[i] < end.strftime(_TS)


def _finish(cohort: Cohort, facts: Facts) -> Cohort:
    """Fill child / lesson / D7 from cohort.members — the new installs."""
    cohort.new = len(cohort.members)
    for device, start in cohort.members:
        cohort.child += device in facts.with_child
        cohort.lesson += device in facts.with_lesson
        t0 = _parse(start)
        if t0 + _D7_TO <= facts.now:
            cohort.d7_eligible += 1
            cohort.d7_active += _acted_between(facts.actions.get(device, []),
                                               t0 + _D7_FROM, t0 + _D7_TO)
    return cohort


def _is_new_install(facts: Facts, device: str, claimed_at: str) -> bool:
    first = facts.first_session.get(device)
    return first is None or _parse(first) >= _parse(claimed_at) - _NEW_INSTALL_SLACK


def build_report_data(facts: Facts) -> dict:
    campaigns: dict[str, Cohort] = {}
    invites = Cohort()

    def campaign(code: str) -> Cohort:
        return campaigns.setdefault(code, Cohort())

    for code, (n, first) in facts.clicks.items():
        if is_campaign_code(code):
            c = campaign(code)
            c.clicks, c.first_seen = n, first
        else:
            invites.clicks += n
    for code, device, claimed_at in facts.claims:
        cohort = campaign(code) if is_campaign_code(code) else invites
        if cohort is not invites and (cohort.first_seen is None or claimed_at < cohort.first_seen):
            cohort.first_seen = claimed_at
        if _is_new_install(facts, device, claimed_at):
            cohort.members.append((device, claimed_at))
        else:
            cohort.already += 1

    for cohort in [*campaigns.values(), invites]:
        _finish(cohort, facts)

    channels: dict[str, Cohort] = {}
    for code, c in campaigns.items():
        ch = channels.setdefault(channel_of(code), Cohort())
        ch.clicks += c.clicks
        ch.already += c.already
        ch.members.extend(c.members)
    for ch in channels.values():
        _finish(ch, facts)

    everyone = Cohort(members=[(d, t) for d, t in facts.first_session.items()
                               if t >= facts.since])
    _finish(everyone, facts)
    return {"campaigns": campaigns, "channels": channels, "invites": invites,
            "everyone": everyone}


def _pct(part: int, whole: int) -> str:
    return f"{part * 100 / whole:.0f}%" if whole else "–"


def _line(c: Cohort, with_clicks: bool = True) -> str:
    parts = []
    if with_clicks:
        parts.append(f"نقرات {c.clicks}")
    installs = f"تثبيت {c.new}"
    if c.already:
        installs += f" (+{c.already} مثبَّت سابقًا)"
    parts += [installs,
              f"طفل {c.child} ({_pct(c.child, c.new)})",
              f"درس {c.lesson} ({_pct(c.lesson, c.new)})",
              f"D7 {c.d7_active}/{c.d7_eligible} ({_pct(c.d7_active, c.d7_eligible)})"]
    return " · ".join(parts)


def format_report(data: dict, days: int, now: datetime) -> str:
    out = [f"📣 <b>تقرير الحملات</b> — آخر {days} يومًا (حتى {now:%Y-%m-%d %H:%M} UTC)", ""]
    campaigns: dict[str, Cohort] = data["campaigns"]
    ranked = sorted(campaigns.items(), key=lambda kv: (-kv[1].new, -kv[1].clicks, kv[0]))
    if not ranked:
        out.append("لا كود حملة له نقرة أو تثبيت في هذه الفترة.")
    for code, c in ranked[:_MAX_CODES_LISTED]:
        since = f" · منذ {c.first_seen[:10]}" if c.first_seen else ""
        out.append(f"<b>{code}</b> · {channel_of(code)}{since}")
        out.append("  " + _line(c))
    rest = ranked[_MAX_CODES_LISTED:]
    if rest:
        out.append(f"… و{len(rest)} كودًا آخر: نقرات {sum(c.clicks for _, c in rest)} · "
                   f"تثبيت {sum(c.new for _, c in rest)}")
    if data["channels"]:
        out += ["", "<b>حسب القناة</b>"]
        for name, c in sorted(data["channels"].items(), key=lambda kv: -kv[1].new):
            out.append(f"{name}: " + _line(c))
    out += ["", "<b>للمقارنة</b>",
            "دعوات شخصية: " + _line(data["invites"]),
            "كل جهاز جديد: " + _line(data["everyone"], with_clicks=False),
            "",
            "التثبيت = طلب إحالة من التطبيق؛ النسب على التثبيتات الجديدة وحدها. "
            "D7 = فعل أسري في الأيام 7–13 بعد التثبيت، على من مضى عليه 14 يومًا."]
    return "\n".join(out)


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
        data = urllib.parse.urlencode(
            {"chat_id": chat_id, "text": part, "parse_mode": "HTML"}).encode()
        try:
            req = urllib.request.Request(url, data=data, method="POST")
            with urllib.request.urlopen(req, timeout=15) as resp:
                body = json.loads(resp.read())
            if not body.get("ok"):
                print(f"Telegram rejected: {body.get('description')}", file=sys.stderr)
                ok_all = False
        except Exception as e:  # noqa: BLE001
            print(f"Telegram send failed: {type(e).__name__}", file=sys.stderr)
            ok_all = False
    return ok_all


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Campaign attribution report (read-only)")
    ap.add_argument("--days", type=int, default=120,
                    help="claims and clicks from the last N days (default 120)")
    ap.add_argument("--db", default=str(_DB), help="path to conversations.db")
    ap.add_argument("--dry-run", action="store_true",
                    help="print the report instead of sending it to Telegram")
    args = ap.parse_args(argv)

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"Error: database {db_path} does not exist", file=sys.stderr)
        return 1
    now = datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)
    conn = _connect_ro(db_path)
    try:
        facts = load_facts(conn, args.days, now)
    finally:
        conn.close()
    report = format_report(build_report_data(facts), args.days, now)

    if args.dry_run:
        print(report)
        return 0
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        print("No TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID — printing instead.", file=sys.stderr)
        print(report)
        return 0
    if send_telegram(token, chat_id, report):
        print("Campaign report sent to Telegram.")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
