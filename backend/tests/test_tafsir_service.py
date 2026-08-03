"""Tests for tafsir_service — MCP client, caching, and fallback behaviour.

These tests mock the HTTP layer (httpx.AsyncClient) so they never hit the
live Tafsir MCP server. They verify:
  - Correct parsing of MCP JSON-RPC/SSE responses
  - Cache hit/miss lifecycle
  - Graceful fallback when the server is unreachable
  - Display formatting
"""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.tafsir_service import (
    TafsirResult,
    fetch_tafsir,
    fetch_ayah_text,
    search_quran,
    format_tafsir_for_display,
    format_tafsir_for_context,
    FALLBACK_MESSAGE,
    _parse_sse_response,
    _cache_key,
    _cache_put,
    _cache_get,
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


@pytest.mark.asyncio
async def test_fetch_tafsir_success(monkeypatch, tmp_path):
    """Live fetch parses attribution + text + footnotes from MCP response."""
    # Point cache at temp DB
    import app.services.tafsir_service as svc
    monkeypatch.setattr(svc, "_TELEMETRY_DB", tmp_path / "test_tafsir.db")

    # Mock httpx.AsyncClient.post
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = _mock_sse_text(_MCP_TAFSIR_RESPONSE)

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.post = AsyncMock(return_value=mock_response)

    with patch("app.services.tafsir_service.httpx.AsyncClient", return_value=mock_client):
        results = await fetch_tafsir(1, 1, ["saadi"])

    assert len(results) == 1
    r = results[0]
    assert r.ok
    assert r.source == "saadi"
    assert r.attribution == "تيسير الكريم الرحمن، السعدي"
    assert "الفاتحة" in r.text
    assert r.footnotes is not None and len(r.footnotes) == 1
    assert not r.cached  # first call — not cached


@pytest.mark.asyncio
async def test_fetch_tafsir_cache_hit(monkeypatch, tmp_path):
    """Second call with same params should hit cache (no HTTP call)."""
    import app.services.tafsir_service as svc
    monkeypatch.setattr(svc, "_TELEMETRY_DB", tmp_path / "test_tafsir_cache.db")

    # First call: mock HTTP
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = _mock_sse_text(_MCP_TAFSIR_RESPONSE)

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.post = AsyncMock(return_value=mock_response)

    with patch("app.services.tafsir_service.httpx.AsyncClient", return_value=mock_client):
        results1 = await fetch_tafsir(1, 1, ["saadi"])
        # Second call — should NOT make an HTTP request
        mock_client.post = AsyncMock(
            side_effect=AssertionError("Should not call HTTP on cache hit")
        )
        results2 = await fetch_tafsir(1, 1, ["saadi"])

    assert results1[0].ok and not results1[0].cached
    assert results2[0].ok and results2[0].cached
    assert results1[0].text == results2[0].text


@pytest.mark.asyncio
async def test_fetch_tafsir_server_down(monkeypatch, tmp_path):
    """When MCP returns None (unreachable), result carries the error."""
    import app.services.tafsir_service as svc
    monkeypatch.setattr(svc, "_TELEMETRY_DB", tmp_path / "test_tafsir_down.db")

    with patch(
        "app.services.tafsir_service._mcp_call",
        new_callable=AsyncMock,
        return_value=None,
    ):
        results = await fetch_tafsir(1, 1, ["saadi"])

    assert len(results) == 1
    assert not results[0].ok
    assert results[0].error == "unavailable"
    assert results[0].text == ""


@pytest.mark.asyncio
async def test_fetch_tafsir_mcp_error(monkeypatch, tmp_path):
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
        results = await fetch_tafsir(1, 1, ["saadi"])

    assert len(results) == 1
    assert not results[0].ok
    assert results[0].error == "mcp_error"


@pytest.mark.asyncio
async def test_fetch_tafsir_no_data(monkeypatch, tmp_path):
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
        results = await fetch_tafsir(1, 1, ["saadi"])

    assert len(results) == 1
    assert not results[0].ok
    assert results[0].error == "no_data"


# ── fetch_ayah_text ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_fetch_ayah_text_success(monkeypatch, tmp_path):
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
        text = await fetch_ayah_text(1, 1)

    assert text is not None
    assert "بسم" in text or "بِسْم" in text


@pytest.mark.asyncio
async def test_fetch_ayah_text_failure_returns_none(monkeypatch, tmp_path):
    import app.services.tafsir_service as svc
    monkeypatch.setattr(svc, "_TELEMETRY_DB", tmp_path / "test_ayah_fail.db")

    with patch(
        "app.services.tafsir_service._mcp_call",
        new_callable=AsyncMock,
        return_value=None,
    ):
        text = await fetch_ayah_text(1, 1)

    assert text is None


# ── search_quran ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_search_quran_success(monkeypatch, tmp_path):
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
        results = await search_quran("رحمن", limit=5)

    assert len(results) == 2
    assert results[0]["surah"] == 1


@pytest.mark.asyncio
async def test_search_quran_failure_returns_empty(monkeypatch, tmp_path):
    import app.services.tafsir_service as svc
    monkeypatch.setattr(svc, "_TELEMETRY_DB", tmp_path / "test_search_fail.db")

    with patch(
        "app.services.tafsir_service._mcp_call",
        new_callable=AsyncMock,
        return_value=None,
    ):
        results = await search_quran("anything")

    assert results == []


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