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
    AI_DAILY_LIMIT          (default 20)   0 disables the per-day AI quota
    REDIS_URL               (optional)     for distributed rate limiting
"""
import datetime as _dt
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
# Fair-use daily quota for LLM generation (growth plan §5.1): generous enough
# that a real parent never feels it, tight enough that scripts/abuse can't run
# the model bill up. Counts only mutating (POST) AI calls per device per UTC
# day. The refusal is deliberately gentle — never «pay», always «tomorrow».
_AI_DAILY_LIMIT = int(os.environ.get("AI_DAILY_LIMIT", "20"))
_DAILY_MESSAGE = "وصلنا لحدّ اليوم من الأسئلة — نستكمل غدًا بإذن الله 🌙"
# Every /api endpoint is rate-limited. The AI assistant (expensive to serve)
# keeps the tighter _LIMIT; all other endpoints (children, progress, referral,
# push, identity, auth) get the more generous _GENERAL_LIMIT so normal app usage
# — cold-start bursts, progress sync — never trips a false 429. Each scope has an
# independent per-device bucket. Setting RATE_LIMIT_PER_MINUTE=0 disables both.
_PROTECTED_PREFIXES = ("/api/",)
# Full-LLM-generation endpoints share the tight "ai" budget: the assistant
# AND story generation (unauthenticated, so otherwise a free 120/min DoS
# vector against the model server).
_AI_PREFIXES = ("/api/assistant", "/api/program/story")
# App feedback is unauthenticated (a user whose session is broken must still be
# able to report it) and accepts an 8MB voice note, so the general 120/min would
# allow ~1GB/min of DB writes per IP — and, once Telegram alerts are on, 120
# notifications a minute. A human writes feedback a handful of times at most.
_FEEDBACK_PREFIXES = ("/api/feedback/app",)
_FEEDBACK_LIMIT = int(os.environ.get("RATE_LIMIT_FEEDBACK_PER_MINUTE", "5"))
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
        # Daily AI quota fallback: "rl:aiday:{date}:{ident}" -> count
        self._daily: dict[str, int] = {}
        self._last_cleanup = time.monotonic()
        self._redis = _get_redis_client()
        if self._redis:
            logger.info("Rate-limit using Redis: %s", _REDIS_URL)

    @staticmethod
    def _utc_today() -> str:
        return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d")

    @staticmethod
    def _seconds_to_utc_midnight() -> int:
        now = _dt.datetime.now(_dt.timezone.utc)
        midnight = (now + _dt.timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        return max(1, int((midnight - now).total_seconds()))

    async def _check_daily(self, ident: str) -> bool:
        """True if this device still has daily AI budget. Increments on use."""
        key = f"rl:aiday:{self._utc_today()}:{ident}"
        if self._redis:
            try:
                pipe = self._redis.pipeline()
                pipe.incr(key)
                pipe.expire(key, 90000)  # ~25h — outlives the UTC day
                count, _ = await pipe.execute()
                return int(count) <= _AI_DAILY_LIMIT
            except Exception as e:  # noqa: BLE001
                logger.warning("Redis daily-quota error: %s", e)
        count = self._daily.get(key, 0) + 1
        self._daily[key] = count
        return count <= _AI_DAILY_LIMIT

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
        if path.startswith(_AI_PREFIXES):
            scope, limit = "ai", _LIMIT
        elif path.startswith(_FEEDBACK_PREFIXES) and request.method == "POST":
            # Reads (the admin listing) stay on the general budget.
            scope, limit = "feedback", _FEEDBACK_LIMIT
        else:
            scope, limit = "api", _GENERAL_LIMIT

        # Per-device if auth token present, otherwise per-IP
        device_id = getattr(request.state, "device_id", None)
        ident = device_id or (request.client.host if request.client else "unknown")
        key = f"rl:{scope}:{ident}"

        # Fair-use daily quota — AI generation POSTs only (GET catalogues like
        # /story-themes stay free). Checked before the minute window so the
        # user sees the gentle daily message, not the generic burst one.
        if scope == "ai" and request.method == "POST" and _AI_DAILY_LIMIT > 0:
            if not await self._check_daily(ident):
                return JSONResponse(
                    status_code=429,
                    content={"detail": _DAILY_MESSAGE, "code": "daily_limit"},
                    headers={"Retry-After": str(self._seconds_to_utc_midnight())},
                )

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

        # Periodic cleanup of expired buckets to prevent memory leaks/OOM
        if now - self._last_cleanup > 300.0:
            expired_keys = [k for k, (start, _) in self._buckets.items() if now - start >= _WINDOW]
            for k in expired_keys:
                self._buckets.pop(k, None)
            today_prefix = f"rl:aiday:{self._utc_today()}:"
            stale_daily = [k for k in self._daily if not k.startswith(today_prefix)]
            for k in stale_daily:
                self._daily.pop(k, None)
            self._last_cleanup = now

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
