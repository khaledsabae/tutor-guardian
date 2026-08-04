"""
Tafsir Service — طبقة مساعدة مستقلة لجلب التفسير الموثّق
============================================================
يتصل بـ Tafsir MCP (https://mcp.tafsir.net/mcp) عبر JSON-RPC over SSE.
الطبقة دي مش جزء من الـRAG الرئيسي — بتتنادى بس لما:
  - المستخدم يسأل عن تفسير آية معينة
  - الورد القرآني يحتاج تفسير
  - درس قرآني يحتاج مصدر موثوق

المميزات:
  - Caching في SQLite (نفس قاعدة ops/sessions.db) عشان ما تكررش الطلبات
  - Timeout قصير (10ث) عشان ما يعلقش الـrequest
  - Fallback واضح لو السيرفر وقع أو مفيش نت
  - مفيش PII بيتبعث — بس أرقام السورة والآية والمصدر
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

# ── Configuration ────────────────────────────────────────────────────────────
TAFSIR_MCP_URL = os.environ.get(
    "TAFSIR_MCP_URL", "https://mcp.tafsir.net/mcp"
)
TAFSIR_TIMEOUT = int(os.environ.get("TAFSIR_TIMEOUT", "10"))  # seconds
TAFSIR_CACHE_ENABLED = os.environ.get(
    "TAFSIR_CACHE_ENABLED", "true"
).lower() in ("1", "true", "yes")
TAFSIR_CACHE_TTL_DAYS = int(os.environ.get("TAFSIR_CACHE_TTL_DAYS", "30"))

# Default tafsir sources — short, parent-friendly, widely trusted
DEFAULT_SOURCES = ["saadi", "moyassar"]

_TELEMETRY_DB = Path(__file__).resolve().parents[3] / "ops" / "sessions.db"


# ── Data types ──────────────────────────────────────────────────────────────
@dataclass
class TafsirResult:
    """نتيجة جلب التفسير — نص موثوق + النسبة العلمية."""
    surah: int
    ayah: int
    source: str
    attribution: str
    text: str  # نص التفسير كما هو من المصدر
    footnotes: list[dict] | None = None
    cached: bool = False
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and bool(self.text)


# ── SQLite cache ────────────────────────────────────────────────────────────
def _cache_key(surah: int, ayah: int, source: str) -> str:
    payload = f"{surah}:{ayah}:{source}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _cache_conn() -> sqlite3.Connection:
    _TELEMETRY_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_TELEMETRY_DB)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute(
        """CREATE TABLE IF NOT EXISTS tafsir_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cache_key TEXT UNIQUE,
            surah INTEGER NOT NULL,
            ayah INTEGER NOT NULL,
            source TEXT NOT NULL,
            attribution TEXT,
            text TEXT NOT NULL,
            footnotes_json TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            hit_count INTEGER DEFAULT 0
        )"""
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_tafsir_cache_lookup "
        "ON tafsir_cache (surah, ayah, source)"
    )
    return conn


def _cache_get(surah: int, ayah: int, source: str) -> TafsirResult | None:
    """Cached tafsir result, or None if not cached / expired / disabled."""
    if not TAFSIR_CACHE_ENABLED:
        return None
    try:
        conn = _cache_conn()
        try:
            fresh = f"-{TAFSIR_CACHE_TTL_DAYS} days"
            row = conn.execute(
                "SELECT attribution, text, footnotes_json FROM tafsir_cache "
                "WHERE cache_key = ? AND created_at >= datetime('now', ?)",
                (_cache_key(surah, ayah, source), fresh),
            ).fetchone()
            if row:
                conn.execute(
                    "UPDATE tafsir_cache SET hit_count = hit_count + 1 "
                    "WHERE cache_key = ?",
                    (_cache_key(surah, ayah, source),),
                )
                conn.commit()
                footnotes = None
                if row["footnotes_json"]:
                    footnotes = json.loads(row["footnotes_json"])
                return TafsirResult(
                    surah=surah, ayah=ayah, source=source,
                    attribution=row["attribution"] or "",
                    text=row["text"], footnotes=footnotes, cached=True,
                )
        finally:
            conn.close()
    except Exception as exc:  # noqa: BLE001 — cache failure must not break the call
        logger.debug("tafsir cache read failed: %s", exc)
    return None


def _cache_put(result: TafsirResult) -> None:
    """Store a fresh tafsir result in cache."""
    if not TAFSIR_CACHE_ENABLED or not result.ok:
        return
    try:
        conn = _cache_conn()
        try:
            footnotes_json = json.dumps(result.footnotes) if result.footnotes else None
            conn.execute(
                """INSERT OR REPLACE INTO tafsir_cache
                   (cache_key, surah, ayah, source, attribution, text, footnotes_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    _cache_key(result.surah, result.ayah, result.source),
                    result.surah, result.ayah, result.source,
                    result.attribution, result.text, footnotes_json,
                ),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception as exc:  # noqa: BLE001 — cache write is best-effort
        logger.debug("tafsir cache write failed: %s", exc)


# ── MCP JSON-RPC client ─────────────────────────────────────────────────────
def _parse_sse_response(raw: str) -> dict | None:
    """Extract the JSON payload from an SSE 'event: message' response."""
    for line in raw.split("\n"):
        line = line.strip()
        if line.startswith("data: "):
            return json.loads(line[6:])
    return None


async def _mcp_call(tool: str, arguments: dict) -> dict | None:
    """Call a Tafsir MCP tool via JSON-RPC over HTTP/SSE.

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
        async with httpx.AsyncClient(timeout=TAFSIR_TIMEOUT) as client:
            resp = await client.post(
                TAFSIR_MCP_URL, json=payload, headers=headers
            )
            if resp.status_code != 200:
                logger.warning(
                    "Tafsir MCP returned %d: %s",
                    resp.status_code, resp.text[:200],
                )
                return None
            data = _parse_sse_response(resp.text)
            if data is None:
                logger.warning("Tafsir MCP: could not parse SSE response")
                return None
            if "error" in data:
                logger.warning(
                    "Tafsir MCP error: %s", data["error"].get("message", "")
                )
                return None
            return data.get("result")
    except httpx.TimeoutException:
        logger.warning("Tafsir MCP timed out after %ds", TAFSIR_TIMEOUT)
        return None
    except Exception as exc:  # noqa: BLE001 — network failures are expected
        logger.warning("Tafsir MCP call failed: %s", exc)
        return None


def _extract_tafsir_entry(raw_text: str) -> dict:
    """Parse the nested JSON string inside MCP content[0].text."""
    try:
        return json.loads(raw_text)
    except (json.JSONDecodeError, TypeError):
        return {}


def _extract_search_results(result: dict) -> list[dict]:
    """Extract result list from MCP search tools.

    Search tools return either:
      - structuredContent.result (observed in production)
      - a single content item whose text is {result: [...]} or {items: [...]}
      - multiple content items each containing a single JSON object
    """
    if not isinstance(result, dict):
        return []

    structured = result.get("structuredContent")
    if isinstance(structured, dict):
        data = structured.get("result", structured.get("items"))
        if isinstance(data, list):
            return data

    content = result.get("content", [])
    if not content:
        return []

    # Single wrapped payload in the first content item
    inner = _extract_tafsir_entry(content[0].get("text", ""))
    if isinstance(inner, list):
        return inner
    if isinstance(inner, dict):
        for key in ("result", "items"):
            data = inner.get(key)
            if isinstance(data, list):
                return data

    # Multiple content items each holding a single result JSON object
    results: list[dict] = []
    for item in content:
        text = item.get("text", "")
        if not text:
            continue
        parsed = _extract_tafsir_entry(text)
        if isinstance(parsed, dict):
            results.append(parsed)
    return results


# ── Public API ──────────────────────────────────────────────────────────────

FALLBACK_MESSAGE = (
    "التفسير غير متاح حاليًا من المصدر الموثّق. "
    "يمكنك الرجوع إلى تفسير السعدي أو التيسير في كتابك، أو المحاولة لاحقًا."
)


async def fetch_tafsir(
    surah: int,
    ayah: int,
    sources: list[str] | None = None,
) -> list[TafsirResult]:
    """جلب تفسير آية من مصدر أو أكثر من Tafsir MCP.

    Args:
        surah: رقم السورة (1-114)
        ayah: رقم الآية
        sources: قائمة المصادر (default: ["saadi", "moyassar"])

    Returns:
        list[TafsirResult] — نتيجة لكل مصدر مطلوب (بالترتيب).
        لو السيرفر وقع، كل نتيجة هتحمل رسالة الـfallback.
    """
    if sources is None:
        sources = DEFAULT_SOURCES
    if not sources:
        sources = DEFAULT_SOURCES

    results: list[TafsirResult] = []
    for source in sources:
        # Check cache first
        cached = _cache_get(surah, ayah, source)
        if cached:
            results.append(cached)
            continue

        # Live fetch from MCP
        mcp_result = await _mcp_call(
            "fetch_tafsir",
            {"surah": surah, "ayah": ayah, "sources": [source]},
        )

        if mcp_result is None:
            results.append(TafsirResult(
                surah=surah, ayah=ayah, source=source,
                attribution="", text="", error="unavailable",
            ))
            continue

        # MCP returns: {content: [{type: "text", text: "<JSON string>"}], isError: false}
        content = mcp_result.get("content", [])
        if mcp_result.get("isError") or not content:
            results.append(TafsirResult(
                surah=surah, ayah=ayah, source=source,
                attribution="", text="", error="mcp_error",
            ))
            continue

        # The text field inside content[0] is a JSON string with the actual data
        inner = _extract_tafsir_entry(content[0].get("text", ""))
        tafsirs = inner.get("tafsirs", [])

        if not tafsirs:
            results.append(TafsirResult(
                surah=surah, ayah=ayah, source=source,
                attribution="", text="", error="no_data",
            ))
            continue

        entry = tafsirs[0]  # we asked for one source
        result = TafsirResult(
            surah=surah, ayah=ayah, source=source,
            attribution=entry.get("attribution", ""),
            text=entry.get("text", ""),
            footnotes=entry.get("footnotes"),
        )
        _cache_put(result)
        results.append(result)

    return results


async def fetch_ayah_text(surah: int, ayah: int) -> str | None:
    """جلب نص آية قرآنية بالرسم العثماني.

    Returns:
        نص الآية، أو None لو السيرفر وقع.
    """
    cached = _cache_get(surah, 0, "_ayah")
    if cached and cached.text:
        return cached.text

    mcp_result = await _mcp_call(
        "fetch_ayah", {"surah": surah, "ayah": ayah}
    )
    if mcp_result is None:
        return None

    content = mcp_result.get("content", [])
    if mcp_result.get("isError") or not content:
        return None

    inner = _extract_tafsir_entry(content[0].get("text", ""))
    text = inner.get("text", "")
    if text:
        _cache_put(TafsirResult(
            surah=surah, ayah=0, source="_ayah",
            attribution="", text=text,
        ))
    return text or None


async def search_quran(query: str, limit: int = 10) -> list[dict]:
    """بحث نصي في آيات القرآن.

    Returns:
        list of {surah, ayah, text, snippet} dicts, or empty list on failure.
    """
    mcp_result = await _mcp_call(
        "search_quran_text",
        {"query": query, "limit": min(limit, 20)},
    )
    if mcp_result is None:
        return []

    content = mcp_result.get("content", [])
    if mcp_result.get("isError") or not content:
        return []

    return _extract_search_results(mcp_result)


async def search_in_tafsir(
    query: str, source: str = "saadi", limit: int = 10
) -> list[dict]:
    """بحث LIKE داخل تفسير معين.

    Returns:
        list of {surah, ayah, tafsir_excerpt, source_attribution} dicts.
    """
    mcp_result = await _mcp_call(
        "search_in_tafsir",
        {"query": query, "source": source, "limit": min(limit, 20)},
    )
    if mcp_result is None:
        return []

    content = mcp_result.get("content", [])
    if mcp_result.get("isError") or not content:
        return []

    return _extract_search_results(mcp_result)


async def fetch_nuzool_reason(
    surah: int, ayah: int
) -> TafsirResult | None:
    """جلب سبب نزول آية إن ثبت في المصادر المعتمدة.

    Returns:
        TafsirResult with the nuzool reason text, or None if unavailable.
    """
    mcp_result = await _mcp_call(
        "fetch_nuzool_reason", {"surah": surah, "ayah": ayah}
    )
    if mcp_result is None:
        return None

    content = mcp_result.get("content", [])
    if mcp_result.get("isError") or not content:
        return None

    inner = _extract_tafsir_entry(content[0].get("text", ""))
    text = inner.get("text", "")
    if not text:
        return None

    return TafsirResult(
        surah=surah, ayah=ayah, source="nuzool",
        attribution=inner.get("attribution", ""),
        text=text,
        footnotes=inner.get("footnotes"),
    )


async def list_tafsir_sources() -> list[dict]:
    """فهرس مصادر التفسير المتاحة.

    Returns:
        list of source dicts with slug, name, author, etc.
    """
    mcp_result = await _mcp_call("list_tafsir_sources", {})
    if mcp_result is None:
        return []

    content = mcp_result.get("content", [])
    if mcp_result.get("isError") or not content:
        return []

    inner = _extract_tafsir_entry(content[0].get("text", ""))
    # Could be a list directly or nested under sources/result/items
    if isinstance(inner, list):
        return inner
    if isinstance(inner, dict):
        return inner.get("sources", inner.get("result", inner.get("items", [])))
    return []


def format_tafsir_for_display(result: TafsirResult) -> str:
    """Format a TafsirResult for display to the parent.

    Returns attribution + text, or the fallback message on error.
    """
    if not result.ok:
        return FALLBACK_MESSAGE

    parts = [f"📖 {result.attribution}"]
    parts.append("")
    parts.append(result.text)

    if result.footnotes:
        parts.append("")
        for fn in result.footnotes:
            marker = fn.get("marker", f"[{fn.get('index', '')}]")
            fn_text = fn.get("text", "")
            parts.append(f"  {marker} {fn_text}")

    return "\n".join(parts)


def format_tafsir_for_context(results: list[TafsirResult]) -> str:
    """Format tafsir results for injection into an LLM context block.

    Only includes successful results — errors are silently dropped
    so the model doesn't try to "help" with the error.
    """
    parts: list[str] = []
    for r in results:
        if not r.ok:
            continue
        parts.append(
            f"【{r.source}】 ({r.attribution})\n{r.text}"
        )
    return "\n---\n".join(parts) if parts else ""


# ── Ayah detection in user questions ────────────────────────────────────────
import re as _re

# Patterns a parent might use to ask about a specific ayah:
#   "تفسير سورة البقرة آية 255"
#   "شرح آية 255 من سورة البقرة"
#   "تفسير الفاتحة 1"
#   "ايتاب الكرسي" (by common name — too broad, skip)
# Surah names → numbers mapping (the 114 surahs). The parent may use the name
# rather than a number, so we resolve it.
_SURAH_NAMES: dict[str, int] = {
    "الفاتحة": 1, "البقرة": 2, "آل عمران": 3, "النساء": 4, "المائدة": 5,
    "الأنعام": 6, "الأعراف": 7, "الأنفال": 8, "التوبة": 9, "يونس": 10,
    "هود": 11, "يوسف": 12, "الرعد": 13, "إبراهيم": 14, "الحجر": 15,
    "النحل": 16, "الإسراء": 17, "الكهف": 18, "مريم": 19, "طه": 20,
    "الأنبياء": 21, "الحج": 22, "المؤمنون": 23, "النور": 24, "الفرقان": 25,
    "الشعراء": 26, "النمل": 27, "القصص": 28, "العنكبوت": 29, "الروم": 30,
    "لقمان": 31, "السجدة": 32, "الأحزاب": 33, "سبأ": 34, "فاطر": 35,
    "يس": 36, "الصافات": 37, "ص": 38, "الزمر": 39, "غافر": 40,
    "فصلت": 41, "الشورى": 42, "الزخرف": 43, "الدخان": 44, "الجاثية": 45,
    "الأحقاف": 46, "محمد": 47, "الفتح": 48, "الحجرات": 49, "ق": 50,
    "الذاريات": 51, "الطور": 52, "النجم": 53, "القمر": 54, "الرحمن": 55,
    "الواقعة": 56, "الحديد": 57, "المجادلة": 58, "الحشر": 59, "الممتحنة": 60,
    "الصف": 61, "الجمعة": 62, "المنافقون": 63, "التغابن": 64, "الطلاق": 65,
    "التحريم": 66, "الملك": 67, "القلم": 68, "الحاقة": 69, "المعارج": 70,
    "نوح": 71, "الجن": 72, "المزمل": 73, "المدثر": 74, "القيامة": 75,
    "الإنسان": 76, "المرسلات": 77, "النبأ": 78, "النازعات": 79, "عبس": 80,
    "التكوير": 81, "الانفطار": 82, "المطففين": 83, "الانشقاق": 84, "البروج": 85,
    "الطارق": 86, "الأعلى": 87, "الغاشية": 88, "الفجر": 89, "البلد": 90,
    "الشمس": 91, "الليل": 92, "الضحى": 93, "الشرح": 94, "التين": 95,
    "العلق": 96, "القدر": 97, "البينة": 98, "الزلزلة": 99, "العاديات": 100,
    "القارعة": 101, "التكاثر": 102, "العصر": 103, "الهمزة": 104, "الفيل": 105,
    "قريش": 106, "الماعون": 107, "الكوثر": 108, "الكافرون": 109, "النصر": 110,
    "المسد": 111, "الإخلاص": 112, "الفلق": 113, "الناس": 114,
}

# Build a regex alternation of all surah names (longest first to avoid
# partial matches like "النحل" eating "النحلة").
_SURAH_NAME_PATTERN = "|".join(
    _re.escape(name) for name in sorted(_SURAH_NAMES, key=len, reverse=True)
)

# Match: (سورة|سوره) <name|number> (آية|ايه|رقم)? <number>
# or: <name> <number> directly (e.g. "البقرة 255")
_AYAH_PATTERN = _re.compile(
    r"(?:سورة\s*|سوره\s*)?(" + _SURAH_NAME_PATTERN + r"|\d+)"
    r"\s*(?:آية|ايه|رقم|رقم|اية)?\s*(\d{1,3})",
    _re.UNICODE,
)
# Also: "تفسير <name> <number>" or "شرح <name> <number>"
_AYAH_PATTERN2 = _re.compile(
    r"(?:تفسير|شرح)\s*(" + _SURAH_NAME_PATTERN + r")\s*(\d{1,3})",
    _re.UNICODE,
)
# Also: bare "<surah_name> <number>" — common in chat
_AYAH_PATTERN3 = _re.compile(
    r"(" + _SURAH_NAME_PATTERN + r")\s+(\d{1,3})\b",
    _re.UNICODE,
)


def _normalize_arabic(text: str) -> str:
    """Strip Arabic diacritics (tashkeel), tatweel, and standardize alef/teh.

    Makes "بِسْمِ اللّٰهِ" match "بسم الله" and "الَّلّه" match "الله".
    """
    import unicodedata

    s = text
    # Remove combining marks (tashkeel: fatha, damma, kasra, sukun, shadda, ...)
    s = "".join(
        ch for ch in unicodedata.normalize("NFD", s)
        if unicodedata.category(ch) != "Mn"
    )
    # Remove tatweel (U+0640 ـ)
    s = s.replace("\u0640", "")
    # Standardize alef variants → ا
    for variant in ("\u0622", "\u0623", "\u0625"):  # آ أ إ
        s = s.replace(variant, "\u0627")
    # Standardize teh marbuta → heh
    s = s.replace("\u0629", "\u0647")  # ة → ه
    # Standardize alef-maksura → yeh
    s = s.replace("\u0649", "\u064a")  # ى → ي
    # Standardize small alef above (used in لّٰه) → plain alef
    s = s.replace("\u0670", "\u0627")  # ٰ (alef superscript) → ا
    # Collapse spaces
    return _re.sub(r"\s+", " ", s).strip()


# Well-known ayahs the parent may reference by their opening words or a
# common name. Keys are NORMALIZED (no tashkeel). Only include ayahs that
# are unambiguous and commonly asked about, to avoid false positives.
# (surah, ayah) 1-indexed.
_AYAH_BY_TEXT: dict[str, tuple[int, int]] = {
    # سورة الفاتحة
    "بسم الله الرحمن الرحيم": (1, 1),
    # آية الكرسي — البقرة 255
    "اية الكرسي": (2, 255),
    "الكرسي": (2, 255),
    "الله لا اله الا هو الحي القيوم": (2, 255),
    "لا اله الا هو الحي القيوم": (2, 255),
    "الحي القيوم": (2, 255),
    # سورة الإخلاص
    "قل هو الله احد": (112, 1),
    "قل هو الله أحد": (112, 1),
    # سورة الناس
    "قل اعوذ برب الناس": (114, 1),
    # سورة الفلق
    "قل اعوذ برب الفلق": (113, 1),
    # سورة الكوثر
    "انا اعطيناك الكوثر": (108, 1),
}


def detect_ayah_reference(text: str) -> tuple[int, int] | None:
    """Detect a surah+ayah reference in a user's question.

    Returns (surah, ayah) or None. Tries multiple patterns from most
    specific (سورة X آية Y) to least (X Y), then falls back to matching
    the opening words of well-known ayahs (آية الكرسي، بسم الله، ...).
    """
    if not text:
        return None

    # Try most specific first
    for pattern in (_AYAH_PATTERN, _AYAH_PATTERN2, _AYAH_PATTERN3):
        m = pattern.search(text)
        if m:
            ref = m.group(1)
            ayah = int(m.group(2))
            # Resolve surah: name lookup or direct number
            surah = _SURAH_NAMES.get(ref)
            if surah is None:
                try:
                    surah = int(ref)
                except ValueError:
                    continue
            if 1 <= surah <= 114 and 1 <= ayah <= 286:
                return (surah, ayah)

    # Fallback: well-known ayahs referenced by their opening words
    # (or a common name). Normalize Arabic (strip tashkeel + tatweel) so
    # "بِسْمِ اللّٰهِ" and "بسم الله" both match.
    norm = _normalize_arabic(text)
    for key, (surah, ayah) in _AYAH_BY_TEXT.items():
        if key in norm:
            return (surah, ayah)
    return None


async def resolve_ayah_reference(text: str) -> tuple[int, int] | None:
    """Resolve an ayah reference from a question, covering the FULL Quran.

    Priority:
      1. Explicit surah+ayah number ("سورة البقرة آية 255") or common
         name ("آية الكرسي") via detect_ayah_reference.
      2. Well-known ayahs by opening words (bismillah, etc.).
      3. **Full-Quran fallback**: if the question quotes ayah text, search
         the entire Quran via the MCP search_quran_text tool and confirm
         the matched ayah's opening words actually appear in the question.
         Returns None (no enrichment) if the search fails or is inconclusive,
         so a generic parenting question is never misattributed to an ayah.
    """
    # Fast path: explicit reference / well-known ayah (no network).
    ref = detect_ayah_reference(text)
    if ref:
        return ref

    # Full-Quran path: normalize the query, then search. Only trust a hit
    # whose opening words appear in the question — users usually quote the
    # start of the ayah. We check the opening anchor (first ~4 words) of the
    # matched ayah is a substring of the normalized question. This guards
    # against a generic parenting question matching a short ayah.
    norm_query = _normalize_arabic(text)
    # A quoted ayah in a question is usually a few words to ~1 line. Skip
    # the expensive network search for very short / non-ayah questions.
    if len(norm_query) < 10:
        return None
    try:
        # Strip a leading request word ("تفسير/شرح/ما معنى/ايه معنى") so the
        # search is run against the quoted ayah text alone. The MCP search is
        # exact-ish; extra words pollute it.
        search_text = _re.sub(r"^(تفسير|شرح|معنى|ما معنى|ايه معنى|ما تفسير|وش معنى)\s*[:؟؟]?\s*",
                              "", text, flags=_re.UNICODE).strip()
        hits = await search_quran(search_text, limit=5)
    except Exception:  # noqa: BLE001 — network failure must not break the call
        return None
    for hit in hits:
        ayah_text = _normalize_arabic(str(hit.get("text") or ""))
        if not ayah_text:
            continue
        # Opening anchor of the ayah (first 4 words). If that appears in the
        # question, the user was quoting this ayah.
        anchor_words = ayah_text.split()
        anchor = " ".join(anchor_words[:4])
        if anchor and anchor in norm_query:
            try:
                return (int(hit["surah"]), int(hit["ayah"]))
            except (KeyError, TypeError, ValueError):
                continue
    return None