#!/usr/bin/env python3
"""Campaign report — which channel brings families who stay.

One block per campaign code (DA01, WA02, KT17 … — the scheme lives in
backend/app/services/attribution.py), then the same numbers for personal
invites and for every new device, as the yardstick:

  clicks    landing-page visits carrying the code: raw referral_clicks rows
            (the same IP and code within 10 minutes count once; link-preview
            fetchers such as facebookexternalhit are not visits) plus
            referral_click_days, where rows older than a week are folded.
  installs  claims (referrals). `new` = the claim came with the first launch;
            `already` = the app was installed before and a tap on the link
            opened it (App Links), so it is re-engagement, not acquisition.
            Every rate below is over `new` only. New installs are split by
            how the claim was made (referrals.via): an exact code (install
            referrer, deep link, typed) or AUTO, a guess from a click on the
            same IP — weaker on a carrier NAT. Claims from before the split
            was recorded show as «قبل التتبّع».
  child     new installs that added a child (ever)
  lesson    … that started a lesson (ever)
  D7        … with a family action in days 7–13 after the claim, over the
            claims at least 14 days old. Action = a parent chat message,
            lesson progress, a habit event, a child mission or a child
            challenge.

Read-only: the database is opened with mode=ro. Aggregates only — no device
ids, IPs or text leave the database. Eval-harness and remote-E2E test devices
are left out of every device number (real_device_sql below).

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
# Exactly two letters and two digits: no typo of a six-character personal
# code can take this shape. Mirror of CAMPAIGN_RE.
CAMPAIGN_RE = re.compile(r"^(?:" + "|".join(CAMPAIGN_CHANNELS) + r")[0-9]{2}$")
# Link-preview fetchers (a share in a chat fetches the preview) were 15% of
# production clicks before the landing pages stopped recording them; this
# keeps the older rows out of the count too. Mirror of PREVIEW_FETCHER_RE.
PREVIEW_FETCHER_RE = re.compile(
    r"facebookexternalhit|Facebot|WhatsApp/|TelegramBot|Twitterbot|Slackbot|"
    r"Discordbot|LinkedInBot|Googlebot|bingbot|Applebot|SkypeUriPreview",
    re.IGNORECASE,
)

# Mirror of backend/app/core/real_traffic.py (eval-harness and remote-E2E test
# devices), copied for the same reason as the channels above;
# backend/tests/test_real_traffic.py fails if the two drift.
_EVAL_DEVICE_LIKE = "eval-harness-%"
_E2E_CHILD_NAME_LIKE = "E2E-Maestro%"
_E2E_QUESTION_LIKE = "E2E test%"


def e2e_devices_sql(tables) -> str:
    tables = set(tables)
    marked = []
    if "child_profiles" in tables:
        marked.append("SELECT device_id FROM child_profiles "
                      f"WHERE name LIKE '{_E2E_CHILD_NAME_LIKE}'")
    if {"chat_messages", "chat_sessions"} <= tables:
        marked.append("SELECT s.device_id FROM chat_messages m "
                      "JOIN chat_sessions s ON s.id = m.session_id "
                      f"WHERE m.role = 'user' AND m.content LIKE '{_E2E_QUESTION_LIKE}'")
    if not marked:
        return "SELECT NULL WHERE 0"
    parts = ["SELECT device_id FROM marked"]
    if "push_tokens" in tables:
        parts.append("SELECT device_id FROM push_tokens WHERE token IN "
                     "(SELECT token FROM push_tokens WHERE device_id IN marked)")
    if "device_aliases" in tables:
        parts.append("SELECT device_id FROM device_aliases WHERE canonical_device IN marked")
        parts.append("SELECT canonical_device FROM device_aliases WHERE device_id IN marked")
    return (f"WITH marked(device_id) AS ({' UNION '.join(marked)}) "
            f"SELECT device_id FROM ({' UNION '.join(parts)}) WHERE device_id IS NOT NULL")


def _json_literal(values) -> str:
    return "'" + json.dumps(sorted(v for v in values if v is not None)).replace("'", "''") + "'"


def real_device_sql(column: str, e2e) -> str:
    return (f"({column} IS NULL OR ({column} NOT LIKE '{_EVAL_DEVICE_LIKE}' "
            f"AND {column} NOT IN (SELECT value FROM json_each({_json_literal(e2e)}))))")


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
    return bool(code) and bool(CAMPAIGN_RE.match(code))


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
    exact: int = 0      # new installs claimed with the code itself
    auto: int = 0       # … matched to a click by IP
    unknown: int = 0    # … from before referrals.via existed
    child: int = 0
    lesson: int = 0
    d7_eligible: int = 0
    d7_active: int = 0
    members: list[tuple[str, str, str | None]] = field(default_factory=list, repr=False)


@dataclass
class Facts:
    """Per-device facts, read once from the database."""
    now: datetime
    since: str
    first_session: dict[str, str]
    with_child: set[str]
    with_lesson: set[str]
    actions: dict[str, list[str]]
    claims: list[tuple[str, str, str, str | None]]  # (code, device, claimed_at, via)
    clicks: dict[str, tuple[int, str]]     # code → (clicks, first click)


def load_facts(conn: sqlite3.Connection, days: int, now: datetime) -> Facts:
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    since = (now - timedelta(days=days)).strftime(_TS)

    def rows(sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        return conn.execute(sql, params).fetchall()

    # The test devices, found once for the whole report.
    e2e = {r[0] for r in rows(e2e_devices_sql(tables)) if r[0] is not None}

    def real(column: str) -> str:
        return real_device_sql(column, e2e)

    first_session = {r[0]: r[1] for r in rows(
        "SELECT device_id, MIN(datetime(created_at)) FROM chat_sessions "
        f"WHERE device_id IS NOT NULL AND {real('device_id')} GROUP BY device_id")} \
        if "chat_sessions" in tables else {}
    with_child = {r[0] for r in rows(
        f"SELECT DISTINCT device_id FROM child_profiles WHERE {real('device_id')}")} \
        if "child_profiles" in tables else set()
    with_lesson = {r[0] for r in rows(
        "SELECT DISTINCT device_id FROM lesson_progress "
        "WHERE (status IN ('in_progress', 'completed') OR started_at IS NOT NULL) "
        f"AND {real('device_id')}")} \
        if "lesson_progress" in tables else set()

    actions: dict[str, list[str]] = {}
    if {"chat_sessions", "chat_messages"} <= tables:
        for r in rows("SELECT cs.device_id, datetime(cm.created_at) FROM chat_messages cm "
                      "JOIN chat_sessions cs ON cs.id = cm.session_id "
                      f"WHERE cm.role = 'user' AND {real('cs.device_id')}"):
            if r[1]:
                actions.setdefault(r[0], []).append(r[1])
    for table, column in _ACTION_COLUMNS:
        if table not in tables:
            continue
        cols = {c[1] for c in conn.execute(f"PRAGMA table_info({table})")}
        if column not in cols:
            continue
        for r in rows(f"SELECT device_id, datetime({column}) FROM {table} "
                      f"WHERE {column} IS NOT NULL AND {real('device_id')}"):
            if r[1]:
                actions.setdefault(r[0], []).append(r[1])
    for stamps in actions.values():
        stamps.sort()

    claims: list[tuple[str, str, str, str | None]] = []
    if "referrals" in tables:
        # referrals.via arrived in schema v32; older databases read as NULL.
        has_via = "via" in {c[1] for c in conn.execute("PRAGMA table_info(referrals)")}
        via = "via" if has_via else "NULL"
        claims = [(r[0], r[1], r[2], r[3]) for r in rows(
            f"SELECT code, referred_device, datetime(created_at), {via} FROM referrals "
            f"WHERE datetime(created_at) >= ? AND {real('referred_device')} "
            "ORDER BY created_at", (since,))]
    clicks: dict[str, tuple[int, str]] = {}

    def add_clicks(code: str, n: int, at: str) -> None:
        total, first = clicks.get(code, (0, at))
        clicks[code] = (total + n, min(first, at))

    if "referral_clicks" in tables:
        for code, user_agent, at in rows(
                "SELECT code, user_agent, datetime(clicked_at) FROM referral_clicks "
                "WHERE datetime(clicked_at) >= ?", (since,)):
            if not PREVIEW_FETCHER_RE.search(user_agent or ""):
                add_clicks(code, 1, at)
    if "referral_click_days" in tables:  # raw rows older than a week, folded
        for code, n, day in rows(
                "SELECT code, SUM(clicks), MIN(day) FROM referral_click_days "
                "WHERE day >= date(?) GROUP BY code", (since,)):
            add_clicks(code, n, f"{day} 00:00:00")
    return Facts(now=now, since=since, first_session=first_session, with_child=with_child,
                 with_lesson=with_lesson, actions=actions, claims=claims, clicks=clicks)


def _acted_between(stamps: list[str], start: datetime, end: datetime) -> bool:
    i = bisect.bisect_left(stamps, start.strftime(_TS))
    return i < len(stamps) and stamps[i] < end.strftime(_TS)


def _finish(cohort: Cohort, facts: Facts) -> Cohort:
    """Fill child / lesson / D7 from cohort.members — the new installs."""
    cohort.new = len(cohort.members)
    for device, start, via in cohort.members:
        cohort.exact += via == "code"
        cohort.auto += via == "auto"
        cohort.unknown += via not in ("code", "auto")
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
    for code, device, claimed_at, via in facts.claims:
        cohort = campaign(code) if is_campaign_code(code) else invites
        if cohort is not invites and (cohort.first_seen is None or claimed_at < cohort.first_seen):
            cohort.first_seen = claimed_at
        if _is_new_install(facts, device, claimed_at):
            cohort.members.append((device, claimed_at, via))
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

    everyone = Cohort(members=[(d, t, None) for d, t in facts.first_session.items()
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
    if with_clicks and c.new:  # a claim-based cohort: say how it was claimed
        split = [f"بالكود {c.exact}", f"بمطابقة IP {c.auto}"]
        if c.unknown:
            split.append(f"قبل التتبّع {c.unknown}")
        installs += " [" + " · ".join(split) + "]"
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
            "«بالكود» = وصل الكود نفسه؛ «بمطابقة IP» = تخمين من نقرة على العنوان نفسه. "
            "D7 = فعل أسري في الأيام 7–13 بعد التثبيت، على من مضى عليه 14 يومًا. "
            "الفعل هنا: رسالة للمساعد، أو تقدّم في درس، أو عادة، أو مهمة طفل، أو تحدٍّ — "
            "أوسع من «رسالة + درس» في weekly_funnel_report.py، فلا تقارن الرقمين."]
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
