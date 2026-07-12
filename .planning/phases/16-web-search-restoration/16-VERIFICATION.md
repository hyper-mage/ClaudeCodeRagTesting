---
phase: 16-web-search-restoration
verified: 2026-07-12T17:39:00Z
status: passed
score: 5/5 must-haves verified
overrides_applied: 0
re_verification:
  # No previous VERIFICATION.md existed — initial verification
---

# Phase 16: Web Search Restoration Verification Report

**Phase Goal:** The agent's `web_search` tool works end-to-end again — users get answers grounded in current web information, with cited sources — and it is verified live on prod.
**Verified:** 2026-07-12T17:39:00Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

The phase goal is achieved. The single root-cause bug (Tavily requires header-only `Authorization: Bearer`, but the code posted the key as a body `api_key`) is fixed in the actual source, the fail-closed gating that already worked is preserved, citation guidance + a graceful failure path + a red failed-state tool card are all present in code, and the 10 phase-16 contract tests plus 2 sk-or regression guards pass (12/12). The live-prod smoke (SC-1/SC-3/SC-4/SC-5) was performed and recorded by the owner in 16-04-SUMMARY.md — the human-gated verification the phase required is complete, not outstanding.

### Observable Truths (ROADMAP Success Criteria — the contract)

| #   | Truth (Success Criterion) | Status     | Evidence       |
| --- | ------------------------- | ---------- | -------------- |
| SC-1 | Agent invokes `web_search` and returns an answer grounded in live web results, visible in the tool card | ✓ VERIFIED | Root-cause transport fix present: `web_search_service.py:24-34` posts `headers={"Authorization": f"Bearer {settings.web_search_api_key}"}`, no `api_key` in body, real `httpx.post` to `api.tavily.com`. Tool exposed via `chat.py:961-962`; tool card renders in `ToolCallCard.tsx`. Owner-confirmed live smoke on `boardgame-rag-prod` (v36): visible completed Web Search card + web-grounded answer (16-04-SUMMARY.md). |
| SC-2 | `web_search` offered only when a provider key is configured; cleanly absent + fail-closed when not | ✓ VERIFIED | Gating preserved: `chat.py:961` `if settings.web_search_enabled: tools.append(WEB_SEARCH_TOOL)`. Service re-guards: `web_search_service.py:12-13` returns `{"error":"Web search not configured","results":[]}` when disabled. `web_search_enabled` = `bool(web_search_api_key)` (`config.py:199-200`). Unit-verified: `test_gating_fail_closed` PASS. |
| SC-3 | The agent's response cites source URLs from web search | ✓ VERIFIED | `config.py:100-102` system_prompt default instructs inline markdown-link citations at point-of-use + a trailing `"Sources:"` list, plus KB-for-rules / web-for-current steer (`config.py:97-99`). Unit-verified: `test_system_prompt_citation_guidance` PASS. Owner-confirmed live: inline `[text](url)` links + Sources list (16-04). Operational dependency noted below. |
| SC-4 | A provider error returns a graceful result without crashing the turn, and is logged server-side | ✓ VERIFIED | `web_search_service.py:48-50` `except Exception` → `logger.error(..., exc_info=True)` + `return {"error": str(e), "results": []}`. Backend classifies via pure `tool_result_is_error` (`chat.py:81-89`), sets `tool_entry["status"]="error"` and emits `"is_error"` on the tool_result SSE event (`chat.py:1285-1286,1303`). Frontend maps `parsed.is_error → 'error'` (`useChat.ts:218`) → red `AlertTriangle` + red border (`ToolCallCard.tsx:88-93,129-133`). Unit-verified: `test_graceful_failure_logs`, `test_tool_result_error_status` PASS. Owner-confirmed live: red card + agent ack + best-effort, no crash (16-04). |
| SC-5 | Web search verified working against the production key on the live prod deployment | ✓ VERIFIED (human, recorded) | Owner-performed live prod smoke recorded in 16-04-SUMMARY.md: `boardgame-rag-prod`, `WEB_SEARCH_API_KEY` Fly secret set (Deployed, digest `feca87ad`), `SYSTEM_PROMPT` secret unset so shipped citation guidance applies, machines restarted (v36) so `@lru_cache get_settings()` re-read and `web_search_enabled` is true. Accepted per launching-agent directive (no automated artifact can cover a live prod key). |

**Score:** 5/5 truths verified

### Plan-Frontmatter Must-Haves (additional detail — all VERIFIED)

| Must-have | Status | Evidence |
| --------- | ------ | -------- |
| Bearer-header transport, no body `api_key`, settings-driven `search_depth` (16-02) | ✓ VERIFIED | `web_search_service.py:26-31`; `grep -c '"api_key"'` = 0 |
| `web_search_depth` setting (default `"basic"`, env `WEB_SEARCH_DEPTH`) (16-02) | ✓ VERIFIED | `config.py:139`; `test_web_search_depth_default` / `_env_override` PASS |
| `tool_result_is_error` pure classifier + `is_error` SSE flag + `"error"` status (16-02) | ✓ VERIFIED | `chat.py:81-89,1285-1286,1303`; `test_tool_result_error_status` PASS |
| `scrub_secrets` redacts `tvly-` keys alongside `sk-or-` (16-02, Security) | ✓ VERIFIED | `log_scrub.py:20,32`; `test_scrub_secrets_redacts_tavily` PASS, no sk-or regression |
| `ToolEvent.status` + `ToolCallCard` Props include `'error'`; is_error→status mapping (16-03) | ✓ VERIFIED | `useChat.ts:21,218`; `ToolCallCard.tsx:12` |
| Red failed-state render (AlertTriangle + red border) on `status === 'error'` (16-03) | ✓ VERIFIED | `ToolCallCard.tsx:88-93,129-133` |

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `backend/services/web_search_service.py` | Bearer transport + settings-driven depth; graceful error + exc_info log | ✓ VERIFIED | Authorization Bearer header (26); no `api_key` body key; `search_depth: settings.web_search_depth` (31); except→logger.error(exc_info=True)+{error} preserved (48-50) |
| `backend/config.py` | `web_search_depth` setting + D-01/D-02/D-03 system_prompt guidance | ✓ VERIFIED | `web_search_depth: str = "basic"` (139); inline-link + Sources + KB/web steer + error-ack nudge (95-108) |
| `backend/routers/chat.py` | `tool_result_is_error` classifier + `is_error` SSE flag + D-01 steer | ✓ VERIFIED | helper (81-89); is_error emit (1303); status=error (1286); WEB_SEARCH_TOOL desc (413-416) + TOOL_SELECTION_GUIDE web_search line (643) |
| `backend/services/log_scrub.py` | `scrub_secrets` extended to `tvly-` | ✓ VERIFIED | `_TAVILY_KEY` regex (20) applied in `scrub_secrets` (32) |
| `frontend/src/hooks/useChat.ts` | `'error'` in ToolEvent union + is_error mapping | ✓ VERIFIED | union (21); `parsed.is_error ? 'error' : 'complete'` (218) |
| `frontend/src/components/ToolCallCard.tsx` | red failed-state branch keyed on status | ✓ VERIFIED | AlertTriangle import (2); Props union (12); red border (88-93); red icon (129-133) |
| `backend/tests/test_web_search.py` | 7 RED→GREEN contract tests | ✓ VERIFIED | 7 tests, all PASS |
| `backend/tests/test_config.py` | depth default/override + tvly- scrub tests | ✓ VERIFIED | 3 phase tests PASS; sk-or tests untouched + PASS |
| `.planning/phases/16-web-search-restoration/16-04-SUMMARY.md` | recorded SC-1..SC-5 live evidence | ✓ VERIFIED | Contains SC-5 evidence, boardgame-rag-prod v36, no raw key |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | -- | --- | ------ | ------- |
| `web_search_service._search_tavily` | `api.tavily.com/search` | `httpx.post headers Authorization Bearer` (no body api_key) | ✓ WIRED | Header present (26); body api_key removed (grep count 0) |
| `chat.py tool_result SSE emit` | `useChat tool_result handler` | `is_error` flag computed by `tool_result_is_error(tool_result)` | ✓ WIRED | Backend emits `"is_error": _is_error` (1303); frontend reads `parsed.is_error` (218) |
| `chat.py WEB_SEARCH_TOOL append` | `settings.web_search_enabled` | conditional `tools.append` gate | ✓ WIRED | `if settings.web_search_enabled:` (961) — uncommented, preserved |
| `log_scrub.scrub_secrets` | logs + SSE error payloads | `tvly-` redaction to `[redacted-key]` | ✓ WIRED | `_TAVILY_KEY.sub("[redacted-key]", s)` (32) |
| `useChat tool_result handler` | `ToolCallCard status render` | `status === 'error'` → red AlertTriangle + red border | ✓ WIRED | Union flows useChat→MessageBubble→ToolCallCard; build green (16-03) |
| `fly secrets set WEB_SEARCH_API_KEY` | `get_settings() @lru_cache` | machine restart re-reads → web_search_enabled true | ✓ WIRED | Owner-confirmed restart v36 post-secret (16-04) |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| -------- | ------------- | ------ | ------------------ | ------ |
| `_search_tavily` result | `results` / `answer` | `httpx.post(api.tavily.com)` → `response.json()` | Yes — real Tavily 200 body mapped content→snippet | ✓ FLOWING |
| tool_result SSE `is_error` | `_is_error` | `tool_result_is_error(tool_result)` — computed from real tool output string | Yes — not hardcoded | ✓ FLOWING |
| `ToolCallCard` status | `status` prop | `useChat` maps `parsed.is_error` off the live SSE event | Yes — real backend flag, defaults to `'complete'` on legacy | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| Phase-16 backend contract tests | `pytest tests/test_web_search.py tests/test_config.py::test_web_search_depth_* tests/test_config.py::test_scrub_secrets_*` | 12 passed | ✓ PASS |
| No `api_key` remains in Tavily body | `grep -c '"api_key"' web_search_service.py` | 0 | ✓ PASS |
| Bearer header present | `grep Authorization.*Bearer web_search_service.py` | match | ✓ PASS |
| Live prod success + failure smoke | browser MCP against live prod (owner) | cited answer + card / red card + ack | ? recorded by owner (16-04) |

### Probe Execution

No `scripts/*/tests/probe-*.sh` probes are declared or conventional for this phase (test-driven backend + frontend restoration; the live smoke is a human checkpoint, not a probe script). Probe step: N/A.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| ----------- | ----------- | ----------- | ------ | -------- |
| WSRCH-01 | 16-01, 16-02, 16-04 | Answers grounded in current web info via restored `web_search` | ✓ SATISFIED | Bearer transport fix + live smoke (SC-1) |
| WSRCH-02 | 16-01, 16-02, 16-04 | Tool exposed when provider configured; fail-closed when not | ✓ SATISFIED | Gating + service guard + `test_gating_fail_closed` (SC-2) |
| WSRCH-03 | 16-01, 16-02, 16-04 | Agent cites source URLs from web results | ✓ SATISFIED | D-02 citation guidance + `test_system_prompt_citation_guidance` + live smoke (SC-3) |
| WSRCH-04 | 16-01, 16-02, 16-03, 16-04 | Failures return graceful error (no crash), logged; failed-state UX | ✓ SATISFIED | Graceful-error path + is_error SSE flag + red card + tests (SC-4) |

All 4 declared requirement IDs are accounted for. REQUIREMENTS.md maps exactly WSRCH-01..04 to Phase 16 (all marked Complete); no orphaned Phase-16 requirements. WSRCH-F1/F2 are explicitly Future/Out-of-Scope.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| (none) | — | No TBD/FIXME/XXX in any phase-modified production file | — | Clean |
| (none) | — | No TODO/HACK/PLACEHOLDER/"not yet implemented" in phase files | — | Clean |

No debt markers, no stub returns, no hollow props. The `{"error": ..., "results": []}` return is a real graceful-degradation path (not a stub), and `is_error` / `status` are real computed values, not hardcoded.

### Human Verification Required

None outstanding. The phase's human-gated live-prod verification (SC-1/SC-3/SC-4/SC-5, plan 16-04, `autonomous:false`) was already performed and recorded by the owner in 16-04-SUMMARY.md — a completed checkpoint, not an open item. Per the launching-agent directive, the owner's recorded confirmation satisfies the live-smoke must-haves.

### Gaps Summary

No gaps. All 5 ROADMAP success criteria and all 6 plan-frontmatter must-haves are backed by real, wired source code (not SUMMARY narrative). The 12 phase-16 automated tests pass. The live-prod smoke that only a human could run is complete and documented.

**Notes (informational, not gaps):**
- **SC-3 operational dependency:** the D-01/D-02/D-03 citation guidance lives in the `config.py` `system_prompt` *default*. It reaches the LLM only when no `SYSTEM_PROMPT` env/secret shadows it. This was correctly handled in prod (owner unset the prod `SYSTEM_PROMPT` secret, 16-04). Local dev `.env` still pins a minimal `SYSTEM_PROMPT`, so citations activate locally only if that override is removed — a dev-env config detail, not a code defect. Future prod ops must keep `SYSTEM_PROMPT` unset (or include the citation clause) or SC-3 formatting regresses.
- **Pre-existing suite debt (NOT phase 16):** `test_key_encryption_secret_default` fails (local `.env` sets `KEY_ENCRYPTION_SECRET`, v1.2 BYOK) and 2 `test_record_manager` fixture errors — confirmed pre-existing, tracked in `deferred-items.md`, unrelated to this phase.
- **Code review (16-REVIEW.md):** 0 critical, 3 warning, 2 info — advisory quality follow-up, no goal-blocking findings.

---

_Verified: 2026-07-12T17:39:00Z_
_Verifier: Claude (gsd-verifier)_
