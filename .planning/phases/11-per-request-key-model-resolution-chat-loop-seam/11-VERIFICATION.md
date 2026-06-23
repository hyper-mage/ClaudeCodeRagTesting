---
phase: 11-per-request-key-model-resolution-chat-loop-seam
verified: 2026-06-22T22:10:00Z
status: human_needed
score: 4/4 must-haves verified (automated) — 2 MANDATORY manual SEC-01 gates pending human confirmation
overrides_applied: 0
re_verification:
  previous_status: none
  previous_score: n/a
  gaps_closed: []
  gaps_remaining: []
  regressions: []
human_verification:
  - test: "[MANDATORY GATE] wrap_openai gate verified against PROD LangSmith — send a BYOK chat turn with a real OAuth-provisioned user key against the prod LangSmith project"
    expected: "Zero LangSmith runs appear for that BYOK turn (the user's key + prompt never reach the owner's LangSmith project)"
    why_human: "Requires a live prod LangSmith project + a real OAuth-provisioned OpenRouter key. No automated test can observe the live prod LangSmith sink. The unit test (test_user_key_client_not_wrapped) proves trace=False yields a bare client, but the load-bearing SEC-01 evidence is a zero-run confirmation in the live prod project (A5/D-10). Flagged MANDATORY in 11-VALIDATION.md — BLOCKS phase sign-off."
  - test: "[MANDATORY GATE] sk-or- key scrubbed out of a logged exc_info traceback at the LIVE log sink — force a logged exception whose locals/str carry an sk-or- token in the running backend"
    expected: "The live log sink line shows [redacted-key] in the traceback, never the raw sk-or-v1-... token"
    why_human: "The unit test (test_logging_filter_scrubs_exc_info) covers the _ScrubFilter end-to-end through routers.chat with a capturing handler, but a live confirm needs a real logged exception carrying a key at the actual production/log-sink configuration (handler set, formatter, propagation). Flagged MANDATORY in 11-VALIDATION.md — BLOCKS phase sign-off."
  - test: "OpenRouter 402 (payment) vs 429 (rate-limit) surface distinctly against a live free-model rate cap / negative-balance owner key"
    expected: "A free-model demo turn driven past the per-minute cap yields code rate_limit; a negative-balance owner key yields payment_required — distinct structured SSE codes"
    why_human: "Requires tripping a live free-model rate cap or a real negative-balance owner key. The unit test (test_429_402_distinct_codes) proves the typed-catch order + distinct codes with synthetic openai.RateLimitError/APIStatusError(402); a live confirm validates real OpenRouter status mapping. Listed manual-only in 11-VALIDATION.md (non-blocking relative to the two MANDATORY gates)."
---

# Phase 11: Per-Request Key + Model Resolution (chat-loop seam) Verification Report

**Phase Goal:** Every chat turn resolves the correct key and model per request — the user's own key when connected, a gated owner-key fallback only when explicitly enabled, and a clean fail-closed refusal otherwise — with no cross-user key bleed and no secret leaking into observability.
**Verified:** 2026-06-22T22:10:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

All four ROADMAP success criteria are VERIFIED in the merged codebase with rigorous, non-vacuous automated tests. The full backend suite returns **174 passed + 2 known pre-existing `test_record_manager` fixture errors** (`fixture 'user_id' not found`) — the two errors are documented out-of-scope (file not in any Phase 11 `files_modified`, predate this work) and are NOT regressions and NOT this phase's scope. The 12 phase-specific Wave-0 tests are all green (un-skipped).

The phase goal is **functionally achieved in code**, but two SEC-01 truths are sealed only by MANDATORY manual gates (live prod LangSmith + live log sink) that no automated test can substitute. Per the verifier decision tree (human items present → status MUST be `human_needed`, never `passed`), the phase is `human_needed` pending those two human confirmations.

### Observable Truths

| # | Truth (ROADMAP Success Criterion) | Status | Evidence |
| --- | --- | --- | --- |
| 1 | SEC-04 — no cross-user bleed: key + model are explicit per-request params threaded `send_message` → `stream_chat_completion` → `get_llm_client`; every owner-key read (incl. budget `fetch_model_context_length`) uses the resolved value; resolver NOT a Settings method, NOT cached | ✓ VERIFIED | `chat.py:152` module-level `_resolve_key_and_model` (no `@lru_cache`, not `self`); `chat.py:787` resolves once/turn; `chat.py:808` `fetch_model_context_length(model, api_key)` (fifth read fixed, log line `{model}` at 812); `stream_chat_completion`/`run_exploration`/`run_document_analysis`/`execute_tool` all threaded `api_key=,model=,trace=(not is_user_key)` (chat.py:842-844, 923-925, 991-993, 1030-1032); `llm_service.py:11` fresh `OpenAI()` per call; `test_no_cross_user_bleed` + `test_user_key_threaded_to_all_call_sites` PASS |
| 2 | DEMO-03 — fail-closed: keyless + demo flag OFF → structured `no_api_key` SSE error, no LLM call; resolution is `if user_key / elif demo_fallback_enabled / else refuse`, never `user_key or owner_key` | ✓ VERIFIED | `chat.py:190-207` explicit three-branch (user→demo→refuse); `chat.py:790-797` `mode=="no_key"` yields `_sse_error("no_api_key", …)` then `return` BEFORE assistant-row insert and any LLM call; `config.py:36` `demo_fallback_enabled: bool = False`; `grep -v '^#' chat.py \| grep -c "user_key or owner_key"` → 0; `test_no_key_flag_off_refuses` + `test_fail_closed_no_or_fallback` (static + behavioral) + `test_demo_fallback_uses_free_model` PASS |
| 3 | SEC-01 — no secret in observability: `wrap_openai` gated OFF for user-key calls (trace=False); `scrub_secrets` (sk-or- regex) before SSE-error AND a `logging.Filter` (`_ScrubFilter`) scrubs the exc_info traceback, installed on ROOT handlers + `routers.chat` (NOT `getLogger("backend")`) | ✓ VERIFIED (code+unit) / ⏳ 2 MANDATORY live gates pending | `llm_service.py:26` `if trace and wrap_openai and settings.langsmith_api_key`; `log_scrub.py:15` `re.compile(r"sk-or-[A-Za-z0-9_-]+")` → `[redacted-key]`; `chat.py:34` `class _ScrubFilter(logging.Filter)` scrubs msg + exc_info traceback (renders to `exc_text`, clears `exc_info`); `chat.py:59-77` installed on ROOT handlers + `getLogger("routers.chat")`; `grep getLogger("backend").addFilter` → none; SSE path `scrub_secrets(str(e))` (chat.py:1182); `test_sk_or_scrubbed_in_sse_error` + `test_logging_filter_scrubs_exc_info` (end-to-end through real logger) + `test_user_key_client_not_wrapped` PASS. **Live prod-LangSmith zero-run + live log-sink redaction = MANDATORY human gates (see Human Verification).** |
| 4 | Model resolves three-tier (thread.model → user_preferences.default_model → owner) tolerating absent P13 schema; 429 vs 402 surface as distinct codes (rate_limit vs payment_required); trailing usage captured + summed across tool-loop + persisted to messages.usage | ✓ VERIFIED | `chat.py:172-177` three-tier with `_safe_thread_model` (absent-key read) + `_safe_user_default_model` (try/except 42P01) → `settings.llm_model`; `chat.py:1141` `except openai.RateLimitError` (429→rate_limit) BEFORE `chat.py:1152 except openai.APIStatusError` `.status_code==402`→payment_required; `llm_service.py:155-160,195-197` usage drained before `if not choice: continue` + yielded before done (early return removed); `chat.py:863-866` `_accumulate_usage` across iterations; `chat.py:1118` persists `"usage": turn_usage or None`; `chat.py:1133-1136` done carries usage + `mode:"demo"`; `test_model_fallthrough_absent_p13_schema` + `test_429_402_distinct_codes` + `test_usage_summed_across_tool_loop` + `test_usage_persisted_to_messages` PASS |

**Score:** 4/4 truths verified at the code+automated-test level. Truth 3's two MANDATORY live-environment SEC-01 sub-checks require human confirmation → overall status `human_needed`.

### Required Artifacts

| Artifact | Expected | Status | Details |
| --- | --- | --- | --- |
| `backend/routers/chat.py` | `_resolve_key_and_model` + budget switch + threaded call sites + scrubbed/structured SSE errors + `_ScrubFilter` + usage persist + demo signal | ✓ VERIFIED | All present and wired; module-level helper, not cached; budget fifth read fixed; 4 call sites threaded; typed 429/402; usage persist + mode signal |
| `backend/services/llm_service.py` | `get_llm_client(api_key, trace)` gate + `stream_chat_completion(api_key, model, trace)` + usage drain | ✓ VERIFIED | trace gate at line 26; params added; early return removed; usage captured before `choices==[]` skip and yielded before done |
| `backend/services/log_scrub.py` | `scrub_secrets()` broadened sk-or- regex | ✓ VERIFIED | `re.compile(r"sk-or-[A-Za-z0-9_-]+")`; non-str passthrough; mirrors FE sentry.ts broadened per D-11 |
| `backend/config.py` | `demo_fallback_enabled` (default False) + `demo_fallback_model` (:free slug) | ✓ VERIFIED | line 36 `= False`; line 41 `meta-llama/llama-3.3-70b-instruct:free`; no resolution method on Settings; no new @lru_cache |
| `backend/services/rerank_service.py` | `rerank`/`rerank_with_llm` threaded; `rerank_with_api` untouched | ✓ VERIFIED | lines 19/88 threaded api_key+model+trace; `rerank_with_api` (line 57) unchanged (dedicated provider key) |
| `backend/services/subagent_service.py` | `run_document_analysis` threaded | ✓ VERIFIED | line 54 signature + client/create use resolved key/model |
| `backend/services/explorer_service.py` | `run_exploration` + `_summarize_findings` threaded — all 3 owner-key read sites | ✓ VERIFIED | client (235), loop create (255), `_summarize_findings._try` (141) all `model or settings.llm_model`; called with `model=model` (line 337) |
| `backend/services/retrieval_service.py` | `search_documents` forwards api_key+model into rerank | ✓ VERIFIED | line 116 `rerank(query, results, api_key=api_key, model=model, trace=trace)` |
| `supabase/migrations/20240301000029_add_usage_to_messages.sql` | additive nullable `usage` JSONB on messages, idempotent, RLS untouched | ✓ VERIFIED (file) / probe per SUMMARY | `ADD COLUMN IF NOT EXISTS usage JSONB DEFAULT NULL`; no DROP/POLICY/user_api_keys; applied to dev per 11-02-SUMMARY (service-role `select('usage')` confirmed column present) |
| `backend/services/metadata_service.py` | UNTOUCHED (ingestion-only) | ✓ VERIFIED | bare `get_llm_client()` + `settings.llm_model` — correctly NOT threaded (D-01 boundary) |
| `backend/services/llm_service.py::get_embedding_client` | UNTOUCHED (embedding key) | ✓ VERIFIED | unconditional wrap retained; chat key not threaded |

### Key Link Verification

| From | To | Via | Status | Details |
| --- | --- | --- | --- | --- |
| `chat.py _resolve_key_and_model` | `crypto_service.decrypt_key` + `user_api_keys` row | service-role read + in-memory decrypt, fail-closed empty-row guard | ✓ WIRED | `chat.py:190` `isinstance(row.data, dict)` guard → `decrypt_key(row.data["encrypted_key"])`; short-lived local |
| `chat.py budget lookup` | `fetch_model_context_length(model, api_key)` | resolved values (not settings.*) | ✓ WIRED | `chat.py:808` uses resolved `model`+`api_key`; Pitfall 1 fixed |
| `chat.py SSE error path` | `scrub_secrets` + structured codes | `scrub_secrets(str(e))` + rate_limit/payment_required/no_api_key | ✓ WIRED | `chat.py:1182` scrub; `_sse_error` (line 80) with fixed copy for known codes |
| `chat.py logging.Filter` | ROOT handler(s) + `routers.chat` logger | `_ScrubFilter` over formatted record incl. exc_info | ✓ WIRED | `chat.py:68-74` ROOT handlers + `getLogger("routers.chat")`; NOT `getLogger("backend")` (verified absent) |
| `chat.py done/persist` | `messages.usage` column + done event | summed `turn_usage` written + `mode` signal | ✓ WIRED | `chat.py:1118` persist; `chat.py:1133-1136` done carries usage + `mode:"demo"` |
| `llm_service get_llm_client` | langsmith `wrap_openai` | trace gate (skip when trace=False/user key) | ✓ WIRED | `llm_service.py:26` `if trace and wrap_openai and settings.langsmith_api_key` |
| `retrieval_service search_documents` | `rerank_service.rerank` | api_key + model forwarded | ✓ WIRED | `retrieval_service.py:116` forwards api_key+model+trace |
| `stream_chat_completion stream loop` | `chunk.usage` | capture before choices==[] continue, no early return | ✓ WIRED | `llm_service.py:155-160` captures before skip; line 188 emit-once guard, no return |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| --- | --- | --- | --- | --- |
| `chat.py` done/persist usage | `turn_usage` | `_accumulate_usage` summing real `event["usage"]` from `stream_chat_completion`'s captured `chunk.usage` | Yes — summed OpenRouter usage flows from the live stream chunk through to `messages.usage` + done event | ✓ FLOWING |
| `chat.py` resolved `api_key` | `api_key` | `decrypt_key(user_api_keys.encrypted_key)` per-request, or owner key (demo), or None (refuse) | Yes — decrypted per-request; distinct per user (test_no_cross_user_bleed) | ✓ FLOWING |
| `messages.usage` column | persisted dict | resolver→stream→accumulate→update | Yes — column present on dev (11-02 probe), update payload carries summed usage (test asserts) | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| --- | --- | --- | --- |
| Full backend suite | `cd backend && venv/Scripts/python -m pytest tests/ -q` | 174 passed, 2 pre-existing record_manager errors | ✓ PASS (errors out-of-scope, expected) |
| Phase-11 Wave-0 tests | `pytest tests/test_key_model_resolution.py tests/test_langsmith_gate.py tests/test_error_surfacing.py tests/test_usage_capture.py -v` | 12 passed (all un-skipped) | ✓ PASS |
| Config demo_fallback + scrub | `pytest tests/test_config.py -k "demo_fallback or scrub"` | 6 passed | ✓ PASS |
| Fail-open one-liner absent | `grep -v '^#' chat.py \| grep -c "user_key or owner_key"` | 0 | ✓ PASS |
| Resolver not cached / not Settings method | grep decorator/`self` before `_resolve_key_and_model` | no decorator, module-level | ✓ PASS |
| Filter not on getLogger("backend") | `grep 'getLogger("backend").addFilter' chat.py` | none | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan(s) | Description | Status | Evidence |
| --- | --- | --- | --- | --- |
| SEC-04 | 11-03, 11-04 | Concurrent requests from different users never share a key or model (per-request client, no cross-user bleed) | ✓ SATISFIED | Truth 1: explicit per-request params, fresh client per call, module-level uncached resolver, budget fifth read fixed; test_no_cross_user_bleed + test_user_key_threaded_to_all_call_sites |
| SEC-01 | 11-01, 11-03, 11-04 | User OpenRouter keys never appear in LangSmith traces, Sentry events, logs, or SSE error payloads | ⏳ SATISFIED (code+unit) — 2 MANDATORY live gates pending human | Truth 3: trace gate + scrub_secrets + _ScrubFilter (exc_info traceback) + SSE scrub; unit tests pass. Live prod-LangSmith zero-run + live log-sink redaction require human confirmation (11-VALIDATION.md MANDATORY GATES) |
| DEMO-03 | 11-01, 11-02, 11-04 | When the user has no key and demo is off, chat refuses with a connect-key prompt (fail-closed) | ✓ SATISFIED | Truth 2: three-branch fail-closed, no_api_key SSE error + return before any LLM call, demo_fallback_enabled default False; test_no_key_flag_off_refuses + test_fail_closed_no_or_fallback |

All 3 requirement IDs declared across the 4 plans' frontmatter (SEC-04, SEC-01, DEMO-03) are accounted for. REQUIREMENTS.md maps exactly these three IDs to Phase 11 (lines 110/113/116) — no orphaned requirements.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| --- | --- | --- | --- | --- |
| (none in production files) | — | — | — | No TBD/FIXME/XXX/TODO/HACK/PLACEHOLDER/NotImplementedError in chat.py or the 5 modified services. No fail-open one-liner. No stub renders. No empty-data returns in the chat-turn path. |

The only `settings.resolved_llm_api_key`/`settings.llm_model` references in chat.py are inside `_resolve_key_and_model` itself (owner-default fallthrough + demo branch + docstring) — these are correct, not stray owner-key reads.

### Human Verification Required

Two MANDATORY SEC-01 gates (flagged in 11-VALIDATION.md as BLOCKING phase sign-off) plus one non-blocking live error-surfacing check. These cannot be substituted by any automated test and are not covered by any later phase.

### 1. [MANDATORY] Prod LangSmith zero-user-key-run

**Test:** Send a real BYOK chat turn against the prod backend using a real OAuth-provisioned OpenRouter user key.
**Expected:** No LangSmith run appears in the prod LangSmith project for that turn — the user's key/prompt never reaches the owner's observability.
**Why human:** Requires a live prod LangSmith project + a real OAuth-provisioned key. The unit test proves `trace=False` yields a bare client, but the load-bearing SEC-01 evidence is a zero-run confirmation in the live prod sink (A5/D-10). BLOCKS sign-off.

### 2. [MANDATORY] Live exc_info traceback redaction at the log sink

**Test:** In the running backend, force a logged exception whose stack-frame local / message carries an `sk-or-…` token (e.g. a decrypt-then-fail path), then inspect the live log sink.
**Expected:** The traceback in the log sink shows `[redacted-key]`, never the raw `sk-or-v1-…` token.
**Why human:** The unit test exercises `_ScrubFilter` end-to-end through `routers.chat` with a capturing handler, but the production log-sink configuration (handler set, propagation, formatter) must be confirmed live. BLOCKS sign-off.

### 3. OpenRouter 402 vs 429 distinct codes (live)

**Test:** Drive a free-model demo turn past the per-minute rate cap (→ 429) and a negative-balance owner key (→ 402) against the live backend.
**Expected:** 429 yields structured code `rate_limit`; 402 yields `payment_required` — distinct, not the generic error.
**Why human:** Requires tripping a live free-model rate cap / real negative-balance key. The unit test proves the typed-catch order with synthetic exceptions; this confirms real OpenRouter status mapping. Non-blocking relative to gates 1 & 2.

### Gaps Summary

No code-level gaps. Every must-have artifact exists, is substantive, is wired, and has real data flowing. All four ROADMAP success criteria are verified by rigorous, non-vacuous automated tests (174 passed; 12 phase-specific tests un-skipped and green). The 2 `test_record_manager` errors are confirmed pre-existing, out-of-scope, and not regressions.

The phase is held at `human_needed` (not `passed`) solely because two SEC-01 truths are sealed by MANDATORY manual gates — prod-LangSmith zero-user-key-run and live exc_info traceback redaction at the log sink — that no automated test can substitute and that no human has yet confirmed. Per the verifier decision tree, the presence of human-verification items forces `human_needed`. Once a human confirms gates 1 and 2, the phase goal is fully sealed and can be marked passed.

---

_Verified: 2026-06-22T22:10:00Z_
_Verifier: Claude (gsd-verifier)_
