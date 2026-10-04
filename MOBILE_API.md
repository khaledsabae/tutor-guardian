# Tutor Guardian — Mobile API Contract

Contract for the **Android/iOS** clients. The backend is the product; this
document is the source of truth for client integration. Pairs with `API.md`
(short reference); this file is the detailed mobile spec.

- **Base URL (prod):** TBD · **(local):** `http://localhost:8000`
- **Content-Type:** `application/json; charset=utf-8` (all bodies are UTF-8 Arabic-safe)
- **All inference is local** (on-server Ollama) — no user data leaves the backend.

---

## 1. Auth

Each install creates a session with a `device_id` (a client-generated UUID,
stored in secure storage). `POST /api/chat/sessions` returns a `token`; send it
as `Authorization: Bearer <token>` on every `/api/...` call except session
creation itself. Everything below §9 is scoped to the device behind that token:
another device's child, fact or follow-up answers `404`, exactly like a missing
one, and a missing/invalid token answers `401`.

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
{ "session_id": "f3c1...-uuid", "token": "tg_…" }
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
- `child_id` (int, optional, **send it** — §9.1): the child the question is about.
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
  "session_id": "uuid",
  "metadata": { "sources": ["UNICEF", "Centers for Disease Control and Prevention (CDC)"] }
}
```
`metadata` is additive and may carry other keys. `metadata.sources` (≤ 4, in
retrieval order) lists the citations behind a grounded answer
(`llm_generated` / `retrieval_only`); it is empty or absent otherwise (other
modes, cached answers, older servers). The same `metadata` rides the `done` frame of `/stream`.

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

---

## 9. Child memory, follow-ups and the weekly plan («المربّي يعرف ابنك», backend schema v30)

The assistant remembers each child across sessions, asks a few days later
whether its advice worked, and builds one plan per child per week. All routes
are additive; older builds keep working and simply never call them.

### 9.0 Rules the client must follow

- **Auth:** `Authorization: Bearer <token>` (§1). Wrong device → `404`.
- **Branchable errors** carry a stable code:
  `{"detail": {"code": "fact_too_long", "message": "<Arabic message to show>"}}`.
  Malformed bodies (wrong type, unknown enum value) get FastAPI's standard
  `422 {"detail": [ … ]}` list instead.
- **No names, ever, in memory text.** Facts and follow-up strategies are stored
  with a placeholder instead of the child's name: «طفلي» in Arabic text,
  "My child"/"my child" in English text. If the parent types the child's name
  in a fact, the server replaces it. The app **may** swap the placeholder for
  the child's name when rendering (on the device only), e.g. «طفلي يخاف من
  الظلام» → «أحمد يخاف من الظلام». Never send the swapped text back unedited.
- **What is never remembered** (say so in the screen's footer): medication
  names, doses, test results, doctors or hospitals; any disclosure about
  self-harm, abuse or sexual matters; anything about the parents' private life.
- **When the server learns:** only while the parent's switch is on **and** the
  device reports a build ≥ the server's `CHILD_MEMORY_MIN_BUILD` (the build
  number the app already sends on every launch to `POST /api/push/register`
  as `build_number`). Until that variable is set on the server to the build
  that ships the memory screen, nothing is learned from chat and no follow-up
  is opened — but every endpoint below works, and facts the parent adds by hand
  are used. `settings.collecting` tells the app which state it is in.

### 9.1 Send the child with every question

`POST /api/assistant/stream` and `/query` accept `"child_id": <int>` (the child
whose screen the parent asked from). Without it the server guesses (the only
child; a child named in the question; the only child in `age_group`) or uses
no memory at all.

The reply's `metadata` (also on the `done` frame) gains two keys:
```json
"metadata": { "sources": ["…"], "child_id": 12, "memory_facts_used": 2 }
```
`memory_facts_used > 0` means the answer was personalised from memory — show a
small chip («مخصّص لأحمد» / "Personalised for Ahmad") that opens §9.3's screen.
`child_id` is `null` when no child could be resolved.

### 9.2 The memory switch — `GET` / `PUT /api/children/memory/settings`

```http
GET /api/children/memory/settings
→ 200 {"enabled": true, "collecting": false}

PUT /api/children/memory/settings
{"enabled": false}
→ 200 {"enabled": false, "collecting": false}
```
- `enabled` — the parent's switch (default `true`). Off = nothing new is
  learned, no follow-up is opened, and remembered facts stop reaching the
  assistant. **Off deletes nothing** — deletion is §9.3/§9.6.
- `collecting` — `enabled` AND this build is allowed to learn (§9.0).

### 9.3 Facts — what the assistant knows about a child

**Fact object**
```json
{
  "id": 41,
  "child_id": 12,
  "category": "temperament",
  "fact": "طفلي يخاف من الظلام",
  "source": "chat",
  "confidence": 0.9,
  "status": "active",
  "lang": "ar",
  "created_at": "2026-10-04 18:20:11",
  "updated_at": "2026-10-04 18:20:11"
}
```
| Field | Values |
|---|---|
| `category` | `temperament`, `challenge`, `goal`, `tried_strategy`, `outcome`, `health_note`, `school`, `worship`, `other` |
| `source` | `chat` (learned from a conversation), `followup` (from a follow-up answer), `parent_manual` (typed or edited by the parent) |
| `status` | `active` — used by the assistant · `pending` — suggested by the assistant, **not used** until the parent confirms · `rejected` — the parent said it is wrong; kept (hidden) only so it is not learned again |
| `lang` | `ar` or `en` (the script the fact is written in) |

Timestamps are UTC, `YYYY-MM-DD HH:MM:SS`.

Suggested category labels: temperament الطبع / Temperament · challenge تحدٍّ /
Challenge · goal هدف / Goal · tried_strategy أسلوب جُرِّب / Tried · outcome
نتيجة تجربة / Result · health_note ملاحظة صحية / Health note · school الدراسة /
School · worship العبادة / Worship · other أخرى / Other.

`health_note` facts learned from chat always arrive as `pending`: show them
first, with "Is this right?" and two buttons (confirm → `active`, reject).

**List** — `GET /api/children/{child_id}/memory?status=all`
(`status` ∈ `all` (default) · `active` · `pending` · `rejected`)
```json
{
  "child_id": 12,
  "facts": [ {Fact}, … ],
  "settings": {"enabled": true, "collecting": true},
  "limits": {"max_fact_chars": 160, "max_facts": 40}
}
```
Newest first. The server keeps at most 40 facts per child; when it must drop
one, it drops the oldest low-confidence fact it learned itself — never one the
parent typed or a follow-up result.

**Add** — `POST /api/children/{child_id}/memory`
```json
{"category": "goal", "fact": "نريد أن يحفظ سورة الملك قبل رمضان"}
→ 201 {Fact}   (source "parent_manual", status "active")
```
**Edit / confirm / reject** — `PATCH /api/children/{child_id}/memory/{fact_id}`
```json
{"fact": "…", "category": "challenge"}   → 200 {Fact}  (becomes source "parent_manual")
{"status": "active"}                       → 200 {Fact}  (confirm a pending fact)
{"status": "rejected"}                     → 200 {Fact}
```
At least one field is required. **Delete one** —
`DELETE /api/children/{child_id}/memory/{fact_id}` → `200 {"deleted": true, "fact_id": 41}`.
A deleted fact can be learned again if the parent says it again; a rejected
one cannot.

**Forget this child** — `DELETE /api/children/{child_id}/memory`
```json
→ 200 {"child_id": 12, "deleted": {"child_facts": 7, "followups": 2, "weekly_plans": 3}}
```
Deleting the child profile (`DELETE /api/children/{id}`) removes all of it too.

| HTTP | `detail.code` | When |
|---|---|---|
| 404 | (string detail) | child not on this device |
| 404 | `fact_not_found` | fact id not on this child |
| 422 | `fact` | empty after cleaning, or contains a link/phone/e-mail |
| 422 | `fact_too_long` | > 160 characters |
| 422 | `category` / `status` | value outside the enums above |
| 422 | `empty_patch` | PATCH with no field |

### 9.4 Follow-ups — «جرّبت النصيحة؟ نفعت؟»

When an answer recommends a concrete action for a concrete problem, the server
opens one follow-up, due 3–7 days later (at most 3 open per child, one per
topic).

**Follow-up object**
```json
{
  "id": 7,
  "child_id": 12,
  "strategy": "روتين نوم ثابت مع قصة قبل النوم",
  "topic": "sleep",
  "lang": "ar",
  "due_at": "2026-10-08 18:20:11",
  "status": "pending",
  "outcome": null,
  "note": null,
  "created_at": "2026-10-04 18:20:11",
  "answered_at": null
}
```
`topic` ∈ `prayer`, `anger`, `sleep`, `study`, `screens`, `fear`, `siblings`,
`eating`, `lying`, `other`. `status` ∈ `pending` → `answered` | `dismissed` |
`expired` (21 days after `due_at` without an answer). `outcome` ∈ `worked`,
`partly`, `didnt_work`, `didnt_try`.

| Route | Returns |
|---|---|
| `GET /api/children/followups/due?limit=10` | `{"followups": [ … ]}` — pending and due now, every child, oldest first (`limit` 1–20). Drive the Home card from this. |
| `GET /api/children/followups/{id}` | `{"followup": {…}}` in **any** status — what the deep link opens. |
| `GET /api/children/{child_id}/followups?status=pending` | `{"child_id": 12, "followups": [ … ]}`; `status` ∈ `pending` (default), `answered`, `dismissed`, `expired`, `all`. |
| `POST /api/children/followups/{id}/answer` | body `{"outcome": "didnt_work", "note": "optional, ≤ 300 chars"}` → `{"followup": {…answered…}, "fact": {Fact}}` |
| `POST /api/children/followups/{id}/dismiss` | `{"followup": {…dismissed…}}` |

Answering stores the result as an `outcome` fact, e.g.
«جُرِّب مع طفلي: روتين نوم ثابت مع قصة قبل النوم — ولم ينجح.» — and from then
on the assistant is told not to repeat a strategy that did not work and to
offer an alternative instead. The note is shown back to the parent as typed;
only its name-free form reaches the fact.

Errors: `404 followup_not_found` · `409 followup_closed` (answer/dismiss on a
follow-up that is no longer pending — show "already answered") ·
`422` bad `outcome` or `note` too long.

Suggested copy: «هل جرّبت: {strategy}؟» / "Did you try: {strategy}?" with
four buttons — نجحت / Worked · نجحت جزئيًا / Partly · لم تنجح / Didn't work ·
لم أجرّب بعد / Haven't tried yet — plus an optional note field and «لا تسألني
عن هذا» / "Don't ask about this" (= dismiss).

**Push.** One evening run (17:00 UTC). A device gets at most one follow-up push
per 7 days, never the same follow-up twice, nothing while the global push cap
applies, and nothing if the parent switched memory off. Only devices whose
build is ≥ `CHILD_MEMORY_MIN_BUILD` receive it. FCM `data` (all strings):
```json
{"type": "followup_due", "link": "/followup/7", "followup_id": "7", "child_id": "12"}
```
The notification text contains the strategy but never the child's name.

**Deep link:** `/followup/{id}` — the client must add this arm to
`deep_link_handler.dart` (same shape as `/l/{id}`, `/p/{id}`): pop to root, then
open the follow-up sheet for `{id}` after `GET /api/children/followups/{id}`.
If it is no longer `pending`, show its result instead of the buttons.
`push_tapped(type)` uses `followup_due`.

### 9.5 The weekly plan — `GET /api/children/{child_id}/weekly-plan`

Query: `lang` (`en` → English; anything else, or absent → Arabic; the
`Accept-Language` header is used when `lang` is absent) and `tz_offset_minutes`
(the device's UTC offset, e.g. `180` for Riyadh — the week is the parent's local
ISO week, Monday to Sunday).

```json
{
  "child_id": 12,
  "week": "2026-W41",
  "week_start": "2026-10-05",
  "lang": "ar",
  "band": "7-9",
  "focus": {
    "topic": "sleep",
    "title": "نوم كافٍ لتركيز أفضل",
    "reason": "memory",
    "reason_text": "بناءً على ما أخبرتنا به عن طفلك."
  },
  "actions": [
    {"key": "sleep_school_1", "text": "ثبّت موعد النوم في أيام الدراسة، ولا تؤخّره كثيرًا في العطلة."},
    {"key": "sleep_school_2", "text": "أوقف الشاشات قبل النوم بساعة، وضع الهاتف خارج الغرفة."},
    {"key": "sleep_school_3", "text": "خفّف السكريات والمنبّهات في المساء."}
  ],
  "adapted_from_outcomes": false,
  "worship": {"key": "worship_school_3", "text": "اختاروا معًا عملًا خيريًا صغيرًا هذا الأسبوع: إطعام، أو مساعدة جار، أو صدقة."},
  "lesson": {
    "id": "lesson_7-9_medical_emotional_health_02",
    "title": "النوم، التركيز، ومتى تطلب المساعدة",
    "path_id": "path_7-9_medical_emotional_health",
    "estimated_minutes": 7,
    "completed": false
  },
  "source": "bank",
  "generated_at": "2026-10-05 06:12:40"
}
```
- Exactly **3** `actions`, one `worship` act, one `focus`. `lesson` may be
  `null` — hide the lesson row then. `lesson.id` is a real curriculum lesson for
  the child's band: open it with the existing lesson route.
- `focus.reason`: `parent_challenge` (the child's current challenge from
  «رحلة الطفل») · `memory` (what the parent told the assistant) ·
  `age_default` (the most common need at this age, rotating weekly). Show
  `reason_text` under the title.
- `adapted_from_outcomes: true` — an action the parent reported as not working
  was replaced by an alternative.
- Built on the first request of the week and then **fixed for the week** (per
  language); a new plan appears automatically on Monday. Nothing in it is
  generated by a model: every text comes from a hand-written, schema-checked
  bank; only the choice is personal.
- **Bands:** every band has a plan. `prenatal-1`/`0-3` → bonding, sleep,
  screens, a calm home of faith · `2-3`/`4-6` → prayer by example, tantrums,
  sleep, screens, fear, sibling jealousy, bonding · `7-9`/`10-12` and
  `13-15`/`16-18` → prayer, anger, study, screens, sleep, worry, siblings.
- Errors: `404` child not on this device.

### 9.6 Delete-all for memory — `DELETE /api/privacy/memory`

Forgets everything about **every** child of this device (facts, follow-ups,
weekly plans and the memory switch):
```json
→ 200 {"deleted": {"child_facts": 12, "followups": 3, "weekly_plans": 4, "child_memory_settings": 1},
       "deleted_at": "2026-10-04T18:30:00+00:00"}
```
