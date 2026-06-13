"""
Auth middleware — Bearer token validation for the Tutor Guardian API.

Protects /api/assistant/* and /api/chat/* endpoints.
The session-creation endpoint itself (POST /api/chat/sessions) is public.
"""
import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.services import conversation_store as store

logger = logging.getLogger(__name__)

# Endpoints that don't require authentication
_PUBLIC_PATHS = {
    "/api/health",
    "/api/chat/sessions",  # POST (create) is public
    "/api/docs",
    "/api/openapi.json",
    "/api/redoc",
}

# Protected prefixes
_PROTECTED_PREFIXES = (
    "/api/assistant",
    "/api/chat",
    "/api/feedback",
    "/api/children",
)
# Progress PATCH is the only mutating verb under /api/program — we
# match on the exact path suffix so the read-only GETs remain public.
_PROTECTED_PROGRAM_PROGRESS = "/api/program/lessons/"


def _is_protected(path: str, method: str) -> bool:
    # Only POST /api/chat/sessions (session creation) is public; the GET
    # on the same path lists the device's history and needs auth.
    if path == "/api/chat/sessions":
        return method != "POST"
    # In-app feedback: POST is public (anyone can send); the GET list/audio
    # endpoints are admin-gated inside the route via the X-Admin-Key header.
    if path == "/api/feedback/app" or path.startswith("/api/feedback/app/"):
        return False
    if path in _PUBLIC_PATHS:
        return False
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

        # Skip public paths
        if not _is_protected(path, request.method):
            return await call_next(request)

        # GET /api/chat/sessions/{id} is protected (requires auth)
        auth_header = request.headers.get("Authorization", "")

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
