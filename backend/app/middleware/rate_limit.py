"""
Lightweight per-IP rate limiter — لا تبعيات خارجية
===================================================
Fixed-window in-memory limiter on the AI endpoints (the expensive ones).
Single-instance only — for a multi-instance mobile backend, swap the store
for Redis. Kept dependency-free on purpose for the current core.

Config via env:
    RATE_LIMIT_PER_MINUTE   (default 30)   0 disables limiting
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
        # ip -> (window_start_epoch, count)
        self._buckets: dict[str, tuple[float, int]] = {}

    async def dispatch(self, request: Request, call_next):
        if _LIMIT <= 0 or not request.url.path.startswith(_PROTECTED_PREFIXES):
            return await call_next(request)

        ip = request.client.host if request.client else "unknown"
        now = time.monotonic()
        start, count = self._buckets.get(ip, (now, 0))

        if now - start >= _WINDOW:
            start, count = now, 0  # new window

        if count >= _LIMIT:
            retry_after = int(_WINDOW - (now - start)) + 1
            return JSONResponse(
                status_code=429,
                content={"detail": "طلبات كثيرة، يُرجى المحاولة بعد قليل."},
                headers={"Retry-After": str(retry_after)},
            )

        self._buckets[ip] = (start, count + 1)
        return await call_next(request)
