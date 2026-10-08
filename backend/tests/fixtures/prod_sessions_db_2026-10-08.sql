-- Production schema of ops/sessions.db (every table and index). Copied
-- 2026-10-08 from tg_backend, read-only:
--   sqlite3.connect('file:/app/ops/sessions.db?mode=ro', uri=True)
--   SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY tbl_name,type DESC,name
-- sqlite_sequence and the sqlite_autoindex_* entries (sql IS NULL) are created
-- by SQLite itself and are omitted. Production's schema_migrations ledger then
-- held llm_telemetry 1 (llm_calls) and 2 (usage_estimated). Schema only, no
-- rows. Regenerate the same way; do not hand-edit (project note
-- fixtures-must-be-copied-not-written).
CREATE TABLE answer_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            qhash TEXT UNIQUE,
            question_norm TEXT NOT NULL,
            age_group TEXT NOT NULL,
            domain TEXT NOT NULL,
            severity TEXT NOT NULL,
            answer TEXT NOT NULL,
            embedding TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            hit_count INTEGER DEFAULT 0
        , redacted INTEGER, kb_revision TEXT);
CREATE INDEX idx_answer_cache_scope ON answer_cache (age_group, domain);
CREATE TABLE bahouth_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cache_key TEXT UNIQUE,
            tool TEXT NOT NULL,
            arguments_json TEXT NOT NULL,
            result_json TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now')),
            hit_count INTEGER DEFAULT 0
        );
CREATE INDEX idx_bahouth_cache_lookup ON bahouth_cache (tool, cache_key);
CREATE TABLE blocked_fiqh_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question TEXT NOT NULL,
                rule_id TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now'))
            , redacted INTEGER);
CREATE TABLE llm_calls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT DEFAULT (datetime('now')),
                provider TEXT, model TEXT, latency_ms INTEGER,
                prompt_tokens INTEGER, completion_tokens INTEGER,
                streamed INTEGER, ok INTEGER
            , tier TEXT, route_reason TEXT, usage_estimated INTEGER NOT NULL DEFAULT 0);
CREATE TABLE query_rewrites (
                question_hash TEXT PRIMARY KEY, rewritten TEXT,
                ts TEXT DEFAULT (datetime('now')), redacted INTEGER);
CREATE TABLE retrieval_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT DEFAULT (datetime('now')),
                question TEXT, domains TEXT, rewritten_query TEXT,
                final_ids TEXT, distances TEXT, rerank_scores TEXT
            , redacted INTEGER);
CREATE TABLE schema_migrations (
    namespace TEXT NOT NULL,
    version INTEGER NOT NULL,
    name TEXT NOT NULL,
    checksum TEXT NOT NULL,
    applied_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY(namespace, version)
);
CREATE TABLE sessions (
            id TEXT PRIMARY KEY,
            ts TEXT,
            domain TEXT,
            behavior_type TEXT,
            age_group TEXT,
            severity TEXT,
            mode TEXT,
            needs_human_review INTEGER,
            reply_length INTEGER,
            retrieved_count INTEGER,
            flag TEXT
        );
CREATE TABLE tafsir_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cache_key TEXT UNIQUE,
            surah INTEGER NOT NULL,
            ayah INTEGER NOT NULL,
            source TEXT NOT NULL,
            attribution TEXT,
            text TEXT NOT NULL,
            footnotes_json TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            hit_count INTEGER DEFAULT 0
        );
CREATE INDEX idx_tafsir_cache_lookup ON tafsir_cache (surah, ayah, source);
