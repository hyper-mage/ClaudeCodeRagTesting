---
phase: 11-per-request-key-model-resolution-chat-loop-seam
plan: 03
subsystem: api
tags: [openrouter, openai-sdk, langsmith, byok, streaming, usage-accounting, rerank, subagent, explorer]

# Dependency graph
requires:
  - phase: 11-01
    provides: Wave 0 test stubs (test_langsmith_gate, test_usage_capture, test_key_model_resolution) and the conftest mock_stream_chat_completion usage-event extension
  - phase: 09
    provides: crypto_service.decrypt_key (consumed downstream by 11-04 at the resolution block)
provides:
  - "get_llm_client(api_key, trace) — per-request key fall-through + LangSmith wrap-gate (SEC-01/D-10)"
  - "stream_chat_completion(api_key, model, trace) — per-request threading + drain-and-accumulate trailing usage chunk (D-04)"
  - "_usage_to_dict helper — defensive usage normalization (cost authoritative, tolerant token fields)"
  - "rerank/rerank_with_llm, run_document_analysis, run_exploration/_summarize_findings, search_documents threaded with resolved api_key+model (D-01)"
affects: [11-04, phase-13, phase-15, phase-14]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Per-request key/model as explicit params (no module singleton, no @lru_cache on key-bearing fns)"
    - "LangSmith wrap-gate at client construction keyed on trace bool"
    - "Drain-and-accumulate streaming usage (capture chunk.usage before the choices==[] skip)"
    - "Aux model defaults to the single resolved turn model (D-02 shared-param seam)"

key-files:
  created: []
  modified:
    - backend/services/llm_service.py
    - backend/services/rerank_service.py
    - backend/services/subagent_service.py
    - backend/services/explorer_service.py
    - backend/services/retrieval_service.py
    - backend/tests/test_langsmith_gate.py
    - backend/tests/test_usage_capture.py
    - backend/tests/test_key_model_resolution.py

key-decisions:
  - "User-key turns pass trace=False so wrap_openai is skipped at construction (SEC-01/D-10) — owner/demo keep tracing"
  - "Removed the early return on finish_reason=='tool_calls' so the stream drains; usage rides the trailing choices==[] chunk and is captured before that chunk is skipped"
  - "Treat OpenRouter cost as authoritative; _usage_to_dict tolerates missing token sub-fields (A4)"
  - "Aux model = the shared resolved turn model param (D-02) — no distinct aux-model param this phase; value source deferred to P13/P15"
  - "rerank_with_api (separate dedicated rerank-provider key) and get_embedding_client left untouched"

patterns-established:
  - "Pattern: per-request api_key/model/trace params with owner-settings fall-through on every chat-turn LLM call site"
  - "Pattern: explorer threads all three owner-key read sites (loop client, loop create, _summarize_findings._try)"

requirements-completed: [SEC-04, SEC-01]

# Metrics
duration: 22min
completed: 2026-06-22
---

# Phase 11 Plan 03: Per-Request Key + Model Seam (chat-loop services) Summary

**Threaded per-request `api_key`/`model`/`trace` through `get_llm_client` and all four chat-turn LLM call sites, gated `wrap_openai` off for user keys, and restructured the stream loop to drain-and-capture the trailing OpenRouter usage chunk.**

## Performance

- **Duration:** ~22 min
- **Started:** 2026-06-22T16:00Z (approx)
- **Completed:** 2026-06-22T16:22Z (approx)
- **Tasks:** 2 (both TDD)
- **Files modified:** 8 (5 service, 3 test) + 1 deferred-items log

## Accomplishments
- `get_llm_client(api_key, trace)` builds a fresh per-call client with owner-key fall-through and skips LangSmith `wrap_openai` when `trace=False` (a user-key call) — SEC-01 / D-10. No module singleton, no `@lru_cache` (Pitfall 8 preserved).
- `stream_chat_completion(api_key, model, trace)` threads the per-request key/model and now **drains** the stream (early `return` on `tool_calls` removed), capturing the trailing `usage` chunk (`choices == []`) and yielding `{"type":"usage","usage":{…}}` before `{"type":"done"}` — D-04.
- All four aux/chat-turn sites threaded with the resolved key+model (D-01): `rerank`/`rerank_with_llm`, `run_document_analysis`, `run_exploration` + `_summarize_findings` (all three explorer owner-key read sites), and the `search_documents`→`rerank` hop.
- Un-skipped + implemented the three Wave 0 stubs this plan owns; targeted suite green.

## Task Commits

Each task was committed atomically (TDD: test → feat):

1. **Task 1 RED: wrap-gate + usage-drain tests** - `101c1d9` (test)
2. **Task 1 GREEN: trace-gate client + stream key/model params + usage drain** - `0db1afe` (feat)
3. **Task 2 RED: aux key/model threading test** - `04388fa` (test)
4. **Task 2 GREEN: thread api_key+model through aux call sites** - `d7aba4a` (feat)
5. **Deferred-items log update** - `9c60c4a` (chore)

_No REFACTOR commits needed — implementations were clean on first green._

## Files Created/Modified
- `backend/services/llm_service.py` - `get_llm_client(api_key, trace)` gate; `stream_chat_completion(api_key, model, trace)`; `_usage_to_dict` helper; drain-and-accumulate usage loop (early return removed).
- `backend/services/rerank_service.py` - `rerank_with_llm` + `rerank` accept/forward `api_key`/`model`/`trace`; `rerank_with_api` untouched.
- `backend/services/subagent_service.py` - `run_document_analysis` threads key/model into the client + `create`.
- `backend/services/explorer_service.py` - `run_exploration` builds the client once with the key; resolved `model` threads the loop `create` and `_summarize_findings._try` (Pitfall 4 — all three sites).
- `backend/services/retrieval_service.py` - `search_documents` forwards `api_key`/`model`/`trace` into the `rerank` hop.
- `backend/tests/test_langsmith_gate.py` - un-skipped + implemented `test_user_key_client_not_wrapped`.
- `backend/tests/test_usage_capture.py` - un-skipped + implemented `test_usage_summed_across_tool_loop` (drives `stream_chat_completion` with a tool_calls chunk + trailing usage-only chunk).
- `backend/tests/test_key_model_resolution.py` - un-skipped + implemented `test_user_key_threaded_to_all_call_sites` (asserts each aux site builds its client via `get_llm_client(api_key=user_key, trace=False)` and `create(model=resolved)`).

## Decisions Made
- **trace=False for user keys:** the test models a real user-key turn (chat.py will pass `trace=(not is_user_key)` in 11-04). User-key calls skip `wrap_openai`; owner/demo (`trace=True`) keep tracing.
- **Cost authoritative:** `_usage_to_dict` pulls `prompt_tokens`/`completion_tokens`/`total_tokens`/`cost` via getattr and tolerates missing token sub-fields (A4 / LiteLLM token-count caveat).
- **D-02 aux seam = shared `model` param:** no distinct aux-model parameter or config field added; aux defaults to the single resolved turn model. The aux-model value source (storage + picker) is deferred to Phase 13/15 by design — not a gap.
- **Untouched by design:** `get_embedding_client` (embedding/ingestion key) and `rerank_with_api` (separate dedicated rerank-provider key) are intentionally not threaded.

## Deviations from Plan

None - plan executed exactly as written. The only test adjustment (passing `trace=False` at the aux call sites in `test_user_key_threaded_to_all_call_sites`) reflects the realistic user-key invocation the plan specifies (`chat.py passes trace=(not is_user_key)`); it is not a deviation from the planned contract.

## Issues Encountered
- **No worktree venv:** the parallel worktree has no `backend/venv` (gitignored, lives in the shared checkout). Resolved by invoking the shared checkout's `venv/Scripts/python.exe` interpreter while running pytest from the worktree's `backend/` cwd — the conftest `sys.path.insert` resolves the worktree source. All targeted + regression tests ran green this way.
- **Pre-existing collection errors (out of scope):** `tests/test_e2e_subagent.py` (`KeyError: VITE_SUPABASE_URL`, live E2E) and `tests/test_record_manager.py::*_integration` (`fixture 'user_id' not found`, live-DB) error at collection independent of this plan's changes. Logged to `deferred-items.md`; not fixed (scope boundary). Unit suite otherwise green: 165 passed, 9 Wave-0 stubs skipped.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Plan 11-04 can now wire `chat.py`: build `_resolve_key_and_model`, decrypt the user key, and pass `api_key`/`model`/`trace=(not is_user_key)` into `stream_chat_completion` and the aux dispatch sites. The `{"type":"usage",...}` event is emitted for 11-04 to sum across the tool loop and persist to the `messages.usage` column (migration 029, already landed by 11-02).
- The remaining Wave-0 stubs in `test_usage_capture.py` (`test_usage_persisted_to_messages`) and `test_key_model_resolution.py` (5 stubs) are owned by plan 11-04.

## Self-Check: PASSED

All 5 modified service files present; all 6 task/doc commits (`101c1d9`, `0db1afe`, `04388fa`, `d7aba4a`, `9c60c4a`, `b4c854f`) found in git history. Targeted tests green (3 passed); regression unit suite green (165 passed, 9 Wave-0 stubs skipped). The 2 pre-existing live-integration collection errors are logged as deferred and out of scope.

---
*Phase: 11-per-request-key-model-resolution-chat-loop-seam*
*Completed: 2026-06-22*
