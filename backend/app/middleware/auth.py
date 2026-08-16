"""
Auth middleware — Bearer token validation for the Tutor Guardian API.

Protects /api/assistant/*, /api/chat/*, /api/insights/* and other auth-gated endpoints.
The session-creation endpoint itself (POST /api/chat/sessions) is public.
"""
import logging
import os

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.services import child_budget
from app.services import child_token as child_token_service
from app.services import conversation_store as store

logger = logging.getLogger(__name__)

# Child-mode endpoints are protected by a separate token scheme.
_CHILD_MODE_PREFIX = "/api/value-tracking/child-mode/"

# The QR web surface mints and carries the same Child-Bearer token, but it was
# left outside every prefix below — so `_is_protected` returned False for it,
# the middleware never populated `request.state`, and /me and /refresh answered
# 401 to every browser no matter how valid its token was. Both prefixes now go
# through the same branch; the paths that must stay reachable without a token
# are named in _CHILD_TOKEN_EXEMPT_PATHS rather than left unmatched.
_CHILD_WEB_PREFIX = "/api/child-web/"
_CHILD_TOKEN_PREFIXES = (_CHILD_MODE_PREFIX, _CHILD_WEB_PREFIX)

# Endpoints that don't require authentication
_PUBLIC_PATHS = {
    "/api/health",
    "/api/app-config",
    "/health",
    "/api/chat/sessions",  # POST (create) is public
    "/api/docs",
    "/api/openapi.json",
    "/api/redoc",
    # Redeeming a QR claim code is how a browser *gets* its token; requiring
    # one here would make the web surface unreachable. The code itself is the
    # credential: single-use, 120-second lifetime, and it opens the screen
    # session (and so passes the age gate) before returning anything.
    "/api/child-web/claim-session",
}

# Protected prefixes
_PROTECTED_PREFIXES = (
    "/api/assistant",
    "/api/chat",
    "/api/feedback",
    "/api/children",
    "/api/insights",
    "/api/referral",
    "/api/push",
    "/api/identity",
    "/api/daily-routine",
    "/api/value-tracking",
    "/api/habit-templates",
    "/api/child-web",
)
# Progress PATCH is the only mutating verb under /api/program — we
# match on the exact path suffix so the read-only GETs remain public.
_PROTECTED_PROGRAM_PROGRESS = "/api/program/lessons/"

# Soft-protected: authenticate when a token is present, but do not 401 when
# it is absent.
#
# /api/program/story generates on the model and was reachable by anyone. It
# needs an identity — but adding it to the list above would 401 every build
# already on Play from the moment this deploys, and pushing to main deploys.
# So the middleware binds device_id when the caller has a token, and lets the
# rest through until STORY_AUTH_ENFORCE is set on the server. Flip it once the
# forced-update floor is above the last build that calls this anonymously; the
# behaviour then is identical to _PROTECTED_PREFIXES.
#
# This is not "unprotected in the meantime": the endpoint sits behind the AI
# rate limiter (rate_limit._AI_PREFIXES) with a per-identity daily quota, and
# an anonymous caller is counted by IP.
#
# Matched exactly, not by prefix: "/api/program/story" as a prefix also
# swallows "/api/program/story-themes", the public catalogue the theme picker
# reads before anyone has picked anything.
_SOFT_PROTECTED_PATHS = frozenset({"/api/program/story"})


def _story_auth_enforced() -> bool:
    """Read at call time, not import time, so the VPS can flip it on restart
    without a redeploy — and so tests can set it per-case."""
    return os.environ.get("STORY_AUTH_ENFORCE", "").strip().lower() in {"1", "true", "yes"}


# Child-token paths that authenticate but do not require a live screen session.
# See the comment at the call site for why each one is here.
_SESSION_CHECK_EXEMPT = frozenset({
    "/api/child-web/me",
    "/api/child-web/refresh",
})


def _skips_session_check(path: str) -> bool:
    return path.endswith("/session-end") or path in _SESSION_CHECK_EXEMPT


def _is_protected(path: str, method: str) -> bool:
    # Only POST /api/chat/sessions (session creation) is public; the GET
    # on the same path lists the device's history and needs auth.
    if path == "/api/chat/sessions":
        return method != "POST"
    # In-app feedback: POST is public (anyone can send); the GET list/audio
    # and digest endpoints are admin-gated inside the route via X-Admin-Key.
    if (path == "/api/feedback/app" or path.startswith("/api/feedback/app/")
            or path == "/api/feedback/digest"):
        return False
    # Telegram calls this webhook; it has no device token and never will.
    # It is NOT unguarded: the route verifies a shared secret sent in the
    # X-Telegram-Bot-Api-Secret-Token header and rejects any chat other than
    # the configured one. It fails closed when that secret is unset.
    # Everything else under /api/feedback (including /replies, which reads the
    # caller's device id from its token) stays protected by the prefix below.
    if path == "/api/feedback/telegram/webhook":
        return False
    if path in _PUBLIC_PATHS:
        return False
    # Coach tip (GET fetch + POST {id}/tap) both read the device identity from
    # request.state.device_id, which is only populated for protected routes.
    # Without this they 401 for everyone and the Home «نصيحة اليوم» card, which
    # silently hides on error, never renders.
    if path.startswith("/api/program/coach-tip"):
        return True
    # Monthly report exposes a child's name and progress — device-owned data.
    if path.startswith("/api/program/monthly-report"):
        return True
    # Once enforcement is on, a soft-protected path is simply protected.
    if path in _SOFT_PROTECTED_PATHS and _story_auth_enforced():
        return True
    for prefix in _PROTECTED_PREFIXES:
        if path.startswith(prefix):
            return True
    if method == "PATCH" and path.startswith(_PROTECTED_PROGRAM_PROGRESS):
        return path.endswith("/progress")
    return False


class AuthMiddleware(BaseHTTPMiddleware):
    """Validates Bearer tokens on protected endpoints."""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Skip public paths — but a soft-protected path in its grace window
        # still gets its identity read, so the route can bind the story to a
        # device and check that the child belongs to it. A caller with no
        # token, or a stale one, passes through anonymous rather than 401.
        if not _is_protected(path, request.method):
            if path in _SOFT_PROTECTED_PATHS:
                header = request.headers.get("Authorization", "")
                if header.startswith("Bearer "):
                    info = store.validate_token(header[7:].strip())
                    if info is not None:
                        request.state.device_id = info["device_id"]
                        request.state.session_id = info["session_id"]
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")

        # Child-mode routes use a separate scoped token scheme.
        if path.startswith(_CHILD_TOKEN_PREFIXES):
            if not auth_header.startswith("Child-Bearer "):
                return JSONResponse(
                    status_code=401,
                    content={"detail": "مطلوب توثيق وضع الطفل."},
                )
            token = auth_header[13:].strip()
            payload = child_token_service.verify_child_token(token, allow_web=True)
            if payload is None:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "توكن وضع الطفل غير صالح أو منتهي."},
                )
            request.state.child_mode = True
            request.state.device_id = payload["device_id"]
            request.state.child_id = payload["child_id"]
            request.state.token = token

            # A valid token is not a live session. The token's TTL is already
            # clamped to the budget at issue time, but clamping alone leaves
            # the window between "budget ran out" and "token expires" — and a
            # token issued for a 20-minute allowance that the child spent in
            # ten still parses fine for the other ten. The open session is the
            # authority; a closed one means the surface is over.
            #
            # session-end is exempt so a client can always report a clean
            # close, including the close that exhausted the budget. The kill
            # switch skips the check entirely — with the surface off, no
            # sessions are being opened, so requiring one would lock every
            # child out rather than restoring the old behaviour.
            #
            # /child-web/me and /child-web/refresh are exempt for a different
            # reason: neither hands the child any content. One returns the name
            # already printed on the QR the parent just showed, the other swaps
            # a token for an equivalent token bound to the same identity. The
            # session check belongs on the surfaces that spend the budget, and
            # those all live under the child-mode prefix. Gating a token
            # refresh on a live session would also mean the browser can never
            # recover from an expired token without a new QR.
            if child_budget.child_surface_enabled() and not _skips_session_check(path):
                if child_budget.active_session(payload["child_id"]) is None:
                    return JSONResponse(
                        status_code=403,
                        content={
                            "error": "child_budget_exhausted",
                            "message_key": "child_gate.budget_exhausted",
                            "message_ar": "خلصت مدة النهارده. نكمل بكرة إن شاء الله 🌙",
                        },
                    )
            return await call_next(request)

        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"detail": "مطلوب توثيق (Bearer token). أنشئ جلسة أولاً عبر POST /api/chat/sessions."},
            )

        token = auth_header[7:].strip()
        token_info = store.validate_token(token)

        if token_info is None:
            return JSONResponse(
                status_code=401,
                content={"detail": "Token غير صالح أو منتهي. أنشئ جلسة جديدة."},
            )

        # Attach device_id + session_id to request state for downstream use
        request.state.device_id = token_info["device_id"]
        request.state.session_id = token_info["session_id"]
        request.state.token = token

        return await call_next(request)
