"""
Community stats router — Phase 3 (social proof / network-effect feel).

A single public, privacy-safe aggregate endpoint: no PII, just counts derived
from anonymous device data. Surfaced on the app Home as «X أب يربّون بثقة معنا»
to give the «you're part of something» feeling that lifts engagement and
retention — the cheapest network-effect lever.

  GET /api/stats/community → {families, lessons_completed, active_this_week}

Public: /api/stats is not in the auth-middleware protected prefixes, so no
token is required (the numbers are aggregate and non-identifying).
"""
from __future__ import annotations

from fastapi import APIRouter

from app.db.init_db import get_conn

router = APIRouter(prefix="/stats", tags=["stats"])


def _count(conn, sql: str) -> int:
    try:
        row = conn.execute(sql).fetchone()
        return int(row[0]) if row and row[0] is not None else 0
    except Exception:  # noqa: BLE001 — a missing table just reads as 0
        return 0


@router.get("/community")
def community_stats() -> dict:
    """Aggregate, non-PII social-proof counts for the Home surface."""
    conn = get_conn()
    try:
        families = _count(
            conn, "SELECT COUNT(DISTINCT device_id) FROM child_profiles"
        )
        lessons = _count(
            conn,
            "SELECT COUNT(*) FROM lesson_progress WHERE status = 'completed'",
        )
        active = _count(
            conn,
            "SELECT COUNT(DISTINCT device_id) FROM lesson_progress "
            "WHERE completed_at >= datetime('now', '-7 days')",
        )
    finally:
        conn.close()
    return {
        "families": families,
        "lessons_completed": lessons,
        "active_this_week": active,
    }
