"""Every route, walked (PR #26 final review, item 9).

Replaces the hand-written list of protected routes: the routes are read from
the app itself, so a route added later is either guarded, explained here, or a
failing test.

* Every guarded route is listed with its guard (`GUARDED`) — exactly.
* Every route whose handler touches child memory or deletes data is guarded,
  or appears in `OPEN` with the reason it may stay open.
* Every route guarded by `require_device_proof` refuses an unproven session,
  and serves a proven one.
"""
from __future__ import annotations

import inspect
import re

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from tests.device_proof_support import prove

GUARD_NAMES = {"require_device_proof", "require_device_proof_irreversible",
               "require_device_proof_once_enrolled"}

GUARDED = {
    ("DELETE", "/api/privacy/memory"): "require_device_proof",
    ("DELETE", "/api/privacy/account"): "require_device_proof_irreversible",
    ("DELETE", "/api/children/{child_id}"): "require_device_proof_once_enrolled",
    ("DELETE", "/api/children/{child_id}/progress"): "require_device_proof_once_enrolled",
    ("GET", "/api/children/followups/due"): "require_device_proof",
    ("GET", "/api/children/followups/{followup_id}"): "require_device_proof",
    ("POST", "/api/children/followups/{followup_id}/answer"): "require_device_proof",
    ("POST", "/api/children/followups/{followup_id}/dismiss"): "require_device_proof",
    ("GET", "/api/children/{child_id}/followups"): "require_device_proof",
    ("GET", "/api/children/{child_id}/memory"): "require_device_proof",
    ("POST", "/api/children/{child_id}/memory"): "require_device_proof",
    ("PATCH", "/api/children/{child_id}/memory/{fact_id}"): "require_device_proof",
    ("DELETE", "/api/children/{child_id}/memory/{fact_id}"): "require_device_proof",
    ("DELETE", "/api/children/{child_id}/memory"): "require_device_proof",
}

# Touch memory or delete, and stay open on purpose.
OPEN = {
    ("POST", "/api/assistant/draft"): "facts reach the prompt, and learning runs, only "
                                      "when request_proven (F4)",
    ("POST", "/api/assistant/stream"): "same as /draft",
    ("GET", "/api/program/coach-tip"): "facts shape the tip only when request_proven (F4)",
    ("PUT", "/api/children/memory/settings"): "off is always allowed; on calls "
                                              "require_device_proof inside the handler",
    ("GET", "/api/children/{child_id}/weekly-plan"): "memory shapes it, and the offset is "
                                                     "recorded, only for a confirmed session",
    ("POST", "/api/identity/link-google"): "records whether the link is confirmed; a bare "
                                           "session cannot move a confirmed link",
    ("DELETE", "/api/daily-routine/events/{event_id}"): "pre-PR: one routine event the "
                                                        "parent logged — unchanged",
    ("DELETE", "/api/value-tracking/events/{event_id}"): "pre-PR: one habit event — unchanged",
}

# What a handler's own source shows when it reads, writes or deletes memory or data.
_TOUCHES = re.compile(
    r"\bcm\.|child_memory\.|weekly_plan\.|erase_\w+\(|DELETE FROM|\.delete_\w+\(|"
    r"child_facts|followups|weekly_plans|request_proven|request_access|confirmed_session")


def _routes():
    from app.main import app
    for route in app.routes:
        if isinstance(route, APIRoute):
            for method in route.methods:
                yield method, route.path, route


def _guard(route) -> str | None:
    names = {getattr(d.call, "__name__", "") for d in route.dependant.dependencies}
    found = names & GUARD_NAMES
    assert len(found) <= 1, (route.path, found)
    return next(iter(found), None)


def test_the_guarded_routes_are_exactly_these():
    actual = {(m, p): _guard(r) for m, p, r in _routes() if _guard(r)}
    assert actual == GUARDED


def test_every_route_that_touches_memory_or_deletes_is_guarded_or_explained():
    unexplained = []
    for method, path, route in _routes():
        try:
            source = inspect.getsource(route.endpoint)
        except (OSError, TypeError):
            continue
        if _TOUCHES.search(source) and (method, path) not in GUARDED \
                and (method, path) not in OPEN:
            unexplained.append(f"{method} {path}")
    assert unexplained == [], "guard these routes, or say in OPEN why they stay open"
    stale = [k for k in OPEN if k not in {(m, p) for m, p, _ in _routes()}]
    assert stale == []


# ── Behaviour: every require_device_proof route, from the app ─────────────

_BODIES = {
    ("POST", "/api/children/followups/{followup_id}/answer"): {"outcome": "worked"},
    ("POST", "/api/children/{child_id}/memory"): {"category": "temperament", "fact": "طفلي هادئ"},
    ("PATCH", "/api/children/{child_id}/memory/{fact_id}"): {"status": "rejected"},
}
_PROOF_ROUTES = sorted(k for k, v in GUARDED.items() if v == "require_device_proof")


@pytest.fixture
def client():
    from app.main import app
    with TestClient(app) as c:
        yield c


@pytest.mark.parametrize("method,path", _PROOF_ROUTES)
def test_each_proof_route_refuses_an_unproven_session_and_serves_a_proven_one(client, method, path):
    device = f"dev-walk-{abs(hash((method, path))) % 100000}"
    r = client.post("/api/chat/sessions", json={"device_id": device})
    h = {"Authorization": f"Bearer {r.json()['token']}"}
    cid = client.post("/api/children", json={"name": "سالم", "age_group": "7-9"},
                      headers=h).json()["id"]
    url = path.format(child_id=cid, fact_id=1, followup_id=1)
    kwargs = {"headers": h}
    if (method, path) in _BODIES:
        kwargs["json"] = _BODIES[(method, path)]
    r = getattr(client, method.lower())(url, **kwargs)
    assert r.status_code == 403 and r.json()["detail"]["code"] == "device_proof_required", url
    detail = r.json()["detail"]
    assert detail["message"] and detail["message_en"] and detail["support_email"]
    prove(client, h, push_token=f"fcm-{device}")
    r = getattr(client, method.lower())(url, **kwargs)
    assert r.status_code != 403, (url, r.text)
