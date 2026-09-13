"""
Test the cinematic landing page and modern interactive components.
"""
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_cinematic_landing_page_renders():
    for path in ["/", "/go"]:
        response = client.get(path)
        assert response.status_code == 200
        html = response.text

        # Verify 4 key pillars are present
        assert "hero-canvas-section" in html
        assert "hero-canvas" in html
        assert "trust-carousel" in html
        assert "bento-features" in html
        assert "model-3d-section" in html
        assert "model-viewer" in html
        assert "guardian_shield.glb" in html
        assert "mountHeroCanvasScrubber" in html

def test_static_assets_accessible():
    # Test GLB 3D model
    glb_res = client.get("/ui/assets/3d/guardian_shield.glb")
    assert glb_res.status_code == 200
    assert len(glb_res.content) > 0

    # Test sample hero frame
    frame_res = client.get("/ui/assets/hero_frames/frame_001.jpg")
    assert frame_res.status_code == 200
    assert len(frame_res.content) > 0

    # Test hero start and end images
    img_start = client.get("/ui/assets/hero_start.jpg")
    assert img_start.status_code == 200
    img_end = client.get("/ui/assets/hero_end.jpg")
    assert img_end.status_code == 200
