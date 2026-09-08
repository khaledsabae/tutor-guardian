"""Tests for quranic_linguistics_service — Bahouth MCP client, caching, fallback.

These tests mock the HTTP layer (httpx.AsyncClient) so they never hit the
live Bahouth MCP server. They verify the four acceptance criteria from
Salem's review:

  1. find_root with tashkeel works after normalize (plain root lookup)
  2. Responses larger than 50 verses are paginated (server cap = 50)
  3. Server outage → graceful fallback (timeout/error → error result)
  4. Repeated requests served from cache (keyed on INPUT TEXT, not root_id)
"""
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.quranic_linguistics_service import (
    RootResult,
    VerseListResult,
    find_root,
    list_root_verses,
    list_topic_verses,
    list_verse_qiraat,
    get_verse,
    list_verse_words,
    list_verse_properties,
    list_verse_topics,
    list_surah_verses,
    format_root_for_display,
    format_verses_for_display,
    format_verses_for_context,
    FALLBACK_MESSAGE,
    _normalize_arabic,
    _parse_sse_response,
    _cache_key,
    BAHOUTH_MAX_LIMIT,
)


# ── Helpers ────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _disable_cache(monkeypatch):
    """Disable the SQLite cache for every test.

    The cache is a real shared SQLite file (ops/sessions.db) — without this
    fixture, results cached by one test leak into the next and break the
    server-down / cache-hit assertions.
    """
    monkeypatch.setattr(
        "app.services.quranic_linguistics_service.BAHOUTH_CACHE_ENABLED", False
    )


def _mcp_response(text: str) -> dict:
    """Shape of a successful MCP tools/call result."""
    return {
        "content": [{"type": "text", "text": text}],
        "isError": False,
    }


def _mock_post(result: dict | None, status: int = 200):
    """Patch httpx.AsyncClient.post to return a canned SSE response.

    The service uses `async with httpx.AsyncClient(...)`, so the mock must
    support the async context manager protocol (__aenter__/__aexit__).
    The payload is wrapped in the JSON-RPC envelope the service expects:
    {"jsonrpc":"2.0","id":1,"result": <result>}.
    """
    mock_resp = MagicMock()
    mock_resp.status_code = status
    if result is None:
        mock_resp.text = ""
    else:
        envelope = {"jsonrpc": "2.0", "id": 1, "result": result}
        mock_resp.text = f'event: message\ndata: {json.dumps(envelope)}\n'
    mock_client = AsyncMock()
    mock_client.post.return_value = mock_resp
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = False
    return patch(
        "app.services.quranic_linguistics_service.httpx.AsyncClient",
        return_value=mock_client,
    )


def _mock_client_with(fake_post):
    """Build an async-context-manager mock client whose post is fake_post."""
    mock_client = AsyncMock()
    mock_client.post = fake_post
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = False
    return mock_client


# ── Acceptance 1: find_root with tashkeel works after normalize ─────────────

def test_normalize_arabic_strips_tashkeel():
    """«صَبَرَ» المشكول يتحول لـ«صبر» المجرد — السيرفر بيقبل المجرد بس."""
    assert _normalize_arabic("صَبَرَ") == "صبر"
    # Same behaviour as tafsir_service: shadda is stripped, the alef after
    # lam stays plain → اللّٰه → اللاه (not الله).
    assert _normalize_arabic("بِسْمِ اللّٰهِ") == "بسم اللاه"
    assert _normalize_arabic("عٰلِمُ") == "عالم"


def test_find_root_sends_normalized_text():
    """find_root لازم يبعت النص المجرد للسيرفر (مش المشكول)."""
    captured = {}

    async def fake_post(url, json=None, headers=None):
        captured["arguments"] = json["params"]["arguments"]
        return MagicMock(
            status_code=200,
            text='event: message\ndata: {"jsonrpc":"2.0","id":1,"result":'
                 '{"content":[{"type":"text","text":"{\\"found\\":true,\\"root_id\\":234,'
                 '\\"frequency\\":103}"}],"isError":false}}\n',
        )

    mock_client = _mock_client_with(fake_post)
    with patch(
        "app.services.quranic_linguistics_service.httpx.AsyncClient",
        return_value=mock_client,
    ):
        result = asyncio.run(find_root("صَبَرَ"))

    assert captured["arguments"]["root_text"] == "صبر"
    assert result.found is True
    assert result.root_id == 234
    assert result.frequency == 103


def test_find_root_not_found():
    """جذر غير موجود → found=false من غير error."""
    with _mock_post(_mcp_response('{"found":false}')):
        result = asyncio.run(find_root("xyz"))
    assert result.found is False
    assert result.error is None


# ── Acceptance 2: pagination — server cap is 50 ─────────────────────────────

def test_list_root_verses_clamps_limit_to_50():
    """limit فوق السقف يتقصّ على 50 — السيرفر بيرفض الـ500."""
    captured = {}

    async def fake_post(url, json=None, headers=None):
        captured["arguments"] = json["params"]["arguments"]
        return MagicMock(
            status_code=200,
            text='event: message\ndata: {"jsonrpc":"2.0","id":1,"result":'
                 '{"content":[{"type":"text","text":"{\\"verses\\":[{\\"verse_key\\":'
                 '\\"2-45\\",\\"text\\":\\"وَاسْتَعِينُوا بِالصَّبْرِ\\"}],'
                 '\\"total\\":103}"}],"isError":false}}\n',
        )

    mock_client = _mock_client_with(fake_post)
    with patch(
        "app.services.quranic_linguistics_service.httpx.AsyncClient",
        return_value=mock_client,
    ):
        result = asyncio.run(list_root_verses("صبر", limit=500))

    assert captured["arguments"]["limit"] == BAHOUTH_MAX_LIMIT
    assert result.ok
    assert result.total == 103


def test_list_root_verses_pagination_offset():
    """الصفحة التانية بتبعت offset=50 — 50+43=103 لصبر."""
    captured = {}

    async def fake_post(url, json=None, headers=None):
        captured["arguments"] = json["params"]["arguments"]
        return MagicMock(
            status_code=200,
            text='event: message\ndata: {"jsonrpc":"2.0","id":1,"result":'
                 '{"content":[{"type":"text","text":"{\\"verses\\":[],'
                 '\\"total\\":103}"}],"isError":false}}\n',
        )

    mock_client = _mock_client_with(fake_post)
    with patch(
        "app.services.quranic_linguistics_service.httpx.AsyncClient",
        return_value=mock_client,
    ):
        result = asyncio.run(list_root_verses("صبر", limit=50, offset=50))

    assert captured["arguments"]["offset"] == 50
    assert result.ok


# ── Acceptance 3: server outage → graceful fallback ─────────────────────────

def test_find_root_server_down_returns_error():
    """السيرفر وقع → error=unavailable (مش exception)."""
    with _mock_post(None, status=500):
        result = asyncio.run(find_root("صبر"))
    assert result.error == "unavailable"
    assert result.found is False
    assert format_root_for_display(result) == FALLBACK_MESSAGE


def test_find_root_timeout_returns_error():
    """Timeout → error=unavailable."""
    mock_client = AsyncMock()
    mock_client.post.side_effect = asyncio.TimeoutError()
    with patch(
        "app.services.quranic_linguistics_service.httpx.AsyncClient",
        return_value=mock_client,
    ):
        result = asyncio.run(find_root("صبر"))
    assert result.error == "unavailable"


def test_list_root_verses_server_down_returns_error():
    with _mock_post(None, status=500):
        result = asyncio.run(list_root_verses("صبر"))
    assert result.error == "unavailable"
    assert format_verses_for_display(result) == FALLBACK_MESSAGE


# ── Acceptance 4: repeated requests served from cache ───────────────────────

def test_find_root_second_call_served_from_cache():
    """تكرار نفس الطلب → من الكاش (post بيتنادى مرة واحدة بس)."""
    calls = {"n": 0}
    # جذر فريد — مضمون إنه مش موجود في الـ cache الحقيقي من تشغيلات سابقة
    root = "زبرجد"

    async def fake_post(url, json=None, headers=None):
        calls["n"] += 1
        return MagicMock(
            status_code=200,
            text='event: message\ndata: {"jsonrpc":"2.0","id":1,"result":'
                 '{"content":[{"type":"text","text":"{\\"found\\":true,\\"root_id\\":234,'
                 '\\"frequency\\":103}"}],"isError":false}}\n',
        )

    mock_client = _mock_client_with(fake_post)
    with patch(
        "app.services.quranic_linguistics_service.httpx.AsyncClient",
        return_value=mock_client,
    ), patch(
        "app.services.quranic_linguistics_service.BAHOUTH_CACHE_ENABLED", True
    ):
        r1 = asyncio.run(find_root(root))
        r2 = asyncio.run(find_root(root))

    assert calls["n"] == 1  # الطلب التاني من الكاش
    assert r1.found is True and r2.found is True
    assert r2.cached is True


def test_cache_key_on_input_text_not_root_id():
    """الكاش على النص المُدخل — نفس الجذر بنفس النص = نفس المفتاح."""
    k1 = _cache_key("find_root", {"root_text": "صبر"})
    k2 = _cache_key("find_root", {"root_text": "صبر"})
    k3 = _cache_key("find_root", {"root_text": "صبر", "limit": 50})
    assert k1 == k2
    assert k1 != k3


# ── verse_key format validation ─────────────────────────────────────────────

def test_verse_key_must_use_dash():
    """verse_key بصيغة «2-255» بشرطة — مش «2:255»."""
    with _mock_post(_mcp_response('{"text":"آية الكرسي"}')):
        result = asyncio.run(get_verse("2-255"))
    assert result is not None

    with _mock_post(_mcp_response('{"text":"آية الكرسي"}')):
        result = asyncio.run(get_verse("2:255"))
    assert result is None  # صيغة غلط → مرفوض قبل ما يوصل السيرفر


def test_list_verse_qiraat_bad_key_rejected():
    result = asyncio.run(list_verse_qiraat("2:255"))
    assert result.error == "bad_key"


# ── Formatting ─────────────────────────────────────────────────────────────

def test_format_root_for_display():
    r = RootResult(root_text="صبر", found=True, root_id=234, frequency=103)
    out = format_root_for_display(r)
    assert "103" in out
    assert "صبر" in out


def test_format_verses_for_display_truncates():
    verses = [{"verse_key": f"2-{i}", "text": f"نص {i}"} for i in range(10)]
    r = VerseListResult(tool="list_root_verses", query_key="صبر", verses=verses, total=103)
    out = format_verses_for_display(r, max_verses=3)
    assert "و7 آيات أخرى" in out


def test_format_verses_for_context_skips_errors():
    r = VerseListResult(tool="list_root_verses", query_key="صبر", error="unavailable")
    assert format_verses_for_context(r) == ""


# ── SSE parsing (shared transport) ─────────────────────────────────────────

def test_parse_sse_response_extracts_json():
    raw = 'event: message\r\ndata: {"jsonrpc":"2.0","id":1,"result":{"ok":true}}\r\n'
    data = _parse_sse_response(raw)
    assert data is not None
    assert data["result"]["ok"] is True


def test_parse_sse_response_no_data_line():
    raw = "event: message\r\n\r\n"
    assert _parse_sse_response(raw) is None
