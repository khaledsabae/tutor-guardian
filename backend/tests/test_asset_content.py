"""
Asset-content endpoint tests — GET /api/program/asset-content/{asset_id}.

Validates the additive v1 endpoint that serves full flashcard/quiz JSON
content to the mobile app (the lesson-assets endpoint only lists metadata).
Mounts only the program router so the heavy RAG stack is never imported.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import curriculum_loader as cl
from app.routers.program import router as program_router


@pytest.fixture
def client():
    cl.load_curriculum()
    a = FastAPI()
    a.include_router(program_router, prefix="/api")
    with TestClient(a) as c:
        yield c


def _first_flashcard_id():
    for bundle in cl._assets_cache.values():
        for entry in bundle.get("flashcards", []) or []:
            if entry.get("id"):
                return entry["id"]
    return None


def test_asset_content_returns_cards(client):
    asset_id = _first_flashcard_id()
    if not asset_id:
        pytest.skip("no flashcard assets wired in lesson_index (clean-asset regeneration in progress)")
    r = client.get(f"/api/program/asset-content/{asset_id}")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == asset_id
    assert body["kind"] == "flashcards"
    assert isinstance(body["cards"], list) and body["cards"]
    assert "front" in body["cards"][0] and "back" in body["cards"][0]


def test_asset_content_unknown_id_404(client):
    r = client.get("/api/program/asset-content/nonexistent-id")
    assert r.status_code == 404


def test_asset_content_traversal_rejected(client):
    r = client.get("/api/program/asset-content/..%2F..%2Fetc%2Fpasswd")
    assert r.status_code == 404


def test_asset_content_is_cached(client):
    asset_id = _first_flashcard_id()
    first = cl.get_asset_content(asset_id)
    assert cl.get_asset_content(asset_id) is first
