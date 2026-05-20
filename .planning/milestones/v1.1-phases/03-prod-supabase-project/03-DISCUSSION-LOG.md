# Phase 3: Prod Supabase Project - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-28
**Phase:** 03-prod-supabase-project
**Areas discussed:** Migration apply method, Seed execution + prod env handoff, Migration count verification, Project metadata + secrets capture

---

## Gray Area Selection

| Option | Description | Selected |
|--------|-------------|----------|
| Migration apply method | Supabase CLI vs Dashboard vs psql bundle | ✓ |
| Seed execution + prod env handoff | Where seed runs + how prod creds injected | ✓ |
| Migration count verification | How to assert all 24 applied | ✓ |
| Project metadata + secrets capture | Region, name, password manager | ✓ |

**User's choice:** All four areas selected.

---

## Migration Apply Method

| Option | Description | Selected |
|--------|-------------|----------|
| Supabase CLI (Recommended) | `supabase link` + `db push`; tracks via schema_migrations | ✓ |
| Dashboard SQL Editor paste | Manual paste 001→024; no schema_migrations | |
| Single concatenated SQL via psql | Cat into one file, run via psql | |

**User's choice:** Supabase CLI.
**Notes:** CLI expects timestamp-prefixed migration filenames; current files are integer-prefixed. Resolution path deferred to planner (rename / `migration repair` / `--include-all`).

| Option | Description | Selected |
|--------|-------------|----------|
| Full `supabase init` + config.toml + seed | Long-term CLI ops bootstrap | ✓ |
| Minimal — config.toml only (Recommended) | Just enough to push | |
| No commit — link is local-only | No repo state | |

**User's choice:** Full init.
**Notes:** Treats Phase 3 as the moment Supabase CLI becomes the project's first-class apply path. Python seed script kept as-is regardless of Supabase's `seed.sql` mechanism.

---

## Seed Execution + Prod Env Handoff

| Option | Description | Selected |
|--------|-------------|----------|
| Local venv with `.env.prod` swap (Recommended) | Run seed locally with prod creds | ✓ |
| Inside Phase 2 Docker image | `docker run --env-file .env.prod ...` | |
| One-off Fly machine post-deploy | Defer to Phase 4 — breaks ROADMAP order | |

**User's choice:** Local venv.
**Notes:** Decouples Phase 3 from Phase 2 image build and Phase 4 Fly deploy. Same script that runs in dev, just different env file.

| Option | Description | Selected |
|--------|-------------|----------|
| `.env.prod` gitignored, populated by hand (Recommended) | Paste from 1Password | ✓ |
| Inline env vars on command line | No file on disk; risk of shell history | |
| Temporary `.env` swap | Risk of forgetting to restore | |

**User's choice:** `.env.prod` gitignored.
**Notes:** `.dockerignore` already covers `.env*`. May need `backend/config.py` patch to honor an `ENV_FILE` env override.

---

## Migration Count Verification

| Option | Description | Selected |
|--------|-------------|----------|
| schema_migrations row count vs CLI list (Recommended) | CLI-native count match | |
| Schema introspection — assert key tables/extensions | Semantic check | |
| Both — count + smoke schema check (Recommended Plus) | Belt and suspenders | ✓ |

**User's choice:** Both.
**Notes:** One-shot prod stand-up wants both layers. Verification bundled as standalone script for future drift checks.

| Option | Description | Selected |
|--------|-------------|----------|
| Leave in repo, exclude from prod apply (Recommended) | Documented as legacy | |
| Delete during Phase 3 | Risk for fresh local resets | |
| Move to `supabase/legacy/` | Move out of CLI's view | ✓ |

**User's choice:** Move to `supabase/legacy/`.
**Notes:** Removes ambiguity from CLI's view, preserves history.

---

## Project Metadata + Secrets Capture

| Option | Description | Selected |
|--------|-------------|----------|
| Region: closest to Fly target (Recommended) | Default `iad`/`us-east-1` if Phase 4 TBD | ✓ |
| Region: cheapest / default | Cross-region latency risk | |
| Defer region to Phase 4 | Wrong dependency direction | |

**User's choice:** Closest to Fly target.

| Option | Description | Selected |
|--------|-------------|----------|
| `boardgame-rag-prod` + 1Password (Recommended) | Mirrors LangSmith naming | ✓ |
| User-chosen + Bitwarden/generic | Whatever PM user already uses | |
| No password manager — `.env.prod` only | Violates ROADMAP criterion #5 | |

**User's choice:** `boardgame-rag-prod` + 1Password.
**Notes:** Single 1Password entry holds URL, anon, service_role, DB password, project_ref as separate fields.

| Option | Description | Selected |
|--------|-------------|----------|
| Rely on migration 004 `CREATE EXTENSION` (Recommended) | Idempotent, no manual step | ✓ |
| Pre-enable via dashboard before push | Belt-and-suspenders manual step | |

**User's choice:** Rely on migration.

---

## Claude's Discretion

- Migration filename/timestamp strategy (rename vs repair vs `--include-all`)
- Verification script language (bash/psql vs python/supabase-py)
- Optional `Makefile` targets (`make seed-prod`, `make verify-prod`)
- Whether to commit a `.env.example.prod` template stub
- Exact dotenv loading patch in `backend/config.py` (if needed for `ENV_FILE` override)

## Deferred Ideas

- DB snapshot/backup automation
- pg_cron nightly demo-user reset (v1.2+)
- Multi-region / read replicas
- Custom `DOCLING_CACHE_DIR` for prod (Phase 2 deferred)
- Anon-key rotation policy
- Fly volume mount for Docling cache (Phase 4)
- Supabase pause-prevention via `/api/health` (Phase 7 OBS-04)
- Seed-from-Phase-2-image variant (rejected)
