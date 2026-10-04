"""
Client IP resolution behind Cloudflare (AUDIT_AND_ROADMAP.md H4).
=================================================================
What reaches this container (verified read-only on the VPS, 2026-10-04):

  * tg_backend publishes no port; it is reachable only on its two Docker
    networks (tutor-guardian_internal, analytics-platform_production_network).
  * tg-api.alsaba.cloud, the app's API: Cloudflare edge → Cloudflare Tunnel →
    the tg_cloudflared container → tg_backend:8000. Sampled for 90 s, every
    connection to :8000 came from tg_cloudflared or from 127.0.0.1 (the
    container's own healthcheck). cloudflared (2026.5.2) forwards the edge's
    headers untouched — a plain RoundTrip, no X-Forwarded-For handling — and
    the edge appends the address that connected to it (Cloudflare docs, "HTTP
    request headers"). So the last entry is the client.
  * alsaba.cloud/seo and /methodology: analytics_nginx → tg_backend:8000.
    nginx appends its own peer ($remote_addr) to X-Forwarded-For and passes
    CF-Connecting-IP through. Through Cloudflare, real_ip (live config) makes
    that peer the visitor. But nginx also takes direct connections: over IPv4
    its peer is the caller's address; over IPv6 docker-proxy relays them from
    the alsaba_edge gateway, 172.23.0.1 — a private address with whatever the
    caller wrote to its left, CF-Connecting-IP included.

The rule:
  1. Forwarding headers are believed only from a trusted peer
     (TRUSTED_PROXY_IPS; default loopback and the private ranges the Docker
     networks use). Only the peer is trusted, never an entry in its chain.
  2. The answer is the LAST X-Forwarded-For entry: what our proxy itself saw
     (the tunnel: the address Cloudflare appended; nginx: its $remote_addr).
     Never skip an entry to the left of it — not even a private one: the
     docker-proxy gateway is private.
  3. If that entry is Cloudflare's (CLOUDFLARE_EDGE_IPS; default the published
     ranges), Cloudflare saw the client, and its CF-Connecting-IP — set by the
     edge on every request, whatever the client sent — is the answer; without
     it, the entry itself.
  4. No chain at all: CF-Connecting-IP (or the peer, without it).

History. Until 2026-10 private and Cloudflare entries were skipped from the
right. That let a caller choose its address twice over: a Cloudflare Worker
reaches the tunnel as "X-Forwarded-For: <anything>, 2a06:98c0:3600::103"
(the Worker's address, in a Cloudflare range), and a direct IPv6 visit to
nginx as "<anything>, 172.23.0.1" — the skipped hop exposed <anything>, or the
caller's own CF-Connecting-IP. Optional hardening outside this repository:
accept 80/443 on the VPS from Cloudflare's ranges only (the analytics-platform
owner's call); the rule above does not depend on it.

The client IP is used by the rate limiter (IP buckets for session minting,
feedback and support verification; the AI scope and the general API when no
token identifies the caller) and by install attribution (landing-page clicks
stored per IP or IPv6 /64, matched by the AUTO referral claim within 24 h, and
the cap on new clicks per minute).

TRUSTED_PROXY_IPS: comma-separated IPs/CIDRs, or "*" to trust every peer
(then the first entry is taken, the old trust-everything behaviour). If the
backend is ever exposed to Cloudflare directly (a published port behind
proxied DNS, no tunnel or local proxy), add Cloudflare's ranges to it.
X-Forwarded-Proto is honoured from trusted peers only, so HTTPS redirects keep
working.
"""
from __future__ import annotations

import ipaddress
import os
from functools import lru_cache

# https://www.cloudflare.com/ips/ — stable for years; override via env if needed.
_CLOUDFLARE = (
    "173.245.48.0/20", "103.21.244.0/22", "103.22.200.0/22", "103.31.4.0/22",
    "141.101.64.0/18", "108.162.192.0/18", "190.93.240.0/20", "188.114.96.0/20",
    "197.234.240.0/22", "198.41.128.0/17", "162.158.0.0/15", "104.16.0.0/13",
    "104.24.0.0/14", "172.64.0.0/13", "131.0.72.0/22",
    "2400:cb00::/32", "2606:4700::/32", "2803:f800::/32", "2405:b500::/32",
    "2405:8100::/32", "2a06:98c0::/29", "2c0f:f248::/32",
)
_PRIVATE = (
    "127.0.0.0/8", "::1/128", "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16",
    "fc00::/7",
)
# Peers whose forwarding headers are read: loopback (the healthcheck) and the
# Docker networks tg_cloudflared and analytics_nginx connect from. A peer is
# trusted to report what IT saw — the last entry — not to vouch for the rest.
DEFAULT_TRUSTED = ",".join(_PRIVATE)
DEFAULT_CLOUDFLARE = ",".join(_CLOUDFLARE)


class _Trust:
    def __init__(self, spec: str) -> None:
        self.always = spec.strip() == "*"
        self.networks = []
        for raw in spec.split(","):
            raw = raw.strip()
            if not raw or raw == "*":
                continue
            try:
                self.networks.append(ipaddress.ip_network(raw, strict=False))
            except ValueError:
                continue
        self.contains = lru_cache(maxsize=4096)(self._contains)

    def _contains(self, host: str) -> bool:
        if self.always:
            return True
        try:
            ip = ipaddress.ip_address(host)
        except ValueError:
            return False
        return any(ip in net for net in self.networks)


def _header(scope, name: bytes) -> str | None:
    for key, value in scope.get("headers") or ():
        if key == name:
            return value.decode("latin-1")
    return None


def _strip_port(host: str) -> str:
    host = host.strip()
    if host.startswith("["):  # [v6]:port
        return host[1:].split("]", 1)[0]
    if host.count(":") == 1:  # v4:port
        return host.split(":", 1)[0]
    return host


class ClientIPMiddleware:
    """Pure ASGI: rewrites scope["client"] / scope["scheme"] for trusted peers."""

    def __init__(self, app, trusted: str | None = None, cloudflare: str | None = None) -> None:
        self.app = app
        self.trust = _Trust(
            trusted if trusted is not None
            else os.environ.get("TRUSTED_PROXY_IPS", DEFAULT_TRUSTED)
        )
        self.edge = _Trust(
            cloudflare if cloudflare is not None
            else os.environ.get("CLOUDFLARE_EDGE_IPS", DEFAULT_CLOUDFLARE)
        )

    def resolve(self, scope) -> str | None:
        """The real client address for this scope, or None to leave it."""
        client = scope.get("client")
        peer = client[0] if client else None
        if not peer or not self.trust.contains(peer):
            return None
        cf = (_header(scope, b"cf-connecting-ip") or "").strip() or None
        xff = _header(scope, b"x-forwarded-for")
        hops = [_strip_port(h) for h in xff.split(",") if h.strip()] if xff else []
        if self.trust.always:             # "*": the old trust-everything behaviour
            return cf or (hops[0] if hops else None)
        if not hops:
            return cf                     # no chain: Cloudflare's own header, if any
        last = hops[-1]                   # what our proxy saw — never skipped, even if private
        if self.edge.contains(last):
            return cf or last             # Cloudflare saw the client: its header says who
        return last

    async def __call__(self, scope, receive, send):
        if scope["type"] in ("http", "websocket"):
            client = scope.get("client")
            peer = client[0] if client else None
            if peer and self.trust.contains(peer):
                proto = _header(scope, b"x-forwarded-proto")
                if proto:
                    proto = proto.split(",")[-1].strip().lower()
                    if scope["type"] == "websocket":
                        proto = proto.replace("http", "ws")
                    if proto in ("http", "https", "ws", "wss"):
                        scope["scheme"] = proto
                real = self.resolve(scope)
                if real:
                    scope["client"] = (real, 0)
        await self.app(scope, receive, send)
