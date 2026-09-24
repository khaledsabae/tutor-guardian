"""ClientIPMiddleware — the real client behind Cloudflare → nginx (audit H4)."""
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.middleware.client_ip import ClientIPMiddleware

NGINX = "172.18.0.5"      # docker bridge — trusted
CF_EDGE = "162.158.1.2"   # Cloudflare range — trusted
CLIENT = "203.0.113.9"    # the parent's phone


def _scope(peer, **headers):
    return {"type": "http", "client": (peer, 1234),
            "headers": [(k.replace("_", "-").encode(), v.encode()) for k, v in headers.items()]}


mw = ClientIPMiddleware(app=None)


def test_cloudflare_then_nginx_resolves_the_phone():
    s = _scope(NGINX, x_forwarded_for=f"{CLIENT}, {CF_EDGE}")
    assert mw.resolve(s) == CLIENT


def test_forged_left_entry_is_never_believed():
    # Attacker hits nginx directly with a forged header: nginx appends the
    # attacker's real address, which is the first untrusted hop from the right.
    s = _scope(NGINX, x_forwarded_for="1.1.1.1, 198.51.100.7")
    assert mw.resolve(s) == "198.51.100.7"


def test_untrusted_peer_headers_are_ignored():
    s = _scope("198.51.100.7", x_forwarded_for="10.0.0.1", cf_connecting_ip="10.0.0.2")
    assert mw.resolve(s) is None


def test_all_hops_trusted_falls_back_to_cf_connecting_ip():
    s = _scope(NGINX, x_forwarded_for=CF_EDGE, cf_connecting_ip=CLIENT)
    assert mw.resolve(s) == CLIENT


def test_scope_rewrite_and_scheme_for_a_trusted_peer():
    import asyncio

    seen = {}

    async def app(scope, receive, send):
        seen.update(client=scope["client"], scheme=scope.get("scheme"))

    scope = _scope(NGINX, x_forwarded_for=f"{CLIENT}, {CF_EDGE}", x_forwarded_proto="https")
    scope["scheme"] = "http"
    asyncio.run(ClientIPMiddleware(app)(scope, None, None))
    assert seen == {"client": (CLIENT, 0), "scheme": "https"}


def test_untrusted_peer_scope_is_left_alone():
    app = FastAPI()

    @app.get("/who")
    def who(request: Request):
        return {"ip": request.client.host}

    app.add_middleware(ClientIPMiddleware)
    # TestClient's peer ("testclient") is not a trusted proxy address.
    r = TestClient(app).get("/who", headers={"x-forwarded-for": CLIENT})
    assert r.json()["ip"] == "testclient"


def test_trust_everything_is_opt_in():
    s = _scope("198.51.100.7", x_forwarded_for=f"{CLIENT}")
    assert ClientIPMiddleware(app=None, trusted="*").resolve(s) == CLIENT
