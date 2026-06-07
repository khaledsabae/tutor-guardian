"""Pydantic models for Tutor Guardian API request/response."""
from pydantic import BaseModel


class ConversationTurn(BaseModel):
    """Single message in a conversation."""

    role: str  # "user" أو "assistant"
    content: str


class UserMessage(BaseModel):
    """Request from the parent describing a child's behaviour concern."""

    age_group: str  # "0-3", "4-6", "7-9", "10-12", "13-15", "16-18"
    domain: str = ""  # auto-detected by classifier; can be empty
    behavior_type: str = ""  # optional
    severity: str  # "خفيف", "متوسط", "شديد", "طارئ"
    message_text: str = ""  # الوصف الحر من الوالد/الوالدة
    # When set, server loads/persists history for this session and ignores
    # the client-sent conversation_history below (server owns the truth).
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
    mode: str = "retrieval_only"  # "retrieval_only" | "llm_generated" | "banned" | "emergency"
    session_id: str | None = None


# ── Chat session management (mobile-ready) ──────────────────────────────────
class SessionCreate(BaseModel):
    device_id: str | None = None
    metadata: dict | None = None


class SessionResponse(BaseModel):
    session_id: str


class ChatMessageOut(BaseModel):
    role: str
    content: str
    domain: str | None = None
    severity: str | None = None
    mode: str | None = None
    needs_human_review: bool = False
    created_at: str


class SessionDetail(BaseModel):
    id: str
    device_id: str | None = None
    created_at: str
    updated_at: str
    metadata: dict
    messages: list[ChatMessageOut]
