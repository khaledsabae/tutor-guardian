"""
Curriculum search endpoint tests — GET /api/program/search.

Additive v1 endpoint: substring search across published lessons, paths,
and daily tips. Mounts only the program router (no heavy RAG imports).
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


def test_search_finds_lessons(client):
    r = client.get("/api/program/search", params={"q": "الصلاة"})
    assert r.status_code == 200
    body = r.json()
    assert body["query"] == "الصلاة"
    assert body["count"] >= 1
    assert all({"type", "id", "title", "age_group"} <= set(item) for item in body["results"])
    # at least one lesson result mentions prayer
    assert any(it["type"] == "lesson" for it in body["results"])


def test_search_title_matches_rank_first(client):
    r = client.get("/api/program/search", params={"q": "التنمر"})
    results = r.json()["results"]
    assert results, "expected matches for التنمر"
    # the first result should have the term in its title
    assert "التنمر" in results[0]["title"]


def test_search_respects_limit(client):
    r = client.get("/api/program/search", params={"q": "نوم", "limit": 3})
    assert r.status_code == 200
    assert len(r.json()["results"]) <= 3


def test_search_min_length_rejected(client):
    r = client.get("/api/program/search", params={"q": "ا"})
    assert r.status_code == 422  # min_length=2


def test_search_no_match_empty(client):
    r = client.get("/api/program/search", params={"q": "zzzqqq"})
    assert r.status_code == 200
    assert r.json()["count"] == 0
