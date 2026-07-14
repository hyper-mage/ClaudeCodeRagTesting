---
status: diagnosed
trigger: "Phase 17 UAT Test 5 (SC-5): two concurrent chat turns (two threads/users, different personas) fail — very laggy setup, error+retry, after several attempts both ran tool calls but produced no output (timed out/errored). Single-turn chat (Tests 1-4) works fine. Goal: find_root_cause_only (no fix)."
created: 2026-07-14T00:00:00Z
updated: 2026-07-14T00:00:00Z
---

## Current Focus

hypothesis: "Concurrent chat turns fail because (a) the configured chat model is a free-tier `:free` OpenRouter slug whose per-key concurrency/RPM caps reject the 2nd simultaneous stream (429/5xx), AND (b) the main chat streaming loop iterates a BLOCKING synchronous OpenAI client directly on the single-worker asyncio event loop (no asyncio.to_thread offload), serializing concurrent turns and starving one toward the 120s llm_timeout → empty content → '[Response interrupted]'."
test: "Static code + config inspection (read-only, per goal find_root_cause_only)."
expecting: "Confirm sync OpenAI client, no to_thread on the main stream, single uvicorn worker, and free-tier model in use."
next_action: "Return ROOT CAUSE FOUND to caller. Do NOT fix."

## Symptoms

expected: "Two chat turns running at the same time (two threads or two users) each stream to completion in their own persona; no cross-persona bleed."
actual: "broken. Very laggy setting up two new chats. When run together they break — error + retry. After several attempts both ran tool calls but still gave no output; assumed they timed out or errored out. No wrong-persona-voice leak observed."
errors: "On-screen error + Retry; no specific error text captured. Turns produce no final output; assistant rows likely stamped '[Response interrupted]'."
reproduction: "Test 5 in 17-HUMAN-UAT.md. Only CONCURRENT turns fail. Single-turn chat (Tests 1-4) passed."
started: "Discovered during UAT 2026-07-14. Concurrency path never tested before."

## Eliminated

- hypothesis: "openrouter_api_key is empty (VERIFICATION carried env note: chat 500s when key empty)."
  evidence: "Tests 1-4 single-turn chat PASSED, and personas/tool calls worked live in prior UAT. A valid key must be present and the model must respond; the failure is specific to CONCURRENCY, not key absence."
  timestamp: 2026-07-14

- hypothesis: "Cross-request shared mutable state (persona resolver / SSE buffers / LLM client singleton) corrupts or serializes concurrent turns (Hypothesis 3 / per-request isolation defect)."
  evidence: "_resolve_persona (chat.py:958) returns a local persona_voice passed as a call parameter; get_llm_client (llm_service.py:11-28) constructs a FRESH OpenAI() per call with NO module singleton and NO @lru_cache (SEC-04, documented); tool_calls_acc (llm_service.py:153) is a per-call local dict; no module-level mutable buffer is shared across requests. Consistent with the observed ABSENCE of persona bleed — the failure is no-output, not corruption."
  timestamp: 2026-07-14

## Evidence

- timestamp: 2026-07-14
  checked: "backend/services/llm_service.py get_llm_client + stream_chat_completion (full)"
  found: "Uses `from openai import OpenAI` (SYNC client, not AsyncOpenAI). stream_chat_completion is a SYNCHRONOUS generator (def, Generator[dict,None,None]). It calls client.chat.completions.create(stream=True, timeout=settings.llm_timeout) (blocking HTTP at .create()) then `for chunk in stream:` (blocking socket read per chunk)."
  implication: "Every next() on this generator runs blocking network I/O with no await."

- timestamp: 2026-07-14
  checked: "backend/routers/chat.py event_generator + _traced_turn (lines 944, 1007-1144, 1559-1591)"
  found: "event_generator is async; _traced_turn is an async generator consumed via `async for ev in worker` (1568). The MAIN token stream is driven by a plain synchronous `for event in stream_chat_completion(...)` at line 1134 — iterated DIRECTLY on the event loop, with NO asyncio.to_thread offload. By contrast, the subagent paths (explore_kb 1216-1235, analyze_document 1291-1310) DO offload their blocking generators via asyncio.create_task(asyncio.to_thread(_drive)) + queue + `await asyncio.to_thread(q.get)`."
  implication: "The primary chat stream blocks the single event loop between yields; only the subagent streams were made non-blocking. Inconsistent concurrency handling; the hot path (every turn) is the blocking one."

- timestamp: 2026-07-14
  checked: "Dockerfile CMD + dev invocation (CLAUDE.md, QUICKSTART.md, 17-11-PLAN.md)"
  found: "CMD [\"uvicorn\", \"main:app\", \"--host\", \"0.0.0.0\", \"--port\", \"8000\"] — NO --workers flag → uvicorn default = 1 worker = 1 process = 1 event loop. Dev runs `uvicorn main:app` (also single worker). CONCERNS.md:133-136 already flags single-process concurrency as a known limit."
  implication: "No process-level parallelism to mask the blocking-loop defect. Two concurrent SSE turns contend on ONE event loop; while turn A blocks in next(stream), turn B cannot progress (cannot connect, cannot stream, no heartbeats)."

- timestamp: 2026-07-14
  checked: "Chat model tier — .env is permission-blocked; corroborated from git-tracked docs"
  found: "HANDOVER.md confirms the app runs `:free` OpenRouter chat slugs (e.g. LLM_MODEL=openai/gpt-oss-120b:free; .env.prod has a `:free` toggle block). PROGRESS.md: '.env configured (OpenRouter + Nemotron models)'. STATE.md Deferred Items: 'Free-model provider 429s make live smokes flaky (D-999.1-LLM-A) — open'. Project research (PITFALLS.md:400, FEATURES.md:214) documents `:free` models have RPM/RPD + concurrency caps. Investigation focus named nvidia/nemotron-3-super-120b-a12b:free as a candidate."
  implication: "The active dev chat model is (strongly inferred) a free-tier `:free` OpenRouter slug. Free tier reliably rejects/queues concurrent streaming requests → 429 (RateLimitError) or upstream 5xx. Single turns pass because they are within the 1-concurrent budget."

- timestamp: 2026-07-14
  checked: "backend/routers/chat.py SSE error taxonomy (1457-1551) + interrupt stamp (1583-1587); config.py llm_timeout"
  found: "openai.RateLimitError → 'rate_limit' typed bubble. APIStatusError 402/401/403/404 typed; else → 'upstream_error' generic bubble. Bare Exception (incl. openai.APITimeoutError, which is an APIConnectionError, NOT APIStatusError) → {'error': scrub(str(e))} generic error event. When full_content is empty at the event_generator seam, the assistant row is stamped '[Response interrupted]'. llm_timeout=120s."
  implication: "A concurrent turn that 429s → error+Retry. A concurrent turn starved by the blocked loop past 120s → APITimeoutError → generic error+Retry, empty content → '[Response interrupted]'. Tool calls can fire (tool_start/tool_result SSE) yet the final synthesis stream stalls/errors → no content_delta → no output. Exact symptom match: 'ran tool calls but gave no output'."

## Resolution

root_cause: |
  CONCURRENT chat turns fail for two compounding reasons; single turns pass because
  neither is exercised until a 2nd simultaneous stream exists.

  (1) ENVIRONMENT / MODEL-TIER (primary trigger of the visible errors): the configured
  chat model is a free-tier `:free` OpenRouter slug (strongly inferred; .env unreadable
  by policy, but HANDOVER.md/PROGRESS.md/STATE.md + project research confirm `:free`
  models are in use and carry RPM/RPD + concurrency caps). Free tier serves ~1 concurrent
  request per key; the 2nd simultaneous streaming turn is rejected/queued → openai
  RateLimitError (429 → 'rate_limit' bubble) or upstream 5xx (→ 'upstream_error' bubble).
  This is the exact signature of "single turn works, two concurrent turns error."

  (2) BACKEND CODE DEFECT (amplifier; independently causes lag + timeout): the main chat
  streaming loop iterates a BLOCKING synchronous OpenAI client (`from openai import OpenAI`,
  stream_chat_completion is a sync generator doing blocking .create() + `for chunk in stream`)
  DIRECTLY on the asyncio event loop (chat.py:1134), with NO asyncio.to_thread offload —
  even though the subagent paths in the same function DO offload via to_thread+queue. Under
  a single uvicorn worker (CMD has no --workers → 1 event loop), while turn A blocks in
  next(stream) waiting on the free model's slow time-to-first-token / inter-chunk gaps, turn
  B's coroutine cannot run at all — it cannot connect, stream, or heartbeat. This produces
  "very laggy setting up two new chats" and can push a starved turn past llm_timeout=120s →
  openai.APITimeoutError → generic error event → empty full_content → '[Response interrupted]'
  ("ran tool calls but gave no output").

  Net: the free-tier model reliably errors the 2nd concurrent stream; the blocking single-loop
  architecture guarantees serialization/lag and can independently time a starved turn out —
  so both surface as error+Retry with no output. No persona bleed occurs because per-request
  isolation is clean (fresh client per call, local persona_voice) — which is why no wrong-voice
  leak was seen; the turns simply never produced output.
fix: ""
verification: ""
files_changed: []
