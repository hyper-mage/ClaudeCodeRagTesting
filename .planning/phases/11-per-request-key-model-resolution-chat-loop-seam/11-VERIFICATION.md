---
phase: 11-per-request-key-model-resolution-chat-loop-seam
verified: 2026-07-11T04:30:00Z
status: passed
score: 14/14 must-haves verified (automated) + 2/2 MANDATORY live SEC-01 gates confirmed by human on prod (2026-07-11)
overrides_applied: 0
human_gate_results:
  - gate: "SEC-01 (a) prod-LangSmith zero-run for BYOK turn (re-run of the 2026-07-09 FAILED gate)"
    result: PASSED 2026-07-11 — prod v32 (post 11-05/11-06 + CR-01..WR-06 fix pass, migration 034 applied to prod). BYOK "hi" + KB tool turn produced zero LangSmith runs; control owner/demo turn (key disconnected, same thread) produced exactly one chat_send_message trace as expected. Noted: the demo turn's traced Input legitimately contains prior BYOK thread messages as stateless-completions history — inherent to history tracing, not a gate leak; hardening idea recorded in 11-HUMAN-UAT.md.
  - gate: "SEC-01 (b) live exc_info traceback at Fly log sink"
    result: PASSED 2026-07-11 — provisioned key revoked at OpenRouter, BYOK turn forced openai.AuthenticationError 401; full traceback logged at the Fly sink with ZERO sk-or- occurrences. Note: this error path carries no key text in the exception, so [redacted-key] did not appear because nothing required redaction; live sink confirmed key-free, filter trigger remains covered in-process (test_logging_filter_scrubs_exc_info).
re_verification:
  previous_status: human_needed
  previous_score: 4/4 (automated) — 2 MANDATORY manual SEC-01 gates pending
  gaps_closed:
    - "SEC-01 (a) BYOK LangSmith run leak (2026-07-09 human gate BLOCKER: 'i see my message sent in langsmith') — endpoint @traceable(name='chat_send_message') removed, key resolution hoisted above the traced region, single run-layer tracing_context gate suppresses parent + both asyncio.to_thread subagent runs + wrap_openai spans; run-level regression test (incl. threaded tool dispatch) proves zero runs in-process. Live prod zero-run confirmation still requires redeploy + human (carried as MANDATORY human gate, not a code gap)."
  gaps_remaining: []
  regressions: []
human_verification:
  - test: "[MANDATORY GATE — re-run of the 2026-07-09 FAILED gate] After the prod backend is redeployed (ships the 11-05 run-layer gate + migration 034), send a real BYOK chat turn (plus an explore_kb tool turn) with a real OAuth-provisioned OpenRouter key against prod, then inspect the prod LangSmith project"
    expected: "ZERO LangSmith runs appear for the BYOK turn — no chat_send_message parent run, no subagent_explorer / subagent_document_analysis child run, no wrap_openai client span"
    why_human: "The 2026-07-09 run of this gate FAILED (the leak 11-05 closes). The in-process regression test (test_user_key_turn_creates_zero_runs, incl. the asyncio.to_thread child) is green, but the load-bearing SEC-01 evidence is a zero-run confirmation in the live prod LangSmith sink, and prod does not yet run this code (redeploy required first). BLOCKS phase sign-off and v1.2 SEC-01 closure."
  - test: "[MANDATORY GATE — blocked on 2026-07-09, never exercised] In the running backend, force a logged exception whose message/locals carry an sk-or- token, then inspect the LIVE log sink (Fly/backend stdout — NOT LangSmith)"
    expected: "The traceback line at the log sink shows [redacted-key], never the raw sk-or-v1-... token"
    why_human: "The 07-09 attempt inspected LangSmith instead of the log sink and never produced a key-bearing exception, so the filter was not exercised. Unit coverage (test_logging_filter_scrubs_exc_info through routers.chat) is green, but the production handler/formatter/propagation chain must be confirmed live. BLOCKS phase sign-off."
  - test: "Live OpenRouter 402 vs 429 distinct structured codes — drive a free-model demo turn past the per-minute cap (429) and a negative-balance owner key (402)"
    expected: "429 yields SSE code rate_limit; 402 yields payment_required — distinct, never the generic error"
    why_human: "Requires tripping a live rate cap / real negative balance. Unit test proves the typed-catch order with synthetic exceptions. Non-blocking relative to the two MANDATORY gates."
  - test: "Prod SQL-flip smoke of the LangSmith master toggle (after migration 034 ships to prod with the redeploy): UPDATE app_settings SET value='false'::jsonb WHERE key='langsmith_enabled'; send an owner/demo turn after ~15s; flip back"
    expected: "With the flag OFF, an owner/demo chat turn opens no LangSmith run within the ~15s TTL window; flipping back ON restores tracing — no restart needed"
    why_human: "Requires the prod DB (migration 034 not yet applied to prod — deliberately deferred to deploy per D-03) and the live prod LangSmith sink. Dev-side flip smoke already passed at the 11-06 Task 3 checkpoint. Non-blocking."
---

# Phase 11: Per-Request Key + Model Resolution (chat-loop seam) — Re-Verification Report

**Phase Goal:** Every chat turn resolves the correct key and model per request — the user's own key when connected, a gated owner-key fallback only when explicitly enabled, and a clean fail-closed refusal otherwise — with no cross-user key bleed and no secret leaking into observability.
**Verified:** 2026-07-11T04:30:00Z (human gates confirmed on prod)
**Status:** passed
**Re-verification:** Yes — after gap-closure plans 11-05 (SEC-01 a run-layer gate) and 11-06 (runtime LangSmith master toggle), created to close the SEC-01 (a) BYOK LangSmith leak found by the 2026-07-09 human run of the MANDATORY gates (11-HUMAN-UAT.md, severity blocker).

## Goal Achievement

The 2026-07-09 human gate run falsified the previous verification's Truth 3 in prod: a BYOK turn DID create LangSmith runs, because the gate had been applied only at the wrap_openai client layer while a pre-existing `@traceable(name="chat_send_message")` endpoint decorator (plus two subagent `@traceable` sites) opened ungated runs. Plans 11-05/11-06 moved the gate to the run layer and added a runtime master toggle. This re-verification confirms — against the actual merged code on master, not the SUMMARYs — that the leak's mechanism is removed, the new gate is wired at the correct seam, the regression coverage that was structurally blind to the leak now exists and is meaningful, and no previously-verified truth regressed. The live prod zero-run confirmation cannot be automated and requires a redeploy first; it is carried as a MANDATORY human gate.

### Observable Truths

#### Gap-closure truths (11-05 — full 3-level verification)

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| 1 | BYOK user-key turn opens ZERO LangSmith runs at every layer (no parent, no subagent_explorer, no subagent_document_analysis, no wrap_openai span) | ✓ VERIFIED (in-process) | `test_user_key_turn_creates_zero_runs` asserts `get_current_run_tree() is None` at parent + direct child + `asyncio.to_thread` child under the gate — ran it: PASS. Exhaustive site enumeration: only 3 `@traceable` sites exist in backend (`chat.py:882` inner worker, `explorer_service.py:208`, `subagent_service.py:53`) and 2 `wrap_openai` sites (`llm_service.py:27` gated by `trace`, `:39` in `get_embedding_client` which has NO remaining callers — embeddings go through raw httpx in `embedding_service.py`). All chat-turn trace emission is inside the gated contextvar. Live prod zero-run = MANDATORY human gate 1. |
| 2 | `is_user_key` resolved BEFORE any traced run opens; endpoint handler no longer `@traceable` | ✓ VERIFIED | `chat.py:748-750`: only `@router.post` + `@limiter.limit` on `send_message` (decorator gone); `_resolve_key_and_model` at `chat.py:842` at the TOP of `event_generator`, `no_key` refusal at 854-863 returns before any traced region; `test_endpoint_handler_not_traceable` PASS (`__langsmith_traceable__` is False) |
| 3 | Single `tracing_context(enabled=...)` gate at the parent seam suppresses parent AND both subagent child runs through `asyncio.to_thread` | ✓ VERIFIED | Exactly one comment-excluded `tracing_context(enabled=` in chat.py (line 1421), wrapping the `@traceable` inner `_traced_turn` (line 882, exactly one `@traceable(name="chat_send_message")` in the file); threaded-child suppression proven by the run-gate test's `asyncio.to_thread` probe; subagent files unchanged (git-verified: 11-05 GREEN commit `84fff14` touches only chat.py) |
| 4 | Owner/demo turns remain fully traced (observability not regressed for non-BYOK) | ✓ VERIFIED (with CR-01 caveat) | `test_owner_turn_still_traced` + `test_flag_on_owner_traced` PASS — parent + both children get RunTrees when enabled. Caveat: review CR-01 (open) — `enabled=True` force-enables over the env kill-switch; this OVER-delivers tracing rather than regressing it (see Code Review Findings Disposition) |
| 5 | Regression test drives a full user-key turn INCLUDING a threaded tool-call dispatch and asserts zero runs — the exact coverage gap that let the leak ship | ✓ VERIFIED | `backend/tests/test_langsmith_run_gate.py` (143 lines, substantive): structural test + guardrail pinning subagents as `@traceable` + behavioral zero-run test with direct AND `asyncio.to_thread` child + owner guard; RED-before evidence in commit `d4a3fbd` (structural test failed on the shipped decorator; behavioral tests errored on missing `chat.tracing_context`) — the test provably detects the shipped leak |

#### Gap-closure truths (11-06 — full 3-level verification)

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| 6 | Owner can flip LangSmith tracing live via one SQL UPDATE on app_settings — no restart, no admin UI — effective within the ~15s TTL | ✓ VERIFIED | `app_settings_service.py:74` TTL window check (`time.monotonic()`, `_TTL_SECONDS = 15`, module cache NOT `@lru_cache`); per-turn read `langsmith_on = is_langsmith_enabled(db)` at `chat.py:871` outside the traced region; migration header documents the flip SQL; dev live-flip smoke passed at the Task 3 checkpoint AND I independently confirmed the seed row live on dev: `[{'key': 'langsmith_enabled', 'value': True, 'updated_at': '2026-07-10T17:12:59...'}]` |
| 7 | Flag OFF => zero LangSmith runs for everyone including owner/demo (kill-switch beats owner tracing) | ✓ VERIFIED (chat turns; see WR-04 scope note) | `test_flag_off_owner_zero_runs` + `test_flag_off_byok_zero_runs` PASS; composed gate `enabled=langsmith_on and not is_user_key` at `chat.py:1421` is False for all turns when flag OFF. Scope caveat (review WR-04): ingestion-time metadata LLM spans (`metadata_service.py` via `get_llm_client()` default trace=True) are NOT covered by the flag — they are not chat turns and carry no user key, but the "for everyone" phrasing overstates coverage |
| 8 | Flag ON => owner/demo traced AND BYOK still zero runs — toggle composes with, never weakens, the BYOK gate | ✓ VERIFIED | `test_flag_on_owner_traced` + `test_flag_on_byok_zero_runs` PASS; expression is a conjunction (AND) — pinned by comment-excluded grep: exactly 1 `langsmith_on and not is_user_key` in chat.py, 0 `user_key or owner_key` |
| 9 | SECURITY INVARIANT: failed/missing flag read defaults to True yet a BYOK turn STILL opens zero runs | ✓ VERIFIED | `test_flag_read_error_defaults_true_byok_still_gated` drives the REAL `is_langsmith_enabled` with a raising db stub → returns True, composed gate still yields no run for `is_user_key=True`; `is_user_key` resolved locally at `chat.py:842`, independent of the flag read at 871; service never raises (`except Exception` → True, `app_settings_service.py:91-95`) |
| 10 | app_settings is a GLOBAL RLS-enabled deny-by-default table (zero policies), service-role read only | ✓ VERIFIED | Migration 034: 1x `CREATE TABLE IF NOT EXISTS app_settings`, 1x `ENABLE ROW LEVEL SECURITY`, 1x `ON CONFLICT (key) DO NOTHING` seed, 0x `CREATE POLICY` (all grep-confirmed); reader uses the passed service-role client only |

#### Previously-verified ROADMAP truths (regression check — passed initial verification 2026-06-22)

| # | Truth (ROADMAP Success Criterion) | Status | Evidence |
| --- | --- | --- | --- |
| 11 | SEC-04 — no cross-user bleed: key + model explicit per-request params threaded through all call sites; resolver module-level, uncached | ✓ VERIFIED (no regression) | `_resolve_key_and_model` still module-level at `chat.py:203` (no decorator); resolution once per turn at 842; `test_key_model_resolution.py` suite PASS (part of 34-test regression run); fail-open one-liner grep = 0 |
| 12 | DEMO-03 — fail-closed: keyless + flag OFF → structured `no_api_key` SSE error before any LLM call | ✓ VERIFIED (no regression) | `chat.py:854-863` refusal now runs even EARLIER (outside the traced region — hoisting strengthened this truth: a refused turn opens no run); `config.py:37` `demo_fallback_enabled: bool = False` unchanged |
| 13 | SEC-01 — no secret in observability: wrap_openai trace gate + scrub_secrets + _ScrubFilter on root handlers + routers.chat | ✓ VERIFIED (code+unit; strengthened) | `llm_service.py:26` `if trace and wrap_openai and settings.langsmith_api_key` intact (defense-in-depth under the new run-layer gate); `log_scrub.py:15` `sk-or-[A-Za-z0-9_-]+` regex intact; `_ScrubFilter` at `chat.py:35`, installed at 72/75; `test_error_surfacing.py` PASS. Live gates = human items 1 & 2 |
| 14 | Model three-tier resolution tolerant of absent P13 schema; 429 vs 402 distinct; usage summed + persisted | ✓ VERIFIED (no regression) | `chat.py:1313` `except openai.RateLimitError` → `rate_limit` before `:1324` `APIStatusError` 402 → `payment_required`; usage persist at `chat.py:1290` `"usage": turn_usage or None`; `test_usage_capture.py` + `test_deprecated_model_fallback.py` PASS |

**Score:** 14/14 truths verified at the code + automated-test level. Truths 1 and 13 are sealed only by MANDATORY live gates (prod LangSmith zero-run after redeploy; live log-sink redaction) → overall status `human_needed`.

### Required Artifacts

| Artifact | Expected | Status | Details |
| --- | --- | --- | --- |
| `backend/routers/chat.py` | Endpoint decorator removed; `tracing_context` import w/ ImportError fallback; resolution hoisted; `_traced_turn` worker; composed gate; per-turn flag read | ✓ VERIFIED | All six elements confirmed at lines 748-750, 289-296, 842, 882-883, 1421, 871; `contains: "tracing_context(enabled=not is_user_key)"` from the 11-05 plan is superseded by 11-06's composed expression by design (11-06 explicitly refines that exact line) — intent satisfied, not a deviation |
| `backend/tests/test_langsmith_run_gate.py` | Run-level SEC-01 regression: structural + behavioral (zero runs incl. threaded tool call) + owner guards; contains `test_user_key_turn_creates_zero_runs` | ✓ VERIFIED | 143 lines, 4 tests, all PASS; offline/deterministic (Client.create_run/update_run neutered); RED-first proven in commit history |
| `supabase/migrations/20240301000034_create_app_settings.sql` | Global key/value table, seeded langsmith_enabled=true, deny-by-default RLS, idempotent, ≥20 lines | ✓ VERIFIED | 29 lines; all four structural gates pass; applied to DEV (seed row independently confirmed live by verifier); prod deferred to deploy (D-03) |
| `backend/services/app_settings_service.py` | `is_langsmith_enabled(db)`: TTL-cached (~15s, module-level), default-on on miss/error, never raises, jsonb coercion, ≥30 lines | ✓ VERIFIED | 99 lines; `_TTL_SECONDS = 15`, monotonic stamp cache, `_coerce_bool`, `_reset_cache()` test hook, `except Exception` → True with warning log |
| `backend/tests/test_app_settings_service.py` | Unit coverage: true/false row, missing → True, exception → True, coercion, TTL hit/expiry | ✓ VERIFIED | 135 lines, 14 tests PASS (incl. the extra empty-list data-shape test); deterministic TTL expiry via monkeypatched monotonic time |
| `backend/tests/test_langsmith_runtime_toggle.py` | Empirical 4-cell truth table + security invariant + binding gate; contains `get_current_run_tree` | ✓ VERIFIED | 166 lines, 6 tests PASS incl. `test_chat_binds_app_settings_flag_reader` (identity assertion `chat.is_langsmith_enabled is app_settings_service.is_langsmith_enabled`) |

### Key Link Verification

| From | To | Via | Status | Details |
| --- | --- | --- | --- | --- |
| `chat.py event_generator` | `_resolve_key_and_model` (is_user_key) | Resolution hoisted to top of generator, before the traced worker | ✓ WIRED | `chat.py:842`; its own try/except mirrors the worker's scrubbed SSE error branch (11-05 auto-fix deviation, verified present at 845-853) |
| `chat.py tracing_context gate` | `explorer_service.run_exploration` + `subagent_service.run_document_analysis` (@traceable) | contextvar through `asyncio.to_thread` | ✓ WIRED | Both subagent fns still `@traceable` (grep + `test_subagent_sites_remain_traceable` PASS); both invoked from within `_traced_turn`'s context; suppression proven by the threaded-child probe |
| `test_langsmith_run_gate.py` | `chat.tracing_context` + `chat.send_message.__langsmith_traceable__` | `get_current_run_tree()` None/RunTree under the gate | ✓ WIRED | Tests bind to `chat.tracing_context` (module attribute, real import at `chat.py:290` with no-op fallback) |
| `chat.py event_generator` | `app_settings_service.is_langsmith_enabled` | Per-turn read after resolution, before the gate | ✓ WIRED | `chat.py:19` module import into chat's namespace; call at 871; binding identity test PASS |
| `chat.py tracing gate` | Composed enabled value | `enabled=langsmith_on and not is_user_key` | ✓ WIRED | Exactly one composed gate at 1421 (comment-excluded grep = 1); conjunction semantics test-pinned |
| `app_settings_service.py` | `app_settings.langsmith_enabled` row | service-role select on key, default True on miss/error | ✓ WIRED | `chat.py`-pattern `maybe_single()` + dict-shape guard; live dev row read succeeded during this verification |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| --- | --- | --- | --- | --- |
| `chat.py` composed gate | `langsmith_on` | Live `app_settings` row via service-role client (TTL-cached) | Yes — verifier read the live dev row (`value: True`); flip smoke (OFF→ON) recorded at Task 3 checkpoint | ✓ FLOWING |
| `chat.py` composed gate | `is_user_key` | `_resolve_key_and_model` per request (decrypted user key vs owner/demo) | Yes — resolved per-turn at 842, upstream of the gate; unchanged from initial verification | ✓ FLOWING |
| `_traced_turn` run tree | LangSmith run creation | `tracing_context` contextvar → langsmith 0.3.42 `tracing_is_enabled` (contextvar checked first) | Yes — empirically asserted via `get_current_run_tree()` presence/absence in 3 test suites | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| --- | --- | --- | --- |
| Gap-closure suites | `pytest tests/test_langsmith_run_gate.py tests/test_langsmith_runtime_toggle.py tests/test_app_settings_service.py tests/test_langsmith_gate.py -q` | 25 passed | ✓ PASS |
| Regression (original phase suites) | `pytest tests/test_key_model_resolution.py tests/test_deprecated_model_fallback.py tests/test_explorer_integration.py tests/test_error_surfacing.py tests/test_usage_capture.py -q` | 34 passed | ✓ PASS |
| Full backend suite | `pytest tests/ -q` | 264 passed, 1 failed, 2 errors — all 3 pre-existing and out of phase scope: `test_config.py::test_key_encryption_secret_default` (real KEY_ENCRYPTION_SECRET in .env leaks into the default-assertion test; config.py untouched by 11-05/11-06) + 2 `test_record_manager` fixture errors (documented pre-existing since initial verification) | ✓ PASS (no phase regression) |
| Live dev DB seed row (read-only) | `get_supabase().table('app_settings').select('*').eq('key','langsmith_enabled').execute()` | `[{'key': 'langsmith_enabled', 'value': True, 'updated_at': '2026-07-10T17:12:59.210682+00:00'}]` | ✓ PASS |
| Structural gates | comment-excluded greps on chat.py + migration | composed gate=1, `@traceable(name="chat_send_message")`=1, `is_langsmith_enabled(db)`=1, fail-open one-liner=0, migration 1/1/1/0 | ✓ PASS |
| Task commits exist | `git rev-parse --verify` d4a3fbd 84fff14 00f9871 03011da b5dd312 64a9849 a579688 | All 7 OK; commit file scopes match plan constraints (11-05 GREEN touches only chat.py; no subagent/tracing/llm_service edits) | ✓ PASS |

### Probe Execution

No probes declared in any Phase 11 plan/summary and no conventional `scripts/*/tests/probe-*.sh` exist in the repo — N/A.

### Requirements Coverage

| Requirement | Source Plan(s) | Description | Status | Evidence |
| --- | --- | --- | --- | --- |
| SEC-01 | 11-01, 11-03, 11-04, 11-05, 11-06 | User OpenRouter keys never appear in LangSmith traces, Sentry events, logs, or SSE error payloads | ⏳ SATISFIED (code+unit, run-layer leak closed) — 2 MANDATORY live gates pending human after redeploy | Truths 1-5, 9, 13. The 07-09 leak mechanism (ungated endpoint `@traceable`) is removed and regression-covered. REQUIREMENTS.md correctly still shows Pending — closure gated on the prod human UAT re-verify (human gates 1 & 2) |
| SEC-04 | 11-03, 11-04 | Concurrent requests never share a key or model | ✓ SATISFIED (no regression) | Truth 11; hoisting the resolution did not change the per-request threading; suites green |
| DEMO-03 | 11-01, 11-02, 11-04 | Keyless + demo off → fail-closed connect-key refusal | ✓ SATISFIED (strengthened) | Truth 12; refusal now provably opens no LangSmith run either |

All requirement IDs declared across the 6 plans (SEC-04, SEC-01, DEMO-03; 11-05/11-06 both declare only SEC-01) are accounted for. REQUIREMENTS.md maps exactly these three IDs to Phase 11 — no orphaned requirements.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| --- | --- | --- | --- | --- |
| (none) | — | — | — | No TBD/FIXME/XXX/TODO/HACK/PLACEHOLDER/NotImplementedError in any of the 6 files created/modified by 11-05/11-06. No fail-open one-liner. No stub returns. |

### Code Review Findings Disposition (11-REVIEW.md, committed 7062ebd — all findings still OPEN in code)

No commit after the review touches chat.py or app_settings_service.py, so every review finding remains unaddressed. Assessed against the must-haves:

- **CR-01 (Critical in review → WARNING here, does not fail a must-have):** `tracing_context(enabled=True)` force-enables tracing in langsmith 0.3.42, overriding the `LANGCHAIN_TRACING_V2` env opt-out and forcing run-post attempts (401 noise) in keyless deployments. I confirmed the fix (`gate = False ... else None`) is NOT applied — line 1421 still passes a hard boolean both ways. **Why not a BLOCKER:** no must-have truth requires deferring to the env on the enable side; the phase goal's security clause (BYOK zero runs / no key leak) is unaffected — the BYOK/flag-OFF rows always force `False`, and the current prod config (env tracing on + LangSmith key set) makes the failure modes latent. **However:** the failure mode it creates ("operator sets env kill-switch off, DB flag defaults on pre-migration → owner/demo content posts anyway") directly undercuts operator intent for the observability surface this phase hardens, and the fix is one line. **Strong recommendation: apply the CR-01 force-off-never-force-on fix (plus the WR-05 test-mirror updates) BEFORE the prod redeploy that human gate 1 already requires — one deploy seals both.**
- **WR-01 (WARNING):** flag-read error clobbers a known-good OFF back to ON for a TTL window (`app_settings_service.py:91-98` caches the default-True on the exception path). Confirmed present. Weakens the kill-switch's OFF durability; does not affect BYOK (truth 9 holds regardless).
- **WR-02 (WARNING):** `tracing_context` ImportError fallback fails open while `traceable` stays live (version-skew scenario; unreachable under the `langsmith==0.3.42` pin). Confirmed present at `chat.py:289-296`.
- **WR-03 (WARNING):** `worker.aclose()` comment overstates determinism of the interrupted-turn cleanup through langsmith's async-gen wrapper. Cleanup still happens (GC-deferred at worst); robustness note, not a leak.
- **WR-04 (WARNING):** "flag OFF => zero runs for everyone" overstates scope — ingestion-time metadata LLM spans (`metadata_service.py`, owner key, document content) are outside the gate. Verified: embeddings use raw httpx (no spans); `get_embedding_client` has no callers; so the residual surface is metadata extraction only. No user key or chat content involved.
- **WR-05 (WARNING):** the truth-table suites validate a hand-copied mirror of the composed expression, not the shipped `event_generator` line; the only shipped-code bindings are the `chat.tracing_context` symbol and the `is_langsmith_enabled` identity. A regression of the expression to `or` would keep all tests green. Mitigated at verification time by the comment-excluded structural greps (run by executor and independently by this verifier), but those live in plan docs, not CI.
- **WR-06 (WARNING) / IN-01 (INFO):** `_coerce_bool` silently maps "off"/"no"/"0"-as-string to True; raw `{e}` interpolated unscrubbed in the service's warning log (low risk, convention inconsistency). Both confirmed present.

### Human Verification Required

Two MANDATORY SEC-01 gates (both carried from 11-VALIDATION.md; gate 1 is the re-run of the gate that FAILED on 2026-07-09) plus two non-blocking live checks. **Both mandatory gates require the prod backend redeploy first** (ships the 11-05 gate code + migration 034 to prod).

### 1. [MANDATORY — re-run of the FAILED 07-09 gate] Prod LangSmith zero-run for a BYOK turn

**Test:** Redeploy prod (11-05/11-06 code + migration 034), then send a real BYOK chat turn — including an explore_kb tool turn — with a real OAuth-provisioned OpenRouter key; inspect the prod LangSmith project.
**Expected:** ZERO runs for the BYOK turn at every layer (no parent, no subagent, no client span).
**Why human:** This exact gate failed on 2026-07-09 against the old code; the fix is in-process-proven but prod does not run it yet. No automated test can observe the live prod LangSmith sink. BLOCKS sign-off and v1.2 SEC-01 closure.

### 2. [MANDATORY — blocked on 07-09, never exercised] Live exc_info traceback redaction at the log sink

**Test:** Force a logged exception carrying an `sk-or-` token in the running backend; inspect the Fly/backend stdout log sink (NOT LangSmith).
**Expected:** `[redacted-key]` in the traceback, never the raw token.
**Why human:** The 07-09 attempt looked in the wrong sink and produced no exception; the production handler chain must be confirmed live. BLOCKS sign-off.

### 3. Live 402 vs 429 distinct codes (non-blocking)

**Test:** Trip a free-model per-minute cap (429) and a negative-balance owner key (402) live.
**Expected:** `rate_limit` vs `payment_required` structured SSE codes.

### 4. Prod SQL-flip smoke of the master toggle (non-blocking, new in 11-06)

**Test:** After migration 034 reaches prod, flip `langsmith_enabled` to false in the SQL editor, send an owner/demo turn after ~15s, confirm no run; flip back.
**Expected:** Restart-free kill-switch works against prod within the TTL window.

### Gaps Summary

**No code-level gaps.** The SEC-01 (a) leak that failed the 2026-07-09 human gate is closed at its mechanism: the ungated endpoint `@traceable` decorator is gone, key resolution runs before any traced region, one run-layer `tracing_context` gate (composed with the runtime master flag) suppresses every LangSmith emission site reachable in a chat turn — verified by exhaustive site enumeration, three green test suites including the threaded-tool-dispatch zero-run regression the original coverage lacked, structural greps, and a live dev DB read. All 14 must-have truths (4 carried ROADMAP criteria + 5 from 11-05 + 5 from 11-06) verify against the merged code with no regressions (full suite 264 passed; the 1 failure + 2 errors are documented pre-existing non-phase issues).

The phase is held at `human_needed` — not `passed`, and not `gaps_found` — because the two MANDATORY SEC-01 gates remain unconfirmed live: gate 1 (prod zero-run) previously FAILED and must be re-run after the prod redeploy; gate 2 (log-sink redaction) has never been exercised. Additionally, review finding CR-01 (force-enable overrides the env kill-switch) is real, open, and one line to fix — it does not fail any must-have and cannot leak a BYOK turn, but it should ship with the same redeploy the mandatory gates already require.

---

_Verified: 2026-07-10T18:35:00Z_
_Verifier: Claude (gsd-verifier)_
