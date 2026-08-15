"""The gate as the network sees it.

test_child_budget.py proves the service refuses. This file proves the refusal
survives being wired to HTTP — including the case that matters most, where a
child holds a perfectly valid token and the surface is over anyway.

The middleware tests mount the real AuthMiddleware rather than the auth stub
the other suites use. Stubbing the thing under test would have passed no
matter what the middleware did.
"""
import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware

from app.config.guardrails_loader import load_child_surface_policy
from app.db.init_db import get_conn, init_db
from app.middleware.auth import AuthMiddleware
from app.routers.child_mode import router as child_mode_router
from app.routers.child_mode_web import router as child_mode_web_router
from app.routers.children import router as children_router
from app.routers.value_tracking import router as value_router
from app.services import child_budget, child_token

DEVICE = "test-device-001"


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    db = tmp_path / "surface.db"
    monkeypatch.setenv("CONVERSATIONS_DB", str(db))
    init_db()
    return db


class _AuthStubMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Child-Bearer "):
            payload = child_token.verify_child_token(auth_header[13:].strip())
            if payload is None:
                from starlette.responses import JSONResponse
                return JSONResponse(status_code=401, content={"detail": "invalid"})
            request.state.child_mode = True
            request.state.device_id = payload["device_id"]
            request.state.child_id = payload["child_id"]
        else:
            request.state.device_id = DEVICE
        return await call_next(request)


@pytest.fixture
def client(tmp_db):
    app = FastAPI()
    app.add_middleware(_AuthStubMiddleware)
    app.include_router(children_router, prefix="/api")
    app.include_router(value_router, prefix="/api")
    app.include_router(child_mode_router, prefix="/api")
    app.include_router(child_mode_web_router, prefix="/api")
    with TestClient(app) as c:
        yield c


def _child_without_agreement(client, age_group="7-9") -> int:
    r = client.post("/api/children", json={"name": "أحمد", "age_group": age_group})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _child(client, age_group="7-9") -> int:
    """A child whose family has signed the media agreement.

    Since Sprint 2 the agreement is an entry condition, so a child without one
    can open nothing but the agreement itself. Most tests here are about what
    happens *after* that, so this helper puts them past it; the gate itself is
    tested with `_child_without_agreement`.
    """
    child_id = _child_without_agreement(client, age_group)
    if age_group in ("prenatal-1", "0-3", "unspecified", "2-3"):
        return child_id  # the age gate refuses before the agreement matters
    _sign_agreement(client, child_id)
    return child_id


def _sign_agreement(client, child_id: int) -> None:
    from app.services import family_agreement

    suggested = client.get(f"/api/children/{child_id}/agreement/clauses/suggested")
    clauses = suggested.json()["clauses"][:4]
    draft = client.post(f"/api/children/{child_id}/agreement", json={"clauses": clauses})
    assert draft.status_code == 200, draft.text
    for c in draft.json()["clauses"]:
        if c["applies_to"] in ("child", "both"):
            family_agreement.acknowledge_clause(DEVICE, child_id, c["id"])
    client.post(f"/api/children/{child_id}/agreement/sign")
    family_agreement.sign(DEVICE, child_id, "child")


def _open(client, child_id, surface="story", tz=180):
    return client.post(
        "/api/value-tracking/child-sessions",
        params={"child_id": child_id, "surface": surface, "tz_offset_minutes": tz},
    )


# ── Issuing a token is where the age gate bites ────────────────────────────

def test_an_infant_gets_a_403_with_something_to_read(client):
    """Not a 500, not an empty body. The parent is told what happened and
    what would change it."""
    cid = _child(client, "prenatal-1")
    r = _open(client, cid)
    assert r.status_code == 403
    detail = r.json()["detail"]
    assert detail["error"] == "age_not_allowed"
    assert detail["message_key"] == "child_gate.under_2"
    assert detail["message_ar"]


def test_a_toddler_may_listen_but_not_watch(client):
    cid = _child(client, "2-3")
    assert _open(client, cid, surface="screen_off").status_code == 200
    assert _open(client, cid, surface="story").status_code == 403


def test_the_token_expires_with_the_budget_not_after_it(client):
    """The plan's clamp: a 10-minute story does not hand out a 30-minute
    token, because the leftover twenty are exactly the window a bypass
    would live in."""
    cid = _child(client)
    body = _open(client, cid).json()
    assert body["allowed_seconds"] == 600
    payload = child_token.verify_child_token(body["token"])
    assert payload is not None
    ttl = payload["exp"] - payload["iat"] if "iat" in payload else None
    assert body["allowed_seconds"] <= 1800
    assert ttl is None or ttl <= 600


def test_a_legacy_client_still_works(client):
    """Builds on Play call this with child_id alone. They keep working, on
    the habit surface, and they are age-gated like everyone else."""
    cid = _child(client)
    r = client.post("/api/value-tracking/child-sessions", params={"child_id": cid})
    assert r.status_code == 200, r.text
    assert r.json()["surface"] == "habit"

    infant = _child(client, "prenatal-1")
    r = client.post("/api/value-tracking/child-sessions", params={"child_id": infant})
    assert r.status_code == 403


def test_another_devices_child_is_refused(client, tmp_db):
    conn = get_conn()
    try:
        cur = conn.execute(
            "INSERT INTO child_profiles (device_id, name, age_group) VALUES (?, ?, ?)",
            ("someone-else", "طفل", "7-9"),
        )
        conn.commit()
        foreign = cur.lastrowid
    finally:
        conn.close()
    assert _open(client, foreign).status_code in (403, 404)


# ── Heartbeat and close ────────────────────────────────────────────────────

def test_heartbeat_reports_what_is_left(client):
    cid = _child(client)
    session = _open(client, cid).json()
    r = client.post(
        "/api/value-tracking/child-mode/heartbeat",
        params={"session_id": session["session_id"]},
        headers={"Authorization": f"Child-Bearer {session['token']}"},
    )
    assert r.status_code == 200, r.text
    assert 0 < r.json()["remaining_seconds"] <= 600
    assert r.json()["exit_ritual"] is False


def test_a_child_cannot_heartbeat_another_childs_session(client):
    """A session id is not an authorisation."""
    mine = _child(client)
    theirs = _child(client)
    my_session = _open(client, mine).json()
    their_session = _open(client, theirs).json()
    r = client.post(
        "/api/value-tracking/child-mode/heartbeat",
        params={"session_id": their_session["session_id"]},
        headers={"Authorization": f"Child-Bearer {my_session['token']}"},
    )
    assert r.status_code == 404


def test_session_end_closes_it(client):
    cid = _child(client)
    session = _open(client, cid).json()
    r = client.post(
        "/api/value-tracking/child-mode/session-end",
        params={"session_id": session["session_id"], "reason": "completed"},
        headers={"Authorization": f"Child-Bearer {session['token']}"},
    )
    assert r.status_code == 200
    assert child_budget.active_session(cid) is None


# ── The parent's view ──────────────────────────────────────────────────────

def test_screen_usage_keeps_listening_and_watching_apart(client):
    cid = _child(client)
    policy = load_child_surface_policy()

    watched = _open(client, cid, surface="story").json()
    child_budget.close_session(watched["session_id"], "completed", policy)
    listened = _open(client, cid, surface="screen_off").json()
    child_budget.close_session(listened["session_id"], "completed", policy)

    r = client.get(f"/api/children/{cid}/screen-usage",
                   params={"tz_offset_minutes": 180})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["budget_seconds"] == 20 * 60
    assert body["screen_off_budget_seconds"] == 60 * 60
    assert set(body["by_surface"]) == {"story", "screen_off"}
    assert body["band"] == "7-9"


def test_screen_usage_needs_to_own_the_child(client, tmp_db):
    conn = get_conn()
    try:
        cur = conn.execute(
            "INSERT INTO child_profiles (device_id, name, age_group) VALUES (?, ?, ?)",
            ("someone-else", "طفل", "7-9"),
        )
        conn.commit()
        foreign = cur.lastrowid
    finally:
        conn.close()
    assert client.get(f"/api/children/{foreign}/screen-usage").status_code == 404


# ── The middleware, unstubbed ──────────────────────────────────────────────

@pytest.fixture
def guarded_client(tmp_db):
    """The real AuthMiddleware in front of a route that does nothing, so a
    non-200 can only have come from the gate."""
    app = FastAPI()
    app.add_middleware(AuthMiddleware)

    @app.post("/api/value-tracking/child-mode/ping")
    def ping(request: Request):
        return {"child_id": request.state.child_id}

    @app.post("/api/value-tracking/child-mode/session-end")
    def end(request: Request):
        return {"ok": True}

    with TestClient(app) as c:
        yield c


def _make_child(age_group="7-9") -> int:
    conn = get_conn()
    try:
        cur = conn.execute(
            "INSERT INTO child_profiles (device_id, name, age_group) VALUES (?, ?, ?)",
            (DEVICE, "أحمد", age_group),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def _sign_agreement_directly(child_id: int) -> None:
    """The service path, for tests that have no HTTP client for the parent."""
    from app.services import family_agreement
    band = "7-9"
    family_agreement.save_draft(DEVICE, child_id,
                                family_agreement.suggested_clauses(band)[:4])
    current = family_agreement.get_current(DEVICE, child_id)
    for c in current["clauses"]:
        if c["applies_to"] in ("child", "both"):
            family_agreement.acknowledge_clause(DEVICE, child_id, c["id"])
    family_agreement.sign(DEVICE, child_id, "parent")
    family_agreement.sign(DEVICE, child_id, "child")


def test_a_valid_token_without_a_live_session_is_refused(guarded_client):
    """The case the TTL clamp alone does not cover: the budget ran out at
    minute ten and the token is good until minute twenty."""
    cid = _make_child()
    token = child_token.issue_child_token(DEVICE, cid, ttl_seconds=1800)
    r = guarded_client.post("/api/value-tracking/child-mode/ping",
                            headers={"Authorization": f"Child-Bearer {token}"})
    assert r.status_code == 403
    assert r.json()["error"] == "child_budget_exhausted"
    assert r.json()["message_key"] == "child_gate.budget_exhausted"


def test_the_same_token_works_once_a_session_is_open(guarded_client):
    cid = _make_child()
    _sign_agreement_directly(cid)
    policy = load_child_surface_policy()
    token = child_token.issue_child_token(DEVICE, cid, ttl_seconds=1800)
    opened = child_budget.open_session(DEVICE, cid, "story", 180, policy)
    assert opened["ok"], opened

    r = guarded_client.post("/api/value-tracking/child-mode/ping",
                            headers={"Authorization": f"Child-Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["child_id"] == cid


def test_closing_the_session_shuts_the_door_again(guarded_client):
    cid = _make_child()
    _sign_agreement_directly(cid)
    policy = load_child_surface_policy()
    token = child_token.issue_child_token(DEVICE, cid, ttl_seconds=1800)
    opened = child_budget.open_session(DEVICE, cid, "story", 180, policy)
    child_budget.close_session(opened["session_id"], "completed", policy)

    r = guarded_client.post("/api/value-tracking/child-mode/ping",
                            headers={"Authorization": f"Child-Bearer {token}"})
    assert r.status_code == 403


def test_session_end_stays_reachable_after_the_budget_is_gone(guarded_client):
    """A client must always be able to report a clean close — including the
    close that spent the last second."""
    cid = _make_child()
    token = child_token.issue_child_token(DEVICE, cid, ttl_seconds=1800)
    r = guarded_client.post("/api/value-tracking/child-mode/session-end",
                            headers={"Authorization": f"Child-Bearer {token}"})
    assert r.status_code == 200


def test_no_token_is_still_a_401(guarded_client):
    assert guarded_client.post("/api/value-tracking/child-mode/ping").status_code == 401


# ── The kill switch ────────────────────────────────────────────────────────

def test_the_switch_restores_the_pre_sprint_token(client, monkeypatch):
    """Off means the app does what it did before this sprint — a flat token,
    no session — not a locked door."""
    monkeypatch.setenv("CHILD_SURFACE_ENABLED", "false")
    cid = _child(client)
    r = _open(client, cid)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["child_surface_enabled"] is False
    assert "session_id" not in body
    assert child_budget.active_session(cid) is None


def test_the_switch_lets_a_tokened_child_through_the_middleware(guarded_client, monkeypatch):
    """The two halves have to agree. A middleware still demanding a session
    while nothing opens one would lock every child out — the opposite of a
    kill switch."""
    monkeypatch.setenv("CHILD_SURFACE_ENABLED", "false")
    cid = _make_child()
    token = child_token.issue_child_token(DEVICE, cid, ttl_seconds=1800)
    r = guarded_client.post("/api/value-tracking/child-mode/ping",
                            headers={"Authorization": f"Child-Bearer {token}"})
    assert r.status_code == 200


def test_the_switch_off_still_refuses_an_infant(client, monkeypatch):
    """It disables the budget, not judgement. With no session there is no age
    gate either — this test records that, so the cost of flipping the switch
    is written down rather than discovered."""
    monkeypatch.setenv("CHILD_SURFACE_ENABLED", "false")
    infant = _child(client, "prenatal-1")
    r = _open(client, infant)
    assert r.status_code == 200
    assert r.json()["child_surface_enabled"] is False


def test_a_typo_leaves_the_surface_on(client, monkeypatch):
    """"flase", "", "1", "yes" — anything that is not an explicit false keeps
    the gate. A misspelt env var must not silently unlock it."""
    for value in ("flase", "", "1", "yes", "TRUE", "on"):
        monkeypatch.setenv("CHILD_SURFACE_ENABLED", value)
        assert child_budget.child_surface_enabled() is True, value
    for value in ("false", "FALSE", "0", "no", "off", " false "):
        monkeypatch.setenv("CHILD_SURFACE_ENABLED", value)
        assert child_budget.child_surface_enabled() is False, value


def test_the_default_is_on(monkeypatch):
    monkeypatch.delenv("CHILD_SURFACE_ENABLED", raising=False)
    assert child_budget.child_surface_enabled() is True


# ── Every door, not just the front one ─────────────────────────────────────

def test_the_qr_web_claim_opens_a_session_too(client):
    """The regression that broke the deploy.

    The QR flow for teens mints its token in child_mode_web rather than
    through /child-sessions, so adding the gate to one entry point left the
    other holding a valid twenty-hour token with no session behind it — every
    request 403'd. Relaxing the middleware for web tokens would have been the
    other way to make it green, and would have made the web surface the one
    place with no budget at all.
    """
    cid = _child(client)
    claim = client.post("/api/value-tracking/child-web-claims",
                        params={"child_id": cid})
    assert claim.status_code == 200, claim.text
    code = claim.json()["claim_code"]

    redeemed = client.post("/api/child-web/claim-session", params={"claim": code})
    assert redeemed.status_code == 200, redeemed.text
    assert redeemed.json()["session_id"] is not None
    assert child_budget.active_session(cid) is not None


def test_the_qr_web_claim_is_age_gated_like_the_front_door(client):
    """A second entry point must not be a second policy."""
    infant = _child(client, "prenatal-1")
    claim = client.post("/api/value-tracking/child-web-claims",
                        params={"child_id": infant})
    code = claim.json()["claim_code"]
    r = client.post("/api/child-web/claim-session", params={"claim": code})
    assert r.status_code == 403
    assert r.json()["detail"]["error"] == "age_not_allowed"


# ── The agreement is the frame, so it is the entry condition ───────────────

def test_without_an_agreement_only_the_agreement_opens(client):
    cid = _child_without_agreement(client)
    refused = _open(client, cid, surface="story")
    assert refused.status_code == 403
    assert refused.json()["detail"]["error"] == "agreement_required"

    allowed = _open(client, cid, surface="agreement")
    assert allowed.status_code == 200


def test_signing_it_opens_the_rest(client):
    cid = _child_without_agreement(client)
    assert _open(client, cid, surface="story").status_code == 403
    _sign_agreement(client, cid)
    assert _open(client, cid, surface="story").status_code == 200


def test_the_age_gate_still_comes_first(client):
    """An infant with a signed agreement is still an infant. Order matters:
    age is refused before the agreement is even considered."""
    infant = _child_without_agreement(client, "prenatal-1")
    r = _open(client, infant, surface="agreement")
    assert r.status_code == 403
    assert r.json()["detail"]["error"] == "age_not_allowed"


def test_reading_the_agreement_costs_the_child_nothing(client):
    cid = _child_without_agreement(client)
    opened = _open(client, cid, surface="agreement").json()
    assert opened["remaining_today"] == 20 * 60


def test_a_child_cannot_sign_clauses_they_have_not_read(client):
    cid = _child_without_agreement(client)
    suggested = client.get(f"/api/children/{cid}/agreement/clauses/suggested").json()
    client.post(f"/api/children/{cid}/agreement",
                json={"clauses": suggested["clauses"][:4]})
    session = _open(client, cid, surface="agreement").json()
    r = client.post("/api/value-tracking/child-mode/agreement/sign",
                    headers={"Authorization": f"Child-Bearer {session['token']}"})
    assert r.status_code == 409
    assert r.json()["detail"]["error"] == "clauses_not_acknowledged"


def test_the_child_reads_and_signs_from_inside_child_mode(client):
    cid = _child_without_agreement(client)
    suggested = client.get(f"/api/children/{cid}/agreement/clauses/suggested").json()
    client.post(f"/api/children/{cid}/agreement",
                json={"clauses": suggested["clauses"][:4]})
    client.post(f"/api/children/{cid}/agreement/sign")

    session = _open(client, cid, surface="agreement").json()
    headers = {"Authorization": f"Child-Bearer {session['token']}"}

    read = client.get("/api/value-tracking/child-mode/agreement", headers=headers)
    assert read.status_code == 200
    for c in read.json()["agreement"]["clauses"]:
        if c["applies_to"] in ("child", "both"):
            ack = client.post("/api/value-tracking/child-mode/agreement/acknowledge",
                              params={"clause_id": c["id"]}, headers=headers)
            assert ack.status_code == 200

    signed = client.post("/api/value-tracking/child-mode/agreement/sign",
                         headers=headers)
    assert signed.status_code == 200
    assert signed.json()["activated"] is True


def test_a_one_sided_draft_is_refused_over_http(client):
    cid = _child_without_agreement(client)
    r = client.post(f"/api/children/{cid}/agreement", json={"clauses": [
        {"applies_to": "child", "text_ar": "مافيش جهاز على السفرة"},
    ]})
    assert r.status_code == 422
    assert r.json()["detail"]["error"] == "nothing_on_the_parent"


def test_suggested_clauses_come_in_pairs_over_http(client):
    cid = _child(client)
    body = client.get(f"/api/children/{cid}/agreement/clauses/suggested").json()
    assert body["age_band"] == "7-9"
    for pair in body["pairs"]:
        assert pair["child"] and pair["parent"]


def test_another_devices_agreement_is_not_reachable(client, tmp_db):
    conn = get_conn()
    try:
        cur = conn.execute(
            "INSERT INTO child_profiles (device_id, name, age_group) VALUES (?, ?, ?)",
            ("someone-else", "طفل", "7-9"),
        )
        conn.commit()
        foreign = cur.lastrowid
    finally:
        conn.close()
    assert client.get(f"/api/children/{foreign}/agreement").status_code == 404


def test_a_toddler_is_not_asked_to_sign_anything(client):
    """A two-year-old cannot read a clause. Their band has no clause bank, so
    the gate does not apply and audio still opens."""
    cid = _child_without_agreement(client, "2-3")
    assert _open(client, cid, surface="screen_off").status_code == 200
