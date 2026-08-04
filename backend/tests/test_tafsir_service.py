"""Tests for tafsir_service — MCP client, caching, and fallback behaviour.

These tests mock the HTTP layer (httpx.AsyncClient) so they never hit the
live Tafsir MCP server. They verify:
  - Correct parsing of MCP JSON-RPC/SSE responses
  - Cache hit/miss lifecycle
  - Graceful fallback when the server is unreachable
  - Display formatting
  - Ayah reference detection in user questions
"""
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.tafsir_service import (
    TafsirResult,
    fetch_tafsir,
    fetch_ayah_text,
    search_quran,
    search_in_tafsir,
    list_tafsir_sources,
    format_tafsir_for_display,
    format_tafsir_for_context,
    FALLBACK_MESSAGE,
    _parse_sse_response,
    _cache_key,
)


# ── SSE parsing ─────────────────────────────────────────────────────────────

def test_parse_sse_response_extracts_json():
    """The MCP server returns SSE-formatted text; we need the JSON payload."""
    raw = 'event: message\r\ndata: {"jsonrpc":"2.0","id":1,"result":{"ok":true}}\r\n'
    data = _parse_sse_response(raw)
    assert data is not None
    assert data["result"]["ok"] is True


def test_parse_sse_response_no_data_line():
    raw = "event: message\r\n\r\n"
    assert _parse_sse_response(raw) is None


def test_parse_sse_response_multiple_lines():
    """Only the 'data:' line matters, not event: or blank lines."""
    raw = (
        'event: message\r\n'
        '\r\n'
        'data: {"jsonrpc":"2.0","id":3,"result":{"content":[{"type":"text","text":"{}"}]}}\r\n'
    )
    data = _parse_sse_response(raw)
    assert data is not None
    assert data["id"] == 3


# ── Cache key ──────────────────────────────────────────────────────────────

def test_cache_key_deterministic():
    """Same (surah, ayah, source) must always produce the same key."""
    k1 = _cache_key(1, 1, "saadi")
    k2 = _cache_key(1, 1, "saadi")
    assert k1 == k2


def test_cache_key_differs_by_source():
    k1 = _cache_key(1, 1, "saadi")
    k2 = _cache_key(1, 1, "moyassar")
    assert k1 != k2


def test_cache_key_differs_by_ayah():
    k1 = _cache_key(1, 1, "saadi")
    k2 = _cache_key(1, 2, "saadi")
    assert k1 != k2


# ── fetch_tafsir with mocked MCP ────────────────────────────────────────────

_MCP_TAFSIR_RESPONSE = {
    "jsonrpc": "2.0",
    "id": 3,
    "result": {
        "content": [{
            "type": "text",
            "text": json.dumps({
                "surah": 1,
                "ayah": 1,
                "tafsirs": [{
                    "source": "saadi",
                    "attribution": "تيسير الكريم الرحمن، السعدي",
                    "text": "تفسير سورة الفاتحة\nوهي مكية\n{بسم الله الرحمن الرحيم}",
                    "footnotes": [{"index": 1, "marker": "[1]", "text": "حاشية"}],
                }],
            }, ensure_ascii=False),
        }],
        "isError": False,
    },
}


def _mock_sse_text(data: dict) -> str:
    """Build a mock SSE string from a dict."""
    return f'event: message\r\ndata: {json.dumps(data, ensure_ascii=False)}\r\n'


def _mock_httpx_client(sse_text: str):
    """Build a mock httpx.AsyncClient that returns the given SSE text."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = sse_text

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.post = AsyncMock(return_value=mock_response)
    return mock_client


def test_fetch_tafsir_success(monkeypatch, tmp_path):
    """Live fetch parses attribution + text + footnotes from MCP response."""
    import app.services.tafsir_service as svc
    monkeypatch.setattr(svc, "_TELEMETRY_DB", tmp_path / "test_tafsir.db")

    mock_client = _mock_httpx_client(_mock_sse_text(_MCP_TAFSIR_RESPONSE))

    with patch("app.services.tafsir_service.httpx.AsyncClient", return_value=mock_client):
        results = asyncio.run(fetch_tafsir(1, 1, ["saadi"]))

    assert len(results) == 1
    r = results[0]
    assert r.ok
    assert r.source == "saadi"
    assert r.attribution == "تيسير الكريم الرحمن، السعدي"
    assert "الفاتحة" in r.text
    assert r.footnotes is not None and len(r.footnotes) == 1
    assert not r.cached  # first call — not cached


def test_fetch_tafsir_cache_hit(monkeypatch, tmp_path):
    """Second call with same params should hit cache (no HTTP call)."""
    import app.services.tafsir_service as svc
    monkeypatch.setattr(svc, "_TELEMETRY_DB", tmp_path / "test_tafsir_cache.db")

    mock_client = _mock_httpx_client(_mock_sse_text(_MCP_TAFSIR_RESPONSE))

    with patch("app.services.tafsir_service.httpx.AsyncClient", return_value=mock_client):
        results1 = asyncio.run(fetch_tafsir(1, 1, ["saadi"]))
        # Second call — should NOT make an HTTP request
        mock_client.post = AsyncMock(
            side_effect=AssertionError("Should not call HTTP on cache hit")
        )
        results2 = asyncio.run(fetch_tafsir(1, 1, ["saadi"]))

    assert results1[0].ok and not results1[0].cached
    assert results2[0].ok and results2[0].cached
    assert results1[0].text == results2[0].text


def test_fetch_tafsir_server_down(monkeypatch, tmp_path):
    """When MCP returns None (unreachable), result carries the error."""
    import app.services.tafsir_service as svc
    monkeypatch.setattr(svc, "_TELEMETRY_DB", tmp_path / "test_tafsir_down.db")

    with patch(
        "app.services.tafsir_service._mcp_call",
        new_callable=AsyncMock,
        return_value=None,
    ):
        results = asyncio.run(fetch_tafsir(1, 1, ["saadi"]))

    assert len(results) == 1
    assert not results[0].ok
    assert results[0].error == "unavailable"
    assert results[0].text == ""


def test_fetch_tafsir_mcp_error(monkeypatch, tmp_path):
    """When MCP returns isError=True, result carries the error."""
    import app.services.tafsir_service as svc
    monkeypatch.setattr(svc, "_TELEMETRY_DB", tmp_path / "test_tafsir_err.db")

    error_response = {
        "jsonrpc": "2.0", "id": 3,
        "result": {"content": [{"type": "text", "text": "{}"}], "isError": True},
    }

    with patch(
        "app.services.tafsir_service._mcp_call",
        new_callable=AsyncMock,
        return_value=error_response["result"],
    ):
        results = asyncio.run(fetch_tafsir(1, 1, ["saadi"]))

    assert len(results) == 1
    assert not results[0].ok
    assert results[0].error == "mcp_error"


def test_fetch_tafsir_no_data(monkeypatch, tmp_path):
    """When MCP returns empty tafsirs, result carries no_data error."""
    import app.services.tafsir_service as svc
    monkeypatch.setattr(svc, "_TELEMETRY_DB", tmp_path / "test_tafsir_nodata.db")

    empty_response = {
        "jsonrpc": "2.0", "id": 3,
        "result": {
            "content": [{
                "type": "text",
                "text": json.dumps({"surah": 1, "ayah": 1, "tafsirs": []}),
            }],
            "isError": False,
        },
    }

    with patch(
        "app.services.tafsir_service._mcp_call",
        new_callable=AsyncMock,
        return_value=empty_response["result"],
    ):
        results = asyncio.run(fetch_tafsir(1, 1, ["saadi"]))

    assert len(results) == 1
    assert not results[0].ok
    assert results[0].error == "no_data"


# ── fetch_ayah_text ────────────────────────────────────────────────────────

def test_fetch_ayah_text_success(monkeypatch, tmp_path):
    import app.services.tafsir_service as svc
    monkeypatch.setattr(svc, "_TELEMETRY_DB", tmp_path / "test_ayah.db")

    ayah_response = {
        "jsonrpc": "2.0", "id": 4,
        "result": {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "surah": 1, "ayah": 1,
                    "text": "بِسْمِ اللَّهِ الرَّحْمَنِ الرَّحِيمِ",
                }),
            }],
            "isError": False,
        },
    }

    with patch(
        "app.services.tafsir_service._mcp_call",
        new_callable=AsyncMock,
        return_value=ayah_response["result"],
    ):
        text = asyncio.run(fetch_ayah_text(1, 1))

    assert text is not None
    assert "بسم" in text or "بِسْم" in text


def test_fetch_ayah_text_failure_returns_none(monkeypatch, tmp_path):
    import app.services.tafsir_service as svc
    monkeypatch.setattr(svc, "_TELEMETRY_DB", tmp_path / "test_ayah_fail.db")

    with patch(
        "app.services.tafsir_service._mcp_call",
        new_callable=AsyncMock,
        return_value=None,
    ):
        text = asyncio.run(fetch_ayah_text(1, 1))

    assert text is None


# ── search_quran ───────────────────────────────────────────────────────────

def test_search_quran_success(monkeypatch, tmp_path):
    import app.services.tafsir_service as svc
    monkeypatch.setattr(svc, "_TELEMETRY_DB", tmp_path / "test_search.db")

    search_response = {
        "jsonrpc": "2.0", "id": 5,
        "result": {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "result": [
                        {"surah": 1, "ayah": 1, "text": "بسم الله", "snippet": "بسم"},
                        {"surah": 55, "ayah": 1, "text": "الرحمن", "snippet": "الرحمن"},
                    ],
                }),
            }],
            "isError": False,
        },
    }

    with patch(
        "app.services.tafsir_service._mcp_call",
        new_callable=AsyncMock,
        return_value=search_response["result"],
    ):
        results = asyncio.run(search_quran("رحمن", limit=5))

    assert len(results) == 2
    assert results[0]["surah"] == 1


def test_search_quran_failure_returns_empty(monkeypatch, tmp_path):
    import app.services.tafsir_service as svc
    monkeypatch.setattr(svc, "_TELEMETRY_DB", tmp_path / "test_search_fail.db")

    with patch(
        "app.services.tafsir_service._mcp_call",
        new_callable=AsyncMock,
        return_value=None,
    ):
        results = asyncio.run(search_quran("anything"))

    assert results == []


def test_search_quran_uses_items_key(monkeypatch, tmp_path):
    """Production MCP returns {items: [...]}; search_quran must fall back to it."""
    import app.services.tafsir_service as svc
    monkeypatch.setattr(svc, "_TELEMETRY_DB", tmp_path / "test_search_items.db")

    search_response = {
        "jsonrpc": "2.0", "id": 5,
        "result": {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "total": 2,
                    "items": [
                        {"surah": 2, "ayah": 255, "text": "الله لا إله إلا هو", "snippet": "الله"},
                    ],
                }),
            }],
            "isError": False,
        },
    }

    with patch(
        "app.services.tafsir_service._mcp_call",
        new_callable=AsyncMock,
        return_value=search_response["result"],
    ):
        results = asyncio.run(search_quran("الله", limit=5))

    assert len(results) == 1
    assert results[0]["surah"] == 2
    assert results[0]["ayah"] == 255


def test_search_quran_uses_structured_content(monkeypatch, tmp_path):
    """Production MCP returns results under structuredContent.result."""
    import app.services.tafsir_service as svc
    monkeypatch.setattr(svc, "_TELEMETRY_DB", tmp_path / "test_search_struct.db")

    search_response = {
        "jsonrpc": "2.0", "id": 5,
        "result": {
            "content": [
                {"type": "text", "text": json.dumps({"surah": 55, "ayah": 1, "text": "الرحمن", "snippet": "الرحمن"})},
                {"type": "text", "text": json.dumps({"surah": 1, "ayah": 3, "text": "الرحمن الرحيم", "snippet": "الرحمن الرحيم"})},
            ],
            "structuredContent": {
                "result": [
                    {"surah": 55, "ayah": 1, "text": "الرحمن", "snippet": "الرحمن"},
                    {"surah": 1, "ayah": 3, "text": "الرحمن الرحيم", "snippet": "الرحمن الرحيم"},
                    {"surah": 1, "ayah": 1, "text": "بسم الله الرحمن الرحيم", "snippet": "بسم الله الرحمن الرحيم"},
                ],
            },
            "isError": False,
        },
    }

    with patch(
        "app.services.tafsir_service._mcp_call",
        new_callable=AsyncMock,
        return_value=search_response["result"],
    ):
        results = asyncio.run(search_quran("الرحمن", limit=5))

    assert len(results) == 3
    assert results[0]["surah"] == 55


# ── search_in_tafsir ───────────────────────────────────────────────────────

def test_search_in_tafsir_uses_items_key(monkeypatch, tmp_path):
    """Production MCP returns {items: [...]} for search_in_tafsir too."""
    import app.services.tafsir_service as svc
    monkeypatch.setattr(svc, "_TELEMETRY_DB", tmp_path / "test_search_tafsir_items.db")

    search_response = {
        "jsonrpc": "2.0", "id": 6,
        "result": {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "total": 1,
                    "items": [
                        {
                            "surah": 1, "ayah": 1,
                            "tafsir_excerpt": "تفسير بسم الله",
                            "source_attribution": "السعدي",
                        },
                    ],
                }),
            }],
            "isError": False,
        },
    }

    with patch(
        "app.services.tafsir_service._mcp_call",
        new_callable=AsyncMock,
        return_value=search_response["result"],
    ):
        results = asyncio.run(search_in_tafsir("الرحمن", source="saadi", limit=5))

    assert len(results) == 1
    assert results[0]["surah"] == 1
    assert results[0]["tafsir_excerpt"] == "تفسير بسم الله"


def test_search_in_tafsir_uses_structured_content(monkeypatch, tmp_path):
    """Production MCP returns tafsir search results under structuredContent.result."""
    import app.services.tafsir_service as svc
    monkeypatch.setattr(svc, "_TELEMETRY_DB", tmp_path / "test_search_tafsir_struct.db")

    search_response = {
        "jsonrpc": "2.0", "id": 6,
        "result": {
            "content": [
                {"type": "text", "text": json.dumps({"surah": 1, "ayah": 1, "tafsir_excerpt": "A", "source_attribution": "x"})},
            ],
            "structuredContent": {
                "result": [
                    {"surah": 1, "ayah": 1, "tafsir_excerpt": "تفسير بسم الله", "source_attribution": "السعدي"},
                    {"surah": 1, "ayah": 3, "tafsir_excerpt": "تفسير الرحمن", "source_attribution": "السعدي"},
                ],
            },
            "isError": False,
        },
    }

    with patch(
        "app.services.tafsir_service._mcp_call",
        new_callable=AsyncMock,
        return_value=search_response["result"],
    ):
        results = asyncio.run(search_in_tafsir("الرحمن", source="saadi", limit=5))

    assert len(results) == 2
    assert results[0]["tafsir_excerpt"] == "تفسير بسم الله"


# ── list_tafsir_sources ───────────────────────────────────────────────────

def test_list_tafsir_sources_uses_items_key(monkeypatch, tmp_path):
    """Production MCP returns {total, items: [...]} for sources list."""
    import app.services.tafsir_service as svc
    monkeypatch.setattr(svc, "_TELEMETRY_DB", tmp_path / "test_sources_items.db")

    sources_response = {
        "jsonrpc": "2.0", "id": 7,
        "result": {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "total": 2,
                    "items": [
                        {"slug": "saadi", "name": "تيسير الكريم الرحمن", "author": "السعدي"},
                        {"slug": "moyassar", "name": "الميسر", "author": "الملك سلمان"},
                    ],
                }),
            }],
            "isError": False,
        },
    }

    with patch(
        "app.services.tafsir_service._mcp_call",
        new_callable=AsyncMock,
        return_value=sources_response["result"],
    ):
        sources = asyncio.run(list_tafsir_sources())

    assert len(sources) == 2
    assert sources[0]["slug"] == "saadi"
    assert sources[1]["slug"] == "moyassar"


# ── Display formatting ──────────────────────────────────────────────────────

def test_format_tafsir_for_display_success():
    r = TafsirResult(
        surah=1, ayah=1, source="saadi",
        attribution="تيسير الكريم الرحمن، السعدي",
        text="هذا تفسير الآية",
    )
    formatted = format_tafsir_for_display(r)
    assert "📖" in formatted
    assert "تيسير الكريم الرحمن" in formatted
    assert "هذا تفسير الآية" in formatted


def test_format_tafsir_for_display_with_footnotes():
    r = TafsirResult(
        surah=1, ayah=1, source="saadi",
        attribution="السعدي",
        text="النص",
        footnotes=[{"index": 1, "marker": "[1]", "text": "حاشية"}],
    )
    formatted = format_tafsir_for_display(r)
    assert "[1]" in formatted
    assert "حاشية" in formatted


def test_format_tafsir_for_display_error():
    r = TafsirResult(
        surah=1, ayah=1, source="saadi",
        attribution="", text="", error="unavailable",
    )
    formatted = format_tafsir_for_display(r)
    assert formatted == FALLBACK_MESSAGE


def test_format_tafsir_for_context_drops_errors():
    """Context formatter silently drops failed results."""
    results = [
        TafsirResult(surah=1, ayah=1, source="saadi",
                     attribution="السعدي", text="نص سعدي"),
        TafsirResult(surah=1, ayah=1, source="tabari",
                     attribution="", text="", error="unavailable"),
    ]
    ctx = format_tafsir_for_context(results)
    assert "سعدي" in ctx
    assert "tabari" not in ctx  # error dropped
    assert "---" not in ctx  # only one valid result, no separator


def test_format_tafsir_for_context_empty():
    ctx = format_tafsir_for_context([])
    assert ctx == ""


# ── TafsirResult properties ─────────────────────────────────────────────────

def test_tafsir_result_ok_property():
    assert TafsirResult(
        surah=1, ayah=1, source="saadi",
        attribution="x", text="y",
    ).ok is True

    assert TafsirResult(
        surah=1, ayah=1, source="saadi",
        attribution="", text="", error="x",
    ).ok is False

    assert TafsirResult(
        surah=1, ayah=1, source="saadi",
        attribution="x", text="",
    ).ok is False


# ── Ayah detection ─────────────────────────────────────────────────────────

def test_detect_ayah_surah_name_with_ayah_number():
    """تفسير سورة البقرة آية 255 → (2, 255)"""
    from app.services.tafsir_service import detect_ayah_reference
    assert detect_ayah_reference("تفسير سورة البقرة آية 255") == (2, 255)


def test_detect_ayah_sharh_prefix():
    """شرح الفاتحة 1 → (1, 1)"""
    from app.services.tafsir_service import detect_ayah_reference
    assert detect_ayah_reference("شرح الفاتحة 1") == (1, 1)


def test_detect_ayah_bare_name_number():
    """البقرة 255 → (2, 255)"""
    from app.services.tafsir_service import detect_ayah_reference
    assert detect_ayah_reference("البقرة 255") == (2, 255)


def test_detect_ayah_numeric_surah():
    """سورة 2 آية 255 → (2, 255)"""
    from app.services.tafsir_service import detect_ayah_reference
    assert detect_ayah_reference("سورة 2 آية 255") == (2, 255)


def test_detect_ayah_in_question_context():
    """ايه تفسير سورة الفاتحة آية 1 عشان ابني يسأل عنها؟ → (1, 1)"""
    from app.services.tafsir_service import detect_ayah_reference
    assert detect_ayah_reference("ايه تفسير سورة الفاتحة آية 1 عشان ابني يسأل عنها؟") == (1, 1)


def test_detect_ayah_none_when_no_reference():
    """ابني ما يحبش يصلي → None"""
    from app.services.tafsir_service import detect_ayah_reference
    assert detect_ayah_reference("ابني ما يحبش يصلي") is None


def test_detect_ayah_none_for_empty():
    from app.services.tafsir_service import detect_ayah_reference
    assert detect_ayah_reference("") is None
    assert detect_ayah_reference(None) is None  # type: ignore[arg-type]


def test_detect_ayah_yaseen():
    """تفسير يس 1 → (36, 1)"""
    from app.services.tafsir_service import detect_ayah_reference
    assert detect_ayah_reference("تفسير يس 1") == (36, 1)


def test_detect_ayah_alkursi_verse():
    """الآية الكرسي: سورة البقرة آية 255 → (2, 255)"""
    from app.services.tafsir_service import detect_ayah_reference
    text = "ابني حافظ آية الكرسي، شرح سورة البقرة آية 255"
    assert detect_ayah_reference(text) == (2, 255)


def test_detect_ayah_by_opening_text_bismillah():
    """تفسير بسم الله الرحمن الرحيم → (1, 1) — آية بلا رقم، بفتحتها."""
    from app.services.tafsir_service import detect_ayah_reference
    assert detect_ayah_reference("تفسير بسم الله الرحمن الرحيم") == (1, 1)


def test_detect_ayah_by_opening_text_ikhlas():
    """تفسير قل هو الله أحد → (112, 1) — نص آية بلا رقم."""
    from app.services.tafsir_service import detect_ayah_reference
    assert detect_ayah_reference("تفسير قل هو الله أحد") == (112, 1)


def test_detect_ayah_by_name_kursi():
    """ما تفسير آية الكرسي → (2, 255) — الاسم المشهور بلا رقم."""
    from app.services.tafsir_service import detect_ayah_reference
    assert detect_ayah_reference("ما تفسير آية الكرسي") == (2, 255)


def test_resolve_ayah_reference_quoted_text_uses_full_quran_search():
    """اقتباس آية عشوائية → يبحث في القرآن كله ويرجع (سورة، آية)."""
    from app.services import tafsir_service as svc
    # A verse not in the well-known map: سورة النحل آية 125 (ادْعُ إِلَىٰ سَبِيلِ رَبِّكَ)
    q = "تفسير ادْعُ إِلَىٰ سَبِيلِ رَبِّكَ بِالْحِكْمَةِ وَالْمَوْعِظَةِ الْحَسَنَةِ"
    fake_hits = [
        {
            "surah": 16,
            "ayah": 125,
            "text": "ادْعُ إِلَىٰ سَبِيلِ رَبِّكَ بِالْحِكْمَةِ وَالْمَوْعِظَةِ الْحَسَنَةِ",
            "snippet": "ادْعُ إِلَىٰ سَبِيلِ رَبِّكَ",
        },
    ]
    with patch.object(svc, "search_quran", AsyncMock(return_value=fake_hits)):
        got = asyncio.run(svc.resolve_ayah_reference(q))
    assert got == (16, 125)


def test_resolve_ayah_reference_no_match_returns_none():
    """سؤال تربوي عام من غير اقتباس آية → None (مفيش بحث مضلل)."""
    from app.services import tafsir_service as svc
    with patch.object(svc, "search_quran", AsyncMock(return_value=[])) as m:
        got = asyncio.run(svc.resolve_ayah_reference("كيف أربي طفلي على الصدق؟"))
    assert got is None


def test_resolve_ayah_reference_matches_loose_spelling_of_hashr():
    """صيغة المستخدم المرنة لآية الحشر 22 → (59, 22) عبر overlap مش anchor صارم."""
    from app.services import tafsir_service as svc
    q = "الله لا اله الا هو عالم الغيب والشهادة هو الرحمن الرحيم"
    fake_hits = [{
        "surah": 59, "ayah": 22,
        "text": "هُوَ اللَّهُ الَّذِي لَا إِلَٰهَ إِلَّا هُوَ عَالِمُ الْغَيْبِ وَالشَّهَادَةِ هُوَ الرَّحْمَٰنُ الرَّحِيمُ",
    }]
    with patch.object(svc, "search_quran", AsyncMock(return_value=fake_hits)):
        got = asyncio.run(svc.resolve_ayah_reference(q))
    assert got == (59, 22)


def test_resolve_ayah_reference_rejects_generic_question_sharing_a_word():
    """سؤال عام فيه كلمة من آية (مش اقتباس آية) → None، ضد الـ false positive."""
    from app.services import tafsir_service as svc
    q = "بنتي بتحب تقرا عن سبيل ربك في القصص"  # shares 'سبيل ربك' but not an ayah
    fake_hits = [{
        "surah": 16, "ayah": 125,
        "text": "ادْعُ إِلَىٰ سَبِيلِ رَبِّكَ بِالْحِكْمَةِ وَالْمَوْعِظَةِ الْحَسَنَةِ",
    }]
    with patch.object(svc, "search_quran", AsyncMock(return_value=fake_hits)):
        got = asyncio.run(svc.resolve_ayah_reference(q))
    assert got is None


def test_detect_ayah_long_verse_adyan_via_dict():
    """آية الدين (2,282) — طويلة فـ overlap ratio بيفشل، بتتلتقط بالقاموس."""
    from app.services.tafsir_service import detect_ayah_reference
    q = "يا أيها الذين آمنوا إذا تداينتم بدين إلى أجل مسمى"
    assert detect_ayah_reference(q) == (2, 282)


def test_detect_ayah_ikhlas_via_dict():
    """قل هو الله أحد → (112, 1) من القاموس (نص صريح)."""
    from app.services.tafsir_service import detect_ayah_reference
    assert detect_ayah_reference("تفسير قل هو الله أحد") == (112, 1)