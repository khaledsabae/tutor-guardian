"""Explicit inventory and effective guards, without invoking protected handlers.

This is a drift gate, not a claim that every public endpoint needs auth or
that authentication alone proves resource ownership.
"""

import asyncio
import importlib
from collections import Counter
from types import SimpleNamespace

import pytest
from fastapi import APIRouter, Depends, FastAPI
from fastapi import routing as fastapi_routing
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from app.main import app
from app.middleware import auth


def _policies():
    # Make deletion/absence report the actual unclassified routes, not just
    # an import error. Other import failures must remain visible.
    try:
        return importlib.import_module("app.security.route_policy").ROUTE_POLICIES
    except ModuleNotFoundError as exc:
        if exc.name not in {"app.security", "app.security.route_policy"}:
            raise
        return {}


def _route_views(application):
    # Newer FastAPI includes routers lazily. Its public contexts retain the
    # effective prefix, schema flags and include-time dependency graph.
    contexts = getattr(fastapi_routing, "iter_route_contexts", None)
    return contexts(application.routes) if contexts else iter(application.routes)


def _entries(application):
    for route in _route_views(application):
        original = getattr(route, "original_route", route)
        if isinstance(original, APIRoute):
            kind = "api"
        elif isinstance(original, Mount):
            kind = "mount"
        elif type(original) is Route:
            kind = "framework"
        else:
            raise AssertionError(f"Unknown route type: {type(original).__name__}")
        for method in sorted(route.methods) if kind != "mount" else ["MOUNT"]:
            yield (kind, method, route.path), route


def _dependencies(dependant):
    return tuple(
        (
            f"{child.call.__module__}.{child.call.__qualname__}",
            tuple(
                getattr(child, "oauth_scopes", None) or getattr(child, "security_scopes", ()) or ()
            ),
            _dependencies(child),
        )
        for child in dependant.dependencies
    )


def _assert_inventory(application, policies):
    entries = list(_entries(application))
    counts = Counter(key for key, _ in entries)
    assert all(n == 1 for n in counts.values()), "Duplicate route registration"
    missing = set(counts) - policies.keys()
    assert not missing, f"Unclassified actual routes: {sorted(missing)}"
    stale = {key for key, policy in policies.items() if not policy.optional} - counts.keys()
    assert not stale, f"Stale required route policies: {sorted(stale)}"
    for key, route in entries:
        policy = policies[key]
        assert policy.auth in {"public", "soft", "device", "child", "ops"}
        assert policy.scope in {"public", "device", "session", "child", "ops"}
        if key[0] == "mount":
            assert isinstance(route.app, StaticFiles), f"Unreviewed mounted app: {key}"
            assert route.name == policy.endpoint, f"Mount changed: {key}"
        else:
            endpoint = f"{route.endpoint.__module__}.{route.endpoint.__qualname__}"
            assert endpoint == policy.endpoint, f"Endpoint changed: {key}"
            assert route.include_in_schema == policy.in_schema, f"Schema exposure changed: {key}"
        if key[0] == "api":
            assert _dependencies(route.dependant) == policy.dependencies, (
                f"Effective dependency graph changed: {key}"
            )


def test_all_actual_routes_have_explicit_policies():
    _assert_inventory(app, _policies())


def _include_guard():
    pass


def _endpoint_guard():
    pass


async def _nested_endpoint():
    return {}


def _nested_inventory(with_include_guard=True):
    from app.security.route_policy import RoutePolicy

    inner = APIRouter()
    inner.add_api_route("/leaf", _nested_endpoint, dependencies=[Depends(_endpoint_guard)])
    outer = APIRouter()
    outer.include_router(inner, prefix="/nested")
    candidate = FastAPI(openapi_url=None, docs_url=None, redoc_url=None)
    candidate.include_router(
        outer, prefix="/outer",
        dependencies=[Depends(_include_guard)] if with_include_guard else [],
    )
    policy = RoutePolicy(
        auth="public", scope="public", endpoint=f"{__name__}._nested_endpoint",
        dependencies=((f"{__name__}._include_guard", (), ()),
                      (f"{__name__}._endpoint_guard", (), ())),
    )
    return candidate, {("api", "GET", "/outer/nested/leaf"): policy}


@pytest.mark.parametrize("with_include_guard", [True, False])
def test_nested_inventory_uses_effective_prefix_and_include_dependencies(with_include_guard):
    candidate, policies = _nested_inventory(with_include_guard)
    if with_include_guard:
        _assert_inventory(candidate, policies)
    else:
        with pytest.raises(AssertionError, match="Effective dependency graph changed"):
            _assert_inventory(candidate, policies)


def test_unclassified_nested_route_is_still_rejected():
    candidate, _ = _nested_inventory()
    with pytest.raises(AssertionError, match="Unclassified actual routes"):
        _assert_inventory(candidate, {})


def test_unknown_route_objects_remain_rejected():
    with pytest.raises(AssertionError, match="Unknown route type: object"):
        _assert_inventory(SimpleNamespace(routes=[object()]), {})


@pytest.mark.parametrize("kind", ["api", "framework", "mount"])
def test_new_route_is_rejected_even_under_a_previously_public_prefix(kind, tmp_path):
    candidate = FastAPI()
    candidate.router.routes = list(app.routes)

    async def new_endpoint():
        return {}

    if kind == "api":
        candidate.add_api_route("/api/program/new-catalogue", new_endpoint)
    elif kind == "framework":
        candidate.router.routes.append(Route("/new-schema.json", new_endpoint))
    else:
        candidate.mount("/new-static", StaticFiles(directory=tmp_path))
    with pytest.raises(AssertionError, match="Unclassified actual routes"):
        _assert_inventory(candidate, _policies())


def test_removing_a_registered_proof_dependency_is_rejected():
    candidate = FastAPI()
    candidate.router.routes = list(_route_views(app))
    original = next(r for r in candidate.router.routes if r.path == "/api/privacy/memory")
    replacement = APIRoute(original.path, original.endpoint, methods=original.methods)
    candidate.router.routes[candidate.router.routes.index(original)] = replacement
    with pytest.raises(AssertionError, match="Effective dependency graph changed"):
        _assert_inventory(candidate, _policies())


def _dispatch(route, method, headers=()):
    request = Request(
        {
            "type": "http",
            "method": method,
            "path": route.path,
            "headers": list(headers),
            "query_string": b"",
            "scheme": "http",
            "server": ("testserver", 80),
            "client": ("127.0.0.1", 1234),
        }
    )

    async def downstream(request):
        return JSONResponse(
            {
                "device": getattr(request.state, "device_id", None),
                "session": getattr(request.state, "session_id", None),
                "child": getattr(request.state, "child_id", None),
            }
        )

    return asyncio.run(auth.AuthMiddleware(app).dispatch(request, downstream))


@pytest.mark.parametrize("story_enforced", [False, True])
def test_effective_middleware_policy_for_every_http_route(monkeypatch, story_enforced):
    policies = _policies()
    _assert_inventory(app, policies)
    assert any(m.cls is auth.AuthMiddleware for m in app.user_middleware)
    monkeypatch.setenv("STORY_AUTH_ENFORCE", str(story_enforced).lower())
    monkeypatch.setattr(
        auth.store,
        "validate_token",
        lambda token: (
            {
                "device_id": "policy-device",
                "session_id": "policy-session",
            }
            if token == "policy-parent"
            else None
        ),
    )
    monkeypatch.setattr(
        auth.child_token_service,
        "verify_child_token",
        lambda token, **kw: (
            {
                "device_id": "policy-device",
                "child_id": 7,
            }
            if token == "policy-child"
            else None
        ),
    )
    monkeypatch.setattr(auth.child_budget, "child_surface_enabled", lambda: False)

    for key, route in _entries(app):
        if key[0] == "mount":
            continue
        policy, method = policies[key], key[1]
        protected = policy.auth in {"device", "child"} or (policy.auth == "soft" and story_enforced)
        assert _dispatch(route, method).status_code == (401 if protected else 200), key
        if policy.auth in {"device", "soft"}:
            result = _dispatch(route, method, [(b"authorization", b"Bearer policy-parent")])
            assert result.status_code == 200, key
            assert b'"device":"policy-device"' in result.body, key
            assert _dispatch(
                route, method, [(b"authorization", b"Child-Bearer policy-child")]
            ).status_code == (401 if protected else 200), key
        elif policy.auth == "child":
            result = _dispatch(route, method, [(b"authorization", b"Child-Bearer policy-child")])
            assert result.status_code == 200 and b'"child":7' in result.body, key
            assert (
                _dispatch(route, method, [(b"authorization", b"Bearer policy-parent")]).status_code
                == 401
            ), key


def test_child_session_exceptions_are_verified_in_dispatch(monkeypatch):
    policies = _policies()
    _assert_inventory(app, policies)
    monkeypatch.setattr(
        auth.child_token_service,
        "verify_child_token",
        lambda token, **kw: {
            "device_id": "policy-device",
            "child_id": 7,
        },
    )
    monkeypatch.setattr(auth.child_budget, "child_surface_enabled", lambda: True)
    monkeypatch.setattr(auth.child_budget, "active_session", lambda child: None)
    for key, route in _entries(app):
        if policies[key].auth != "child":
            continue
        result = _dispatch(route, key[1], [(b"authorization", b"Child-Bearer policy-child")])
        assert result.status_code == (403 if policies[key].live_child_session else 200), key


@pytest.mark.parametrize(
    "path,method,payload",
    [
        ("/api/stats/ops-llm", "GET", None),
        ("/api/admin/send-push", "POST", {}),
        ("/api/feedback/app", "GET", None),
        ("/api/feedback/digest", "GET", None),
        ("/api/feedback/app/policy-test/audio", "GET", None),
        ("/api/feedback/app/policy-test/reply", "POST", {"text": "test"}),
        ("/api/feedback/telegram/webhook", "POST", {}),
    ],
)
@pytest.mark.parametrize("configured", [False, True])
def test_handler_ops_guards_reject_without_credentials_before_effects(
    monkeypatch,
    path,
    method,
    payload,
    configured,
):
    from app import main
    from app.routers import feedback, stats

    def forbidden_effect(*args, **kwargs):
        pytest.fail("Unauthorized handler reached a database or sender")

    value = "policy-test-secret" if configured else ""
    monkeypatch.setenv("OPS_METRICS_TOKEN", value)
    monkeypatch.setenv("TG_ADMIN_KEY", value)
    monkeypatch.setattr(feedback, "_ADMIN_KEY", value)
    monkeypatch.setattr(feedback, "_TG_WEBHOOK_SECRET", value)
    monkeypatch.setattr(feedback, "get_conn", forbidden_effect)
    monkeypatch.setattr(feedback, "_deliver_reply", forbidden_effect)
    monkeypatch.setattr(stats, "get_conn", forbidden_effect)
    monkeypatch.setattr(stats.sqlite3, "connect", forbidden_effect)
    monkeypatch.setattr(main, "send_to_device", forbidden_effect)
    # No lifespan: no model warm-up, scheduler, FCM, or server startup.
    response = TestClient(app).request(method, path, json=payload)
    assert response.status_code == 403, response.text


@pytest.mark.parametrize("key", [key for key, policy in _policies().items() if policy.dependencies])
def test_registered_proof_dependency_actually_blocks_before_handler(monkeypatch, key):
    from app.core import proof
    from app.routers import child_memory, children, privacy

    monkeypatch.setattr(
        auth.store,
        "validate_token",
        lambda token: {
            "device_id": "policy-device",
            "session_id": "policy-session",
        },
    )
    monkeypatch.setattr(
        proof,
        "request_access",
        lambda *args, **kwargs: SimpleNamespace(
            ok=False,
            reason="unproven",
        ),
    )
    monkeypatch.setattr(proof.device_proof, "required_for_every_device", lambda: True)
    monkeypatch.setattr(proof.device_proof, "paused_until", lambda device: None)
    monkeypatch.setattr(children, "get_conn", lambda: pytest.fail("child handler reached"))
    monkeypatch.setattr(child_memory, "get_conn", lambda: pytest.fail("memory handler reached"))
    monkeypatch.setattr(privacy, "erase_device_memory", lambda *args: pytest.fail("erase reached"))
    path = key[2].replace("{child_id}", "7").replace("{followup_id}", "7").replace("{fact_id}", "7")
    response = TestClient(app).request(
        key[1], path, json={}, headers={"Authorization": "Bearer test"}
    )
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "device_proof_required"


@pytest.mark.parametrize("enforced", [False, True])
def test_public_session_mint_has_its_documented_conditional_identity_guard(monkeypatch, enforced):
    monkeypatch.setenv("SESSION_MINT_ENFORCE", str(enforced).lower())
    client = TestClient(app)
    first = client.post("/api/chat/sessions", json={"device_id": "policy-known"})
    assert first.status_code == 201
    bare = client.post("/api/chat/sessions", json={"device_id": "policy-known"})
    assert bare.status_code == (401 if enforced else 201)
    proven = client.post(
        "/api/chat/sessions",
        json={"device_id": "policy-other"},
        headers={"Authorization": f"Bearer {first.json()['token']}"},
    )
    assert proven.status_code == 201
    assert proven.json()["device_id"] == "policy-known"


def test_public_qr_claim_transport_still_requires_a_claim_capability(monkeypatch):
    from app.routers import child_mode_web

    def forbidden_effect():
        pytest.fail("Invalid claim reached profile data")

    monkeypatch.setattr(child_mode_web, "get_conn", forbidden_effect)
    client = TestClient(app)
    assert client.post("/api/child-web/claim-session").status_code == 422
    assert client.post("/api/child-web/claim-session?claim=invalid-policy-claim").status_code == 410


def test_ops_cases_cover_every_handler_authenticated_policy():
    endpoints = {p.endpoint for p in _policies().values() if p.auth == "ops"}
    assert endpoints == {
        "app.main.admin_send_push",
        "app.routers.stats.ops_llm_metrics",
        "app.routers.feedback.list_app_feedback",
        "app.routers.feedback.feedback_digest",
        "app.routers.feedback.get_app_feedback_audio",
        "app.routers.feedback.admin_reply",
        "app.routers.feedback.telegram_webhook",
    }, "Add an effective handler-denial case when reviewing a new ops policy"
