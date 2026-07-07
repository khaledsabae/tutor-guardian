"""Integration tests for the QR Web App (Phase 4)."""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import child_token as child_token_service


@pytest.fixture
def parent_client():
    return TestClient(app)


@pytest.fixture
def parent(parent_client):
    r = parent_client.post("/api/chat/sessions")
    assert r.status_code == 201
    return parent_client, r.json()["token"]


@pytest.fixture
def teen_child(parent):
    client, token = parent
    r = client.post(
        "/api/children",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "teen", "age_group": "13-15", "avatar_emoji": "🧑"},
    )
    assert r.status_code == 201, r.text
    return client, token, r.json()["id"]


def test_create_web_claim_returns_one_time_url(teen_child):
    client, token, child_id = teen_child
    r = client.post(
        "/api/value-tracking/child-web-claims",
        headers={"Authorization": f"Bearer {token}"},
        params={"child_id": child_id},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["child_id"] == child_id
    assert data["claim_code"]
    assert data["claim_url"].startswith("http://testserver/child-mode/web/?claim=")
    assert data["expires_in_seconds"] == 120


def test_redeem_claim_code_issues_long_lived_web_token(teen_child):
    client, token, child_id = teen_child
    r = client.post(
        "/api/value-tracking/child-web-claims",
        headers={"Authorization": f"Bearer {token}"},
        params={"child_id": child_id},
    )
    code = r.json()["claim_code"]

    r = client.post(f"/api/child-web/claim-session?claim={code}")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["token"]
    assert data["child_id"] == child_id
    assert data["child_name"] == "teen"
    assert data["age_group"] == "13-15"

    # The token is a 20-hour web token (habit_child_web scope).
    payload = child_token_service.verify_child_token(data["token"], allow_web=True)
    assert payload["scope"] == "habit_child_web"


def test_web_token_can_fetch_today_habits(teen_child):
    client, token, child_id = teen_child
    r = client.post(
        "/api/value-tracking/child-web-claims",
        headers={"Authorization": f"Bearer {token}"},
        params={"child_id": child_id},
    )
    code = r.json()["claim_code"]
    r = client.post(f"/api/child-web/claim-session?claim={code}")
    web_token = r.json()["token"]

    r = client.get(
        "/api/value-tracking/child-mode/today",
        headers={"Authorization": f"Child-Bearer {web_token}"},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["child_id"] == child_id
    assert isinstance(data["habits"], list)


def test_claim_code_is_single_use(teen_child):
    client, token, child_id = teen_child
    r = client.post(
        "/api/value-tracking/child-web-claims",
        headers={"Authorization": f"Bearer {token}"},
        params={"child_id": child_id},
    )
    code = r.json()["claim_code"]

    r = client.post(f"/api/child-web/claim-session?claim={code}")
    assert r.status_code == 200

    r = client.post(f"/api/child-web/claim-session?claim={code}")
    assert r.status_code == 410


def test_static_web_app_served(teen_child):
    client, *_ = teen_child
    r = client.get("/child-mode/web/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "ميزان العادات" in r.text


def test_claim_query_param_url_format(teen_child):
    client, token, child_id = teen_child
    r = client.post(
        "/api/value-tracking/child-web-claims",
        headers={"Authorization": f"Bearer {token}"},
        params={"child_id": child_id},
    )
    claim_url = r.json()["claim_url"]
    assert "/child-mode/web/?claim=" in claim_url
    assert "?token=" not in claim_url
    assert "&token=" not in claim_url
