#!/usr/bin/env python3
"""Weekly launch report — every marketing decision on retention per code.

Launch plan «نور والقناديل» (Oct 2026 → Ramadan 1448), phase A item 4 and the
«الأرقام اللي بنحكم بيها» table. One Telegram message, every Sunday 09:00
Cairo, to the same chat as weekly_dashboard.py (TELEGRAM_BOT_TOKEN and
TELEGRAM_CHAT_ID in tg_backend's environment).

Definitions
-----------
North Star  — weekly active families with a real parenting action:
    weekly_funnel_report.get_north_star, unchanged — distinct real devices
    (eval-harness and remote-E2E devices left out, backend/app/core/
    real_traffic.py) with at least one action in the window. An action is a
    question to the assistant or any row of app.services.family_actions.
    ACTION_SOURCES: lesson progress, a habit check-in, a child mission
    (assigned when the child opens it, claimed, confirmed), a challenge
    started, a follow-up answered, a weekly-plan step ticked, a Ramadan mark,
    a Prayer Journey started. Opening the app is not an action. The same list
    lights the in-app lanterns, and gave the 2026-10-04 baseline (~90/week).
Week        — the 7 full UTC days before the run day (a Sunday run reads
    Sunday–Saturday).
Per code    — campaign codes (two letters + two digits, attribution.py).
    clicks and installs come from campaign_report.py unchanged: installs are
    new-install claims (`referrals`), split by how the code arrived.
    Day 0 is the claim's UTC day, and a member counts only once its window is
    over — the funnel report's cohort rules:
    D1 (DB)    = seen on day 1: a «اليوم» tip fetched (coach_tips), a daily
                 login (daily_login_streaks) or an action that day.
    D7 action  = an action on days 7–13.
    GA4        = new users with firstUserCampaignName = the code, and
                 cohortSpec retention (cohortActiveUsers on nthDay 1 and 7
                 over cohortTotalUsers). Never active7DayUsers: it
                 double-counts overlapping windows.
    Cost       = spend for the code (docs/marketing/campaign_spend.csv) ÷
                 families with a D7 action.
Gate        — D7 action over the funnel report's family cohorts (week of a
    device's first child profile) whose days 7–13 are over, last six weeks.
Decisions   — D1 < 10% ⇒ أوقف · 10–20% ⇒ راقب ولا تزد · ≥ 20% ⇒ كمّل. On fewer
    than MIN_SAMPLE installs there is no decision, only the count. D7 action
    ≥ 12% opens the second wave; (direct) < 30% of new users; crash-free ≥ 99.5%.
Crash-free  — sessions are NOT measurable here: Crashlytics has no BigQuery
    export on project almorabbi (no dataset) and no session API. The report
    shows GA4 crashFreeUsersRate (users, not sessions) and Play vitals
    crashRate (user-days) and says so.

Where it runs
-------------
The production database is in tg_backend on the VPS; the GA4 key is on the
laptop. So the run has two halves, glued by PCC on the laptop:

  laptop:    python launch_weekly_report.py --via-ssh root@<vps> --keyfile K
             (fetches GA4 + Play vitals + the spend CSV into one JSON bundle,
              then pipes it into the container half over ssh)
  container: python ops/scripts/launch_weekly_report.py --ga4-json -
             (reads the database read-only, composes, sends to Telegram)

Other modes: --fetch-ga4 (print the bundle), --emit-db-json (print the
database aggregates), --db-json FILE (compose from saved aggregates). Every
mode takes --dry-run: print instead of sending.

Read-only: the database is opened with mode=ro. Aggregates only — no device
ids, IPs or text leave the database or reach Telegram.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sqlite3
import subprocess
import sys
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

_HERE = Path(globals().get("__file__", "")).resolve()
# Piped to `python -` there is no file; the container's working dir is /app.
_ROOT = _HERE.parents[2] if _HERE.is_file() else Path.cwd()
_DB = Path(os.environ.get("CONVERSATIONS_DB", str(_ROOT / "ops" / "conversations.db")))
_SPEND_CSV = _ROOT / "docs" / "marketing" / "campaign_spend.csv"

GA4_PROPERTY = "541338024"
PLAY_PACKAGE = "com.alsaba.almorabbi"
LAUNCH = date(2026, 7, 31)          # before this: internal tests only
NORTH_STAR_BASELINE = 90             # master plan, production DB, 2026-10-04
NORTH_STAR_TARGET_PRE_RAMADAN = 3    # ×3 before Ramadan
NORTH_STAR_TARGET_RAMADAN = 10       # ×10 in Ramadan
D1_STOP, D1_KEEP = 10.0, 20.0        # per code, percent
D7_ACTION_GATE = 12.0                # second-wave gate, percent
DIRECT_MAX = 30.0                    # (direct) share of new users, percent
CRASH_FREE_MIN = 99.5                # percent
MIN_SAMPLE = 20                      # installs before a code gets a decision
FEATURE_VERSION = (1, 0, 73)         # first build with the «نور» events

FEATURE_EVENTS = (
    "horizon_strip_shown", "horizon_strip_tapped", "horizon_gate_tapped",
    "horizon_to_action_48h", "lantern_lit", "next_step_committed",
    "companion_shown", "companion_reply", "family_road_opened",
    "child_corner_opened", "child_corner_pick", "child_corner_mission",
    "child_corner_ended", "share_moment", "referral_claimed",
)

_TS = "%Y-%m-%d %H:%M:%S"
_TG_LIMIT = 3800


# ── shared helpers ───────────────────────────────────────────────────────────

def _cr():
    """ops/scripts/campaign_report.py — imported only where the database is
    read, so the laptop half runs from a lone file."""
    for p in (_HERE.parent if _HERE.is_file() else None, _ROOT / "ops" / "scripts"):
        if p is not None and str(p) not in sys.path:
            sys.path.insert(0, str(p))
    import campaign_report  # noqa: PLC0415
    return campaign_report


def week_windows(today: date) -> dict:
    """This week = the 7 full days before `today`; last week the 7 before."""
    return {
        "this": (today - timedelta(days=7), today - timedelta(days=1)),
        "last": (today - timedelta(days=14), today - timedelta(days=8)),
    }


def version_tuple(v: str) -> tuple[int, ...]:
    try:
        return tuple(int(x) for x in v.split("+")[0].split("."))
    except ValueError:
        return ()


def pct(part: float, whole: float) -> float | None:
    return part * 100.0 / whole if whole else None


def fmt_pct(value: float | None, digits: int = 0) -> str:
    return "–" if value is None else f"{value:.{digits}f}%"


def read_spend_csv(path: Path) -> list[list]:
    """code,date,amount rows; '#' lines, blanks and the header are skipped.
    A malformed row is an error, not a silent zero."""
    rows = []
    with open(path, encoding="utf-8") as fh:
        for n, raw in enumerate(csv.reader(fh), start=1):
            if not raw or not raw[0].strip() or raw[0].strip().startswith("#"):
                continue
            if raw[0].strip().lower() == "code":
                continue
            if len(raw) < 3:
                raise ValueError(f"{path.name} line {n}: want code,date,amount")
            code, day, amount = (c.strip() for c in raw[:3])
            date.fromisoformat(day)
            rows.append([code.upper(), day, float(amount)])
    return rows


# ── laptop half: GA4 + Play vitals ───────────────────────────────────────────

def _google_headers(keyfile: str, scope: str) -> dict:
    import google.auth.transport.requests as gtr  # noqa: PLC0415
    from google.oauth2 import service_account  # noqa: PLC0415
    creds = service_account.Credentials.from_service_account_file(keyfile, scopes=[scope])
    creds.refresh(gtr.Request())
    return {"Authorization": f"Bearer {creds.token}", "Content-Type": "application/json"}


def _post(url: str, headers: dict, body: dict) -> dict:
    import requests  # noqa: PLC0415
    resp = requests.post(url, headers=headers, json=body, timeout=90)
    if resp.status_code != 200:
        raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")
    return resp.json()


def ga4_rows(report: dict) -> list[list[str]]:
    return [[d["value"] for d in r.get("dimensionValues", [])]
            + [m["value"] for m in r.get("metricValues", [])]
            for r in report.get("rows", [])]


def parse_cohorts(report: dict) -> dict:
    """cohortSpec rows → {campaign: {"d1": [active, total], "d7": [...]}}.

    GA4 puts a user in one cohort only, so the two cohorts must not overlap:
    "old" (first seen up to 8 days ago) is read on nthDay 1 and 7, "recent"
    (2–7 days ago) on nthDay 1 only. The total comes from any row of the
    cohort (GA4 repeats it on each)."""
    parts: dict[str, dict[str, dict]] = {}
    for cohort, nth, campaign, active, total in ga4_rows(report):
        slot = parts.setdefault(campaign, {}).setdefault(cohort, {"total": 0})
        slot["total"] = int(total)
        slot[nth] = int(active)
    out: dict[str, dict] = {}
    for campaign, cohorts in parts.items():
        d1 = [0, 0]
        for name in ("old", "recent"):
            if name in cohorts:
                d1[0] += cohorts[name].get("0001", 0)
                d1[1] += cohorts[name]["total"]
        entry = {"d1": d1}
        if "old" in cohorts:
            entry["d7"] = [cohorts["old"].get("0007", 0), cohorts["old"]["total"]]
        out[campaign] = entry
    return out


def parse_vitals(report: dict) -> dict:
    """Play vitals daily rows → user-weighted crash rate over the window."""
    crashed = users = 0.0
    days = []
    for row in report.get("rows", []):
        m = {x["metric"]: float(x.get("decimalValue", {}).get("value", 0))
             for x in row.get("metrics", [])}
        n = m.get("distinctUsers", 0.0)
        users += n
        crashed += m.get("crashRate", 0.0) * n
        st = row.get("startTime", {})
        if st:
            days.append(f"{st['year']:04d}-{st['month']:02d}-{st['day']:02d}")
    return {"crash_rate": crashed / users if users else None,
            "user_days": int(users), "days": len(days),
            "last_day": max(days) if days else None}


def fetch_ga4(keyfile: str, today: date, cohort_days: int) -> dict:
    """Everything the report needs from Google, as one JSON-able dict. A
    failing call records its error and the rest still runs."""
    week = week_windows(today)
    ws, we = (str(d) for d in week["this"])
    cohort_start = max(LAUNCH, today - timedelta(days=cohort_days))
    out: dict = {"fetched_at": datetime.now(timezone.utc).strftime(_TS),
                 "today": str(today), "week": [ws, we],
                 "cohort_start": str(cohort_start), "errors": []}
    url = f"https://analyticsdata.googleapis.com/v1beta/properties/{GA4_PROPERTY}:runReport"
    try:
        h = _google_headers(keyfile, "https://www.googleapis.com/auth/analytics.readonly")
    except Exception as e:  # noqa: BLE001
        out["errors"].append(f"GA4 auth: {type(e).__name__}: {e}"[:200])
        h = None

    def ga4(name: str, body: dict):
        if h is None:
            return None
        try:
            return _post(url, h, body)
        except Exception as e:  # noqa: BLE001
            out["errors"].append(f"GA4 {name}: {e}"[:200])
            return None

    week_range = [{"startDate": ws, "endDate": we}]
    if r := ga4("sources", {"dateRanges": week_range,
                            "dimensions": [{"name": "firstUserSource"},
                                           {"name": "firstUserCampaignName"}],
                            "metrics": [{"name": "newUsers"}], "limit": 500}):
        out["new_users_by_source"] = [[s, c, int(n)] for s, c, n in ga4_rows(r)]
    if r := ga4("campaigns", {"dateRanges": [{"startDate": str(cohort_start),
                                              "endDate": str(today - timedelta(days=1))}],
                              "dimensions": [{"name": "firstUserCampaignName"}],
                              "metrics": [{"name": "newUsers"}], "limit": 500}):
        out["campaign_new_users"] = {c: int(n) for c, n in ga4_rows(r)}
    cohorts = []
    old_end, recent_start = today - timedelta(days=8), today - timedelta(days=7)
    if cohort_start <= old_end:
        cohorts.append({"name": "old", "dimension": "firstSessionDate", "dateRange": {
            "startDate": str(cohort_start), "endDate": str(old_end)}})
    cohorts.append({"name": "recent", "dimension": "firstSessionDate", "dateRange": {
        "startDate": str(max(cohort_start, recent_start)),
        "endDate": str(today - timedelta(days=2))}})
    if cohorts and (r := ga4("cohorts", {
            "cohortSpec": {"cohorts": cohorts, "cohortsRange": {
                "granularity": "DAILY", "startOffset": 0, "endOffset": 7}},
            "dimensions": [{"name": "cohort"}, {"name": "cohortNthDay"},
                           {"name": "firstUserCampaignName"}],
            "metrics": [{"name": "cohortActiveUsers"}, {"name": "cohortTotalUsers"}],
            "limit": 10000})):
        out["campaign_cohorts"] = parse_cohorts(r)
    if r := ga4("events", {"dateRanges": week_range,
                           "dimensions": [{"name": "eventName"}],
                           "metrics": [{"name": "eventCount"}, {"name": "totalUsers"}],
                           "dimensionFilter": {"filter": {"fieldName": "eventName",
                                                          "inListFilter": {"values": list(FEATURE_EVENTS)}}}}):
        out["events"] = {e: [int(c), int(u)] for e, c, u in ga4_rows(r)}
    if r := ga4("versions", {"dateRanges": week_range,
                             "dimensions": [{"name": "appVersion"}],
                             "metrics": [{"name": "activeUsers"}, {"name": "crashAffectedUsers"}],
                             "limit": 200}):
        out["versions"] = [[v, int(n), int(c)] for v, n, c in ga4_rows(r)]
    if r := ga4("crash", {"dateRanges": week_range,
                          "metrics": [{"name": "activeUsers"}, {"name": "crashAffectedUsers"},
                                      {"name": "crashFreeUsersRate"}]}):
        rows = ga4_rows(r)
        if rows:
            active, affected, rate = rows[0]
            out["active_users"] = int(active)
            out["crash"] = {"crash_affected_users": int(affected),
                            "crash_free_users_rate": float(rate)}

    # Play vitals: user-days, ~2 days behind; day boundaries in Los Angeles.
    # endTime is exclusive and may not pass the data's freshness.
    try:
        import requests  # noqa: PLC0415
        vh = _google_headers(keyfile, "https://www.googleapis.com/auth/playdeveloperreporting")
        base = (f"https://playdeveloperreporting.googleapis.com/v1beta1/apps/"
                f"{PLAY_PACKAGE}/crashRateMetricSet")
        meta = requests.get(base, headers=vh, timeout=60)
        meta.raise_for_status()
        fresh = [f["latestEndTime"] for f in meta.json()["freshnessInfo"]["freshnesses"]
                 if f["aggregationPeriod"] == "DAILY"][0]
        fresh_day = date(fresh["year"], fresh["month"], fresh["day"])
        d0, d1 = week["this"]
        end = min(d1 + timedelta(days=1), fresh_day)

        def ymd(d: date) -> dict:
            return {"year": d.year, "month": d.month, "day": d.day,
                    "timeZone": {"id": "America/Los_Angeles"}}
        if end <= d0:
            out["vitals"] = {"crash_rate": None, "user_days": 0, "days": 0, "last_day": None}
        else:
            r = _post(base + ":query", vh,
                      {"timelineSpec": {"aggregationPeriod": "DAILY",
                                        "startTime": ymd(d0), "endTime": ymd(end)},
                       "metrics": ["crashRate", "distinctUsers"]})
            out["vitals"] = parse_vitals(r)
    except Exception as e:  # noqa: BLE001
        out["errors"].append(f"Play vitals: {e}"[:200])
    return out


# ── container half: the database ─────────────────────────────────────────────

def _wf():
    """ops/scripts/weekly_funnel_report.py — the North Star, the cohorts and
    the one list of family actions (app.services.family_actions)."""
    _cr()  # puts ops/scripts on sys.path
    import weekly_funnel_report  # noqa: PLC0415
    return weekly_funnel_report


def day_cohort(members, open_days: dict, action_days: dict, today: date) -> dict:
    """D1 open and D7 action for (device, start timestamp) members, counted in
    UTC days from the start day like weekly_funnel_report's cohorts: a member
    is eligible once its whole window is over."""
    d1 = [0, 0]
    d7 = [0, 0]
    for device, start, *_ in members:
        d0 = datetime.strptime(start, _TS).date()
        if d0 + timedelta(days=1) < today:
            d1[1] += 1
            d1[0] += (d0 + timedelta(days=1)) in open_days.get(device, ())
        if d0 + timedelta(days=13) < today:
            d7[1] += 1
            pool = action_days.get(device, ())
            d7[0] += any(d0 + timedelta(days=k) in pool for k in range(7, 14))
    return {"d1_retained": d1[0], "d1_eligible": d1[1],
            "d7_active": d7[0], "d7_eligible": d7[1]}


def collect_db(db_path: Path, now: datetime, cohort_days: int) -> dict:
    """Every database number the report shows, as aggregates only."""
    cr, wf = _cr(), _wf()
    today = now.date()
    midnight = datetime.combine(today, datetime.min.time())

    # Clicks and claims, and which claims are new installs: campaign_report.
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        facts = cr.load_facts(conn, cohort_days, now)
    finally:
        conn.close()
    data = cr.build_report_data(facts)

    # Retention: the funnel report's actions and open signals, one list.
    since = midnight - timedelta(days=cohort_days + 1)
    events = wf.get_action_events(db_path, since)
    action_days: dict[str, set[date]] = {}
    for device, ts in events:
        action_days.setdefault(device, set()).add(ts.date())
    open_days = wf._open_days(db_path, since.date(), events)

    def cohort(c) -> dict:
        return {"clicks": c.clicks, "first_seen": c.first_seen, "new": c.new,
                "already": c.already, "exact": c.exact, "auto": c.auto,
                "unknown": c.unknown,
                **day_cohort(c.members, open_days, action_days, today)}

    # North Star: whole UTC days, the week before today first.
    north = wf.get_north_star(db_path, weeks=6, now=midnight)
    for w in north:  # funnel windows end at midnight; show the last day inside
        w["end"] = str(date.fromisoformat(w["end"]) - timedelta(days=1))

    # Second-wave gate: D7 action over the funnel report's family cohorts
    # (week of a device's first child profile), every cohort already measurable.
    rows = wf.get_cohort_retention(db_path, cohorts=6, now=now)
    measured = [r for r in rows if r["d7_action"][1]]
    gate = {"from": measured[-1]["week"] if measured else None,
            "to": measured[0]["week"] if measured else None,
            "active": sum(r["d7_action"][0] for r in measured),
            "eligible": sum(r["d7_action"][1] for r in measured),
            "d1_open": [sum(r["d1_open"][0] for r in rows), sum(r["d1_open"][1] for r in rows)]}

    wk_lo, wk_hi = f"{today - timedelta(days=7)} 00:00:00", f"{today} 00:00:00"
    return {
        "generated_at": now.strftime(_TS), "today": str(today),
        "cohort_days": cohort_days,
        "north_star": north,
        "campaigns": {code: cohort(c) for code, c in data["campaigns"].items()},
        "invites": cohort(data["invites"]),
        "gate": gate,
        "new_devices_week": sum(1 for t in facts.first_session.values()
                                if wk_lo <= t < wk_hi),
    }


# ── compose ──────────────────────────────────────────────────────────────────

def code_label(code: str, names: dict[str, str]) -> str:
    """`DA03 (د. جاسم المطوع)` — the registry name beside the code, when known."""
    return f"{code} ({names[code]})" if names.get(code) else code


def decide_code(code: str, db: dict | None, ga4: list[int] | None,
                label: str | None = None) -> str:
    """One decision line for a code, from whichever D1 sample is larger."""
    code, prefix = (label or code), code[:2]
    samples = []
    if db and db.get("d1_eligible"):
        samples.append((db["d1_retained"], db["d1_eligible"], "قاعدة"))
    if ga4 and ga4[1]:
        samples.append((ga4[0], ga4[1], "GA4"))
    if not samples:
        return f"{code}: لا تثبيت مكتمل اليوم الأول بعد ⇒ لا قرار"
    kept, n, src = max(samples, key=lambda s: s[1])
    if n < MIN_SAMPLE:
        return f"{code}: العيّنة {n} أقل من {MIN_SAMPLE} ⇒ لا قرار بعد، استمر بالقياس"
    d1 = kept * 100.0 / n
    tag = f"D1 {d1:.0f}% ({src}، n={n})"
    if d1 < D1_STOP:
        return f"{code}: {tag} < {D1_STOP:.0f}% ⇒ أوقف"
    if d1 < D1_KEEP:
        return f"{code}: {tag} بين {D1_STOP:.0f}% و{D1_KEEP:.0f}% ⇒ راقب أسبوعًا ولا تزد الصرف"
    more = " — ويجوز رفع الميزانية" if prefix == "PD" else ""
    return f"{code}: {tag} ≥ {D1_KEEP:.0f}% ⇒ كمّل{more}"


def _money(x: float) -> str:
    return f"{x:,.2f}".rstrip("0").rstrip(".")


def compose(db: dict, ga4: dict | None, spend: list[list] | None,
            spend_source: str | None, names: dict[str, str] | None = None) -> str:
    cr_re = re.compile(r"^(?:DA|EN|WA|KT|CM|PD|OT)[0-9]{2}$")
    loaded: dict[str, str] = {}
    try:
        cr = _cr()
        cr_re = cr.CAMPAIGN_RE
        loaded = cr.code_names()   # who holds each code: docs/marketing/campaign_codes.md
    except Exception:  # noqa: BLE001 — the laptop half has no campaign_report
        pass
    names = loaded if names is None else names
    ga4 = ga4 or {}
    ws, we = db["north_star"][0]["start"], db["north_star"][0]["end"]
    out = [f"🚀 تقرير الإطلاق الأسبوعي — المربّي", f"الأسبوع {ws} ← {we} (UTC)", ""]
    decisions: list[str] = []

    # 1. North Star
    ns_this, ns_last = db["north_star"][0]["families"], db["north_star"][1]["families"]
    target = NORTH_STAR_BASELINE * NORTH_STAR_TARGET_PRE_RAMADAN
    change = pct(ns_this - ns_last, ns_last)
    out += ["① النجم الشمالي — أسر نشطة بفعل تربوي حقيقي",
            f"هذا الأسبوع {ns_this} · الماضي {ns_last}"
            + (f" ({change:+.0f}%)" if change is not None else "")
            + f" · الأساس {NORTH_STAR_BASELINE}",
            f"الهدف قبل رمضان {target} (×{NORTH_STAR_TARGET_PRE_RAMADAN}) — "
            f"المحقَّق {ns_this * 100 // target}% منه",
            "اتجاه ٦ أسابيع: " + " ← ".join(str(w["families"]) for w in reversed(db["north_star"])),
            ""]
    if ns_this < ns_last:
        decisions.append(f"النجم الشمالي نزل من {ns_last} إلى {ns_this} ⇒ راجع القنوات وأكبر نقطة تسرّب")

    # 2. Per campaign code
    ga_new = {k.upper(): v for k, v in (ga4.get("campaign_new_users") or {}).items()}
    ga_coh = {k.upper(): v for k, v in (ga4.get("campaign_cohorts") or {}).items()}
    spend_by: dict[str, float] = {}
    for code, _day, amount in spend or []:
        spend_by[code] = spend_by.get(code, 0.0) + amount
    codes = sorted(set(db["campaigns"]) | {c for c in ga_new if cr_re.match(c)}
                   | {c for c in ga_coh if cr_re.match(c)} | set(spend_by))
    out.append(f"② لكل كود حملة (منذ {ga4.get('cohort_start') or 'آخر ' + str(db['cohort_days']) + ' يومًا'})")
    if not codes:
        out.append("لا كود حملة له نقرة أو تثبيت أو صرف بعد.")
    for code in codes:
        c = db["campaigns"].get(code) or {}
        coh = ga_coh.get(code, {})
        d1g, d7g = coh.get("d1"), coh.get("d7")
        line = [f"{code_label(code, names)}: نقرات {c.get('clicks', 0)}",
                f"تثبيت {c.get('new', 0)} (بالكود {c.get('exact', 0)} · IP {c.get('auto', 0)})",
                f"GA4 جدد {ga_new.get(code, 0)}"]
        out.append(" · ".join(line))
        out.append("   D1 قاعدة " + fmt_pct(pct(c.get("d1_retained", 0), c.get("d1_eligible", 0)))
                   + f" ({c.get('d1_retained', 0)}/{c.get('d1_eligible', 0)})"
                   + " · D1 GA4 " + (fmt_pct(pct(*d1g)) + f" ({d1g[0]}/{d1g[1]})" if d1g else "–")
                   + " · D7 GA4 " + (fmt_pct(pct(*d7g)) + f" ({d7g[0]}/{d7g[1]})" if d7g else "–")
                   + " · D7 فعل " + fmt_pct(pct(c.get("d7_active", 0), c.get("d7_eligible", 0)))
                   + f" ({c.get('d7_active', 0)}/{c.get('d7_eligible', 0)})")
        if code in spend_by:
            s = spend_by[code]
            if c.get("d7_eligible"):
                cost = (f"{_money(s / c['d7_active'])} للأسرة الباقية (D7)" if c.get("d7_active")
                        else "لا أسرة باقية بعد D7 — كل الصرف بلا أثر")
            else:
                cost = "D7 لم يكتمل بعد"
            per_install = f" · {_money(s / c['new'])} للتثبيت" if c.get("new") else ""
            out.append(f"   صرف {_money(s)}$ · {cost}{per_install}")
        decisions.append(decide_code(code, c or None, d1g, code_label(code, names)))
    if spend_by:
        out.append(f"(الصرف من {spend_source})")
    inv, g = db["invites"], db["gate"]
    out.append(f"للمقارنة — كل الأسر الجديدة (أسابيع {g['from']} ← {g['to']}): D1 فتح "
               + fmt_pct(pct(*g["d1_open"])) + f" ({g['d1_open'][0]}/{g['d1_open'][1]})")
    out.append(f"دعوات شخصية: تثبيت {inv['new']} · D1 "
               + fmt_pct(pct(inv["d1_retained"], inv["d1_eligible"]))
               + " · D7 فعل " + fmt_pct(pct(inv["d7_active"], inv["d7_eligible"])))
    gate = pct(g["active"], g["eligible"])
    out.append(f"بوابة الموجة الثانية — D7 فعل تربوي للأسر الجديدة (أسابيع {g['from']} ← {g['to']}): "
               f"{fmt_pct(gate, 1)} ({g['active']}/{g['eligible']}) · الهدف ≥ {D7_ACTION_GATE:.0f}%")
    if gate is not None:
        decisions.append(
            f"D7 فعل تربوي {gate:.1f}% ≥ {D7_ACTION_GATE:.0f}% ⇒ بوابة الموجة الثانية مفتوحة"
            if gate >= D7_ACTION_GATE else
            f"D7 فعل تربوي {gate:.1f}% < {D7_ACTION_GATE:.0f}% ⇒ الموجة الثانية تتصغّر والصرف يروح على الاحتفاظ")
    out.append("")

    # 3. (direct) share
    out.append("③ مصدر المستخدمين الجدد هذا الأسبوع (GA4)")
    src = ga4.get("new_users_by_source")
    if src is None:
        out.append("GA4 غير متاح — لا رقم.")
    else:
        total = sum(n for _s, _c, n in src)
        direct = sum(n for s, _c, n in src if s == "(direct)")
        share = pct(direct, total)
        by_source: dict[str, int] = {}
        for s, _c, n in src:
            by_source[s] = by_source.get(s, 0) + n
        top = sorted(by_source.items(), key=lambda kv: -kv[1])[:5]
        out.append(f"جدد {total} · (direct) {direct} = {fmt_pct(share)} · الهدف < {DIRECT_MAX:.0f}%")
        out.append("  " + " · ".join(f"{s} {n}" for s, n in top))
        out.append(f"(القاعدة: {db['new_devices_week']} جهاز جديد في الأسبوع نفسه)")
        if share is not None:
            decisions.append(
                f"(direct) {share:.0f}% ≥ {DIRECT_MAX:.0f}% ⇒ فيه لينكات من غير كود — راجع كل رابط منشور"
                if share >= DIRECT_MAX else f"(direct) {share:.0f}% < {DIRECT_MAX:.0f}% ⇒ الروابط مكوّدة")
    out.append("")

    # 4. New-feature funnel
    out.append("④ ميزات «نور» الجديدة (GA4، مستخدمون فريدون)")
    events = ga4.get("events")
    versions = ga4.get("versions") or []
    by_version = sum(row[1] for row in versions)   # a user on two builds counts twice
    active_all = ga4.get("active_users") or by_version
    active_new = sum(row[1] for row in versions if version_tuple(row[0]) >= FEATURE_VERSION)
    if events is None:
        out.append("GA4 غير متاح — لا رقم.")
    else:
        def u(name: str) -> int:
            return events.get(name, [0, 0])[1]

        def n(name: str) -> int:
            return events.get(name, [0, 0])[0]
        v = ".".join(map(str, FEATURE_VERSION))
        out.append(f"على {v}+: {active_new} من {active_all} نشط ({fmt_pct(pct(active_new, active_all))}) — "
                   "الأرقام تحت لا تُقرأ قبل أن يصل أغلب النشطين")
        out.append(f"الأفق: ظهر {u('horizon_strip_shown')} → نُقر {u('horizon_strip_tapped')} "
                   f"({fmt_pct(pct(u('horizon_strip_tapped'), u('horizon_strip_shown')))}، الهدف ≥ 15%) "
                   f"→ فعل خلال 48 س {u('horizon_to_action_48h')} "
                   f"({fmt_pct(pct(u('horizon_to_action_48h'), u('horizon_strip_tapped')))})")
        per = n("lantern_lit") / active_new if active_new else None
        out.append(f"القناديل: {n('lantern_lit')} إضاءة على {u('lantern_lit')} مستخدم = "
                   + (f"{per:.2f}" if per is not None else "–") + f" لكل نشط على {v}+")
        out.append(f"الخطوة التالية: التزم {u('next_step_committed')} → ردّ على نور {u('companion_reply')} "
                   f"(من {u('companion_shown')} رأوا سطر نور)")
        out.append(f"ركن الطفل: فُتح {u('child_corner_opened')} → مهمة {u('child_corner_mission')} "
                   f"({fmt_pct(pct(u('child_corner_mission'), u('child_corner_opened')))})")
        out.append(f"المشاركة: لحظة {u('share_moment')} · إحالة مُطالَب بها {u('referral_claimed')}")
    out.append("")

    # 5. Health
    out.append("⑤ الصحة")
    out.append("الجلسات بلا أعطال (crash-free sessions): غير مقيسة — Crashlytics بلا تصدير "
               "BigQuery على مشروع almorabbi وبلا API للجلسات.")
    crash = ga4.get("crash")
    if crash:
        rate = crash["crash_free_users_rate"] * 100
        out.append(f"المستخدمون بلا أعطال (GA4): {rate:.2f}% — {crash['crash_affected_users']} "
                   f"متأثر من {ga4.get('active_users', '?')} · الهدف ≥ {CRASH_FREE_MIN}%")
        crashed = sorted((row for row in versions if len(row) > 2 and row[2]), key=lambda r: -r[2])
        if crashed:
            out.append("الأعطال حسب النسخة: " + " · ".join(f"{r[0]}: {r[2]}" for r in crashed[:6]))
        decisions.append(
            f"بلا أعطال {rate:.2f}% < {CRASH_FREE_MIN}% (مستخدمون، أشد من الجلسات) ⇒ أوقف التوسيع وأصلح"
            if rate < CRASH_FREE_MIN else
            f"بلا أعطال {rate:.2f}% ≥ {CRASH_FREE_MIN}% (مستخدمون لا جلسات) ⇒ لا عائق")
    else:
        out.append("المستخدمون بلا أعطال (GA4): غير متاح.")
    vit = ga4.get("vitals")
    if vit and vit.get("crash_rate") is not None:
        out.append(f"Play vitals: معدل الأعطال {vit['crash_rate'] * 100:.2f}% من {vit['user_days']} "
                   f"مستخدم-يوم ({vit['days']} أيام، آخرها {vit['last_day']} — متأخر يومين عادةً)")
    else:
        out.append("Play vitals: لا صفوف للأسبوع.")
    if versions:
        top = sorted(versions, key=lambda x: -x[1])[:6]
        out.append("النسخ: " + " · ".join(f"{r[0]} {fmt_pct(pct(r[1], by_version))}" for r in top))
    out.append("")

    # 6. Decisions
    out.append("⑥ القرارات")
    out += [f"• {d}" for d in decisions] or ["• لا قرار هذا الأسبوع"]
    errors = ga4.get("errors") or []
    if not ga4:
        out += ["", "⚠️ لم تصل بيانات GA4 — أقسام ②③④⑤ ناقصة."]
    elif errors:
        out += ["", "⚠️ أخطاء جلب: " + " | ".join(errors)[:600]]
    out += ["", "التعريفات: الفعل = سؤال للمساعد، أو تقدّم في درس، أو عادة، أو مهمة طفل، "
            "أو تحدٍّ، أو ردّ على متابعة، أو خطوة من خطة الأسبوع، أو علامة رمضان، أو بدء رحلة "
            "الصلاة (family_actions.py)؛ فتح التطبيق وحده ليس فعلًا. "
            "D1 قاعدة = ظهر الجهاز في اليوم التالي للتثبيت. D7 فعل = فعل في الأيام ٧–١٣. "
            "D1/D7 GA4 = cohortSpec. القرار من العيّنة الأكبر، ولا قرار تحت "
            f"{MIN_SAMPLE} تثبيتًا."]
    return "\n".join(out)


# ── delivery ─────────────────────────────────────────────────────────────────

def _chunk(text: str, limit: int = _TG_LIMIT) -> list[str]:
    chunks, cur = [], ""
    for line in text.split("\n"):
        if cur and len(cur) + len(line) + 1 > limit:
            chunks.append(cur.rstrip())
            cur = ""
        cur += line + "\n"
    if cur.strip():
        chunks.append(cur.rstrip())
    return chunks or [""]


def send_telegram(token: str, chat_id: str, text: str) -> list[int]:
    """Plain text (no parse_mode: «D1 8% < 10%» would break HTML). Returns the
    message ids Telegram created — the proof it arrived; raises otherwise."""
    ids = []
    for part in _chunk(text):
        data = urllib.parse.urlencode({"chat_id": chat_id, "text": part}).encode()
        req = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage",
                                     data=data, method="POST")
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = json.loads(resp.read())
        if not body.get("ok"):
            raise RuntimeError(f"Telegram rejected: {body.get('description')}")
        ids.append(body["result"]["message_id"])
    return ids


def _cairo_hour(now_utc: datetime) -> int:
    from zoneinfo import ZoneInfo  # noqa: PLC0415
    return now_utc.astimezone(ZoneInfo("Africa/Cairo")).hour


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Weekly launch report (read-only)")
    ap.add_argument("--db", default=str(_DB), help="path to conversations.db")
    ap.add_argument("--db-json", help="compose from saved --emit-db-json output")
    ap.add_argument("--emit-db-json", action="store_true",
                    help="print the database aggregates as JSON and stop")
    ap.add_argument("--ga4-json", help="GA4 bundle from --fetch-ga4 (a file, or - for stdin)")
    ap.add_argument("--fetch-ga4", action="store_true",
                    help="print the GA4 + Play vitals + spend bundle as JSON and stop")
    ap.add_argument("--via-ssh", metavar="HOST",
                    help="laptop half: fetch GA4, then run the container half on HOST")
    ap.add_argument("--container", default="tg_backend")
    ap.add_argument("--keyfile", default=str(_ROOT / "scripts" / "play_service_account.json"))
    ap.add_argument("--spend-csv", help=f"spend CSV (default {_SPEND_CSV.relative_to(_ROOT)})")
    ap.add_argument("--cohort-days", type=int, default=120,
                    help="per-code window, like campaign_report.py (default 120)")
    ap.add_argument("--only-at-cairo-hour", type=int,
                    help="exit quietly unless it is this hour in Cairo (DST-proof cron)")
    ap.add_argument("--dry-run", action="store_true", help="print instead of sending")
    args = ap.parse_args(argv)

    now = datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)
    if args.only_at_cairo_hour is not None and _cairo_hour(
            now.replace(tzinfo=timezone.utc)) != args.only_at_cairo_hour:
        print(f"skip: not {args.only_at_cairo_hour}:00 in Cairo")
        return 0

    if args.fetch_ga4 or args.via_ssh:
        bundle = fetch_ga4(args.keyfile, now.date(), args.cohort_days)
        spend_path = Path(args.spend_csv) if args.spend_csv else None
        if spend_path and spend_path.exists():
            bundle["spend"] = read_spend_csv(spend_path)
            bundle["spend_source"] = str(spend_path)
        if args.fetch_ga4:
            print(json.dumps(bundle, ensure_ascii=False))
            return 0
        remote = (f"docker exec -i -w /app {args.container} python "
                  "ops/scripts/launch_weekly_report.py --ga4-json -"
                  f" --cohort-days {args.cohort_days}"
                  + (" --dry-run" if args.dry_run else ""))
        proc = subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=20",
                               args.via_ssh, remote], input=json.dumps(bundle),
                              text=True, capture_output=True, timeout=600)
        sys.stdout.write(proc.stdout)
        sys.stderr.write(proc.stderr)
        return proc.returncode

    if args.db_json:
        db = json.loads(Path(args.db_json).read_text(encoding="utf-8"))
    else:
        db_path = Path(args.db)
        if not db_path.exists():
            print(f"Error: database {db_path} does not exist", file=sys.stderr)
            return 1
        db = collect_db(db_path, now, args.cohort_days)
        if args.emit_db_json:
            print(json.dumps(db, ensure_ascii=False))
            return 0

    ga4 = None
    if args.ga4_json:
        raw = sys.stdin.read() if args.ga4_json == "-" else Path(args.ga4_json).read_text(encoding="utf-8")
        ga4 = json.loads(raw) if raw.strip() else None
    spend, spend_source = (ga4 or {}).get("spend"), (ga4 or {}).get("spend_source")
    if spend is None:
        path = Path(args.spend_csv) if args.spend_csv else _SPEND_CSV
        if path.exists():
            spend, spend_source = read_spend_csv(path), str(path.relative_to(_ROOT)
                                                            if path.is_relative_to(_ROOT) else path)
    report = compose(db, ga4, spend, spend_source)

    if args.dry_run:
        print(report)
        return 0
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        print("Error: TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set — nothing sent.",
              file=sys.stderr)
        print(report)
        return 1
    try:
        ids = send_telegram(token, chat_id, report)
    except Exception as e:  # noqa: BLE001
        print(f"Telegram send failed: {type(e).__name__}: {e}"[:300], file=sys.stderr)
        return 1
    print(f"Launch report sent to Telegram: message_id {ids}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
