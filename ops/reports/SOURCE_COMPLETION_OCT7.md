# Source completion: six current approvals and two nonknowledge quarantines

Continues `afdf8acd` on `codex/source-recovery-final`. Authoritative originals
were cherry-picked in timestamp/dependency order:
`78895565 → dcdc7c83`, `d0806de9 → 519e2416`,
`6016bb4c → 27995bb2`, `cbd81a099 → d1f41dc4`.
Both queue conflicts were resolved by removing only the three approved keys
for that commit. The authored corpus stayed at 1393 through integration.

## Current approval proof

| Pair | PDF / printed page | Canonical raw verdict |
| --- | --- | --- |
| `isl-1057f72f` | 80 / 79 | `three-real-source-en-review-2026-10-07.json` |
| `isl-14bc16f5` | 53 / 52 | same |
| `isl-2aa57245` | 57 / 56 | same; retained low title note |
| `isl-2fee1086` | 134 / 133 | `SOURCE_FOUR_B_EN_REVIEW_OCT7.json` |
| `isl-552b4f5a` | 79 / 78 | same |
| `isl-8f8f836b` | 173 / 172 | same |

The first raw record is under `ops/data/kb_fidelity/source_recovery/`, the
second under `ops/reports/`. Both committed actual raw-verdict batches were
parsed and matched the stored verdicts. Six current canonical hashes match
the AR/EN title and summary fields; DeepSeek and GLM are independent families,
neither an author. Arabic files and all reviewed English wording were unchanged
between each draft and approval commit. No reviewer was called in this phase,
no manual/human approval stamp was created, and scholar review remains pending.
Stale Group B English metadata was clarified without changing reviewed fields.

The surviving primary PDF checksum again matched
`7fa6f88fbf1ba714947983c11cde1e8c67b576374ae06c08a081444743d1272c`.
Only the six pages above were freshly rendered and visually re-read. All eight
new draft proof excerpt hashes were checked; four selected hadith fragments
matched the local corpus at Bukhari 3747, 77, 5743 and 5027. Historical
Mu'tamir household prayer is not a modern child-age mandate; the healing
supplication does not promise a medical outcome. Earlier historical Ashura
and Eid limits remain unchanged. Exact hashes and provenance are recorded in
`ops/data/kb_fidelity/source_recovery/source-completion-audit-2026-10-07.json`.

## Nonknowledge is outside retrieval

A fresh scan of 934 curriculum/mapping JSON files found zero references to
`isl-23c2dd25` or `isl-7349e59c`, including English twins. The former records
the modern author's collection/assessment method (PDF9 / printed8); the latter
is a table of contents (PDF184–185 / printed183–184). These bibliographic
facts are not parenting evidence, chapter proof or verified guidance.

Used the existing `review_en_parity.py unpublish --with-source` tool for exactly
these two pairs. Both AR and EN files were recoverably moved into
`ops/data/en_unpublished/kb_units_source/` and `kb_units/`; all four file bytes
were preserved. Reasons are in `ops/data/en_unpublished/MANIFEST.json`.
The two primary proof files remain under `source_recovery/`, outside loaders.
Only four index entries, two queue entries and two stale `judged_faithful`
entries were removed. No curriculum anchors were replaced or files changed.
The old proposal in `SOURCE_RECOVERY_NEXTBATCH_AUDIT_OCT7.md` is now implemented.

Final authored count: **1389 files / 1389 unique index rows**. All 1377 retained
index rows outside the six approved pairs remain equal to the phase base;
the twelve changed sizes equal their actual source-excerpt lengths. Default
retrieval loads none of the four quarantined IDs. Global parity inventory:
**347 translated KB units: 341 valid, 6 held**.

Remaining source queue keys:

- `isl-c0936200__en`
- `isl-d6faddeb__en`
- `isl-f6bbab53__en`
- `isl-f782f2ed__en`
- `isl-fb04bcd3__en`
- `isl-fe2f3c39__en`

The only other queue entry is unchanged `adhkar:family_adhkar`, category
`awaiting-review`. Every unrelated queue and faithfulness verdict is preserved.

## Semantic answer cache validity

The old cache key hashes the question/scope, not the KB. Both assistant paths
look up answers before `_ensure_index`, so the existing rebuild-triggered
purge alone cannot protect the first cached response after a source removal.

Added one nullable `kb_revision` column with an in-place legacy migration.
Store records `retrieval._fingerprint(load_default_knowledge_units())`;
both exact and semantic queries require that same current serving-corpus
fingerprint. Legacy rows without a revision cannot hit. Computing this guard
does not initialize an embedding model or index. Source removal or text
revision therefore blocks the frozen answer before rebuild/purge, including
when purge fails. Existing retention, question scoping and purge paths remain. A native guard
probe took 127 ms for the current corpus and confirmed no embedder/index
initialization; legacy cache entries now miss until regenerated.

Regression tests first failed correctly on the six stale-cache cases
(**6 failed, 1 passed; exit 1**). With the guard and quarantine,
**28 tests passed; exit 0**, covering exact/semantic hits for both removed
sources, changed source text, legacy rows, default-loader exclusion, existing
cache behavior, index-purge/seed wiring and cached-answer retention.
All embedding calls were stubbed in the tests; no models/build/emulator ran.
Ruff and whitespace checks passed. Both approval cherry commits used normal
commit hooks; the final quarantine/cache commit also uses normal hooks.

## New PR paths

The full comparison to the PR60 tree is in
`SOURCE_COMPLETION_CHANGED_PATHS_OCT7.txt`, including earlier six-pair work.
Main additions/changes in this phase:

- `backend/app/services/answer_cache.py`
- `backend/tests/test_answer_cache_source_revision.py`
- Six accepted AR/EN pairs and their source proofs under `knowledge_base/units/`
  and `ops/data/kb_fidelity/source_recovery/`
- Both nonknowledge AR/EN pairs moved to `ops/data/en_unpublished/`
- `knowledge_base/units_index.json`, `ops/data/en_parity_queue.json`,
  `ops/data/en_unpublished/MANIFEST.json`, `ops/data/kb_fidelity/judged_faithful.json`
- Committed actual review JSON/reports for both batches and this closeout

Primary dirty checkout and other managed worktrees were untouched. No push,
deployment, emulator, application build or human approval. PR60 merge
`5d566611` has the same tree as the branch's `e20fe437` base; no rebase needed
to inspect the change relative to that merged content.
