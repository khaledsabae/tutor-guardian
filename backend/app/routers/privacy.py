"""
Privacy router.

Serves the static privacy-policy.md at GET /privacy-policy.
Required by Google Play for the data-safety form.

The file path is resolved relative to PROJECT_ROOT (the repo root) so the
content is served from the deployed repo, not bundled into the Docker image.

And `api_router` (mounted under /api, Bearer auth) holds the two delete-all
paths:

* DELETE /api/privacy/memory erases everything the assistant has learned about
  the caller's children — every table in MEMORY_TABLES. A table that stores
  per-device memory and is missing from that tuple survives a parent's "forget
  everything"; tests/test_child_memory.py fails if a v30 table is left out.
* DELETE /api/privacy/account?confirm=true deletes the account: every row tied
  to the device in every table, found by introspection at call time (any
  table with a `device_id` column, whatever its age), plus the rows that hang
  off them, plus the Google identity. Google Play requires in-app account
  deletion for an app with sign-in. tests/test_account_deletion.py fails if a
  table exists that this module has not classified.
"""
import logging
import os
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, Response

from app.core.contact import SUPPORT_EMAIL
from app.core.proof import require_device_proof
from app.db.init_db import get_conn

logger = logging.getLogger(__name__)

router = APIRouter()
api_router = APIRouter()

# Every table holding what the assistant learned about a device's children,
# with the column that scopes a row to the device. Schema v30. The memory
# switch (MEMORY_SETTINGS_TABLE) is not deleted by a memory erase: an erase is
# not «turn memory back on» (A4) — it keeps the parent's choice and bumps the
# erase generation so an extraction in flight cannot write after it.
MEMORY_TABLES: tuple[tuple[str, str], ...] = (
    ("child_facts", "device_id"),
    ("followups", "device_id"),
    ("weekly_plans", "device_id"),
)
MEMORY_SETTINGS_TABLE = "child_memory_settings"


def erase_device_memory(device_id: str) -> dict[str, int]:
    """Delete every MEMORY_TABLES row of one device, in one transaction."""
    from app.services.child_memory import bump_generation

    conn = get_conn()
    try:
        counts: dict[str, int] = {}
        conn.execute("BEGIN IMMEDIATE")
        for table, column in MEMORY_TABLES:
            cur = conn.execute(f"DELETE FROM {table} WHERE {column} = ?", (device_id,))
            counts[table] = cur.rowcount
        bump_generation(conn, device_id)
        conn.commit()
        return counts
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@api_router.delete("/privacy/memory", summary="Forget everything about my children",
                   dependencies=[Depends(require_device_proof)])
def delete_my_memory(request: Request):
    """The privacy delete-all for child memory: facts, follow-ups and weekly
    plans, for every child of the calling device. The memory switch keeps its
    setting."""
    device_id = getattr(request.state, "device_id", None)
    if not device_id:
        raise HTTPException(status_code=401, detail="مطلوب توثيق.")
    counts = erase_device_memory(device_id)
    logger.info("privacy: device memory erased (%d rows)", sum(counts.values()))
    return {
        "deleted": counts,
        "deleted_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }

# Project root (…/tutor-guardian), overridable for containers.
PROJECT_ROOT = Path(os.environ.get("PROJECT_ROOT", Path(__file__).resolve().parents[3]))
_PRIVACY_CANDIDATES = [
    PROJECT_ROOT / "docs" / "privacy-policy.md",
    Path(__file__).resolve().parents[2] / "docs" / "privacy-policy.md",  # /app/docs/ inside container
    Path(__file__).resolve().parents[3] / "docs" / "privacy-policy.md",
]


def _is_servable(path: Path) -> bool:
    """Existing is not enough — the file has to be *readable* by this process.

    docs/ is bind-mounted into the container from the host, and the container
    runs as appuser (uid 10001) while the host files arrive by rsync owning
    uid 1000 mode 0600. `is_file()` still passes on those (the directory is
    traversable), so a bare existence check let FileResponse start a 200,
    fail to open the file, and emit a truncated body — which Cloudflare turned
    into an opaque 520. Checking readability makes that an honest 503 instead.
    """
    return path.is_file() and os.access(path, os.R_OK)


def _resolve_privacy_policy_path() -> Path:
    """Find privacy-policy.md across the candidate locations.

    The container image has docs/ at /app/docs/, while dev mode puts it at
    PROJECT_ROOT/docs/. We try the env-driven path first, then fall back.
    """
    for candidate in _PRIVACY_CANDIDATES:
        if _is_servable(candidate):
            return candidate
    return _PRIVACY_CANDIDATES[0]  # default; endpoint will return 503


PRIVACY_POLICY_PATH = _resolve_privacy_policy_path()


@router.get("/privacy-policy", include_in_schema=False)
async def get_privacy_policy():
    """Serve the privacy policy as plain text/markdown."""
    # Re-checked per request, not just at import: docs/ is a bind mount whose
    # permissions can change under a running container.
    if not _is_servable(PRIVACY_POLICY_PATH):
        if PRIVACY_POLICY_PATH.is_file():
            logger.error(
                "Privacy policy file at %s exists but is not readable by uid %s",
                PRIVACY_POLICY_PATH,
                os.getuid(),
            )
        else:
            logger.error("Privacy policy file not found at %s", PRIVACY_POLICY_PATH)
        return Response(
            content=f"Privacy policy is temporarily unavailable. Please contact {SUPPORT_EMAIL}.",
            status_code=503,
            media_type="text/plain; charset=utf-8",
        )
    return FileResponse(
        path=str(PRIVACY_POLICY_PATH),
        media_type="text/markdown; charset=utf-8",
        headers={"Cache-Control": "public, max-age=300"},
    )


# ── The public deletion page ──────────────────────────────────────────────
#
# Google Play asks for a web route to request deletion that works for someone
# who no longer has the app. Served from code, not from docs/: docs/ is a bind
# mount whose permissions have broken the policy route before (see above), and
# this page must answer even then. System fonts only — no request leaves the
# visitor's browser for a third party.


DELETE_ACCOUNT_HTML = """<!doctype html>
<html lang="ar">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>حذف الحساب والبيانات — المربّي · Delete your account — Almorabbi</title>
<style>
  body { font-family: system-ui, -apple-system, "Segoe UI", Tahoma, sans-serif;
         max-width: 44rem; margin: 2rem auto; padding: 0 1rem; line-height: 1.7;
         color: #1f2933; }
  h1 { font-size: 1.5rem; } h2 { font-size: 1.15rem; margin-top: 1.6rem; }
  section { margin-bottom: 2.5rem; }
  a { color: #0b6e4f; }
  .box { background: #f4f7f6; border-radius: .6rem; padding: .8rem 1rem; }
</style>
</head>
<body>
<section dir="rtl" lang="ar">
<h1>حذف حسابك وبياناتك — المربّي</h1>

<h2>من داخل التطبيق</h2>
<ol>
  <li>افتح <b>الإعدادات</b>.</li>
  <li>اضغط <b>«حذف الحساب»</b> ثم أكّد.</li>
</ol>
<p>يُحذف فورًا كل ما يرتبط بهاتفك على خوادمنا: ملفات الأطفال وتقدّمهم، والأسئلة
وإجاباتها، وذاكرة الطفل والمتابعات وخطط الأسبوع، وأدوات المتابعة اليومية، وبيانات
وضع الطفل، والملاحظات وردودها، ورمز الإشعارات، والدعوات، والنسخ الاحتياطية، ورموز
الجلسة. وإن كنت سجّلت الدخول بحساب Google تُحذف كذلك بيانات كل هاتف مرتبط بالحساب،
وبيانات الحساب نفسه.</p>
<p>هذا الخيار موجود في إصدارات التطبيق التي تحويه؛ إن لم تجده فحدّث التطبيق أو اتبع
الطريقة التالية. وقبل الحذف يتحقق التطبيق تلقائيًا أن الطلب من هاتفك برسالة صامتة؛ فإن
تعذّر التحقق فاتبع الطريقة التالية. ولحذف جزء فقط: من شاشة ذاكرة الطفل تحذف معلومة واحدة أو كل ما يخصّ
طفلًا، ومن ملف الطفل تحذف الطفل وبياناته.</p>

<h2>دون التطبيق</h2>
<p class="box">راسلنا على
<a href="mailto:{email}?subject=%D8%B7%D9%84%D8%A8%20%D8%AD%D8%B0%D9%81%20%D8%A8%D9%8A%D8%A7%D9%86%D8%A7%D8%AA%20%2F%20Data%20deletion%20request">{email}</a>
بعنوان «طلب حذف بيانات».</p>
<ul>
  <li>إن كنت سجّلت الدخول بحساب Google: راسلنا من بريد ذلك الحساب، فنحذف كل البيانات
  المرتبطة به وبكل هاتف مرتبط به.</li>
  <li>إن لم تسجّل الدخول: بياناتك مرتبطة بمعرّف عشوائي أنشأه هاتفك، ولا نستطيع ربطه
  ببريدك. اكتب لنا ما يساعد على التعرّف عليها — الفترة التقريبية لاستعمال التطبيق،
  والاسم الأول والفئة العمرية لطفلك كما أدخلتهما — فنحذف ما نستطيع مطابقته بثقة،
  ونخبرك إن لم نجد شيئًا.</li>
</ul>
<p>ننفّذ الطلب خلال <b>30 يومًا</b> ونؤكّده لك بالبريد.</p>

<h2>ما لا يشمله الحذف</h2>
<p>سجلات تقنية لا تحمل أي معرّف لك أو لهاتفك، وتُحذف تلقائيًا خلال 90 يومًا على
الأكثر، والإحصاءات المجمّعة. وتبقى البيانات المحذوفة في النسخ الاحتياطية لقاعدة
البيانات 14 يومًا على الأكثر. وما يحفظه مزوّدو الخدمة (مثل Google وDeepSeek) يخضع
لسياساتهم.</p>
<p><a href="/privacy-policy">سياسة الخصوصية</a></p>
</section>

<hr>

<section dir="ltr" lang="en">
<h1>Delete your account and data — Almorabbi</h1>

<h2>In the app</h2>
<ol>
  <li>Open <b>Settings</b>.</li>
  <li>Tap <b>"Delete Account"</b> and confirm.</li>
</ol>
<p>Everything linked to your phone on our servers is deleted immediately: child
profiles and progress, questions and answers, child memory, follow-ups and weekly
plans, the daily tracking tools, child-mode data, feedback and replies, the
notification token, invites, backups and session tokens. If you signed in with
Google, the data of every phone linked to that account, and the account record
itself, are deleted too.</p>
<p>This option exists in app versions that include it; if you do not see it,
update the app or use the method below. Before deleting, the app checks
automatically, with a silent message, that the request comes from your phone; if
that check cannot work, use the method below. To delete only part of your data: on the
child-memory screen you can delete one item or everything about a child, and from
a child's profile you can delete that child and their data.</p>

<h2>Without the app</h2>
<p class="box">Email
<a href="mailto:{email}?subject=Data%20deletion%20request">{email}</a>
with the subject "Data deletion request".</p>
<ul>
  <li>If you signed in with Google: write from that Google account's address, and we
  delete all data linked to it and to every phone linked to it.</li>
  <li>If you never signed in: your data is linked only to a random identifier your
  phone created, which we cannot connect to your email address. Tell us what can
  help identify it — roughly when you used the app, and your child's first name and
  age group as you entered them — and we delete what we can match with confidence,
  or tell you if we find nothing.</li>
</ul>
<p>We complete the request within <b>30 days</b> and confirm by email.</p>

<h2>What deletion does not cover</h2>
<p>Technical logs that carry no identifier of you or your phone, which are deleted
automatically within 90 days at most, and aggregate statistics. Deleted data stays in
our database backups for at most 14 days. What our service providers (such as Google
and DeepSeek) keep is governed by their own policies.</p>
<p><a href="/privacy-policy">Privacy policy</a></p>
</section>
</body>
</html>
""".replace("{email}", SUPPORT_EMAIL)


@router.get("/delete-account", include_in_schema=False)
def delete_account_page():
    """How to delete an account — in the app, or by email without it."""
    return HTMLResponse(
        DELETE_ACCOUNT_HTML,
        headers={"Cache-Control": "public, max-age=300"},
    )


# ── Account deletion ──────────────────────────────────────────────────────
#
# Inventory checked against the production schema (read-only dump,
# 2026-10-04, schema v29): 34 tables. Production has NO foreign key on
# agreement_clauses or user_feedback, so cascades are not relied on anywhere —
# every dependent row is deleted explicitly, with foreign keys off for the
# transaction so the order of deletion cannot trip a RESTRICT either.

# Rows with no device_id that belong to a device through a parent row:
# (table, column, parent_table, parent_column).
DEPENDENT_TABLES: tuple[tuple[str, str, str, str], ...] = (
    ("chat_messages", "session_id", "chat_sessions", "id"),
    ("user_feedback", "session_id", "chat_sessions", "id"),
    ("routine_events", "routine_id", "child_daily_routines", "id"),
    ("agreement_clauses", "agreement_id", "family_agreements", "id"),
)

# A device referenced under a column with another name.
OTHER_DEVICE_COLUMNS: tuple[tuple[str, str], ...] = (
    ("referrals", "referrer_device"),
    ("referrals", "referred_device"),
)

# The Google identity behind a signed-in account (email, display name, and the
# zero-knowledge backups filed under it).
IDENTITY_TABLES: tuple[tuple[str, str], ...] = (
    ("parent_identities", "google_id"),
    ("user_backups", "google_id"),
)

# Tables that hold nothing tied to a device — and why. A new table must be
# added to one of these four lists or carry a device_id column; the test
# refuses an unclassified table.
NOT_DEVICE_DATA: dict[str, str] = {
    "schema_version": "schema bookkeeping",
    "referral_clicks": "a landing-page click (IP + code) before any device exists",
    "referral_click_days": "per-code daily click counts (PR #25): no IP, no device",
    "story_cache": "shared generated stories keyed by theme/age/gender; the "
                   "child's name is substituted on the way out, never stored",
    "tg_updates_seen": "Telegram webhook update ids (dedupe)",
    "donations": "the donations ledger carries no device id (today/donate branch)",
    # Transient tables that exist only inside a migration's transaction.
    "child_challenges_v27": "v27 migration scratch table",
    "lesson_progress_new": "lesson_progress migration scratch table",
}


def _table_columns(conn: sqlite3.Connection) -> dict[str, set[str]]:
    names = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
    )]
    return {n: {r[1] for r in conn.execute(f"PRAGMA table_info('{n}')")} for n in names}


def account_devices(conn: sqlite3.Connection, device_id: str,
                    tables: dict[str, set[str]]) -> tuple[list[str], list[str]]:
    """(devices, google_ids) that make up the caller's account.

    Signed out, the account is the device. Signed in, it is the Google
    identity — every device linked to it. A reinstall links a new device to
    the same identity and copies the children over (identity._merge_legacy_
    device_data), so deleting only the calling device would leave a full copy
    one sign-in away.
    """
    devices = {device_id}
    google_ids: list[str] = []
    if "identity_links" in tables:
        google_ids = [r[0] for r in conn.execute(
            "SELECT google_id FROM identity_links WHERE device_id = ?", (device_id,))]
        for g in google_ids:
            devices |= {r[0] for r in conn.execute(
                "SELECT device_id FROM identity_links WHERE google_id = ?", (g,))}
    return sorted(devices), google_ids


def erase_child(device_id: str, child_id: int) -> dict[str, int]:
    """Delete one child and every row tied to it, in one transaction.

    Every table with a `child_id` column — discovered at call time, so a table
    added later is covered without touching this code — plus the rows that
    hang off them with no child_id of their own (routine events, agreement
    clauses). Deleting only child_profiles left progress, coach tips (with the
    child's name and topic), missions and their notes, agreements, licences,
    scenario answers, screen sessions and streaks behind (PR #26 review, P3).
    Legacy lesson_progress rows (child_id 0) belong to the device, not a child,
    and stay.
    """
    conn = get_conn()
    try:
        conn.execute("PRAGMA foreign_keys = OFF")
        conn.execute("BEGIN IMMEDIATE")
        tables = _table_columns(conn)
        counts: Counter = Counter()
        for table, column, parent, parent_col in DEPENDENT_TABLES:
            pcols = tables.get(parent, set())
            if table in tables and "child_id" in pcols and "device_id" in pcols:
                cur = conn.execute(
                    f"DELETE FROM {table} WHERE {column} IN (SELECT {parent_col} FROM "
                    f"{parent} WHERE child_id = ? AND device_id = ?)",
                    (child_id, device_id),
                )
                counts[table] += cur.rowcount
        for table, cols in tables.items():
            if table == "child_profiles" or "child_id" not in cols:
                continue
            if "device_id" in cols:
                cur = conn.execute(
                    f"DELETE FROM {table} WHERE child_id = ? AND device_id = ?",
                    (child_id, device_id))
            else:
                cur = conn.execute(f"DELETE FROM {table} WHERE child_id = ?", (child_id,))
            counts[table] += cur.rowcount
        cur = conn.execute("DELETE FROM child_profiles WHERE id = ? AND device_id = ?",
                           (child_id, device_id))
        counts["child_profiles"] += cur.rowcount
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return {t: n for t, n in sorted(counts.items()) if n}


def erase_account(device_id: str) -> dict:
    """Delete every row tied to the caller's account, in one transaction."""
    conn = get_conn()
    try:
        # Off for this connection, before the transaction opens: production's
        # foreign keys are not the repository's, and every dependent is
        # deleted explicitly below anyway.
        conn.execute("PRAGMA foreign_keys = OFF")
        conn.execute("BEGIN IMMEDIATE")
        tables = _table_columns(conn)
        devices, google_ids = account_devices(conn, device_id, tables)
        marks = ",".join("?" * len(devices))
        counts: Counter = Counter()

        # 1. Children of device rows first: their subquery needs the parents.
        for table, column, parent, parent_col in DEPENDENT_TABLES:
            if table in tables and "device_id" in tables.get(parent, set()):
                cur = conn.execute(
                    f"DELETE FROM {table} WHERE {column} IN "
                    f"(SELECT {parent_col} FROM {parent} WHERE device_id IN ({marks}))",
                    devices,
                )
                counts[table] += cur.rowcount
        # 2. Every table that carries a device_id — discovered, not listed.
        for table, cols in tables.items():
            if "device_id" in cols:
                cur = conn.execute(
                    f"DELETE FROM {table} WHERE device_id IN ({marks})", devices)
                counts[table] += cur.rowcount
        # 3. The device under another name.
        for table, column in OTHER_DEVICE_COLUMNS:
            if column in tables.get(table, set()):
                cur = conn.execute(
                    f"DELETE FROM {table} WHERE {column} IN ({marks})", devices)
                counts[table] += cur.rowcount
        # 4. The Google identity itself.
        if google_ids:
            gmarks = ",".join("?" * len(google_ids))
            for table, column in IDENTITY_TABLES:
                if column in tables.get(table, set()):
                    cur = conn.execute(
                        f"DELETE FROM {table} WHERE {column} IN ({gmarks})", google_ids)
                    counts[table] += cur.rowcount
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return {
        "devices": len(devices),
        "signed_in": bool(google_ids),
        "deleted": {t: n for t, n in sorted(counts.items()) if n},
    }


@api_router.delete("/privacy/account", summary="Delete my account and all its data",
                   dependencies=[Depends(require_device_proof)])
def delete_my_account(request: Request, confirm: bool = Query(False)):
    """Everything tied to this device — and, when signed in with Google, to
    every device linked to that Google account: children, progress, chat,
    memory, push tokens, backups, the identity itself. The bearer token used
    for this call is revoked by it; the app starts over with a new session.

    `confirm=true` is required: an accidental DELETE must not be the way an
    account disappears.
    """
    device_id = getattr(request.state, "device_id", None)
    if not device_id:
        raise HTTPException(status_code=401, detail="مطلوب توثيق.")
    if not confirm:
        raise HTTPException(status_code=400, detail={
            "code": "confirm_required",
            "message": "أضف confirm=true لتأكيد حذف الحساب وكل بياناته.",
        })
    result = erase_account(device_id)
    logger.info(
        "privacy: account erased (%d device(s), signed_in=%s, %d rows)",
        result["devices"], result["signed_in"], sum(result["deleted"].values()),
    )
    return {**result, "deleted_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
