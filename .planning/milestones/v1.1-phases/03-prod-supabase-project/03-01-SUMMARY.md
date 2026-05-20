---
phase: 03-prod-supabase-project
plan: 01
subsystem: prod-infra
tags: [supabase, migrations, deploy, schema, rls, pgvector, ltree, pgcrypto]
requires: []
provides:
  - prod Supabase project provisioned (boardgame-rag-prod, ref ybehhhduhynsdujmxdzx, region us-east-1)
  - 24 migrations applied via `supabase db push` and recorded in `supabase_migrations.schema_migrations`
  - `supabase/config.toml` (CLI bootstrap)
  - `scripts/verify_prod_supabase.sh` reusable schema-verification harness
  - `.env*` gitignore widening (pre-empts secret leaks in 03-02)
  - `ENV_FILE` env-var override in `backend/config.py` (so 03-02 seed can target `.env.prod`)
affects:
  - supabase/migrations/* (renamed to YYYYMMDDHHMMSS_*.sql; 9 + 17 patched)
  - supabase/legacy/run_all_module2.sql (moved out of CLI's view)
  - .gitignore (`.env` -> `.env*`)
tech-stack:
  added: [Supabase CLI 2.95.4]
  patterns: [Supabase db push migrations, schema verify harness, env-file override pattern]
key-files:
  created:
    - supabase/config.toml
    - supabase/.gitignore
    - supabase/legacy/run_all_module2.sql (moved)
    - scripts/verify_prod_supabase.sh
  modified:
    - .gitignore
    - backend/config.py
    - supabase/migrations/20240301000009_fix_vector_dims_and_realtime.sql
    - supabase/migrations/20240301000017_create_system_user.sql
    - supabase/migrations/* (24 files renamed from NNN_*.sql to 20240301NNNNNN_*.sql)
decisions:
  - Path A migration rename (synthetic monotonic timestamp 20240301NNNNNN_*.sql)
  - pgcrypto explicitly enabled in `extensions` schema and schema-qualified in migration 17 (Supabase prod ships pgcrypto installed but not on default search_path)
  - No ivfflat index on document_chunks.embedding (pgvector caps ivfflat at 2000 dims; column is VECTOR(2048))
  - Project region: East US (North Virginia) / us-east-1 (D-15)
  - Project name: boardgame-rag-prod (D-16, exact)
metrics:
  duration: ~25 minutes (Tasks 6-8 only; Tasks 1-5 done in earlier session)
  completed: 2026-05-01
---

# Phase 3 Plan 01: Prod Supabase Project Bootstrap — Summary

One-liner: Provisioned the prod Supabase project `boardgame-rag-prod`, prepped the repo for first-class CLI ops (gitignore widen, `supabase init`, ENV_FILE override, migration rename to timestamp form, legacy bundle moved aside), and pushed all 24 migrations against the empty prod DB with two real-prod-only migration bug fixes uncovered along the way.

## What was done

**Tasks 1-5** (committed in earlier session):
- Task 1 — `40091e8` widen `.gitignore` to `.env*` (pre-empt 03-02 secret leak)
- Task 2 — `9a6f40c` add `scripts/verify_prod_supabase.sh` reusable harness
- Task 3 — `123ca4c` honor `ENV_FILE` env var override in `backend/config.py`
- Task 4 — `d5197b5` rename 24 migrations to `20240301NNNNNN_*.sql`, move `run_all_module2.sql` to `supabase/legacy/`
- Task 5 — manual: developer provisioned `boardgame-rag-prod` (ref `ybehhhduhynsdujmxdzx`, region us-east-1, free tier) and stored creds in 1Password; ran `supabase login` + `supabase link --project-ref ybehhhduhynsdujmxdzx`.

**Tasks 6-8** (this session):
- Task 6 — `db7c710` `supabase init` produced `supabase/config.toml` (project_id `claude-code-agentic-rag-masterclass`) and `supabase/.gitignore` (correctly excludes `.branches` and `.temp`). Migrations untouched.
- Task 7 — `supabase db push` applied all 24 migrations after two deviation fixes (see below). `supabase migration list --linked` shows all 24 rows synced local↔remote.
- Task 8 — Inline schema verification via `supabase db query --linked` (since `psql` is not installed in this shell): all 7 base checks PASS — see "Verify results" below. Formal `bash scripts/verify_prod_supabase.sh` run is gated on `.env.prod` being created with `DATABASE_URL` (developer step, also a precondition for plan 03-02).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Migration 9: ivfflat index recreate fails on VECTOR(2048)**
- Found during: Task 7 (`supabase db push` mid-stream)
- Issue: `20240301000009_fix_vector_dims_and_realtime.sql` runs `ALTER COLUMN embedding TYPE VECTOR(2048)` and then `CREATE INDEX ... USING ivfflat (embedding vector_cosine_ops)`. pgvector caps ivfflat at 2000 dimensions, so the CREATE INDEX errored with SQLSTATE 54000 (`column cannot have more than 2000 dimensions for ivfflat index`). Migration 10 already removes all embedding indexes deliberately ("No vector index — pgvector on Supabase limits indexes to 2000 dims"), so the index in 9 was always vestigial; it had silently survived in dev only because state had drifted, never on a fresh prod project.
- Fix: removed the failing `CREATE INDEX` from migration 9 and added a comment pointing to migration 10's rationale. Sequential scan handles the dataset size.
- Files modified: `supabase/migrations/20240301000009_fix_vector_dims_and_realtime.sql`
- Commit: `7300964`

**2. [Rule 1 - Bug] Migration 17: `gen_salt(unknown) does not exist` on prod**
- Found during: Task 7 (`supabase db push`)
- Issue: `20240301000017_create_system_user.sql` calls `gen_salt('bf')` and `crypt(...)` unqualified. Supabase prod projects ship `pgcrypto` installed in the `extensions` schema but NOT on the default search_path, so unqualified calls fail with SQLSTATE 42883. Dev projects often have looser search_path config and survived this.
- Fix: prepended `CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA extensions;` and schema-qualified both calls (`extensions.gen_salt`, `extensions.crypt`).
- Files modified: `supabase/migrations/20240301000017_create_system_user.sql`
- Commit: `7300964`

**3. [Rule 1 - Bug] Verify harness checked wrong RPC name (`kb_glob` vs `kb_glob_match`)**
- Found during: Task 8 inline verification
- Issue: `scripts/verify_prod_supabase.sh` `rpcs.kb` check listed `kb_glob`, but migration 23 defines the function as `kb_glob_match` (the Python wrapper `services.kb_tools_service.kb_glob` calls `db.rpc("kb_glob_match", ...)`). Result: count of 4 instead of 5 even though all RPCs were correctly applied.
- Fix: replaced `kb_glob` with `kb_glob_match` in the script's IN-list.
- Files modified: `scripts/verify_prod_supabase.sh`
- Commit: `1f3dad8`

### Out-of-scope but observed

- After deviation fix #1, dev DBs that have the historical 2048-dim ivfflat index will still carry it; nothing in this plan attempts to drop it on dev. Future drift check will surface this if needed.

## Verify results (inline, against linked prod DB)

Ran via `supabase db query --linked` (psql unavailable in shell; queries are byte-identical to the harness's checks):

```
ext.vector              = 1   PASS
ext.ltree               = 1   PASS
migrations.count        = 24  PASS
tables.core             = 5   PASS  (documents, document_chunks, folders, messages, threads)
rpcs.kb                 = 5   PASS  (match_document_chunks, keyword_search_chunks, kb_grep_regex, kb_glob_match, execute_readonly_query)
storage.bucket.documents = 1  PASS
storage.policies        = 3   PASS  (Users can upload documents, Users can read own documents, Users can delete own documents)
```

`supabase migration list --linked` shows all 24 migrations with both Local and Remote populated, names `20240301000001` through `20240301000024`, monotonic timestamps `2024-03-01 00:00:01`..`2024-03-01 00:00:24`.

## ROADMAP success-criteria status

- ✅ #1 — prod project exists separate from dev with `pgvector` enabled before migrations run (`ext.vector=1`)
- ✅ #2 — `supabase db push` applied all 24 migrations; `schema_migrations` count matches (`migrations.count=24`)
- ✅ #3 — `documents` bucket + 3 RLS policies live (`storage.bucket.documents=1`, `storage.policies=3`)
- ⏳ #4, #5 — land in plan 03-02 (seed)

## Hand-off note for plan 03-02

`.env.prod` is **not yet on disk**. Plan 03-02 starts by creating it at repo root with at minimum:

```
DATABASE_URL=postgresql://postgres:<DB_PASSWORD>@db.ybehhhduhynsdujmxdzx.supabase.co:5432/postgres
SUPABASE_URL=https://ybehhhduhynsdujmxdzx.supabase.co
SUPABASE_ANON_KEY=...
SUPABASE_SERVICE_ROLE_KEY=...
SUPABASE_JWT_SECRET=...
OPENAI_API_KEY=...           # or EMBEDDING_API_KEY for embeddings
LLM_API_KEY=...
LLM_MODEL=...
```

All values come from the 1Password entry **Supabase — boardgame-rag-prod** (D-18). The first thing 03-02 should do (after creating `.env.prod`) is run `bash scripts/verify_prod_supabase.sh` to formally close Task 8 of this plan, then proceed with seed via `ENV_FILE=.env.prod`.

`.env.prod` will be auto-ignored by the `.env*` rule added in Task 1.

The pooler URL in `supabase/.temp/pooler-url` is `postgresql://postgres.ybehhhduhynsdujmxdzx@aws-1-us-east-1.pooler.supabase.com:5432/postgres` — useful if direct DB connection has issues.

## Self-Check: PASSED

- `supabase/config.toml` — FOUND (committed in `db7c710`)
- `supabase/.gitignore` — FOUND (committed in `db7c710`)
- `supabase/migrations/` — 24 files, all `20240301NNNNNN_*.sql` pattern, no integer-prefixed remnants
- `supabase/legacy/run_all_module2.sql` — present (from `d5197b5`)
- `scripts/verify_prod_supabase.sh` — present, executable, syntax-valid
- Commit `db7c710` — FOUND
- Commit `7300964` — FOUND
- Commit `1f3dad8` — FOUND
- Prod schema: 24 migrations applied, 7/7 verify checks PASS inline
