# Golden evaluation in CI

At base `5d566611`, `ops/eval/golden_set.jsonl` contains **126 valid unique
items**, including the original 92. No subset is selected. Reports carry every
item ID, revision, counts, errors, and explicit scope. `COMPLETED` means the
reported work finished; it does not mean quality passed a threshold.

The same-repository PR candidate-image job automatically produces a nonblocking
report using the candidate's real baked Chroma index, e5 embeddings and hybrid
retrieval/reranker. The index is copied to a private temporary database. Docker
has no network, no credentials, no production volumes, and bounded resources
and time. No app lifespan or generator is started. Only the production
keyword/fallback domain classifier runs; LLM classification and query rewriting
are excluded. Domain recall and unit recall score only supported targets, with
denominators; unsupported domains and missing/withdrawn expected IDs remain
explicit in each row. Empty targets have null scores. This cannot measure
abstention, emergency/discipline behavior, memory use, or answer quality.

The report/summary is uploaded for 14 days. A failed build, unavailable model,
empty index, retrieval exception or timeout never becomes a fake quality pass.
Failed setup reports all items UNAVAILABLE; individual failures retain their
IDs as ERROR. Fork PRs inherit the candidate workflow's existing skip policy.
An atomic per-item checkpoint preserves completed rows and the remaining IDs
on interruption; the wrapper renders that partial evidence after a timeout.
The current source-label inventory has 17 distinct expected unit IDs absent
from the committed KB; the runtime checks the actual baked index independently.

## Full answer quality remains pending

The manual `golden-full.yml` workflow runs only from trusted main and currently
reports **UNAVAILABLE** for all items. Existing checked workflow definitions
have no generation/judge credential wiring. GH secret-list requests were not
retried; this is not a claim that repository secrets do not exist. Production's
self-hosted `.env` is not a sanctioned hosted-CI credential route and is never
read or mounted. No keys, credits, providers or paid executions were added.

`golden_ci.py --mode full` implements the orchestration for a future explicitly
approved DeepSeek route: preflight requires `GOLDEN_PROVIDER_ROUTE_APPROVED=true`,
`LLM_PRIMARY_PROVIDER=deepseek`, a present `DEEPSEEK_API_KEY`, and the public
`https://api.deepseek.com` endpoint. These are names, not credential evidence.
Do not enable this route without the user's approval. A later reviewed change
must wire the approved credential into a trusted, pinned candidate runtime;
the current manual workflow intentionally supplies none and does not build
an image or execute the application. Other providers need separate route work.

When enabled in that isolated runtime, the wrapper invokes the existing
`eval_answers.run_pipeline` real TestClient HTTP pipeline and `judge_all` real
judge. Conversation/cache/telemetry SQLite databases and index are private.
Ollama fallbacks point to unreachable loopback, warm-up is disabled, and no
production fallback hosts are contacted. Raw results persist before judging;
judge metrics remain the harness's existing groundedness, completeness,
actionability, Arabic fluency, safety and applicable deterministic checks.
Failed or missing judgments prevent COMPLETED. No mock is reported as quality.

Local tests cover report correctness and orchestration failures; fixture
responses are solely control-flow tests. Neither paid golden generation nor
the full hosted retrieval/quality report was executed during implementation.
