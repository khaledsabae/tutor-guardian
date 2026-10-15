"""The canonical registry of meaningful family actions («عدّاد صادق»).

One list decides what counts as a parenting action in a family's week — the
weekly funnel report (ops/scripts/weekly_funnel_report.py) and the lantern
counter /api/family/week (`family_week` below) both read it, so the report and
the lanterns can never disagree about which rows are acts.

Standing rules (نور والقناديل plan):
* Worship acts NEVER light the weekly lanterns. The lanterns are for parenting
  acts only: a lesson, a question (at most one a day), a follow-up answered, a
  mission confirmed, a weekly-plan step taken. Which rows are worship is
  declared here, per source (`ActionSource.worship`), not buried in a query;
  adhkar and Qur'an tables are not sources at all.
* Du'as are answered only by their id from the guarded `family_adhkar` bank,
  never free text — no ayah is ever used as an app metaphor.

Semantics are lifted verbatim from the funnel report: (table, timestamp
column, extra WHERE). Timestamps go through SQLite's datetime() because the
tables disagree on format. Tables or columns missing from a database are
skipped by the reader, not fatal.

The report counts EVERY row of every source (its North Star numerator is
unchanged — a Ramadan «تمّ» still makes a family active there). The lanterns
read the same rows minus the worship ones. They differ in one more way, on
purpose: the report uses rolling UTC 7-day windows; the lanterns use the
family's local ISO week.
"""
from __future__ import annotations

import logging
import sqlite3
from datetime import date, datetime, timedelta, timezone
from typing import Any, NamedTuple, Optional

logger = logging.getLogger(__name__)

# `ActionSource.worship` value: every row of the source is an act of worship.
WORSHIP_ALL = "ALL"


class ActionSource(NamedTuple):
    """Where one kind of family act is recorded, and what it is.

    * `table`, `column`, `where` — read by the funnel report as before
      (`where` is extra SQL appended to its WHERE; "" for none).
    * `kind` — the act's label on the lantern counter (/api/family/week).
    * `worship` — which of its rows are acts of worship, which never light a
      weekly lantern: "" none, WORSHIP_ALL every row, otherwise an SQL
      predicate on the table's own columns (NULL-safe: written with IS).
    """

    table: str
    column: str
    where: str
    kind: str
    worship: str = ""


# A Prayer Journey task («صلّيتها») is a child_missions row too
# (services/prayer_journey.py: source = 'prayer_journey') — a prayer, not a
# parenting step.
_PRAYER_TASK = "source IS 'prayer_journey'"

ACTION_SOURCES: tuple[ActionSource, ...] = (
    ActionSource("lesson_progress", "started_at", "", "lesson"),
    ActionSource("lesson_progress", "updated_at", "", "lesson"),
    ActionSource("lesson_progress", "completed_at", "", "lesson"),
    # ميزان العادات: the "worship" category is صلاة الفجر، ورد القرآن، قيام الليل…
    # (routers/value_tracking.py _DEFAULT_HABITS) — worship, not a lantern.
    ActionSource("habits_value_events", "created_at", "", "habit",
                 "category IS 'worship'"),
    ActionSource("child_missions", "assigned_at", "", "mission", _PRAYER_TASK),
    ActionSource("child_missions", "claimed_at", "", "mission", _PRAYER_TASK),
    ActionSource("child_missions", "confirmed_at", "", "mission", _PRAYER_TASK),
    ActionSource("child_challenges", "started_at", "", "challenge"),
    # Family programs (backend schema v34): the report counts a Ramadan «تمّ»
    # and a Prayer Journey started as acts of an active family. Both are
    # worship, so they never light a lantern — Ramadan has its own street of
    # lanterns, a family calendar without numbers. Absent tables are skipped.
    ActionSource("ramadan_marks", "created_at", "", "ramadan_mark", WORSHIP_ALL),
    ActionSource("prayer_journeys", "created_at", "", "prayer_journey", WORSHIP_ALL),
    # A follow-up answered (نور والقناديل, Phase 0): the parent came back and
    # reported whether the advice worked — the truest parenting act there is.
    ActionSource("followups", "answered_at", "", "followup"),
    # A weekly-plan step ticked (Phase 3, PUT /children/{id}/weekly-plan/marks).
    # The plan's worship item (bank keys worship_<group>_<n>) is worship.
    ActionSource("weekly_plan_marks", "created_at", "", "plan_tick",
                 "substr(item_id, 1, 8) IS 'worship_'"),
)

# A question to the assistant: a user row in chat_messages joined to its
# session's device — the report's rule (get_action_events). It is not a row
# of ACTION_SOURCES because it needs that join. On the lanterns it counts at
# most once per local day.
QUESTION_KIND = "question"


def lantern_sources() -> tuple[ActionSource, ...]:
    """The sources that can light a lantern: every one not wholly worship."""
    return tuple(s for s in ACTION_SOURCES if s.worship != WORSHIP_ALL)


# ── Reading one device's acts ──────────────────────────────────────────────

# The column naming what the act was about, for a cheap human title. Nothing
# else is read: no note, no strategy, no habit name the parent may have typed.
_TITLE_REF = {
    "lesson_progress": "lesson_id",
    "child_missions": "mission_key",
    "weekly_plan_marks": "item_id",
}

_MAX_OFFSET = 14 * 60
_WEEKS_SHOWN = 8


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc_naive(moment: datetime) -> datetime:
    if moment.tzinfo is None:
        return moment
    return moment.astimezone(timezone.utc).replace(tzinfo=None)


def _parse_ts(value: Optional[str]) -> Optional[datetime]:
    """`datetime()`-normalised SQLite text → naive UTC datetime."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {r[1] for r in conn.execute(f'PRAGMA table_info("{table}")')}


def device_acts(conn: sqlite3.Connection, device_id: str) -> list[dict[str, Any]]:
    """Every act of one device that may light a lantern, all time.

    Worship rows are left out here, at the source. Not yet deduplicated: a
    lesson row yields up to three acts (started, updated, completed) — see
    `lanterns`. Each act: kind, at (naive UTC), child_id (None when the row
    is the family's, not a child's), row (source table and rowid), ref (what
    a title may be looked up by).
    """
    acts: list[dict[str, Any]] = []
    cols_cache: dict[str, set[str]] = {}
    for src in lantern_sources():
        if src.table not in cols_cache:
            cols_cache[src.table] = _columns(conn, src.table)
        cols = cols_cache[src.table]
        if src.column not in cols or "device_id" not in cols:
            continue
        ref = _TITLE_REF.get(src.table)
        select = [
            "rowid AS rid",
            f"datetime({src.column}) AS ts",
            "child_id" if "child_id" in cols else "NULL AS child_id",
            f"{ref} AS ref" if ref in cols else "NULL AS ref",
        ]
        worship = f"AND NOT ({src.worship})" if src.worship else ""
        sql = (f'SELECT {", ".join(select)} FROM "{src.table}" '
               f"WHERE device_id = ? AND {src.column} IS NOT NULL {worship} {src.where}")
        try:
            rows = conn.execute(sql, (device_id,)).fetchall()
        except sqlite3.OperationalError:
            # A store whose schema lacks a column the worship rule reads:
            # skipped like a missing table, never counted unfiltered.
            logger.warning("family_actions: %s.%s unreadable — skipped",
                           src.table, src.column, exc_info=True)
            continue
        for r in rows:
            ts = _parse_ts(r["ts"])
            if ts is None:
                continue
            acts.append({
                "kind": src.kind,
                "at": ts,
                "child_id": r["child_id"] or None,      # 0 = a device-level legacy row
                "row": (src.table, r["rid"]),
                "ref": r["ref"],
            })

    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' "
        "AND name IN ('chat_messages', 'chat_sessions')")}
    if tables == {"chat_messages", "chat_sessions"}:
        for r in conn.execute(
            "SELECT datetime(cm.created_at) AS ts FROM chat_messages cm "
            "JOIN chat_sessions cs ON cs.id = cm.session_id "
            "WHERE cs.device_id = ? AND cm.role = 'user'", (device_id,),
        ):
            ts = _parse_ts(r["ts"])
            if ts is not None:
                acts.append({"kind": QUESTION_KIND, "at": ts, "child_id": None,
                             "row": None, "ref": None})
    return acts


def lanterns(acts: list[dict[str, Any]], tz_offset_minutes: int) -> list[dict[str, Any]]:
    """One lantern per source row per local day, and one question a local day.

    A lesson started and finished on the same evening is one lantern, not
    three; a mission assigned, claimed and confirmed the same day, one. The
    earliest moment of the day is the lantern's. Adds `local_day`.
    """
    out: dict[tuple, dict[str, Any]] = {}
    for act in sorted(acts, key=lambda a: a["at"]):
        day = (act["at"] + timedelta(minutes=tz_offset_minutes)).date()
        key = (QUESTION_KIND, day) if act["kind"] == QUESTION_KIND else (act["row"], day)
        if key not in out:
            out[key] = {**act, "local_day": day}
    return list(out.values())


def _monday(day: date) -> date:
    return day - timedelta(days=day.weekday())


class _Titles:
    """A short label from the hand-written banks, or None. Never personal:
    lesson and mission titles and weekly-plan step texts are curriculum."""

    def __init__(self, lang: Optional[str]):
        from app.services import content_lang
        self.lang = content_lang.normalise(lang)
        self._missions: dict[str, dict[str, str]] = {}

    def _mission(self, key: str) -> Optional[str]:
        # Bank ids carry their band: mission_<band>_<slug>.
        parts = key.split("_")
        if len(parts) < 3:
            return None
        band = parts[1]
        if band not in self._missions:
            from app.services import child_missions
            self._missions[band] = {
                m["id"]: m.get("title_ar", "")
                for m in child_missions.load_missions(band, self.lang)
            }
        return self._missions[band].get(key) or None

    def of(self, act: dict[str, Any]) -> Optional[str]:
        ref = act.get("ref")
        if not ref:
            return None
        try:
            if act["kind"] == "lesson":
                from app import curriculum_loader as cl
                lesson = cl.get_lesson(ref, lang=self.lang) or {}
                return lesson.get("title") or None
            if act["kind"] == "mission":
                return self._mission(ref)
            if act["kind"] == "plan_tick":
                from app.services import weekly_plan
                return weekly_plan.item_text(ref, self.lang)
        except Exception:  # a title is decoration: never fail the counter for one
            logger.warning("family_actions: no title for %s %s", act["kind"], ref,
                           exc_info=True)
        return None


def family_week(device_id: str, *, tz_offset_minutes: Optional[int] = None,
                now: Optional[datetime] = None, lang: Optional[str] = None) -> dict[str, Any]:
    """This device's lanterns: its acts in the current LOCAL ISO week (Monday
    start — the week weekly_plan.py builds plans for), whether the week is lit,
    how many weeks were ever lit, and the last eight weeks (oldest first).

    `tz_offset_minutes` — the device's UTC offset; when None, the one it last
    reported (the weekly plan's rule: a missing offset is not UTC), else UTC.
    """
    from app.core.times import iso_z
    from app.db.init_db import get_conn
    from app.services import weekly_plan

    if tz_offset_minutes is None:
        tz_offset_minutes = weekly_plan.stored_offset(device_id)
    offset = max(-_MAX_OFFSET, min(_MAX_OFFSET, int(tz_offset_minutes or 0)))
    moment = _as_utc_naive(now or _utcnow())
    _, monday = weekly_plan.iso_week((moment + timedelta(minutes=offset)).date())

    conn = get_conn()
    try:
        lit = lanterns(device_acts(conn, device_id), offset)
    finally:
        conn.close()

    weeks = {_monday(a["local_day"]) for a in lit}
    this_week = [a for a in lit if _monday(a["local_day"]) == monday]
    titles = _Titles(lang)
    shown = [monday - timedelta(weeks=k) for k in range(_WEEKS_SHOWN - 1, -1, -1)]
    return {
        "week_start": monday.isoformat(),
        "acts": [
            {"kind": a["kind"], "at": iso_z(a["at"]), "child_id": a["child_id"],
             "title": titles.of(a)}
            for a in this_week
        ],
        "lit_this_week": bool(this_week),
        # Every week ever lit, up to this one. Derived from the acts, so it
        # never resets — only erasing the acts themselves can lower it.
        "lit_weeks_total": len({w for w in weeks if w <= monday}),
        "last_8": [{"week_start": w.isoformat(), "lit": w in weeks} for w in shown],
    }
