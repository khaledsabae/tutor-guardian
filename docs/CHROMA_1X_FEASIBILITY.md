# Phase 4: Chroma 1.x feasibility and recall plan

Read-only research/code proposal at `090a6806ef0c5288fc274982495d8e963b0f8bb5`.
No dependency change, model import/download, image build, database opening,
index mutation, paid call, deployment or production measurement occurred.
Actual production provider/version, RAM and effective mounts remain pending
the parent's encrypted diagnostics. Repository declarations are not live proof.

## Actual dependency/API inventory

`backend/requirements.txt:28` allows `chromadb>=0.5,<1`; the image/hosted CI
also applies `.github/ci/constraints-prod.txt:30`, pinning **0.6.3**. Thus this
is not a demonstrated 0.5 runtime. Leave both constraints and the pinned
torch/transformers/sentence-transformers/HF stack unchanged in this task.

| Current call/site | Compatibility assessment / proposed validation |
| --- | --- |
| `retrieval.py:_get_collection`: `PersistentClient(path=...)` | Embedded persistent database, not a separately deployed Chroma server. Opening an old directory is not a read-only diagnostic: migration/startup may write. Test only disposable copies or a fresh directory. |
| `list_collections` string-or-`.name` normalization | Already accommodates 0.6 names and 1.0 Collection objects. No pathname-only compatibility patch is needed here. |
| `get_collection` / `create_collection`, explicit custom embedding function, `metadata={"hnsw:space":"cosine"}` | Verify exact selected 1.x release supports these arguments and cosine configuration. Preserve explicit normalized e5 vectors, prefixes, dimensions and distance metric. Do not replace the embedder with Chroma's default or silently drop cosine metadata. |
| Custom `MultilingualEmbedding.__call__(input)` | Input signature already follows the post-0.4.16 contract. Check exact target release's embedding-function persistence/configuration requirements; only add serialization/name/config methods if the disposable SDK test proves they are required. |
| `.add(ids, documents, metadatas, embeddings)` | Vectors are supplied explicitly. Check insertion, count, persistence/reopen and metadata round trips with deterministic small vectors before any real-embedding run. |
| `.query(query_embeddings=..., n_results=..., where=..., include=[documents, metadatas, distances])` | Main hybrid path supplies memoized explicit query vectors; legacy branch uses `query_texts`. Verify both, filters, distance ordering, empty results and IDs. No returned embeddings are consumed here. |
| `.get()["ids"]`, `.count()`, `.delete(ids=...)` | ID membership is checked as sets; no dependency on undocumented get-ordering. Guard empty input against the documented filtering change. |
| `_hnsw_is_bloated`: `chromadb.segment.VectorReader`, `collection._client._manager.get_segment`, `seg._index.get_current_count()` | Private Python-segment introspection is a major Rust-engine risk. Exceptions currently return False, hiding unavailable diagnostics. Proposed patch: report capability UNAVAILABLE rather than claiming a healthy graph; use immutable fresh rebuilds instead of a private Rust graph probe. |
| `_purge_persist_dir`: `SharedSystemClient.clear_system_cache()`, then directory deletion | Private/global cache operation and destructive shared-directory mutation. Do not use this to upgrade a live mounted index. Process/container replacement is the safe boundary for the migration rehearsal. |

Official [migration notes](https://docs.trychroma.com/docs/overview/migration)
state that 1.0 rewrote much of the engine in Rust and returned Collection
objects from `list_collections`. The separate Chroma server/container config
and `/data` changes do not automatically apply to this application's embedded
`PersistentClient`. Built-in Chroma server auth removal is not evidence that
the application's device/session auth must change. Exact target 1.x version
and dependency resolution still need a scheduled disposable compatibility run.

## Fresh rebuild beside old; no in-place migration

The current `_content_fingerprint` hashes units' embedding text and metadata,
but not the Chroma engine/version or embedding-model revision. An unchanged
corpus can therefore cause startup to open a cross-version directory before
deciding the index matches. `_install_seed_if_current` can also purge/copy a
seed into the live directory; equal content fingerprints do not prove storage
compatibility. `index_knowledge_units(force=True)` explicitly deletes contents.

Proposed implementation, in a future separately scoped backend patch:

1. Add a seed manifest containing exact Chroma/storage format, model revision,
   embedding dimensions, normalization/prefix rules, cosine configuration,
   corpus fingerprint and source image digest. Reject a mismatched format
   **before** constructing `PersistentClient` or copying a seed.
2. Reuse `index_seed.main`'s nonempty-directory refusal. Build a fresh 1.x
   database in a new named volume/directory, beside the intact 0.6 volume.
   Do not initialize 1.x on the production volume, even just to inspect it.
3. Keep model files, corpus, vectors, metadata and query/rerank policy fixed.
   A first engine-isolation experiment can reuse previously verified vectors;
   the later fresh-embedding rehearsal must independently prove the exact
   model revision and dimension. Neither experiment was run here.
4. Validate privately on a hosted/disposable candidate: no production mounts,
   no `.env`, isolated conversation/cache/telemetry databases, offline warmed
   models, bounded memory/time. Measure RSS/peak RAM and latency; compose's
   declared 4 GB limit/1 GB reservation are only configuration evidence.
5. Quiesce the old writer before taking a consistent SQLite/WAL/HNSW volume
   snapshot. Record old image digest, exact volume identity, checksums and
   restore proof. Obtain effective mount/RAM diagnostics before cutover.
6. Cut over only after compatibility, complete recall evidence, resource fit
   and restart tests pass. Rollback pairs the old image **with the untouched
   old volume**. Never start 0.6 against a 1.x-written directory. Preserve
   independent sessions/ops state and use an isolated candidate answer cache.

## Existing real baseline and comparator

Existing `retrieval_probe.py` calls the LLM classifier/query rewriter and
real hybrid retrieval; it reports text/reference/rerank pairs, not canonical
expected-ID denominators. `age_reach_probe.py` and `language_rank_probe.py`
measure different concerns. `golden_ci.py` already supplies deterministic
domain/fallback + real offline hybrid retrieval and canonical supported-target
scores. The new comparator **calls its `score_retrieval` directly**; it does
not implement a second recall definition or execute retrieval.

The parent supplied hosted run **37650768957**, artifact
`golden-retrieval-8613a0a...`, locally at
`~/.codex/evidence/tutor-guardian/oct7-pr62/golden-090/report.json`.
Its recorded merge revision is `8613a0a39c7f8cae55d5e71951e3e7e26af135d7`;
the parent reports that its tree matches head 090 based on dd81. This task
does not independently attest that GitHub tree equivalence.

Read-only aggregation reproduces **126/126 evaluated, zero errors/unavailable**,
unit recall **0.17261904761904762 over 84 scored items**, domain recall
**0.6853448275862069 over 116**. Answer quality remains UNAVAILABLE. Artifact
SHA-256: `593183cb05b60fe32b6f85e36fe4d9d1ba8db75695f4ebd5b24d0cb1ad64468b`.
No local model/index was opened to produce these numbers; they inventory the
existing hosted baseline. No genuine 1.x capture exists in this task.

Baseline-only inventory (no catalog inferred, exit 2):

```sh
python3 ops/tools/chroma_recall_probe.py \
  --baseline /path/to/existing/golden/report.json --out /private/baseline.json
```

For paired comparison supply `--baseline old.json --candidate new.json
--catalog frozen-catalog.json --out comparison.json`. Each capture wraps its
existing golden report `items` plus a `metadata` object:

* `chroma_version` and `top_k`;
* `golden_sha256`, `catalog_sha256`: `chroma_recall_probe.digest` of the parsed
  full golden list and catalog object;
* `corpus_sha256`, `embedding_sha256`, `query_policy_sha256`: actual frozen
  corpus/vector/model-policy manifests, identical on both sides.

The catalog is `{"unit_ids": [...], "domains": [...]}` exported from the
actual isolated index, including merged KB directories and published daily
tips. Do not infer the catalog from retrieved IDs or only `units/`. The hosted
baseline did not retain a full catalog/model/index provenance manifest: recover
it from the exact candidate, or repeat the baseline under a frozen profile.
Do not invent metadata just to get a complete comparison status.

The CLI preserves every golden item. It rejects duplicate/unknown IDs, corpus
or policy drift, wrong input hashes, out-of-catalog IDs and oversized captures.
Unsupported targets remain explicit; missing/error items cannot be paired.
Macro and micro recall use the same supported targets on both sides; null
targets receive no vacuous perfect score. Lost supported IDs remain visible.
Existing golden reports sort returned IDs, so do not reinterpret their list
order as ranking; compare the complete captured set with identical `top_k`.

Exit 0 means COMPARISON_COMPLETE report coverage, **not an upgrade pass**.
Partial/incomparable/unavailable input exits 2. Runtime compatibility always
remains UNVERIFIED and recall_gate NOT_EVALUATED; scheduled evaluation must
apply its reviewed acceptance criteria to genuine captures. Baseline-only mode
retains reported baseline scores while candidate/paired coverage stays zero.

## Scheduled checks, still pending

Run exact-version SDK CRUD/query/reopen tests with small fixed vectors; prove
cosine and every age/domain filter, stale-handle handling, empty inputs, fresh
seed format refusal and rollback reopening on separate directories. Reuse
existing `test_index_seed`, retrieval age/embed-once tests and candidate smoke,
adapting the private introspection assertion only after measuring the 1.x SDK.
Then capture all 126 golden items under a frozen profile, report paired recall,
per-domain/age/category losses and unsupported targets, and measure memory,
latency, cold/warm restart and rollback. Full answer generation/judging is a
separate pending scope and is not implied by an offline recall comparison.

This task's fixtures test report arithmetic/provenance/coverage only. They
are not real Chroma, real embeddings, RAM measurements or 1.x recall results.

## Manual hosted recall experiment

`.github/workflows/chroma-1x-recall.yml` runs only on `workflow_dispatch`, on
`ubuntu-latest`, with read-only repository permissions and no secrets or deploy
step. It installs the production hashed locks under the production constraints
in a baseline venv. A separate venv starts with the same package set, then
installs the latest stable `chromadb>=1,<2`, resolved without constraints and
pinned exactly before installation. A conflict with the remaining production
pins fails the experiment rather than selecting an older candidate. Production
requirements, constraints, images, indexes and volumes are never changed.

`ops/tools/chroma_recall_capture.py` freezes the full default loader corpus
(including merged directories and published daily tips) in insertion order,
actual normalized document vectors, every golden query vector, model snapshot
revisions, model library versions and retrieval source/configuration hashes.
It builds fresh, separate cosine indexes below `RUNNER_TEMP` from these same
records/vectors. The application's custom embedding-function collection API is
used, but queries replay the frozen vectors; no candidate re-embedding occurs.
BM25 and language metadata also use the frozen full unit records.

Both sides reuse `golden_ci.offline_report` with deterministic fallback domains
and production hybrid/rerank defaults. SDK query failures, unfrozen queries and
reranker fallback invalidate affected items. Candidate model loading is offline;
network access is denied during both retrieval captures. No LLM classifier,
query rewrite, generation or judge is called. Identical input is not a promise
of deterministic HNSW ranking, and this run does not measure migration, restart,
rollback, memory fit or complete production API compatibility.

The existing `chroma_recall_probe.py` compares the captures. The job summary
shows coverage and paired macro/micro recall; the artifact
`chroma-1x-recall-<commit>-<attempt>` retains `baseline.json`, `candidate.json`,
`comparison.json`, `summary.md`, both actual catalogs, frozen inputs, dependency
lists and the exact latest-1.x resolver report for 14 days. Reporting and upload
run after capture failures too; missing/failed captures remain explicit and
fail the job. `COMPARISON_COMPLETE` still means coverage, not upgrade approval.

GitHub requires a manually dispatched workflow to exist on the default branch.
Once this workflow is on `main`, select **Actions → Chroma 1.x recall
experiment → Run workflow**, choose the ref to evaluate, and dispatch. CLI:

```sh
gh workflow run chroma-1x-recall.yml --repo khaledsabae/tutor-guardian --ref main
gh run list --repo khaledsabae/tutor-guardian --workflow chroma-1x-recall.yml --limit 5
gh run watch RUN_ID --repo khaledsabae/tutor-guardian --exit-status
gh run download RUN_ID --repo khaledsabae/tutor-guardian --dir ./chroma-recall-evidence
```

The PR adding this workflow does not dispatch or merge itself. To evaluate a
later branch after the workflow exists on `main`, replace `--ref main` with
that branch name.
