"""
Smoke tests for public SEO pages added to backend/app/routers/seo.py.
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


# All 10 new pain-point pages plus the index
SEO_SLUGS = [
    "pray-child",
    "tantrums-child",
    "screen-time-child",
    "toilet-training",
    "lying-child",
    "sleep-child",
    "violent-games-child",
    "sibling-kindness",
    "quran-child",
    "shared-screen-toddler",
]


@pytest.mark.parametrize("slug", SEO_SLUGS)
def test_seo_page_200(client, slug):
    r = client.get(f"/seo/{slug}")
    assert r.status_code == 200
    assert "schema.org" in r.text or "المربّي" in r.text


def test_seo_index_200(client):
    r = client.get("/seo")
    assert r.status_code == 200
    for slug in SEO_SLUGS:
        assert f"/seo/{slug}" in r.text


def test_seo_page_not_found(client):
    r = client.get("/seo/does-not-exist")
    assert r.status_code == 404


def test_seo_schema_faq_in_page(client):
    r = client.get("/seo/pray-child")
    assert r.status_code == 200
    assert '"@type": "FAQPage"' in r.text


def test_seo_free_cta_in_page(client):
    r = client.get("/seo/tantrums-child")
    assert r.status_code == 200
    assert "مجاناً" in r.text
