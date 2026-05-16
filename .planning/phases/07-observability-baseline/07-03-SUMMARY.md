---
phase: 07-observability-baseline
plan: "03"
subsystem: observability
tags: [langsmith, tracing, pydantic-settings, fastapi, env-vars, pytest]

# Dependency graph
requires:
  - phase: 04-deploy-backend-to-fly-io
    provides: Fly prod deployment + LANGCHAIN_PROJECT secret target for the rename
  - phase: 06-prod-wiring-auth-cors-rate-limiting-cost-caps
    provides: Hardened prod chat endpoint that emits the traces this routing fix targets
provides:
  - "Settings.langsmith_project field reading the canonical LANGSMITH_PROJECT env var"
  - "Three-tier project-name precedence in setup_tracing() (RESEARCH Pitfall 5 fix)"
  - "Dual env-var write (LANGSMITH_PROJECT + LANGCHAIN_PROJECT) for defense in depth"
  - "backend/scripts/verify_langsmith_routing.py — live E2E routing probe"
  - "backend/tests/test_tracing.py — 4 unit tests pinning the precedence contract"
affects: [07-04, 07-05, future-observability-phases]

# Tech tracking
tech-stack:
  added: []  # no new deps — uses existing langsmith 0.3.42 + httpx
  patterns:
    - "Three-tier env-precedence resolution: canonical env > legacy env > settings default"
    - "Dual env-var write for SDK compat (defense in depth)"
    - "Cross-platform JWT minting in pure Python (avoid bash dependency in scripts)"

key-files:
  created:
    - backend/scripts/verify_langsmith_routing.py
    - backend/tests/test_tracing.py
  modified:
    - backend/config.py
    - backend/services/tracing.py

key-decisions:
  - "Pydantic field renamed langchain_project -> langsmith_project to read the canonical LANGSMITH_PROJECT env (langsmith SDK 0.3.42+ documented var)"
  - "Field default 'rag-masterclass' preserved as zero-config local fallback"
  - "setup_tracing() writes BOTH env aliases to the resolved value (Pitfall 5 — SDK env-var walker checks both paths)"
  - "Verify script's API-key guard placed in main(), not at module level — so module import works without LANGSMITH_API_KEY (cleaner test surface)"
  - "JWT minting reimplemented in Python (not bash subprocess) — cross-platform durability"

patterns-established:
  - "Three-tier env precedence: os.environ.get('CANONICAL') or os.environ.get('LEGACY') or settings.default"
  - "Dual-write defense: write resolved value to BOTH env-var aliases so all downstream SDK code paths agree"
  - "Verify scripts: module-level constants for live endpoints + main()-guarded auth requirements"

requirements-completed: [OBS-02]

# Metrics
duration: 32min
completed: 2026-05-16
---

# Phase 07 Plan 03: LangSmith Routing Fix + E2E Verify Script Summary

**Three-tier env-precedence in setup_tracing() with dual env-var write, plus a real E2E verify script that asserts boardgame-rag-prod sees the trace and boardgame-rag-dev does not.**

## Performance

- **Duration:** ~32 min
- **Started:** 2026-05-16T05:16:43Z
- **Completed:** 2026-05-16T05:48Z (approx)
- **Tasks:** 3 / 3
- **Files modified:** 2 / created: 2

## Accomplishments

- Renamed `Settings.langchain_project` -> `Settings.langsmith_project` so pydantic-settings reads the canonical `LANGSMITH_PROJECT` env var (the langsmith SDK 0.3.42 documented name).
- Patched `setup_tracing()` to resolve the project name via three-tier precedence (`LANGSMITH_PROJECT env > LANGCHAIN_PROJECT env > settings default`) and write the resolved value to BOTH env-var aliases — closes RESEARCH §Pitfall 5 and ensures every SDK code path agrees.
- Shipped 4 pytest tests pinning the contract (no-op, canonical-env-wins, settings-fallback, legacy-env-still-routes). All 4 pass.
- Shipped `backend/scripts/verify_langsmith_routing.py` (194 lines, 4 functions): mints a Supabase JWT, POSTs a chat to the deployed Fly URL, drains the SSE stream, then polls LangSmith for ≥1 completed run in `boardgame-rag-prod` and 0 runs in `boardgame-rag-dev` within a 90s window.

## Task Commits

Each task was committed atomically on branch `worktree-agent-a290ba8cd49f90c9e`:

1. **Task 1: Rename Settings.langchain_project -> langsmith_project** — `a25bd8c` (feat)
2. **Task 2: Three-tier precedence + dual env-var write in setup_tracing + tests** — `3f35fbd` (feat)
3. **Task 3: Add verify_langsmith_routing.py end-to-end probe** — `08dc1a5` (feat)

## Files Created/Modified

- `backend/config.py` — renamed field `langchain_project` -> `langsmith_project` (default `"rag-masterclass"` preserved)
- `backend/services/tracing.py` — added three-tier precedence resolution + dual-write to both env-var aliases
- `backend/tests/test_tracing.py` *(new)* — 4 unit tests covering no-op, canonical-env-wins, settings-fallback, and legacy-env-still-routes paths
- `backend/scripts/verify_langsmith_routing.py` *(new)* — 194-line E2E verify probe: JWT mint -> chat POST -> SSE drain -> LangSmith poll -> assert prod-only routing

## Decisions Made

See frontmatter `key-decisions`. Summary:

- **Field rename, not aliasing.** Pydantic supports field aliases, but a rename is cleaner: only `LANGSMITH_PROJECT` reads the field; the legacy env var name still routes correctly via the second tier of the precedence chain.
- **Dual-write to both env-var aliases.** langsmith 0.3.42 has multiple code paths that may read either alias; writing the same resolved value to both is cheap defense in depth.
- **API-key guard in `main()`, not module-level.** Module import succeeds without `LANGSMITH_API_KEY`, which keeps the import-sanity test simple and avoids surprising failures in static analysis tools.
- **Pure-Python JWT minting** in `get_test_jwt()` instead of subprocess'ing the bash helper — cross-platform (Windows/Linux/macOS) without dependency on bash.

## Deviations from Plan

None — plan executed exactly as written.

The plan defined 3 optional bonus test #4 (legacy `LANGCHAIN_PROJECT` env still routes); it was straightforward, so it was implemented — yielding 4 tests instead of 3. All acceptance criteria green.

## Issues Encountered

- **Worktree cwd drift caught early.** Initial Edit was applied to the main repo's `backend/config.py` (orchestrator-side path leaking through), not the worktree copy. Caught by the pre-commit HEAD safety assertion (which detected branch `master` instead of `worktree-agent-*`) before any commit happened. The main-repo edit was reverted and the change re-applied to the correct worktree path. **Lesson reinforced:** always derive Edit/Write paths from `git rev-parse --show-toplevel` run inside the worktree, not from `pwd` captured in the orchestrator context. No commits were lost.
- **Pre-existing test infra issues** in `tests/test_e2e_subagent.py` (missing `VITE_SUPABASE_URL` env var) and `tests/test_record_manager.py::test_*_integration` (missing `user_id` fixture in conftest — only `test_user_id`/`mock_user_id` exist). Both are scope-boundary out-of-scope (unrelated to this plan's changes) — logged below under Deferred Issues, not auto-fixed.

## Deferred Issues

Pre-existing infrastructure issues surfaced during the full-suite run but NOT caused by this plan's changes (scope-boundary rule — not auto-fixed here):

| File | Issue | Surfaced by |
|------|-------|-------------|
| `backend/tests/test_e2e_subagent.py` | `KeyError: 'VITE_SUPABASE_URL'` at module import; expects env vars not present in the test environment | full `pytest tests/` run |
| `backend/tests/test_record_manager.py::test_check_duplicate_integration` | Fixture `user_id` not registered in conftest.py (only `test_user_id` / `mock_user_id` exist) | full `pytest tests/` run |
| `backend/tests/test_record_manager.py::test_find_previous_version_integration` | Same missing `user_id` fixture | full `pytest tests/` run |

Recommend a future cleanup pass to either (a) skip these tests when env vars are missing or (b) refactor to use the canonical `mock_user_id` fixture.

## Test Results

```
backend $ pytest tests/test_tracing.py -x -v
============================== 4 passed in 0.31s ==============================

backend $ pytest tests/ -k "not _integration and not test_seed_default_kb and not test_upload_folder and not test_subagent_alignment" --ignore=tests/test_e2e_subagent.py
================ 98 passed, 25 deselected, 1 warning in 13.45s ================
```

All 4 new tracing tests pass. All 98 unit tests pass. Excluded items are pre-existing integration tests requiring live env config (see Deferred Issues above).

## User Setup Required — Fly Secret Rename Runbook

**This plan ships the code that consumes the renamed secret.** The Fly-side rename executes during Wave 3 (07-04 / 07-05) alongside the dashboard / verification work. Until then, prod still has the legacy secret name and traces will route to the legacy project. Required runbook:

```bash
# 1. Remove the legacy secret on Fly prod
flyctl secrets unset LANGCHAIN_PROJECT --app boardgame-rag-prod

# 2. Set the canonical secret name with the correct value
flyctl secrets set LANGSMITH_PROJECT=boardgame-rag-prod --app boardgame-rag-prod

# 3. Trigger a redeploy so the new secret takes effect
fly deploy

# 4. After deploy is healthy, run the verify probe from your dev machine
cd backend && venv/Scripts/python.exe scripts/verify_langsmith_routing.py
# Expected output:
#   [1/2] Sending test chat to https://boardgame-rag-prod.fly.dev ...
#         thread_id=<uuid> t0=<iso>
#   [2/2] Polling LangSmith (timeout 90s) ...
#   PASS: N completed run(s) found in boardgame-rag-prod
#   PASS: 0 runs leaked into boardgame-rag-dev
#   OBS-02 VERIFY: PASS
```

**Local `.env` companion** (also part of the OBS-02 user decision):

```dotenv
LANGSMITH_PROJECT=boardgame-rag-dev
# (Remove any legacy LANGCHAIN_PROJECT=... line if present — the new precedence chain
#  will still route correctly if it stays, but cleaning it up avoids confusion.)
```

## Threat Flags

No new security surface introduced beyond what the threat register in 07-03-PLAN.md already documents (T-07-13 through T-07-17 — all mitigated or accepted as documented).

## Self-Check: PASSED

- `backend/config.py` — modified ✓ (committed in `a25bd8c`)
- `backend/services/tracing.py` — modified ✓ (committed in `3f35fbd`)
- `backend/tests/test_tracing.py` — created ✓ (committed in `3f35fbd`)
- `backend/scripts/verify_langsmith_routing.py` — created ✓ (committed in `08dc1a5`)
- All 3 task commits present in `git log` ✓
- `grep -rn 'langchain_project' backend/` — 0 matches ✓
- Both `LANGSMITH_PROJECT` and `LANGCHAIN_PROJECT` referenced in `tracing.py` (dual-write) ✓
- `pytest tests/test_tracing.py` — 4 passed ✓
- Verify script module-importable without `LANGSMITH_API_KEY` ✓

## Next Phase Readiness

- **OBS-02 code-side complete.** Ready for Wave 3 (07-04 dashboard / 07-05 sign-off) to execute the Fly secret rename + run the verify probe against the live deploy.
- The verify probe is the regression check for any future change that touches `setup_tracing()` or LangSmith project routing — run it after any tracing-adjacent edit before merging.

---
*Phase: 07-observability-baseline*
*Completed: 2026-05-16*
