"""
Chat session router — إدارة جلسات المحادثة (mobile-ready)
==========================================================
POST /api/chat/sessions          → create a session, returns session_id + auth token
GET  /api/chat/sessions/{id}     → full session with message history (requires auth)
"""
from fastapi import APIRouter, HTTPException, Request, status

from app.models.api import SessionCreate, SessionCreateResponse, SessionResponse
from app.services import conversation_store as store

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/sessions", response_model=SessionCreateResponse, status_code=status.HTTP_201_CREATED)
def create_session(body: SessionCreate | None = None) -> SessionCreateResponse:
    """Create a new session and return an auth token.

    The returned `token` should be sent as `Authorization: Bearer <token>`
    header on all subsequent requests to /api/assistant/* and /api/chat/*.
    """
    body = body or SessionCreate()
    sid, token = store.create_session_with_token(
        device_id=body.device_id,
        metadata=body.metadata,
    )
    return SessionCreateResponse(session_id=sid, token=token)


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
