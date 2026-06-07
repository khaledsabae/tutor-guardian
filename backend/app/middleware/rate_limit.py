"""
Rate limiter — per-device (or per-IP fallback) fixed-window
=============================================================
Extracts device_id from request.state (set by AuthMiddleware) for accurate
per-device rate limiting behind NAT. Falls back to client IP if no auth.

Config via env:
    RATE_LIMIT_PER_MINUTE   (default 30)   0 disables limiting

Future: swap in-memory dict for Redis (REDIS_URL) for multi-instance.
"""
import os
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

_LIMIT = int(os.environ.get("RATE_LIMIT_PER_MINUTE", "30"))
_WINDOW = 60.0
_PROTECTED_PREFIXES = ("/api/assistant",)


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        # key (device_id or ip) -> (window_start_epoch, count)
        self._buckets: dict[str, tuple[float, int]] = {}

    async def dispatch(self, request: Request, call_next):
        if _LIMIT <= 0 or not request.url.path.startswith(_PROTECTED_PREFIXES):
            return await call_next(request)

        # Per-device if auth token present, otherwise per-IP
        device_id = getattr(request.state, "device_id", None)
        key = device_id if device_id else (request.client.host if request.client else "unknown")

        now = time.monotonic()
        start, count = self._buckets.get(key, (now, 0))

        if now - start >= _WINDOW:
            start, count = now, 0

        if count >= _LIMIT:
            retry_after = int(_WINDOW - (now - start)) + 1
            return JSONResponse(
                status_code=429,
                content={"detail": "طلبات كثيرة، يُرجى المحاولة بعد قليل."},
                headers={"Retry-After": str(retry_after)},
            )

        self._buckets[key] = (start, count + 1)
        return await call_next(request)
