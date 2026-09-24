"""Pydantic models for Tutor Guardian API request/response."""
import json

from pydantic import BaseModel, Field, field_validator

# Request-size ceilings (audit M6). Every byte of a question is fed to the
# classifier, the embedder, BM25 and the LLM; unbounded fields let one request
# carry megabytes through all of them. The app caps its composer at 2000
# characters, so these leave generous headroom for every real client.
MAX_MESSAGE_CHARS = 4000
MAX_HISTORY_TURNS = 12
_CLIENT_ROLES = frozenset({"user", "assistant"})


class ConversationTurn(BaseModel):
    """Single message in a conversation."""

    role: str  # "user" أو "assistant"
    content: str


class UserMessage(BaseModel):
    """Request from the parent describing a child's behaviour concern."""

    age_group: str = Field(max_length=32)
    domain: str | None = Field(None, max_length=64)
    behavior_type: str = Field("", max_length=200)
    severity: str = Field(max_length=32)
    message_text: str = Field("", max_length=MAX_MESSAGE_CHARS)
    session_id: str | None = Field(None, max_length=64)
    # Client-supplied history is only used when there is no server session;
    # it is capped so it cannot smuggle an unbounded transcript into the prompt.
    conversation_history: list[ConversationTurn] = Field(
        default_factory=list, max_length=MAX_HISTORY_TURNS
    )

    @field_validator("conversation_history")
    @classmethod
    def _bounded_client_turns(cls, turns: list[ConversationTurn]) -> list[ConversationTurn]:
        # Checked here, not on ConversationTurn: the server rebuilds turns from
        # stored answers (conversation_store.get_history), which may be long.
        for t in turns:
            if t.role not in _CLIENT_ROLES:
                raise ValueError("history role must be 'user' or 'assistant'")
            if len(t.content) > MAX_MESSAGE_CHARS:
                raise ValueError(f"history turn exceeds {MAX_MESSAGE_CHARS} characters")
        return turns


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
    """POST /api/chat/sessions — create a new session + auth token.

    Both fields were unbounded on a public endpoint. The app sends a UUIDv4
    device id; the pattern also admits the server's own `device_<hex>` form.
    """
    device_id: str | None = Field(
        None, min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$"
    )
    metadata: dict | None = None

    @field_validator("metadata")
    @classmethod
    def _bounded_metadata(cls, v: dict | None) -> dict | None:
        if v is not None and len(json.dumps(v, ensure_ascii=False)) > 4096:
            raise ValueError("metadata too large (max 4 KB)")
        return v


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
