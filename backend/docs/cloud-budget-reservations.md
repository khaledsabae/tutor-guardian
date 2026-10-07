# Monthly cloud reservation design

**HELD — review-ready milestone, not merge/deployment-ready or a proven provider
billing hard cap.** Atomic SQLite admission works against the supplied numeric
reservation, but input UTF-8 bytes + 1024 framing tokens is an unverified billing
assumption. A deliberately failing acceptance test requires unknown tokenizer,
framing and input-billing contracts to be denied before the first paid wire.
Receiving over-bound usage and quarantining afterward is too late to guarantee
that first bill. Ampere must resolve this before acceptance; no independent
review or production-hard-cap approval is claimed here.

Scope: the configured monthly **token** ceilings, not a fixed currency bill. No
production settings, credentials, provider purchases or deployment change here.
Local Ollama remains outside the paid-wallet ledger and is available as fallback.

## Wire boundaries observed at 3d40ae7b

- Chat `generate`, chat `stream`, and `aux_generate` reach
  `OpenAIChatProvider._events`. Reserve inside its attempt loop immediately
  before `httpx.stream` enters the transport. The gateway's outer retries and
  the provider's status/network/model/unsupported-field retries must all pass
  this check. An advisory routing check cannot authorize a wire attempt.
- Azure quality `generate` and `stream` call the OpenAI SDK. Disable hidden SDK
  retries (`max_retries=0`) and reserve immediately before each create call.
  Streaming must close the SDK stream on abort. A caller's thread timeout does
  not refund a request still running in another thread.
- Telemetry remains best-effort diagnostic data after admission. It cannot
  mint budget or free a reservation. Main, auxiliary and safety-valve aliases
  draw from the same physical endpoint wallet, independent of model or API-key
  rotation. A separate endpoint is a separate wallet; different endpoint aliases
  for the same provider account cannot be discovered automatically.

## Atomic admission and state

Use the existing SQLite path with a dedicated monthly-wallet table and immutable
attempt IDs. Each admission uses its own connection and `BEGIN IMMEDIATE` so all
threads/processes sharing that DB see committed reservations before deciding.
Check opening legacy spend + all reserved/settled charges + proposed upper bound
against the configured cap in the same transaction as inserting the attempt.
No TTL, process-local total, or stale preflight sum participates in authorization.

Import legacy main/aux/fallback/Azure totals once per wallet/month, atomically.
Legacy telemetry has no endpoint/account identifier, so it cannot establish
separate old wallets: each wallet imports all known paid aliases conservatively.
Both
known prompt and completion counts are required; a matching legacy row with null,
negative or non-integral counts makes that month's opening spend unknown and
denies cloud admission. A fresh DB starts at zero. Unreadable/corrupt/busy SQLite
denies admission. Existing lower telemetry totals never reduce the ledger.

Reserve UTF-8 bytes of the exact serialized message list, plus 1024 tokens of
framing allowance, plus the strictly positive integer `max_tokens` actually sent.
This deliberately overestimates tokenization for the supported byte-backed
tokenizers and a single user-message framing. Input bounds and provider-enforced
output caps are billing assumptions, not independently verified invoices. Unknown
usage, HTTP errors, network ambiguity, generator close, cancellation, process
death and failed settlement retain the entire bound. Unresolved older-month
attempts also consume current-month capacity until their billing becomes known.
Do not assume a connection error or rejected request was free.

Only a completed successful protocol response with both valid counts may reduce
its charge once to actual usage at or below its bound. A completed response
without usable counts finalizes at the full bound; it frees no room that month.
Azure additionally requires a terminal choice before finalization. Usage above
the bound quarantines that wallet, including future months, rather than freeing room or hiding
a violated billing assumption. Retried attempts always get separate tickets.
No automatic recovery/reclamation of an orphan ticket is safe without provider
billing evidence. Settlement belongs to the ticket's admission month, even if
it completes after UTC month rollover. An old unresolved ticket is carried into
each subsequent admission month; if it completes late, its charge is counted in
both admission and completion months to cover either invoice convention. Known
usage can reduce a carry charge; unknown abandoned attempts never age out.
Month rollover does not rewrite history.

## Wallet/cap policy and review limits

DeepSeek-compatible main/aux/fallback route labels share a wallet keyed by
normalized endpoint origin. When DeepSeek is primary its primary cap applies;
otherwise the fallback cap applies. Azure has a distinct endpoint wallet and
uses the existing primary token ceiling. No additive primary+fallback allowance
is created. An explicit primary cap of zero retains the existing documented
unlimited opt-out; it is not a hard-cap configuration. Invalid/negative caps deny.

This controls gateway admissions, not other applications, machines using a
different SQLite DB, external API-key usage, provider price changes, provider
misreporting or retroactive charges. Deploying requires one shared persistent DB
and draining older unreserved writers before the one-time legacy import; a mixed
old/new rollout cannot provide a hard admission guarantee. Human review must
confirm endpoint/account alias mapping and billing assumptions. No rollout is
performed in this task.

SQLite persistence is a required premise: deleting/replacing the database,
restoring an older snapshot, or starting a new deployment with an empty volume
can reset accounted spend. A fresh DB is a new accounting history, not proof of
zero prior provider billing. Migration/rollout must establish its opening balance
and storage identity; this change does not authorize an automatic fresh-volume
production rollout.

## TDD acceptance checks (written before implementation)

Race independent SQLite connections for the final slot; share main/aux in-flight
charges; reject oversized UTF-8 input before transport; charge each ambiguous
network retry; preserve closed-stream charges; allow local answers when the
ledger is unreadable; settle only complete bounded usage once; keep orphans;
import legacy aliases together; and settle a previous-month ticket without
freeing current-month capacity. Exact validation results and the held acceptance contract are recorded below.

## Bounded milestone evidence / Ampere handoff

Base: `3d40ae7bcd93b909fc410a6dcd8fba95e1f932bd`, own managed worktree
`/home/khalednew/.codex/worktrees/cloud-budget-cap/tutor-guardian`, branch
`codex/cloud-budget-cap`. Assigned approximately 09:17 UTC, 40-minute deadline
approximately 09:57 UTC on 2026-10-07. This milestone remains held from merge.

Implemented files:

- `backend/app/services/cloud_budget.py`: SQLite immediate transactions,
  immutable per-attempt IDs, conservative legacy opening totals, atomic
  admission, one-time finalization, unknown charge retention, cross-month carry,
  and wallet quarantine on a reported bound violation.
- `backend/app/services/ai_gateway.py`: per-wire OpenAI-compatible hooks for
  main/aux/fallback/generate/stream/internal retries; Azure SDK retry/redirect
  control, stream closure and terminal-choice validation; fail-closed primary
  routing and local continuity; budget denial does not mark provider health bad.
- `backend/tests/test_cloud_budget_reservations.py`: real SQLite thread/process
  contention and mock-transport boundary cases, including an intentionally
  failing unverified-billing contract gate. No paid API or external model calls.
- `backend/tests/test_primary_budget.py`: replaces the obsolete fail-open
  expectation with the authorized fail-closed policy.
- This design/evidence document. Production environment settings unchanged.

TDD history: initial suite **exit 1, 10 failed**; expanded pre-hook suite
**exit 1, 18 failed**. New review probes then found retry/redirect/health issues
(**2 failed, 19 passed**), rollover/terminal-response issues (**3 failed,
21 passed**) and legacy paid-alias attribution (**1 failed, 26 deselected**).
Those implementations were corrected after observing the failures.

Before adding the unresolved billing-contract gate, all eight focused modules
passed together: **exit 0, 146 passed, 3 dependency deprecation warnings** in
47.58 seconds. That is proof of admission behavior under the supplied estimate,
not proof of the estimate's relationship to provider billing. The final held
run deliberately includes the failing billing-contract acceptance test; its
actual exit/count is recorded below after completion.

The canonical final command uses the existing repository virtualenv Python,
`-B -m pytest`, `-q -p no:cacheprovider --override-ini addopts=''`, against:
`test_cloud_budget_reservations.py`, `test_primary_budget.py`,
`test_safety_valve.py`, `test_aux_llm_routing.py`, `test_tier_routing.py`,
`test_stream_cancellation.py`, `test_child_memory.py`, `test_deepseek_wire.py`.
Tests run with `HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1`. An earlier system-Python
aggregate had exit 2 because ChromaDB was absent, and an earlier aggregate
without offline isolation timed out after 180 seconds; neither was counted as
success. Subsequent bounded offline runs used the existing complete virtualenv.
Ruff and `git diff --check` exited 0.

Remaining technical acceptance blockers:

1. Prove supported tokenizer, provider-added framing and billable input bounds,
   or refuse unverified provider/model profiles before transport. A 1024-token
   framing allowance alone cannot establish a provider billing hard cap. The
   failing test demonstrates that an unknown profile can currently transmit,
   report 10000 input tokens against a 1500 cap, and only then be quarantined.
2. Independently review wallet/account alias mapping, zero-cap opt-out semantics,
   Azure terminal usage assumptions and reservation/settlement integration.
   Ampere is the requested next reviewer; no independent acceptance is invented.
3. Production cutover requires persistent shared SQLite, known opening balances,
   and drained old unreserved writers. Empty/lost/restored volumes and other
   deployments/API-key consumers are outside this ledger's guarantee. No rollout
   or settings change is authorized by this commit.

The SQLite module gives a hard bound on its own atomic **admission accounting**.
The entire gateway cannot yet be described as having a proven hard monthly
provider-billing cap. Do not merge or advertise it as completed until the first
blocker is resolved and the acceptance test genuinely passes.

Final held aggregate: **exit 1, 146 passed, 1 failed, 3 dependency warnings**
in 46.86 seconds. The sole failure is
`test_unverified_input_billing_contract_is_denied_before_any_paid_wire`. The final
explicit-unknown-model version was checked separately: **exit 1, 1 failed,
27 deselected**. This is an intentional, unmarked merge-blocking acceptance
failure, not an xfail or a fabricated success. All other focused contracts pass.
