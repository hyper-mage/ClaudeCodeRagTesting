---
phase: 16-web-search-restoration
plan: 02
subsystem: web-search
tags: [tavily, web-search, bearer-auth, pydantic-settings, sse, log-scrub, system-prompt, tdd-green]

# Dependency graph
requires:
  - phase: 16-web-search-restoration
    plan: 01
    provides: "test_web_search.py (7 RED contract tests) + test_config.py depth/tvly- RED tests — the baseline this plan turns GREEN"
  - phase: 11-secret-custody
    provides: "scrub_secrets (services/log_scrub.py) + _ScrubFilter exc_info log path"
provides:
  - "backend/services/web_search_service.py — header-only Bearer Tavily transport + settings-driven search_depth (WSRCH-01, D-04)"
  - "backend/config.py — web_search_depth setting + D-02 citation guidance + D-03 error-ack nudge in system_prompt"
  - "backend/routers/chat.py — pure tool_result_is_error() classifier + is_error flag on the tool_result SSE event + D-01 web_search steer"
  - "backend/services/log_scrub.py — scrub_secrets redacts tvly- keys alongside sk-or-"
  - "The is_error SSE contract plan 16-03 (frontend failed-state render) consumes"
affects: [16-03, web-search-restoration, tavily, config-settings, log-scrub, chat-tool-loop]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Header-only Bearer auth for the Tavily transport (key rides Authorization header, never the JSON body / str(e) / SSE payload)"
    - "Pure module-level classifier (tool_result_is_error) as the single seam shared by the SSE emit and the unit test"
    - "Env-isolated config-default test: import config first (load_dotenv runs), then monkeypatch.delenv the ambient override before constructing Settings"

key-files:
  created: []
  modified:
    - backend/services/web_search_service.py
    - backend/config.py
    - backend/routers/chat.py
    - backend/services/log_scrub.py
    - backend/tests/test_web_search.py

key-decisions:
  - "The Tavily API is header-only Bearer today — deleted the body api_key entirely (Pitfall 2 closed) and added the Authorization header; the 200-response content→snippet mapping and graceful-error path were preserved untouched"
  - "tool_result_is_error uses the substring form ('\"error\"' in tool_result) — every tool error path serializes an error key, so it is safe and side-effect-free; kept at module scope so the 16-01 test imports the exact seam the SSE emit uses"
  - "Isolated test_system_prompt_citation_guidance from the ambient SYSTEM_PROMPT .env override (Rule 3) so it pins the shipped config default, not the dev's runtime prompt — the assertion content is unchanged"

patterns-established:
  - "Bearer-header external-provider transport (no key in body/logs/SSE)"
  - "Single pure classifier seam shared by production emit + unit test"

requirements-completed: [WSRCH-01, WSRCH-02, WSRCH-03, WSRCH-04]

# Metrics
duration: 7min
completed: 2026-07-12
---

# Phase 16 Plan 02: Web-Search Backend Restoration Summary

**Surgical four-file backend fix that turns the plan 16-01 RED baseline GREEN: `_search_tavily` now authenticates header-only via `Authorization: Bearer` (no body `api_key`) with a settings-driven `search_depth`, the system prompt encodes inline-markdown + trailing-`Sources:` citations and a tool-error nudge, `chat.py` exposes a pure `tool_result_is_error` classifier that flags `is_error` on the `tool_result` SSE event, and `scrub_secrets` now redacts `tvly-` keys.**

## Performance

- **Duration:** ~7 min
- **Started:** 2026-07-12T00:00:42Z
- **Completed:** 2026-07-12T00:08:12Z
- **Tasks:** 3
- **Files modified:** 5 (4 production + 1 test-robustness fix)

## Accomplishments
- **WSRCH-01 / D-04 (Task 1):** `_search_tavily` sends `headers={"Authorization": f"Bearer {settings.web_search_api_key}"}`, removed the body `api_key`, and reads `search_depth` from the new `settings.web_search_depth` (default `"basic"`, env `WEB_SEARCH_DEPTH`). URL, `timeout=30`, `include_answer`, `max_results`, the content→snippet mapping, and the `except Exception` → `logger.error(..., exc_info=True)` + `{"error", "results": []}` path were preserved exactly. No new dependency.
- **WSRCH-03 / D-01 / D-02 / D-03-nudge (Task 2):** `system_prompt` now instructs inline markdown-link citations at point-of-use PLUS a trailing `"Sources:"` list, steers KB-for-rules / web_search-for-current-external-facts, and adds the one-sentence tool-error acknowledgement nudge. `chat.py` TOOL_SELECTION_GUIDE + `WEB_SEARCH_TOOL.description` encode the D-01 external/not-in-KB board-game framing.
- **WSRCH-04 / D-03-backend / Security (Task 3):** Extracted the pure module-level `tool_result_is_error(tool_result)` in `routers.chat`; the `tool_result` SSE event now carries `"is_error"` and the persisted `tool_entry` status is `"error"` on a failed result. `scrub_secrets` gained a compiled `tvly-[A-Za-z0-9_-]+` pattern (redacts to `[redacted-key]`) with no `sk-or-` regression.
- **WSRCH-02 verified, not rebuilt:** the `settings.web_search_enabled` gate on the `WEB_SEARCH_TOOL` append and the `search_web` service guard were confirmed intact by inspection + `test_gating_fail_closed`.

## Task Commits

Each task was committed atomically:

1. **Task 1: Bearer transport + settings-driven search_depth** — `968a7fa` (fix)
2. **Task 2: D-02 citation format + D-01 steer + D-03 error-ack nudge** — `5f19ac6` (feat)
3. **Task 3: tool_result_is_error classifier + is_error SSE flag + tvly- scrub** — `8b1e047` (feat)

**Plan metadata:** docs commit — this SUMMARY + STATE/ROADMAP/REQUIREMENTS.

## Files Created/Modified
- `backend/services/web_search_service.py` — header-only Bearer auth; body `api_key` removed; `search_depth` from `settings.web_search_depth`; graceful-error + `exc_info` log preserved.
- `backend/config.py` — added `web_search_depth: str = "basic"`; rewrote the `system_prompt` citation clause (inline links + `Sources:` list + KB/web steer + error-ack nudge).
- `backend/routers/chat.py` — added module-level `tool_result_is_error()`; tool_result SSE emit computes `_is_error`, sets `tool_entry["status"]` to `"error"`/`"complete"`, and adds `"is_error"` to the event payload; expanded TOOL_SELECTION_GUIDE + WEB_SEARCH_TOOL description with the D-01 steer.
- `backend/services/log_scrub.py` — added `_TAVILY_KEY` regex; `scrub_secrets` now redacts `tvly-` alongside `sk-or-`.
- `backend/tests/test_web_search.py` — **test-robustness fix (deviation):** isolated `test_system_prompt_citation_guidance` from the ambient `SYSTEM_PROMPT` `.env` override (see Deviations).

## Verification (RED → GREEN)

All 10 plan-16-01 contract tests now GREEN:

| Test | Result |
|------|--------|
| test_web_search.py::test_tavily_bearer_auth | PASS |
| test_web_search.py::test_tavily_maps_results | PASS |
| test_web_search.py::test_search_depth_passed | PASS |
| test_web_search.py::test_gating_fail_closed | PASS |
| test_web_search.py::test_system_prompt_citation_guidance | PASS |
| test_web_search.py::test_graceful_failure_logs | PASS |
| test_web_search.py::test_tool_result_error_status | PASS |
| test_config.py::test_web_search_depth_default | PASS |
| test_config.py::test_web_search_depth_env_override | PASS |
| test_config.py::test_scrub_secrets_redacts_tavily | PASS |

- `cd backend && venv/Scripts/python -m pytest tests/test_web_search.py tests/test_config.py -q` → **23 passed, 1 failed** (the 1 failure is the pre-existing `test_key_encryption_secret_default`, env-dependent — see Issues).
- `cd backend && venv/Scripts/python -m pytest -q` → **288 passed, 1 failed, 2 errors** (up from the 16-01 baseline of 281 passed; the 7 previously-RED web-search tests are now GREEN). The 1 failure + 2 errors are all pre-existing, out-of-scope, and already tracked in `deferred-items.md`. No regressions.
- Static: `grep -c '"api_key"'` → 0; Bearer header present; `tool_result_is_error` + `"is_error"` + `tvly-` present; `settings.web_search_enabled` gating (uncommented) intact.

## Decisions Made
- Deleted the body `api_key` outright rather than leaving it as a harmless duplicate — Tavily's header-only contract makes it dead weight and RESEARCH Pitfall 2 explicitly flags leaving it as a leak/confusion risk.
- Used the substring `'"error"' in tool_result` classifier form (executor discretion allowed by the plan) — cheaper and side-effect-free vs. `json.loads`, and correct because every tool error path serializes an `"error"` key.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking test coupling] Isolated the citation-guidance test from an ambient `SYSTEM_PROMPT` .env override**
- **Found during:** Task 2 verification.
- **Issue:** The local `.env` sets `SYSTEM_PROMPT` to a minimal 68-char prompt. `pydantic-settings` (via `load_dotenv` → `os.environ`) resolves that override ahead of the `config.py` field default, so `test_system_prompt_citation_guidance` — which reads `Settings().system_prompt` — could never observe the new default guidance regardless of the config edit. The test was coupled to ambient deployment state rather than the shipped code default it is meant to pin.
- **Fix:** `import config` first (so `load_dotenv` has run), then `monkeypatch.delenv("SYSTEM_PROMPT", raising=False)` before constructing `Settings()`. The assertion content (`"Sources:"` / `"inline"`) is unchanged — the test now deterministically validates the config default. Mirrors the existing `_env_override` tests' use of `monkeypatch`.
- **Files modified:** `backend/tests/test_web_search.py`
- **Commit:** `5f19ac6`

## User Setup Required

**Local (and prod) `SYSTEM_PROMPT` env override shadows the new citation guidance.** The code default in `backend/config.py` now carries the D-01/D-02/D-03 guidance, and the app uses it **only when no `SYSTEM_PROMPT` env var is set**. The dev `.env` currently sets a minimal `SYSTEM_PROMPT` ("You are a helpful assistant. Answer questions clearly and concisely."), which overrides the new default at runtime. To activate inline-link + `Sources:` citations and the KB/web steer in the running app:
- **Local:** remove (or update) `SYSTEM_PROMPT` from the repo-root `.env`.
- **Prod:** verify `.env.prod` / the Fly secret does not pin a stale `SYSTEM_PROMPT` (a prod-verify concern for the phase's ops plan). The `.env` files are permission-restricted and untracked, so this SUMMARY flags it rather than editing them.

Web-search itself also requires `WEB_SEARCH_API_KEY` (a `tvly-` key) to be set for the tool to appear (fail-closed gating) — an existing ops step, unchanged by this plan.

## Known Stubs
None — the transport returns real Tavily results, `is_error` is a real computed flag, and no hardcoded empty value flows to the UI.

## Issues Encountered
- **Pre-existing, out-of-scope failures (NOT fixed, already tracked in `deferred-items.md`):**
  - `test_config.py::test_key_encryption_secret_default` FAILS because the local `.env` has `KEY_ENCRYPTION_SECRET` set (v1.2 BYOK) — same env-dependent failure 16-01 flagged.
  - `test_record_manager.py::test_check_duplicate_integration` / `::test_find_previous_version_integration` ERROR (missing `user_id` fixture) — known pre-v1.1 test debt.
  - Neither is collateral from this plan (confirmed against the 16-01 baseline counts).

## Threat Surface
No new security-relevant surface beyond the plan's `<threat_model>`. T-16-03 (tvly- key in exc_info logs) and T-16-04 (key in SSE/tool-result payload) are mitigated as planned: the key rides the `Authorization` header only, `scrub_secrets` now redacts `tvly-` as whole-process defense-in-depth, and the SSE `tool_result` event carries only the output preview + `is_error` flag. No new endpoint, no user-controlled URL (endpoint is the hardcoded constant), no `verify=False`.

## Next Phase Readiness
- The backend contract is complete and GREEN. Plan 16-03 (frontend failed-state render) can consume the `is_error` boolean now present on every `tool_result` SSE event and the `"error"` `tool_entry` status.
- Ops follow-up (flagged above): remove the `SYSTEM_PROMPT` override from `.env`/`.env.prod` so the new citation guidance is actually served, and set `WEB_SEARCH_API_KEY` in prod for the tool to activate.
- No blockers.

## Self-Check: PASSED

---
*Phase: 16-web-search-restoration*
*Completed: 2026-07-12*
