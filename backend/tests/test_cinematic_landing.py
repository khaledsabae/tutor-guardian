"""
Test the cinematic landing page and modern interactive components.
"""
import re

import pytest
from fastapi.testclient import TestClient

from app.main import app

_PAGES = ["/", "/go", "/ui/"]


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_cinematic_landing_page_renders(client):
    for path in _PAGES:
        response = client.get(path)
        assert response.status_code == 200
        html = response.text

        # The pillars that remain
        assert "hero-canvas-section" in html
        assert "hero-canvas" in html
        assert "trust-carousel" in html
        assert "bento-features" in html
        assert "mountHeroCanvasScrubber" in html


def test_the_3d_shield_section_stays_removed(client):
    # Khaled, 2026-10-04: «٠٢ — مجسم درع الأمان التفاعلي» was useless,
    # incomplete and wrong — removed with its model-viewer script and asset.
    for path in _PAGES:
        html = client.get(path).text
        for gone in ("model-3d-section", "model-viewer", "guardian_shield", "مجسم"):
            assert gone not in html, f"{path}: {gone}"
    assert client.get("/ui/assets/3d/guardian_shield.glb").status_code == 404


def test_every_in_page_link_has_a_target(client):
    for path in _PAGES:
        html = client.get(path).text
        ids = set(re.findall(r'\bid="([^"]+)"', html))
        anchors = set(re.findall(r'href="#([^"]+)"', html))
        assert anchors, path
        assert anchors <= ids, f"{path}: dangling {sorted(anchors - ids)}"


def test_static_assets_accessible(client):
    # Test sample hero frame
    frame_res = client.get("/ui/assets/hero_frames/frame_001.jpg")
    assert frame_res.status_code == 200
    assert len(frame_res.content) > 0

    # Test hero start and end images
    img_start = client.get("/ui/assets/hero_start.jpg")
    assert img_start.status_code == 200
    img_end = client.get("/ui/assets/hero_end.jpg")
    assert img_end.status_code == 200
