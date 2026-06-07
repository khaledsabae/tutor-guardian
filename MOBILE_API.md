# Tutor Guardian — Mobile API Contract

Contract for the **Android/iOS** clients. The backend is the product; this
document is the source of truth for client integration. Pairs with `API.md`
(short reference); this file is the detailed mobile spec.

- **Base URL (prod):** TBD · **(local):** `http://localhost:8000`
- **Content-Type:** `application/json; charset=utf-8` (all bodies are UTF-8 Arabic-safe)
- **All inference is local** (on-server Ollama) — no user data leaves the backend.

---

## 1. Auth (current + planned)

**Current:** none — endpoints are open. Do not ship to public stores as-is.

**Planned (mobile):** each install creates a session with a `device_id`
(a client-generated UUID, stored in the device keychain/keystore). The server
ties conversations to `device_id`. When real accounts land, a bearer token will
be added in the `Authorization` header; design your HTTP layer to inject it now.

---

## 2. Enums (stable — safe to hard-code in the app)

| Field | Values |
|-------|--------|
| `age_group` | `0-3`, `4-6`, `7-9`, `10-12`, `13-15`, `16-18` |
| `severity` | `خفيف`, `متوسط`, `شديد`, `طارئ` |
| `domain` (returned) | `medical`, `cyber`, `islamic_parenting`, `development` |
| `mode` (returned) | `retrieval_only`, `llm_generated`, `banned`, `emergency` |
| `escalation_target` | `pediatrician`, `cybersecurity_specialist`, `emergency_services`, `null` |

> `severity` values are Arabic strings — send them exactly. Localize labels in
> the UI, but the wire value stays Arabic.

---

## 3. Endpoints

### 3.1 `GET /health`
Liveness probe. → `200 {"status":"ok"}`. Use for a startup connectivity check.

### 3.2 `POST /api/chat/sessions` — create a session
Call once per conversation (or reuse across the app's lifetime per device).

Request (all optional):
```json
{ "device_id": "550e8400-e29b-41d4-a716-446655440000", "metadata": {"app_version":"1.0.0"} }
```
Response `201`:
```json
{ "session_id": "f3c1...-uuid" }
```

### 3.3 `GET /api/chat/sessions/{session_id}` — history
Response `200`:
```json
{
  "id": "uuid",
  "device_id": "uuid|null",
  "created_at": "2026-06-07T01:00:00",
  "updated_at": "2026-06-07T01:05:00",
  "metadata": {},
  "messages": [
    { "role": "user", "content": "...", "domain": null, "severity": null,
      "mode": null, "needs_human_review": false, "created_at": "..." },
    { "role": "assistant", "content": "...", "domain": "medical",
      "severity": "متوسط", "mode": "llm_generated",
      "needs_human_review": true, "created_at": "..." }
  ]
}
```
`404` if the session id is unknown. Use this to rehydrate a chat on app open.

### 3.4 `POST /api/assistant/query` — blocking answer
Use when you don't need streaming (e.g. background/notification flows).

Request:
```json
{
  "age_group": "7-9",
  "severity": "متوسط",
  "behavior_type": "قلق",
  "message_text": "ابني قلق من المدرسة، أعمل إيه؟",
  "session_id": "uuid"
}
```
- `age_group` + `severity` + `message_text` required. `behavior_type` optional.
- With `session_id`: server persists the turn and owns history → **do not send
  `conversation_history`**. Without it, you may send
  `conversation_history: [{role,content}, ...]` (legacy/stateless mode).

Response `200` — **AssistantReply**:
```json
{
  "reply_text": "…",
  "domain": "medical",
  "severity": "متوسط",
  "needs_human_review": true,
  "escalation_target": "pediatrician",
  "mode": "llm_generated",
  "session_id": "uuid"
}
```

### 3.5 `POST /api/assistant/stream` — streaming answer (preferred for chat UI)
Same request body as `/query`. Response is **`text/event-stream`**.

Event frames (separated by a blank line `\n\n`):
```
event: token
data: {"delta": "في"}

event: token
data: {"delta": " هذه"}

event: done
data: {"reply_text":"…","domain":"medical","severity":"متوسط",
       "needs_human_review":true,"escalation_target":"pediatrician",
       "mode":"llm_generated","session_id":"uuid"}
```
On failure: `event: error` `data: {"detail":"..."}`.

**Guarantees the client can rely on:**
- Safety replies (`banned`, `emergency`, no-context, forced-fallback) are sent as
  a **single `done` event with zero `token` events** — never partially streamed.
- Exactly **one** terminal event (`done` or `error`) per request.
- Append `delta`s in arrival order to build the message; replace with
  `done.reply_text` at the end (it is the authoritative final text).

---

## 4. Rendering the safety flags

Drive the UI from the `done`/reply object — never parse the prose:
- `needs_human_review == true` → show a "راجع مختصاً" (verify with a specialist) banner.
- `escalation_target == "emergency_services"` → red "حالة طارئة" banner + a call-to-action.
- `mode == "banned"` → show the out-of-scope notice; don't render as a normal answer.

---

## 5. Errors

| HTTP | Meaning | Client action |
|------|---------|---------------|
| `404` | unknown `session_id` | drop the stored id, create a new session, retry |
| `422` | validation (bad/missing field) | fix the payload; check enums |
| `429` | rate limited (`Retry-After` header, seconds) | back off, then retry |
| `5xx` | server/model error | show retry; the `/stream` path may also emit `event: error` |

Rate limit: per-IP fixed window on `/api/assistant/*` (default 30/min).

---

## 6. Client SSE consumers (reference)

### Swift (iOS) — `URLSession` bytes stream
```swift
var req = URLRequest(url: URL(string: "\(base)/api/assistant/stream")!)
req.httpMethod = "POST"
req.setValue("application/json", forHTTPHeaderField: "Content-Type")
req.httpBody = try JSONEncoder().encode(payload)   // {age_group, severity, message_text, session_id}

let (bytes, _) = try await URLSession.shared.bytes(for: req)
var buffer = ""
for try await line in bytes.lines {
    if line.hasPrefix("data: ") {
        let json = String(line.dropFirst(6))
        // decode {"delta": "..."} (token) or the full reply (done)
        handle(json)
    }
}
```

### Kotlin (Android) — OkHttp streaming body
```kotlin
val body = json.toRequestBody("application/json".toMediaType())
val req = Request.Builder().url("$base/api/assistant/stream").post(body).build()
client.newCall(req).execute().use { resp ->
    val source = resp.body!!.source()
    while (!source.exhausted()) {
        val line = source.readUtf8Line() ?: break
        if (line.startsWith("data: ")) handle(line.removePrefix("data: "))
    }
}
```

### Dart (Flutter) — `http` streamed response
```dart
final req = http.Request('POST', Uri.parse('$base/api/assistant/stream'))
  ..headers['Content-Type'] = 'application/json'
  ..body = jsonEncode(payload);
final res = await req.send();
res.stream.transform(utf8.decoder).transform(const LineSplitter()).listen((line) {
  if (line.startsWith('data: ')) handle(line.substring(6));
});
```

> A reference parser in plain JS lives in `frontend/index.html` (dev/test client).

---

## 7. Recommended client flow
1. On first launch: generate + persist a `device_id` (UUID) in secure storage.
2. Create a session (`POST /api/chat/sessions`) → cache `session_id`.
3. For each question: `POST /api/assistant/stream` with `session_id` + the new
   message only. Render tokens live; on `done`, apply safety flags.
4. On app reopen: `GET /api/chat/sessions/{id}` to restore history (or start fresh).
5. Handle `404` by recreating the session; `429` by backing off.

---

## 8. Versioning
This contract is **v1**. Breaking changes will move under a `/api/v2` prefix;
additive fields may appear on responses — clients must ignore unknown fields.
