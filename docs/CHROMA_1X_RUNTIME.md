# Chroma 0.6.3 → 1.5.9 runtime and persisted-index experiment

The fresh-index recall experiment [37788055548](https://github.com/khaledsabae/tutor-guardian/actions/runs/37788055548)
reported identical recall. That result does not establish that 1.x can open
a production-format 0.6.3 directory or run the backend API/tests unchanged.
This separate, manual experiment collects that evidence. It does not change
the production requirements, locks, volumes, or deployment configuration.

## Procedure

`.github/workflows/chroma-1x-runtime.yml` runs only on `workflow_dispatch`,
on `ubuntu-latest`, with `contents: read`, no secrets and no deployment.
Every DB/cache belongs to the disposable runner. Paths are exported through
`$GITHUB_ENV`, never through `runner.*` in job-level `env`.

1. Install the production and dev locks in a baseline venv using
   `--require-hashes --no-deps --only-binary=:all:` and production constraints.
   Run `pip check`; verify Chroma is exactly 0.6.3. Invoke the real
   `app.services.index_seed.main()` with only its persist/seed paths redirected.
   This calls `retrieval._ensure_index()`, loads all default knowledge units,
   embeds their production `embedding_text`, and verifies count/fingerprint.
   Warm the same reranker used by backend CI so tests can load models offline.
2. Exit the baseline process, then copy its complete SQLite/HNSW directory
   into the hosted checkout's `knowledge_base/chroma_db`. Verify every file
   hash, schema, migrations and fingerprint match, and the source is unchanged.
   The backend suite uses that hardcoded application path.
3. Create a second venv, install the same hash locks, then upgrade only
   `chromadb==1.5.9`. Remove **only** the `chromadb` entry from a temporary
   constraints file. Keep every other production pin, including old
   Chroma-only packages; new dependencies resolve under those constraints.
   A dependency conflict fails the experiment. Run `pip check` and save the
   resolver report and both package inventories. No committed lock is changed.
4. In a fresh candidate process, open the **copied** directory and execute
   actual `retrieval._ensure_index()` with `_index_built=False`. Harness guards
   forbid purge, collection creation/mutation and document embedding; the
   normal fingerprint check must skip seeding/rebuilding. Compare the complete
   IDs/documents/metadata/vectors digest, count, UUID and fingerprint to 0.6.3.
   Query the real `retrieve_relevant_units` path in Arabic and English using
   the real e5 embedding function. Require successful Chroma queries and
   nonempty results, and fail on logged vector exceptions that `_query` would
   otherwise swallow. No frozen vectors or lexical fallback are used here.
5. Reopen the migrated copy in a second fresh candidate process and repeat
   startup/data/smoke verification, proving the result survives process exit.
6. Run **all** `pytest backend/tests` under 1.5.9 with `SKIP_API_SMOKE=1`
   and JUnit. Migration/smoke failure does not suppress this step when the
   candidate installation succeeded. Existing test fixtures control warmup,
   network access and temporary databases; these tests are a separate runtime
   signal from the guarded copied-index startup proof.

## Evidence and interpretation

The always-uploaded `chroma-1x-runtime-<sha>-<attempt>` artifact contains:

- `baseline.json`, `copy.json`, `migration.json`, `reopen.json`: collection
  identity/data digest, before/after SQLite schema and migration rows, file
  hashes, fingerprint, changed files, real query IDs/call counts, and failures.
- `baseline-freeze.txt`, `candidate-freeze.txt`, `candidate-constraints.txt`,
  `candidate-resolve.json` when resolution succeeds, and install/pip-check logs.
- `backend-junit.xml`, `harness-junit.xml`, phase logs and explicit exit codes.
- `summary.md`/`summary.json`: observed migration behavior, actual JUnit case
  counts and failure `file:line` locations. Inspect tracebacks to distinguish
  a Chroma API breakage from a test/environment failure.

`migrated_in_place` means schema or recorded migrations changed while opening
and running the existing copied collection. `opened_in_place_no_schema_change`
means opening/querying succeeded without a detectable schema/migrations change;
ordinary file changes alone are not called a schema migration.
`refused_copied_index` means the client failed while opening the persisted copy.
`opened_but_runtime_incompatible` means opening succeeded but startup/query
failed. The JSON records whether schema already changed before that failure.

The experiment does not attempt a fresh rebuild or export/import on refusal,
so it does not assert either is necessary without further investigation. Never
reopen the candidate copy under 0.6.3: in-place changes can be irreversible.
The untouched baseline is the rollback source for this disposable experiment.
A green result requires every phase to exit zero and a nonempty passing backend
JUnit suite. Missing/skipped phases cannot produce a green summary.

The backend suite may mutate its copied index after the migration/reopen
reports are collected; those reports describe the guarded pre-suite processes.
Private HNSW bloat introspection remains best-effort in production code and is
not validated as a supported 1.x API by a successful query.

## Dispatch and download

GitHub requires the workflow file on the default branch before manual dispatch.
The PR adds the experiment and remains unmerged; it does not claim an observed
1.5.9 runtime/migration result before a hosted run is available.
After an authorized merge, select **Actions → Chroma 1.x runtime and migration
experiment → Run workflow**, choose the exact ref, or use:

```bash
gh workflow run chroma-1x-runtime.yml --repo khaledsabae/tutor-guardian --ref main
gh run list --repo khaledsabae/tutor-guardian --workflow chroma-1x-runtime.yml --limit 5
gh run watch RUN_ID --repo khaledsabae/tutor-guardian --exit-status
gh run download RUN_ID --repo khaledsabae/tutor-guardian --dir ./chroma-runtime-evidence
```

Use the recorded `commit.txt` to bind the result to the evaluated revision.
A green experiment supports planning an upgrade; it does not authorize one.
