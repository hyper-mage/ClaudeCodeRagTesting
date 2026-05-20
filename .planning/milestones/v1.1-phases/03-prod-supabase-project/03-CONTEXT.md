# Phase 3: Prod Supabase Project - Context

**Gathered:** 2026-04-28
**Status:** Ready for planning

<domain>
## Phase Boundary

Stand up a dedicated production Supabase project, separate from dev, with the exact runtime contract the app expects: `pgvector` + `ltree` extensions, all 24 SQL migrations applied in order, Storage bucket `documents` with policies reapplied (declared in migration 007 — no dashboard click), and the default board game KB seeded (≥10 public games owned by the system user under the Board Games root folder). Prod `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, anon key, and DB password captured in 1Password under `Supabase — boardgame-rag-prod`. Dev project untouched throughout.

Out of scope for Phase 3 (deferred):
- `fly.toml` / Fly secrets (Phase 4)
- CORS allowlist with the CF Pages origin (Phase 6)
- Auth redirect URLs for prod frontend (Phase 6)
- LangSmith `boardgame-rag-prod` project wiring (Phase 7)
- Sentry, UptimeRobot, observability (Phase 7)
- Demo user seeding (Phase 8)
- Database backup / snapshot automation
- Supabase pause-prevention via /api/health touch (Phase 7, OBS-04)

</domain>

<decisions>
## Implementation Decisions

### Migration Apply Method
- **D-01:** Use Supabase CLI: `supabase link --project-ref <prod-ref>` followed by `supabase db push`. Tracks applications in `supabase_migrations.schema_migrations`, repeatable, version-controlled. Replaces dev's ad-hoc Dashboard SQL Editor flow.
- **D-02:** Run `supabase init` and commit `supabase/config.toml` to repo. Sets up the project for long-term CLI ops so future migrations land cleanly without re-bootstrapping. Optionally use Supabase's `seed.sql` mechanism — see D-08 caveat (we keep python seed regardless).
- **D-03:** Migration filename pattern is the planner's call: current files use integer prefix (`001_create_threads.sql` … `024_…`), but Supabase CLI expects timestamp prefix (`<YYYYMMDDHHMMSS>_name.sql`). Planner picks one of: (a) rename in-place to timestamps preserving order, (b) use `supabase migration repair` after push, or (c) `db push --include-all`. Whichever path keeps the 24 migrations in their existing dependency order is acceptable. Document the choice in 03-01-PLAN.md.

### Run-all bundle
- **D-04:** `supabase/migrations/run_all_module2.sql` moves to `supabase/legacy/run_all_module2.sql` before `db push`. Removes ambiguity from CLI's view, preserves the historical bootstrap artifact, single small commit. Update any docs/scripts referencing the old path.

### pgvector + ltree enablement
- **D-05:** Rely on in-repo migrations to enable extensions: `004_enable_pgvector.sql` (`CREATE EXTENSION IF NOT EXISTS vector`) and `016_enable_ltree.sql` (`CREATE EXTENSION IF NOT EXISTS ltree`). Both are idempotent; both run before any object that depends on them (005 documents, 018 folders). No manual dashboard toggle required.
- **D-06:** Verification post-push: `SELECT extname FROM pg_extension WHERE extname IN ('vector','ltree');` must return both rows.

### Migration verification (success criterion #2)
- **D-07:** Two-layer verify — "Recommended Plus":
  1. Row count: `SELECT count(*) FROM supabase_migrations.schema_migrations` matches `supabase migration list --linked --remote` count for migrations defined in `supabase/migrations/`.
  2. Smoke schema check: assert `pg_extension` has `vector` + `ltree`; `information_schema.tables` has `documents`, `document_chunks`, `folders`, `messages`, `threads`; key RPCs exist via `pg_proc` lookup (`match_document_chunks`, `keyword_search_chunks`, `kb_grep_regex`, `kb_glob`, `execute_readonly_query`).
- **D-08:** Bundle the verification as a small standalone script (planner's choice: bash/psql or python/supabase-py). Reusable for future "did prod schema drift?" checks. Output: pass/fail + list of present objects.

### Storage bucket + policies
- **D-09:** Migration `007_create_storage_bucket.sql` already does `INSERT INTO storage.buckets` and creates the three RLS policies on `storage.objects`. `supabase db push` applies it identically to dev. No dashboard step. Verification: `SELECT id, name, public FROM storage.buckets WHERE id='documents';` returns one row; `pg_policies` shows the three named policies (`Users can upload documents`, `Users can read own documents`, `Users can delete own documents`).

### Seed execution
- **D-10:** Run `python -m scripts.seed_default_kb` from the local backend venv (NOT inside the Phase 2 Docker image, NOT post-Phase-4 on Fly). Same script that works in dev, just with prod env loaded. Keeps Phase 3 independent of Phase 2 image build and decoupled from Phase 4's Fly deploy.
- **D-11:** Prod env is supplied via a gitignored `.env.prod` file at repo root. Developer pastes prod `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, anon key, plus `OPENROUTER_API_KEY` (seed processes documents via the ingestion pipeline → embedding calls). After seed completes, `.env.prod` may be left in place for re-runs but stays out of git. `.dockerignore` already covers `.env*`. Add `.env.prod` line to `.gitignore` if not already covered by the existing `.env*` pattern.
- **D-12:** Seed loader pattern: pydantic-settings reads from explicit env file. Either set `ENV_FILE=.env.prod python -m scripts.seed_default_kb` or invoke `dotenv -f .env.prod run -- python -m scripts.seed_default_kb` (planner picks based on what `backend/config.py` currently honors; if neither is supported, smallest patch is to allow `Settings(model_config=SettingsConfigDict(env_file=os.environ.get("ENV_FILE",".env")))`).
- **D-13:** Seed is idempotent (`check_duplicate` per-game via content hash; folder lookups before create). Re-runs on partial fail are safe — no special partial-fail tooling needed.
- **D-14:** Verification: `SELECT count(*) FROM documents WHERE visibility='public'` ≥ 10; `SELECT count(*) FROM folders WHERE visibility='public'` ≥ 11 (Board Games root + 10 game subfolders); `SELECT count(*) FROM document_chunks WHERE document_id IN (SELECT id FROM documents WHERE visibility='public')` > 0.

### Project metadata
- **D-15:** Region: pick Supabase region geographically closest to Fly target. Phase 4 must match. If Phase 4 region is still TBD at time of Phase 3 execution, pick `us-east-1` (`iad`) by default — covers the largest portfolio reviewer audience and matches Fly's most common free-tier region. Document the chosen region in 03 PLAN/SUMMARY so Phase 4 can mirror it.
- **D-16:** Project name: `boardgame-rag-prod`. Same string is reused as the LangSmith project name in Phase 7 (`boardgame-rag-prod`) for naming consistency across observability surfaces.
- **D-17:** Org: developer's existing default Supabase org (free tier).

### Secrets capture (success criterion #5)
- **D-18:** Password manager: 1Password entry titled `Supabase — boardgame-rag-prod`, with separate fields:
  - `SUPABASE_URL` (https://<project-ref>.supabase.co)
  - `SUPABASE_ANON_KEY`
  - `SUPABASE_SERVICE_ROLE_KEY`
  - `DB_PASSWORD` (Postgres direct connection password — useful for `psql` smoke checks)
  - `PROJECT_REF`
- **D-19:** Repo gets nothing. `.env.prod` on disk is the working copy; 1Password is the source of truth. README in Phase 8 references "see 1Password" not the values.

### Dev project preserved
- **D-20:** Dev `.env` and dev Supabase project are not edited during Phase 3. The CLI `link` is local-only — `supabase unlink` after `db push` if the developer wants the local checkout back to "no project linked" state. Planner notes the unlink in 03 PLAN as the final cleanup step.

### Claude's Discretion
- Migration filename/timestamp strategy (D-03): planner picks rename vs `migration repair` vs `--include-all` based on what produces the cleanest schema_migrations row set.
- Verification script language and exact query bundle (D-08): bash/psql vs python/supabase-py — pick whichever is shorter and less new dependency surface.
- Whether to add a tiny `Makefile` target (e.g., `make seed-prod`, `make verify-prod`) — nice-to-have, not required.
- `.env.prod` shape: a literal `.env.example.prod` template stub may be committed for documentation; or skipped if README's "see 1Password" suffices.
- Exact dotenv loading patch in `backend/config.py` if needed (D-12) — minimum diff that lets pydantic-settings honor an `ENV_FILE` override without breaking dev.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase contract
- `.planning/ROADMAP.md` §Phase 3: Prod Supabase Project — 5 success criteria
- `.planning/REQUIREMENTS.md` — DEPLOY-03 definition

### Prior-phase context (carry forward, do not re-plan)
- `.planning/phases/01-secrets-repo-hygiene/01-CONTEXT.md` §`.dockerignore Scope` (D-09) — `.env*` already excluded; `.env.prod` inherits exclusion. CORS env-driven allowlist already in place.
- `.planning/phases/02-dockerize-backend/02-CONTEXT.md` §Build Strategy — Phase 2 image is NOT used for the Phase 3 seed run (per D-10).

### Migrations (the contract being deployed)
- `supabase/migrations/004_enable_pgvector.sql` — pgvector enable; success criterion #1
- `supabase/migrations/007_create_storage_bucket.sql` — `documents` bucket + 3 RLS policies on `storage.objects`; success criterion #3
- `supabase/migrations/016_enable_ltree.sql` — ltree extension (folders prerequisite)
- `supabase/migrations/017_create_system_user.sql` — system user UUID `00000000-…` (seed owner)
- `supabase/migrations/018_create_folders_table.sql` — `folders` table + `Board Games` root UUID `a0000000-0000-0000-0000-000000000001` (seed parent folder)
- `supabase/migrations/020_update_rls_policies.sql` — mixed-visibility RLS (public default KB + private user docs)
- `supabase/migrations/` (full directory, files `001_…` through `024_…`) — apply in order, all 24
- `supabase/migrations/run_all_module2.sql` — moves to `supabase/legacy/` (D-04); not part of CLI apply

### Seed
- `backend/scripts/seed_default_kb.py` — idempotent seed; success criterion #4
- `data/default-kb/` — 10 markdown files (catan, ticket-to-ride, pandemic, carcassonne, 7-wonders, codenames, azul, splendor, dominion, wingspan)

### Source files this phase TOUCHES (small surface)
- `supabase/config.toml` — CREATE via `supabase init` (D-02)
- `supabase/legacy/run_all_module2.sql` — MOVED here (D-04)
- `.gitignore` — confirm `.env.prod` covered (likely already by `.env*`)
- `backend/config.py` — possibly patched to honor `ENV_FILE` env var (D-12)

### Source files this phase REFERENCES (do not modify)
- `backend/database.py` — `get_supabase()` reads `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY` from settings; nothing prod-specific needs to change
- `backend/services/ingestion_service.py` — `process_document` consumed by seed
- `backend/services/record_manager.py` — `check_duplicate` for seed idempotency

### Upstream docs
- https://supabase.com/docs/guides/cli/local-development — `supabase init`, `link`, `db push`
- https://supabase.com/docs/reference/cli/supabase-migration — migration commands incl. `repair`

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend/scripts/seed_default_kb.py` — already idempotent (per-game `check_duplicate` by content hash + folder lookup-before-create). Re-runnable safely against prod after partial failures.
- `backend/config.py` — pydantic-settings `Settings`. Same env var contract works for prod; only switch is which `.env*` file is loaded.
- `backend/database.py` `get_supabase()` — service-role client; bypasses RLS for server-side seed inserts. Identical behavior dev vs prod.
- Migrations 016/017/018 already declare ltree, system user, and `Board Games` root folder with the fixed UUID the seed expects. No drift between dev and prod once `db push` completes.

### Established Patterns
- All schema changes live in `supabase/migrations/` as numbered SQL files; dev was bootstrapped via Dashboard SQL Editor (per `run_all_module2.sql` comment). Phase 3 introduces CLI as the first-class apply path going forward.
- Storage bucket + policies declared in SQL migration (007) — not a manual dashboard step. `supabase db push` reapplies identically.
- System user owns all default KB rows (`user_id = 00000000-…`). Seed never touches `auth.users` — relies on migration 017 having created the row.

### Integration Points
- `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY` from `.env.prod` flow into `Settings` → `get_supabase()` → seed.
- After Phase 3, the same prod creds get pushed into `flyctl secrets` in Phase 4 (consumes from 1Password).
- After Phase 3, the prod `SUPABASE_URL` + `SUPABASE_ANON_KEY` get set as `VITE_SUPABASE_URL` + `VITE_SUPABASE_ANON_KEY` on Cloudflare Pages in Phase 5 (consumes from 1Password).

### Gotchas surfaced during scout
- Migration filenames are integer-prefixed (`001_…`), not timestamp-prefixed. Supabase CLI's default `db push` expects `<timestamp>_name.sql`. Planner must resolve via rename, `migration repair`, or `--include-all`. Choosing rename means a single big diff but a clean go-forward state. (D-03)
- `supabase/migrations/run_all_module2.sql` is a hand-rolled bundle, not a real migration. CLI may or may not skip it depending on apply mode. D-04 moves it to `supabase/legacy/` to remove ambiguity.
- Seed processes each markdown file through the FULL ingestion pipeline → embedding API calls → costs ~$0.001-0.01 per game depending on length. `OPENROUTER_API_KEY` (and the embedding provider key, whatever's wired) MUST be present in `.env.prod` or seed errors mid-run on the first chunk.
- Seed re-uploads use content hash for dedup; if the markdown file changes between dev seed and prod seed, prod will end up with both versions or only the newer one depending on `check_duplicate` semantics. Verify the 10 default markdowns are stable before prod seed.
- `backend/config.py:7` calls `load_dotenv()` from repo root (per Phase 1 context). If we add an `ENV_FILE` override path (D-12), make sure it composes with the existing `load_dotenv()` — easiest is to gate `load_dotenv(os.environ.get("ENV_FILE",".env"))`.
- ROADMAP success criterion #4 says "≥10 games" — 10 default KB markdowns map exactly. No headroom.

</code_context>

<specifics>
## Specific Ideas

- User picked Recommended on every gray area — low appetite for re-litigation. Stay close to the ROADMAP's plain reading and Supabase CLI defaults.
- User chose "Both" verification (D-07) — wants belt-and-suspenders for a one-shot prod stand-up, not a minimal happy-path check.
- User chose to commit `supabase init` + `config.toml` (D-02) — treats Phase 3 as setting up long-term CLI ops, not one-off ops. Future migrations should land via the same `supabase db push` path.
- 1Password (specifically) is the password manager target (D-18). Naming convention uses `boardgame-rag-prod` to mirror the LangSmith project string from Phase 7.

</specifics>

<deferred>
## Deferred Ideas

- DB snapshot/backup automation — not required for fresh prod project; revisit if data accumulates beyond seed
- pg_cron nightly demo-user reset — explicitly v1.2+ per REQUIREMENTS.md "Future Requirements"
- Multi-region / read replicas — out of scope, free-tier portfolio
- Custom `DOCLING_CACHE_DIR` for prod — Phase 2 deferred; not Phase 3's concern
- Anon-key rotation policy — out of scope
- Fly volume mount for Docling cache — Phase 4 decision
- Supabase project pause-prevention via `/api/health` DB touch — Phase 7 (OBS-04)
- Seed-from-Phase-2-image variant — rejected (D-10); revisit only if local venv path proves brittle in execution

</deferred>

---

*Phase: 03-prod-supabase-project*
*Context gathered: 2026-04-28*
