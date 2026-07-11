---
phase: 16-web-search-restoration
plan: 01
subsystem: testing
tags: [pytest, tavily, web-search, pydantic-settings, monkeypatch, red-baseline, tdd]

# Dependency graph
requires:
  - phase: 11-secret-custody
    provides: "scrub_secrets (services/log_scrub.py) + monkeypatch/MagicMock SSE-error test convention (test_error_surfacing.py)"
provides:
  - "backend/tests/test_web_search.py — seven RED tests pinning WSRCH-01..04 + D-04 + D-03 backend half"
  - "backend/tests/test_config.py — web_search_depth default/override + tvly- scrub RED tests"
  - "Executable sub-30s RED baseline the Wave 2 backend fix (plan 16-02) turns GREEN"
affects: [16-02, web-search-restoration, tavily, config-settings, log-scrub, chat-tool-loop]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Transport-isolation via SimpleNamespace fake settings (isolates the not-yet-added Settings.web_search_depth field from the transport assertions)"
    - "Capturing httpx.post fake (records headers/json/timeout kwargs + call count) via monkeypatch on the module symbol — no HTTP-mock dependency"
    - "Local (in-test) import of a not-yet-extracted helper so only that test ERRORs on ImportError, not module collection"

key-files:
  created:
    - backend/tests/test_web_search.py
    - .planning/phases/16-web-search-restoration/deferred-items.md
  modified:
    - backend/tests/test_config.py

key-decisions:
  - "Wave 0 RED scaffold: no production code touched; every assertion fails/errors against current code and pins real behavior 16-02 must satisfy"
  - "Three of the seven web-search tests intentionally PASS now (test_tavily_maps_results, test_gating_fail_closed, test_graceful_failure_logs) — they verify already-correct WSRCH-01/02/04 behavior and act as regression guards"
  - "test_tool_result_error_status uses a LOCAL import of routers.chat.tool_result_is_error so its ImportError is scoped to that test, keeping module collection green"

patterns-established:
  - "SimpleNamespace fake settings for service-layer transport tests"
  - "Capturing-fake httpx.post with monkeypatch + MagicMock (project's no-HTTP-mock-lib convention)"

requirements-completed: []  # Wave 0 RED scaffold — WSRCH-01..04 are pinned by RED tests here but SATISFIED by plan 16-02 (tests go GREEN + prod-verify). Traceability stays Pending until 16-02.

# Metrics
duration: 12min
completed: 2026-07-11
---

# Phase 16 Plan 01: Web-Search RED Test Scaffold Summary

**Seven-test RED baseline (`test_web_search.py`) + three config/scrub RED tests pinning Tavily Bearer-auth, content→snippet mapping, fail-closed gating, D-02 citation guidance, graceful-failure logging, the `tool_result_is_error` classifier, and env-configurable `web_search_depth` — all failing against current code, ready for plan 16-02 to turn GREEN.**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-07-11T23:40:00Z
- **Completed:** 2026-07-11T23:52:13Z
- **Tasks:** 2
- **Files modified:** 2 created (test_web_search.py, deferred-items.md) + 1 modified (test_config.py)

## Accomplishments
- Created `backend/tests/test_web_search.py` with the seven named contract tests (five RESEARCH Test-Map names + two finer-grained additions), pinning the WSRCH-01..04 + D-04 + D-03-backend contract.
- Extended `backend/tests/test_config.py` with `web_search_depth` default/env-override tests and a `tvly-` scrub-redaction test, mirroring the existing `chat_max_iterations` + `scrub_secrets` patterns.
- Established an executable, sub-30s RED baseline: the one genuine bug (Tavily now requires header-only `Authorization: Bearer`, not a body `api_key`) is pinned by `test_tavily_bearer_auth`, so the 16-02 fix cannot regress.
- No new dependency introduced — all mocking via `monkeypatch` + `unittest.mock.MagicMock`.

## Task Commits

Each task was committed atomically:

1. **Task 1: Create test_web_search.py (RED contract)** - `435d6fc` (test)
2. **Task 2: Extend test_config.py with depth + tvly- scrub tests (RED)** - `3ed101d` (test)

**Plan metadata:** (docs commit — this SUMMARY + STATE/ROADMAP/REQUIREMENTS)

## Files Created/Modified
- `backend/tests/test_web_search.py` - Seven RED tests: `test_tavily_bearer_auth`, `test_tavily_maps_results`, `test_gating_fail_closed`, `test_system_prompt_citation_guidance`, `test_graceful_failure_logs`, `test_tool_result_error_status`, `test_search_depth_passed`. Capturing httpx.post fake + SimpleNamespace fake settings; local import of the not-yet-extracted `tool_result_is_error`.
- `backend/tests/test_config.py` - Appended `test_web_search_depth_default`, `test_web_search_depth_env_override`, `test_scrub_secrets_redacts_tavily` (existing sk-or- tests untouched).
- `.planning/phases/16-web-search-restoration/deferred-items.md` - Logged pre-existing out-of-scope failures (see Issues Encountered).

## RED Baseline (verification)

Intended RED failures (all against current code, as designed):

| Test | Mode | Reason (RED) |
|------|------|--------------|
| test_web_search.py::test_tavily_bearer_auth | FAIL | No `Authorization` header sent; `api_key` still in body; depth hardcoded |
| test_web_search.py::test_search_depth_passed | FAIL | `search_depth` hardcoded `"basic"`, not read from settings |
| test_web_search.py::test_system_prompt_citation_guidance | FAIL | `system_prompt` lacks "Sources:" / inline-links guidance |
| test_web_search.py::test_tool_result_error_status | ERROR (ImportError) | `routers.chat.tool_result_is_error` not extracted until 16-02 Task 3 |
| test_config.py::test_web_search_depth_default | ERROR (AttributeError) | `Settings.web_search_depth` field absent until 16-02 Task 1 |
| test_config.py::test_web_search_depth_env_override | ERROR (AttributeError) | same missing field |
| test_config.py::test_scrub_secrets_redacts_tavily | FAIL | `log_scrub` regex only matches `sk-or-` today |

Intentionally GREEN now (verify already-correct behavior; act as regression guards): `test_tavily_maps_results`, `test_gating_fail_closed`, `test_graceful_failure_logs`.

Full suite: **281 passed**, 8 failed (7 intended RED scaffold + 1 pre-existing env-dependent), 2 errors (pre-existing `test_record_manager` fixture debt). No collateral breakage.

## Decisions Made
- Kept three of the seven web-search tests GREEN now — they lock already-correct WSRCH-01/02/04 behavior (result mapping, fail-closed gating, graceful failure) as permanent regression guards rather than forcing artificial RED.
- Used a `SimpleNamespace` fake settings object for `_search_tavily` transport tests so the assertions are isolated from the not-yet-added `Settings.web_search_depth` field (which is what the `test_config.py` depth test is meant to flag).
- Scoped the `tool_result_is_error` ImportError to a single test via a local (in-body) import, keeping module collection green.

## Deviations from Plan

None - plan executed exactly as written. Two test files created/modified as specified; no production code touched (Wave 0 RED scaffold by design).

## Issues Encountered
- **Pre-existing failures surfaced during the full-suite run (out of scope, NOT fixed):**
  - `test_config.py::test_key_encryption_secret_default` FAILS because the local `.env` has `KEY_ENCRYPTION_SECRET` set (v1.2 BYOK) — confirmed pre-existing by stashing my Task 2 edit and re-running at HEAD.
  - `test_record_manager.py::test_check_duplicate_integration` and `::test_find_previous_version_integration` ERROR (missing `user_id` fixture) — already tracked as known tech debt in STATE.md/PROJECT.md.
  - Both logged to `.planning/phases/16-web-search-restoration/deferred-items.md`; neither is collateral from this plan.

## User Setup Required
None - no external service configuration required for this test-scaffold plan. (The prod `WEB_SEARCH_API_KEY` Fly secret is a later-plan ops step, not this plan.)

## Next Phase Readiness
- The RED baseline is in place and reproducible: `cd backend && venv/Scripts/python -m pytest tests/test_web_search.py tests/test_config.py -q`.
- Plan 16-02 (Wave 2 backend fix) turns these GREEN by: (1) adding `Settings.web_search_depth="basic"` + env override; (2) editing `system_prompt` for D-02 citation guidance + error-ack nudge; (3) switching `_search_tavily` to header-only Bearer auth reading `search_depth` from settings; (4) extracting `tool_result_is_error` in `routers.chat` and emitting `is_error` on the SSE `tool_result` event; (5) extending `scrub_secrets` to also redact `tvly-` keys.
- No blockers.

## Self-Check: PASSED

- FOUND: backend/tests/test_web_search.py
- FOUND: backend/tests/test_config.py (modified)
- FOUND: .planning/phases/16-web-search-restoration/16-01-SUMMARY.md
- FOUND: .planning/phases/16-web-search-restoration/deferred-items.md
- FOUND: commit 435d6fc (Task 1)
- FOUND: commit 3ed101d (Task 2)

---
*Phase: 16-web-search-restoration*
*Completed: 2026-07-11*
