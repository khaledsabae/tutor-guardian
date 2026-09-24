# Tutor Guardian: Architecture & Security Audit and Improvement Roadmap

**Date:** 2026-09-24
**Scope:**
- FastAPI backend (`backend/app`): 21k LOC, 25 routers, 30+ services.
- Local LLM and RAG pipeline: Ollama/DeepSeek gateway, ChromaDB + BM25 + cross-encoder.
- SQLite persistence: `conversations.db` and `sessions.db`.
- Classification and guardrails: intent guard, fiqh guard, domain classifier, policies YAML.
- Flutter client (`mobile/lib`): 58k LOC.
- The public web surfaces and the CI/CD workflows.

The mobile UI/UX audit lives in its own document, **[UX_UI_ROADMAP.md](UX_UI_ROADMAP.md)** (summary in §7).

**Method:**
- Read the code paths end to end (request → middleware → router → services → DB/LLM).
- Reproduced suspected defects in isolation: in-memory SQLite, and pure-function probes of the guards.
- Pinned every fix with a regression test.
- Baselines taken before any change:
  - backend `pytest`, run on a clean worktree of `HEAD`;
  - `flutter analyze`: no issues;
  - `flutter test`: 498 tests passing.

Severity scale:

| Level | Meaning |
|---|---|
| **Critical** | Child-safety or security failure that can happen in normal use, or that exposes production. |
| **High** | Security or data-integrity defect, or a production feature that is broken. |
| **Medium** | Degrades correctness, privacy, performance or UX under realistic conditions. |
| **Low** | Hygiene, deprecations, latent defects. |

Status: ✅ **fixed in this PR** · 📋 **roadmap** (needs an owner decision, production access or a larger change).

---

## 1. Summary

| Severity | Found | Fixed here | Roadmap |
|---|---:|---:|---:|
| Critical | 3 | 3 | 0 (C3 settings toggle still advised) |
| High | 9 | 8 | 1 (H5, partly) |
| Medium | 17 | 8 | 9 |
| Low | 12 | 6 | 6 |

*Updated for release v1.0.61 (release-hardening pass): C3, H4, H6, H7 fixed; H5 partly
fixed (validation, proof and staged enforcement; token hashing and expiry still open);
M9 and M14 fixed. See [ops/RELEASE_v1.0.61.md](ops/RELEASE_v1.0.61.md) for the deployment runbook.*

The three items that matter most:
1. **C1:** a parent reporting a child's suicidal talk could get a religious-referral reply instead of the emergency escalation.
2. **C3:** pull-request CI runs on the production server.
3. **H1:** one device could read another device's chat history through the assistant endpoint.

---

## 2. Critical

### C1 — Emergency escalation was pre-empted by the fiqh guard ✅
- **Where:** `backend/app/routers/assistant.py`, both `/draft` and `/stream`.
- **What:** the fiqh hard-block ran *before* `check_emergency_keywords`/`is_emergency`.
- **Reproduced:** «ابني بيقول عايز ينتحر بعد الطلاق» ("my son says he wants to kill himself after the divorce") matches the emergency lexicon *and* the fiqh rule `fiqh_talaq_khalaa`, and received the fiqh deflection ("ask a religious authority") with no escalation.
- **Fix:** the order is now banned → emergency keywords → emergency severity → fiqh guard, in both handlers. The guard's blocking SQLite log write also moved off the event loop.
- **Test:** `test_fiqh_guard_precision.py::test_{draft,stream}_escalates_emergency_instead_of_fiqh_deflection`.

### C2 — Fiqh guard regexes blocked core parenting and medical questions, and missed plain fatwa phrasing ✅
**Where:** `backend/app/services/fiqh_guard.py`.

The rules matched substrings of *different words*. All 8 legitimate test questions were blocked:

| Question | Rule hit | Why |
|---|---|---|
| «ابني حديث الولادة ووزنه ضعيف» (newborn, low weight) | `hadith_tahdith` | «حديث الولادة» = newborn |
| «كيف أعلم ابني ترك الغيبة» (backbiting) | `aqeedah_ghayb` | الغيبة ⊃ الغيب |
| «ضعف في الرؤية» (eyesight) | `aqeedah_sifaat` | الرؤية = vision |
| «الصور … التحكم الأبوي» (parental controls) | `halaal_haraam_images` | التحكم ⊃ حكم |
| «ما موضوع الحديث…» / «ضعيف في القراءة… رواية» | `hadith_tahdith2` | موضوع = topic, رواية = novel |

At the same time:
- «ما حكم الموسيقى؟», the plainest fatwa form, was **not** blocked, because the ruling word came before the topic.
- Every alternative written with أ/آ («أطلق زوجته», «الأرواح», «آلات الموسيقى») was dead code. The text is normalized before matching; the patterns were not.

A newborn-health question getting a fiqh reply is a patient-safety problem. The guard also runs before retrieval, so the parent gets no medical content at all.

**Fix (the approved option: narrow the collisions, keep the categories):**
- Patterns are normalized at compile time.
- Word-start guards on ruling words (حكم/حرام/حلال).
- `الغيب` no longer matches when followed by more letters, so الغيبة/الغيبوبة pass.
- The bare `الرؤية` now requires aqeedah context.
- `حديث` excludes «حديث/حديثي الولادة·العهد·السن» and «تحديث».
- Bounded gaps.
- Reverse word order is covered, so «ما حكم X» now blocks.

**Tests:** 11 must-pass and 17 must-block cases in `test_fiqh_guard_precision.py`, including the FIQH_GUARD.md v3 "wrapped prompt" examples.

**Still open 📋:**
- `الطلاق` still blocks *every* mention of divorce, including «كيف أتعامل مع أطفالي بعد الطلاق», which FIQH_GUARD.md calls tarbawi and in scope. Fixing this needs the intent classifier (plan step 4), not a regex.
- «هل الله يغفر الذنب» is listed in the spec but no rule covers it.
- `blocked_fiqh_log` stores raw question text (it can contain child names) with no retention limit. Add redaction and a 90-day TTL.

### C3 — Pull-request CI executes on the production server ✅
- **Where:** `.github/workflows/backend.yml`, `docker.yml` and `flutter.yml`. All are triggered by `pull_request` and run on `runs-on: [self-hosted, production]`. That runner is the VPS: `deploy.yml` uses it to `docker build/run` and it holds `/root/tutor-guardian/.env`.
- **Risk:** the repository is **public**. Code from a fork PR would execute on the production host. GitHub's "require approval for outside contributors" setting is the only barrier, and it is a settings toggle, not a guarantee.
- **Recommended:**
  1. Move the `pull_request` jobs to GitHub-hosted runners, or to a separate, unprivileged, ephemeral self-hosted runner with no Docker socket and no secrets.
  2. Keep the `production` label for `deploy.yml` only (push to `main`).
  3. Set *Settings → Actions → Fork pull request workflows → Require approval for all outside collaborators*.
- **Fixed (release pass):** every job in `backend.yml`, `docker.yml` and `flutter.yml` now carries
  `if: github.event_name != 'pull_request' || github.event.pull_request.head.repo.full_name == github.repository`.
  A fork PR skips all jobs, so it never reaches the production runner. Pushes, manual runs and same-repo branches (which need write access) are unchanged.
  The workflows also declare `permissions: contents: read`.
  Point 3 (the settings toggle) is still advised as defence in depth.

---

## 3. High

### H1 — IDOR: any device could use any `session_id` in the assistant ✅
- **Where:** `routers/assistant.py`. The handlers only checked `session_exists(session_id)`.
- **Impact:** an authenticated device naming a foreign session had that session's history read into its prompt (so the model could restate it) and wrote its own turn into the victim's conversation. `GET /api/chat/sessions/{id}` already enforced ownership; the assistant did not. UUIDv4 IDs make guessing hard, but IDs travel in URLs and logs.
- **Fix:** new `conversation_store.session_owner()`, and `_require_owned_session()` returns 404 for a foreign session (indistinguishable from a missing one; the client already recovers from 404).
- **Test:** `test_audit_regressions.py::test_assistant_rejects_a_foreign_session_id`.

### H2 — Changing a child's challenge a third time returned 500 ✅
- **Where:** `db/init_db.py` (`child_challenges`). The table key was `UNIQUE(device_id, child_id, status)`, which allows **one resolved row per child, ever**.
- **Reproduced:** set A, switch to B, switch to C: `IntegrityError` → HTTP 500. A clear after one earlier resolve also failed. The existing test only did two changes.
- **Fix (migration v27):**
  - The table is rebuilt in one explicit transaction, following the `_ensure_lesson_progress_child_key` pattern.
  - The table-level key is replaced by a partial unique index `(device_id, child_id) WHERE status='active'`.
  - The dormant v7→v12 migration's reference to a nonexistent `resolved_at` column (in the old table) is fixed as well.
- **Tests:** repeated churn over the API, plus migration from the legacy schema (idempotent).

### H3 — Encrypted backup sync was unreachable in production ✅
Two independent defects:
1. The router declared `/api/sync/upload` and was mounted with `prefix="/api"`, so the live paths were `/api/api/sync/*`.
2. `/api/sync` was missing from `AuthMiddleware._PROTECTED_PREFIXES`, so `request.state.device_id` was never set and the handlers always answered 401. They also parsed up to a 50 MB body before doing so.

`tests/test_sync.py` stubbed the middleware and mounted the router without a prefix, so both defects were invisible.

**Fix:** relative routes plus the protected prefix. The stubbed test now mounts the router like `app.main` does, and new tests run against the real app. (The mobile client does not call sync yet; this makes the endpoint work before it does.)

### H4 — Rate-limit identity does not identify callers ✅
- **Where:** `middleware/rate_limit.py` and `main.py`.
- **Proxy order.** `ProxyHeadersMiddleware` is registered first, so it runs *innermost*. `RateLimitMiddleware` therefore sees the nginx container's IP for every request without a token. In production, every anonymous request shares **one** bucket: curriculum GETs (the app sends no token on them), `POST /api/chat/sessions`, feedback (5/min *globally*), and anonymous story generation. `trusted_hosts="*"` also lets any client spoof `X-Forwarded-For` for downstream readers (`referral.py`, `web.py`).
- **Token rotation.** Unvalidated token hashes are used as bucket keys, so a random `Bearer` value per request gets a fresh per-minute bucket *and* a fresh daily AI quota. That works on public and soft-protected LLM routes (`/api/program/story` while `STORY_AUTH_ENFORCE` is unset).
- **Session minting.** Unlimited public session creation makes the per-device quota advisory.
- **Unmetered LLM route.** `/api/insights` calls the LLM but is in the general scope, outside the AI quota.
- **Recommended:**
  1. Register `ProxyHeadersMiddleware` last (outermost) with `trusted_hosts` set to the nginx network CIDR via env. Verify first with `redis-cli --scan --pattern 'rl:api:ip:*'` on production.
  2. For the AI scope, validate the token (one SQLite read per LLM call is negligible) and key on the device.
  3. Add `/api/insights` to `_AI_PREFIXES`.
  4. Rate-limit `POST /api/chat/sessions` per real IP.
- **Fixed (release pass):**
  - A new pure-ASGI `middleware/client_ip.py` is registered **last**, so it runs first. It trusts `X-Forwarded-For`/`X-Forwarded-Proto` only from loopback, private or Docker ranges, and Cloudflare's published ranges (`TRUSTED_PROXY_IPS`). It walks the chain from the right, so a forged left-hand entry is never used, and falls back to `CF-Connecting-IP`.
  - The spoofable `ProxyHeadersMiddleware(trusted_hosts="*")` is removed. `referral.py` and `web.py` now read `request.client`.
  - The AI scope validates the token and keys on the **device**, so random Bearer values no longer buy buckets and a second session doesn't reset the quota.
  - `/api/insights` is in the AI scope, and its GETs count against the daily quota.
  - Session minting and feedback are keyed on IP only; minting has its own budget (`RATE_LIMIT_SESSION_PER_MINUTE`, default 30).
  - **Tests:** `test_client_ip.py`, `test_rate_limit_identity.py` (updated plus new cases), and `test_referral_fingerprint.py` (now models the nginx peer, plus a spoofing test).

### H5 — `device_id` is a bearer credential ◐ (partly fixed)
- `POST /api/chat/sessions` is public and mints a token for **any** `device_id` in the body. Knowing a device ID is therefore equivalent to owning the account: children, progress, chat history, backups.
- Device IDs are logged (`sync.py`, `push_sender.py`), partly echoed to Telegram, and sent in unauthenticated feedback bodies.
- Tokens never expire and are stored in plaintext.
- **Recommended:**
  1. When the device already has a token, require proof of possession (an existing valid token, or a device key pair in the Android Keystore) to mint a new one.
  2. Store `sha256(token)`.
  3. Add `expires_at` with sliding renewal.
  4. Stop logging raw device IDs.
- **Fixed (release pass):**
  - `SessionCreate` bounds `device_id` (≤128 characters, safe charset) and `metadata` (≤4 KB).
  - A Bearer proof for a *different* device → 403.
  - For a *known* device without proof: refused with 401 when `SESSION_MINT_ENFORCE` is set; otherwise logged by hash.
  - Build 106 sends its last token as proof (`TgClient.createSession`, kept across `endSession`).
  - Minting is IP-rate-limited (H4).
  - **Enforcement is staged:** flip it once the forced-update floor is ≥ 106.
- **Still open 📋:** hash stored tokens, `expires_at` with renewal, and removing raw device IDs from `sync.py`/`push_sender.py` logs.

### H6 — Threadpool starvation under concurrent streams ✅
- Each SSE stream runs `run_sync_stream` in the **default** executor for its whole duration. On a 2-CPU container that pool has about 6 workers.
- `worker.cancel()` does not stop the thread (see the comment in `assistant.py`), so an abandoned stream keeps its thread until generation ends.
- The same pool serves every `asyncio.to_thread` SQLite call, so about 6 concurrent answers stall *all* DB-backed requests.
- `AIGateway.generate()` has no overall deadline: cloud (60s) + 3 primary retries (120s each) + fallback chain (120+180+60s) + valve.
- **Recommended:**
  - a dedicated bounded executor for LLM streams, or async `httpx` streaming with cooperative cancellation;
  - a total deadline per request;
  - a circuit breaker on the primary provider (the auxiliary tier already has one).
- **Fixed (release pass):**
  - SSE workers run on a dedicated bounded pool (`LLM_STREAM_WORKERS`, default 8), so SQLite `to_thread` calls can't be starved.
  - `_pump_stream` stops at the next chunk once the client disconnects and **closes** the generator, which closes the provider's HTTP stream. The gateway logs the aborted call (`route_reason=client_disconnected`).
  - A per-answer deadline (`LLM_STREAM_DEADLINE_S`, default 300).
  - **Tests:** `test_stream_cancellation.py`.
  - **Still open 📋:** a primary-provider circuit breaker, and an overall deadline for the blocking `generate()` path.

### H7 — Mobile wipes its identity on any secure-storage read error ✅
`_AuthStore._safeRead` (`mobile/lib/api/tg_client.dart`) calls `_storage.deleteAll()` on *any* exception. A transient keystore error during early boot deletes `tg_device_id`, and every server-side record for the family (children, progress, reflections) is orphaned.

`resetOnError: true` already handles the real corruption case (BadPadding).

**Recommended:** delete only on the known corruption exceptions, retry once, and back up `device_id` to `SharedPreferences` as a recovery hint.

**Fixed (release pass):**
- No `deleteAll()` anywhere. Reads and writes retry once.
- `device_id` is mirrored to `SharedPreferences` and restored from there.
- A new ID is never written over an unreadable keystore entry.
- **Tests:** `auth_store_resilience_test.dart`.

### H8 — Stored XSS on the teen web surface ✅
- **Where:** `backend/static/child_mode/index.html`. `habit_name`, which includes parent-typed custom template names with no character validation, was interpolated into `innerHTML`. The page keeps the child token in `localStorage`.
- **Fix:** an `esc()` helper.

### H9 — Monthly report reported wrong numbers for multi-child families ✅
- **Where:** `routers/program.py::monthly_report`.
  - The streak was read across **all** of a device's children. Duplicate dates stopped the loop, so two children who both opened the app every day showed a streak of 1.
  - Partial habits were counted as `"partial"`, but the stored status is `"partially"` (`models/value_tracking.STATUSES`), so partial check-ins always showed 0.
  - The month bound `…-01T00:00:00+00:00` sorted *after* space-separated SQLite timestamps from the 1st, which dropped the first day of every month.
- **Fix:** per-child `DISTINCT` dates, the right status key, and a date-only bound.
- **Test:** `test_monthly_report_streak_and_partials_are_per_child`.

---

## 4. Medium

| ID | Finding | Where | Status |
|---|---|---|---|
| M1 | Stream path did SQLite writes (`_single`) and SQLite-backed redaction (`redact_for_cloud`) **on the event loop**, stalling every in-flight stream | `assistant.py` | ✅ moved to `to_thread`; `get_running_loop()` |
| M2 | The request URL (with the caller's query string) was reflected unescaped into `href=""` on public pages | `routers/web.py` | ✅ escaped (`_page` and the landing template) |
| M3 | `audio_base64` had no length limit, so a huge string was base64-decoded before the 8 MB check | `routers/feedback.py` | ✅ `max_length` |
| M4 | `redact_for_cloud` replaces the names of **every family's** children with «طفلي», with no word boundaries. Prophet names (يوسف، محمد، مريم) in fiqh questions, the tier routed to the cloud, get corrupted. It also runs thousands of `re.sub` calls per request as the user base grows | `services/privacy.py` | 📋 scope to the caller's children and add Arabic word boundaries |
| M5 | The semantic answer cache (cosine ≥0.92) can serve an answer that addresses another family's child by name, because the question text is part of the prompt | `services/answer_cache.py` | 📋 redact names before storing; exact-match only when a name was present |
| M6 | `message_text` and `conversation_history` are unbounded, so a single request can carry megabytes into the classifier, embedder, BM25 and LLM. Client-supplied history (no `session_id`) can inject fake assistant turns | `models/api.py` | 📋 `max_length` of about 4000; history ≤ 12 turns; ignore client history when a session exists |
| M7 | Retrieval embeds the same query up to about 18 times per request (per domain × query × leg) | `services/retrieval.py` | 📋 embed once, pass `query_embeddings` |
| M8 | `/` and `/go` insert a `referral_clicks` row per request, with no rate limit (the routes are outside `/api`) and a spoofable IP | `routers/web.py` | 📋 throttle and trust only the proxy's IP |
| M9 | The referral `AUTO` claim matches by client-controlled `X-Forwarded-For`/`CF-Connecting-IP` | `routers/referral.py` | ✅ fixed with H4 |
| M10 | Push `register` returned 500 on non-string `token`/`platform`, and connections leaked on error | `routers/push.py` | ✅ |
| M11 | `privacy.known_child_names` is cached on the main DB file's mtime, which WAL writes don't change, so the cache goes stale | `services/privacy.py` | 📋 |
| M12 | Mobile creates `TgClient()` ad hoc in 19 places. Each has its own un-closed `http.Client` and session cache, and concurrent `ensureSession()` calls can mint duplicate sessions | `mobile/lib/**` | 📋 route everything through `tgClientProvider`; dedupe in-flight `ensureSession` |
| M13 | Mobile SSE has a timeout only on the headers, so a server stall mid-stream hangs the chat indefinitely | `tg_client.dart::streamQuery` | 📋 idle timeout per chunk |
| M14 | Each token rebuilds the full chat state and re-parses the whole Markdown, which is O(n²) on long answers | `state/chat_notifier.dart` | ✅ deltas batched every 60 ms and flushed on done, error, stop and pause (UX-2) |
| M15 | `ops-llm` metrics are open when `OPS_METRICS_TOKEN` is unset, and the token was compared in non-constant time | `routers/stats.py` | ✅ `compare_digest`; 📋 fail closed in production |
| M16 | Error `detail` strings echo internal exceptions (`f"DB error: {exc}"`, `f"bad audio: {exc}"`) | `routers/feedback.py` | 📋 |
| M17 | Monolithic `init_db.py` (1,100 lines of hand-written migrations); two SQLite files, with DDL scattered across `ai_gateway`, `answer_cache`, `retrieval`, `fiqh_guard` and `query_rewriter` | `db/`, services | 📋 see Phase 3 |

## 5. Low

| ID | Finding | Status |
|---|---|---|
| L1 | `main.py` warm-up block was mis-indented. With `SKIP_WARMUP` set it still ran and raised `NameError`, logged as a misleading warning. It also reloaded the whole KB just to log a count | ✅ |
| L2 | `conversation_store.create_token/create_session` and `identity.get_identity` leaked connections on exceptions | ✅ |
| L3 | `asyncio.get_event_loop()` inside a coroutine (deprecated); an unused exception variable | ✅ |
| L4 | Dead code: `retrieval._cached_domain_age_query`, `retrieve_multi_domain`, `conversation_store.get_device_id`, `ci.yml` | 📋 |
| L5 | `datetime.utcnow()` (deprecated in 3.12) in `children.py` and `program.py` | 📋 |
| L6 | `_unit_languages()` `lru_cache` is never invalidated after a KB rebuild | 📋 |
| L7 | `MultilingualEmbedding._lazy_load` is not thread-safe (masked by the warm-up) | 📋 |
| L8 | `identity._verify_google_id_token` does not check `email_verified`; the legacy merge copies child profiles but not their progress | 📋 |
| L9 | `pytest` and `pytest-anyio>=0.0.0` ship in the runtime image; `pytest-anyio` is obsolete because anyio ships its own plugin | 📋 split `requirements-dev.txt` |
| L10 | Push `registerToken` attaches a new `onTokenRefresh` listener on every call and hard-codes `platform: 'android'` | 📋 |
| L11 | The `child_web` claim store is in-process memory, so it breaks with more than one worker and codes are lost on restart | 📋 move to Redis |
| L12 | `lint` gate is deliberately narrow; there are pre-existing unused imports (`assistant.py`, `fiqh_guard.py`) | 📋 widen ruff gradually |

---

## 6. Dependencies and architecture

### Dependencies
| Area | Item | Note |
|---|---|---|
| Python | `chromadb>=0.5,<1` | Deliberately held (the production volume is in 0.6 format). Plan the 1.x migration: back up the volume, reindex, verify recall with `ops/tools/retrieval_probe.py`. |
| Python | `torch==2.13.0` + `sentence-transformers==6.0.0` + `transformers==5.16.1` | Pinned for a model-load regression. The default wheel pulls CUDA into a CPU-only image; use the CPU index (`--index-url …/whl/cpu`) to cut several GB. |
| Python | `requests` **and** `httpx` | The gateway uses sync `requests` behind `to_thread` (H6). Standardize on async `httpx`. |
| Python | unpinned lower bounds (`openai`, `firebase-admin`, `cryptography`, …) | Add a lock file (`uv pip compile`/`pip-tools`) and Dependabot or Renovate. |
| Flutter | `intl: any` | Pin it (it follows `flutter_localizations`). |
| Flutter | `google_sign_in ^6` | Uses the legacy Android Sign-In APIs; v7 moves to Credential Manager, with an API change. |
| Flutter | `just_audio_background ^0.0.1-beta.17` | Beta. Evaluate `audio_service`. |
| Flutter | `firebase_*`, `file_picker ^8`, `flutter_local_notifications ^18`, `share_plus ^11` | Majors behind: 106 packages have newer incompatible versions (`flutter pub outdated`). |
| Flutter | `flame` listed under the "Firebase" comment | Housekeeping. |

### Architectural gaps
1. **Two anonymous-identity models:** device-bound tokens for parents, HMAC tokens for children. There is no key possession, rotation or expiry (H5).
2. **Security-relevant behaviour lives in middleware ordering and prefix lists** (H3, H4). A table-driven route policy (public / soft / device / child) asserted by a test over `app.routes` would have caught both.
3. **Blocking I/O in async handlers** is handled case by case with `to_thread` (M1, H6). Either make handlers plain `def` (FastAPI's threadpool) or move to async drivers (`aiosqlite`, `httpx`).
4. **Telemetry DDL is spread across five modules,** each creating its tables on first write. Centralize it with the schema migrations.
5. **Guardrails are split** between regex (intent, fiqh), YAML policies and the prompt. There is no single evaluation harness: `ops/eval/golden_set.jsonl` exists but is not in CI. Add a guard-precision suite (as `test_fiqh_guard_precision.py` does here) for every guard.

---

## 7. Mobile UI/UX (summary; details in UX_UI_ROADMAP.md)

Fixed in this PR (UX-0):
- WCAG-failing button contrast in dark mode (white on #10B981 at 2.5:1 and on #FBBF24 at 1.7:1) and on the light gold button (3.2:1), fixed with new `onPrimary`/`onAccent` tokens.
- Invalid form fields had no error outline.
- Standard chip, dialog, bottom-sheet, list-tile, divider and text-button themes.
- A spacing scale and touch-target tokens.
- Streaming answers now stay in view when the reader is at the bottom.
- The send/stop button has an accessible name.
- 10 places showed raw exception text (`TgApiError(500)…`, `SocketException…`) to parents.
- Child habit buttons: failing-contrast hard-coded colours, a punitive red ✗, overflow at large text, and no success haptic.
- A semantic `Haptics` helper.

The rest (ThemeExtension migration, bundled fonts, chat lifecycle, charts and gamification, child theme) is phased in UX_UI_ROADMAP.md.

---

## 8. Roadmap

### Phase 0: this PR (done)
Fixes: C1, C2, H1, H2, H3, H8, H9, M1–M3, M10, M15 (partial), L1–L3, and UX-0.

Tests added:
- backend: `test_fiqh_guard_precision.py`, `test_audit_regressions.py`; `test_sync.py` corrected; the date-dependent daily-tip test fixed;
- mobile: `design_system_contrast_test.dart`.

### Phase 0b: release hardening, v1.0.61 (done)
- C3, H4, H6, H7, H5 (partly), M9, M14.
- UX-1: on-colour and `successText` tokens, WCAG-safe domain gradients, dark-mode-safe insights cards.
- UX-2: thinking state, token batching, follow-up chips (`follow_ups` field), inline retry, jump-to-latest, 16/1.7 answer type.
- Schema v27 runbook (`ops/scripts/migrate_schema_v27.sh`) and the release checklist `ops/RELEASE_v1.0.61.md`.

### Phase 1: security hardening (1–2 weeks)
1. ~~C3~~ ✅ (the settings toggle is still advised).
2. ~~H4~~ ✅.
3. **H5 (rest):**
   - flip `SESSION_MINT_ENFORCE` after the forced-update floor reaches 106;
   - hash stored tokens;
   - add `expires_at` with renewal;
   - stop logging `device_id`.
4. **M6:** request size limits on `UserMessage`.
5. **M4/M5:**
   - scope and word-bound the PII redaction;
   - make the answer cache name-aware;
   - redact the fiqh block log and add a TTL.
6. **C2 follow-up:** the fiqh intent classifier (FIQH_GUARD.md step 4), with a golden set from `blocked_fiqh_log`.

### Phase 2: reliability and performance (2–4 weeks)
1. **H6 (rest):** a primary-provider circuit breaker and a deadline for `generate()` (the stream path is ✅).
2. **M7:** single query embedding per request. Measure p95 before and after with `/api/stats/ops-llm`.
3. **M13:** mobile SSE idle timeout (M14 batching ✅).
4. ~~H7~~ ✅.
5. **M12:** a single `TgClient`, with in-flight session dedupe.
6. Run `ops/eval/golden_set.jsonl` in CI as a non-blocking report.

### Phase 3: maintainability (1–2 months)
1. Replace `init_db.py` with versioned migrations (Alembic, or numbered SQL files with a runner). Move all telemetry DDL there and merge `sessions.db` into one migrated store.
2. A route policy table plus a test over `app.routes` (§6.2).
3. Convert async handlers that only do blocking work to `def`.
4. Lock files and Renovate for pip and pub; split `requirements-dev.txt`.
5. Remove dead code (L4) and widen the ruff rules gradually.

### Phase 4: platform upgrades (as scheduled)
1. The ChromaDB 1.x migration, with a recall probe gate.
2. Flutter majors: `google_sign_in` 7 (Credential Manager), Firebase, notifications, `file_picker`.
3. `datetime.utcnow` cleanup ahead of Python 3.12+.

---

## 9. Verification performed

**Release pass (v1.0.61+106), final gate:**
- `ruff check backend/ ops/ scripts/`: all checks passed.
- `pytest`: **1110 passed, 0 failed**, 2 skipped (the first pass had 1088; the release pass adds 22 backend tests).
- `flutter analyze`: no issues.
- `flutter test`: **532/532** passed.
- `flutter build appbundle --release`: `app-release.aab` (94.4 MB), versionCode 106 / versionName 1.0.61. The zip CRCs check out and `jarsigner` verifies it. It is signed with the **debug** key because no upload keystore is present here, so it must be rebuilt where `key.properties` lives (see `ops/RELEASE_v1.0.61.md` §6).
- `ops/scripts/migrate_schema_v27.sh` exercised end to end against a v26 legacy copy: preflight → verified backup → apply → verify → rollback.

**First pass:**
**Backend:**
- `pytest` full suite, before and after:
  - baseline `HEAD`: 1045 passed, **1 failed**, 2 skipped. The failure is `test_get_daily_tip_0_3_has_pool`, which depends on the date since the `prenatal-1` migration (c4aca27); corrected here.
  - after: **1088 passed, 0 failed**, 2 skipped (42 new tests).
- New regression tests pass.
- `ruff check backend/ ops/ scripts/` (the repo gate) passes.

**Mobile:**
- `flutter analyze`: no issues, before and after.
- `flutter test`: 498 → 520 passing (22 new), 0 failing.

**Reproductions:**
- the challenge UNIQUE crash (in-memory SQLite);
- the guard ordering and the 8 false positives (pure-function probes);
- the sync double prefix (the real app returned 404).
