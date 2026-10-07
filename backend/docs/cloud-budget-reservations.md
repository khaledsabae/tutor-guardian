# Monthly cloud reservation design

**Independent follow-up:** capped admission now requires an exact documented
endpoint/model profile and reserves its entire input+generated context window.
The prior UTF-8/framing estimate has been removed. Unknown profiles fail closed
before transport; the local chain remains available. Explicit primary cap `0`
continues to opt out of the ledger and is **not** a hard-cap configuration.
This is an admission-accounting ceiling under the documented provider contract,
not an absolute guarantee against provider misbilling, hidden charges, external
account consumers or loss of the persistent ledger. Production cutover remains
an operational prerequisite; no production rollout is authorized here.

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

Reserve **1,048,576 tokens per attempt** for exact official DeepSeek HTTPS
origin `api.deepseek.com:443`, path root or `/v1`, model `deepseek-flash` or
`deepseek-v4-pro`. The [model pricing documentation](https://api-docs.deepseek.com/quick_start/pricing)
retrieved 2026-10-07 specifies a 1M context and bills input + output; the
[chat API contract](https://api-docs.deepseek.com/api/create-chat-completion)
explicitly limits total input plus generated tokens to the context window and
requires `max_tokens` between 1 and 393,216. Rounding 1M up to 2**20 is
conservative regardless of decimal/binary display. Reserve the **entire** window,
not a guessed byte/token bound plus completion allowance; the context already
includes completion. Validate the actual model after every switch and the actual
positive integer `max_tokens` sent on every attempt, never a configured label
that differs from the wire. A small request is refused if that full window cannot
fit; completed valid usage may later reduce the charge.

Mutable legacy aliases (`deepseek-chat`), Azure deployment labels, generic
OpenAI-compatible services, other paths/origins and undocumented models have no
verified profile here, so capped mode denies them. Do not add profiles from a
model name alone. The native default model is now the documented `deepseek-flash`;
explicit `DEEPSEEK_MODEL` values are preserved, including unknown values that
will fall back locally in capped mode. Defaults remain local primary `ollama`,
cloud safety valve disabled, Azure tier disabled, primary cap 100,000,000 and
fallback cap 10,000,000. No live environment/credentials were read or changed.
Primary `0` preserves the explicit unlimited opt-out even for an unknown profile;
fallback `0` still disables that safety valve. Only positive caps with known
profiles have the contract-bounded admission guarantee.

Unknown usage, HTTP errors, network ambiguity, generator close, cancellation,
process death and failed settlement retain the entire bound. Unresolved older
months consume current capacity until billing becomes known. Provider violations
of the documented context/output contract are outside the admission guarantee;
over-bound reported usage quarantines the wallet without pretending the bill
was prevented.

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
charges; reject requests whose full context bound cannot fit before transport; charge each ambiguous
network retry; preserve closed-stream charges; allow local answers when the
ledger is unreadable; settle only complete bounded usage once; keep orphans;
import legacy aliases together; and settle a previous-month ticket without
freeing current-month capacity. Exact validation results and the held acceptance contract are recorded below.

## Historical held milestone evidence / Ampere handoff

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

Historical technical acceptance blockers at the held milestone:

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

## Independent wallet/persistence review (2026-10-07)

Main, auxiliary, model-switch retries and fallback aliases on one normalized
origin share one wallet; `/v1` and explicit `:443` do not mint another wallet.
API-key rotation also cannot reset it. Primary versus fallback cap selection is
one configured policy, not additive quotas. Azure has a separate endpoint wallet
but is denied in capped mode until a specific deployment contract is verified.
Different origins/accounts cannot automatically be proven to share a physical
wallet, and external tools are not counted; audit these before rollout. Legacy
opening totals are intentionally imported conservatively to every wallet because
old telemetry has no endpoint/account attribution.

Production Compose maps `tg_sessions:/app/ops`; `_TELEMETRY_DB` resolves to
`/app/ops/sessions.db` inside the image. This is shared persistent state only if
all admitted gateway workers actually use that same volume/file. Cutover must
stop/drain old unreserved writers (including retries/in-flight SDK calls), take an
SQLite online backup preserving telemetry and all `cloud_budget_*` tables, record
known external opening spend/aliases, then start only reserved writers against the
same DB. Never substitute an empty DB, delete a ledger to clear a cap, restore an
older snapshot without reconciling intervening spend, or mix old/new writers.
These are deployment preconditions, not actions performed by this commit.

Test-only small `BillingProfile` fixtures exercise contention, Azure boundary and
retry accounting without asserting real profiles exist for synthetic models.
Localhost protocol tests explicitly opt out with primary cap zero; the separate
reservation suite keeps real cap enforcement at every mocked wire. Unknown-profile
rejection, local continuity and model-switch revalidation have independent tests.
Historical held counts above remain evidence of the earlier milestone, not the
follow-up result. Final focused validation is recorded below after completion.

### Follow-up acceptance evidence

Independent worktree `cloud-budget-profile-review`, based exactly on held
`5be9627bfed04c16b108499aa40cfd476eb21dda`. New contract tests first failed:
exit 1, 13 failed / 27 deselected, including the original unverified-billing
admission failure. Profile/reservation suite after implementation: exit 0,
40 passed. Final complete focused command (the eight held modules plus
`test_cloud_billing_profiles.py`), offline HF/Transformers, existing virtualenv,
`-B -m pytest -v -p no:cacheprovider --override-ini addopts='' --durations=5`:
**exit 0, 161 passed, 3 dependency warnings, 51.91 seconds**. This includes
main/aux contention, internal model-switch/retry admission, SDK/stream aborts,
unknown-profile local fallback, ledger persistence/rollover and explicit zero
opt-out semantics. Ruff and `git diff --check`: exit 0. No live provider requests,
mobile builds, production changes, credentials, deployment or purchases.

One intermediate aggregate had exit 124 at its 150-second limit and a new
fixture mistakenly used HTTP404 where the model-switch protocol requires 400;
neither was counted as a pass. The fixture was corrected, then the entire suite
above passed. Raw bounded logs and official-source captures remain private under
`/tmp/tg-cloud-profile-private/`. The original held history is preserved above.

The original merge-blocking unknown-profile admission test is now green because
unknown capped profiles cannot reach transport. Acceptance is restricted to
known-profile, contract-bounded gateway admissions with a persistent shared ledger.
No absolute provider-invoice guarantee or production-cutover approval is implied.
