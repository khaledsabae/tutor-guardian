"""
Chat session router — إدارة جلسات المحادثة (mobile-ready)
==========================================================
POST /api/chat/sessions          → create a session, returns session_id
GET  /api/chat/sessions/{id}     → full session with message history
"""
from fastapi import APIRouter, HTTPException, status

from app.models.api import SessionCreate, SessionDetail, SessionResponse
from app.services import conversation_store as store

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/sessions", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
def create_session(body: SessionCreate | None = None) -> SessionResponse:
    body = body or SessionCreate()
    sid = store.create_session(device_id=body.device_id, metadata=body.metadata)
    return SessionResponse(session_id=sid)


@router.get("/sessions/{session_id}", response_model=SessionDetail)
def get_session(session_id: str) -> SessionDetail:
    data = store.get_session(session_id)
    if data is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return SessionDetail(**data)
