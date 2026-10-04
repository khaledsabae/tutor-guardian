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
    ("PATCH", "/api/children/{child_id}"): "a rename re-letters the siblings' memory and "
                                          "turns the old name into the child's placeholder "
                                          "(PR #39 review) — nothing is read out or deleted",
}

# What a handler's own source shows when it reads, writes or deletes memory or data.
_TOUCHES = re.compile(
    r"\bcm\.|child_memory\.|weekly_plan\.|erase_\w+\(|DELETE FROM|\.delete_\w+\(|"
    r"child_facts|followups|weekly_plans|request_proven|request_access|confirmed_session")


def _effective(routes):
    """Every effective route, however this FastAPI exposes included routers.

    Up to 0.140 include_router copied each APIRoute into app.routes; from 0.141
    (CI and production run 0.141.1) it appends one nested _IncludedRouter per
    router, which expands through effective_candidates() into contexts that
    carry the original route, the prefixed path and the combined dependencies.
    Duck-typed, like test_landing_attribution's walk (f0f4682a), so it reads
    both shapes.
    """
    for route in routes:
        nested = getattr(route, "effective_candidates", None)
        if callable(nested):
            yield from _effective(nested())
        else:
            yield route


def _routes(routes=None):
    if routes is None:
        from app.main import app
        routes = app.routes
    for route in _effective(routes):
        original = getattr(route, "original_route", route)
        if not isinstance(original, APIRoute) and not getattr(route, "_api_route", False):
            continue
        for method in getattr(route, "methods", None) or ():
            yield method, route.path, route


def _guard(route) -> str | None:
    names = {getattr(getattr(d, "dependency", None), "__name__", "")
             for d in getattr(route, "dependencies", None) or ()}
    dependant = getattr(route, "dependant", None)
    if dependant is not None:
        names |= {getattr(d.call, "__name__", "") for d in dependant.dependencies}
    found = names & GUARD_NAMES
    assert len(found) <= 1, (route.path, found)
    return next(iter(found), None)


def test_the_walk_finds_the_routes():
    """Fail here, by name, if a future FastAPI hides routes from the walk,
    rather than as a vacuous pass below."""
    found = {(m, p) for m, p, _ in _routes()}
    assert len(found) > 50
    missing = (set(GUARDED) | set(OPEN)) - found
    assert not missing, f"the route walk did not find {sorted(missing)}"


def test_the_walk_reads_fastapi_0_141_nested_routers():
    """The shape FastAPI 0.141 gives app.routes, built by hand."""
    from fastapi import Depends

    from app.core.proof import require_device_proof

    def endpoint():
        return None

    class Context:                       # _EffectiveRouteContext
        def __init__(self, path, methods, dependencies):
            self.original_route = APIRoute(path, endpoint, methods=list(methods))
            self.path, self.methods, self.endpoint = path, set(methods), endpoint
            self.dependencies = dependencies
            self.dependant = None

    class IncludedRouter:                # _IncludedRouter
        def __init__(self, *children):
            self.children = children

        def effective_candidates(self):
            return list(self.children)

    tree = [IncludedRouter(
        Context("/api/x/memory", {"GET"}, [Depends(require_device_proof)]),
        IncludedRouter(Context("/api/y", {"DELETE"}, [])),
    )]
    walked = {(m, p): _guard(r) for m, p, r in _routes(tree)}
    assert walked == {("GET", "/api/x/memory"): "require_device_proof",
                      ("DELETE", "/api/y"): None}


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
