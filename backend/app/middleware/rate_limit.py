"""
Rate limiter — per-device (or per-IP fallback) fixed-window
=============================================================
Extracts device_id from request.state (set by AuthMiddleware) for accurate
per-device rate limiting behind NAT. Falls back to client IP if no auth.

Backends:
  1. Redis (if REDIS_URL is set) — multi-instance compatible
  2. In-memory dict (default) — single-instance, no dependencies

Config via env:
    RATE_LIMIT_PER_MINUTE   (default 30)   0 disables limiting
    REDIS_URL               (optional)     for distributed rate limiting
"""
import logging
import os
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

_LIMIT = int(os.environ.get("RATE_LIMIT_PER_MINUTE", "30"))
_GENERAL_LIMIT = int(os.environ.get("RATE_LIMIT_GENERAL_PER_MINUTE", "120"))
_WINDOW = 60.0
# Every /api endpoint is rate-limited. The AI assistant (expensive to serve)
# keeps the tighter _LIMIT; all other endpoints (children, progress, referral,
# push, identity, auth) get the more generous _GENERAL_LIMIT so normal app usage
# — cold-start bursts, progress sync — never trips a false 429. Each scope has an
# independent per-device bucket. Setting RATE_LIMIT_PER_MINUTE=0 disables both.
_PROTECTED_PREFIXES = ("/api/",)
_ASSISTANT_PREFIX = "/api/assistant"
_EXEMPT_PREFIXES = ("/api/health", "/api/healthz")
_REDIS_URL = os.environ.get("REDIS_URL", "")


def _get_redis_client():
    """Lazy-init Redis client (only if REDIS_URL is set)."""
    if not _REDIS_URL:
        return None
    try:
        import redis.asyncio as aioredis
        return aioredis.from_url(_REDIS_URL, decode_responses=True)
    except ImportError:
        logger.warning("REDIS_URL set but redis-py not installed — falling back to in-memory")
        return None


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        # In-memory fallback: key -> (window_start_epoch, count)
        self._buckets: dict[str, tuple[float, int]] = {}
        self._redis = _get_redis_client()
        if self._redis:
            logger.info("Rate-limit using Redis: %s", _REDIS_URL)

    async def _check_redis(self, key: str, limit: int) -> bool | None:
        """Check rate-limit via Redis. Returns True if allowed, False if blocked, None on error."""
        if not self._redis:
            return None
        try:
            # Sliding window via sorted set
            now = time.time()
            window_start = now - _WINDOW
            pipe = self._redis.pipeline()
            pipe.zremrangebyscore(key, 0, window_start)  # remove old entries
            pipe.zcard(key)  # count current
            pipe.zadd(key, {str(now): now})
            pipe.expire(key, int(_WINDOW) + 1)
            _, count, _, _ = await pipe.execute()
            return count <= limit
        except Exception as e:
            logger.warning("Redis rate-limit error: %s", e)
            return None  # fall through to in-memory

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if (
            _LIMIT <= 0
            or not path.startswith(_PROTECTED_PREFIXES)
            or path.startswith(_EXEMPT_PREFIXES)
        ):
            return await call_next(request)

        # Two independent budgets: the AI assistant (expensive) vs the rest of the
        # API. Namespacing the key by scope keeps their buckets separate so a busy
        # chat session can't exhaust the CRUD budget or vice versa.
        if path.startswith(_ASSISTANT_PREFIX):
            scope, limit = "ai", _LIMIT
        else:
            scope, limit = "api", _GENERAL_LIMIT

        # Per-device if auth token present, otherwise per-IP
        device_id = getattr(request.state, "device_id", None)
        ident = device_id or (request.client.host if request.client else "unknown")
        key = f"rl:{scope}:{ident}"

        # Try Redis first, fall back to in-memory
        redis_allowed = await self._check_redis(key, limit)
        if redis_allowed is not None:
            if not redis_allowed:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "طلبات كثيرة، يُرجى المحاولة بعد قليل."},
                    headers={"Retry-After": str(int(_WINDOW))},
                )
            return await call_next(request)

        # In-memory fallback
        now = time.monotonic()
        start, count = self._buckets.get(key, (now, 0))

        if now - start >= _WINDOW:
            start, count = now, 0

        if count >= limit:
            retry_after = int(_WINDOW - (now - start)) + 1
            return JSONResponse(
                status_code=429,
                content={"detail": "طلبات كثيرة، يُرجى المحاولة بعد قليل."},
                headers={"Retry-After": str(retry_after)},
            )

        self._buckets[key] = (start, count + 1)
        return await call_next(request)
