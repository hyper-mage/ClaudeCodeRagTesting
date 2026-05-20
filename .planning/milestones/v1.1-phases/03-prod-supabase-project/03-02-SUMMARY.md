---
phase: 03-prod-supabase-project
plan: 02
subsystem: database
tags: [supabase, prod, seed, default-kb, board-games, pgvector, ltree, env]

requires:
  - phase: 03-prod-supabase-project (plan 01)
    provides: prod Supabase project + 24 migrations + verify harness
provides:
  - Default board-game KB seeded into prod (10 documents, 11 public folders, 62 chunks)
  - `.env.prod` shape locked: backend reads `SUPABASE_URL` (not VITE_ prefix); both kept side-by-side for backend + frontend reuse
  - `supabase` CLI unlinked from prod (D-20 cleanup state)
  - 1Password entry `Supabase — boardgame-rag-prod` is canonical source of prod creds (manual confirmation)
affects: [04-fly-deploy, 05-frontend-deploy, 06-agent-tooling]

tech-stack:
  added: []
  patterns:
    - "ENV_FILE=.env.prod overrides backend/config.py dotenv path for prod ops"
    - "Idempotent seed via content-hash dedup (D-13) — re-runs safe"

key-files:
  created:
    - .planning/phases/03-prod-supabase-project/03-02-SUMMARY.md
  modified:
    - .env.prod (gitignored — added SUPABASE_URL/SUPABASE_ANON_KEY un-prefixed for backend Settings)

key-decisions:
  - ".env.prod must include un-prefixed SUPABASE_URL/SUPABASE_ANON_KEY in addition to VITE_ prefixed copies; backend Settings reads un-prefixed names"
  - "Seed metadata-extraction warnings are non-fatal; default DocumentMetadata used when LLM returns invalid document_type literal — does not affect chunk ingestion"

patterns-established:
  - "Prod seed pattern: cd backend && ENV_FILE=.env.prod ./venv/Scripts/python.exe -m scripts.seed_default_kb"
  - "Prod verify pattern (Windows): PATH augmented with scoop psql then bash scripts/verify_prod_supabase.sh --include-seed"

requirements-completed: [DEPLOY-03]

duration: ~30min
completed: 2026-05-03
---

# Phase 3 Plan 2: Seed default KB to prod and lock secrets

**Default board-game KB seeded into prod Supabase: 10 documents, 11 public folders, 62 chunks. CLI unlinked. .env.prod backend var names corrected.**

## Performance

- **Duration:** ~30 min
- **Started:** 2026-05-03T20:12:20Z
- **Completed:** 2026-05-04T00:43:58Z (wall clock includes user-side checkpoint waits)
- **Tasks:** 3 (1 human-action checkpoint, 1 auto, 1 human-verify checkpoint w/ automation done by Claude)
- **Files modified:** 1 (`.env.prod` — gitignored, never committed)

## Accomplishments

- Prod default KB live: 10 board-game documents (Catan, Ticket to Ride, Pandemic, Carcassonne, 7 Wonders, Codenames, Azul, Splendor, Dominion, Wingspan), 11 public folders (Board Games root + 10 game subfolders), 62 chunks total
- Verify harness with `--include-seed` returns `VERIFY OK` (10/10 PASS)
- Zero half-ingested rows: `SELECT count(*) FROM documents WHERE status IN ('pending','failed') AND visibility='public'` = 0
- Anti-leak grep clean: zero JWT-shaped tokens in tracked repo outside `.planning/` (where they appear only as documentation patterns, not real values)
- `supabase unlink` ran cleanly: `supabase/.temp/project-ref` removed
- ROADMAP success criteria #4 (default KB seeded) and #5 (creds in 1Password — pending user confirmation step) addressed

## Seed details

- **Run type:** Fresh run (10 Seeded, 0 Skipping). Idempotency confirmed in script logic; not exercised this run.
- **Counts (post-seed):**
  - `documents WHERE visibility='public'` = 10
  - `folders WHERE visibility='public'` = 11
  - `document_chunks` for those documents = 62
  - half-ingested (`status IN ('pending','failed')`) = 0

## Task Commits

1. **Task 1: Populate .env.prod from 1Password** — no commit (file is gitignored). Smoke test passed: `OK https://ybehhhduhynsdujmxdzx.supabase.co embedding_key_prefix= sk-or-`
2. **Task 2: Run seed and verify counts** — no repo changes; seed writes only to prod DB. Verify printed `VERIFY OK`.
3. **Task 3: Confirm 1Password + unlink CLI** — automated portions (anti-leak grep, `supabase unlink`) done; 1Password manual confirmation deferred to user.

**Plan metadata commit:** to be created after this SUMMARY (along with STATE.md / ROADMAP.md updates).

## Files Created/Modified

- `.env.prod` (gitignored, on-disk only) — added un-prefixed `SUPABASE_URL` and `SUPABASE_ANON_KEY` lines beside the existing `VITE_*` versions so `backend/config.py` Settings can load them
- `.planning/phases/03-prod-supabase-project/03-02-SUMMARY.md` — this summary

## Decisions Made

- **Keep both VITE_ and un-prefixed Supabase URL/anon key in `.env.prod`:** backend `Settings` reads `SUPABASE_URL`/`SUPABASE_ANON_KEY`; frontend Vite reads `VITE_SUPABASE_URL`/`VITE_SUPABASE_ANON_KEY`. Single env file used for both contexts during prod ops.
- **Seed metadata warnings tolerated:** LLM occasionally returns invalid `document_type` literals (e.g., ":", ", ", ": tutorial"). Existing `extract_metadata_safe()` falls back to `DocumentMetadata()` defaults; chunk ingestion proceeds correctly. Not a blocker for Phase 3.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Backend Settings missing `SUPABASE_URL`/`SUPABASE_ANON_KEY` in `.env.prod`**
- **Found during:** Task 1 smoke test
- **Issue:** `.env.prod` was populated from dev `.env` and contained only `VITE_SUPABASE_URL` / `VITE_SUPABASE_ANON_KEY`. Backend `backend/config.py` Settings class reads `supabase_url` and `supabase_anon_key` (un-prefixed). Without those names present, `pydantic-settings` defaulted to empty string, smoke test asserted on `s.supabase_url.startswith('https://')` and failed.
- **Fix:** Appended `SUPABASE_URL=` and `SUPABASE_ANON_KEY=` lines to `.env.prod` with the same values as the `VITE_*` lines.
- **Files modified:** `.env.prod` (gitignored)
- **Verification:** Smoke test now prints `OK https://ybehhhduhynsdujmxdzx.supabase.co embedding_key_prefix= sk-or-`. Full seed + verify-with-seed succeed downstream.
- **Committed in:** N/A (file is gitignored)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** No scope creep; fix was prerequisite for the seed even running. No code or migration change. Should be reflected back into Phase 4 (Fly secrets) and Phase 5 (Cloudflare/Pages frontend) so both naming conventions are kept in sync going forward.

## Issues Encountered

- **psql not on PATH in Git Bash subshell:** scoop's `postgresql` install puts `psql.exe` at `C:/Users/56kbps/scoop/apps/postgresql/current/bin/psql.exe`, but Git Bash launched from a tool subshell did not inherit that PATH. Resolved by prefixing `PATH="/c/Users/56kbps/scoop/apps/postgresql/current/bin:$PATH"` to the verify invocation. Documented for Windows operators.
- **Seed metadata extraction LLM warnings:** non-fatal (see Decisions); `extract_metadata_safe()` falls back. No data integrity impact.

## 1Password entry shape (manual confirmation deferred)

Expected fields per D-18 (values NOT recorded here):

- `SUPABASE_URL` — `https://ybehhhduhynsdujmxdzx.supabase.co`
- `SUPABASE_ANON_KEY`
- `SUPABASE_SERVICE_ROLE_KEY`
- `DB_PASSWORD`
- `PROJECT_REF` — `ybehhhduhynsdujmxdzx`
- `DATABASE_URL` (added in plan 03-01)

**User action remaining:** open 1Password → entry `Supabase — boardgame-rag-prod` → confirm all 6 fields present and match prod. If any missing, paste from `.env.prod` (canonical-by-recovery: 1Password is source of truth per D-19, but `.env.prod` currently mirrors valid prod values).

## CLI unlink confirmation

`supabase unlink` ran successfully:

```
Finished supabase unlink.
Unlinking project: ybehhhduhynsdujmxdzx
```

Post-state:
- `supabase/.temp/project-ref` — removed (file does not exist)
- `supabase/.temp/` — directory still present with `cli-latest` only (CLI metadata, not project link)
- Day-to-day `supabase` CLI commands now operate on no-project-linked state; will not accidentally hit prod.

## `.env.prod` disposition

Remains on disk at repo root, gitignored. Holds full prod credential set for future re-seed runs and ad-hoc psql ops. May be deleted at user's discretion; 1Password is canonical source per D-19. Recommendation: keep until Phase 4 (Fly deploy) is green so the same file can be referenced when running `flyctl secrets set` mappings.

## Hand-off note for Phase 4 / Phase 5

When provisioning Fly secrets in Phase 4, copy from 1Password entry `Supabase — boardgame-rag-prod`:
- `flyctl secrets set SUPABASE_URL=...`
- `flyctl secrets set SUPABASE_SERVICE_ROLE_KEY=...`
- `flyctl secrets set SUPABASE_JWT_SECRET=...`
- `flyctl secrets set DATABASE_URL=...` (if backend uses it directly)

When provisioning Cloudflare Pages / Vite env in Phase 5:
- `VITE_SUPABASE_URL=...` (same value as `SUPABASE_URL`)
- `VITE_SUPABASE_ANON_KEY=...`

Note that `.env.prod` already mirrors both naming conventions; copy from there if 1Password retrieval is awkward.

## User Setup Required

**Manual confirmation required (does not block phase verifier):**

- Open 1Password, navigate to `Supabase — boardgame-rag-prod`, confirm 6 fields (SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY, DB_PASSWORD, PROJECT_REF, DATABASE_URL) all populated. If any are missing, paste current values from `.env.prod`.

No additional dashboard config or env-var changes required.

## Next Phase Readiness

- ROADMAP Phase 3 success criteria #1–#5 satisfied (criteria #4 verified live, #5 pending the manual 1Password confirmation above).
- DEPLOY-03 work complete.
- Phase 4 (Fly deploy) can begin once user confirms 1Password entry.
- Anti-leak invariant verified — safe to push branch.

## Self-Check: PASSED

- File created: `.planning/phases/03-prod-supabase-project/03-02-SUMMARY.md` — present
- Verify harness: `VERIFY OK` (10/10 PASS, including 3 seed checks)
- Half-ingested rows: 0
- `supabase unlink` confirmed: `supabase/.temp/project-ref` absent
- `.env.prod`: gitignored (`git check-ignore .env.prod` exits 0; not in `git status`)

---
*Phase: 03-prod-supabase-project*
*Completed: 2026-05-03*
