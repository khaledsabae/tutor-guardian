"""ClientIPMiddleware — the real client behind the local proxies (audit H4).

Production (2026-10-04): tg-api.alsaba.cloud arrives Cloudflare → Tunnel →
tg_cloudflared → app; alsaba.cloud/seo and /methodology arrive at
analytics_nginx → app, through Cloudflare or directly (over IPv6, relayed by
docker-proxy from the alsaba_edge gateway). The app publishes no port, so the
TCP peer is always one of those two containers or the healthcheck.
"""
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.middleware.client_ip import DEFAULT_CLOUDFLARE, DEFAULT_TRUSTED, ClientIPMiddleware

TUNNEL = "172.18.0.2"     # tg_cloudflared on tutor-guardian_internal
NGINX = "172.19.0.10"     # analytics_nginx on analytics-platform_production_network
GW = "172.23.0.1"         # alsaba_edge gateway: docker-proxy's source for direct IPv6
CF_EDGE = "173.245.48.1"  # a Cloudflare edge node (published range)
WORKER = "2a06:98c0:3600::103"   # any Cloudflare Worker, as Cloudflare reports it
CLIENT = "203.0.113.9"    # the parent's phone
DIRECT = "100.200.1.2"    # someone connecting to nginx without Cloudflare
CHOSEN = "198.51.100.66"  # an address a caller writes into X-Forwarded-For
CHOSEN_CF = "192.0.2.77"  # … or into CF-Connecting-IP


def _scope(peer, **headers):
    return {"type": "http", "client": (peer, 1234),
            "headers": [(k.replace("_", "-").encode(), v.encode()) for k, v in headers.items()]}


mw = ClientIPMiddleware(app=None)


# ── The production paths resolve the visitor ──────────────────────────────


def test_through_the_tunnel_the_phone_is_resolved():
    s = _scope(TUNNEL, x_forwarded_for=CLIENT, cf_connecting_ip=CLIENT)
    assert mw.resolve(s) == CLIENT


def test_a_forged_left_entry_through_the_tunnel_is_never_believed():
    # The phone sent its own X-Forwarded-For; Cloudflare appended the real one.
    s = _scope(TUNNEL, x_forwarded_for=f"{CHOSEN}, {CLIENT}", cf_connecting_ip=CLIENT)
    assert mw.resolve(s) == CLIENT


def test_a_worker_cannot_choose_its_address():
    """A Cloudflare Worker's request reaches the tunnel from a Cloudflare
    address. Skipped as a proxy hop, it used to expose the caller's own
    left-hand entry — a fresh rate-limit bucket, or a planted referral click,
    per request."""
    s = _scope(TUNNEL, x_forwarded_for=f"{CHOSEN}, {WORKER}", cf_connecting_ip=WORKER)
    assert mw.resolve(s) == WORKER


def test_nginx_through_cloudflare_resolves_the_phone():
    # Live config: real_ip turns nginx's peer into the phone, then nginx
    # appends it after what Cloudflare sent.
    s = _scope(NGINX, x_forwarded_for=f"{CHOSEN}, {CLIENT}, {CLIENT}", cf_connecting_ip=CLIENT)
    assert mw.resolve(s) == CLIENT


def test_nginx_without_real_ip_defers_to_cloudflare():
    # nginx appended the edge it saw; Cloudflare's header names the phone.
    s = _scope(NGINX, x_forwarded_for=f"{CLIENT}, {CF_EDGE}", cf_connecting_ip=CLIENT)
    assert mw.resolve(s) == CLIENT


def test_a_direct_ipv4_visit_to_nginx_is_its_own_address():
    # DNAT keeps the source; a forged chain and CF-Connecting-IP are ignored.
    s = _scope(NGINX, x_forwarded_for=f"{CHOSEN}, {DIRECT}", cf_connecting_ip=CHOSEN_CF)
    assert mw.resolve(s) == DIRECT


def test_the_healthcheck_keeps_its_own_address():
    assert mw.resolve(_scope("127.0.0.1")) is None


# ── A direct IPv6 visit arrives from docker-proxy's private gateway ───────
#
# nginx's real_ip trusts Cloudflare only, so its $remote_addr is the gateway
# and it appends that after whatever the caller wrote. Skipping the private
# hop handed the caller the answer; every shape must stop at the gateway.


def test_ipv6_direct_with_a_forged_chain_stops_at_the_gateway():
    assert mw.resolve(_scope(NGINX, x_forwarded_for=f"{CHOSEN}, {GW}")) == GW


def test_ipv6_direct_with_a_forged_cf_connecting_ip_stops_at_the_gateway():
    assert mw.resolve(_scope(NGINX, x_forwarded_for=GW, cf_connecting_ip=CHOSEN_CF)) == GW


def test_ipv6_direct_with_a_forged_cloudflare_hop_stops_at_the_gateway():
    s = _scope(NGINX, x_forwarded_for=f"{CHOSEN}, {CF_EDGE}, {GW}", cf_connecting_ip=CHOSEN_CF)
    assert mw.resolve(s) == GW


def test_a_private_last_entry_is_the_answer_not_a_header_behind_it():
    s = _scope(NGINX, x_forwarded_for="10.0.0.3", cf_connecting_ip=CLIENT)
    assert mw.resolve(s) == "10.0.0.3"


# ── Cloudflare's header, and only where Cloudflare is the last hop ────────


def test_a_cloudflare_hop_without_its_header_is_not_walked_past():
    s = _scope(NGINX, x_forwarded_for=f"{CHOSEN}, {CF_EDGE}")
    assert mw.resolve(s) == CF_EDGE


def test_only_cloudflares_header_from_a_proxy():
    # What the attribution tests send: no chain, the proxy's peer header only.
    assert mw.resolve(_scope(TUNNEL, cf_connecting_ip=CLIENT)) == CLIENT


# ── Peers ─────────────────────────────────────────────────────────────────


def test_untrusted_peer_headers_are_ignored():
    s = _scope("198.51.100.7", x_forwarded_for="10.0.0.1", cf_connecting_ip="10.0.0.2")
    assert mw.resolve(s) is None


def test_a_cloudflare_peer_is_not_a_proxy_of_ours():
    """No Cloudflare node connects to the app (no published port): one that
    does is not on the path the headers describe."""
    s = _scope(CF_EDGE, x_forwarded_for=CHOSEN, cf_connecting_ip=CHOSEN)
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


def test_cloudflare_as_a_trusted_peer_is_an_explicit_setting(monkeypatch):
    """For a backend exposed to Cloudflare directly (no tunnel, no local
    proxy): the edge becomes the peer, and still only the entry it appended
    counts."""
    monkeypatch.setenv("TRUSTED_PROXY_IPS", f"{DEFAULT_TRUSTED},{DEFAULT_CLOUDFLARE}")
    direct = ClientIPMiddleware(app=None)
    assert direct.resolve(_scope(CF_EDGE, x_forwarded_for=f"{CHOSEN}, {CLIENT}")) == CLIENT


def test_cloudflare_ranges_can_be_updated_from_the_environment(monkeypatch):
    monkeypatch.setenv("CLOUDFLARE_EDGE_IPS", "192.0.2.0/24")
    updated = ClientIPMiddleware(app=None)
    s = _scope(TUNNEL, x_forwarded_for=f"{CHOSEN}, 192.0.2.10", cf_connecting_ip=CLIENT)
    assert updated.resolve(s) == CLIENT
