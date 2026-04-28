# Phase 3: Prod Supabase Project - Research

**Researched:** 2026-04-28
**Domain:** Supabase project provisioning, CLI migration apply, Storage policies, idempotent KB seed, secrets capture
**Confidence:** HIGH

## Summary

Phase 3 stands up `boardgame-rag-prod` on Supabase free tier and applies the existing 24-migration contract via `supabase db push`, then runs `python -m scripts.seed_default_kb` from the local backend venv against prod creds loaded from a gitignored `.env.prod`. Almost every gray area is already locked in CONTEXT.md; the planner's job is to translate decisions D-01..D-20 into 1–2 plans plus a small reusable verification script.

The only real research surface left is: (a) reconciling the integer-prefixed migration filenames (`001_…`–`024_…`) with Supabase CLI's expected `<timestamp>_name.sql` format (D-03 — three viable paths confirmed below), and (b) noting that `.gitignore` currently lists `.env` literally, NOT `.env*`, so `.env.prod` is NOT covered today and a one-line patch is mandatory before the file is created on disk.

**Primary recommendation:** Path A (rename in-place to timestamp prefixes preserving lexical order, single big diff commit) is the cleanest; the row IDs in `supabase_migrations.schema_migrations` then are the timestamps and `supabase migration list --linked` is fully functional going forward. Path C (`--include-all`) works for one-shot apply but leaves integer-prefixed version IDs in the remote history table and makes future drift detection awkward. Document the choice in 03-01-PLAN.md.

## User Constraints (from CONTEXT.md)

### Locked Decisions

**Migration apply method**
- D-01: Use Supabase CLI: `supabase link --project-ref <prod-ref>` then `supabase db push`. Tracked in `supabase_migrations.schema_migrations`. Replaces dev's Dashboard SQL Editor flow.
- D-02: Run `supabase init` and commit `supabase/config.toml`. Long-term CLI ops bootstrap. Keep python seed regardless of any `seed.sql` mechanism.
- D-03: Migration filename strategy = planner's call (rename / `migration repair` / `--include-all`). Document choice in plan.

**Run-all bundle**
- D-04: Move `supabase/migrations/run_all_module2.sql` → `supabase/legacy/run_all_module2.sql` before `db push`.

**pgvector + ltree**
- D-05: Rely on in-repo migrations 004 (vector) and 016 (ltree). Both idempotent. No dashboard toggle.
- D-06: Verify post-push: `SELECT extname FROM pg_extension WHERE extname IN ('vector','ltree');` returns both rows.

**Migration verification (success criterion #2)**
- D-07: Two-layer ("Recommended Plus") — schema_migrations row count match + smoke schema check (extensions + key tables + key RPCs).
- D-08: Bundle verification as a standalone reusable script. Planner picks bash/psql vs python/supabase-py.

**Storage bucket + policies**
- D-09: Migration 007 declares bucket + 3 RLS policies. `supabase db push` reapplies. Verify via `storage.buckets` + `pg_policies`.

**Seed execution**
- D-10: Run `python -m scripts.seed_default_kb` from local backend venv. NOT inside Phase 2 Docker. NOT post-Phase-4 on Fly.
- D-11: Prod env via gitignored `.env.prod` at repo root. Holds prod URL, anon, service_role, plus `OPENROUTER_API_KEY` (seed embeds → costs). `.dockerignore` already covers `.env*`. Add `.env.prod` to `.gitignore` if not covered by existing pattern. **(See gotcha — current `.gitignore` only lists `.env`, NOT `.env*`.)**
- D-12: Loader = `ENV_FILE=.env.prod python -m scripts.seed_default_kb` or `dotenv -f .env.prod run -- ...`. Patch `backend/config.py` minimally if neither works.
- D-13: Seed is idempotent (per-game `check_duplicate` by content hash; folder lookup-before-create). Re-runs after partial fail are safe.
- D-14: Verify: `documents WHERE visibility='public'` ≥ 10; `folders WHERE visibility='public'` ≥ 11 (root + 10 game subfolders); `document_chunks` for those documents > 0.

**Project metadata**
- D-15: Region: closest to Fly target. Default `us-east-1` (`iad`) if Phase 4 region still TBD. Phase 4 must mirror.
- D-16: Project name: `boardgame-rag-prod` (mirrors LangSmith project string from Phase 7).
- D-17: Org: developer's existing default Supabase org (free tier).

**Secrets capture (success criterion #5)**
- D-18: 1Password entry titled `Supabase — boardgame-rag-prod`, fields: `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `DB_PASSWORD`, `PROJECT_REF`.
- D-19: Repo gets nothing. `.env.prod` is working copy; 1Password is source of truth.

**Dev project preserved**
- D-20: Dev `.env` and dev project not edited. `supabase unlink` after `db push` as final cleanup if developer wants the local checkout back to "no project linked" state.

### Claude's Discretion

- Migration filename/timestamp strategy (D-03): planner picks rename vs `migration repair` vs `--include-all`.
- Verification script language (D-08): bash/psql vs python/supabase-py — pick whichever is shorter.
- Optional `Makefile` targets (`make seed-prod`, `make verify-prod`).
- Whether to commit `.env.example.prod` template stub.
- Exact dotenv loading patch in `backend/config.py` (D-12) — minimum diff to honor an `ENV_FILE` override without breaking dev.

### Deferred Ideas (OUT OF SCOPE)

- DB snapshot/backup automation
- pg_cron nightly demo-user reset (v1.2+)
- Multi-region / read replicas
- Custom `DOCLING_CACHE_DIR` for prod (Phase 2 deferred)
- Anon-key rotation policy
- Fly volume mount for Docling cache (Phase 4)
- Supabase pause-prevention via `/api/health` (Phase 7 OBS-04)
- Seed-from-Phase-2-image variant (rejected, D-10)

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DEPLOY-03 | Developer has a dedicated prod Supabase project with all migrations applied in order, pgvector enabled, Storage bucket policies applied, and default board game KB seeded | All five success criteria addressed in this research: project provisioning (§Standard Stack), `supabase link`/`db push` flow (§Architecture Patterns), bucket policies via migration 007 (§Standard Stack), idempotent seed via `seed_default_kb.py` (§Code Examples), 1Password secret capture (§User Constraints D-18) |

## Standard Stack

### Core
| Library / Tool | Version | Purpose | Why Standard |
|---------------|---------|---------|--------------|
| Supabase CLI | latest stable (1.x+) | Link prod project, run `db push`, manage migrations | The official CLI is the only first-class apply path that records to `supabase_migrations.schema_migrations` for drift detection |
| `supabase-py` | 2.13.0 (already pinned) | Python client for seed (service-role) | Already in `backend/requirements.txt`; same client `get_supabase()` returns; no new dep |
| `pydantic-settings` | 2.9.1 (already pinned) | Load `.env.prod` for seed run | Already in use in `backend/config.py`; one-line `env_file` override is enough |
| `python-dotenv` | 1.1.0 (already pinned) | `load_dotenv()` in `backend/config.py` | Already imported; can swap path based on `ENV_FILE` env |

### Supporting
| Tool | Version | Purpose | When to Use |
|------|---------|---------|-------------|
| `psql` (PostgreSQL client) | 14+ | Optional smoke verification queries | If planner chooses bash/psql verify script (D-08); needs `DB_PASSWORD` from 1Password |
| 1Password (or Bitwarden) | — | Secrets capture per D-18 | Mandatory for success criterion #5 |
| `npm i -g supabase` or `brew install supabase/tap/supabase` | latest | Install the CLI | Pick whichever the developer's machine already supports |

### Alternatives Considered
| Instead of | Could Use | Tradeoff (rejected) |
|------------|-----------|---------------------|
| `supabase db push` | Dashboard SQL Editor paste 001→024 | Rejected by D-01 — no `schema_migrations` row → no drift detection later |
| `supabase db push` | Single concatenated SQL via `psql` | Rejected by D-01 — same problem; harder to repeat for future migrations |
| Local venv seed | Phase 2 Docker image seed | Rejected by D-10 — couples Phase 3 to image build |
| Local venv seed | One-off Fly machine post-deploy | Rejected by D-10 — breaks ROADMAP order; Phase 4 doesn't exist yet |

**Installation (Supabase CLI):**
```bash
# Windows (the dev's platform, per env): scoop or pre-built binary
scoop bucket add supabase https://github.com/supabase/scoop-bucket.git
scoop install supabase
# Or download release binary from https://github.com/supabase/cli/releases
```

**Version verification:**
```bash
supabase --version          # confirm CLI installed
supabase migration list --linked  # post-link: confirms remote schema_migrations is reachable
```

## Architecture Patterns

### Recommended Project Structure
```
.
├── .env.prod                       # gitignored, populated from 1Password (NEW, on disk only)
├── .gitignore                      # ADD `.env*` (current only lists `.env` literal)
├── supabase/
│   ├── config.toml                 # NEW — created by `supabase init` (D-02)
│   ├── migrations/                 # 24 *.sql files, run_all_module2.sql REMOVED
│   │   ├── 001_create_threads.sql            # OR renamed to <timestamp>_create_threads.sql (D-03 path A)
│   │   ├── …
│   │   └── 024_add_tools_used_to_messages.sql
│   └── legacy/                     # NEW — D-04
│       └── run_all_module2.sql     # MOVED here from migrations/
├── backend/
│   ├── config.py                   # patched: load_dotenv(os.environ.get("ENV_FILE", ".env"))
│   └── scripts/
│       └── seed_default_kb.py      # unchanged
└── scripts/                        # NEW (or backend/scripts/) — verification harness
    └── verify_prod_schema.{sh|py}  # D-07 + D-08, reusable for future drift checks
```

### Pattern 1: Link + Push (the canonical D-01 flow)
**What:** Authenticate the CLI, link the local checkout to the prod project, push migrations, verify via `migration list --linked`.
**When to use:** First-time apply (this phase) and every future migration after.
**Example:**
```bash
# 1. Auth (one-time per machine)
supabase login

# 2. Link this repo to the prod project (creates supabase/.temp/, doesn't commit)
supabase link --project-ref <prod-ref>
# Prompts for DB password — paste from 1Password Supabase — boardgame-rag-prod

# 3. Push all migrations
supabase db push
# OR if filenames not yet timestamp-prefixed:
supabase db push --include-all

# 4. Verify
supabase migration list --linked
# Expect: 24 rows under both Local and Remote columns, all in sync
```

### Pattern 2: Filename strategy decision (D-03)

| Path | What | Pro | Con |
|------|------|-----|-----|
| **A. Rename to timestamps** | `001_create_threads.sql` → `20240301000001_create_threads.sql` (etc., preserving order via monotonic timestamps) | Clean go-forward; `supabase migration list` works fully; future `supabase migration new` files line up | Single large rename diff; touches 24 files |
| **B. `supabase migration repair --status applied <version>` per file** | Apply schema manually OR via psql once, then mark each integer-versioned row as applied | No file renames | Tedious (24 repairs); leaves integer version IDs in remote table; non-standard |
| **C. `supabase db push --include-all`** | One command applies all migrations not in remote history regardless of name | Zero-touch on filenames | Remote `schema_migrations` rows have integer IDs; future timestamp-prefixed migrations sort lexically AFTER `024_…` (which works), but mixed history is ugly; `migration list --linked` may flag mismatches |

**Recommendation:** Path A. The rename is one commit; everything downstream is clean. Suggested mapping = preserve numeric order with synthetic timestamps anchored at the dev project's known apply dates or simply monotonically generated `2024030100000<N>_originalname.sql`. Document the mapping table in 03-01-PLAN.md.

### Pattern 3: ENV_FILE override in `backend/config.py` (D-12)
**What:** Smallest patch that lets the seed pick up `.env.prod` instead of `.env` without breaking dev.
**Example:**
```python
# backend/config.py:7 — current
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

# After patch
env_file_name = os.environ.get("ENV_FILE", ".env")
load_dotenv(os.path.join(os.path.dirname(__file__), "..", env_file_name))
```
Then: `ENV_FILE=.env.prod python -m scripts.seed_default_kb` (works from `backend/` venv).

### Pattern 4: Idempotent seed re-run (D-13, validated against `backend/scripts/seed_default_kb.py`)
**What:** Seed checks `content_hash` per game and folder existence per game name before insert.
**When to use:** After partial failure mid-run (rate limit, network blip) — just re-invoke. Already-seeded games print `Skipping <game> (already seeded)`.
**Code reference:** `backend/scripts/seed_default_kb.py:99-103` (`check_duplicate` gate); `:53-62` (folder lookup-before-create).

### Pattern 5: Two-layer schema verification (D-07)
**What:** Reusable script that asserts both row count and structural shape after `db push`.
**Example (Python; pick this OR bash/psql):**
```python
# scripts/verify_prod_schema.py — D-07 + D-08
import os, sys
from supabase import create_client

REQUIRED_EXTENSIONS = {"vector", "ltree"}
REQUIRED_TABLES = {"documents", "document_chunks", "folders", "messages", "threads"}
REQUIRED_RPCS = {
    "match_document_chunks", "keyword_search_chunks",
    "kb_grep_regex", "kb_glob", "execute_readonly_query",
}
REQUIRED_BUCKET = "documents"
REQUIRED_STORAGE_POLICIES = {
    "Users can upload documents",
    "Users can read own documents",
    "Users can delete own documents",
}
EXPECTED_MIGRATION_COUNT = 24  # D-07 layer 1

def verify(supabase):
    failures = []
    # Layer 1: migration row count
    rows = supabase.rpc("execute_readonly_query", {
        "query_text": "SELECT count(*) AS c FROM supabase_migrations.schema_migrations"
    }).execute().data
    if rows[0]["c"] != EXPECTED_MIGRATION_COUNT:
        failures.append(f"schema_migrations count={rows[0]['c']}, expected {EXPECTED_MIGRATION_COUNT}")

    # Layer 2: shape — extensions, tables, RPCs, bucket, policies, seed counts
    # ... (one query per category, fail-fast aggregation)
    return failures
```
Output: pass/fail list; exit code 0/1.

### Anti-Patterns to Avoid
- **Toggling `pgvector` from the dashboard before `db push`:** Migration 004 already does `CREATE EXTENSION IF NOT EXISTS vector`. Manual toggle creates a no-op pre-step that drifts from the migration source of truth. (D-05)
- **Creating the Storage bucket via Dashboard:** Migration 007 owns the bucket + 3 policies. Dashboard creation duplicates intent and risks RLS divergence. (D-09)
- **Running seed inside the Phase 2 Docker image with a mounted `.env.prod`:** Couples this phase to image build state. Rejected (D-10).
- **Putting `.env.prod` in the repo or as `.env.example.prod` containing real values:** Violates D-19. The optional template stub MUST contain placeholder strings only.
- **Skipping `supabase init` and just running `supabase link` + `db push`:** Works once but leaves no `config.toml` for future contributors. Rejected (D-02).
- **Running seed without `OPENROUTER_API_KEY` (or whichever embedding key is wired):** Seed processes each markdown through `process_document` → embedding API. Without the key, errors mid-run on the first chunk and leaves a partial document row.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Apply schema to prod | `psql -f` loop or hand-paste in dashboard | `supabase db push` | Records `schema_migrations`, enables drift detection, repeatable for future migrations (D-01) |
| Track which migrations applied | Custom tracking table | `supabase_migrations.schema_migrations` (Supabase-managed) | Built into CLI; `migration list --linked` reads it |
| Storage bucket + RLS in prod | Dashboard click + manual policy paste | Migration 007 (already exists) | Already a SQL migration; `db push` reapplies identically (D-09) |
| Idempotent seed | Custom dedup logic | Existing `check_duplicate` in `record_manager` + `seed_default_kb.py` flow | Already idempotent (D-13); per-game content hash + folder lookup-before-create |
| Prod env loading | Bespoke env merger | `ENV_FILE` override + existing `load_dotenv` in `backend/config.py` | One-line patch (D-12) |
| Seed scheduling | Cron / Fly machine job | One-shot `python -m scripts.seed_default_kb` | One-time stand-up; future re-seeds are rare and developer-triggered (D-10) |

**Key insight:** Every piece of infrastructure this phase needs is already built and tested in dev. The phase is configuration + a single CLI session + one Python invocation. Do not invent new tooling.

## Runtime State Inventory

> Phase 3 stands up new prod state from scratch — there is no pre-existing prod runtime to migrate. Inventory still applied for completeness because the seed touches stored data and the change touches local config files that aren't in git.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | New prod Supabase Postgres tables (empty until `db push`); new prod Storage bucket (empty until seed); 1Password vault (entry created at end of phase) | Create via `db push`; populate via `seed_default_kb`; create 1Password entry per D-18 |
| Live service config | Supabase project settings (region, name, org); CLI `supabase/.temp/` link state (gitignored by default) | Create project in dashboard (D-15..D-17); `supabase link --project-ref <ref>` writes to `supabase/.temp/`; optional `supabase unlink` cleanup per D-20 |
| OS-registered state | None — no OS-level registrations involved (no Task Scheduler, launchd, pm2). | None — verified by absence of any background daemon in the phase scope |
| Secrets/env vars | New on-disk file `.env.prod` at repo root (gitignored). 1Password entry `Supabase — boardgame-rag-prod` (5 fields per D-18). No code reference to `.env.prod` literal — loaded via `ENV_FILE` env var | Create `.env.prod` from 1Password values; verify `.gitignore` covers it (currently only `.env` literal — needs `.env*` patch) |
| Build artifacts / installed packages | Supabase CLI binary on developer machine (not committed). Nothing else built or compiled this phase. | Install CLI once if missing (`scoop install supabase` on Windows, or release binary) |

**The canonical question:** *After every file in the repo is updated, what runtime systems still have the old string cached, stored, or registered?*
**Answer:** None — Phase 3 introduces new state, doesn't rename existing state. The only carryover concern is the dev project's `.env` and dev Supabase project, which D-20 explicitly preserves.

## Common Pitfalls

### Pitfall 1: `.gitignore` doesn't cover `.env.prod`
**What goes wrong:** Developer creates `.env.prod` at repo root, commits, pushes prod service-role key to GitHub.
**Why it happens:** Current `.gitignore` (verified) contains exactly two lines: `venv/` and `.env`. The literal `.env` does NOT glob to `.env.prod`. CONTEXT.md D-11 assumes `.env*` is already covered — it is NOT.
**How to avoid:** First task in 03-01-PLAN.md must add `.env*` (or explicitly `.env.prod`) to `.gitignore`, then verify with `git check-ignore .env.prod`.
**Warning signs:** `git status` shows `.env.prod` as untracked file when it should be ignored.

### Pitfall 2: Migration filename mismatch silently changes behavior of `db push`
**What goes wrong:** `supabase db push` (without `--include-all`) compares local migrations to remote `schema_migrations` by timestamp. Integer-prefixed files have version `001`, `002`, etc. — these may parse as low timestamps and trigger unexpected "out of order" warnings, OR the CLI may simply not see them as eligible to push.
**Why it happens:** D-03 is unresolved at start of execution.
**How to avoid:** Resolve D-03 BEFORE first push. Recommend Path A (rename) per §Pattern 2. If Path C (`--include-all`) is chosen, run `supabase db push --include-all --dry-run` first and visually confirm all 24 files are listed.
**Warning signs:** `supabase db push` reports "0 migrations to apply" against a fresh prod project; `migration list --linked` shows local files but no remote rows.

### Pitfall 3: Seed runs without embedding API key, leaves partial document rows
**What goes wrong:** Seed inserts a `documents` row, then `process_document` calls embedding API, fails with 401, leaves a half-ingested document.
**Why it happens:** `.env.prod` is missing `OPENROUTER_API_KEY` (or whichever embedding key the prod config wires — see `backend/config.py` `embedding_api_key` and `resolved_embedding_api_key`).
**How to avoid:** 03-01-PLAN.md "prepare `.env.prod`" task explicitly enumerates required keys: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWT_SECRET`, `OPENROUTER_API_KEY` / `LLM_API_KEY`, `OPENAI_API_KEY` (for embeddings; or `EMBEDDING_API_KEY` if separate provider), and any other keys `Settings` reads at seed-relevant code paths. Smoke-test `.env.prod` by booting `python -c "from config import get_settings; print(get_settings().resolved_embedding_api_key[:6])"` before invoking seed.
**Warning signs:** First game's `process_document` raises 401/403; `documents` table has 1 row with `status='pending'` and no chunks.

### Pitfall 4: Seed's content hash treats dev-edited markdown as a new game
**What goes wrong:** Developer edits one of the 10 markdown files between dev seed and prod seed. Prod seed inserts the new version; success criterion #4 still passes (≥10 docs), but dev and prod have diverged content for that game.
**Why it happens:** `check_duplicate` keys on `(SYSTEM_USER_ID, content_hash)`. New hash → not a duplicate → fresh insert.
**How to avoid:** Before running seed against prod, `git status data/default-kb/` should be clean and the file mtimes should match the latest commit. Plan task: "verify default-kb is clean and committed".
**Warning signs:** `seed_default_kb` output shows 10 "Seeded" lines instead of "Skipping" (only matters if you expected dev content to be reused — but on a fresh prod project, all 10 SHOULD be Seeded; this pitfall only applies if re-running a partially-seeded prod with edited files mid-run).

### Pitfall 5: `supabase link` fails on Windows due to long path / temp dir issues
**What goes wrong:** CLI writes to `supabase/.temp/` and pulls schema; on long Windows paths, can hit MAX_PATH limits or symlink errors.
**Why it happens:** Windows default 260-char path limit + repo path is already deep (`C:\Users\56kbps\Desktop\Projects\VibeCoded Projects\AI Automators Masterclass\claude-code-agentic-rag-masterclass\` is ~110 chars before any subpath).
**How to avoid:** Run CLI commands from a shorter alias path if possible, or enable Windows long-path support (`git config --global core.longpaths true`, registry `LongPathsEnabled`). Plan task can include a smoke check: `supabase --version && supabase status` from the repo root before `link`.
**Warning signs:** `supabase link` errors with `path too long` or `cannot create file`.

### Pitfall 6: `supabase init` overwrites or conflicts with existing files
**What goes wrong:** `supabase init` creates `supabase/config.toml` AND wants to scaffold `supabase/seed.sql`, `supabase/functions/`, etc.
**Why it happens:** First-time init in a repo that already has a `supabase/migrations/` folder.
**How to avoid:** Run `supabase init` and then audit the diff — keep `config.toml`, discard or `.gitignore` any unwanted scaffolding. Or use `supabase init --workdir supabase` and confirm no destructive changes.
**Warning signs:** `git status` after init shows new directories that weren't intended (`supabase/functions/`, `supabase/seed.sql`).

### Pitfall 7: Free-tier Supabase project pauses after 7 days idle
**What goes wrong:** Phase 3 completes, then Phase 4 takes >7 days. Supabase pauses prod project. Phase 4's first request returns 5xx until manually unpaused.
**Why it happens:** Free-tier auto-pause.
**How to avoid:** Out of scope for Phase 3 (covered by Phase 7 OBS-04 `/api/health` DB touch). Just note it in 03-SUMMARY.md as a transition risk if Phase 4 is delayed.

## Code Examples

### Example 1: Full Phase 3 happy path (CLI + verify + seed)
```bash
# Source: .planning/phases/03-prod-supabase-project/03-CONTEXT.md (D-01..D-20)

# --- 1. Setup (one-time on developer machine) ---
supabase login

# --- 2. Repo prep (committed changes) ---
echo ".env*" >> .gitignore                              # Pitfall 1 fix
git mv supabase/migrations/run_all_module2.sql supabase/legacy/run_all_module2.sql  # D-04
supabase init                                           # D-02 — creates supabase/config.toml
# (Optional Path A — rename migrations to timestamp prefix; commit as one diff)

# --- 3. Create prod project (Supabase dashboard, manual one-time) ---
# Org: developer's default
# Name: boardgame-rag-prod (D-16)
# Region: us-east-1 / iad unless Phase 4 says otherwise (D-15)
# Capture: PROJECT_REF, DB_PASSWORD, SUPABASE_URL, anon key, service_role key → 1Password (D-18)

# --- 4. Populate .env.prod from 1Password (gitignored, on disk only) ---
cat > .env.prod <<'EOF'
SUPABASE_URL=https://<project-ref>.supabase.co
SUPABASE_SERVICE_ROLE_KEY=<from-1password>
SUPABASE_JWT_SECRET=<from-1password>
OPENROUTER_API_KEY=<from-1password>
OPENAI_API_KEY=<from-1password>           # for embeddings (or EMBEDDING_API_KEY if split)
LLM_API_KEY=<from-1password>
LLM_MODEL=<same-as-dev>
EOF

# --- 5. Link + push migrations ---
supabase link --project-ref <project-ref>             # D-01; prompts for DB_PASSWORD
supabase db push                                       # OR: supabase db push --include-all (D-03 path C)
supabase migration list --linked                       # confirm 24 rows local AND remote

# --- 6. Verify schema (D-07, D-08) ---
ENV_FILE=.env.prod python scripts/verify_prod_schema.py
# Expect: PASS — 24 migrations, 2 extensions, 5 tables, 5 RPCs, 1 bucket, 3 policies

# --- 7. Seed default KB (D-10..D-14) ---
cd backend && source venv/bin/activate
ENV_FILE=.env.prod python -m scripts.seed_default_kb
# Expect: "Seeded 10 games, skipped 0"

# --- 8. Verify seed (success criterion #4) ---
ENV_FILE=.env.prod python scripts/verify_prod_schema.py --include-seed-counts
# Expect: documents public ≥10, folders public ≥11, chunks > 0

# --- 9. Cleanup (D-20) ---
supabase unlink   # optional — restores "no project linked" state
```

### Example 2: `backend/config.py` ENV_FILE patch (D-12)
```python
# Source: backend/config.py:1-7 (current) → smallest diff to honor ENV_FILE

# BEFORE
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

# AFTER
_env_filename = os.environ.get("ENV_FILE", ".env")
load_dotenv(os.path.join(os.path.dirname(__file__), "..", _env_filename))
```
Side effects: zero in dev (default still `.env`); seed honors `ENV_FILE=.env.prod`.

### Example 3: Verification SQL (D-06, D-07, D-09, D-14)
```sql
-- Source: CONTEXT.md D-06..D-14 + supabase/migrations/007_create_storage_bucket.sql

-- D-06: extensions
SELECT extname FROM pg_extension WHERE extname IN ('vector','ltree') ORDER BY extname;
-- Expect: 2 rows: ltree, vector

-- D-07 layer 1: migration row count
SELECT count(*) FROM supabase_migrations.schema_migrations;
-- Expect: 24

-- D-07 layer 2: tables
SELECT table_name FROM information_schema.tables
 WHERE table_schema = 'public'
   AND table_name IN ('documents','document_chunks','folders','messages','threads');
-- Expect: 5 rows

-- D-07 layer 2: RPCs
SELECT proname FROM pg_proc
 WHERE proname IN ('match_document_chunks','keyword_search_chunks','kb_grep_regex','kb_glob','execute_readonly_query');
-- Expect: 5 rows

-- D-09: storage bucket
SELECT id, name, public FROM storage.buckets WHERE id = 'documents';
-- Expect: 1 row, public=false

-- D-09: storage policies
SELECT policyname FROM pg_policies
 WHERE schemaname = 'storage' AND tablename = 'objects'
   AND policyname IN ('Users can upload documents','Users can read own documents','Users can delete own documents');
-- Expect: 3 rows

-- D-14: seed counts (after seed runs)
SELECT count(*) FROM documents WHERE visibility = 'public';      -- ≥ 10
SELECT count(*) FROM folders   WHERE visibility = 'public';      -- ≥ 11 (root + 10 game subfolders)
SELECT count(*) FROM document_chunks
 WHERE document_id IN (SELECT id FROM documents WHERE visibility = 'public');  -- > 0
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Apply schema via Dashboard SQL Editor (dev's path) | `supabase link` + `supabase db push` | This phase forward | Drift detection via `schema_migrations`; future migrations are `git add` + `db push` |
| `run_all_module2.sql` bootstrap bundle | Per-file numbered migrations + CLI apply | This phase | Bundle moves to `supabase/legacy/` (D-04); historical reference only |
| Integer-prefixed migrations (`001_…`) | Timestamp-prefixed (`<YYYYMMDDHHMMSS>_…`) | D-03 path A (recommended) | Aligns with Supabase CLI convention; future `supabase migration new` files line up correctly |

**Deprecated/outdated:**
- Dashboard SQL Editor as primary apply path — superseded by CLI for prod.
- Manual bucket creation via Storage UI — superseded by migration 007 (already in repo).

## Open Questions

1. **Which embedding key does prod use — `OPENAI_API_KEY` or a separate `EMBEDDING_API_KEY` over an OpenRouter-compatible endpoint?**
   - What we know: `backend/config.py` `Settings` exposes `embedding_api_key` AND `resolved_embedding_api_key` (which falls back to `openai_api_key`). Dev `.env` content is gitignored, so we can't inspect it directly without running.
   - What's unclear: which env var is actually populated in dev today and therefore must be mirrored in `.env.prod`.
   - Recommendation: 03-01-PLAN.md task "build `.env.prod`" should grep `backend/config.py` for `_api_key` fields and require ALL relevant ones be filled before seed run. Or: add a tiny pre-flight check that imports `get_settings()` and asserts `resolved_embedding_api_key` is non-empty.

2. **Does `supabase db push` honor the integer-prefix files at all without `--include-all`?**
   - What we know: Official docs only document `<timestamp>_name.sql`. Behavior on integer-prefixed files is not documented.
   - What's unclear: whether `db push` (no flags) silently skips them, errors, or treats `001` as a low timestamp.
   - Recommendation: Test with `supabase db push --dry-run` AFTER linking to a throwaway free-tier project, OR commit to Path A (rename) up-front so the question doesn't arise. Path A is the safer plan-time choice.

3. **Will `supabase init` scaffold unwanted files (`seed.sql`, `functions/`, `extensions.sql`)?**
   - What we know: `supabase init` is documented as scaffolding `supabase/config.toml` plus optional supporting structure depending on flags.
   - What's unclear: exact files created in 2026-current CLI version.
   - Recommendation: After `init`, plan task does `git status` audit and explicitly commits only `config.toml`; any other generated files either get added to `.gitignore` or kept depending on intent. (CONTEXT.md D-02 says config.toml is committed; everything else is planner discretion.)

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Supabase CLI | `supabase init`, `link`, `db push`, `migration list` | TBD — verify with `supabase --version` | Latest stable expected | Install via scoop / brew / release binary |
| Python venv at `backend/venv/` | `python -m scripts.seed_default_kb` | Likely yes (used in dev) | 3.10+ | `python -m venv backend/venv && pip install -r backend/requirements.txt` |
| `git` | move `run_all_module2.sql`, `.gitignore` edit | ✓ (repo is git-tracked, confirmed via session env) | — | — |
| `psql` (optional) | If verify script chosen as bash/psql instead of python | Optional | 14+ ideal | Use python/supabase-py path instead (D-08 discretion) |
| 1Password (or any password manager) | Capture prod creds (D-18) | TBD — user-side, not machine-detectable | — | Bitwarden / KeePass — but D-18 specifically names 1Password |
| Network access to `*.supabase.co` and OpenRouter / OpenAI APIs | `db push`, seed embedding calls | Assumed yes | — | None — phase blocks without it |

**Missing dependencies with no fallback:**
- Supabase CLI — must install before phase can run.
- Network egress to Supabase + embedding provider — required.

**Missing dependencies with fallback:**
- `psql` — can substitute python/supabase-py for verification (D-08).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (per `backend/tests/` directory layout); but Phase 3 validation is primarily SQL/CLI assertions, not unit tests |
| Config file | None Phase-3-specific; reuse repo-root pytest if any (none detected at repo root) |
| Quick run command | `ENV_FILE=.env.prod python scripts/verify_prod_schema.py` (proposed verification harness, D-08) |
| Full suite command | Same — single script covering all 5 success criteria + seed counts |
| Phase gate | All 5 success criteria assertions PASS in `verify_prod_schema.py` before `/gsd:verify-work` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DEPLOY-03 #1 | Prod project exists with `pgvector` enabled | smoke | `psql -c "SELECT extname FROM pg_extension WHERE extname='vector'"` OR python equivalent | ❌ Wave 0 — `scripts/verify_prod_schema.py` |
| DEPLOY-03 #1 | `ltree` enabled (folders prerequisite, D-05) | smoke | `psql -c "SELECT extname FROM pg_extension WHERE extname='ltree'"` | ❌ Wave 0 — same script |
| DEPLOY-03 #2 | All 24 migrations applied | smoke | `SELECT count(*) FROM supabase_migrations.schema_migrations` returns 24 | ❌ Wave 0 — same script |
| DEPLOY-03 #2 | Migration list in sync local/remote | smoke | `supabase migration list --linked` shows 24 sync'd rows | ✓ (CLI built-in) |
| DEPLOY-03 #3 | `documents` Storage bucket exists | smoke | `SELECT id FROM storage.buckets WHERE id='documents'` returns 1 row | ❌ Wave 0 — same script |
| DEPLOY-03 #3 | 3 RLS policies on `storage.objects` | smoke | `pg_policies` query returns the 3 policy names | ❌ Wave 0 — same script |
| DEPLOY-03 #4 | Default KB seeded with ≥10 public games | integration | `SELECT count(*) FROM documents WHERE visibility='public'` ≥ 10 | ❌ Wave 0 — same script |
| DEPLOY-03 #4 | Folders seeded (root + 10 game subfolders) | integration | `SELECT count(*) FROM folders WHERE visibility='public'` ≥ 11 | ❌ Wave 0 — same script |
| DEPLOY-03 #4 | Chunks generated for seeded docs | integration | `SELECT count(*) FROM document_chunks WHERE document_id IN (...)` > 0 | ❌ Wave 0 — same script |
| DEPLOY-03 #5 | 1Password entry created with all 5 fields | manual | Human verification — open 1Password, confirm `Supabase — boardgame-rag-prod` entry has 5 populated fields | manual-only |
| DEPLOY-03 #5 | No prod secrets in repo | smoke | `git ls-files | xargs grep -l '<service-role-prefix>'` returns 0; `git check-ignore .env.prod` returns 0 (ignored) | ❌ Wave 0 — small bash check (could be inlined into the verify script as a pre-check) |

### Sampling Rate
- **Per task commit:** Run only the assertions affected by the task (e.g., after `db push`, run extension + migration count check).
- **Per wave merge:** `ENV_FILE=.env.prod python scripts/verify_prod_schema.py` — all assertions.
- **Phase gate:** Full verify script PASS + manual 1Password sanity check before `/gsd:verify-work`.

### Wave 0 Gaps
- [ ] `scripts/verify_prod_schema.py` (or `scripts/verify_prod_schema.sh`) — implements all D-06/D-07/D-09/D-14 SQL queries, exits 0/1, prints pass/fail per assertion. Reusable for future drift checks (D-08).
- [ ] `.gitignore` patch: add `.env*` so `.env.prod` is excluded (Pitfall 1).
- [ ] Optional: `Makefile` with `make seed-prod` + `make verify-prod` targets (Claude's discretion).
- [ ] Optional: `.env.example.prod` template stub with placeholder values, no real secrets (Claude's discretion).

*(Existing test infrastructure does not cover any of this — Phase 3 is infrastructure provisioning, not application logic.)*

## Project Constraints (from CLAUDE.md)

- **No LangChain / LangGraph** — N/A for Phase 3 (no LLM call code added).
- **Use Pydantic for structured LLM outputs** — N/A.
- **All tables need RLS — users only see their own data** — Migration 020 already enforces mixed-visibility RLS (public default KB + private user docs). Phase 3 reapplies via `db push`; no new tables.
- **Python backend must use a `venv` virtual environment** — Seed runs from `backend/venv/`, satisfied (D-10).
- **GSD Workflow Enforcement** — All Edits/Writes during Phase 3 must go through a GSD command (the `/gsd:execute-phase` flow). Direct ad-hoc edits forbidden.
- **Planning** — Plans saved to `.agent/plans/` (project rule). NOTE: this conflicts with the GSD layout `.planning/phases/03-…/03-XX-PLAN.md`. The GSD orchestrator path is the active convention used by this repo for v1.1; the planner should follow `.planning/phases/…` per current project state.
- **Test Credentials** — `ragtest1@gmail.com` / `testpass123` — relevant to Phase 6/8 demo flow, not Phase 3.

## Sources

### Primary (HIGH confidence)
- [Supabase CLI — `supabase db push` reference](https://supabase.com/docs/reference/cli/supabase-db-push) — confirmed flags: `--linked`, `--dry-run`, `--include-all`, `--include-seed`, `-p/--password`. Confirmed remote tracking table: `supabase_migrations.schema_migrations`.
- [Supabase CLI — `supabase migration` reference](https://supabase.com/docs/reference/cli/supabase-migration) — confirmed `migration repair --status applied|reverted <version>` and `migration list --linked`.
- [Supabase deployment — Database Migrations](https://supabase.com/docs/guides/deployment/database-migrations) — confirmed `supabase login` + `supabase link` + `supabase db push` flow.
- [Supabase Local Development overview](https://supabase.com/docs/guides/local-development/overview) — confirmed migration filename pattern `<timestamp>_name.sql`.
- Repo files (canonical): `supabase/migrations/004_enable_pgvector.sql`, `007_create_storage_bucket.sql`, `016_enable_ltree.sql`, `017_create_system_user.sql`, `018_create_folders_table.sql`, `020_update_rls_policies.sql`, `backend/scripts/seed_default_kb.py`, `backend/config.py`, `.gitignore` (current contents read directly).
- `.planning/phases/03-prod-supabase-project/03-CONTEXT.md` — all 20 user decisions.
- `.planning/REQUIREMENTS.md` — DEPLOY-03 definition.
- `.planning/ROADMAP.md` Phase 3 — 5 success criteria.

### Secondary (MEDIUM confidence)
- WebSearch results cross-verified against official Supabase docs for migration filename behavior and `db push --include-all` semantics.

### Tertiary (LOW confidence)
- None — all critical claims verified against either repo files or official Supabase docs.

## Metadata

**Confidence breakdown:**
- Standard stack (CLI, supabase-py, pydantic-settings): HIGH — pinned versions in repo + official CLI docs.
- Architecture patterns (link/push, ENV_FILE, idempotent seed): HIGH — verified against repo source files (`seed_default_kb.py`, `config.py`, `007_create_storage_bucket.sql`).
- Filename strategy (D-03 paths): MEDIUM — Path A and Path C are documented; Path B (`migration repair`) is documented but for a different use case (repairing drift, not bypassing filename convention). Planner should `--dry-run` whichever path is chosen.
- Pitfalls: HIGH for #1 (`.gitignore` literal `.env`, verified by reading file) and #3 (key requirements, verified by reading `backend/config.py` + `seed_default_kb.py`); MEDIUM for #2 and #5 (CLI behavior on edge cases — recommend dry-run to confirm).
- Open Q1 (which embedding key): MEDIUM — `config.py` exposes both options; dev `.env` not inspected.
- Open Q2 (db push without --include-all on integer-prefixed files): MEDIUM — undocumented; mitigated by recommending Path A.

**Research date:** 2026-04-28
**Valid until:** 2026-05-28 (30 days — Supabase CLI flag set is stable; only revisit if a new Supabase CLI major version ships)
