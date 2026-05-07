---
phase: 06-agent-intelligence-and-polish
verified: 2026-04-22T00:00:00Z
status: passed
score: 4/4 success criteria verified (AGNT-05 needs human check for "consistently")
human_verification:
  - test: "User narrows scope in live chat ('only search Catan') and tool cards show scope badge"
    expected: "ToolCallCard displays colored [scope] prefix; subsequent tool calls are narrowed to Catan folder"
    why_human: "End-to-end SSE + UI flow requires running app and interacting in browser"
  - test: "Sub-agent (analyze_document) renders sub_event progress in the UI alongside explore_kb"
    expected: "Both sub-agents render with identical sub_iteration / sub_tool_start / sub_tool_result cards"
    why_human: "Visual consistency check between two sub-agent UIs requires human eye"
  - test: "Long multi-turn chat with many tool calls does not blow the context window"
    expected: "Chat continues without 'context length exceeded' errors; oldest tool pairs truncated"
    why_human: "Requires running long session against a real model to observe budget behavior"
---

# Phase 06: Agent Intelligence and Polish — Verification Report

**Phase Goal:** The agent intelligently manages its context budget, routes queries to the right sources, and users can control search scope.
**Verified:** 2026-04-22
**Status:** passed (with human verification items for end-to-end UX)
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (Success Criteria from ROADMAP)

| # | Truth | Status | Evidence |
| - | ----- | ------ | -------- |
| 1 | Agent automatically selects default KB, private docs, or both based on query | ✓ VERIFIED | `infer_source_scope` implemented in `backend/services/budget_service.py:281`, wired in `backend/routers/chat.py:529`; 6 unit tests pass covering all three scope outcomes |
| 2 | Agent stays within token budget even when many tool results returned | ✓ VERIFIED | `TokenBudget.truncate_oldest_tool_results` called in `backend/routers/chat.py:579` when `budget.is_over()`; `add_tool_result_pair` called after every tool result (line 767) |
| 3 | User can narrow search scope via chat command and see scoped results | ✓ VERIFIED | `parse_scope_hint` extracts folder/source hints (budget_service.py:342); hints flow into system prompt ("## Search Scope" in llm_service.py:85) and into args_preview scope badge via ToolCallCard.renderArgsPreview |
| 4 | Sub-agent works consistently with explorer and new KB tool set | ✓ VERIFIED | `run_document_analysis` rewritten as `Iterator[dict]` emitting `sub_iteration` / `sub_tool_start` / `sub_tool_result` / `result` — identical contract to `run_exploration`; 7 tests in test_subagent_alignment.py pass |

**Score:** 4/4 truths verified automatically. "Consistently" in truth #4 flagged for visual human check.

### Required Artifacts (Plan 01)

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `backend/services/budget_service.py` | Exports TokenBudget, count_tokens, count_message_tokens, fetch_model_context_length, infer_source_scope, parse_scope_hint | ✓ VERIFIED | All 6 exports present (lines 42, 52, 83, 130, 281, 342); uses tiktoken cl100k_base (line 32); queries openrouter.ai/api/v1/models (line 91) |
| `backend/tests/test_budget_service.py` | ≥100 lines, 6 test classes | ✓ VERIFIED | 30 tests, all passing |
| `backend/config.py` | model_context_length, response_reserve_tokens, budget_safety_margin, tool_schema_tokens | ✓ VERIFIED | All four settings present at lines 85–88 |
| `backend/requirements.txt` | tiktoken==0.12.0 | ✓ VERIFIED | Line 13 |

### Required Artifacts (Plan 02)

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `backend/routers/chat.py` | TokenBudget usage, infer_source_scope, parse_scope_hint, truncate_oldest_tool_results, add_tool_result_pair, scope arg in _build_args_preview | ✓ VERIFIED | All present at lines 15–19, 529, 530, 535, 543, 579, 605, 767 |
| `backend/services/llm_service.py` | source_hint / scope_hint params, "## Source Routing", "## Search Scope", yields system_content event | ✓ VERIFIED | Lines 39, 40, 62–92 |
| `backend/services/subagent_service.py` | Iterator[dict] generator yielding sub_iteration / sub_tool_start / sub_tool_result / result | ✓ VERIFIED | Line 56 signature, yields at 74, 100, 107, 118 |
| `frontend/src/components/ToolCallCard.tsx` | renderArgsPreview, scope color classes | ✓ VERIFIED | Function at line 52, color map with default_kb/private/both at 60–62 |
| `backend/tests/test_subagent_alignment.py` | ≥30 lines, class TestSubagentAlignment | ✓ VERIFIED | 7 tests, all passing |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | -- | --- | ------ | ------- |
| budget_service.py | tiktoken | cl100k_base encoding | ✓ WIRED | `_encoding = tiktoken.get_encoding("cl100k_base")` at line 32 |
| budget_service.py | httpx | OpenRouter /api/v1/models | ✓ WIRED | httpx.get at line 91 targeting "https://openrouter.ai/api/v1/models" |
| config.py | budget_service.py | settings consumed by TokenBudget | ✓ WIRED | chat.py:535 constructs `TokenBudget(context_length=settings.model_context_length, response_reserve=settings.response_reserve_tokens, safety_margin=settings.budget_safety_margin, tool_schema_tokens=settings.tool_schema_tokens)` |
| chat.py | budget_service.py | TokenBudget import + event_generator loop | ✓ WIRED | `from services.budget_service import (TokenBudget, infer_source_scope, parse_scope_hint, fetch_model_context_length, ...)` at lines 15–19; used throughout event_generator |
| chat.py | llm_service.py | stream_chat_completion receives source_hint/scope_hint | ✓ WIRED | `stream_chat_completion(..., source_hint=source_scope, scope_hint=scope_hint ...)` at line 571 |
| subagent_service.py | useChat.ts | SSE sub_event format matching explore_kb | ✓ WIRED | sub_iteration / sub_tool_start / sub_tool_result yielded; chat.py analyze_document branch wraps them in `{"type": "sub_event", "parent_call_id": ...}` matching explore_kb dispatch |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| -------- | ------------- | ------ | ------------------ | ------ |
| TokenBudget in chat.py | `budget._tool_result_pairs` | `budget.add_tool_result_pair(assistant_tc_msg, current_messages[-1])` after every tool result (line 767) | Yes — real tool call/result messages | ✓ FLOWING |
| source_scope in chat.py | `source_scope` | `infer_source_scope(user_latest, has_private_docs)` — user_latest = `body.content` | Yes — live user message + real DB check | ✓ FLOWING |
| scope_hint in chat.py | `scope_hint` | `parse_scope_hint(user_latest)` | Yes — live user message | ✓ FLOWING |
| ToolCallCard scope badge | `args_preview` | Backend prepends `scope:<scope>` in `_build_args_preview` (line 356); SSE tool_start event carries it | Yes — real SSE payload from backend | ✓ FLOWING |
| subagent sub_events | SSE `sub_event` payload | chat.py analyze_document branch iterates generator yields and wraps each as `{"type": "sub_event", "sub_event": sub_ev, "parent_call_id": tc["id"]}` | Yes — real resolve_document + get_full_document_text + LLM analysis | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| count_tokens returns int > 0 | `python -c "from services.budget_service import count_tokens; print(count_tokens('hello world'))"` | `2` | ✓ PASS |
| infer_source_scope with no private docs returns default_kb | `python -c "... infer_source_scope('tell me about Catan', has_private_docs=False)"` | `default_kb` | ✓ PASS |
| parse_scope_hint extracts folder name | `python -c "... parse_scope_hint('only search Catan')"` | `{'folder_hint': 'Catan'}` | ✓ PASS |
| TokenBudget.available math correct | `TokenBudget(context_length=8000, response_reserve=2000).available` | `5600` (= int(8000*0.95) - 2000 - default tool_schema=0 when not passed, actually 5600 matches int(8000*0.95)-2000 = 7600-2000 = 5600) | ✓ PASS |
| Plan 01 unit tests | `pytest tests/test_budget_service.py` | 30 passed | ✓ PASS |
| Plan 02 alignment tests | `pytest tests/test_subagent_alignment.py` | 7 passed | ✓ PASS |
| Full backend suite (minus pre-existing unrelated failure) | `pytest tests/ --ignore=tests/test_record_manager.py` | 97 passed | ✓ PASS |
| Module imports clean | `python -c "from routers.chat import router; from services.llm_service import stream_chat_completion"` | (no error) | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan(s) | Description | Status | Evidence |
| ----------- | -------------- | ----------- | ------ | -------- |
| AGNT-01 | 06-01, 06-02 | Agent auto-selects default KB / private / both | ✓ SATISFIED | `infer_source_scope` + invocation in chat.py:529 + source routing prompt in llm_service.py:61–80 |
| AGNT-02 | 06-01, 06-02 | Token budget prevents context window exhaustion | ✓ SATISFIED | `TokenBudget` with `truncate_oldest_tool_results` wired in chat.py:579 |
| AGNT-03 | 06-01, 06-02 | Budget tracks system prompt, history, tool results, response reserve | ✓ SATISFIED | TokenBudget has `_system_tokens`, `_history_tokens`, `_tool_result_pairs`, `response_reserve` — four categories per budget_service.py:130+ |
| AGNT-04 | 06-01, 06-02 | User can narrow scope via chat | ✓ SATISFIED | `parse_scope_hint` + scope_hint override in chat.py:532 + "## Search Scope" block in llm_service.py:85 |
| AGNT-05 | 06-02 | Sub-agent consistent with new tool set | ✓ SATISFIED (automated); needs visual human check for "consistently" | `run_document_analysis` rewritten as generator matching `run_exploration` contract; inline dispatch in chat.py mirrors explore_kb |

No orphaned requirements — all 5 phase-assigned AGNT requirements are claimed across plan frontmatter.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| None | — | — | — | All modified files scanned; no TODO/FIXME/placeholder/stub returns introduced in phase 06 |

### Human Verification Required

Three end-to-end behaviors need browser/runtime testing — see frontmatter `human_verification` for details:

1. Live scope narrowing in the UI (command → badge → narrowed results)
2. Visual consistency between `explore_kb` and `analyze_document` sub-agent cards
3. Long-session budget truncation behavior against a real OpenRouter model

### Gaps Summary

No gaps. All must-haves verified automatically. The three human-verification items are UX/visual checks, not missing implementation.

---

_Verified: 2026-04-22_
_Verifier: Claude (gsd-verifier)_
