"""
Chat session router — إدارة جلسات المحادثة (mobile-ready)
==========================================================
POST /api/chat/sessions          → create a session, returns session_id + auth token
GET  /api/chat/sessions/{id}     → full session with message history (requires auth)
"""
import hashlib
import logging
import os

from fastapi import APIRouter, HTTPException, Request, status

from app.models.api import SessionCreate, SessionCreateResponse, SessionResponse
from app.services import conversation_store as store

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])


def _session_mint_enforced() -> bool:
    """Read per call (like STORY_AUTH_ENFORCE) so ops can flip it on restart."""
    return os.environ.get("SESSION_MINT_ENFORCE", "").strip().lower() in {"1", "true", "yes"}


@router.post("/sessions", response_model=SessionCreateResponse, status_code=status.HTTP_201_CREATED)
def create_session(request: Request, body: SessionCreate | None = None) -> SessionCreateResponse:
    """Create a new session and return an auth token.

    The returned `token` should be sent as `Authorization: Bearer <token>`
    header on all subsequent requests to /api/assistant/* and /api/chat/*.

    Minting is where a device identity is claimed, and it used to hand a token
    to anyone for any `device_id` — knowing a device id was owning the family's
    data (audit H5). Now:

      * a caller that presents a valid Bearer token (the app sends its last
        one, see TgClient.createSession) may only mint for THAT device — a
        mismatch is refused;
      * a caller claiming a device id that already has tokens, without such
        proof, is refused once SESSION_MINT_ENFORCE is set. Until then it is
        allowed and logged: builds already on Play mint without proof, and
        pushing to main deploys. Flip it once the forced-update floor is above
        the first build that sends proof — the same staging STORY_AUTH_ENFORCE
        uses;
      * new device ids need no proof (that is how an install begins), and the
        per-IP minting budget in rate_limit.py bounds how many a caller gets.
    """
    body = body or SessionCreate()
    device_id = body.device_id

    header = request.headers.get("Authorization", "")
    proof = store.validate_token(header[7:].strip()) if header.startswith("Bearer ") else None
    if proof is not None:
        if device_id and device_id != proof["device_id"]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="الجهاز لا يطابق التوثيق.")
        device_id = device_id or proof["device_id"]
    elif device_id and store.device_has_tokens(device_id):
        if _session_mint_enforced():
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                                detail="مطلوب توثيق الجهاز لإنشاء جلسة جديدة.")
        # Hash only — a raw device id is a credential (audit H5).
        logger.info(
            "session minted for a known device without proof (dev=%s)",
            hashlib.sha256(device_id.encode()).hexdigest()[:12],
        )

    sid, token = store.create_session_with_token(
        device_id=device_id,
        metadata=body.metadata,
    )
    return SessionCreateResponse(session_id=sid, token=token)


@router.get("/sessions")
def list_sessions(request: Request, limit: int = 50) -> dict:
    """List the authenticated device's past conversations (newest first),
    each with a title + message count — powers the chat history drawer."""
    device_id = request.state.device_id
    sessions = store.list_sessions(device_id, limit=limit)
    return {"sessions": sessions}


@router.get("/sessions/{session_id}", response_model=SessionResponse)
def get_session(session_id: str, request: Request) -> SessionResponse:
    """Get full session with message history. Requires auth token.

    The authenticated device can only access its own sessions.
    """
    # Verify this device owns the session
    auth_device = request.state.device_id
    data = store.get_session(session_id)
    if data is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    if data.get("device_id") and data["device_id"] != auth_device:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    return SessionResponse(**data)
