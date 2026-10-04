"""ClientIPMiddleware — the real client behind the local proxies (audit H4).

Production (2026-10-04): tg-api.alsaba.cloud arrives Cloudflare → Tunnel →
tg_cloudflared → app; alsaba.cloud/seo and /methodology arrive Cloudflare →
analytics_nginx → app. The app publishes no port, so the TCP peer is always
one of those two containers. Cloudflare appends the connecting address to
X-Forwarded-For and sets CF-Connecting-IP itself.
"""
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.middleware.client_ip import DEFAULT_CLOUDFLARE, DEFAULT_TRUSTED, ClientIPMiddleware

TUNNEL = "172.18.0.2"     # tg_cloudflared on tutor-guardian_internal
NGINX = "172.19.0.5"      # analytics_nginx on analytics-platform_production_network
CF_EDGE = "162.158.1.2"   # a Cloudflare edge node (published range)
WORKER = "2a06:98c0:3600::103"   # any Cloudflare Worker, as Cloudflare reports it
CLIENT = "203.0.113.9"    # the parent's phone


def _scope(peer, **headers):
    return {"type": "http", "client": (peer, 1234),
            "headers": [(k.replace("_", "-").encode(), v.encode()) for k, v in headers.items()]}


mw = ClientIPMiddleware(app=None)


# ── The two production paths ──────────────────────────────────────────────


def test_through_the_tunnel_the_phone_is_resolved():
    s = _scope(TUNNEL, x_forwarded_for=CLIENT, cf_connecting_ip=CLIENT)
    assert mw.resolve(s) == CLIENT


def test_a_forged_left_entry_through_the_tunnel_is_never_believed():
    # The phone sent its own X-Forwarded-For; Cloudflare appended the real one.
    s = _scope(TUNNEL, x_forwarded_for=f"1.1.1.1, {CLIENT}", cf_connecting_ip=CLIENT)
    assert mw.resolve(s) == CLIENT


def test_a_worker_cannot_choose_its_address():
    """The hole this closes: a Cloudflare Worker's request reaches the tunnel
    from a Cloudflare address. Trusted as a proxy hop, it was skipped and the
    caller's own left-hand entry won — a fresh rate-limit bucket, or a planted
    referral click, per request."""
    s = _scope(TUNNEL, x_forwarded_for=f"198.51.100.77, {WORKER}", cf_connecting_ip=WORKER)
    assert mw.resolve(s) == WORKER


def test_nginx_with_real_ip_resolves_the_phone():
    # real_ip made nginx's peer the phone; it appends that to the chain.
    s = _scope(NGINX, x_forwarded_for=f"{CLIENT}, {CLIENT}", cf_connecting_ip=CLIENT)
    assert mw.resolve(s) == CLIENT


def test_nginx_without_real_ip_defers_to_cloudflare():
    # nginx appended the edge it saw; Cloudflare's header names the phone.
    s = _scope(NGINX, x_forwarded_for=f"{CLIENT}, {CF_EDGE}", cf_connecting_ip=CLIENT)
    assert mw.resolve(s) == CLIENT


def test_a_cloudflare_hop_without_its_header_is_not_walked_past():
    s = _scope(NGINX, x_forwarded_for=f"198.51.100.77, {CF_EDGE}")
    assert mw.resolve(s) == CF_EDGE


def test_forged_left_entry_is_never_believed():
    # Attacker hits nginx directly with forged headers: nginx appends the
    # attacker's real address, the first untrusted hop from the right, and
    # CF-Connecting-IP (not from Cloudflare) is ignored.
    s = _scope(NGINX, x_forwarded_for="1.1.1.1, 198.51.100.7", cf_connecting_ip="9.9.9.9")
    assert mw.resolve(s) == "198.51.100.7"


def test_only_cloudflares_header_from_a_proxy():
    # What the attribution tests send: no chain, the proxy's peer header only.
    assert mw.resolve(_scope(TUNNEL, cf_connecting_ip=CLIENT)) == CLIENT


def test_a_chain_of_proxies_only_falls_back_to_cf_connecting_ip():
    s = _scope(NGINX, x_forwarded_for="10.0.0.3", cf_connecting_ip=CLIENT)
    assert mw.resolve(s) == CLIENT
    assert mw.resolve(_scope(NGINX, x_forwarded_for="10.0.0.3")) == "10.0.0.3"


# ── Peers ─────────────────────────────────────────────────────────────────


def test_untrusted_peer_headers_are_ignored():
    s = _scope("198.51.100.7", x_forwarded_for="10.0.0.1", cf_connecting_ip="10.0.0.2")
    assert mw.resolve(s) is None


def test_a_cloudflare_peer_is_not_a_proxy_of_ours():
    """No Cloudflare node connects to the app (no published port): one that
    does is not on the path the headers describe."""
    s = _scope(CF_EDGE, x_forwarded_for="198.51.100.77", cf_connecting_ip="198.51.100.77")
    assert mw.resolve(s) is None


def test_scope_rewrite_and_scheme_for_a_trusted_peer():
    import asyncio

    seen = {}

    async def app(scope, receive, send):
        seen.update(client=scope["client"], scheme=scope.get("scheme"))

    scope = _scope(TUNNEL, x_forwarded_for=CLIENT, cf_connecting_ip=CLIENT,
                   x_forwarded_proto="https")
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


# ── Configuration ─────────────────────────────────────────────────────────


def test_trust_everything_is_opt_in():
    s = _scope("198.51.100.7", x_forwarded_for=f"{CLIENT}")
    assert ClientIPMiddleware(app=None, trusted="*").resolve(s) == CLIENT


def test_cloudflare_as_a_trusted_proxy_is_an_explicit_setting(monkeypatch):
    """For a backend exposed to Cloudflare directly (no tunnel, no local
    proxy): the old behaviour, by configuration only."""
    monkeypatch.setenv("TRUSTED_PROXY_IPS", f"{DEFAULT_TRUSTED},{DEFAULT_CLOUDFLARE}")
    direct = ClientIPMiddleware(app=None)
    assert direct.resolve(_scope(CF_EDGE, x_forwarded_for=CLIENT)) == CLIENT


def test_cloudflare_ranges_can_be_updated_from_the_environment(monkeypatch):
    monkeypatch.setenv("CLOUDFLARE_EDGE_IPS", "192.0.2.0/24")
    updated = ClientIPMiddleware(app=None)
    s = _scope(TUNNEL, x_forwarded_for="198.51.100.77, 192.0.2.10", cf_connecting_ip=CLIENT)
    assert updated.resolve(s) == CLIENT
