# Deferred Items — Phase 999.1 (chat-empty-state-ux)

Out-of-scope discoveries logged during execution. Not fixed in this phase.

## D-999.1-LINT-A: Pre-existing `react-hooks/set-state-in-effect` in ChatPage.tsx

- **Found during:** Plan 999.1-03, Task 1 (lint of `frontend/src/pages/ChatPage.tsx`)
- **Rule:** `react-hooks/set-state-in-effect` — "Calling setState synchronously within an effect"
- **Location:** the `useEffect(() => { loadThreads() }, [loadThreads])` initial-load effect (`loadThreads` calls `setThreads`).
- **Status:** PRE-EXISTING on HEAD (`git stash` confirmed the identical error on the unmodified file before any Plan 03 edit). NOT introduced by the auto-create-on-send change; the touched `handleSend` body and new imports are lint-clean.
- **Scope decision:** Out of scope for Plan 03 (SCOPE BOUNDARY — only auto-fix issues directly caused by this task's changes). The initial-load-on-mount effect is an idiomatic data-fetch pattern the new lint rule flags but does not break behavior.
- **Suggested fix (future):** either disable the rule for the data-load effect with a scoped `// eslint-disable-next-line`, or migrate the threads fetch to a query/loader pattern. Triage in a dedicated lint-cleanup pass.

## D-999.1-LLM-A: Chat completion fails for the configured free OpenRouter model

- **Found during:** Plan 999.1-03, Task 3 (live human-verify checkpoint)
- **Symptom:** The chat completion fails at runtime — the configured `:free` model (`nvidia/nemotron-3-super-120b-a12b:free`) returns an in-band SSE error: HTTP 200, then `event: error`. No real streamed assistant answer arrives, so the D-03 live happy path (streamed reply + backend-generated title) could not be observed.
- **Diagnosis:** Orchestrator probes confirmed the raw model + tools + streaming all work — so this is a runtime rate-limit / provider-availability issue (free-tier), NOT a phase defect. It affects **any** chat on **any** thread, not just the empty-state / auto-create path.
- **Status:** OUT OF SCOPE for Phase 999.1 (frontend-only empty-state UX). The user accepted the phase on this basis and will resolve the LLM provider/model separately when wiring broader testing.
- **Suggested fix (future):** revisit `LLM_MODEL` / provider config (OpenRouter vs OpenAI) — choose a non-free / paid model for reliable end-to-end chat testing, then re-run the Plan 03 Task 3 live round-trip to confirm the streamed reply + backend titling. Do NOT create a new plan; fold into the next testing/ops pass.

## D-999.1-DEMO-A: `POST /api/demo/bootstrap` fails ("Couldn't start the demo")

- **Found during:** Plan 999.1-03, Task 3 (live human-verify checkpoint, flow 5 — anon hint)
- **Symptom:** The LoginPage "Try the demo" / anonymous-session bootstrap (`POST /api/demo/bootstrap`) fails with "Couldn't start the demo." This blocked the live anon-hint check (Task 3 flow 5). The anon empty-state page parity is still covered in jsdom by `ChatPage.test.tsx` Test 6.
- **Status:** PRE-EXISTING and untouched by this phase. OUT OF SCOPE for Phase 999.1.
- **Suggested fix (future):** triage the demo-bootstrap endpoint / anonymous Supabase session path in a dedicated pass (relevant to the Phase 15 demo-fallback gating work). Do NOT create a new plan from this phase.
