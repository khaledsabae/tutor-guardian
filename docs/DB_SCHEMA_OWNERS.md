# DB schema owners (M17 inventory)

Who issues DDL against which SQLite file, what production actually has, and
which owners already go through the numbered runner
(`backend/app/db/migrations/runner.py`). Snapshot 2026-10-08.

**Production evidence.** Schema only, read-only (`file:/app/ops/<db>?mode=ro`
inside `tg_backend`, `SELECT type,name,tbl_name,sql FROM sqlite_master`), no
rows. Taken twice that day; the two dumps are identical. The sessions.db dump
is checked in as `backend/tests/fixtures/prod_sessions_db_2026-10-08.sql`; the
conversations.db dump stays in the private evidence directory. SQLite 3.46.1.
Regenerate them the same way. Do not write them by hand.

## The two physical databases

| file | version stamp | numbered-runner ledger (`schema_migrations`) |
|---|---|---|
| `ops/conversations.db` (`CONVERSATIONS_DB`) | table `schema_version` = **35**. `PRAGMA user_version` is **0**: the "core v35" stamp lives in a table, not in the pragma | none yet |
| `ops/sessions.db` (path hard-coded per service; one service reads it from `ANSWER_CACHE_DB`) | none | `llm_telemetry` 1 `llm_calls` and 2 `usage_estimated`. Both checksums match the source byte for byte. This change adds `tafsir_cache` 1 and `bahouth_cache` 1 |

## Owner inventory

An *owner* is a runtime function that issues `CREATE`/`ALTER`/`DROP` against a
production DB. There are 16, not counting the runner's own ledger. **3 are on
the runner**: telemetry, plus the two cache owners migrated here.

### ops/sessions.db: one owner per table, each opens its own connection

| # | table | owner function | runs | production shape | runner |
|---|---|---|---|---|---|
| 1 | `llm_calls` | `services/ai_gateway._ensure_telemetry_schema` | each telemetry write | 12 cols, incl. `tier`, `route_reason`, `usage_estimated INTEGER NOT NULL DEFAULT 0`; no `redacted` | ✅ `llm_telemetry` 0001+0002 |
| 2 | `tafsir_cache` | `services/tafsir_service._cache_conn` | each cache get/put | 10 cols, `UNIQUE(cache_key)`, `idx_tafsir_cache_lookup(surah,ayah,source)` | ✅ `tafsir_cache` 0001 |
| 3 | `bahouth_cache` | `services/quranic_linguistics_service._cache_conn` | each cache get/put | 7 cols, `UNIQUE(cache_key)`, `idx_bahouth_cache_lookup(tool,cache_key)` | ✅ `bahouth_cache` 0001 |
| 4 | `query_rewrites` | `services/query_rewriter._get_conn` | each rewrite lookup | 4 cols incl. `redacted`; TEXT PK `question_hash` | — |
| 5 | `sessions` | `services/session_logger._get_conn` | each logged turn | 11 cols, TEXT PK | — |
| 6 | `answer_cache` | `services/answer_cache._conn` (+`ALTER ADD kb_revision`, `idx_answer_cache_scope`) | each cache access | 12 cols incl. `redacted`, `kb_revision`; `UNIQUE(qhash)` | — |
| 7 | `blocked_fiqh_log` | `services/fiqh_guard._log_block` (+`retention.ensure_marker`) | each blocked question | 5 cols incl. `redacted` | — |
| 8 | `retrieval_log` | `services/retrieval.log_retrieval` (process flag `_log_schema_ready`) | first log per process | 9 cols incl. `redacted` | — |
| 9 | `fiqh_intent_shadow` | `services/fiqh_intent.report_shadow` | shadow mode only | **absent in production** (shadow mode has never run there) | — |
| 10 | `redacted` column on 4, 6, 7, 8 | `services/retention.ensure_marker` / `_purge(drop_unmarked=True)` | nightly retention | ⚠ if the marker column is missing, `_purge` **deletes every row** and then adds the column. A baseline for 4/6/7/8 must treat `redacted` as part of the shape | — |

### ops/conversations.db: one monolith plus satellites

| # | owner | tables | runs | notes |
|---|---|---|---|---|
| 11 | `db/init_db.init_db` with its 31 `_ensure_*` helpers in the same file | 49 of the 52 tables: `chat_sessions`, `chat_messages`, `api_tokens`, `user_feedback`, `child_profiles`, `lesson_progress`, `coach_tips`, `child_challenges`, `referral_codes`, `referrals`, `push_tokens`, `push_sends`, `parent_identities`, `identity_links`, `daily_login_streaks`, `child_daily_routines`, `routine_events`, `habits_value_events`, `habit_templates`, `user_backups`, `referral_clicks`, `referral_click_days`, `feedback_replies`, `child_screen_sessions`, `family_agreements`, `agreement_clauses`, `child_missions`, `child_licences`, `child_scenario_answers`, `child_web_claims`, `child_facts`, `followups`, `weekly_plans`, `child_memory_settings`, `device_proof_challenges`, `device_proof_sessions`, `device_proofs`, `device_alerts`, `donations`, `device_aliases`, `device_fold_log`, `program_settings`, `program_children`, `ramadan_fasting`, `ramadan_marks`, `prayer_journeys`, `milestone_alerts`, `erased_devices`, `schema_version` | app startup (`main.py`), `ops/scripts/migrate_schema_v27.sh`, `ops/tools/candidate_smoke.py` | Uses `executescript`, which COMMITs implicitly. Has destructive rebuilds: `_ensure_lesson_progress_child_key` (via `lesson_progress_new`), `_ensure_child_challenges_table` and `_active_key` (via `_old`/`_v27`), and `_ensure_donations_table` (`DROP TABLE donations` when its shape is wrong) |
| 12 | `db/init_db.ensure_device_twin_tables` | `device_aliases`, `device_fold_log` | also from `services/device_twins._fold_rows`, inside the fold transaction | Plain `execute` on purpose, so it can run inside a caller's transaction |
| 13 | `services/erased_devices.record` (`CREATE_TABLE`) | `erased_devices` | inside an erase | Same DDL as the v35 step |
| 14 | `services/coach_service._ensure_coach_tips_table` | `coach_tips` | each coach-tip read/write | **Duplicate owner**, with a different index set from `init_db._CREATE_COACH_TIPS` (see drift) |
| 15 | `routers/feedback._ensure_app_feedback_table` | `app_feedback` (+ looped `ALTER ADD`), `tg_updates_seen` | each feedback request | Not in `init_db` at all |
| 16 | `services/story_service._ensure_schema` | `story_cache` | each story access | Not in `init_db` at all |

Not owners:

* `db/migrations/v16_habit_templates.py` and `v20_feedback_replies.py` are
  legacy `executescript` + `UPDATE schema_version` modules. Nothing imports them.
* The ops reports (`ops/scripts/*report*.py`, `min_build.sh`,
  `runtime_readiness_report.py`) open their DBs with `mode=ro`.
* `backend/scripts/debug_coach.py` and `generate_coach_samples.py` only touch DBs in `/tmp`.

## Production drift: what a fresh build from today's code gets wrong

Method: run every owner on an empty pair of DBs, then compare
`table_xinfo`/`index_list` against production (evidence: `drift.py`, `drift.json`).

* **sessions.db**: no drift. Every table the owners create matches production.
  (`blocked_fiqh_log`/`retrieval_log` are created lazily on first write, and
  their DDL already includes `redacted`.)
* **conversations.db**: the same 52 tables on both sides, but 7 differ:
  * `chat_messages`: production **lacks `model` and `guardrail_version`**.
    `_ensure_chat_messages_columns` never adds them. Production's index is
    `(session_id)`; code builds `(session_id, created_at)`.
  * `user_feedback`: production has no `message_id`, and its `session_id` is
    nullable (code says `NOT NULL`). Production also has
    `ix_user_feedback_session`. `routers/feedback.py` already introspects the
    columns before it inserts.
  * `child_challenges`: production `domain` is nullable (code says
    `NOT NULL`). Production's index is named `ix_child_challenges_active`;
    code uses `ix_child_challenges_device_child`.
  * `coach_tips`: production has only `ix_coach_tips_device_date`. Code also
    creates `ix_coach_tips_device_child_date` and `ix_coach_tips_date`. Because
    `coach_service` created the table first, `init_db`'s guarded create never ran.
  * `api_tokens`, `child_profiles`, `habits_value_events`: same columns,
    different order (added later by `ALTER`). Harmless, unless a migration
    compares SQL text instead of `table_xinfo`.

Any conversations.db baseline must adopt *these* production shapes or refuse
them explicitly. It must not assume `init_db`'s DDL.

## Migration rules used here (and for the next owners)

1. One namespace per owner, inside the file that owner writes to. Each
   migration file is self-contained, so its SHA-256 checksum covers all of its
   behaviour.
2. Baseline = adopt-if-matches:
   * Columns are compared by affinity, NOT NULL, default and the hidden flag.
     Keys are compared by `index_list`/`pragma_index_xinfo`.
   * Extra columns are allowed if an INSERT that omits them still works.
   * A missing performance index is recreated.
   * Anything else raises `MigrationError` and leaves the DB unchanged.
     Nothing is rebuilt and nothing is dropped.
3. Fixtures are production's own DDL, copied from the read-only dump. Variants
   are derived from that text.
4. Before shipping a baseline, run its read-only `_check(..., complete=True)`
   against the live DB in `mode=ro`.
5. Known cost: the runner takes `BEGIN IMMEDIATE` on every connection open.
   The cache paths therefore now briefly take the sessions.db writer lock even
   on a read (`busy_timeout` 5000), as telemetry already did. The cache-hit and
   cache-put paths write anyway.

## Next owners, in order of risk

1. **sessions.db logs and caches:** `query_rewrites`, `sessions`,
   `blocked_fiqh_log`, `retrieval_log`, `answer_cache`. Each has a single
   owner. Their baselines must include `redacted` (and `kb_revision` for
   `answer_cache`); `retention.ensure_marker` should become a no-op validator,
   and `retrieval`'s process flag goes away.
2. **conversations.db satellites outside `init_db`'s version stamp:**
   `story_cache`, `app_feedback`/`tg_updates_seen`, `erased_devices`. These
   would be the first runner ledger in conversations.db.
3. **`coach_tips`:** merge the two owners into one baseline that accepts
   production's single index.
4. **The `init_db` monolith**, table by table. The destructive rebuild steps
   (`lesson_progress`, `child_challenges`, `donations`) come last, and each one
   needs its own backup and rollback plan.
