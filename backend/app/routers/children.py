"""
Children router — Phase 5.

Endpoints (all require Bearer auth — see AuthMiddleware):

  POST /api/children
      Body: {name, age_group, gender?, avatar_emoji?}
      Returns: {id, name, age_group, gender, avatar_emoji, created_at, updated_at}
      Side-effect: row linked to the device_id from the Bearer token.

  GET  /api/children/{id}/progress
      Returns: {child_id, device_id, lessons: [...],
                streak_days, last_completed_at, fetched_at}
      Authorization: the child must belong to the requester's device.

The progress PATCH lives in `routers/program.py` to keep all
`/api/program/...` mutating endpoints in one place.

Cross-cutting:
  * All age_group values are validated against `CANONICAL_AGE_GROUPS`
    (the same enum used by the curriculum content layer).
  * 404 on cross-device access (we do NOT leak the existence of a
    child that belongs to another device).
  * 422 on validation errors (FastAPI's Pydantic v2 / manual checks).
"""
from __future__ import annotations

import re
import sqlite3
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field, field_validator

from app.config.guardrails_loader import load_child_surface_policy
from app.core.taxonomy import CANONICAL_AGE_GROUPS, map_profile_age_to_band
from app.db.init_db import get_conn
from app.services import child_budget, child_missions, family_agreement
from app.services.coach_service import CHALLENGE_TOPICS

router = APIRouter()

# ── Pydantic models ──────────────────────────────────────────────────────


class ChildCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    age_group: str
    gender: Optional[str] = Field(default=None, max_length=20)
    avatar_emoji: Optional[str] = Field(default=None, max_length=8)

    @field_validator("age_group")
    @classmethod
    def _validate_age_group(cls, v: str) -> str:
        if v not in CANONICAL_AGE_GROUPS:
            raise ValueError(
                f"age_group غير صالح. القيم المسموحة: {sorted(CANONICAL_AGE_GROUPS)}"
            )
        return v

    @field_validator("name")
    @classmethod
    def _strip_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name لا يمكن أن يكون فارغاً")
        return v

    @field_validator("avatar_emoji")
    @classmethod
    def _validate_emoji(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        # A simple sanity check: 1-6 grapheme-ish chars; not perfect but
        # rejects multi-line / control-character input. Surrogate-pair
        # emojis (4-byte) take 2 chars in UTF-16 / 1 codepoint.
        if not re.match(r"^[\U0001F000-\U0010FFFF\U00002600-\U000027BF\U0001F300-\U0001FAFF\u2600-\u27BF\u200D\uFE0F]+$", v):
            raise ValueError("avatar_emoji يجب أن يكون إيموجي واحد أو أكثر")
        return v


class ChildUpdateRequest(BaseModel):
    """Phase 7 — all fields optional; the client only sends what
    it wants to change. Empty payload is a 422 (we require at least
    one field) so the client doesn't silently no-op."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=80)
    age_group: Optional[str] = Field(default=None, max_length=10)
    gender: Optional[str] = Field(default=None, max_length=20)
    avatar_emoji: Optional[str] = Field(default=None, max_length=8)

    @field_validator("age_group")
    @classmethod
    def _validate_age_group(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if v not in CANONICAL_AGE_GROUPS:
            raise ValueError(
                f"age_group غير صالح. القيم المسموحة: {sorted(CANONICAL_AGE_GROUPS)}"
            )
        return v

    @field_validator("name")
    @classmethod
    def _strip_name(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("name لا يمكن أن يكون فارغاً")
        return v

    @field_validator("avatar_emoji")
    @classmethod
    def _validate_emoji(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if not re.match(r"^[\U0001F000-\U0010FFFF\U00002600-\U000027BF\U0001F300-\U0001FAFF\u2600-\u27BF\u200D\uFE0F]+$", v):
            raise ValueError("avatar_emoji يجب أن يكون إيموجي واحد أو أكثر")
        return v

    def has_any_field(self) -> bool:
        return any(
            getattr(self, f) is not None
            for f in ("name", "age_group", "gender", "avatar_emoji")
        )


class ChildResponse(BaseModel):
    id: int
    name: str
    age_group: str
    gender: Optional[str]
    avatar_emoji: Optional[str]
    created_at: str
    updated_at: str


class ChallengeRequest(BaseModel):
    """«رحلة الطفل» — set the child's current challenge. The key must be one
    of the curated `CHALLENGE_TOPICS`; the topic/domain are derived server-side
    so the coach pipeline stays grounded."""

    challenge_key: str
    note: Optional[str] = Field(default=None, max_length=300)

    @field_validator("challenge_key")
    @classmethod
    def _validate_key(cls, v: str) -> str:
        if v not in CHALLENGE_TOPICS:
            raise ValueError(
                f"challenge_key غير صالح. القيم المسموحة: {sorted(CHALLENGE_TOPICS)}"
            )
        return v


# ── Helpers ──────────────────────────────────────────────────────────────


def _row_to_child(row: sqlite3.Row) -> ChildResponse:
    return ChildResponse(
        id=row["id"],
        name=row["name"],
        age_group=row["age_group"],
        gender=row["gender"],
        avatar_emoji=row["avatar_emoji"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _require_device_id(request: Request) -> str:
    """Pull the device_id that the auth middleware attached to request.state."""
    device_id = getattr(request.state, "device_id", None)
    if not device_id:
        # Should be unreachable on protected routes, but defensive.
        raise HTTPException(status_code=401, detail="مطلوب توثيق.")
    return device_id


def _load_owned_child(
    conn: sqlite3.Connection, child_id: int, device_id: str
) -> sqlite3.Row:
    """Load a child by id AND verify device ownership.

    Returns the row on success. Raises HTTPException(404) otherwise —
    we never leak the existence of a child belonging to another
    device.
    """
    row = conn.execute(
        "SELECT * FROM child_profiles WHERE id = ?", (child_id,)
    ).fetchone()
    if row is None or row["device_id"] != device_id:
        raise HTTPException(status_code=404, detail="طفل غير موجود.")
    return row


# ── Streak calculation (Phase 6) ────────────────────────────────────────
#
# A "streak day" is a UTC calendar day on which the user completed
# at least one lesson. The streak is the run of consecutive days
# ending at today (or yesterday — a streak is allowed to skip today
# while it is still morning, but breaks the day *after* a gap).
#
# Examples (UTC dates):
#   completed_dates = {2026-06-08, 2026-06-07, 2026-06-06}
#   today = 2026-06-08 → streak_days = 3
#
#   completed_dates = {2026-06-07, 2026-06-06, 2026-06-05}
#   today = 2026-06-08 → streak_days = 3  (streak "alive" — user
#                                         has not done today's lesson
#                                         yet, but the gap-free run
#                                         from yesterday back is
#                                         still credited)
#
#   completed_dates = {2026-06-06}
#   today = 2026-06-08 → streak_days = 0  (gap of 2 days)
#
# `last_completed_at` is the timestamp of the most recent completion
# (UTC, ISO 8601) — surfaced to the UI so it can render a "X days
# since last lesson" affordance when streak = 0.


def _parse_iso_utc_date(s: Optional[str]) -> Optional[date]:
    if not s:
        return None
    try:
        # Accept both "2026-06-08T12:00:00Z" and "2026-06-08T12:00:00+00:00".
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return datetime.fromisoformat(s).date()
    except (TypeError, ValueError):
        return None


def _compute_streak(
    completion_dates: list[date],
    today: date,
) -> tuple[int, Optional[date]]:
    """Return (streak_days, last_completed_date)."""
    if not completion_dates:
        return 0, None

    unique = sorted(set(completion_dates), reverse=True)
    last_completed = unique[0]

    # Anchor: today if user has completed today, else yesterday.
    if last_completed == today:
        anchor = today
    elif last_completed == today - timedelta(days=1):
        anchor = today - timedelta(days=1)
    else:
        return 0, last_completed

    streak = 0
    expected = anchor
    for d in unique:
        if d == expected:
            streak += 1
            expected = expected - timedelta(days=1)
        elif d < expected:
            # Gap — stop counting.
            break
    return streak, last_completed


# ── Routes ───────────────────────────────────────────────────────────────


@router.post(
    "/children",
    status_code=201,
    response_model=ChildResponse,
    summary="Create a child profile for the current device",
)
def create_child(payload: ChildCreateRequest, request: Request) -> ChildResponse:
    device_id = _require_device_id(request)
    conn = get_conn()
    try:
        cur = conn.execute(
            """
            INSERT INTO child_profiles
                (device_id, name, age_group, gender, avatar_emoji)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                device_id,
                payload.name,
                payload.age_group,
                payload.gender,
                payload.avatar_emoji,
            ),
        )
        conn.commit()
        new_id = cur.lastrowid
        row = conn.execute(
            "SELECT * FROM child_profiles WHERE id = ?", (new_id,)
        ).fetchone()
        return _row_to_child(row)
    finally:
        conn.close()


@router.get(
    "/children/{child_id}/progress",
    summary="Fetch lesson_progress for a child (must belong to this device)",
)
def get_child_progress(
    child_id: int,
    request: Request,
    path_id: Optional[str] = None,
):
    device_id = _require_device_id(request)
    conn = get_conn()
    try:
        _load_owned_child(conn, child_id, device_id)

        # Scoped to THIS child. child_id = 0 rows are legacy progress written
        # before any child profile existed — surfaced to every child rather
        # than lost.
        sql = (
            "SELECT lesson_id, path_id, status, started_at, completed_at "
            "FROM lesson_progress WHERE device_id = ? AND child_id IN (?, 0)"
        )
        params: list = [device_id, child_id]
        if path_id is not None:
            sql += " AND path_id = ?"
            params.append(path_id)
        sql += " ORDER BY completed_at DESC"
        rows = conn.execute(sql, params).fetchall()
        lessons = [
            {
                "lesson_id": r["lesson_id"],
                "path_id": r["path_id"],
                "status": r["status"],
                "started_at": r["started_at"],
                "completed_at": r["completed_at"],
            }
            for r in rows
        ]

        # Streak is computed across ALL completed lessons for THIS child
        # (path filter doesn't apply to the streak — a child can be on
        # multiple paths).
        completion_dates: list[date] = []
        last_completed_at: Optional[str] = None
        for r in conn.execute(
            "SELECT completed_at FROM lesson_progress "
            "WHERE device_id = ? AND child_id IN (?, 0) AND status = 'completed' "
            "ORDER BY completed_at DESC",
            (device_id, child_id),
        ).fetchall():
            d = _parse_iso_utc_date(r["completed_at"])
            if d is not None:
                completion_dates.append(d)
            if last_completed_at is None and r["completed_at"]:
                last_completed_at = r["completed_at"]

        streak_days, _ = _compute_streak(
            completion_dates,
            today=datetime.now(timezone.utc).date(),
        )

        # Daily login streak (v10): counts consecutive calendar days on which
        # the app was opened for this child. We upsert today's row idempotently
        # and compute the run from the stored dates, so opening the app daily
        # increments the streak even when no lesson is completed.
        today_str = datetime.utcnow().strftime("%Y-%m-%d")
        conn.execute(
            """
            INSERT INTO daily_login_streaks (device_id, child_id, date)
            VALUES (?, ?, ?)
            ON CONFLICT(device_id, child_id, date) DO NOTHING
            """,
            (device_id, child_id, today_str),
        )
        login_dates_rows = conn.execute(
            "SELECT date FROM daily_login_streaks "
            "WHERE device_id = ? AND child_id = ? ORDER BY date DESC",
            (device_id, child_id),
        ).fetchall()
        login_dates = [_parse_iso_utc_date(r["date"]) for r in login_dates_rows]
        login_dates = [d for d in login_dates if d is not None]
        daily_login_streak, _ = _compute_streak(
            login_dates,
            today=datetime.now(timezone.utc).date(),
        )

        return {
            "child_id": child_id,
            "device_id": device_id,
            "lessons": lessons,
            "streak_days": streak_days,
            "daily_login_streak": daily_login_streak,
            "last_completed_at": last_completed_at,
            "fetched_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        }
    finally:
        conn.close()


# ── «رحلة الطفل» — current challenge (feeds the proactive coach) ──────────


def _challenge_row_to_dict(row: Optional[sqlite3.Row]) -> Optional[dict]:
    if row is None:
        return None
    return {
        "challenge_key": row["challenge_key"],
        "topic": row["topic"],
        "domain": row["domain"],
        "note": row["note"],
        "started_at": row["started_at"],
    }


def _clear_todays_coach_tip(
    conn: sqlite3.Connection, device_id: str, child_id: int
) -> None:
    """Invalidate today's cached coach tip so the next fetch reflects the
    new/cleared challenge same-day instead of waiting until tomorrow."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    try:
        conn.execute(
            "DELETE FROM coach_tips WHERE device_id = ? AND child_id = ? AND date = ?",
            (device_id, child_id, today),
        )
    except sqlite3.Error:
        pass  # coach_tips may not exist yet on a fresh DB — harmless


@router.get(
    "/children/{child_id}/challenge",
    summary="Get the child's active current-challenge (or null)",
)
def get_challenge(child_id: int, request: Request):
    device_id = _require_device_id(request)
    conn = get_conn()
    try:
        _load_owned_child(conn, child_id, device_id)
        row = conn.execute(
            "SELECT challenge_key, topic, domain, note, started_at "
            "FROM child_challenges "
            "WHERE device_id = ? AND child_id = ? AND status = 'active' "
            "ORDER BY id DESC LIMIT 1",
            (device_id, child_id),
        ).fetchone()
        return {"child_id": child_id, "challenge": _challenge_row_to_dict(row)}
    finally:
        conn.close()


@router.get(
    "/children/{child_id}/screen-usage",
    summary="What the child's screen and listening time looked like on a day",
)
def get_screen_usage(child_id: int, request: Request,
                     on_date: Optional[str] = Query(None, alias="date"),
                     tz_offset_minutes: int = 0):
    """The parent's view of the budget.

    Screen and listening are reported as separate numbers on purpose. Adding
    them would recreate the single "hours today" figure that the policy exists
    to argue against — forty minutes of a dark screen and a recitation is not
    the same thing as forty minutes of a game, and a parent deciding what to
    do next needs to see which one it was.
    """
    device_id = _require_device_id(request)
    conn = get_conn()
    try:
        _load_owned_child(conn, child_id, device_id)
        age_group = conn.execute(
            "SELECT age_group FROM child_profiles WHERE id = ?", (child_id,)
        ).fetchone()["age_group"]
    finally:
        conn.close()

    policy = getattr(request.app.state, "child_surface_policy", None) \
        or load_child_surface_policy()
    band = policy.band(map_profile_age_to_band(age_group))
    local_date = on_date or child_budget.local_date_for(
        datetime.now(timezone.utc), tz_offset_minutes
    )
    usage = child_budget.today_usage(child_id, local_date, policy)
    return {
        "child_id": child_id,
        "date": local_date,
        "band": band.band,
        "budget_seconds": band.daily_budget_minutes * 60,
        "screen_off_budget_seconds": band.screen_off_daily_budget_minutes * 60,
        **usage,
    }


@router.put(
    "/children/{child_id}/challenge",
    summary="Set/replace the child's current challenge",
)
def set_challenge(child_id: int, payload: ChallengeRequest, request: Request):
    device_id = _require_device_id(request)
    topic, domain = CHALLENGE_TOPICS[payload.challenge_key]
    conn = get_conn()
    try:
        _load_owned_child(conn, child_id, device_id)
        # Resolve any existing active challenge, then insert the new one.
        conn.execute(
            "UPDATE child_challenges SET status = 'resolved', "
            "resolved_at = datetime('now') "
            "WHERE device_id = ? AND child_id = ? AND status = 'active'",
            (device_id, child_id),
        )
        conn.execute(
            "INSERT INTO child_challenges "
            "(device_id, child_id, challenge_key, topic, domain, note) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (device_id, child_id, payload.challenge_key, topic, domain, payload.note),
        )
        _clear_todays_coach_tip(conn, device_id, child_id)
        conn.commit()
        return {
            "child_id": child_id,
            "challenge": {
                "challenge_key": payload.challenge_key,
                "topic": topic,
                "domain": domain,
                "note": payload.note,
            },
        }
    finally:
        conn.close()


@router.delete(
    "/children/{child_id}/challenge",
    summary="Resolve (clear) the child's current challenge",
)
def clear_challenge(child_id: int, request: Request):
    device_id = _require_device_id(request)
    conn = get_conn()
    try:
        _load_owned_child(conn, child_id, device_id)
        conn.execute(
            "UPDATE child_challenges SET status = 'resolved', "
            "resolved_at = datetime('now') "
            "WHERE device_id = ? AND child_id = ? AND status = 'active'",
            (device_id, child_id),
        )
        _clear_todays_coach_tip(conn, device_id, child_id)
        conn.commit()
        return {"child_id": child_id, "challenge": None}
    finally:
        conn.close()


# ── Phase 7 — list / update / reset ──────────────────────────────────────


@router.get(
    "/children",
    summary="List the children profiles owned by the current device",
)
def list_children(request: Request):
    """Phase 7 — supports multi-child UIs in the future. Phase 6's
    onboarding still creates a single child, but the settings screen
    and child-switcher will read from this list."""
    device_id = _require_device_id(request)
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM child_profiles WHERE device_id = ? "
            "ORDER BY created_at ASC",
            (device_id,),
        ).fetchall()
        return {
            "device_id": device_id,
            "count": len(rows),
            "children": [_row_to_child(r) for r in rows],
        }
    finally:
        conn.close()


@router.patch(
    "/children/{child_id}",
    response_model=ChildResponse,
    summary="Update name / age_group / gender / avatar_emoji of a child",
)
def update_child(
    child_id: int,
    payload: ChildUpdateRequest,
    request: Request,
) -> ChildResponse:
    """Phase 7 settings screen. Empty payloads are rejected (422) so
    the client can't accidentally no-op."""
    if not payload.has_any_field():
        raise HTTPException(
            status_code=422,
            detail="يجب إرسال حقل واحد على الأقل للتعديل.",
        )
    device_id = _require_device_id(request)
    conn = get_conn()
    try:
        _load_owned_child(conn, child_id, device_id)
        sets: list[str] = []
        params: list = []
        for field in ("name", "age_group", "gender", "avatar_emoji"):
            v = getattr(payload, field)
            if v is not None:
                sets.append(f"{field} = ?")
                params.append(v)
        sets.append("updated_at = datetime('now')")
        params.append(child_id)
        conn.execute(
            f"UPDATE child_profiles SET {', '.join(sets)} WHERE id = ?",
            params,
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM child_profiles WHERE id = ?", (child_id,)
        ).fetchone()
        return _row_to_child(row)
    finally:
        conn.close()


@router.delete(
    "/children/{child_id}/progress",
    summary="Reset all lesson_progress rows for the given child",
)
def reset_child_progress(child_id: int, request: Request):
    """Phase 7 — the "reset streak" affordance. Wipes every
    `lesson_progress` row whose `device_id` matches the requester's
    AND whose `lesson_id` is in the same set the GET endpoint would
    return (i.e. all device progress, not path-scoped).

    The child profile itself (name, age_group, avatar_emoji) is
    untouched. After the call:
      * GET /api/children/{id}/progress → streak_days = 0
      * PathDetailScreen's ProgressIndicator → 0 / N
      * PathDetailScreen's StreakChip → "🔥 ابدأ سلسلتك اليوم"

    Idempotent: a second call on an already-reset child returns
    `deleted: 0` (still 200) — no error needed.
    """
    device_id = _require_device_id(request)
    conn = get_conn()
    try:
        _load_owned_child(conn, child_id, device_id)
        # Only THIS child's rows (plus unattributed legacy child_id=0 rows,
        # which the GET also surfaces for every child) — never siblings'.
        cur = conn.execute(
            "DELETE FROM lesson_progress WHERE device_id = ? AND child_id IN (?, 0)",
            (device_id, child_id),
        )
        deleted = cur.rowcount
        conn.commit()
        return {
            "child_id": child_id,
            "device_id": device_id,
            "deleted": deleted,
            "reset_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        }
    finally:
        conn.close()


@router.delete(
    "/children/{child_id}",
    summary="Delete a child profile",
)
def delete_child(child_id: int, request: Request):
    """Phase 7 — remove a child profile entirely. Ownership-enforced via
    device_id (a missing/unowned child raises 404 via _load_owned_child)."""
    device_id = _require_device_id(request)
    conn = get_conn()
    try:
        _load_owned_child(conn, child_id, device_id)
        conn.execute(
            "DELETE FROM child_profiles WHERE id = ? AND device_id = ?",
            (child_id, device_id),
        )
        conn.commit()
        return {
            "child_id": child_id,
            "deleted": True,
            "deleted_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        }
    finally:
        conn.close()


# ── Family media agreement ─────────────────────────────────────────────────

class AgreementClauseIn(BaseModel):
    applies_to: str = Field(pattern="^(child|parent|both)$")
    text_ar: str = Field(min_length=1, max_length=400)
    clause_key: Optional[str] = None
    is_custom: bool = False
    sort_order: int = 0


class AgreementDraftIn(BaseModel):
    clauses: list[AgreementClauseIn] = Field(min_length=1, max_length=40)


@router.get(
    "/children/{child_id}/agreement/clauses/suggested",
    summary="Suggested clause pairs for the child's age band",
)
def suggested_agreement_clauses(child_id: int, request: Request):
    """Pairs, always. The UI shows the parent's clause next to the child's so
    the trade is visible while they edit rather than discovered after."""
    device_id = _require_device_id(request)
    conn = get_conn()
    try:
        _load_owned_child(conn, child_id, device_id)
        age_group = conn.execute(
            "SELECT age_group FROM child_profiles WHERE id = ?", (child_id,)
        ).fetchone()["age_group"]
    finally:
        conn.close()
    band = map_profile_age_to_band(age_group)
    return {"child_id": child_id, "age_band": band,
            "pairs": family_agreement.load_clause_bank(band),
            "clauses": family_agreement.suggested_clauses(band)}


@router.get("/children/{child_id}/agreement", summary="The child's agreement")
def get_agreement(child_id: int, request: Request):
    device_id = _require_device_id(request)
    conn = get_conn()
    try:
        _load_owned_child(conn, child_id, device_id)
    finally:
        conn.close()
    return {"child_id": child_id,
            "agreement": family_agreement.get_current(device_id, child_id)}


@router.post("/children/{child_id}/agreement", summary="Create or replace the draft")
def put_agreement_draft(child_id: int, body: AgreementDraftIn, request: Request):
    device_id = _require_device_id(request)
    conn = get_conn()
    try:
        _load_owned_child(conn, child_id, device_id)
    finally:
        conn.close()

    result = family_agreement.save_draft(
        device_id, child_id, [c.model_dump() for c in body.clauses]
    )
    if not result["ok"]:
        # 422 rather than 400: the draft is well-formed JSON that fails a rule
        # about what an agreement is, and the message names which rule.
        raise HTTPException(status_code=422, detail={
            "error": result["reason"],
            "message_key": f"agreement.{result['reason']}",
        })
    return result["agreement"]


@router.post("/children/{child_id}/agreement/sign", summary="Parent signs the draft")
def sign_agreement_as_parent(child_id: int, request: Request):
    device_id = _require_device_id(request)
    conn = get_conn()
    try:
        _load_owned_child(conn, child_id, device_id)
    finally:
        conn.close()

    result = family_agreement.sign(device_id, child_id, "parent")
    if not result["ok"]:
        raise HTTPException(status_code=409, detail={"error": result["reason"]})
    return result


# ── The parent's evening: one card, one button ─────────────────────────────

class MissionConfirmItem(BaseModel):
    mission_id: int
    confirmed: bool = True
    note: Optional[str] = Field(default=None, max_length=280)


class MissionConfirmIn(BaseModel):
    items: list[MissionConfirmItem] = Field(min_length=1, max_length=50)


@router.get("/children/missions/pending",
            summary="Every mission across every child that is waiting on the parent")
def pending_missions(request: Request):
    device_id = _require_device_id(request)
    return {"pending": child_missions.pending_for_device(device_id)}


@router.post("/children/missions/confirm",
             summary="Settle several missions at once")
def confirm_missions(body: MissionConfirmIn, request: Request):
    """A parent with three children presses one button, not six.

    Batching is the feature: the evening notification opens onto a list, and
    a confirmation flow that costs one tap per child is a flow that gets
    abandoned by the second child.
    """
    device_id = _require_device_id(request)
    result = child_missions.confirm_batch(
        device_id, [i.model_dump() for i in body.items]
    )
    return result


@router.get("/children/{child_id}/today",
            summary="The parent's one-screen view of a child's day")
def child_day_summary(child_id: int, request: Request,
                      tz_offset_minutes: int = 0):
    """Screen, listening, the mission, the agreement — on one card.

    Assembled server-side so the app makes one call rather than four, and so
    the numbers a parent compares are computed from the same instant.

    Screen and listening stay separate all the way out. Adding them recreates
    the single "hours today" figure this whole feature exists to argue
    against: forty minutes of a dark screen and a recitation is not the same
    thing as forty minutes of a game.
    """
    device_id = _require_device_id(request)
    conn = get_conn()
    try:
        _load_owned_child(conn, child_id, device_id)
        row = conn.execute(
            "SELECT name, age_group FROM child_profiles WHERE id = ?", (child_id,)
        ).fetchone()
    finally:
        conn.close()

    policy = getattr(request.app.state, "child_surface_policy", None) \
        or load_child_surface_policy()
    band_name = map_profile_age_to_band(row["age_group"])
    band = policy.band(band_name)
    now = datetime.now(timezone.utc)
    local_date = child_budget.local_date_for(now, tz_offset_minutes)
    usage = child_budget.today_usage(child_id, local_date, policy)

    agreement = family_agreement.get_active(device_id, child_id)
    mission = child_missions.today_mission(device_id, child_id, band_name, local_date)

    month_start = local_date[:8] + "01"
    leverage = child_missions.leverage(
        child_id, month_start, screen_seconds=_month_screen_seconds(child_id, month_start)
    )

    return {
        "child_id": child_id,
        "child_name": row["name"],
        "date": local_date,
        "band": band_name,
        "screen": {
            "counted_seconds": usage["counted_seconds"],
            "budget_seconds": band.daily_budget_minutes * 60,
        },
        "listening": {
            "counted_seconds": usage["screen_off_seconds"],
            "budget_seconds": band.screen_off_daily_budget_minutes * 60,
        },
        "mission": mission,
        "agreement": None if agreement is None else {
            "status": agreement["status"],
            "next_review_date": agreement["next_review_date"],
            "review_due": agreement["review_due"],
            "clauses_on_parent": agreement["clauses_on_parent"],
            "clauses_on_child": agreement["clauses_on_child"],
        },
        "month": leverage,
    }


def _month_screen_seconds(child_id: int, month_start: str) -> int:
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT COALESCE(SUM(counted_seconds), 0) AS s "
            "FROM child_screen_sessions WHERE child_id = ? AND local_date >= ? "
            "AND surface NOT IN ('screen_off', 'agreement')",
            (child_id, month_start),
        ).fetchone()
        return int(row["s"])
    finally:
        conn.close()
