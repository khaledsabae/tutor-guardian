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

import os
import sqlite3

from fastapi import APIRouter, Header, HTTPException

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


@router.get("/ops-llm")
def ops_llm_metrics(
    x_ops_token: str | None = Header(default=None),
    days: int = 7,
) -> dict:
    """Aggregate LLM cost/latency metrics for external monitoring (OMAR).

    Growth plan §5.1 (تتبع التكلفة/مستخدم) + §4.4 (p95). No PII — counts,
    tokens and latencies only. Gated by OPS_METRICS_TOKEN when set; open in
    dev when the env var is absent.
    """
    expected = os.environ.get("OPS_METRICS_TOKEN", "")
    if expected and x_ops_token != expected:
        raise HTTPException(status_code=403, detail="forbidden")
    days = max(1, min(days, 30))

    from app.config.llm_config import LLM
    from app.services.ai_gateway import _TELEMETRY_DB

    out: dict = {"window_days": days}
    try:
        tconn = sqlite3.connect(_TELEMETRY_DB)
        tconn.row_factory = sqlite3.Row
        try:
            row = tconn.execute(
                "SELECT COUNT(*) AS total, SUM(ok) AS ok FROM llm_calls "
                "WHERE ts >= datetime('now', ?)",
                (f"-{days} days",),
            ).fetchone()
            total = int(row["total"] or 0)
            ok = int(row["ok"] or 0)
            lat = [
                int(r["latency_ms"])
                for r in tconn.execute(
                    "SELECT latency_ms FROM llm_calls "
                    "WHERE ts >= datetime('now', ?) AND ok = 1 "
                    "AND latency_ms IS NOT NULL",
                    (f"-{days} days",),
                )
            ]
            lat.sort()
            month_tokens = {
                r["provider"]: int(r["tok"] or 0)
                for r in tconn.execute(
                    "SELECT provider, "
                    "SUM(COALESCE(prompt_tokens,0)+COALESCE(completion_tokens,0)) AS tok "
                    "FROM llm_calls "
                    "WHERE ts >= strftime('%Y-%m-01 00:00:00','now') "
                    "GROUP BY provider"
                )
            }
            month_calls = {
                r["provider"]: int(r["c"] or 0)
                for r in tconn.execute(
                    "SELECT provider, COUNT(*) AS c FROM llm_calls "
                    "WHERE ts >= strftime('%Y-%m-01 00:00:00','now') AND ok = 1 "
                    "GROUP BY provider"
                )
            }
        finally:
            tconn.close()
        valve_used = month_tokens.get("deepseek_fallback", 0)
        out.update(
            calls=total,
            success_rate=round(ok / total, 3) if total else None,
            p95_latency_ms=lat[int(len(lat) * 0.95)] if len(lat) >= 20 else (lat[-1] if lat else None),
            avg_latency_ms=round(sum(lat) / len(lat), 1) if lat else None,
            month_tokens_by_provider=month_tokens,
            month_calls_by_provider=month_calls,
            # §5.1 KPI: share of answers served with zero inference cost.
            cache_hit_rate=round(
                (month_calls.get("answer_cache", 0) + month_calls.get("story_cache", 0))
                / sum(month_calls.values()),
                3,
            ) if sum(month_calls.values()) else None,
            valve={
                "enabled": LLM.deepseek_fallback_enabled,
                "used_tokens": valve_used,
                "cap_tokens": LLM.deepseek_fallback_monthly_token_cap,
                "used_pct": round(
                    valve_used / LLM.deepseek_fallback_monthly_token_cap, 3
                ) if LLM.deepseek_fallback_monthly_token_cap else None,
            },
        )
    except Exception as exc:  # noqa: BLE001 — monitoring must degrade, not 500
        out["telemetry_error"] = str(exc)

    conn = get_conn()
    try:
        active_month = _count(
            conn,
            "SELECT COUNT(DISTINCT device_id) FROM chat_sessions "
            "WHERE created_at >= strftime('%Y-%m-01 00:00:00','now')",
        )
    finally:
        conn.close()
    out["active_chat_devices_month"] = active_month
    month_total = sum(out.get("month_tokens_by_provider", {}).values())
    out["month_tokens_per_active_device"] = (
        round(month_total / active_month) if active_month else None
    )
    return out
