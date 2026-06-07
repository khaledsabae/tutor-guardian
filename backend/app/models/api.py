"""Pydantic models for Tutor Guardian API request/response."""
from pydantic import BaseModel


class ConversationTurn(BaseModel):
    """Single message in a conversation."""

    role: str  # "user" أو "assistant"
    content: str


class UserMessage(BaseModel):
    """Request from the parent describing a child's behaviour concern."""

    age_group: str
    domain: str | None = None
    behavior_type: str = ""
    severity: str
    message_text: str = ""
    session_id: str | None = None
    conversation_history: list[ConversationTurn] = []


class AssistantReply(BaseModel):
    """Guardrailed assistant reply returned to the parent."""

    reply_text: str
    domain: str
    severity: str
    needs_human_review: bool
    escalation_target: str | None = None
    metadata: dict | None = None
    mode: str = "retrieval_only"
    session_id: str | None = None


# ── Auth & session management (mobile-ready) ─────────────────────────────────
class SessionCreate(BaseModel):
    """POST /api/chat/sessions — create a new session + auth token."""
    device_id: str | None = None
    metadata: dict | None = None


class SessionCreateResponse(BaseModel):
    """Response to session creation — includes auth token."""
    session_id: str
    token: str


class SessionResponse(BaseModel):
    """GET /api/chat/sessions/{id} response."""
    id: str
    device_id: str | None = None
    created_at: str
    updated_at: str
    metadata: dict
    messages: list["ChatMessageOut"]


class ChatMessageOut(BaseModel):
    role: str
    content: str
    domain: str | None = None
    severity: str | None = None
    mode: str | None = None
    needs_human_review: bool = False
    created_at: str
