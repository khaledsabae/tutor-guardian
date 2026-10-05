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

**Erased devices — `410 device_erased`** (backend schema v35). An account
deletion (§10) keeps a one-way hash of every device id it removed, never the id.
A mint that claims such an id **without a live token of it** — an install
restored from an Android Auto Backup after the deletion, or one settling a
deletion whose answer was lost — answers:
```http
POST /api/chat/sessions
X-App-Build: 120
{"device_id": "<an erased id>"}
→ 410 {"detail": {"code": "device_erased",
                  "message": "حُذف هذا الحساب نهائيًا. سيبدأ التطبيق من جديد على هذا الهاتف.",
                  "message_en": "This account was deleted. The app will start over on this phone."}}
```
- **Only for builds that send `X-App-Build: <build number>`** (the integer Android
  `versionCode`, digits only) **≥ the server's `ERASED_DEVICE_410_MIN_BUILD`**,
  which `GET /api/app-config` reports as `"erased_device_410_min_build": 120`
  (`null` = no build yet). Send the header on every mint once the build handles
  the 410; a build that does not handle it must not send it. Any other mint —
  no header, a lower build, or the variable unset — gets the fresh, empty `201`
  it always got.
- **Client on `410 device_erased`:** this device id's account is gone. Wipe
  everything the backup restored with it — the session and the last token kept
  as mint proof, cached children and chat, preferences, the stored `device_id`
  and its backup copy —
  generate a **new** `device_id`, and mint again (`201`). Never retry the old id.
  Show at most a calm notice (`message` / `message_en`); it is not an error.
- **Not refused:** a brand-new device id; and an erased id presented together with
  a token minted for it *after* the deletion (`Authorization: Bearer`) — an older
  build reinstalled meanwhile and started a new account under the old id, which
  is a live install. Only a token from before the deletion (gone with the data)
  is no proof.

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
- **Timestamps:** every timestamp in §9–§10 is ISO 8601, UTC, with `Z`
  (`"2026-10-04T18:30:00Z"`). Parse it as UTC; show it in the device's time.
- **Proven session required** for every route in §9.3, §9.4 and §9.6, for
  `PUT /api/children/memory/settings` with `{"enabled": true}`, and for §10.
  *Proven* = this session (bearer token) completed the device-proof challenge
  (§9.0.1), and the push token the code went to is still this device's push
  token. Otherwise these routes answer
  `403 {"detail": {"code": "device_proof_required", "message": "…", "message_en": "…",
  "support_email": "support@alsaba.cloud"}}`. **Client flow:** on
  `device_proof_required`, run §9.0.1 once, then retry the request once.
  **Always allowed without a proof:** `GET /api/children/memory/settings`,
  switching memory **off** (`PUT … {"enabled": false}`), and the weekly plan (§9.5).
- **Destructive child routes** — `DELETE /api/children/{id}`,
  `DELETE /api/children/{id}/progress`, and `PATCH /api/children/{id}` **when it
  changes `name`** (a rename rewrites the siblings' memory, see *Placeholders*) —
  need a proven session too, **once this device has proven at least once** (and
  for every device once the server's `MINIMUM_BUILD_NUMBER` reaches
  `CHILD_MEMORY_MIN_BUILD`). Same `403`, same flow: wrap a rename in the same
  prove-and-retry-once as a child deletion. A `PATCH` that leaves `name` as it
  is (age group, gender, avatar) never needs it.
  Any push-token pause (§9.0.1) refuses them for every session, proven or not.
  **What a child deletion removes:** from a proven session, everything tied to the
  child (progress, memory, tools…); from any other session — possible only on a
  device that never proved, outside every pause — only the profile row, exactly
  as before this change. Either way the siblings' memory is re-lettered (see
  *Placeholders* below); nothing of theirs is deleted.
- **A proof belongs to one session and one push token.** Minting a new session
  (`POST /api/chat/sessions`) or a new FCM token (`onTokenRefresh`, reinstall,
  another phone) means proving again. Earlier tokens never vouch for a new one —
  presenting the last token when minting (what builds ≥ 106 do) still links the
  new session to the device, but grants nothing protected. Reuse one session
  for the app's lifetime where you can.
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
  In memory text **every** child name of the family is replaced wherever it
  stands as a word — with و/ف/ب/ل/ك attached, and in the accusative («محمدًا»)
  — even a name that is also an ordinary word (نور، أمل، هدى، دعاء…): «يحب نور
  القرآن» in a fact of a family with a نور is stored «يحب طفلي القرآن» (or
  «الطفل ب…» for a sibling). That is deliberate; the on-device swap gives the
  parent back the words they wrote. Not replaced: the name with «ال» attached
  (النور), a religious reference (النبي محمد ﷺ، سورة يوسف), «على» for a
  child named علي, and «ف/ك» read off a word that is an everyday word as a
  whole («فعلا» for a child «علا», «كريم» for «ريم»; «فعمر» is still عمر). A child whose name is the onboarding default — «طفلي» /
  "My child" — has no name to replace: in any text «طفلي» stays the fact's
  own child, never that sibling (it keeps its letter for placeholders).
- **What is never remembered** (say so in the screen's footer): medicines —
  names, doses, prescriptions — test results, doctors or hospitals; anything
  about self-harm, suicide, abuse, sexual matters or drugs; anything about the
  parents' private life. This holds for every category, every follow-up strategy
  and every note — a parent-typed fact like that is refused with `422 sensitive`.
  A question that names a *second* child of the family is not learned from.
- **Placeholders:** one child → «طفلي»; several → the question's child is «طفلي»
  and siblings «الطفل أ», «الطفل ب»… by profile order. A fact may therefore
  mention «الطفل ب»: render it with that sibling's name on the device.
  "Profile order" is ascending child `id`, counting only children whose
  trimmed name has ≥ 2 characters; letters `أبجدهوزحطيكلمن`, then `15`, `16`…
  The letters always match the family **as it is now**: when a child is
  deleted, the server rewrites the siblings' memory in the same step — a
  remaining sibling gets its new letter, and a mention of the deleted child
  (by letter, by name, or by name in a follow-up's `note`) becomes the plain
  words «طفل آخر» (`another child` in English text; «طفلة أخرى» where it was
  written «الطفلة ب»). A rename (`PATCH /api/children/{id}` with `name`) that
  crosses the 2-character floor re-letters the same way, and a stored mention
  of the child's old name becomes its placeholder. Render «طفل آخر» as it is.
  Never keep rendered memory text across a child deletion or rename —
  re-fetch, then render with the current child list.
- **When memory is used and learned:** only for a **proven session** (above),
  while the parent's switch is on, on a device that reports a build ≥ the
  server's `CHILD_MEMORY_MIN_BUILD` (the build number the app already sends on
  every launch to `POST /api/push/register` as `build_number`). Then remembered
  facts reach answers (§9.1) and the daily coach tip, and the answer can teach
  memory something new. For any other session nothing is learned and no fact is
  used — the answer is simply general. Until that variable is set on the server
  to the build that ships the memory screen, nothing is learned or used.
  `settings.collecting` tells the app which state this session is in.

### 9.0.1 Device proof — the FCM challenge

The server proves a session holds the phone by sending a one-time code to the
device's **current** push token, as a silent data message. Data messages need
no notification permission — **register the FCM token on every launch even when
the parent declined notifications.**

```http
GET /api/device-proof
→ 200 {"proven": false, "proven_at": null, "push_registered": true,
       "cooldown_until": null, "deletion_paused_until": null}

POST /api/device-proof/start
→ 202 {"challenge_id": "q3Vb0J7xQ2m8YtKa", "expires_in": 300}

# FCM data message to this device's registered token — no notification block:
#   {"type": "device_proof", "challenge_id": "q3Vb0J7xQ2m8YtKa", "code": "<32 characters>"}

POST /api/device-proof/complete
{"challenge_id": "q3Vb0J7xQ2m8YtKa", "code": "<the code from the data message>"}
→ 200 {"proven": true, "proven_at": "2026-10-04T18:30:00Z"}
```
- **Same session throughout:** call `start` and `complete` with the same bearer
  token. Handle the data message in `FirebaseMessaging.onMessage` (the app is in
  the foreground: the parent just tapped something) and in the background
  handler; post it back **only if `challenge_id` is the one this session is
  waiting for** — ignore any other `device_proof` message. Never show the code
  or log it.
- **Wait at most 20 seconds** for the message. If it does not come, or
  `complete` fails, start once more; after that show `message` / `message_en`
  with the support address (`support_email`) — the parent can still turn
  memory off, and can ask for deletion by e-mail.
- **When to prove:** on `device_proof_required` (then retry the request once);
  and proactively, in the background, after minting a session or registering a
  new FCM token while memory is in use — otherwise answers and coach tips go
  without memory until the parent opens a protected screen.
- The code lives **5 minutes**, works **once**, and only while the device's push
  token is still the one it was sent to.
- **Push-token cooldown.** When this device's push token is replaced by a
  session that had not proven the old one — a new phone, a reinstall, or
  someone else — every route that needs a proof answers
  `403 {"detail": {"code": "device_proof_cooldown", "message", "message_en",
  "support_email", "available_at": "2026-10-07T18:30:00Z"}}` for **72 hours**
  (`available_at` is UTC), even after this session proves. Show the message with
  the time; do not re-run the challenge. Switching memory **off** still works.
  `GET /api/device-proof` and the memory settings carry `cooldown_until`. The
  install that proved the old token can change it freely (`onTokenRefresh`):
  register the new token with the **same, proven session** and nothing pauses.
- **First token of an existing account.** When a device that already has history
  (a session or a child older than 72 hours) registers its **first** push token,
  account deletion (§10) and child deletion/progress reset answer the same
  `device_proof_cooldown` for 72 hours. Memory is not paused.
  `GET /api/device-proof` → `deletion_paused_until`. A brand-new install is not
  paused. Show the time, and point to the e-mail path on the deletion screen.
- **The previous phone is told.** It gets one notification (safety channel,
  at most one a day, 09:00–21:00 its time), Arabic and English, no account data:
  FCM `data` `{"type": "account_alert"}`. Tapping it just opens the app — the
  launch re-registers that phone's own token, which voids the newcomer's proof
  and is accepted at once if that phone had proven it.

| HTTP | `detail.code` | When — what the app does |
|---|---|---|
| 409 | `no_push_token` | no FCM token registered (or FCM called it dead) — register it, try again; else show the message (it names the support address) |
| 503 | `push_unavailable` | the server could not send — try again shortly; else show the message |
| 429 | `proof_rate_limited` | more than 5 starts per session (20 per device) in an hour |
| 409/404 | `proof_failed` | `detail.reason`: `wrong_code` · `expired` · `used` · `other_session` · `push_token_changed` · `not_found` — start again once |
| 403 (protected routes) | `device_proof_cooldown` | the push token changed without a proven session — wait until `available_at` |

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
→ 200 {"enabled": true, "collecting": false, "proven": false, "cooldown_until": null}

PUT /api/children/memory/settings
{"enabled": false}
→ 200 {"enabled": false, "collecting": false, "proven": false, "cooldown_until": null}
```
No proof is needed to read the settings or to switch memory **off**; switching
it **on** needs a proven session (§9.0). `proven` says whether this session may
open the memory screen now. If it is `false`: when `cooldown_until` is set, say
when the screen opens (§9.0.1, push-token cooldown); otherwise run §9.0.1 first.
- `enabled` — the parent's switch (default `true`). Off = nothing new is
  learned, no follow-up is opened, and remembered facts stop reaching the
  assistant. **Off deletes nothing** — deletion is §9.3/§9.6 — and **deleting
  keeps the switch as it was** (off stays off).
  **While off, nothing new goes into memory by any route** (since PR #36's
  review): the follow-up loop pauses — `followups/due` answers
  `{"followups": [], "memory_enabled": false}`, an answer is not kept (§9.4:
  `200`, `"remembered": false`, `"fact": null`, the follow-up stays `pending`)
  and no follow-up push is sent — and adding a fact is refused
  (`409 memory_off`, §9.3). Still open while off: reading memory, editing,
  confirming, rejecting and deleting facts, dismissing a follow-up, erasing
  (§9.3/§9.6). Switched back on, pending follow-ups that are still due come back.
  **Client:** while off, hide the Today follow-up card, show the follow-up
  sheet without its four answer buttons (say memory is paused, with a way to
  turn it on), and disable "add a fact" on the memory screen.
- `collecting` — `enabled` AND a memory build AND this session is proven (§9.0).

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
  "created_at": "2026-10-04T18:20:11Z",
  "updated_at": "2026-10-04T18:20:11Z"
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
| 422 | `sensitive` | something memory never keeps (medicine, self-harm, abuse, sexual, drugs) |
| 422 | `category` / `status` | value outside the enums above |
| 403 | `device_proof_required` | session not proven — run the device proof (§9.0.1), retry once |
| 422 | `empty_patch` | PATCH with no field |
| 409 | `memory_off` | POST (add) while the memory switch is off — nothing was stored; offer to turn memory on (§9.2). PATCH and DELETE never get it. |

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
  "due_at": "2026-10-08T18:20:11Z",
  "status": "pending",
  "outcome": null,
  "note": null,
  "created_at": "2026-10-04T18:20:11Z",
  "answered_at": null
}
```
`topic` ∈ `prayer`, `anger`, `sleep`, `study`, `screens`, `fear`, `siblings`,
`eating`, `lying`, `other`. `status` ∈ `pending` → `answered` | `dismissed` |
`expired` (21 days after `due_at` without an answer). `outcome` ∈ `worked`,
`partly`, `didnt_work`, `didnt_try`.

| Route | Returns |
|---|---|
| `GET /api/children/followups/due?limit=10&tz_offset_minutes=180` | `{"followups": [ … ], "memory_enabled": true}` — pending and due now, every child, oldest first (`limit` 1–20). Drive the Home card from this. While memory is off: `{"followups": [], "memory_enabled": false}` (§9.2). **Send `tz_offset_minutes`** (the device's UTC offset): the follow-up push only goes out during the family's daytime, and a device whose offset was never sent gets no push. |
| `GET /api/children/followups/{id}` | `{"followup": {…}, "memory_enabled": true}` in **any** status — what the deep link opens. `memory_enabled: false`: an answer would not be kept — show the strategy without the answer buttons. |
| `GET /api/children/{child_id}/followups?status=pending` | `{"child_id": 12, "followups": [ … ]}`; `status` ∈ `pending` (default), `answered`, `dismissed`, `expired`, `all`. |
| `POST /api/children/followups/{id}/answer` | body `{"outcome": "didnt_work", "note": "optional, ≤ 300 chars"}` → `{"followup": {…answered…}, "fact": {Fact}, "note_dropped": false, "remembered": true}` — `note_dropped: true` when the note was something memory never keeps (it was discarded; tell the parent gently). Answering the same strategy again updates the outcome fact (the latest result wins). **Memory off:** `200 {"followup": {…still pending…}, "fact": null, "note_dropped": false, "remembered": false}` — nothing was kept (no outcome, no note, no fact); say so («الذاكرة متوقفة، فلم نحفظ إجابتك») rather than the usual thank-you, which promises to remember. Treat a missing `remembered` (older server) as `true`. |
| `POST /api/children/followups/{id}/dismiss` | `{"followup": {…dismissed…}}` |

Answering stores the result as an `outcome` fact, e.g.
«جُرِّب مع طفلي: روتين نوم ثابت مع قصة قبل النوم — ولم ينجح.» — and from then
on the assistant is told not to repeat a strategy that did not work and to
offer an alternative instead. The note is shown back to the parent as typed
(except that a deleted sibling's name in it becomes «طفل آخر»); only its
name-free form reaches the fact.

Errors: `404 followup_not_found` · `409 followup_closed` (answer/dismiss on a
follow-up that is no longer pending — show "already answered") ·
`422` bad `outcome` or `note` too long.

Suggested copy: «هل جرّبت: {strategy}؟» / "Did you try: {strategy}?" with
four buttons — نجحت / Worked · نجحت جزئيًا / Partly · لم تنجح / Didn't work ·
لم أجرّب بعد / Haven't tried yet — plus an optional note field and «لا تسألني
عن هذا» / "Don't ask about this" (= dismiss).

**Push.** At **19:00 on the family's own clock** (from the last `tz_offset_minutes`
the app sent; unknown offset → no push), in every time zone and never at night.
A device gets at most one follow-up push per 7 days, never the same follow-up
twice, nothing older than 21 days past due, nothing if it already had any push
in the last 20 hours, and nothing if the parent switched memory off. Only devices
whose build is ≥ `CHILD_MEMORY_MIN_BUILD` receive it. The text is **generic** (no name, no strategy) and the notification is
**private** on the lock screen; the app shows the strategy once opened. FCM `data`
(all strings):
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
(optional — the device's UTC offset, e.g. `180` for Riyadh; the week is the
parent's local ISO week, Monday to Sunday). Send it when you can: it is recorded
for the follow-up push. When it is absent, the offset last sent (here or with
§9.4's `followups/due`) is used, and nothing is recorded — an omitted offset never
resets the family's clock to UTC.
This route does not require a proven session — but only a proven session (§9.0)
on a memory build, while the memory switch is on, gets a plan shaped by memory
(any other request gets the plan built from the chosen challenge and the
default topic order), and only a proven session's `tz_offset_minutes` is
recorded.

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
  "generated_at": "2026-10-05T06:12:40Z"
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

Forgets everything about **every** child of this device (facts, follow-ups and
weekly plans). The memory switch keeps its setting. Requires a proven session (§9.0).
```json
→ 200 {"deleted": {"child_facts": 12, "followups": 3, "weekly_plans": 4},
       "deleted_at": "2026-10-04T18:30:00Z"}
```

---

## 10. Account deletion — `DELETE /api/privacy/account?confirm=true`

Google Play requires an in-app way to delete the account and its data (the app
offers Google sign-in). This is that call. Wire it to Settings → «حذف الحساب» /
"Delete Account" (the `deleteAccount` ARB key exists) behind a confirmation
dialog that says it cannot be undone.

```http
DELETE /api/privacy/account?confirm=true
Authorization: Bearer <token>
→ 200
{
  "devices": 1,
  "signed_in": false,
  "deleted": {"api_tokens": 2, "chat_messages": 14, "chat_sessions": 3,
              "child_facts": 6, "child_profiles": 2, "lesson_progress": 9,
              "push_tokens": 1, "…": 0},
  "deleted_at": "2026-10-04T18:40:00Z"
}
```
- **Scope.** Signed out: this device. Signed in with Google **through a link a
  proven session made** (`POST /api/identity/link-google` from a session that
  passed §9.0.1): **every device linked to that account the same way**, plus the
  Google identity itself (e-mail, display name), its backups and every remaining
  link to it — a reinstall links a new device and copies the children over, so
  deleting one device alone would leave a full copy one sign-in away. A device
  linked by a session that had **not** proven is not included (until session
  minting is enforced, such a link is cheap to make for someone else's device),
  and through such a link of its own the caller deletes only itself. `devices`
  says how many devices were erased.
- **Google link from an unproven session:** it is recorded as unconfirmed, and
  it cannot replace a link a proven session made to a *different* account —
  `link-google` answers `{"ok": false, "error": "device_proof_required"}`; prove
  (§9.0.1) and link again.
- **What goes:** every row tied to those devices — children and everything
  under them (progress, streaks, routines and their events, habits, agreements
  and clauses, missions, licences, screen sessions, challenges, coach tips,
  memory, follow-ups, weekly plans), chat sessions and messages, ratings, app
  feedback and replies, push token and send log, referral code and referral
  links, backups, auth tokens. `deleted` lists non-zero counts per table.
- **One transaction:** a `5xx` means nothing was deleted — safe to retry. The
  bearer tokens go in the same transaction as the data, and so does a one-way
  hash (never the id) of every device id removed — see §3.2 `410 device_erased`.
- **The answer was lost** (timeout, app killed) — find out, don't guess:
  - **Authoritative, when `GET /api/app-config` → `erased_device_410_min_build`
    is not `null` and ≤ this build:** mint for the same `device_id` with
    `X-App-Build` (and the old token as `Authorization`, as always).
    `410 device_erased` → the deletion went through: do the post-`200` steps below.
    `201` → it did not: the account is intact (the old token works too); ask
    again before retrying the DELETE.
  - **Otherwise:** re-send the same `DELETE` with the same token. `200` → deleted
    now. `401` → already deleted (its token was deleted with the data) — treat as
    deleted. (A token lapses only after 180 idle days, so on a retry `401` means
    deleted.)
  - Re-sending a `DELETE` that went through never deletes anything new: there is
    nothing left under that token.
- **The token used for the call is revoked by it.** After `200`: sign out of
  Google in the app, wipe local storage (cached children, preferences, the
  stored `device_id`), generate a **new** `device_id`, and start over with
  `POST /api/chat/sessions`. Any further call with the old token gets `401`,
  and a mint for the old `device_id` gets `410 device_erased` (§3.2) — the same
  steps apply if a reinstall ever restores it from a phone backup.
- Errors: `401` no/invalid token · `400 {"detail": {"code": "confirm_required", …}}`
  when `confirm=true` is missing · `403 {"detail": {"code": "device_proof_required", …}}`
  for a session that has not proven it holds the phone (§9.0.1, then retry once) ·
  `403 {"detail": {"code": "device_proof_cooldown", "available_at": …}}` for 72 hours
  after a new push token (§9.0.1) — show when it becomes available.
  If the proof cannot work (no push token, the code never arrives), show the
  message with its support address — deletion by e-mail is the fallback.
- **Child-mode tokens are opaque.** Since this change they no longer contain the
  parent's device id; never decode them on the client (old ones keep working until
  they expire).
- Not affected: aggregate telemetry that carries no device identifier and so
  cannot be linked back to the account.
- **Public pages (no auth):** the privacy policy stays at
  `https://tg-api.alsaba.cloud/privacy-policy` (Arabic + English; the Settings
  "About" row already opens it), and `https://tg-api.alsaba.cloud/delete-account`
  explains deletion for people without the app — that is the URL for the Play
  Console "Delete account URL" field. A confirmation dialog may link to it too.

---

## 11. Family programs — Ramadan, the Prayer Journey, milestones (backend schema v34)

Three content-driven programs (content: `knowledge_base/curriculum/programs/`,
documented in `knowledge_base/curriculum/schema.md` §8). The server picks the
right piece for a child on a day; **every string you render comes from the
response** (Arabic by default, English with `lang=en`). All of this is
additive: builds that never call these endpoints are unaffected.

### 11.0 Rules for every call

| Rule | What the client does |
|---|---|
| Auth | Parent endpoints: `Authorization: Bearer <token>`. The two child-mode endpoints (§11.4.6): `Authorization: Child-Bearer <token>` with a live screen session, like every `/api/value-tracking/child-mode/*` route. |
| `tz_offset_minutes` | **Send it on every call**: minutes east of UTC right now (`DateTime.now().timeZoneOffset.inMinutes`; Cairo winter = `120`, New York = `-300`). Range −720…840, else `422`. It decides the family's date (the Ramadan day turns at *their* midnight) and the server remembers it — the milestone push (§11.5.3) is sent at the family's 20:00 and is **never sent to a device that never reported one**. Omitted → the date is UTC for that response and nothing is stored. |
| `lang` | `en` for English; omit (or anything else) for Arabic. Remembered for the push language. Untranslated content falls back to Arabic. |
| `as_of=YYYY-MM-DD` | QA only. `403 {"error":"as_of_disabled"}` unless the server sets `PROGRAMS_AS_OF_ENABLED=1`. Never send it from the shipped app. |
| Errors | `{"detail": {"error": "<code>", ...extra}}` — codes in §11.6. `404 {"error":"child_not_found"}` for a child of another device. `503 {"error":"program_unavailable"}` if a program file is unpublished. |
| Hadith | Only in `evidence[]` cards: `{id, kind:"hadith", text_ar, source, provenance:{book, number}, context, meaning?}`. Render `text_ar` + `source`; in English also `meaning` under a label "Meaning". Never quote a hadith anywhere else. |
| Quran | References only: `{surah, from, to, topic?}`. Render the verse text from `mobile/assets/data/quran.json`. Never translate it; English shows the Arabic verse (+ a tafsir only if labelled as tafsir). |
| Never a shame metric | Show progress as counts that only go up ("3 this week"), never as misses or deficits. Going back a Prayer Journey stage is silent to the child. A fasting day not practised is not recorded at all. |

### 11.1 Birth month on child profiles

Optional `birth_month` (`"YYYY-MM"`) on `POST /api/children`, `PATCH /api/children/{id}`,
and in every child object returned (`GET /api/children`, the POST/PATCH responses).
Up to 10 months ahead (an expected baby) and up to 19 years back, else `422`.

```json
POST /api/children
{"name": "أحمد", "age_group": "7-9", "gender": "male", "birth_month": "2019-03"}
→ 201
{"id": 12, "name": "أحمد", "age_group": "7-9", "gender": "male", "avatar_emoji": null,
 "birth_month": "2019-03", "created_at": "2026-10-04 17:12:13", "updated_at": "2026-10-04 17:12:13"}
```

```json
PATCH /api/children/12   {"birth_month": "2019-04"}   → the child object
PATCH /api/children/12   {"birth_month": null}        → clears it (an explicit null counts as a change)
PATCH /api/children/12   {"name": "عمر"}               → birth_month untouched
```

What it changes: programs use the **age from the birth month** when known,
otherwise the profile's `age_group` (every program response has
`"age": {"basis": "birth_month"|"age_group", "band": "7-9", "months": 95|null, "years": 7|null}`).
Without it there is **no milestone push** (the cards still appear by band), so
ask for it — `needs_profile` in §11.5.1 tells you when. Deleting the child
deletes it, and every program row about that child (§11.7).

### 11.2 `GET /api/programs` — what applies to each child today

One call for the Today screen. Query: `tz_offset_minutes`, `lang`.

```json
{
  "date": "2027-02-10",
  "tz_offset_minutes": 180,
  "server_features": ["weekly_plan"],
  "unavailable": [],
  "ramadan": {
    "state": "ramadan",                       // upcoming | ramadan | eid | after | off_season
    "season": {"hijri_year": 1448, "starts_on": "2027-02-08", "days": 30, "eid_on": "2027-03-10",
               "bridge_ends_on": "2027-04-07", "start_source": "estimate",
               "days_confirmed": false, "shift_days": 0},
    "day": 3, "days_until_start": null, "after_week": null, "recap_available": false
  },
  "children": [
    {"child_id": 12,
     "age": {"basis": "birth_month", "band": "7-9", "months": 95, "years": 7},
     "ramadan": {"variant_band": "7-9"},
     "prayer_journey": {"eligible_track": "journey", "enrolled": true, "track": "journey", "stage": 1,
                        "advance_suggested": true, "can_graduate": false, "pending_confirmations": 0},
     "milestones": {"due": 1, "needs_profile": []}}
  ]
}
```

`season` is `null` when the server knows no Ramadan. `prayer_journey.eligible_track: null`
= the Journey is not for this child (under 4, over 15, or an unknown band) — hide it.

**Each program stands alone** (contract change, PR #32 review): if one program's file cannot be
read, its name is in `unavailable` (`"ramadan_family"`, `"prayer_journey"`, `"milestones"`) and
its sections are `null` — top-level `ramadan`, and each child's `ramadan` / `prayer_journey` /
`milestones` — while the other programs are served as usual. Hide a `null` section; never treat
it as an error. (The program's own endpoints answer `503 program_unavailable` meanwhile.)

### 11.3 «رمضان العائلة» — Ramadan

#### 11.3.1 The calendar

`state` for the family's date:

| state | when | payload filled |
|---|---|---|
| `upcoming` | before the first day (`days_until_start`) | `kickoff`, `fasting` |
| `ramadan` | day 1…`season.days` (`day`) | `content`, `marks`, `fasting` |
| `eid` | the day after the last day | `eid`, `fasting`; the recap card opens |
| `after` | four «bridge» weeks after Eid (`after_week` 1–4) | `after`, `fasting` |
| `off_season` | after the bridge, no next season known | — |

The first day is announced by moon sighting, so the server reads it from its
configuration (`season.start_source: "configured"`) and uses the content's
estimate (`"estimate"`: 2027-02-08 for 1448, **2028-01-28 for 1449**) until then. After 1448's
bridge (from 2027-04-08) the state is `upcoming` for **1449** — a countdown, not `off_season`
(`off_season` only after the last season the content knows). The month is 30 days
until the server confirms 29 (`days_confirmed`); day 30 is the content's
`may_not_occur` farewell. A family whose country sighted the moon a day
earlier/later, or whose month had 29 days, fixes it for itself with
`PUT /api/programs/ramadan/settings` (§11.3.6) — offer that in the program's
settings, and on day 29's evening ("Is tomorrow Eid?").

The night precedes its day: night 21 is the **evening of day 20**, so the
nights of the last ten are `odd_night: true` on days 20, 22, 24, 26, 28 and
`night_joined` is ticked on days 20–28.

#### 11.3.2 `GET /api/children/{child_id}/ramadan/today`

Query: `tz_offset_minutes`, `lang`, `features` (comma list of what this build
can show — send `weekly_plan` only if this build has the weekly-plan screen,
see «requires_feature» below).

```json
{
  "program": "ramadan_family", "child_id": 12, "date": "2027-02-10", "tz_offset_minutes": 180,
  "state": "ramadan",
  "season": {"hijri_year": 1448, "starts_on": "2027-02-08", "days": 30, "eid_on": "2027-03-10",
             "bridge_ends_on": "2027-04-07", "start_source": "estimate", "days_confirmed": false,
             "shift_days": 0},
  "title": "Family Ramadan", "subtitle": "Thirty days of worship and joy, together",
  "age": {"basis": "birth_month", "band": "7-9", "months": 95, "years": 7},
  "variant_band": "7-9",
  "bands_text": "The program is for the whole family: … (who sees what — show it to the parent)",
  "days_until_start": null, "day": 3, "after_week": null,
  "kickoff": null,
  "content": {
    "day": 3, "phase": "first_ten", "key": "iftar_table", "title": "The iftar table",
    "family_challenge": {"title": "Set the table together and begin with Bismillah",
                         "steps": ["Hand out small jobs before the adhan: …", "…"],
                         "minutes": 10, "cost": "free", "at_home": true, "when": "at_iftar",
                         "materials": []},
    "parent_note": {"text": "In the attached hadith …", "evidence": [{"id": "h_bismillah", "kind": "hadith",
                    "text_ar": "يا غلام سم الله وكل بيمينك وكل مما يليك", "source": "صحيح البخاري — حديث ٥٣٧٦",
                    "provenance": {"book": "البخاري", "number": 5376}, "context": "…", "meaning": "…"}]},
    "variant": {"band": "7-9", "addressed_to": "child", "text": "Your job: water and cups on the table …"},
    "quran": {"together": {"surah": 114, "from": 1, "to": 6}, "theme_ref": null, "parent_juz": 3},
    "story_id": "abdullah_bismillah",
    "last_ten": false, "odd_night": false, "may_not_occur": false,
    "tracks": ["challenge_done", "wird_done", "story_heard", "juz_read"],
    "family_word_choices": null
  },
  "eid": null, "after": null,
  "marks": {"challenge_done": false, "wird_done": false, "story_heard": false, "juz_read": false},
  "fasting": {"ladder_band": "7-9", "fasts": "partial", "reached_puberty": false,
              "current_step": {"key": "morning_hours", "label": "Morning hours", "until": "mid_morning",
                               "approx_hours": 3, "max_days_per_week": 3},
              "practised_today": false, "practised_this_week": 0, "rest_suggested": false},
  "recap_available": false
}
```

* **Who sees which variant** (`variant_band`, from the content's `band_map`):
  `0-3`/`2-3` → `0-3`; `4-6`; `7-9`; `10-12`; `13-15`/`16-18` → `13-15`;
  `prenatal-1` and unknown → `null` (the family challenge and its note only —
  `content.variant` is `null` and `fasting` is `null`). `addressed_to: "parent"`
  for 0-3 and 4-6 (the child does not read); `"child"` from 7-9 up (fit for child mode).
* **`story_id`** points into the app's bundled `stories.json` / `stories_en.json`; `null` = no story today.
* **`marks`** has one boolean per entry of `content.tracks` (the day card's «تمّ» toggles), plus
  `family_word: {"choice_index": 3, "word": "Joy"} | null` on day 28. Marks are the **family's**: the
  same on every child's card.
* `upcoming` → `"kickoff": {"title", "text", "setup_steps": [...]}` (and let the parent set each
  child's fasting step now).
* `eid` → `"eid": {"title", "activities": [...], "parent_note": {text, evidence}, "variant": {...}|null,
  "quran": {...}, "evidence": [...]}`.
* `after` →
  ```json
  "after": {"title": "After Ramadan: keep going together", "text": "…",
            "keep_habits": [{"key": "weekly_quran_circle", "title": "…", "text": "…"}, …],
            "week": {"week": 4, "title": "Week 4: Beyond the bridge", "text": "…",
                     "requires_feature": "weekly_plan", "feature_available": false},
            "weeks": [ …all four, resolved the same way… ],
            "links": {"program_ids": ["prayer_journey"], "path_ids": [...], "lesson_ids": [...]},
            "evidence": [...]}
  ```
  **«requires_feature»:** a week that promises a feature carries `requires_feature` and
  `feature_available`. Its `text` is already resolved: the promise when the server serves the
  feature **and** this request listed it in `features`, the content's fallback otherwise. Render
  `text` as is.

#### 11.3.3 `GET /api/children/{child_id}/ramadan/days/{day}` — any day 1–30

For "tomorrow's challenge needs paper" and "I forgot to tick yesterday". Query as above.

```json
{"child_id": 12, "date": "2027-02-10", "state": "ramadan", "season": {…}, "variant_band": "7-9",
 "content": { …same shape as today's `content`… },
 "markable": true,
 "marks": {"challenge_done": true, "wird_done": false, "juz_read": false}}
```
`markable` is true for days up to today during the month, and for the whole month from Eid to the
end of the bridge; `marks` is `null` when not markable. `404 {"error":"no_such_day"}` outside 1–30.

#### 11.3.4 `POST /api/programs/ramadan/marks` — tick / untick a family «تمّ»

Query: `tz_offset_minutes`. Body:
```json
{"mark": "challenge_done", "day": 3, "done": true}
{"mark": "family_word", "day": 28, "choice_index": 3}
```
* `mark` ∈ `challenge_done`, `wird_done`, `story_heard`, `juz_read`, `night_joined`, `family_word`
  — and only the ones in that day's `tracks` (`422 mark_not_on_this_day`).
* `day` defaults to today during the month; required from Eid on (`422 day_required`); never a
  future day (`422 day_not_markable` with `markable_up_to`). Outside the month and its bridge:
  `409 not_in_season`.
* `done: false` removes the mark. Idempotent both ways.
* `family_word` (day 28 only): `choice_index` into that day's `content.family_word_choices`
  (8 words, in the reader's language; `null` on other days). The chosen word comes back in
  `marks.family_word.word`. Never free text.

Response: `{"hijri_year": 1448, "day": 3, "marks": { …the day's marks after the change… }}`.

#### 11.3.5 The fasting ladder

`GET /api/children/{child_id}/ramadan/fasting` — the ladder screen:
```json
{"child_id": 12, "date": "2027-02-10", "state": "ramadan", "season": {…}, "day": 3,
 "age": {…},
 "ladder_band": "7-9", "fasts": "partial", "summary": "Hours, not full days. …",
 "reached_puberty": false,
 "current_step": null,
 "steps": [
   {"key": "morning_hours", "label": "Morning hours", "until": "mid_morning", "approx_hours": 3,
    "min_age_years": 7, "max_days_per_week": 3, "advance_when": "…", "text": "…", "eligible": true},
   {"key": "until_dhuhr", …, "min_age_years": 7, "eligible": true},
   {"key": "until_asr", …, "min_age_years": 9, "eligible": false}],
 "practised_today": false, "practised_this_week": 0, "rest_suggested": false,
 "guidance": {"title": "The fasting ladder", "principles": [...], "doctor_first": [...],
              "stop_signs": [...], "stop_action": "…", "urgent_signs": [...],
              "urgent_action": "…", "tips": [...], "evidence": [...]}}
```
* `fasts`: `no` (0-3, 4-6 — no fasting before seven), `partial` (7-9), `partial_to_full` (10-12),
  `full_supported` (13-15). `eligible:false` = the child's known age is below `min_age_years`
  (unknown age: all `true`; show `min_age_years` beside each step).
* **Always show `guidance`** on this screen — stop signs, the urgent signs and what to do.
* `rest_suggested: true` = the step's own weekly cap is reached ("tomorrow is a rest day") — a
  care message, never a score.

`PUT /api/children/{child_id}/ramadan/fasting` — body `{"step_key": "until_dhuhr"}` and/or
`{"reached_puberty": true}`. Response = the ladder (without `guidance`) plus `"climbed": true|false`.
* `reached_puberty: true` moves the child to the 13-15 ladder whatever the band (puberty, not age,
  makes fasting obligatory — content §8.2); settable any time; also retires the
  "before puberty" milestone cards. Offer it as a quiet profile toggle on the ladder screen.
* All-or-nothing: the step is checked against the ladder the **new** `reached_puberty` value
  implies, and a refused request writes nothing (neither the step nor the flag).
* `422 unknown_step` (not on this child's ladder), `422 step_not_for_age` (`min_age_years`),
  `409 not_in_season` (a step outside a season), `422 nothing_to_change` (empty body).
* A move to a step with more hours **during the month** is a "climb" — counted, privately, in the
  recap's `family_only`. A step down is not recorded anywhere.

`POST /api/children/{child_id}/ramadan/fasting/practice` — body `{}` (today), `{"day": 2}`,
`{"done": false}` (undo). "Practised their step today." Needs a step (`409 no_step_set`).
Response: `{"child_id", "day", "done", "current_step", "practised_today", "practised_this_week",
"rest_suggested"}`.

#### 11.3.6 `PUT /api/programs/ramadan/settings` — the family's own sighting

Body (either or both): `{"start_shift_days": -1|0|1}`, `{"month_days": 29|30|null}` (`null` = back to
the server's). Applies to the current/next season only. Response:
`{"state", "season", "day"}` recomputed. `409 not_in_season` off season; `422 nothing_to_change`.

#### 11.3.7 `GET /api/programs/ramadan/recap` — «رمضان عائلتنا»

Query: `lang`, `tz_offset_minutes`, `hijri_year` (default: the latest season that has started).

```json
{"hijri_year": 1448, "available": true, "available_on": "2027-03-10", "show_on": "eid",
 "card": {
   "title": "Our Family's Ramadan",
   "headline": "Our Family's Ramadan 1448",
   "lines": [{"keys": ["challenges_done"], "text": "Family challenges: 12"},
             {"keys": ["family_word"], "text": "Our Ramadan word: Joy"}],
   "metrics": [{"key": "challenges_done", "label": "Family challenges", "value": 12},
               {"key": "family_word", "label": "Our Ramadan word", "value": "Joy"}],
   "closing": "May Allah accept from us and from you",
   "share_text": "This was our family's Ramadan with the Almorabbi app. … https://play.google.com/store/apps/details?id=com.alsaba.almorabbi&referrer=ref_QXV6SC%26utm_source%3Dramadan-card…"},
 "progress": [{"key": "challenges_done", "label": "Family challenges", "value": 12, "max": 30}, …],
 "family_only": [{"key": "fasting_steps", "label": "Fasting steps our children climbed", "value": 2}],
 "privacy": "The card carries no children's names, ages, photos or anything anyone has typed: …"}
```
* `card` is `null` before Eid (`available: false`); `progress` is there all month (in-app counters).
* **Render the shareable image from `card` only** (`headline`, `lines[].text`, `closing`); Arabic
  numbers already come as ١٢. A line below the content's `min_to_show` is already dropped — do
  not re-add it. Share with `share_text` (it carries the family's invite link, so installs are
  credited to them).
* **`family_only` never goes on the card or into the share** — the children's fasting is the
  family's business. Show it inside the app only.

### 11.4 «رحلة الصلاة» — the Prayer Journey

#### 11.4.1 Tracks

| track | who | what |
|---|---|---|
| `preparation` | age 4–6 (band `4-6`) | activities only — no tasks, no coins, no daily follow-up |
| `journey` | age 7–10 (band `7-9`) | 6 stages over 12 weeks; child tasks with coins |
| `ownership` | age 11–15 (bands `10-12`, `13-15`), and after graduating | «صلاتي مسؤوليتي»: the child records his own prayers |

By age when the birth month is known, else by band. Under 4, over 15, `2-3`, `16-18`,
`prenatal-1`: not shown (`eligible_track: null`). An `ownership`-eligible child who does not pray
regularly yet may take the `journey` instead, from any stage (`allowed_tracks`).

#### 11.4.2 `GET /api/children/{child_id}/prayer-journey`

```json
{"child_id": 12, "date": "2026-10-04", "age": {…},
 "title": "The Prayer Journey", "subtitle": "Twelve weeks from love to responsibility",
 "eligible_track": "journey", "allowed_tracks": ["journey"], "bands_text": "…",
 "enrolment": {"track": "journey", "stage": 1, "status": "active", "started_on": "2026-10-04",
               "stage_started_on": "2026-10-04", "week": 1},
 "basis": {"text": "…", "evidence": [...]}, "principles": ["…"],
 "reward_policy": {"text": "Coins here encourage the effort of learning; …", "daily_cap": 60},
 "stages": [{"stage": 1, "key": "love_and_presence", "title": "…", "goal": "…", "week_from": 1, "week_to": 2}, …6],
 "graduation": {"title": "…", "text": "…", "certificate_text": "…",
                "covenant": {"coins_target": 300, "examples": ["…"]},
                "journey_milestone_keys": ["keeps_prayer"], "evidence": [...]},
 "graduated_on": null,
 "stage": {"stage": 1, "key": "love_and_presence", "title": "…", "goal": "…", "week_from": 1, "week_to": 2,
           "parent_assignments": [{"key": "pray_where_seen", "text": "…"}, …],
           "confirmation": {"how": "…", "counts_when": "…"},
           "encouragement": ["I saw you stand beside me so calmly. Well done!", …],
           "if_struggling": "…", "covenant": {"coins_target": 100, "examples": ["…"]},
           "lesson_ids": ["lesson_7-9_islamic_parenting_worship_01"], "quran": [], "evidence": [...],
           "journey_milestone_key": null},
 "preparation": null, "ownership": null,
 "tasks": [{"task_id": "prayer_s1_pray_beside", "title": "I pray beside Mum or Dad", "instruction": "…",
            "estimated_minutes": 7, "needs_parent": true, "materials": [], "skill": "Following an example",
            "coins": 10, "per_week": 5, "per_day": 1, "week_limit": 5,
            "today": {"recorded": 0, "confirmed": 0, "slots_left": 1},
            "this_week": {"recorded": 0, "confirmed": 0}}, …],
 "advancement": {"days_in_stage": 0, "stage_planned_days": 14, "next_stage": 2,
                 "advance_suggested": false, "advance_suggested_on": "2026-10-18",
                 "can_graduate": false, "graduation_available_on": null},
 "pending_confirmations": 0,
 "coins": {"confirmed_in_stage": 0, "covenant_target": 100}}
```
* Not enrolled: `enrolment`, `stage`, `advancement`, `coins` are `null`, `tasks` is `[]`;
  `preparation` / `ownership` carry their track's content for the eligible track.
* `stage.journey_milestone_key` (e.g. `first_prayer` at stage 3) and `graduation.journey_milestone_keys`
  are keys of the app's journey log (`mobile/assets/content/journey/milestones.*.json`) — suggest
  recording them.
* **Parent-only texts**: `stage.*` except `encouragement` (sentences the parent says to the child),
  `graduation.text`, `if_struggling`. Never show them in child mode.

#### 11.4.3 `POST /api/children/{child_id}/prayer-journey/enrol`

Body: `{}` (the eligible track, stage 1), or `{"track": "journey", "start_stage": 3}`, or
`{"restart": true, …}` to replace an active enrolment. Response = §11.4.2.
Errors: `409 not_eligible`, `409 track_not_for_age` (`allowed_tracks`), `409 already_enrolled`
(`track`, `stage`), `422 unknown_stage`, `422 stage_only_for_journey`.

#### 11.4.4 `PUT /api/children/{child_id}/prayer-journey/stage` — `{"stage": n}`

Forward **one** stage at a time (`409 one_stage_at_a_time` with `next_stage`), back to **any**
earlier stage. Moving on is the parent's call: suggest it when `advancement.advance_suggested`
(the stage's weeks are up) — never gate it on the week's counts (`per_week` is a goal, not a
condition). Going back is silent to the child: child mode shows only today's tasks. Response = §11.4.2.
`409 not_in_journey` for a child not on the journey track. `409 stage_changed`: the stage moved
since this screen read it (a double tap on "next stage" moves it once) — refetch §11.4.2.

#### 11.4.5 `POST /api/children/{child_id}/prayer-journey/graduate` · `DELETE /api/children/{child_id}/prayer-journey`

Graduate from stage 6 once its two weeks are done (`advancement.can_graduate`; else
`409 graduation_not_yet` with `available_on`). The journey closes and the `ownership` track opens;
show `graduation` (certificate text, the big covenant). A second tap answers
`409 already_graduated` (never a 500) — refetch §11.4.2. `DELETE` stops the journey
(`409 not_enrolled` if none). Both return §11.4.2.

#### 11.4.6 Child mode — the child's tasks

`GET /api/value-tracking/child-mode/prayer/today?tz_offset_minutes=180&lang=en` (Child-Bearer):
```json
{"date": "2026-10-04", "available": true, "enrolled": true, "track": "journey",
 "tasks": [{"task_id": "prayer_s1_pray_beside", "title": "I pray beside Mum or Dad",
            "instruction": "Stand beside your dad or mum in one prayer today …",
            "estimated_minutes": 7, "needs_parent": true, "materials": [], "skill": "Following an example",
            "coins": 10, "per_day": 1, "week_limit": 5,
            "recorded_today": 0, "slots_left_today": 1, "recorded_this_week": 0}, …]}
```
`enrolled: false` (no tasks: not enrolled, or the preparation track) → show nothing.
`available: false` (new): the program file cannot be read right now — `enrolled` is `false`,
`tasks` is `[]`; show nothing, it is not an error. (The claim answers `503 program_unavailable`.)

`POST /api/value-tracking/child-mode/prayer/claim?task_id=prayer_s1_pray_beside&tz_offset_minutes=180`
→ «صلّيتها». Recorded at once; the child does not wait for anyone:
```json
{"ok": true, "status": "claimed", "mission_id": 41, "task_id": "prayer_s1_pray_beside",
 "slot": 1, "recorded_today": 1, "slots_left_today": 0}
```
A task has `per_day` slots a day (two prayers a day → 2); a "N times a week" task
(`week_limit`) is complete for the week after N. When `slots_left_today` is 0, show it as done
(✓), not as an error. Errors: `409 day_complete`, `409 week_complete`, `409 task_not_current`
(the stage changed — refetch), `409 not_enrolled`, `503 program_unavailable`. A double tap is
recorded once: the cap check and the insert are one transaction, so the second tap gets
`day_complete` / `week_complete` (`409 already_recorded` remains only as a last guard). Treat all
of them as "done" on the child's screen.

#### 11.4.7 The parent's evening — the existing mission flow

The claim is a `child_missions` row, so it appears in the **existing**
`GET /api/children/missions/pending` and the 21:00 digest push (`link: "/missions"`), and is
settled by the existing `POST /api/children/missions/confirm`. Additive fields on a prayer card in
`pending`:
```json
{"mission_id": 41, "mission_key": "prayer_s1_pray_beside#1", "status": "claimed", "local_date": "2026-10-04",
 "title_ar": "I pray beside Mum or Dad", "instruction_ar": "…", "estimated_minutes": 7,
 "needs_parent": true, "needs_outdoors": false, "materials": [], "skill": "…",
 "program": "prayer_journey", "task_id": "prayer_s1_pray_beside", "slot": 1, "coins": 10,
 "child_id": 12, "child_name": "أحمد"}
```
(`title_ar` / `instruction_ar` carry the text in the requested `lang`, as for bank missions.)
Additive fields on the confirm response:
```json
{"ok": true, "settled": 2,
 "coins": [{"mission_id": 41, "child_id": 12, "task_id": "prayer_s1_pray_beside", "coins": 10}],
 "deferred": []}
```
* **Batch size: up to 200 items** (was 50; `422` above). Send the whole evening list in one call.
* **`coins` is idempotent** (contract change): it lists every prayer mission **in this request**
  that is confirmed — including ones an earlier attempt already confirmed. So a retried request
  (the first response was lost) reports the same entries again, and `settled` counts only rows
  changed by *this* request. **The client credits each `mission_id` exactly once**: keep the set of
  credited `mission_id`s on the device and skip an entry already in it. Credit them to the
  family's coins on the device (`CoinsService` — one wallet for the family). Parent-confirmed
  program coins are **exempt from the app's daily earning cap** (60, which exists so games cannot
  mint coins): the content and the server already bound them per child per day. Show the family
  the coins actually credited. Persist the batch before sending it, and resend it on the next
  open if its answer never arrived — the retry reports the same `coins`.
* A card confirmed `false` ("not yet") earns nothing (never, also on retry), costs nothing, and
  frees its slot. Unanswered cards expire quietly after 48 h.
* `deferred` (new): prayer cards the server would not settle because the program file cannot be
  read right now (settling them would pay 0). They stay pending and are **hidden** from `pending`
  meanwhile; they come back, payable, when the file does. Do nothing special — just don't count
  them as confirmed.
* The stage's `coins.confirmed_in_stage` / `covenant_target` (§11.4.2) feed the covenant progress.

The bank card's own claim endpoint (`POST /api/value-tracking/child-mode/mission/claim`) now
claims bank cards only, and refuses an expired one: `409 expired`; a prayer `mission_id` there is
`409 mission_not_found` (prayer tasks are claimed only through §11.4.6).

### 11.5 Proactive milestones

#### 11.5.1 `GET /api/children/{child_id}/milestones`

```json
{"child_id": 12, "date": "2027-02-10", "age": {…},
 "alert_policy": {"text": "At most one notification per child per month; …", "pushes": true},
 "needs_profile": [],
 "due": [{"key": "first_fasting", "order": 4, "state": "due", "basis": "birth_month",
          "due_on": "2027-02-08", "alert_on": "2027-01-09",
          "season": {"name": "ramadan", "hijri_year": 1448, "starts_on": "2027-02-08", "start_source": "estimate"},
          "title": "First fasting attempts", "medical": true,
          "alert": {"title": "Ramadan is a month away", "body": "…"},
          "cards": [{"title": "Training, not obligation", "body": "…"}, …3-5],
          "red_flags": ["Fainting, confusion or a seizure → emergency services at once; …", …],
          "quran": [], "evidence": [...],
          "links": {"program_ids": ["ramadan_family"], "path_ids": [...], "lesson_ids": [...],
                    "story_ids": [], "features": []},
          "pushed_at": null}],
 "upcoming": [ …same shape, state "upcoming", within the next 12 months… ],
 "library": [ …state "library": no birth month, shown by band, due_on/alert_on null… ],
 "past": [ …state "past", due in the last 12 months… ]}
```
* `due`: from `alert_on` (the 1st of the month before; 30 days before a season) until 90 days after `due_on`.
* `needs_profile`: `"birth_month"` (no timing and no push without it), `"gender"` (a
  gender-specific card — puberty — is withheld until the profile says the gender). Show
  "complete the profile" instead of those cards.
* `medical: true` cards carry `red_flags` — render them visibly.
* `links.features` ⊂ `agreement`, `license`, `missions`, `covenant`, `screen_off`, `assistant`:
  existing app screens to link to. All texts are **for the parent**; never in child mode.

#### 11.5.2 `GET /api/children/{child_id}/milestones/{key}` — one card (the push's deep link)

`{"child_id": 12, "date": "…", "milestone": { …one card as above… }}`;
`404 {"error":"milestone_not_found"}` when it is not this child's (other gender, unknown key) —
then open the list.

#### 11.5.3 The push

Sent by the backend about a month ahead, **only** when: the child has a birth month; the
device's build ≥ `MILESTONES_MIN_BUILD` (server setting — **unset = no push to anyone**); the
device has a push token and has reported `tz_offset_minutes`; it is 20:00–20:59 on the family's
clock; no push of any kind in the last 20 h; at most one milestone push per device per week and
one per child per month (the most important first). A mission waiting on the parent does **not**
hold it back (contract change): the 21:00 digest ignores milestone pushes in its own
once-a-day cap, so on such an evening the parent gets both — the milestone at 20:00 and
`/missions` at 21:00. Payload (Android channel `almorabbi_reengagement`, private on
the lock screen):
```json
{"notification": {"title": "Turning seven next month", "body": "At seven, teaching prayer begins, …"},
 "data": {"type": "milestone", "kind": "milestone", "link": "/milestones/12/prayer_start",
          "child_id": "12", "milestone_key": "prayer_start"}}
```
**Deep link the client must add:** `/milestones/{child_id}/{milestone_key}` → open
§11.5.2 for that child (fall back to the list on 404). Report taps as `push_tapped(type=milestone)`.
Tell the orchestrator the first build number that routes it, so the server floor can be set.

### 11.6 Error codes

| code | HTTP | meaning |
|---|---|---|
| `child_not_found` | 404 | not this device's child |
| `program_unavailable` | 503 | program file unpublished/unreadable |
| `as_of_disabled` | 403 | `as_of` sent to a server that does not allow it |
| `invalid_date_or_offset` | 422 | bad `tz_offset_minutes` or `as_of` |
| `not_in_season` | 409 | no current/next Ramadan, or after the bridge |
| `day_required` / `day_not_markable` | 422 | `day` missing from Eid on / a future or out-of-range day |
| `mark_not_on_this_day` / `unknown_mark` / `choice_index_required` | 422 | see §11.3.4 |
| `unknown_step` / `step_not_for_age` / `no_step_set` / `nothing_to_change` | 422/422/409/422 | see §11.3.5 |
| `no_such_day` / `no_season` / `milestone_not_found` | 404 | |
| `not_eligible` / `track_not_for_age` / `already_enrolled` | 409 | see §11.4.3 |
| `unknown_stage` / `stage_only_for_journey` | 422 | |
| `one_stage_at_a_time` / `not_in_journey` / `graduation_not_yet` / `not_enrolled` | 409 | |
| `stage_changed` / `already_graduated` | 409 | a stale screen or a double tap — refetch (§11.4.4, §11.4.5) |
| `day_complete` / `week_complete` / `task_not_current` / `already_recorded` | 409 | child mode, §11.4.6 |
| `expired` / `mission_not_found` | 409 | the bank card claim endpoint, §11.4.7 |

### 11.7 Privacy and deletion

Server-side rows: the birth month (on the child profile); the family's Ramadan marks and
sighting settings; each child's fasting step, "reached puberty" flag and practice ticks; Prayer
Journey enrolment and its tasks (as `child_missions` rows); the milestone push log; the device's
last offset and language. Deleting a child (`DELETE /api/children/{id}`) from a session proven
to hold the phone (§9.0.1) deletes all of that child's rows — profile with its birth month,
fasting step, puberty flag, journey and its prayer cards, milestone log; from any other session it
deletes the profile row only (which carries the birth month), as that route always did. The
family's own Ramadan marks stay when one child is deleted. Account deletion (§10) reaches all of
it: every table carries `device_id`. All of it is disclosed in the privacy policy ("Family
programs"). The recap card never carries names, ages, photos or typed text.

### 11.8 Server settings (ops, not the client)

| env | default | effect |
|---|---|---|
| `RAMADAN_START_<hijri year>` (e.g. `RAMADAN_START_1448=2027-02-08`) | content estimate | the announced first day |
| `RAMADAN_DAYS_<hijri year>` | 30 (unconfirmed) | `29` or `30` once announced |
| `MILESTONES_MIN_BUILD` | unset = no milestone push | first build that routes `/milestones/…` |
| `PROGRAMS_AS_OF_ENABLED` | off | lets QA pass `as_of` |
