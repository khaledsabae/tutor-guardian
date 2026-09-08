"""
Quranic Linguistics Service — طبقة مساعدة مستقلة للتحليل اللغوي القرآني
========================================================================
يتصل بـ Bahouth MCP (https://bahouth.tafsir.net/mcp) عبر JSON-RPC over SSE.
الطبقة دي مش جزء من الـRAG الرئيسي — بتتنادى بس لما:
  - المستخدم يسأل عن جذر كلمة أو تكرارها في القرآن
  - المستخدم يسأل عن آيات موضوع معين
  - المستخدم يسأل عن قراءات آية أو خصائص كلمة

المميزات (نفس نمط tafsir_service.py):
  - Caching في SQLite على النص المُدخل (مش على root_id — الـid داخلي
    لنسخة v1.28.0 وممكن يتغير لو القاعدة اتحدثت)
  - Timeout قابل للضبط (الافتراضي 15ث — list_root_verses ممكن يرجّع
    صفحات كتير فـ 10ث مش كافي)
  - Fallback واضح لو السيرفر وقع أو مفيش نت
  - Normalize عربي على مدخل find_root قبل الإرسال (السيرفر حسّاس
    للتشكيل: «صبر» المجرد يشتغل، «صَبَرَ» المشكول بيرجع found=false)
  - مفيش PII بيتبعث — بس جذور وكلمات وأرقام آيات

التحقق العملي (2026-09-08):
  - initialize → 200, serverInfo "Bahouth Quranic Linguistic" v1.28.0
  - find_root("صبر") → found=true, root_id 234, frequency 103
  - سقف limit = 50 بالظبط، pagination بالـ offset (50+43=103 ✓)
  - verse_key بصيغة "2-255" (بشرطة، مش نقطتين)
  - list_topic_verses بياخد topic_id رقمي
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re as _re
import sqlite3
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

# ── Configuration ────────────────────────────────────────────────────────────
BAHOUTH_MCP_URL = os.environ.get(
    "BAHOUTH_MCP_URL", "https://bahouth.tafsir.net/mcp"
)
BAHOUTH_TIMEOUT = int(os.environ.get("BAHOUTH_TIMEOUT", "15"))  # seconds
BAHOUTH_CACHE_ENABLED = os.environ.get(
    "BAHOUTH_CACHE_ENABLED", "true"
).lower() in ("1", "true", "yes")
BAHOUTH_CACHE_TTL_DAYS = int(os.environ.get("BAHOUTH_CACHE_TTL_DAYS", "30"))
BAHOUTH_MAX_LIMIT = 50  # سقف السيرفر الفعلي (متحقق منه)

_TELEMETRY_DB = Path(__file__).resolve().parents[3] / "ops" / "sessions.db"


# ── Data types ──────────────────────────────────────────────────────────────
@dataclass
class RootResult:
    """نتيجة بحث جذر — معرف الجذر + تكراره في القرآن."""
    root_text: str
    found: bool
    root_id: int | None = None
    frequency: int | None = None
    cached: bool = False
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and self.found


@dataclass
class VerseListResult:
    """نتيجة قائمة آيات — مع pagination."""
    tool: str
    query_key: str
    verses: list[dict] = field(default_factory=list)
    total: int | None = None
    cached: bool = False
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None


# ── Arabic normalization (same as tafsir_service) ──────────────────────────
def _normalize_arabic(text: str) -> str:
    """Normalize Arabic so user input matches the server's plain-root lookup.

    Steps (order matters):
      1. Map alef-wasla (ٱ) and superscript alef (ٰ) to plain ا FIRST, because
         the superscript alef is a combining mark (Mn) that the NFD strip below
         would otherwise delete.
      2. NFD + drop combining marks (tashkeel: fatha/damma/kasra/sukun/shadda).
      3. Drop tatweel.
      4. Unify all alef variants (آ أ إ) and hamza carriers → ا.
      5. teh-marbuta → heh, alef-maksura → yeh.
    """
    s = text
    # 1. Superscript alef (U+0670) + alef wasla (U+0671) → plain ا (before NFD).
    s = s.replace("\u0670", "\u0627").replace("\u0671", "\u0627")
    # 2. Remove combining marks (tashkeel, shadda, etc.).
    s = "".join(
        ch for ch in unicodedata.normalize("NFD", s)
        if unicodedata.category(ch) != "Mn"
    )
    # 3. Remove tatweel (U+0640 ـ)
    s = s.replace("\u0640", "")
    # 4. Standardize alef variants + hamza carriers → ا
    for variant in ("\u0622", "\u0623", "\u0625", "\u0624", "\u0626"):  # آ أ إ ؤ ئ
        s = s.replace(variant, "\u0627")
    # 5. teh-marbuta → heh, alef-maksura → yeh
    s = s.replace("\u0629", "\u0647")  # ة → ه
    s = s.replace("\u0649", "\u064a")  # ى → ي
    # Collapse spaces
    return _re.sub(r"\s+", " ", s).strip()


# ── SQLite cache (keyed on the INPUT TEXT, never on root_id) ────────────────
def _cache_key(tool: str, arguments: dict) -> str:
    payload = json.dumps({"t": tool, "a": arguments}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _cache_conn() -> sqlite3.Connection:
    _TELEMETRY_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_TELEMETRY_DB)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute(
        """CREATE TABLE IF NOT EXISTS bahouth_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cache_key TEXT UNIQUE,
            tool TEXT NOT NULL,
            arguments_json TEXT NOT NULL,
            result_json TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now')),
            hit_count INTEGER DEFAULT 0
        )"""
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_bahouth_cache_lookup "
        "ON bahouth_cache (tool, cache_key)"
    )
    return conn


def _cache_get(tool: str, arguments: dict) -> dict | None:
    """Cached MCP result, or None if not cached / expired / disabled."""
    if not BAHOUTH_CACHE_ENABLED:
        return None
    try:
        conn = _cache_conn()
        try:
            fresh = f"-{BAHOUTH_CACHE_TTL_DAYS} days"
            row = conn.execute(
                "SELECT result_json FROM bahouth_cache "
                "WHERE cache_key = ? AND created_at >= datetime('now', ?)",
                (_cache_key(tool, arguments), fresh),
            ).fetchone()
            if row:
                conn.execute(
                    "UPDATE bahouth_cache SET hit_count = hit_count + 1 "
                    "WHERE cache_key = ?",
                    (_cache_key(tool, arguments),),
                )
                conn.commit()
                return json.loads(row["result_json"])
        finally:
            conn.close()
    except Exception as exc:  # noqa: BLE001 — cache failure must not break the call
        logger.debug("bahouth cache read failed: %s", exc)
    return None


def _cache_put(tool: str, arguments: dict, result: dict) -> None:
    """Store a fresh MCP result in cache."""
    if not BAHOUTH_CACHE_ENABLED or not result:
        return
    try:
        conn = _cache_conn()
        try:
            conn.execute(
                """INSERT OR REPLACE INTO bahouth_cache
                   (cache_key, tool, arguments_json, result_json)
                   VALUES (?, ?, ?, ?)""",
                (
                    _cache_key(tool, arguments),
                    tool,
                    json.dumps(arguments, ensure_ascii=False),
                    json.dumps(result, ensure_ascii=False),
                ),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception as exc:  # noqa: BLE001 — cache write is best-effort
        logger.debug("bahouth cache write failed: %s", exc)


# ── MCP JSON-RPC client (same transport as tafsir_service) ─────────────────
def _parse_sse_response(raw: str) -> dict | None:
    """Extract the JSON payload from an SSE 'event: message' response."""
    for line in raw.split("\n"):
        line = line.strip()
        if line.startswith("data: "):
            return json.loads(line[6:])
    return None


async def _mcp_call(tool: str, arguments: dict) -> dict | None:
    """Call a Bahouth MCP tool via JSON-RPC over HTTP/SSE.

    Returns the parsed result dict, or None on failure.
    The MCP streamable-HTTP transport is stateless here — each request is
    a standalone POST that returns a single SSE event.
    """
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": tool, "arguments": arguments},
    }
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    try:
        async with httpx.AsyncClient(timeout=BAHOUTH_TIMEOUT) as client:
            resp = await client.post(
                BAHOUTH_MCP_URL, json=payload, headers=headers
            )
            if resp.status_code != 200:
                logger.warning(
                    "Bahouth MCP returned %d: %s",
                    resp.status_code, resp.text[:200],
                )
                return None
            data = _parse_sse_response(resp.text)
            if data is None:
                logger.warning("Bahouth MCP: could not parse SSE response")
                return None
            if "error" in data:
                logger.warning(
                    "Bahouth MCP error: %s", data["error"].get("message", "")
                )
                return None
            return data.get("result")
    except httpx.TimeoutException:
        logger.warning("Bahouth MCP timed out after %ds", BAHOUTH_TIMEOUT)
        return None
    except Exception as exc:  # noqa: BLE001 — network failures are expected
        logger.warning("Bahouth MCP call failed: %s", exc)
        return None


def _extract_content_text(result: dict) -> str:
    """Extract the text payload from MCP content[0].text."""
    if not isinstance(result, dict):
        return ""
    content = result.get("content", [])
    if not content or result.get("isError"):
        return ""
    return str(content[0].get("text", ""))


def _parse_inner(raw_text: str) -> dict | list | None:
    """Parse the nested JSON string inside MCP content[0].text."""
    try:
        return json.loads(raw_text)
    except (json.JSONDecodeError, TypeError):
        return None


# ── Public API ──────────────────────────────────────────────────────────────

FALLBACK_MESSAGE = (
    "المعلومات اللغوية غير متاحة حاليًا من المصدر الموثّق. "
    "يمكنك المحاولة لاحقًا."
)


async def find_root(root_text: str) -> RootResult:
    """ابحث عن جذر كلمة في القرآن.

    Args:
        root_text: الجذر (يُطبَّق عليه normalize تلقائيًا — السيرفر
            حسّاس للتشكيل: «صبر» يشتغل، «صَبَرَ» بيرجع found=false).

    Returns:
        RootResult — found=true مع root_id و frequency، أو found=false.
    """
    normalized = _normalize_arabic(root_text)
    if not normalized:
        return RootResult(root_text=root_text, found=False, error="empty")

    arguments = {"root_text": normalized}
    cached = _cache_get("find_root", arguments)
    if cached is not None:
        return RootResult(
            root_text=root_text,
            found=bool(cached.get("found")),
            root_id=cached.get("root_id"),
            frequency=cached.get("frequency"),
            cached=True,
        )

    mcp_result = await _mcp_call("find_root", arguments)
    if mcp_result is None:
        return RootResult(root_text=root_text, found=False, error="unavailable")

    inner = _parse_inner(_extract_content_text(mcp_result))
    if not isinstance(inner, dict):
        return RootResult(root_text=root_text, found=False, error="mcp_error")

    found = bool(inner.get("found", False))
    result = RootResult(
        root_text=root_text,
        found=found,
        root_id=inner.get("root_id"),
        frequency=inner.get("frequency"),
    )
    if found:
        _cache_put("find_root", arguments, {
            "found": found,
            "root_id": result.root_id,
            "frequency": result.frequency,
        })
    return result


async def list_root_verses(
    root_text: str, limit: int = 50, offset: int = 0
) -> VerseListResult:
    """آيات جذر معين (بصفحات — سقف السيرفر 50).

    Args:
        root_text: الجذر (normalize تلقائي).
        limit: عدد النتائج (يُقصّ على 50 — سقف السيرفر المتحقق منه).
        offset: إزاحة الصفحة (50+43=103 لصبر ✓).

    Returns:
        VerseListResult — verses مع total لو متاح.
    """
    normalized = _normalize_arabic(root_text)
    if not normalized:
        return VerseListResult(tool="list_root_verses", query_key=root_text, error="empty")

    arguments = {
        "root_text": normalized,
        "limit": min(int(limit), BAHOUTH_MAX_LIMIT),
        "offset": max(int(offset), 0),
    }
    cached = _cache_get("list_root_verses", arguments)
    if cached is not None:
        return VerseListResult(
            tool="list_root_verses", query_key=root_text,
            verses=cached.get("verses", []),
            total=cached.get("total"),
            cached=True,
        )

    mcp_result = await _mcp_call("list_root_verses", arguments)
    if mcp_result is None:
        return VerseListResult(tool="list_root_verses", query_key=root_text, error="unavailable")

    inner = _parse_inner(_extract_content_text(mcp_result))
    if isinstance(inner, dict):
        verses = inner.get("verses", inner.get("result", inner.get("items", [])))
        total = inner.get("total")
    elif isinstance(inner, list):
        verses = inner
        total = None
    else:
        verses = []
        total = None

    if not isinstance(verses, list):
        verses = []

    result = VerseListResult(
        tool="list_root_verses", query_key=root_text,
        verses=verses, total=total,
    )
    if verses:
        _cache_put("list_root_verses", arguments, {
            "verses": verses, "total": total,
        })
    return result


async def list_topic_verses(topic_id: int, limit: int = 50, offset: int = 0) -> VerseListResult:
    """آيات موضوع معين (topic_id رقمي — متحقق منه).

    Args:
        topic_id: معرف الموضوع الرقمي.
        limit: عدد النتائج (يُقصّ على 50).
        offset: إزاحة الصفحة.
    """
    arguments = {
        "topic_id": int(topic_id),
        "limit": min(int(limit), BAHOUTH_MAX_LIMIT),
        "offset": max(int(offset), 0),
    }
    cached = _cache_get("list_topic_verses", arguments)
    if cached is not None:
        return VerseListResult(
            tool="list_topic_verses", query_key=str(topic_id),
            verses=cached.get("verses", []),
            total=cached.get("total"),
            cached=True,
        )

    mcp_result = await _mcp_call("list_topic_verses", arguments)
    if mcp_result is None:
        return VerseListResult(tool="list_topic_verses", query_key=str(topic_id), error="unavailable")

    inner = _parse_inner(_extract_content_text(mcp_result))
    if isinstance(inner, dict):
        verses = inner.get("verses", inner.get("result", inner.get("items", [])))
        total = inner.get("total")
    elif isinstance(inner, list):
        verses = inner
        total = None
    else:
        verses = []
        total = None

    if not isinstance(verses, list):
        verses = []

    result = VerseListResult(
        tool="list_topic_verses", query_key=str(topic_id),
        verses=verses, total=total,
    )
    if verses:
        _cache_put("list_topic_verses", arguments, {
            "verses": verses, "total": total,
        })
    return result


async def list_verse_qiraat(verse_key: str) -> VerseListResult:
    """قراءات آية (verse_key بصيغة «2-255» بشرطة — متحقق منه).

    Args:
        verse_key: مفتاح الآية بالصيغة «سورة-آية» (مثل "2-255").
    """
    key = str(verse_key).strip()
    if not _re.match(r"^\d{1,3}-\d{1,3}$", key):
        return VerseListResult(tool="list_verse_qiraat", query_key=key, error="bad_key")

    arguments = {"verse_key": key}
    cached = _cache_get("list_verse_qiraat", arguments)
    if cached is not None:
        return VerseListResult(
            tool="list_verse_qiraat", query_key=key,
            verses=cached.get("verses", []),
            total=cached.get("total"),
            cached=True,
        )

    mcp_result = await _mcp_call("list_verse_qiraat", arguments)
    if mcp_result is None:
        return VerseListResult(tool="list_verse_qiraat", query_key=key, error="unavailable")

    inner = _parse_inner(_extract_content_text(mcp_result))
    if isinstance(inner, dict):
        verses = inner.get("qiraat", inner.get("verses", inner.get("result", inner.get("items", []))))
        total = inner.get("total")
    elif isinstance(inner, list):
        verses = inner
        total = None
    else:
        verses = []
        total = None

    if not isinstance(verses, list):
        verses = []

    result = VerseListResult(
        tool="list_verse_qiraat", query_key=key,
        verses=verses, total=total,
    )
    if verses:
        _cache_put("list_verse_qiraat", arguments, {
            "verses": verses, "total": total,
        })
    return result


async def get_verse(verse_key: str) -> dict | None:
    """جلب آية واحدة (verse_key بصيغة «2-255»).

    Returns:
        dict بالآية، أو None لو السيرفر وقع أو المفتاح غلط.
    """
    key = str(verse_key).strip()
    if not _re.match(r"^\d{1,3}-\d{1,3}$", key):
        return None

    arguments = {"verse_key": key}
    cached = _cache_get("get_verse", arguments)
    if cached is not None:
        return cached

    mcp_result = await _mcp_call("get_verse", arguments)
    if mcp_result is None:
        return None

    inner = _parse_inner(_extract_content_text(mcp_result))
    if not isinstance(inner, dict):
        return None

    _cache_put("get_verse", arguments, inner)
    return inner


async def list_verse_words(verse_key: str) -> list[dict]:
    """كلمات آية (verse_key بصيغة «2-255»)."""
    key = str(verse_key).strip()
    if not _re.match(r"^\d{1,3}-\d{1,3}$", key):
        return []

    arguments = {"verse_key": key}
    cached = _cache_get("list_verse_words", arguments)
    if cached is not None:
        return cached.get("words", [])

    mcp_result = await _mcp_call("list_verse_words", arguments)
    if mcp_result is None:
        return []

    inner = _parse_inner(_extract_content_text(mcp_result))
    if isinstance(inner, dict):
        words = inner.get("words", inner.get("result", inner.get("items", [])))
    elif isinstance(inner, list):
        words = inner
    else:
        words = []

    if not isinstance(words, list):
        words = []
    if words:
        _cache_put("list_verse_words", arguments, {"words": words})
    return words


async def list_verse_properties(verse_key: str) -> dict | None:
    """خصائص آية (verse_key بصيغة «2-255»)."""
    key = str(verse_key).strip()
    if not _re.match(r"^\d{1,3}-\d{1,3}$", key):
        return None

    arguments = {"verse_key": key}
    cached = _cache_get("list_verse_properties", arguments)
    if cached is not None:
        return cached

    mcp_result = await _mcp_call("list_verse_properties", arguments)
    if mcp_result is None:
        return None

    inner = _parse_inner(_extract_content_text(mcp_result))
    if not isinstance(inner, dict):
        return None

    _cache_put("list_verse_properties", arguments, inner)
    return inner


async def list_verse_topics(verse_key: str) -> list[dict]:
    """موضوعات آية (verse_key بصيغة «2-255»)."""
    key = str(verse_key).strip()
    if not _re.match(r"^\d{1,3}-\d{1,3}$", key):
        return []

    arguments = {"verse_key": key}
    cached = _cache_get("list_verse_topics", arguments)
    if cached is not None:
        return cached.get("topics", [])

    mcp_result = await _mcp_call("list_verse_topics", arguments)
    if mcp_result is None:
        return []

    inner = _parse_inner(_extract_content_text(mcp_result))
    if isinstance(inner, dict):
        topics = inner.get("topics", inner.get("result", inner.get("items", [])))
    elif isinstance(inner, list):
        topics = inner
    else:
        topics = []

    if not isinstance(topics, list):
        topics = []
    if topics:
        _cache_put("list_verse_topics", arguments, {"topics": topics})
    return topics


async def list_surah_verses(surah: int, limit: int = 50, offset: int = 0) -> VerseListResult:
    """آيات سورة (سقف 50 — السيرفر مش للجلب الجماعي، استخدم الصفحات)."""
    arguments = {
        "surah": int(surah),
        "limit": min(int(limit), BAHOUTH_MAX_LIMIT),
        "offset": max(int(offset), 0),
    }
    cached = _cache_get("list_surah_verses", arguments)
    if cached is not None:
        return VerseListResult(
            tool="list_surah_verses", query_key=str(surah),
            verses=cached.get("verses", []),
            total=cached.get("total"),
            cached=True,
        )

    mcp_result = await _mcp_call("list_surah_verses", arguments)
    if mcp_result is None:
        return VerseListResult(tool="list_surah_verses", query_key=str(surah), error="unavailable")

    inner = _parse_inner(_extract_content_text(mcp_result))
    if isinstance(inner, dict):
        verses = inner.get("verses", inner.get("result", inner.get("items", [])))
        total = inner.get("total")
    elif isinstance(inner, list):
        verses = inner
        total = None
    else:
        verses = []
        total = None

    if not isinstance(verses, list):
        verses = []

    result = VerseListResult(
        tool="list_surah_verses", query_key=str(surah),
        verses=verses, total=total,
    )
    if verses:
        _cache_put("list_surah_verses", arguments, {
            "verses": verses, "total": total,
        })
    return result


# ── Formatting helpers ──────────────────────────────────────────────────────
def format_root_for_display(result: RootResult) -> str:
    """Format a RootResult for display to the parent."""
    if not result.ok:
        if result.error == "unavailable":
            return FALLBACK_MESSAGE
        return f"الجذر «{result.root_text}» غير موجود في قاعدة الجذور."
    return (
        f"🔤 جذر «{result.root_text}» — ورد في القرآن {result.frequency} موضعًا."
    )


def format_verses_for_display(result: VerseListResult, max_verses: int = 5) -> str:
    """Format a verse list for display (truncated)."""
    if not result.ok:
        return FALLBACK_MESSAGE
    if not result.verses:
        return "لا توجد نتائج."
    parts: list[str] = []
    for v in result.verses[:max_verses]:
        if isinstance(v, dict):
            ref = v.get("verse_key") or v.get("key") or ""
            text = v.get("text") or v.get("verse_text") or ""
            parts.append(f"• {ref}: {text}")
        else:
            parts.append(f"• {v}")
    if len(result.verses) > max_verses:
        parts.append(f"… و{len(result.verses) - max_verses} آيات أخرى")
    return "\n".join(parts)


def format_verses_for_context(result: VerseListResult) -> str:
    """Format verses for injection into an LLM context block."""
    if not result.ok or not result.verses:
        return ""
    parts: list[str] = []
    for v in result.verses:
        if isinstance(v, dict):
            ref = v.get("verse_key") or v.get("key") or ""
            text = v.get("text") or v.get("verse_text") or ""
            parts.append(f"【{ref}】 {text}")
        else:
            parts.append(str(v))
    return "\n".join(parts)
