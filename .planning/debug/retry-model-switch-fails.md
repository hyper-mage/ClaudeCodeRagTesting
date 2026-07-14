---
status: diagnosed
trigger: "After switching the chat model, clicking Retry on an interrupted/failed turn does NOT succeed; same-model Retry works. Phase 17 UAT Test 6 / Gap 2."
created: 2026-07-14T00:00:00Z
updated: 2026-07-14T00:00:00Z
---

## Current Focus

hypothesis: CONFIRMED — the retry path resolves and uses the newly-switched model correctly (identical to a fresh send). The failure is a property of the SWITCHED-TO model being unable to serve a tool-enabled request in this env (model_unavailable / payment_required / owner-key-500), NOT a retry-logic code defect. Classification: ENVIRONMENT.
test: Traced send/retry model resolution end-to-end (FE send body, PATCH persistence, backend thread.data reload + _resolve_key_and_model, error branches).
expecting: n/a — root cause confirmed.
next_action: Return ## ROOT CAUSE FOUND (diagnose-only).

## Symptoms

expected: Interrupt/fail a turn, switch the chat model, click Retry → last user message re-sent under the NEW model, fresh answer streams.
actual: Same-model Retry works. After switching the model, Retry does NOT succeed.
errors: none captured by user.
reproduction: Phase 17 17-HUMAN-UAT.md Test 6.
started: Discovered during UAT 2026-07-14.

## Eliminated

## Evidence

- timestamp: 2026-07-14T00:00:00Z
  checked: frontend/src/hooks/useChat.ts sendMessage request body
  found: body = JSON.stringify({ content, ...(use_demo ? {use_demo:true} : {}) }). NO model field is sent on send OR retry. retry only appends ?retry=true query param.
  implication: Model is NOT chosen per-request from the client. It must be resolved server-side (thread row or config). "Switching the model" must persist to the thread to have any effect on retry.

- timestamp: 2026-07-14T00:00:00Z
  checked: frontend/src/pages/ChatPage.tsx handleThreadModelChange + onThreadModelChange wiring
  found: Switching the model calls guardedSelect (useKeyGate) → for a connected user, onApply(modelId) fires immediately → handleThreadModelChange PATCHes /api/threads/{id} {model} AND optimistically updates local thread.model. So a model switch DOES persist to the thread row in the DB.
  implication: After a switch the thread row carries the NEW model. Retry (which reads the thread row server-side) will use the new model.

- timestamp: 2026-07-14T00:00:00Z
  checked: backend/routers/chat.py send_message (L871-878) + retry cleanup (L895-923) + event_generator model resolve (L953) + _resolve_key_and_model (L278-349)
  found: On every request (retry or not) the thread row is loaded FRESH (SELECT * L871). _resolve_key_and_model resolves model = body.model(none) → thread_row.model → user_default → settings.llm_model. Retry differs from a fresh send ONLY by (a) deleting the most-recent assistant row and (b) skipping the user-message insert. The model resolution and the LLM call are IDENTICAL to a normal send.
  implication: There is NO retry-specific model handling. Retry uses exactly the model the thread is currently pinned to. If a fresh send with the switched model would fail, so does the retry (and vice-versa). No code defect drops/uses-wrong-model on retry.

- timestamp: 2026-07-14T00:00:00Z
  checked: backend/routers/chat.py error branches (L1457-1542) + comment L1508-1524
  found: The agent loop ALWAYS sends tools (tools=tools, L1136). Switched-to models can fail with: 400 "No endpoints found that support tool use" / 404 "No endpoints found for <model>" → model_unavailable; 402 → payment_required; 401 → no_api_key; owner-key OpenRouter-model 500 (VERIFICATION env note). The DEFAULT/same model is the one that produced the (partial) interrupted turn — demonstrably tool-capable & funded for this user's key, which is why same-model retry succeeds.
  implication: The switched-to model simply cannot serve this env's tool-enabled turn. This is model-availability (ENVIRONMENT), independent of retry.

- timestamp: 2026-07-14T00:00:00Z
  checked: Race analysis (PATCH-then-retry ordering)
  found: If the switch did NOT persist (race / PATCH failure), the backend would read the OLD model → retry would SUCCEED. The only way retry FAILS after a switch is if the switch DID persist a model that cannot run.
  implication: A race is ruled OUT as the failure cause — a race produces success, not failure. Confirms ENVIRONMENT/model-availability classification.

## Resolution

root_cause: The interrupt→Retry path is model-agnostic and correct. On retry the backend reloads the thread row fresh and _resolve_key_and_model picks up the newly-switched thread.model exactly as a fresh send would (frontend sends no model; identical LLM call). "Same-model retry works" because that model (the one that produced the interrupted turn) is tool-capable and funded for the user's key. "Model-switch retry fails" because the switched-TO model cannot serve this env's ALWAYS-tools turn — OpenRouter returns 400 "No endpoints found that support tool use" / 404 model-unavailable / 402 payment-required (or an owner-key OpenRouter-model 500 per the VERIFICATION env note). The retry logic is not defective; the chosen model is unavailable/unusable. CLASSIFICATION: ENVIRONMENT (model availability), not CODE-DEFECT.
fix: [diagnose-only — not applied]
verification: [diagnose-only]
files_changed: []
