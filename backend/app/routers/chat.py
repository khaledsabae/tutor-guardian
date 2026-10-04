"""
Chat session router — إدارة جلسات المحادثة (mobile-ready)
==========================================================
POST /api/chat/sessions          → create a session, returns session_id + auth token
GET  /api/chat/sessions/{id}     → full session with message history (requires auth)
POST /api/chat/sessions/{id}/stop → stop the answer being generated (requires auth)
"""
import asyncio
import logging
import os

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel

from app.core.log_safety import device_tag
from app.models.api import SessionCreate, SessionCreateResponse, SessionResponse
from app.services import conversation_store as store
from app.services import device_twins

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

    One exception to "a mismatch is refused", and one addition, both for
    installs that 1.0.58-1.0.67 split into two device ids (services/
    device_twins.py has the evidence rule): when the claimed device and the
    proven one are the two halves of one install, or the proven device is a
    childless twin of the family's device, the session is minted for the
    family's device and the twin is folded into it. The response names the
    device minted for; the app adopts it when it differs from what it asked.
    """
    body = body or SessionCreate()
    # A device id folded into its family's device (services/device_twins.py)
    # stands for that device: the app still has the old id on disk.
    device_id = device_twins.canonical_of(body.device_id) or body.device_id

    header = request.headers.get("Authorization", "")
    proof = header[7:].strip() if header.startswith("Bearer ") else None
    # An expired token still proves the device (token_device): tokens now
    # lapse after TOKEN_TTL_DAYS idle, and the install holding one must be
    # able to mint its next session once minting is enforced.
    proof_device = store.token_device(proof) if proof else None
    if proof_device is not None:
        device_id = device_twins.resolve_mint(device_id, proof_device, proof=proof)
        if device_id is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="الجهاز لا يطابق التوثيق.")
    elif device_id and store.device_has_tokens(device_id):
        if _session_mint_enforced():
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                                detail="مطلوب توثيق الجهاز لإنشاء جلسة جديدة.")
        logger.info("session minted for a known device without proof (%s)",
                    device_tag(device_id))

    sid, token = store.create_session_with_token(
        device_id=device_id,
        metadata=body.metadata,
    )
    return SessionCreateResponse(session_id=sid, token=token, device_id=device_id)


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


class StopRequest(BaseModel):
    message_id: int | None = None


@router.post("/sessions/{session_id}/stop")
async def stop_answer(session_id: str, request: Request,
                      body: StopRequest | None = None) -> dict:
    """Stop the answer this session is generating — the parent pressed Stop.

    Additive (2026-10). Without it a Stop looked exactly like the app going to
    the background, and the server finished the rejected answer anyway: paid
    tokens, a worker held for minutes, and an answer the parent dismissed
    written into the conversation. App builds that never call this keep the
    old behaviour: a closed stream is finished in the background.

    Lives under /api/chat, not /api/assistant: stopping must not count against
    the daily AI question quota. `message_id` names the question being
    stopped; a stop that arrives after a newer question started is a no-op.
    """
    exists, owner = await asyncio.to_thread(store.session_owner, session_id)
    caller = getattr(request.state, "device_id", None)
    if not exists or (owner and owner != caller):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    from app.routers.assistant import cut_pending_turn  # lazy: avoid an import cycle

    stopped = await cut_pending_turn(
        session_id, "stopped_by_parent",
        only_message_id=body.message_id if body else None,
    )
    return {"stopped": stopped}
