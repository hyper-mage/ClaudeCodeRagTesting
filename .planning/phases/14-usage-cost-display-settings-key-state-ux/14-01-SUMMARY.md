---
phase: 14-usage-cost-display-settings-key-state-ux
plan: 01
subsystem: api
tags: [fastapi, pydantic, openrouter, sse, httpx, byok, cost, security]

# Dependency graph
requires:
  - phase: 11-byok-usage-capture
    provides: "messages.usage JSONB capture (cost + tokens summed across the tool loop) + the typed APIStatusError/RateLimitError SSE error handler + scrub_secrets + _ScrubFilter"
  - phase: 10-byok-key-exchange
    provides: "user_api_keys table, crypto_service encrypt/decrypt, /api/keys exchange+status+disconnect handlers, KeyStatusResponse"
  - phase: 09-app-layer-encryption
    provides: "MultiFernet decrypt_key control (request-local key lifetime, never logged)"
provides:
  - "MessageResponse.usage — per-message cost+tokens now survives GET /api/threads/{id} history load (read-path fix for COST-01/COST-04)"
  - "BalanceResponse model + GET /api/keys/balance server-side OpenRouter proxy (COST-02/COST-03) returning only {connected, limit_remaining, is_low}"
  - "low_balance_threshold_usd config (COST-03 / D-03), env LOW_BALANCE_THRESHOLD_USD, default 1.00"
  - "Mid-stream OpenRouter 401 -> no_api_key and 403 -> forbidden structured SSE error codes (D-09 backend half / SC#4)"
affects: [14-02, 14-03, frontend-usage-cost-display, frontend-key-state-ux, frontend-balance-indicator]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Server-side balance proxy: decrypt key in-memory per-request, proxy provider, return only derived non-secret fields"
    - "Server-computed threshold flag (is_low) never sent to client — tamper-proof"
    - "Typed e.status_code branching in the APIStatusError handler (never str(e) parsing) for distinct recoverable SSE codes"

key-files:
  created: []
  modified:
    - backend/models/schemas.py
    - backend/config.py
    - backend/routers/chat.py
    - backend/routers/keys.py

key-decisions:
  - "D-01/D-02: declare usage on MessageResponse so FastAPI response_model stops stripping the field on history load (Pitfall 1)"
  - "D-03: low_balance_threshold_usd defaults to 1.00 in code so absence of the env override is harmless; threshold computed server-side, never sent to client"
  - "D-04: null limit_remaining (pay-as-you-go) yields is_low=false unconditionally"
  - "D-09 (backend half): a mid-stream 401 reuses the SAME no_api_key code as the pre-flight no-key path so the FE [Reconnect] mapping is reused; 403 gets its own forbidden code; neither dead-ends on the generic upstream_error bubble"
  - "T-14-02: no exc_info on the balance error path (the traceback could capture the outbound Bearer header)"

patterns-established:
  - "Balance/secret-proxy endpoints return only a Pydantic model of derived non-secret fields, never resp.json()/resp.text/provider body"
  - "Mid-stream provider auth failures map to distinct structured SSE codes the FE can recover from"

requirements-completed: [COST-01, COST-02, COST-03, COST-04, PREF-01]

# Metrics
duration: ~18min
completed: 2026-06-29
---

# Phase 14 Plan 01: Usage Read-Path + Balance Proxy + Mid-Stream Key-Failure Codes Summary

**Exposed per-message `usage` on history load, added the `GET /api/keys/balance` server-side OpenRouter proxy (returns only `{connected, limit_remaining, is_low}`), and made mid-stream 401/403 distinct recoverable SSE codes (`no_api_key`/`forbidden`).**

## Performance

- **Duration:** ~18 min
- **Started:** 2026-06-29T20:00Z (approx)
- **Completed:** 2026-06-29T20:18:05Z
- **Tasks:** 3 (Task 1 pre-existing/verified; Tasks 2 + 3 executed)
- **Files modified:** 4 (Tasks 2 + 3)

## Accomplishments
- `usage: dict | None` declared on `MessageResponse` — per-message cost + token counts now survive `GET /api/threads/{id}` response_model serialization (read-path fix that lets per-message cost and the per-thread Σ total survive a reload).
- New `BalanceResponse` model + `GET /api/keys/balance` handler: decrypts the stored sk-or key in-memory for the single request, proxies OpenRouter `GET /api/v1/key`, computes `is_low` server-side, and returns ONLY `{connected, limit_remaining, is_low}` — never the key, never the raw provider body.
- `low_balance_threshold_usd` config field (default 1.00, env `LOW_BALANCE_THRESHOLD_USD`) — threshold computed server-side, never sent to the client (tamper-proof).
- Mid-stream OpenRouter `401 -> no_api_key` and `403 -> forbidden` SSE branches added to `chat.py`, both before the `else: upstream_error`; the existing 402 `payment_required` branch and the `RateLimitError`(429)-before-`APIStatusError` catch ordering are unchanged.

## Task Commits

Each task was committed atomically:

1. **Task 1: Author Wave 0 backend test scaffolds (RED)** - `c76ae8f` (test) — PRE-EXISTING on base; verified on disk, NOT recreated.
2. **Task 2: Expose usage + BalanceResponse + threshold config + 401/403 SSE branches** - `4228ee9` (feat)
3. **Task 3: Add GET /api/keys/balance server-side proxy** - `2e190ce` (feat)

_Tasks 2 and 3 are `tdd="true"` plan tasks turning pre-authored RED tests GREEN; the RED commit is Task 1's `c76ae8f`._

## Files Created/Modified
- `backend/models/schemas.py` - Added `usage: dict | None = None` to `MessageResponse`; added `BalanceResponse` model after `KeyStatusResponse`.
- `backend/config.py` - Added `low_balance_threshold_usd: float = 1.00` (COST-03 / D-03).
- `backend/routers/chat.py` - Added `elif e.status_code == 401:` (-> `no_api_key`) and `elif e.status_code == 403:` (-> `forbidden`) branches in the `APIStatusError` handler, before the `else`.
- `backend/routers/keys.py` - Added `GET /api/keys/balance` handler + the four new imports (`logging`/`logger`, `get_settings`, `decrypt_key`, `scrub_secrets`, `BalanceResponse`).

## Decisions Made
None beyond the plan — implemented D-01/D-02 (read-path), D-03 (threshold), D-04 (null = not low), D-09 backend half (401/403 codes) exactly as specified.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- The worktree has no `backend/venv` and no repo-root `.env`. Resolved by running the main checkout's venv Python (`backend/venv/Scripts/python.exe`) against the worktree source from the worktree `backend/` dir; `tests/conftest.py` inserts the backend dir on `sys.path`, so the worktree modules are exercised with the venv's dependencies.
- Full-suite run surfaced 3 pre-existing/out-of-scope errors, none caused by this plan:
  - `tests/test_record_manager.py::test_check_duplicate_integration` and `::test_find_previous_version_integration` — missing `user_id` fixture (documented pre-existing fixture debt per STATE.md / plan acceptance).
  - `tests/test_e2e_subagent.py` — collection `KeyError: 'VITE_SUPABASE_URL'` (a live-Supabase e2e test reading `os.environ` at import; environmental, no `.env` in the worktree). Unrelated to the four files touched.
  - With these excluded: **207 passed**, including all 11 Wave-0 trio cases.

## Test Results
- Wave-0 trio GREEN: `test_keys_balance.py` (5), `test_thread_usage_exposed.py` (1), `test_error_surfacing.py` (5, incl. `test_unauthorized_code_on_401` + `test_forbidden_code_on_403`) — 11/11.
- `test_429_402_distinct_codes` still passes (no regression to 402/429 codes).
- Source assertions: `BalanceResponse` class count = 1; `MessageResponse` has a `usage:` line; `low_balance_threshold_usd` present in config.py; `"forbidden"` present in chat.py; the balance handler body references no functional `exc_info`, `resp.text`, `data.label`, or the key in any return/HTTPException detail (all such tokens in keys.py are docstring/comment text only).

## Notes on Acceptance Criteria Wording
- Plan Task 3 acceptance states `grep -c "exc_info" backend/routers/keys.py` should return 0. That literal count was already non-zero on the base file because the **module docstring** (line 19) and the **exchange handler comment** (line 56) describe the "never add exc_info" security rule in prose. The threat-model INTENT (T-14-02: no functional `exc_info` on the balance path) is fully satisfied — the balance handler uses a plain `logger.warning(scrub_secrets(...))` with no `exc_info` argument. Treated as a wording discrepancy in the plan, not an implementation gap.

## Security (threat model verification)
- T-14-01: `/balance` returns only `BalanceResponse{connected, limit_remaining, is_low}` — verified by `test_balance_returns_remaining` (`assert "sk-or-" not in resp.text`).
- T-14-02: balance error path logs `scrub_secrets(str(e))` with NO `exc_info`; fixed generic 502 detail — verified by `test_balance_provider_error_scrubbed`.
- T-14-03: decrypted key held in a request-local `key` var only; never stored/returned/logged.
- T-14-04: `is_low` computed server-side from `low_balance_threshold_usd`; threshold never sent to client.
- T-14-05: row lookup bound to the JWT sub via `.eq("user_id", user_id)`.
- T-14-06: 401/403 SSE payloads carry only the structured CODE via `_sse_error` (scrub-wrapped).

## User Setup Required
Optional: set `LOW_BALANCE_THRESHOLD_USD` in `.env` (dev) / `.env.prod` (prod) to override the 1.00 default. Live balance verification (COST-02) needs a real OAuth-connected OpenRouter key. The code default makes the threshold harmless if unset.

## Next Phase Readiness
- Backend read-path + balance proxy + mid-stream key-failure codes are all in place; the Phase 14 frontend surfaces (usage/cost display, balance indicator, [Reconnect] on mid-chat 401) can now consume real data.
- No blockers introduced. STATE.md/ROADMAP.md intentionally NOT modified (worktree mode — orchestrator owns those writes after the wave).

---
*Phase: 14-usage-cost-display-settings-key-state-ux*
*Completed: 2026-06-29*
