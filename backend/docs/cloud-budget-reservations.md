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
denies cloud admission. Missing/fresh/uninitialized history never authorizes zero
opening spend. Explicit activation on an existing verified telemetry DB is required;
unreadable/corrupt/busy SQLite denies admission. Existing lower telemetry totals
never reduce the ledger.

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
These are source defaults only; production model and caps are runtime-unverified.
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

SQLite persistence is a required premise. Admission now refuses a missing DB,
lost schema, uninitialized wallet/month, missing continuity witness, or an older
DB snapshot that disagrees with its retained witness. A fresh DB is no proof of
zero prior provider billing. Migration/rollout must establish its opening balance
and storage identity; there is no automatic fresh-volume activation.

## Explicit activation and operator CLI

`CloudBudget.bootstrap(receipt)` is the only initializer. It opens an **existing**
telemetry DB in SQLite `mode=rw`; admission and bootstrap cannot create a missing
DB or silently recreate an activated ledger's lost tables. It accepts an intact
pre-activation ledger while preserving existing opening totals, settled charges,
pending attempts and quarantine. Diagnostic reads/writes also cannot recreate
lost activated telemetry. Every wallet and each new UTC month needs its own
receipt before a paid wire; unresolved older tickets still consume capacity.

Receipt fields are mandatory:

| Field | Required evidence |
| --- | --- |
| `db_identity` | Nonempty operator-recorded identity of the verified persistent DB; reused for all its wallets/months. |
| `wallet` | Exact normalized gateway wallet, e.g. `cloud:https://api.deepseek.com:443`; verify account/origin aliases externally. |
| `month` | Current UTC `YYYY-MM`. |
| `opening_tokens` | Explicit nonnegative integer covering **all actual monthly token charges** through the cutoff, including external writers, main, aux, fallback and Azure aliases. At least the known telemetry sum; no absent/empty history inference. |
| `reconciled_through` | Timezone-aware ISO timestamp in that month, not in the future and not before any matching historical row. |
| `legacy_aliases` | List including `azure_deepseek`, `deepseek`, `deepseek_aux`, `deepseek_fallback` and any additional paid aliases; new unreconciled aliases deny admission. |
| `evidence_reference` | Nonempty reference to the actual reconciliation evidence, retained with the receipt. |
| `unreserved_writers_drained` | Literal `true`: old and external unreserved writers are quiesced through activation. |

The software validates this receipt and historical lower bound; it cannot prove
provider invoice completeness or authenticate an operator's evidence reference.
Explicit zero is accepted only as attested evidence, never supplied as a default.
An identical receipt is idempotent. Any changed receipt for an already activated
wallet/month is refused, even a lower opening balance. Bootstrap never clears
attempts, carry charges or quarantine; first adoption may conservatively count
overlapping legacy telemetry and existing reservations twice rather than drop
known charges.

For a later approved deployment, drain writers, verify the persistent telemetry
history and all provider/account aliases, reconcile charges through the cutoff,
and prepare the receipt from that evidence. Execute with explicit paths from an
installed backend runtime (the CLI has no environment/config/provider reads):

```sh
python -m app.services.cloud_budget_bootstrap \
  --db /verified/persistent/history/sessions.db \
  --receipt /verified/reconciliation/wallet-month.json
```

No operational receipt, zero opening balance, activation or deployment is created
by this change. Repeat the same command safely with the same receipt; monthly
rollover requires a new current-month reconciliation and preserves uncertain carry.

The durable witness `<DB>.cloud-budget-anchor` stores the DB identity and a hash
of all ledger schema/rows. An OS lock serializes each SQLite transaction and
atomic, fsynced witness replacement across workers. A commit/witness-write crash
leaves traffic refused until offline reconciliation; the committed charge remains.
Hashing scans ledger rows, so latency grows with retained attempts; admission
remains fail-closed on lock contention. Keep the lock/witness on the same shared
persistent filesystem with working advisory locks and fsync, accessible to every
worker. Preserve the **latest witness separately from rollback DB snapshots**.
Replacing only the DB with an older snapshot fails closed, as does deleting the
witness. Restoring both DB and its old witness, losing both, or unauthorized edits
to both cannot be detected by local state alone: reconcile against independently
retained provider/account evidence before recovery. This CLI deliberately refuses
to repair a continuity mismatch or accept a changed reseed; it is not a recovery
tool and supplies no invoice guarantee.

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

### Activation fix acceptance evidence (2026-10-07)

Native bounded follow-up on `f59b66d9976c139244f308421fad61df42b1deb8`, atop the
held `5be9627` baseline, in the same isolated worktree. The checkout was detached;
`codex/cloud-budget-profile-review` was created at that exact HEAD. The existing
untracked cutover test was inspected, preserved privately, then extended; the
primary checkout and other workers' files were not changed. The supplied
independent `/tmp/tg-f59-review-5wuyxlxi/test_cutover_review.py` was absent here.

TDD: initial cutover suite **exit 1, 24 failed**, including actual admission on a
missing DB and uninitialized telemetry. After the initial gate: **exit 0, 24
passed**. Additional witness-corruption, operational-CLI and diagnostic-healing
probes: **exit 1, 3 failed / 1 passed**; those behaviors were corrected. Existing
reservation tests now explicitly initialize simulated evidence instead of silently
granting fresh-history budget. Added regressions cover all lost tables, database
deletion/restore, missing/corrupt witness, settled/pending reseed preservation,
legacy ledger adoption, all paid aliases, DB/wallet/cutoff binding, rollover carry,
and local generate/stream continuity with no paid transport.

Final offline focused run used the existing virtualenv, `HF_HUB_OFFLINE=1
TRANSFORMERS_OFFLINE=1`, `timeout 150`, `-B -m pytest -q -p no:cacheprovider
--override-ini addopts='' --durations=5`, against the nine previously accepted
modules plus `test_cloud_budget_cutover.py`: **exit 0, 201 passed, 3 dependency
warnings, 64.72 seconds**. Ruff and `git diff --check`: exit 0. Temporary raw logs
and the preserved prior-worker test are under `/tmp/tg-budget-activation/`.
Earlier intermediate fixture/collection failures are not counted as acceptance.
No production reads/config changes, deploy, push, external model calls, mobile
build or emulator use occurred. Source defaults are runtime-unverified. Activation
still requires real independently verified reconciliation evidence and persistence;
there is no automatic zero seed or provider-invoice guarantee.

## Activation blockers fixed on fix/budget-cap-activatable (2026-10-08)

Four blockers found against production (runtime report of 2026-10-07, sanitized
aggregates only) kept this branch from ever admitting a paid call there. Each
fix below was written test-first.

### 1. `deepseek-chat` — explicit alias, never a built-in profile

Production sets `DEEPSEEK_MODEL=deepseek-chat` (878 October rows), and the
weekly `kb_gap_judge` hard-codes it. `_BILLING_PROFILES` knows only the two
documented models, so every capped primary call would be `BudgetDenied`.

DeepSeek's official pages, fetched 2026-10-08 ~07:13 UTC (SHA-256 of the HTML
as served; the pages embed build assets, so the hash pins this snapshot, it is
not a reproducibility promise):

| URL | SHA-256 | What it says |
|---|---|---|
| https://api-docs.deepseek.com/quick_start/pricing/ | `210f102275ccf1a6542f08a3bc9e4b4c7c83278cb74b35217bffa112df6363b2` | Models: `deepseek-flash` (DeepSeek-V4.1-Flash) and `deepseek-v4-pro`; context 1M; max output 384K. Prices per 1M tokens, peak (off-peak is half): flash input cache-hit $0.006, cache-miss $0.30, output $1.20; v4-pro $0.044 / $1.32 / $3.96. Legacy names still accepted: **only** `deepseek-v4-flash`, `deepseek-v4-flash-vision-exp`. `deepseek-chat` is not mentioned. |
| https://api-docs.deepseek.com/api/create-chat-completion/ | `e7133a7c2a7c2662567cca2e2392b503f97c2fb583009ff85f878744e0a36ba7` | `model` possible values: `deepseek-flash`, `deepseek-v4-pro`. `max_tokens` 1..393216; input+generated limited by context. |
| https://api-docs.deepseek.com/updates/ | `2922113bc4e0e970fa6d3c4065c3cff3ec661a4db03d671cc2310545c5b5bb71` | V4 preview (2026-04-24): `deepseek-chat`/`deepseek-reasoner` "will be discontinued in three months (2026-07-24)"; until then they pointed to deepseek-v4-flash non-thinking/thinking. 2026-09-10: V4-Flash retired, `deepseek-v4-flash*` temporarily routed to V4.1-Flash. No later word on `deepseek-chat`. |
| https://api-docs.deepseek.com/news/news260910/ | `f18dc22d37393381b31c9069996138f45aa7b02b08442d43af7c6c57f587bdce` | From 2026-09-14 04:00 UTC `deepseek-v4-pro` routes to V4.1-Flash at Flash rates. |
| https://api-docs.deepseek.com/api/list-models/ | `41551c3c498a93b6e6459eaeee89829940ca8acf999b24436a38a2231c7e091b` | `/models` returns `context_window` and `max_output_tokens` per model (a live check an operator can run with the key). |

**Verdict:** what `deepseek-chat` aliases today, its context length and its
price are **not verifiable** from the official docs: its documented end date
has passed and the current pages do not name it, yet production calls still
succeed. So it gets no built-in profile. Instead:

- `DEEPSEEK_BILLING_PROFILE_ALIASES="deepseek-chat=deepseek-flash"` (env, read
  into `LLM.deepseek_billing_profile_aliases`) lets the cap reserve
  `deepseek-chat` calls under the `deepseek-flash` profile. It is the
  operator's attestation, not a verified fact.
- Default is empty → `deepseek-chat` stays denied (fail closed; the local chain
  answers). A malformed or duplicated entry voids the whole setting.
- One hop, same origin, onto a verified profile only; a documented model can
  never be re-pointed; another origin never inherits an alias.
- Safety net if the attestation is wrong: a settled usage above the reserved
  context still quarantines the wallet (`blocked=1`).
- The verified alternative is to switch `DEEPSEEK_MODEL` (and the kb-gap
  judge's model) to `deepseek-flash`, which needs no alias — a quality decision
  for Khaled.

The cap counts **tokens, not money**; the prices above are recorded for the
operator's monthly reconciliation, not used by the code.

### 2. Opening history with the new telemetry (PR #65, telemetry_0002)

`_opening()` sums the month's paid `llm_calls` as the floor an attested
`opening_tokens` must reach. With the batch-oct8 telemetry:

- `usage_estimated=1` rows carry numbers (bytes/3 estimates, or an explicit
  flagged zero for a refused request) and **count at face value**. For a floor
  that is the safe direction: bytes/3 over-reads Arabic. If a real billing
  export comes in below the telemetry floor, the operator enters
  `opening_tokens = max(billing export, telemetry floor)` — over-counting, never
  under-counting.
- `provider='gateway'` rows (the all-failed marker, not a request) are never
  wallet spend, even if someone lists `gateway` as an alias.
- Legacy NULL-token rows still **block** activation, unless the receipt lists
  them in `unknown_usage_rows_covered` (llm_calls row ids). The list must equal
  the month's unknown paid rows up to the cutoff exactly — a missing, extra,
  duplicated or known row id denies — and it is part of the stored receipt, so
  changing it later is a forbidden reseed. Listing them asserts that the
  billing export behind `opening_tokens` already includes whatever they cost.
- Read-only helper for the operator:
  `python -m app.services.cloud_budget_bootstrap --db /app/ops/sessions.db --list-unknown-rows 2026-11`
  prints the ids (and ts/counts) to paste into the receipt; it opens the DB
  `mode=ro` and never creates the anchor.

### 3. Unknown usage settles to the request's bound, not the whole context

Before: `settle()` charged the full reservation (1,048,576 tokens) for any
attempt without final usage, and attempts that ended in an exception, a retry
(`continue`) or a consumer leaving mid-stream were never settled at all (held
in full and carried into later months). At October's rate (26 unknown rows in
~7 days, ~115/month) that parks ~120M tokens against a 100M cap for <1M of real
spend; ten such calls exhaust the 10M fallback cap.

Now every reserved attempt is settled exactly once (`_WireCharge`), on every
exit path (DeepSeek `_events` per attempt, Azure generate/stream), and a
missing count is charged at the request's own bound
(`cloud_budget.unknown_usage_bounds`):

- **input** = UTF-8 bytes of the serialized messages (keys/roles/escapes
  included) + `UNKNOWN_USAGE_FRAMING_TOKENS` (4096, chat-template headroom);
- **output** = the request's `max_tokens`;
- a reported half (e.g. prompt known, completion missing) is kept;
- never above the reservation, and an estimate never quarantines the wallet.

Why not the telemetry's bytes/3 estimate itself (which `llm_calls` still
records, flagged `usage_estimated=1`)? It is an estimate, not a bound: digits,
punctuation and emoji can tokenize at more than one token per 3 bytes, and for
a cut stream the received text is a lower bound on what was generated. The
ledger needs a bound, so it charges bytes (≥ 3× the estimate) + framing +
`max_tokens`. For an Arabic RAG prompt of ~10 KB and `max_tokens` 1024 that is
~15K tokens per unknown call — ~1.7M/month at October's rate, versus ~120M
before.

**Trade-off (explicit):** the full-context hold was provable from the
documented context limit alone; the request bound additionally assumes (a) the
tokenizer emits no more text tokens than bytes (true of byte-level BPE and of
byte-fallback tokenizers) and (b) provider-added input stays within the 4096
framing allowance, and (c) the provider honours `max_tokens`. Hidden
provider-side input beyond that would be under-charged **only on calls whose
usage never arrived**; calls with reported usage are charged exactly as before
and still quarantine the wallet if they exceed the reservation. The monthly
reconciliation against DeepSeek's billing export is the backstop. Unchanged:
a reservation whose process died mid-call is never settled and keeps its full
bound (carried across months).

HTTP refusals (4xx/5xx before a stream) are also charged the request bound
here, although DeepSeek most likely bills nothing for them — conservative by a
few thousand tokens per refusal.

### 4. Writers: recorded is not reserved — batch writers now reserve too

Inventory of every DeepSeek writer in the merged tree (guarded structurally by
`tests/test_deepseek_callers_are_recorded.py`: only allow-listed files may name
DeepSeek's host/key, and only the gateway may send a chat completion itself):

| Writer | Path | Ledger |
|---|---|---|
| Chat primary/fallback, aux (classifier, rewriter, memory), Azure | `ai_gateway` providers | reserved per wire attempt |
| `golden_ci`, `feedback_digest` | through the gateway | reserved |
| `kb_gap_judge` (weekly VPS cron, `deepseek-chat`, max_tokens 200/16), `eval_answers`, `generate_dataset_v2`, `ingest_pdf` | `record_chat_completion` | **now reserved** when the host is DeepSeek's |
| `feedback_auto_fix.py` | deleted on batch-oct8 (test asserts absence) | — |

PR #65 made the batch tools *recorded* (`llm_calls`), but the cap's ledger only
counts `cloud_budget_attempts`, so after activation the weekly judge would have
spent from the capped wallet invisibly. `record_chat_completion` now reserves
and settles exactly like a gateway attempt whenever the request goes to
`api.deepseek.com`: bounded `max_tokens` required, SDK hidden retries disabled
(`with_options(max_retries=0)`), `BudgetDenied` raised **before** any request
when the cap is full or not activated (row `route_reason=budget_denied`,
explicit 0/0). Other wallets (Ollama Cloud, local) are untouched.

Consequence to know: any machine whose `ops/sessions.db` is not an activated
ledger (the laptop) now gets `BudgetDenied` from these tools and from the
gateway unless it sets `DEEPSEEK_PRIMARY_MONTHLY_TOKEN_CAP=0` (explicit
unlimited opt-out) — which makes that machine an **unreserved writer** on the
same DeepSeek account.

What `unreserved_writers_drained: true` attests, and what code cannot prove:
every process that can spend from this DeepSeek account outside the VPS
container's ledger is stopped at the cutoff and stays stopped (or moves to a
different account): laptop/CI runs with the key, any other API key on the
account, untracked scripts or crons on the VPS host, console/playground use.
The in-container writers above all reserve against `/app/ops/sessions.db`.

### 5. `CLOUD_BUDGET_ENFORCE` — safe to merge and deploy before any bootstrap

Without a switch, deploying this branch to an un-bootstrapped production would
deny every cloud call (fail closed) and put every parent on the local chain.
So the ledger has an explicit activation switch, `CLOUD_BUDGET_ENFORCE`
(`LLM.cloud_budget_enforce`; only `1`/`true`/`yes` turn it on):

| | Off (default) | On |
|---|---|---|
| Paid wire attempt (gateway, Azure, `record_chat_completion`) | no reservation, never denied | reserved per attempt, fail closed |
| No ledger / no bootstrap | calls proceed exactly as on `main` | `BudgetDenied` → local chain (batch tools raise) |
| Soft ceiling `primary_budget_available` (sum of `llm_calls`) | applies; unreadable telemetry fails **open** (as on `main`) | advisory; unreadable fails **closed** |
| `max_tokens` required by batch tools | no | yes |
| Telemetry (`llm_calls`, estimates) | recorded | recorded |
| `cloud_budget_*` tables / anchor | never created | created by bootstrap only |

Tests: `tests/test_cloud_budget_switch.py` (off + no ledger → cloud answers,
no ledger tables; on + no bootstrap → denied, local answers; batch tools; the
soft ceiling's fail-open/closed). The transport tests in
`test_answer_reliability.py` run unmodified with the switch off.

Remaining off-mode differences from `main` are Azure-only hardening (SDK
retries off, `include_usage`, a stream without a terminal choice is an error);
Azure is disabled in production.

## Activation runbook (operator)

Order matters: the switch goes on right before the bootstrap (§6).

1. **Model decision.** Set `DEEPSEEK_BILLING_PROFILE_ALIASES=deepseek-chat=deepseek-flash`
   (attestation, §1), or move `DEEPSEEK_MODEL` to `deepseek-flash`. The
   weekly `kb_gap_judge` hard-codes `deepseek-chat`, so it needs the alias
   either way, or move it to Ollama (`OLLAMA_API_KEY` on the VPS).
2. **Merge and deploy with the switch off.** Production behaves as before;
   telemetry keeps recording.
3. **Drain unreserved writers** (§4): stop laptop/CI use of the key, list every
   key on the DeepSeek account, check the VPS host crontab for untracked jobs,
   and confirm the kb-gap cron runs *inside* the container (writes
   `/app/ops/sessions.db`).
4. **Collect the evidence** (Khaled): DeepSeek usage/billing export for the
   account from the 1st of the cutover month 00:00 UTC to the cutoff — daily,
   per model, tokens (cache hit/miss/output) and amount. Bootstrap early in a
   fresh month: October 2026 has 26 legacy NULL rows that would need
   `unknown_usage_rows_covered`.
5. **Write the receipt** (JSON, outside git):
   `wallet="cloud:https://api.deepseek.com:443"`, `month` = current UTC month,
   `reconciled_through` = the bootstrap moment (tz-aware, ≤ now, same month),
   `opening_tokens` = max(export through its last complete day + `llm_calls`
   tokens after that day, telemetry floor) (§6),
   `legacy_aliases` ⊇ the four paid aliases, `db_identity` (a name you choose
   for the volume), `evidence_reference` (where the export is kept),
   `unreserved_writers_drained: true`, and if needed
   `unknown_usage_rows_covered` from
   `python -m app.services.cloud_budget_bootstrap --db /app/ops/sessions.db --list-unknown-rows YYYY-MM`.
6. **Turn the switch on first:** `CLOUD_BUDGET_ENFORCE=true` in the VPS `.env`,
   then Compose **recreate** (not restart) of `tg_backend`. From here until
   step 7 every capped call is denied and the local chain answers — keep it
   to minutes. (Spend after a cutoff but before switch-on would be
   unreserved and refuse the first rollover, §6.)
7. **Bootstrap inside the container** with `reconciled_through` = now:
   `python -m app.services.cloud_budget_bootstrap --db /app/ops/sessions.db --receipt <file>`
   → "activation verified"; the anchor file appears next to `sessions.db`.
8. **Verify by effect:** after a real chat, a settled row in
   `cloud_budget_attempts` and an `llm_calls` row; no `BudgetDenied` in the logs.
   **Rollback:** switch off + recreate (the ledger stays, untouched).
9. **Month boundaries** roll over automatically when continuity is proven
   (§6); otherwise cloud stays denied from 00:00 UTC on the 1st and the log
   says why — then repeat steps 4–6 for the new month.

### 6. Automatic monthly rollover — only on proven continuity

Before: every month needed a new manual receipt, so with enforcement on every
capped call was denied from 00:00 UTC on the 1st until the operator acted.

Now, when `reserve()` finds no activation for the current month, it tries
`CloudBudget._auto_rollover` inside the same continuity-verified transaction
(anchor identity + ledger digest already checked, so a restored, replaced or
edited ledger never reaches it). It rolls over only if **all** hold:

- the immediately previous month was activated for this wallet, on the same
  `db_identity`, with `unreserved_writers_drained: true`;
- the wallet is not quarantined and the previous month's opening row exists;
- every reservation up to the previous month is settled (an in-flight call
  across midnight just delays the rollover until it settles);
- telemetry shows no spend the ledger did not reserve: no paid row with
  unknown usage, and paid `llm_calls` tokens ≤ ledger charges (attempts +
  carry) — for the previous month after its attested cutoff, and for the new
  month so far. More telemetry than ledger means a writer spent without a
  reservation; that refuses the rollover.

Then the new month opens at what the ledger measured: an activation receipt
marked `rollover_from`, `reconciled_through` = 00:00 UTC on the 1st,
`opening_tokens` 0, plus the late settlements already in `cloud_budget_carry`.
Otherwise nothing is written, cloud stays denied (fail closed; local chain
answers) and the log says why:
`cloud budget auto-rollover refused for <wallet> <month>: <reason>; explicit bootstrap required`.
Recovery is a manual receipt for the new month (runbook steps 4–6).

Known conservative edges: a skipped month (no activation for the previous
month) never rolls; enabling Azure (another wallet with the same aliases in
telemetry) would make telemetry exceed this wallet's ledger and refuse the
rollover; the comparison relies on each telemetry row's tokens being ≤ the
charge of the attempt(s) behind it, which holds for reported usage (equal)
and for the bytes/3 estimates against the byte bound of §3.

Runbook consequence: turn the switch on **before** bootstrapping (cloud is
denied for those minutes, the local chain answers), and set the cutoff at
the bootstrap moment. Spend between a cutoff and switch-on is unreserved: it
would sit in telemetry after the cutoff without a ledger charge and refuse
the first rollover. Take `opening_tokens` = max(export through its last
complete day + `llm_calls` tokens after that day, telemetry floor).

### 7. Contention and history (review of PR #71, P1)

Found by review probes p2/p3: `_transaction` gave up after 0.2 s and
`_digest` hashed every ledger row of every month twice per transaction. At 5k
prior rows with 4 concurrent streams, 15 of 49 settles were swallowed, each
leaving a 1,048,576-token orphan that carries forever and blocks rollover
(~95 lost settles exhaust 100M).

- **A settle is never a denial.** It retries until `SETTLE_TIMEOUT_S` (120 s);
  only if the ledger stays locked that long is the attempt left as an orphan,
  logged at ERROR with the remedy. `reserve` waits up to `RESERVE_TIMEOUT_S`
  (5 s, it is on the answer's critical path), bootstrap/admin 30 s. Threads of
  one process queue on an in-process lock (woken at release, no polling
  starvation); processes still serialize on the flock.
- **O(1) continuity witness.** SQLite triggers on every ledger table bump
  `cloud_budget_witness.seq` and keep running totals (rows, charged, settled,
  opening, blocked, …) on *any* INSERT/UPDATE/DELETE, including edits made
  outside this code. The anchor mirrors `(db_identity, witness row, hash of
  the ledger's schema incl. triggers)`. A restored snapshot, an edited or
  deleted row, or a dropped trigger/table no longer matches → denied.
  Unrelated schema changes in `sessions.db` (app tables, telemetry
  migrations) are outside the hash. A forged witness row (edit rows, then
  write the old totals back) is caught by `_recount` — the full O(history)
  recount — at every monthly rollover, which refuses on disagreement.
- **Closed months are archived.** At rollover, settled attempts and carries
  of months before the previous one move to `cloud_budget_attempts_archive`
  (still witnessed); unsettled attempts never move. A partial index on
  unsettled attempts keeps the carry scan off settled history.
- **Orphans: offline, audited.**
  `python -m app.services.cloud_budget_bootstrap --db … --settle-orphans --older-than-minutes 60 --evidence "<why>" [--policy request-bound|full] [--dry-run]`
  settles unsettled attempts reserved before the age limit (an in-flight call
  is never touched), at their request bound (from `cloud_budget_attempt_meta`)
  or in full, and writes one `cloud_budget_audit` row each (time, attempt,
  old/new charge, policy, evidence). A later real settle cannot rewrite them.

Probe results on this branch (copies of the review probes, scratch DBs):
p3 at 50k rows × 8 streams × 15 iterations: 120 reserved, **0 unsettled**;
p2 at 0/3k/10k/50k/150k rows × 8 threads: 40/40 reserve+settle each, single
reserve+settle 14–70 ms independent of history; p1 (12 processes × 20 for 10
slots): 10 admitted, never more.
