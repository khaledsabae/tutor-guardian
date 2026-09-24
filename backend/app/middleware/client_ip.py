"""
Client IP resolution behind Cloudflare → nginx (AUDIT_AND_ROADMAP.md H4).
======================================================================
Production traffic arrives Cloudflare → analytics_nginx → tg_backend, so the
TCP peer of every request is the nginx container. Everything that keys on
`request.client.host` — the rate limiter first of all — used to see that one
address for every anonymous caller: the whole user base shared one bucket.

The old fix, `ProxyHeadersMiddleware(trusted_hosts="*")`, had two problems:

  * it was registered first, so it ran *innermost* — after the rate limiter
    had already read the peer address;
  * "*" makes uvicorn take the LEFTMOST X-Forwarded-For entry, which is
    whatever the client typed. Any caller could pick their own bucket.

This middleware runs outermost (registered last in app.main) and only
believes forwarding headers when the TCP peer is a trusted proxy. The chain is
walked from the right, skipping trusted hops, so the first untrusted address
is the one the nearest trusted proxy actually saw — a forged left-hand entry
is never reached. Trusted by default: loopback, the private ranges Docker
networks use, and Cloudflare's published edge ranges. Override with
TRUSTED_PROXY_IPS (comma-separated IPs/CIDRs, or "*" to restore the old
trust-everything behaviour).

If every hop is trusted (e.g. nginx overwrote X-Forwarded-For with the
Cloudflare edge address) the Cloudflare-set CF-Connecting-IP header is used.
X-Forwarded-Proto is honoured from trusted peers only, as before, so HTTPS
redirects keep working.
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
DEFAULT_TRUSTED = ",".join(_PRIVATE + _CLOUDFLARE)


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

    def __init__(self, app, trusted: str | None = None) -> None:
        self.app = app
        self.trust = _Trust(
            trusted if trusted is not None
            else os.environ.get("TRUSTED_PROXY_IPS", DEFAULT_TRUSTED)
        )

    def resolve(self, scope) -> str | None:
        """The real client address for this scope, or None to leave it."""
        client = scope.get("client")
        peer = client[0] if client else None
        if not peer or not self.trust.contains(peer):
            return None
        xff = _header(scope, b"x-forwarded-for")
        if xff:
            hops = [_strip_port(h) for h in xff.split(",") if h.strip()]
            for hop in reversed(hops):
                if not self.trust.contains(hop):
                    return hop
        cf = _header(scope, b"cf-connecting-ip")
        if cf and cf.strip():
            return cf.strip()
        if xff:
            hops = [_strip_port(h) for h in xff.split(",") if h.strip()]
            if hops:
                return hops[0]
        return None

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
