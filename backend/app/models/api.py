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
    conversation_history: list[ConversationTurn] = []


class AssistantReply(BaseModel):
    """Guardrailed assistant reply returned to the parent."""

    reply_text: str
    domain: str
    severity: str
    needs_human_review: bool
    escalation_target: str | None = None
    metadata: dict | None = None
    mode: str = "retrieval_only"  # "retrieval_only" | "llm_generated"
