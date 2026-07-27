"""
Regression tests for GET /privacy-policy.

The endpoint is a Google Play requirement, and on 2026-07-27 it was serving a
200 with an empty body in production: docs/ is bind-mounted from the host, the
rsynced privacy-policy.md was mode 0600 owned by uid 1000, and the container
runs as uid 10001. The old guard only asked `is_file()`, which passes on an
unreadable file, so FileResponse sent headers and then failed to open it.
Cloudflare reported that truncated response as an opaque 520 and the deploy
smoke test rolled back with no usable diagnosis.
"""
import os

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers import privacy


@pytest.fixture
def client():
    return TestClient(app)


def test_privacy_policy_is_served(client):
    resp = client.get("/privacy-policy")
    assert resp.status_code == 200
    assert resp.content, "privacy policy served an empty body"
    assert "markdown" in resp.headers["content-type"]


def test_unreadable_file_returns_503_not_empty_200(client, tmp_path, monkeypatch):
    """An existing-but-unreadable file must fail loudly, not serve a broken 200."""
    unreadable = tmp_path / "privacy-policy.md"
    unreadable.write_text("# secret", encoding="utf-8")
    unreadable.chmod(0o000)

    # Root bypasses permission bits, so this check is meaningless as root.
    if os.access(unreadable, os.R_OK):
        pytest.skip("running as root — permission bits are not enforced")

    monkeypatch.setattr(privacy, "PRIVACY_POLICY_PATH", unreadable)

    resp = client.get("/privacy-policy")
    assert resp.status_code == 503
    assert resp.content, "503 should still carry an explanatory body"


def test_missing_file_returns_503(client, tmp_path, monkeypatch):
    monkeypatch.setattr(privacy, "PRIVACY_POLICY_PATH", tmp_path / "nope.md")

    resp = client.get("/privacy-policy")
    assert resp.status_code == 503
