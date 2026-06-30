---
slug: model-switch-error
status: resolved
trigger: |
  DATA_START
  Switching to certain models mid-chat via the per-thread header selector produces a
  generic error bubble: "The assistant ran into a problem. Try again, or rephrase your
  question." with a Retry button, which then shows "[Response interrupted]". User wants
  to switch models on a chat without errors. (Phase 14 UAT follow-up FU-C.)
  DATA_END
created: 2026-06-30
updated: 2026-06-30
---

# Debug: model-switch-error

## Symptoms

- **Expected:** Switch the model on an active chat (per-thread header selector) and keep
  chatting — no error.
- **Actual:** With *certain* models, an assistant turn fails with the GENERIC error bubble
  "The assistant ran into a problem. Try again, or rephrase your question." + Retry, then
  the bubble shows "[Response interrupted]".
- **Error message:** Generic bubble text above — NOT a typed key-error (not the 401/402/403
  recovery variants from Phase 14 D-09). Maps to the `upstream_error` / unknown catch-all,
  i.e. the SSE `error` event's code is not one of no_api_key/payment_required/forbidden.
- **Repro:** Only on CERTAIN models (not every switch). Per-thread header selector (Phase 14
  D-07). Switch UI itself appears to work; failure surfaces on a turn with the selected model.
- **Timeline:** Noticed during Phase 14 UAT (2026-06-30). Unknown whether pre-existing.

## Initial direction (hypotheses to test, not yet confirmed)

1. Selected model id is invalid / not available to the connected OpenRouter key (404/400
   `model not found` or `not a valid model`), or requires a data-policy/privacy opt-in →
   OpenRouter returns a 4xx the chat loop maps to the generic `upstream_error` branch.
2. Model id mismatch between the header selector's option value and what the backend sends
   to OpenRouter (e.g. a stale/renamed slug, or a free-tier `:free` variant that's
   rate-limited/unavailable).
3. The per-thread selected model is not persisted/passed correctly on the next turn, so the
   request goes out with an unexpected model.
4. A model that doesn't support tool-calling (the agent loop sends tools) → OpenRouter 400
   "no endpoints support tool use" for that model.

Where to look: `frontend/src/components/` model selector + `useChat` request payload →
backend `routers/chat.py` model resolution + the SSE error taxonomy (`else → upstream_error`)
→ how the model id flows from the per-thread selector to the OpenRouter completion call.

## Current Focus

reasoning_checkpoint:
  hypothesis: "Switching to a model with NO live serving endpoint (retired/stealth/parked, e.g. openrouter/owl-alpha) makes the always-tools chat turn raise openai.NotFoundError (404 'No endpoints found for <model>') at llm_service.py:142. chat.py's APIStatusError chain has no branch for the model-unavailable family, so it lands in the else->upstream_error code, which useChat treats as a non-keyed generic error -> generic bubble + toast, then '[Response interrupted]'."
  confirming_evidence:
    - "Checkpoint log line: 'Chat upstream error: Error code: 404 - No endpoints found for openrouter/owl-alpha.' raised at llm_service.py:142, caught by the APIStatusError else-branch -> upstream_error (exact taxonomy match)."
    - "Anthropic/GPT-class models work after the SAME header switch -> MODEL-SPECIFIC, not the switch mechanism (eliminates hyp 2 id-mismatch and hyp 3 pin-not-persisted)."
    - "Evidence trail already proved: client sends no model; thread pin resolves server-side; loop ALWAYS sends tools; APIStatusError else maps 400/404 -> upstream_error; useChat KEY_FAILURE_CODES excludes upstream_error -> generic bubble + toast."
  falsification_test: "After adding a typed model_unavailable branch (404, and 400 'No endpoints found' variants), repro on owl-alpha must show the typed in-thread bubble ('That model isn't available right now') with a plain Retry and NO toast/Reconnect; a plain 400 (no marker) must STILL surface upstream_error."
  fix_rationale: "Fix B addresses the ROOT defect: a recoverable, model-specific 4xx was being funneled into the generic broken-stream dead-end. A typed code routes it to clear, actionable copy. A static catalog filter (A) can't fix this class (owl-alpha has zero serving endpoints at call time even when the cached catalog looked valid), so B is the correct primary fix."
  blind_spots: "Assuming ALL 404 on the completions endpoint == model-unavailable (true for OpenRouter chat completions). 400 detection relies on the OpenRouter message substring 'no endpoints found' surviving in str(e) — verified the existing _status_error test helper exposes the message via str(e). Toast suppression for this typed bubble is a UX choice matching the existing typed-error single-surface pattern."
test: DONE — backend pytest (8/8, 3 new) green; frontend build green; lint adds zero new errors.
next_action: RESOLVED. Fix B applied + verified. Coordinator to handle commit/archive. Option A (catalog tool-capability filter) noted as a deferred follow-up; it would NOT prevent owl-alpha's 404.

## Evidence

- timestamp: 2026-06-30
  checked: frontend/src/hooks/useChat.ts sendMessage (lines 110-339) — the chat request payload
  found: The POST body is ONLY `JSON.stringify({ content })`. No model field is ever sent from the client on a turn.
  implication: The turn's model is NOT carried in the message body; it must be resolved server-side from the thread pin.

- timestamp: 2026-06-30
  checked: backend/models/schemas.py MessageCreate (lines 77-78)
  found: MessageCreate has a single field `content: str` — no `model`.
  implication: `getattr(body, "model", None)` in _resolve_key_and_model is ALWAYS None. Model resolution falls to the thread pin.

- timestamp: 2026-06-30
  checked: frontend/src/components/ChatContainer.tsx + backend/routers/threads.py (PATCH /{thread_id}, lines 58-88) + ThreadModelUpdate schema
  found: The per-thread header ModelSelector calls onThreadModelChange → PATCH /api/threads/{id} which writes threads.model. The pin persists on the thread row.
  implication: Mid-chat model switch = a thread.model write; the next turn reads it back. Confirms "per-thread header selector, mid-chat" repro path.

- timestamp: 2026-06-30
  checked: backend/routers/chat.py _resolve_key_and_model (lines 152-207) + event_generator model use (lines 763, 891-900)
  found: model = body.model(None) → _safe_thread_model(thread_row) → user default → settings.llm_model. The agent loop ALWAYS builds tools=[KB_LS,KB_TREE,KB_READ,KB_GREP,KB_GLOB,EXPLORE_KB,(+RETRIEVAL/ANALYZE/SQL/WEB)] and passes tools=tools to stream_chat_completion every iteration.
  implication: Whatever model the thread is pinned to is called WITH a tools array, unconditionally. A model lacking tool-calling support cannot satisfy this request.

- timestamp: 2026-06-30
  checked: backend/services/llm_service.py stream_chat_completion (lines 134-142)
  found: kwargs always includes tools when tools is non-empty; client.chat.completions.create(stream=True, tools=...). With stream=True the openai SDK issues the HTTP request at .create() and raises an APIStatusError subclass on a non-2xx BEFORE yielding any chunk.
  implication: A 4xx from OpenRouter raises inside the `for event in stream_chat_completion(...)` loop, caught by chat.py's except chain.

- timestamp: 2026-06-30
  checked: backend/routers/chat.py SSE error taxonomy (lines 1196-1265)
  found: 429→rate_limit; APIStatusError 402→payment_required, 401→no_api_key, 403→forbidden, ELSE (400/404/5xx)→upstream_error; bare Exception→{"error": scrub(str(e))}. There is NO branch for "model does not support tools" / 400 / 404.
  implication: A 400/404 "no endpoints support tool use" (or invalid/data-policy) lands in the generic else→upstream_error branch (or the Exception branch). Neither is a typed key-failure code.

- timestamp: 2026-06-30
  checked: frontend/src/hooks/useChat.ts error handling (lines 260-331)
  found: KEY_FAILURE_CODES = [no_api_key, payment_required, forbidden]. Codes upstream_error / rate_limit / any other string → generic bubble copy "The assistant ran into a problem. Try again, or rephrase your question." + 4s red toast. Then backend finally writes "[Response interrupted]" when full_content is empty.
  implication: EXACT symptom match. The generic bubble fires for upstream_error and for any non-keyed error string.

- timestamp: 2026-06-30
  checked: backend/routers/models.py + backend/services/model_catalog_service.py (full)
  found: GET /api/models serves the ENTIRE OpenRouter catalog (340+ models) via refresh_if_stale + build_model_response. The ONLY filter offered is ?free_only. There is NO tool-capability filter. The raw OpenRouter model object IS stored in model_cache.raw (which contains `supported_parameters`), but `supported_parameters` is never read anywhere in the backend (grep: 0 hits).
  implication: ROOT-CAUSE SURFACE — the per-thread selector exposes non-tool-capable models as selectable. Picking one guarantees the always-tools turn fails with a 4xx → generic bubble. The data needed to filter (supported_parameters) is already cached but unused.

- timestamp: 2026-06-30
  checked: Runtime checkpoint response — user reproduced on dev with a real OpenRouter key.
  found: Failing model = openrouter/owl-alpha. Backend log: "Chat upstream error: Error code: 404 - {'error': {'message': 'No endpoints found for openrouter/owl-alpha.', 'code': 404}}". Raised at llm_service.py:142 client.chat.completions.create, caught by APIStatusError else-branch -> upstream_error -> generic bubble + "[Response interrupted]". Anthropic/GPT models work fine after the SAME switch.
  implication: CONFIRMS root cause and exact taxonomy path. Model-specific 404 "No endpoints found" (retired/stealth/parked model) is funneled into the generic upstream_error dead-end. A static supported_parameters filter would NOT catch owl-alpha (zero serving endpoints at call time), so the primary fix must be a typed SSE error branch (Fix B).

## Eliminated

- hypothesis: "Model id mismatch between the header selector option value and what the backend sends to OpenRouter (stale/renamed slug)."
  evidence: "Anthropic/GPT-class models work fine after the identical header switch + thread.model write -> the id round-trips correctly; the failure is specific to models with no live endpoint, not a mismatch."
  timestamp: 2026-06-30
- hypothesis: "The per-thread selected model is not persisted/passed correctly on the next turn."
  evidence: "Same as above — switching to working models via the same persistence path succeeds; only owl-alpha (no serving endpoint) 404s. The pin persists and is read back correctly."
  timestamp: 2026-06-30

## Resolution

root_cause: |
  Switching the per-thread model to one with NO live serving endpoint (retired/stealth/parked,
  e.g. openrouter/owl-alpha) makes the always-tools chat turn raise openai.NotFoundError —
  404 "No endpoints found for <model>" — at llm_service.py:142. chat.py's APIStatusError chain
  had branches for 402/401/403 but NOT for the model-unavailable family (404 + the 400 "No
  endpoints found that support tool use" / "matching your data policy" variants), so it fell to
  the generic else -> `upstream_error`. useChat's KEY_FAILURE_CODES excludes `upstream_error`,
  so it rendered the GENERIC broken-stream bubble + 4s toast and the backend then wrote
  "[Response interrupted]". A static catalog (supported_parameters) filter cannot fully prevent
  this class — a model can 404 at call time even when the cached catalog looked valid.
fix: |
  Fix B — typed SSE error branch for the model-unavailable family.
  Backend (chat.py): added an APIStatusError branch BEFORE the else, matching status 404 OR
  (status 400 AND OpenRouter message contains "no endpoints found"), yielding the new structured
  code `model_unavailable` ("That model isn't available right now. Pick a different model.").
  Logged at warning level + scrubbed; plain 400s without the marker still fall to upstream_error.
  Frontend: extended Message.errorType and ErrorMessageBubble's `type` union with
  `model_unavailable`; added it to the typed-code list (renamed KEY_FAILURE_CODES ->
  TYPED_ERROR_CODES) in useChat so it renders the typed in-thread bubble with empty content and
  NO toast; added a dedicated ErrorMessageBubble variant with the model-specific sentence and a
  PLAIN Retry button (no Reconnect / Add credits). ChatContainer already forwards msg.errorType.
verification: |
  Backend: backend/tests/test_error_surfacing.py — 8/8 pass, incl. 3 new
  (test_model_unavailable_code_on_404, test_model_unavailable_code_on_400_no_tool_endpoints,
  test_generic_400_stays_upstream_error). Frontend: `npm run build` (tsc -b + vite) green; `npm
  run lint` adds ZERO new errors — the 5 reported problems are pre-existing in untouched files
  (FileUpload/AuthContext/ToastContext/ChatPage/themeBootstrap.test), confirmed identical count
  with the two changed files stashed. Changed files (useChat.ts, ErrorMessageBubble.tsx) are lint-clean.
files_changed:
  - backend/routers/chat.py (APIStatusError 404/400 model_unavailable branch)
  - backend/tests/test_error_surfacing.py (3 new tests)
  - frontend/src/hooks/useChat.ts (errorType union + TYPED_ERROR_CODES)
  - frontend/src/components/ErrorMessageBubble.tsx (type union + RECOVERY_SENTENCE + variant)

## Follow-up (Option A — not implemented this session)

- Filter the per-thread ModelSelector to tool-capable models using the already-cached
  `supported_parameters` (model_cache.raw). Additive/low-value here: it would NOT stop
  owl-alpha's 404 (zero serving endpoints at call time), and `supported_parameters` is
  currently read nowhere in the backend. Defer to a dedicated catalog-UX task.
