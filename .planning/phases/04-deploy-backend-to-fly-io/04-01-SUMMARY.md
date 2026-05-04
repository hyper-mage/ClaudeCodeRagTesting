---
phase: 04-deploy-backend-to-fly-io
plan: 01
subsystem: infra
tags: [fly.io, deploy, sse, smoke-test, bash, supabase-auth]

requires:
  - phase: 02-dockerize-backend
    provides: Dockerfile at repo root, docker_smoke.sh JWT pattern
  - phase: 03-prod-supabase-project
    provides: .env.prod at repo root with prod Supabase URL/keys
provides:
  - fly.toml at repo root with free-tier shape (D-11/D-12)
  - sourceable get_test_jwt helper shared by docker_smoke and fly_smoke
  - fly_smoke.sh post-deploy SSE smoke (chunk-count + first-chunk-latency)
affects: [04-02 (deploy + verify), 05 (frontend deploy will read fly.dev URL), 07 (observability points at same URL)]

tech-stack:
  added: [fly.toml TOML config]
  patterns: [sourceable bash helper under backend/scripts/_lib/, process-substitution SSE assertion]

key-files:
  created:
    - fly.toml
    - backend/scripts/_lib/get_test_jwt.sh
    - backend/scripts/fly_smoke.sh
  modified:
    - backend/scripts/docker_smoke.sh

key-decisions:
  - "fly.toml verbatim per D-11: shared-cpu-1x@1gb, internal_port=8000, auto_stop_machines=\"suspend\", min_machines_running=0, [[http_service.checks]] on /api/health"
  - "Keep-warm toggle is a single commented line directly above the active min_machines_running=0 (D-12 adjacency)"
  - "JWT helper extracted to backend/scripts/_lib/get_test_jwt.sh; reads VITE_SUPABASE_URL/ANON_KEY from already-sourced env (D-14)"
  - "fly_smoke.sh asserts both ≥3 SSE data lines AND first chunk <20s (RESEARCH Pitfall 3 hardening beyond bare D-13)"
  - "Endpoint for SSE chat is POST /api/threads/{thread_id}/messages — verified from backend/routers/chat.py line 30 prefix + line 458 route (NOT /api/chat)"

patterns-established:
  - "Shared bash helpers live under backend/scripts/_lib/ and are sourced (not exec'd) by sibling scripts"
  - "Smoke scripts let the caller load env (set -a; source <file>; set +a) and helpers read exported vars"
  - "SSE assertions in bash use process substitution (done < <(curl ...)) to keep loop variables in scope"

requirements-completed: [DEPLOY-04, DEPLOY-07, SEC-03]

duration: 3min
completed: 2026-05-04
---

# Phase 04 Plan 01: Fly.io Deploy Config + Smoke Scripts Summary

**fly.toml with free-tier suspend defaults plus shared get_test_jwt helper and fly_smoke.sh asserting SSE chunk count and first-chunk latency.**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-05-04T12:49:04Z
- **Completed:** 2026-05-04T12:51:53Z
- **Tasks:** 3
- **Files modified:** 4 (3 created, 1 modified)

## Accomplishments

- fly.toml at repo root locks ROADMAP §Phase 4 success criterion #1 (verbatim D-11 keys + D-12 commented adjacency toggle)
- get_test_jwt helper extracted from docker_smoke.sh to backend/scripts/_lib/, ready for reuse by fly_smoke.sh against .env.prod
- docker_smoke.sh refactored to consume the helper with zero behavior change (Phase 2 regression intact)
- fly_smoke.sh ready for Plan 02 to invoke against the live Fly URL — polls /api/health, creates a thread, asserts SSE chat at the verified `/api/threads/{id}/messages` endpoint, fails on first-chunk-latency >20s (Pitfall 3 hardening)

## Task Commits

1. **Task 1: Create fly.toml** — `ce3a352` (feat)
2. **Task 2: Extract get_test_jwt helper + refactor docker_smoke.sh** — `38dad27` (refactor)
3. **Task 3: Create fly_smoke.sh** — `d780c23` (feat)

## Files Created/Modified

- `fly.toml` (created) — Fly deploy config: `app="boardgame-rag-prod"`, `primary_region="iad"`, `[build] dockerfile="Dockerfile"`, `[http_service]` with suspend semantics + commented keep-warm toggle, `[[http_service.checks]]` on `/api/health`, `[[vm]] shared-cpu-1x / 1gb`. No `[env]` section (secrets via flyctl per SEC-03).
- `backend/scripts/_lib/get_test_jwt.sh` (created) — Sourceable Supabase password-grant helper exposing `get_test_jwt()` that exports `$JWT`. Reads `$VITE_SUPABASE_URL` and `$VITE_SUPABASE_ANON_KEY` from already-loaded env; supports `$TEST_EMAIL` / `$TEST_PASSWORD` overrides (defaults to `ragtest1@gmail.com` / `testpass123`).
- `backend/scripts/fly_smoke.sh` (created, executable) — Post-deploy SSE smoke. Takes `$1=$FLY_URL`, polls `/api/health` (60s/2s), sources `_lib/get_test_jwt.sh` after loading `.env.prod`, creates a thread, opens SSE on `POST /api/threads/{id}/messages` with body `{"message":"What is Catan?"}`, requires `MIN_DATA_LINES=3` and `FIRST_CHUNK_MAX=20`s. Uses process substitution for in-scope loop variables.
- `backend/scripts/docker_smoke.sh` (modified) — JWT block at former lines 86-94 replaced with `source "$(dirname "$0")/_lib/get_test_jwt.sh" && get_test_jwt`. Behavior identical; rest of script untouched.

## Decisions Made

- Helper placed at `backend/scripts/_lib/get_test_jwt.sh` (per D-14 discretion) — keeps `backend/scripts/` flat for primary scripts and quarantines reusable internals.
- `fly.toml` uses `[[http_service.checks]]` (array-of-tables) per RESEARCH Pattern 2 so a second check can be added later without TOML restructuring.
- `fly_smoke.sh` does NOT upload PDFs (per D-13) — keeps prod Storage clean; ingestion path remains exercised by `docker_smoke.sh` against local containers.
- Body field is `message` (not `content`) and seed query is `"What is Catan?"` to leverage Phase 3's deterministic 10-game default KB.

## Deviations from Plan

None — plan executed exactly as written. The plan's `<automated>` verify block contained one regex (`/^min_machines_running = 0/`) that doesn't account for the indented placement inside `[http_service]` (the verbatim TOML block in the plan indents the line by 2 spaces). The actual D-12 adjacency requirement (commented line directly above active line, no blank line between) is satisfied — confirmed via `awk '/# min_machines_running = 1/{c=NR} /^[[:space:]]*min_machines_running = 0/{a=NR} END{exit !(a==c+1)}' fly.toml` returning 0. The verbatim TOML in the plan's `<action>` was followed exactly; no content change made.

**Total deviations:** 0
**Impact on plan:** None — verbatim execution of D-11/D-12/D-13/D-14 specs.

## Issues Encountered

- Git CRLF warnings on bash scripts (Windows `core.autocrlf` behavior). Files commit cleanly; the warning is informational. Scripts execute via Git Bash in the dev workflow and via Linux sh in the Fly machine (both tolerate either ending; bash itself is line-ending agnostic).

## Phase 2 Regression Check (docker_smoke.sh refactor)

The refactor is a function-extraction only:
- Before: inline `curl` POST against `$VITE_SUPABASE_URL/auth/v1/token?grant_type=password` with `jq -r '.access_token'` parse, exiting via `fail` on empty.
- After: `source "$(dirname "$0")/_lib/get_test_jwt.sh"` then `get_test_jwt || fail "Auth failed (see stderr above)"`.
- Helper performs the identical curl POST with identical parse and exports `$JWT` (consumed by the unchanged `Authorization: Bearer $JWT` header in the upload curl at line 101 of docker_smoke.sh).
- `bash -n backend/scripts/docker_smoke.sh` returns 0; no other lines edited.
- A live `bash backend/scripts/docker_smoke.sh` run was NOT executed in this plan (out of scope — Plan 02 owns deploy, and the plan's verification block marks the live re-run as OPTIONAL).

## Next Phase Readiness

Plan 02 (Wave 2) can now execute from a clean working tree:
- `flyctl launch --no-deploy --copy-config` (or `flyctl apps create boardgame-rag-prod`) will pick up the committed `fly.toml`.
- `flyctl secrets import < .env.prod` per D-04 (planner picks the VITE_* filter approach).
- `flyctl deploy` builds against the repo-root `Dockerfile`.
- `bash backend/scripts/fly_smoke.sh https://boardgame-rag-prod.fly.dev` validates end-to-end SSE.

No blockers. Fallback app name `bgkb-rag-prod` (D-01) is available if `boardgame-rag-prod` collides at `flyctl apps create` — that pivot updates `fly.toml` line 4 and any default URL in fly_smoke usage docs.

## Self-Check: PASSED

- Files exist: fly.toml, backend/scripts/_lib/get_test_jwt.sh, backend/scripts/fly_smoke.sh (executable), backend/scripts/docker_smoke.sh (modified)
- Commits exist on master: ce3a352, 38dad27, d780c23
- All `bash -n` syntax checks pass
- All grep checks in plan `<verification>` block pass (with adjacency relaxation noted in Deviations)
- `.gitignore` line 5 `.env*` confirmed (excludes `.env.prod` — no edit needed)

---
*Phase: 04-deploy-backend-to-fly-io*
*Completed: 2026-05-04*
