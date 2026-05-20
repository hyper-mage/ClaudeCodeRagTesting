---
phase: 04-deploy-backend-to-fly-io
verified: 2026-05-05T13:05:00Z
status: passed
score: 4/4 must-haves verified
re_verification: null
---

# Phase 4: Deploy Backend to Fly.io — Verification Report

**Phase Goal:** Containerized backend reachable at public *.fly.dev URL, talking to prod Supabase, serving /api/health and SSE chat end-to-end.
**Verified:** 2026-05-05T13:05:00Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| 1 | fly.toml at repo root with required key set (shared-cpu-1x@1gb, internal_port=8000, /api/health check, auto_stop_machines="suspend", commented keep-warm toggle) | VERIFIED | `fly.toml` lines 1-28; adjacency awk passes (commented `# min_machines_running = 1` at line 15 directly above active `min_machines_running = 0` at line 16) |
| 2 | All runtime secrets in flyctl, not baked into image | VERIFIED | SUMMARY 04-02 lines 74-77: `flyctl secrets list` shows 24 keys (9 D-05 required), zero `^VITE_` leakage; runtime probe via `flyctl ssh console -C printenv` confirms only Fly secrets + standard system env present in container; no `.env*` baked into `/app` |
| 3 | fly deploy succeeded; curl /api/health returns 200 | VERIFIED | Live `curl https://boardgame-rag-prod.fly.dev/api/health` returned `{"status":"ok"}` HTTP 200 during this verification run; SUMMARY 04-02 records image `registry.fly.io/boardgame-rag-prod:deployment-01KQV7ATBRJG7S7P5C2FJRRR82` deployed 2026-05-05 |
| 4 | End-to-end SSE chat streams without buffering (≥3 chunks) | VERIFIED | Live `bash backend/scripts/fly_smoke.sh https://boardgame-rag-prod.fly.dev` exited 0 with `SMOKE PASS: 3 SSE 'data:' lines, first chunk in 4s` (under FIRST_CHUNK_MAX=20s) |

**Score:** 4/4 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
| --- | --- | --- | --- |
| `fly.toml` | Free-tier deploy config with D-11/D-12 key set | VERIFIED | Contains `app = "boardgame-rag-prod"`, `primary_region = "iad"`, `internal_port = 8000`, `force_https = true`, `auto_stop_machines = "suspend"`, `auto_start_machines = true`, `min_machines_running = 0`, commented toggle adjacent, `[[http_service.checks]]` on `/api/health`, `[[vm]] shared-cpu-1x / 1gb`, `[build] dockerfile = "Dockerfile"`. No `[env]` section. |
| `backend/scripts/_lib/get_test_jwt.sh` | Sourceable Supabase password-grant helper exporting `$JWT` | VERIFIED | Defines `get_test_jwt()`, uses `grant_type=password`, `export JWT`, reads `VITE_SUPABASE_URL` / `VITE_SUPABASE_ANON_KEY` from already-sourced env |
| `backend/scripts/fly_smoke.sh` | Post-deploy SSE smoke (≥3 chunks, first chunk <20s) | VERIFIED | Polls `/api/health`, sources helper, creates thread, SSE-asserts on `/api/threads/{id}/messages` with `Accept: text/event-stream`, body `{"content":"What is Catan?"}`, MIN_DATA_LINES=3, FIRST_CHUNK_MAX=20. Live run passes. |
| `backend/scripts/docker_smoke.sh` | Refactored to consume `_lib/get_test_jwt.sh` | VERIFIED | Lines 87-90: sources helper + calls `get_test_jwt`. Inline curl POST removed. |

### Key Link Verification

| From | To | Via | Status | Details |
| --- | --- | --- | --- | --- |
| `fly_smoke.sh` | `_lib/get_test_jwt.sh` | `source "$(dirname "$0")/_lib/get_test_jwt.sh"` | WIRED | line 59 |
| `docker_smoke.sh` | `_lib/get_test_jwt.sh` | `source` + `get_test_jwt` | WIRED | lines 89-90 |
| `fly.toml [build]` | `Dockerfile` | `dockerfile = "Dockerfile"` | WIRED | line 8 |
| Fly secrets store | container env at runtime | `flyctl secrets import --stage` | WIRED | SUMMARY 04-02: 24 secrets present, runtime probe confirms loaded |
| `fly_smoke.sh` | `https://boardgame-rag-prod.fly.dev/api/threads/{id}/messages` | Bearer JWT + `Accept: text/event-stream` | WIRED | Live smoke run produced 3 SSE data lines, first chunk in 4s |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| --- | --- | --- | --- |
| /api/health returns 200 | `curl -fsS https://boardgame-rag-prod.fly.dev/api/health` | `{"status":"ok"}` HTTP 200 | PASS |
| SSE chat streams ≥3 chunks within 20s first-chunk budget | `bash backend/scripts/fly_smoke.sh https://boardgame-rag-prod.fly.dev` | `SMOKE PASS: 3 SSE 'data:' lines, first chunk in 4s` (exit 0) | PASS |
| fly.toml syntactic shape | `awk` adjacency check on commented keep-warm toggle | exit 0 | PASS |
| Bash scripts syntactically valid | `bash -n` on fly_smoke.sh, get_test_jwt.sh, docker_smoke.sh | (validated by Plan 01 SUMMARY self-check) | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| --- | --- | --- | --- | --- |
| DEPLOY-04 | 04-01, 04-02 | Developer can run `fly deploy` and reach backend at public *.fly.dev URL serving /api/health and SSE chat end-to-end | SATISFIED | Live `/api/health` returns 200; live SSE smoke passes 3 chunks/4s. Both requirement halves green. |
| DEPLOY-07 | 04-01, 04-02 | `fly.toml` defaults to free-tier (`auto_stop_machines="suspend"`, no `min_machines_running` set) with documented one-line toggle | SATISFIED | `fly.toml` line 13 = `auto_stop_machines = "suspend"`, line 15 = commented `# min_machines_running = 1` toggle directly above line 16 active `min_machines_running = 0`. Adjacency awk passes. |
| SEC-03 | 04-01, 04-02 | All secrets live in `flyctl secrets` and CF Pages env vars — never committed, never baked into image | SATISFIED (Fly side) | 24 secrets in `flyctl secrets list`, zero VITE_* leakage. Runtime probe via `flyctl ssh console -C printenv` confirms no Dockerfile-baked ENV directives for any of the 9 required keys; no `.env*` files in `/app`. CF Pages portion (CF Pages env vars) is Phase 5 scope. Docker history grep deferred (documented, not blocking) — equivalent runtime evidence captured. |

REQUIREMENTS.md confirms all three IDs marked Phase 4 / Complete (lines 14, 17, 24, 72, 75, 79). No orphaned requirement IDs for Phase 4.

### Anti-Patterns Found

None. No TODO/FIXME/placeholder strings in created artifacts. No empty implementations. No hardcoded stub responses (live SSE produces real LLM-generated chunks against prod Supabase + OpenRouter).

### Human Verification Required

None mandatory for goal achievement. Documented deferred items (per task prompt — not gaps):

- TAVILY_API_KEY value empty (web search out of Phase 4 scope)
- Docker history grep deferred (Docker Desktop not running on host) — runtime SSH probe captured equivalent SEC-03 evidence
- 1Password TEST_USER_EMAIL/PASSWORD field add (manual user follow-up)
- Fly trial machine 5-min lifetime (CC required to remove; pre-public-demo concern)
- LLM_API_KEY discovery: backend chain is `LLM_API_KEY → OPENAI_API_KEY` (NOT `OPENROUTER_API_KEY`); Fly secret set correctly to OPENROUTER value; `.env.prod` backfill recommended for self-sufficient future imports

### Gaps Summary

No gaps. All four must-haves verified against the actual deployed Fly app and committed repo artifacts. Live `/api/health` returns 200; live SSE smoke passes with 3 chunks and 4s first-chunk latency (well under the 20s buffering threshold). Phase goal achieved.

---

*Verified: 2026-05-05T13:05:00Z*
*Verifier: Claude (gsd-verifier)*
