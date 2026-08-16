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


# ── The router the middleware could not see ────────────────────────────────
#
# /api/child-web sat outside _PROTECTED_PREFIXES and outside the child-mode
# prefix, so _is_protected returned False for it and the middleware never
# populated request.state. Both endpoints below read request.state.child_id
# and 401 when it is missing — which it always was. They answered 401 to every
# browser holding a perfectly valid token, and no test covered either one.


@pytest.fixture
def claimed_web_token(teen_child):
    client, token, child_id = teen_child
    r = client.post(
        "/api/value-tracking/child-web-claims",
        headers={"Authorization": f"Bearer {token}"},
        params={"child_id": child_id},
    )
    code = r.json()["claim_code"]
    r = client.post(f"/api/child-web/claim-session?claim={code}")
    assert r.status_code == 200, r.text
    return client, r.json()["token"], child_id


def test_me_returns_the_profile_for_a_valid_web_token(claimed_web_token):
    client, web_token, child_id = claimed_web_token
    r = client.get(
        "/api/child-web/me",
        headers={"Authorization": f"Child-Bearer {web_token}"},
    )
    assert r.status_code == 200, r.text
    assert r.json() == {"child_id": child_id, "child_name": "teen",
                        "age_group": "13-15"}


def test_refresh_issues_a_new_token_for_the_same_child(claimed_web_token):
    client, web_token, child_id = claimed_web_token
    r = client.post(
        "/api/child-web/refresh",
        headers={"Authorization": f"Child-Bearer {web_token}"},
    )
    assert r.status_code == 200, r.text
    fresh = r.json()["token"]
    assert r.json()["child_id"] == child_id
    payload = child_token_service.verify_child_token(fresh, allow_web=True)
    assert payload["child_id"] == child_id


def test_me_rejects_a_caller_with_no_token(claimed_web_token):
    """The negative half: now that the path is protected, an anonymous caller
    is stopped by the middleware rather than by a check inside the route."""
    client, _web_token, _child_id = claimed_web_token
    assert client.get("/api/child-web/me").status_code == 401


def test_me_rejects_a_parent_bearer_token(teen_child):
    """A parent token is not a child token. Before the prefix was added the
    route could not tell the difference, because it saw neither."""
    client, token, _child_id = teen_child
    r = client.get("/api/child-web/me",
                   headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


def test_claim_session_stays_reachable_without_a_token(teen_child):
    """Protecting the prefix must not close the door that mints the token in
    the first place — that would make the whole web surface unreachable."""
    client, token, child_id = teen_child
    r = client.post(
        "/api/value-tracking/child-web-claims",
        headers={"Authorization": f"Bearer {token}"},
        params={"child_id": child_id},
    )
    code = r.json()["claim_code"]
    assert client.post(f"/api/child-web/claim-session?claim={code}").status_code == 200


def test_refresh_survives_a_closed_session(claimed_web_token):
    """A web token outlives the screen session it was minted alongside (20h vs
    minutes). Requiring a live session to refresh would mean a teen can never
    recover from an expired token without asking for a new QR."""
    from app.services import child_budget
    from app.config.guardrails_loader import load_child_surface_policy

    client, web_token, child_id = claimed_web_token
    session = child_budget.active_session(child_id)
    assert session is not None
    child_budget.close_session(session["id"], "parent_exit",
                               load_child_surface_policy())
    assert child_budget.active_session(child_id) is None

    r = client.post("/api/child-web/refresh",
                    headers={"Authorization": f"Child-Bearer {web_token}"})
    assert r.status_code == 200, r.text
