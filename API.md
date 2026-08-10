# Tutor Guardian API

The backend is the product; the web page under `/ui` is a dev/test client only.
The real client is a native mobile app (Android/iOS) consuming this API.

Base URL (local): `http://localhost:8000`

## Auth

Bearer token, enforced by `backend/app/middleware/auth.py` on these prefixes:

```
/api/assistant  /api/chat            /api/feedback         /api/children
/api/insights   /api/referral        /api/push             /api/identity
/api/daily-routine   /api/value-tracking   /api/habit-templates
```

Everything else is public on purpose: the curriculum is readable without an
account. Two mutations are carved out of otherwise-public prefixes and do
require a token — `PATCH /api/program/lessons/{id}/progress` and
`/api/program/monthly-report` — while the read-only GETs beside them stay open.

Child Mode issues its own short-lived token, and admin endpoints use an
`X-Admin-Key` header compared with `secrets.compare_digest`.

## Endpoints

### `GET /health`
Liveness probe → `{"status": "ok"}`.

### `POST /api/chat/sessions`
Create a server-side conversation session.
```json
// body (all optional)
{ "device_id": "abc-123", "metadata": {} }
// 201 →
{ "session_id": "uuid" }
```

### `GET /api/chat/sessions/{session_id}`
Full session with message history. `404` if unknown.

### `POST /api/assistant/query`
Blocking (non-streamed) reply.
```json
// body
{
  "age_group": "7-9",            // 0-3|4-6|7-9|10-12|13-15|16-18
  "severity": "متوسط",           // خفيف|متوسط|شديد|طارئ
  "behavior_type": "قلق",        // optional
  "message_text": "ابني قلق من المدرسة",
  "session_id": "uuid"           // optional; if set, server owns history
}
// 200 → AssistantReply
{
  "reply_text": "...",
  "domain": "medical",
  "severity": "متوسط",
  "needs_human_review": true,
  "escalation_target": "pediatrician",   // or null
  "mode": "llm_generated",               // retrieval_only|llm_generated|banned|emergency
  "session_id": "uuid"
}
```
If `session_id` is set, the server persists both the user message and the
reply, and loads history from the DB (ignores any client-sent
`conversation_history`). Unknown `session_id` → `404`.

### `POST /api/assistant/stream`
Same input as `/query`, but the answer streams as **Server-Sent Events**:
```
event: token   data: {"delta": "..."}     ← repeated, LLM tokens
event: done    data: { <AssistantReply> } ← always, terminal
event: error   data: {"detail": "..."}    ← on failure
```
Safety decisions (banned / emergency / no-context / forced fallback) run
**before** any token is sent — those replies arrive as a single `done` event
(never streamed). Only genuine LLM generation streams.

Consuming SSE on mobile: read the chunked body, split frames on `\n\n`, parse
`event:` / `data:` lines. (See `frontend/index.html` for a reference parser.)

## Rate limiting
Per-IP fixed window on `/api/assistant/*`: `RATE_LIMIT_PER_MINUTE` (default 30,
`0` disables) → `429` with `Retry-After`.

## Notes for the mobile team
- Send `session_id` and only the new `message_text`; the server keeps history.
- The reply's `needs_human_review` / `escalation_target` drive the UI's
  "see a specialist / emergency" banners.
- All LLM inference is **local** (Ollama) — no user data leaves the backend.
