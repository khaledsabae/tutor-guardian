"""The family media agreement — the frame the rest of the child surface sits in.

Not to be confused with `CovenantService` in the app, which is a rewards list
that happens to be called «عهد». This is the other thing: what the family
agreed about screens, signed by both sides.

Two properties are load-bearing and both are enforced here rather than left to
the UI:

**Every clause names who it binds.** A clause bank where each rule points at
the child is a list of orders with a signature line, and the research this
feature rests on — the family media plan — is about an agreement. Suggested
clauses are therefore emitted in pairs, and an agreement that ends up with
nothing on the parent is refused before it can be signed.

**Signing is per clause, then per person.** The child ticks each clause and
then signs; a single OK for the whole page is a signature on something
unread, which is the failure mode paper contracts have and we get to avoid.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from app.db.init_db import get_conn
from app.services import content_lang

_UTC = timezone.utc

CLAUSES_DIR = (
    Path(__file__).resolve().parents[3] / "knowledge_base" / "curriculum" / "agreements"
)

# How long an agreement stands before the app asks the family to look at it
# again. A media plan a nine-year-old signed and nobody reopened is a document,
# not an agreement.
REVIEW_AFTER_DAYS = 30

_APPLIES_TO = ("child", "parent", "both")


def _now_iso() -> str:
    return datetime.now(_UTC).isoformat(timespec="seconds")


# ── The clause bank ────────────────────────────────────────────────────────

def load_clause_bank(age_band: str,
                     lang: Optional[str] = None) -> list[dict[str, Any]]:
    """Suggested clause pairs for a band, or [] when none are published.

    `lang` picks the translated bank when one exists and falls back to Arabic
    when it does not — see content_lang.localised for why the fallback matters
    more than the translation here.
    """
    path = content_lang.localised(CLAUSES_DIR, f"clauses_{age_band}.json", lang)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    if not data.get("is_published", True):
        return []
    return list(data.get("pairs", []))


def suggested_clauses(age_band: str,
                      lang: Optional[str] = None) -> list[dict[str, Any]]:
    """The bank flattened into rows ready to store — child clause then the
    parent clause that answers it, so the pairing survives into the UI."""
    rows: list[dict[str, Any]] = []
    for order, pair in enumerate(load_clause_bank(age_band, lang)):
        key = pair.get("key")
        if pair.get("child"):
            rows.append({"applies_to": "child", "clause_key": key,
                         "text_ar": pair["child"], "sort_order": order * 2})
        if pair.get("parent"):
            rows.append({"applies_to": "parent", "clause_key": key,
                         "text_ar": pair["parent"], "sort_order": order * 2 + 1})
    return rows


# ── Reads ──────────────────────────────────────────────────────────────────

def _clauses_for(conn: sqlite3.Connection, agreement_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT id, applies_to, clause_key, text_ar, is_custom, sort_order, "
        "acknowledged_at FROM agreement_clauses WHERE agreement_id = ? "
        "ORDER BY sort_order, id",
        (agreement_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def _row_to_agreement(conn: sqlite3.Connection, row: sqlite3.Row) -> dict[str, Any]:
    clauses = _clauses_for(conn, row["id"])
    return {
        "id": row["id"],
        "child_id": row["child_id"],
        "version": row["version"],
        "status": row["status"],
        "signed_by_parent_at": row["signed_by_parent_at"],
        "signed_by_child_at": row["signed_by_child_at"],
        "next_review_date": row["next_review_date"],
        "created_at": row["created_at"],
        "clauses": clauses,
        "clauses_on_parent": sum(1 for c in clauses if c["applies_to"] in ("parent", "both")),
        "clauses_on_child": sum(1 for c in clauses if c["applies_to"] in ("child", "both")),
        "review_due": _review_due(row["next_review_date"]),
    }


def _review_due(next_review_date: Optional[str]) -> bool:
    if not next_review_date:
        return False
    try:
        return date.fromisoformat(next_review_date) <= datetime.now(_UTC).date()
    except ValueError:
        return False


def get_active(device_id: str, child_id: int) -> Optional[dict[str, Any]]:
    """The child's live agreement, or None. `None` is what the entry gate
    keys on, so it must mean exactly "nothing signed by both sides"."""
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM family_agreements WHERE device_id = ? AND child_id = ? "
            "AND status = 'active' ORDER BY id DESC LIMIT 1",
            (device_id, child_id),
        ).fetchone()
        return _row_to_agreement(conn, row) if row else None
    finally:
        conn.close()


def get_current(device_id: str, child_id: int) -> Optional[dict[str, Any]]:
    """The active agreement if there is one, otherwise the open draft."""
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM family_agreements WHERE device_id = ? AND child_id = ? "
            "AND status IN ('active', 'draft') "
            "ORDER BY CASE status WHEN 'active' THEN 0 ELSE 1 END, id DESC LIMIT 1",
            (device_id, child_id),
        ).fetchone()
        return _row_to_agreement(conn, row) if row else None
    finally:
        conn.close()


def awaits_child_signature(device_id: str, child_id: int) -> bool:
    """A parent has signed a draft and the child has not.

    The signing screen is registered, routed and tested — and unreachable in
    practice, because the only thing that opens it is the server refusing a
    surface, and that refusal is behind AGREEMENT_REQUIRED, which is off and
    stays off until the floor build is live. So a parent signs, hands over the
    device, and the child lands on the habit screen having never seen the
    agreement they are supposed to agree to.

    This is the other door: not a refusal, just a fact the client can act on.
    """
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT 1 FROM family_agreements "
            "WHERE device_id = ? AND child_id = ? AND status = 'draft' "
            "AND signed_by_parent_at IS NOT NULL "
            "AND signed_by_child_at IS NULL LIMIT 1",
            (device_id, child_id),
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def has_active_agreement(device_id: str, child_id: int) -> bool:
    return get_active(device_id, child_id) is not None


# ── Writes ─────────────────────────────────────────────────────────────────

def save_draft(device_id: str, child_id: int,
               clauses: list[dict[str, Any]]) -> dict[str, Any]:
    """Create or replace the draft for a child.

    Refuses a draft that binds only the child. The check lives here and not in
    the UI because the UI is where a rushed parent would skip it, and an
    agreement with nothing on the parent is the exact artefact this feature
    exists to replace.
    """
    cleaned = []
    for order, c in enumerate(clauses):
        applies_to = (c.get("applies_to") or "").strip()
        text = (c.get("text_ar") or "").strip()
        if applies_to not in _APPLIES_TO or not text:
            continue
        cleaned.append({
            "applies_to": applies_to,
            "clause_key": c.get("clause_key"),
            "text_ar": text[:400],
            "is_custom": 1 if c.get("is_custom") else 0,
            "sort_order": c.get("sort_order", order),
        })

    if not cleaned:
        return {"ok": False, "reason": "no_clauses"}
    if not any(c["applies_to"] in ("parent", "both") for c in cleaned):
        return {"ok": False, "reason": "nothing_on_the_parent"}
    if not any(c["applies_to"] in ("child", "both") for c in cleaned):
        return {"ok": False, "reason": "nothing_on_the_child"}

    conn = get_conn()
    try:
        existing = conn.execute(
            "SELECT id FROM family_agreements WHERE device_id = ? AND child_id = ? "
            "AND status = 'draft' ORDER BY id DESC LIMIT 1",
            (device_id, child_id),
        ).fetchone()
        if existing:
            agreement_id = existing["id"]
            conn.execute("DELETE FROM agreement_clauses WHERE agreement_id = ?",
                         (agreement_id,))
            # A redrafted agreement is unsigned again by definition.
            conn.execute(
                "UPDATE family_agreements SET signed_by_parent_at = NULL, "
                "signed_by_child_at = NULL WHERE id = ?", (agreement_id,)
            )
        else:
            active = conn.execute(
                "SELECT MAX(version) AS v FROM family_agreements "
                "WHERE device_id = ? AND child_id = ?", (device_id, child_id),
            ).fetchone()
            version = (active["v"] or 0) + 1
            cur = conn.execute(
                "INSERT INTO family_agreements (device_id, child_id, version, status) "
                "VALUES (?, ?, ?, 'draft')",
                (device_id, child_id, version),
            )
            agreement_id = cur.lastrowid

        conn.executemany(
            "INSERT INTO agreement_clauses (agreement_id, applies_to, clause_key, "
            "text_ar, is_custom, sort_order) VALUES (?, ?, ?, ?, ?, ?)",
            [(agreement_id, c["applies_to"], c["clause_key"], c["text_ar"],
              c["is_custom"], c["sort_order"]) for c in cleaned],
        )
        conn.commit()
        row = conn.execute("SELECT * FROM family_agreements WHERE id = ?",
                           (agreement_id,)).fetchone()
        return {"ok": True, "agreement": _row_to_agreement(conn, row)}
    finally:
        conn.close()


def acknowledge_clause(device_id: str, child_id: int, clause_id: int) -> dict[str, Any]:
    """The child says they understood this one clause."""
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT c.id FROM agreement_clauses c "
            "JOIN family_agreements a ON a.id = c.agreement_id "
            "WHERE c.id = ? AND a.device_id = ? AND a.child_id = ? "
            "AND a.status = 'draft'",
            (clause_id, device_id, child_id),
        ).fetchone()
        if row is None:
            return {"ok": False, "reason": "clause_not_found"}
        conn.execute("UPDATE agreement_clauses SET acknowledged_at = ? WHERE id = ?",
                     (_now_iso(), clause_id))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


def sign(device_id: str, child_id: int, by: str) -> dict[str, Any]:
    """Sign the draft as `parent` or `child`; activate once both have.

    A child cannot sign until every clause that binds them is acknowledged.
    Signing what you have not read is the thing paper contracts get wrong.
    """
    if by not in ("parent", "child"):
        return {"ok": False, "reason": "unknown_signer"}

    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM family_agreements WHERE device_id = ? AND child_id = ? "
            "AND status = 'draft' ORDER BY id DESC LIMIT 1",
            (device_id, child_id),
        ).fetchone()
        if row is None:
            return {"ok": False, "reason": "no_draft"}

        if by == "child":
            unread = conn.execute(
                "SELECT COUNT(*) AS n FROM agreement_clauses WHERE agreement_id = ? "
                "AND applies_to IN ('child', 'both') AND acknowledged_at IS NULL",
                (row["id"],),
            ).fetchone()["n"]
            if unread:
                return {"ok": False, "reason": "clauses_not_acknowledged",
                        "remaining": unread}

        column = "signed_by_parent_at" if by == "parent" else "signed_by_child_at"
        conn.execute(f"UPDATE family_agreements SET {column} = ? WHERE id = ?",
                     (_now_iso(), row["id"]))

        row = conn.execute("SELECT * FROM family_agreements WHERE id = ?",
                           (row["id"],)).fetchone()
        activated = False
        if row["signed_by_parent_at"] and row["signed_by_child_at"]:
            review = (datetime.now(_UTC).date() + timedelta(days=REVIEW_AFTER_DAYS))
            conn.execute(
                "UPDATE family_agreements SET status = 'archived' "
                "WHERE device_id = ? AND child_id = ? AND status = 'active'",
                (device_id, child_id),
            )
            conn.execute(
                "UPDATE family_agreements SET status = 'active', next_review_date = ? "
                "WHERE id = ?", (review.isoformat(), row["id"]),
            )
            activated = True

        conn.commit()
        row = conn.execute("SELECT * FROM family_agreements WHERE id = ?",
                           (row["id"],)).fetchone()
        return {"ok": True, "activated": activated,
                "agreement": _row_to_agreement(conn, row)}
    finally:
        conn.close()
