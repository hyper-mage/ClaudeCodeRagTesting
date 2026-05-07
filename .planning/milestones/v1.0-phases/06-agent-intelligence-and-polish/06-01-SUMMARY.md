---
phase: 06-agent-intelligence-and-polish
plan: 01
subsystem: backend-services
tags: [tiktoken, token-budget, source-routing, scope-parsing, openrouter, pydantic-settings]

requires:
  - phase: 05-explorer-sub-agent
    provides: "Budget enforcement patterns (max_iterations, tool result clipping) extended to parent agent"
provides:
  - "Token counting helpers (count_tokens, count_message_tokens) with cl100k_base + OpenAI message overhead math"
  - "TokenBudget class tracking system / history / tool-result categories with FIFO oldest-pair truncation preserving assistant+tool pairing"
  - "fetch_model_context_length helper that queries OpenRouter /api/v1/models with graceful fallback"
  - "infer_source_scope keyword heuristic returning default_kb | private | both (D-01, D-02)"
  - "parse_scope_hint natural-language scope parser for folder/source narrowing (D-08, D-09)"
  - "Four new budget settings in config.py (model_context_length, response_reserve_tokens, budget_safety_margin, tool_schema_tokens)"
affects: [06-02, chat-event-generator, subagent-alignment]

tech-stack:
  added: ["tiktoken==0.12.0"]
  patterns:
    - "Module-level tiktoken encoding singleton shared across threads"
    - "Paired (assistant tool_call + tool result) truncation by call_id set to avoid orphaned tool messages"
    - "Keyword-only source routing (no LLM call) defaulting to 'both' when ambiguous"
    - "Stateless per-message scope parsing (no persistence between turns)"

key-files:
  created:
    - "backend/services/budget_service.py"
    - "backend/tests/test_budget_service.py"
  modified:
    - "backend/config.py"
    - "backend/requirements.txt"

key-decisions:
  - "Used tiktoken cl100k_base as cross-model approximation; 5% safety margin absorbs 5-15% variance for non-OpenAI models"
  - "Truncation pops oldest tool-result pair and removes both the assistant tool_call message and its paired tool result, matched by call_id set"
  - "Source routing is a hint, not a filter -- LLM still sees all tools (Pitfall 4)"
  - "parse_scope_hint source-hints win over folder-hints when both present, since source hints are more explicit"

patterns-established:
  - "Four-category budget tracking (system / history / tool-result pairs / response reserve) with configurable safety margin"
  - "Keyword heuristic + default-to-both ambiguity rule for invisible source routing"

requirements-completed: [AGNT-01, AGNT-02, AGNT-03, AGNT-04]

duration: 10 min
completed: 2026-04-22
---

# Phase 06 Plan 01: Token Budget Service Summary

**tiktoken-backed TokenBudget class plus source routing and scope parsing heuristics -- standalone, fully tested, ready to wire into the chat loop in Plan 02.**

## Performance

- **Duration:** 10 min
- **Started:** 2026-04-22T03:17:47Z
- **Completed:** 2026-04-22T03:27:26Z
- **Tasks:** 1 (TDD: RED + GREEN)
- **Files modified:** 4

## Accomplishments

- TokenBudget tracks four categories (system / history / tool-result pairs / response reserve) and truncates the oldest tool-call round-trip without orphaning `role=tool` messages (Pitfall 3)
- `count_message_tokens` matches the OpenAI cookbook formula: 4 tokens per message + content + serialized tool_calls + 2-token reply priming
- `fetch_model_context_length` queries OpenRouter `/api/v1/models`, returns None on any failure so callers fall back to `settings.model_context_length` (128k default)
- `infer_source_scope` returns "default_kb" when user has no private docs, "private" on explicit private signals without default-KB keywords, and "both" otherwise (D-02)
- `parse_scope_hint` handles "only search X", "look in my uploads", and folder paths containing `/` with stateless per-message evaluation (D-09)

## Task Commits

1. **Task 1 RED:** failing tests + config + requirements -- `4a739c8` (test)
2. **Task 1 GREEN:** budget_service.py implementation -- `bfcdf30` (feat)

_No REFACTOR commit -- implementation was already clean at GREEN._

## Files Created/Modified

- `backend/services/budget_service.py` - NEW: token counting, TokenBudget, source routing, scope parsing, OpenRouter context-length lookup
- `backend/tests/test_budget_service.py` - NEW: 30 unit tests across 6 test classes
- `backend/config.py` - MODIFIED: added `model_context_length`, `response_reserve_tokens`, `budget_safety_margin`, `tool_schema_tokens`
- `backend/requirements.txt` - MODIFIED: added `tiktoken==0.12.0`

## Decisions Made

- **Paired truncation via call_id set:** Each `add_tool_result_pair` records the assistant's tool_call ids so `truncate_oldest_tool_results` can drop both messages together, matched by id. Avoids the "tool_call_id not found" API error documented in research Pitfall 3.
- **Source-hint precedence in parse_scope_hint:** When a user says both "my uploads" and "search Board Games/Catan/", we return `{"source_hint": "private"}`. Source hints are more explicit than folder hints and the folder hint would conflict with the source.
- **Safety margin as int() floor:** `int(context_length * (1 - margin))` floors, so we err on the low side of available tokens -- matches the Pitfall 1 "add a safety margin" guidance.
- **fetch_model_context_length requires ctx > 0:** Guards against API returning `null` or `0` (Pitfall 5 -- budget immediately exhausted on first message).

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required. tiktoken installs silently and fetches its BPE data on first use.

## Next Phase Readiness

- budget_service is fully testable and standalone; Plan 02 can import `TokenBudget`, `infer_source_scope`, `parse_scope_hint`, `fetch_model_context_length` directly
- Config settings are in place so Plan 02's integration into `chat.py` event_generator only needs to wire the pieces together
- Tool schema token estimate (3000 default) is a static starting point -- Plan 02 may want to compute it dynamically once at startup from the tool list

## Self-Check: PASSED

- File `backend/services/budget_service.py` exists: FOUND
- File `backend/tests/test_budget_service.py` exists: FOUND
- Commit `4a739c8` present: FOUND
- Commit `bfcdf30` present: FOUND
- `pytest tests/test_budget_service.py` result: 30 passed, 0 failed
- All acceptance criteria grep-verified (tiktoken.get_encoding, openrouter.ai/api/v1/models, config fields, requirements.txt entry)

---
*Phase: 06-agent-intelligence-and-polish*
*Completed: 2026-04-22*
