# Phase 11: Per-Request Key + Model Resolution (chat-loop seam) - Research

**Researched:** 2026-06-22
**Domain:** Per-request BYOK key + model resolution at the FastAPI agentic chat-loop seam (OpenRouter via raw OpenAI SDK), fail-closed demo fallback, observability secret-scrub, streaming usage capture
**Confidence:** HIGH (every code seam read directly; OpenRouter usage/error semantics + OpenAI SDK exception hierarchy + LangSmith gating + free-model slug verified against current sources 2026-06-22)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** All LLM calls within a chat turn run on the resolved user key — `stream_chat_completion` (main), `rerank_service`, `subagent_service` (`analyze_document`), `explorer_service` (`explore_kb`). `metadata_service` is ingestion-only → untouched. Thread the resolved key + model into all four call sites' `get_llm_client()`.
- **D-02:** Aux model defaults to the single resolved turn model. Seam supports an OPTIONAL "utility/aux model" override (plumbing + fallthrough only this phase; storage/picker → P13/P15).
- **D-03:** Graceful fallthrough — full three-tier resolution function (`thread.model` → `user_preferences.default_model` → owner default) that TOLERATES the absent P13 schema (the `thread.model` column and `user_preferences` table do NOT exist yet). Resolves to owner default now; auto-lights-up in P13. ZERO P13 schema created in P11.
- **D-04:** Capture + persist the trailing `usage` object (summed across all tool-loop iterations) to a new `messages` usage/cost column (adds a migration). Phase 14 only reads + renders. Today `stream_chat_completion` returns on `finish_reason == "tool_calls"` (llm_service.py:148) and discards the final chunk — must restructure to capture the trailing usage chunk.
- **D-05:** Everyone is eligible for the owner-key fallback when the flag is ON, including anonymous Try-demo users. No eligibility narrowing; the cost bound comes from the MODEL, not from who's eligible.
- **D-06:** Owner-key fallback is PINNED to a free model via a new `demo_fallback_model` config (default a known live `:free` slug; executor confirms current). Demo users picking among free models → P12/P15.
- **D-07:** Demo users retain the Connect-OpenRouter affordance (Phase 10).
- **D-08:** Demo-mode signal exposed in P11 — emit a `mode: "demo"` (+ free-tier) indicator on the response/SSE. Notice copy: "Demo mode — a free model is in use; it may be slower, less accurate, or temporarily rate-limited (no usage left)." Banner UI itself is Phase 15.
- **D-09:** `demo_fallback_enabled: bool = False` — new in `config.py`, env-driven, OFF by default (incl. dev). Fail-closed three-branch shape fully built + testable now; enabling in prod is Phase 15 (hard-gated on SEC-03 / backlog 999.2).
- **D-10:** `wrap_openai` (LangSmith) gated OFF for per-user-key calls — build the client without the wrapper when key source is a user key. Owner/demo calls may still trace. Validate against the prod LangSmith project during planning (highest-blast-radius item).
- **D-11:** A `sk-or-[A-Za-z0-9_-]+` regex scrub runs before any backend log line OR SSE-error payload. Today the SSE error path yields `{"error": str(e)}` (chat.py ~907) — `str(e)` can leak a key.
- **D-12:** OpenRouter 429 (rate-limit) vs 402 (payment) detected distinctly, surfaced as tailored structured SSE errors, NOT the generic error. Structured `no_api_key` error reuses the existing `useChat.ts` in-band error path.

### Claude's Discretion

Exact resolved-value parameter signatures (`get_llm_client(api_key=…, model=…)`, `stream_chat_completion(..., api_key=…, model=…)`), the `_resolve_key_and_model()` helper shape/location, the aux-model override parameter name, the `messages` usage/cost column name(s) + migration filename (next free number = **029**), the `demo_fallback_model` / `demo_fallback_enabled` config field names, structured-error code taxonomy (`no_api_key` / `rate_limit` / `payment_required` etc.), and where the `mode:"demo"` signal rides (done event vs a dedicated SSE event) — planner/executor decide, following existing conventions.

### Deferred Ideas (OUT OF SCOPE)

- **D-09-A** — `execute_readonly_query` `SET LOCAL role` (42501) fix — stays DEFERRED (separate RPC-fix plan; orthogonal to the key/model seam).
- User-facing "utility/aux model" override (storage + picker) → Phase 13 / 15.
- Demo users picking among free models (free-only catalog filter) → Phase 12 + Phase 15.
- Non-dismissible demo-mode banner UI → Phase 15. P11 ships the `mode:"demo"` signal only.
- Per-message cost display, balance, low-balance warning, settings/key-state UX, mid-chat 401/402/403 recovery → Phase 14.
- Enabling `demo_fallback_enabled` in prod → Phase 15 (hard-gated on SEC-03 / backlog 999.2).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| **SEC-04** | Concurrent requests from different users never share a key or model (per-request client, no cross-user bleed) | Per-request parameter threading (no module-level client singleton; `@lru_cache` only on `get_settings()` for owner/global config, never on the key-bearing client). See §Architecture Patterns Pattern 1, §Pitfall 1, §Code Examples 1. The codebase already has NO cached LLM client — `get_llm_client()` constructs a fresh `OpenAI(...)` each call; the fix is purely additive params. |
| **SEC-01** (backend half) | User OpenRouter keys never appear in LangSmith traces, Sentry events, logs, or SSE error payloads | LangSmith `wrap_openai` gate at client construction (D-10) + backend `sk-or-` regex scrub before every log line and SSE-error payload (D-11). See §Architecture Patterns Pattern 2 & 3, §Pitfall 2, §Code Examples 2 & 4. Frontend Sentry half already shipped (Phase 10, `sentry.ts`). |
| **DEMO-03** | When the user has no key and demo is off, chat refuses with a connect-key prompt (fail-closed) | Three-branch fail-closed resolution (`if user_key / elif demo_flag_on / else refuse`) emitting a structured `no_api_key` SSE error consumed by the existing `useChat.ts` in-band path. See §Architecture Patterns Pattern 1, §Pitfall 5, §Code Examples 1 & 3. |
</phase_requirements>

## Summary

This is a **narrow, high-blast-radius integration seam**, not greenfield. The entire phase rewires three things at the chat-loop boundary while leaving the agent's tool loop, budget logic, and SSE contract structurally intact: (1) **where the API key and model come from** (global `settings` → per-request resolved values), (2) **whether the LangSmith wrapper traces the call** (always-on → gated off for user keys), and (3) **what reaches logs/SSE** (raw `str(e)` → `sk-or-`-scrubbed). All four chat-turn LLM call sites (`llm_service.stream_chat_completion`, `rerank_service`, `subagent_service`, `explorer_service`) currently read `settings.llm_model` and call `get_llm_client()` with zero arguments — the work is threading two explicit parameters (`api_key`, `model`) through each, plus the budget lookup at `chat.py:590`.

The codebase is **well-positioned for SEC-04**: there is no module-level LLM client singleton and no `@lru_cache` on any key-bearing function. `get_llm_client()` already builds a fresh `OpenAI(...)` per call; `@lru_cache` is only on `get_settings()` (owner/global config, correctly cacheable). So the cross-user-bleed fix is additive parameters, not a refactor away from a singleton. The one trap is the budget lookup `fetch_model_context_length(settings.llm_model, settings.resolved_llm_api_key)` at chat.py:590 — it must switch to the resolved per-request key+model or it probes OpenRouter with the wrong credentials.

The two genuinely tricky pieces are: **(a) usage capture** — today `stream_chat_completion` does `return` on `finish_reason == "tool_calls"` (line 148), discarding the chunk that carries OpenRouter's `usage` object, which arrives in the **last SSE message always** (the `stream_options`/`usage:{include}` params are now deprecated no-ops — usage is automatic); the loop must drain to stream end and accumulate `usage` across all tool-loop iterations; and **(b) 402-vs-429 detection** — the OpenAI SDK has a `RateLimitError` subclass for 429 but **no dedicated 402 class** (402 surfaces as a bare `APIStatusError` with `.status_code == 402`), so the catch order is `RateLimitError` first, then `APIStatusError` branching on `.status_code`.

**Primary recommendation:** Add a single `_resolve_key_and_model(db, user_id, thread, body)` helper in `chat.py` returning `(api_key, model, mode, is_user_key)`; thread `api_key` + `model` + a `trace: bool` (= `not is_user_key`) through `get_llm_client()` and all four call sites; restructure the `stream_chat_completion` stream loop to drain-and-accumulate `usage`; catch `RateLimitError`/`APIStatusError(402)` distinctly and emit structured SSE errors via a `sk-or-`-scrubbed helper. Default `demo_fallback_model = "meta-llama/llama-3.3-70b-instruct:free"` (verified live 2026-06-22).

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Key + model resolution (decrypt user key, three-tier model, demo gate) | API / Backend (`chat.py send_message`) | Database (`user_api_keys` read via service-role) | Secret custody is backend-only; the frontend never sees the key or the resolution branch. Resolution must run under the user's JWT-bound `user_id`. |
| Per-request LLM client construction | API / Backend (`llm_service.get_llm_client`) | — | The key is now request-scoped state; the client must be built per request, never cached at module scope (SEC-04). |
| LangSmith trace gating | API / Backend (`llm_service` client construction) | Observability (LangSmith vendor) | The wrapper is applied at client-build time; gating it off for user keys keeps user secrets + prompts inside the trust boundary (SEC-01). |
| `sk-or-` scrub on logs + SSE errors | API / Backend (`chat.py` error path + a scrub helper) | — | Mirrors the frontend Sentry rule already shipped (`sentry.ts`); the backend is the only place `str(e)` from an OpenRouter SDK call is stringified. |
| Usage capture + persistence | API / Backend (`llm_service` stream loop → `chat.py` → `messages` column) | Database (`messages` migration 029) | OpenRouter is the source of truth for usage; capture from the last streamed chunk, sum across loop iterations, persist server-side. |
| Demo-mode signal | API / Backend (SSE `done` or dedicated event) → Frontend (`useChat.ts` consumes) | — | P11 guarantees the signal exists; the banner UI render is Phase 15. |
| 402/429 error surfacing | API / Backend (catch in chat loop) → Frontend (`useChat.ts` in-band error path) | — | The status distinction is only visible to the backend that holds the SDK exception; the frontend renders tailored copy. |

## Standard Stack

No new dependencies. Everything needed is already pinned and imported.

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `openai` | 1.74.0 | Per-request chat client against OpenRouter; exception hierarchy (`RateLimitError`, `APIStatusError`) for 429/402 detection | `[VERIFIED: backend/config.py + CLAUDE.md stack]` Already the sole LLM SDK (project rule: raw SDK, no LangChain). `stream_chat_completion` already uses it. |
| `langsmith` | 0.3.42 | `wrap_openai` wrapper — gated OFF for user-key calls (D-10) | `[VERIFIED: backend/services/llm_service.py:6 import]` Already imported with an ImportError fallback. Gate is "don't call `wrap_openai()`", no new API. |
| `cryptography` (MultiFernet) | 46.0.5 | `crypto_service.decrypt_key()` — exercised for the first time this phase | `[VERIFIED: backend/services/crypto_service.py]` Phase 9 built encrypt/decrypt; P11 calls `decrypt_key()` in the resolution block. |
| `supabase` (python) | 2.13.0 | Service-role read of `user_api_keys`; write usage to `messages` | `[VERIFIED: CLAUDE.md + backend/database.py]` Existing service-role pattern; bypasses RLS for the keys-table read. |
| `httpx` | (transitive, used directly) | `fetch_model_context_length` budget lookup — must switch to resolved key | `[VERIFIED: backend/services/budget_service.py:25]` Already the OpenRouter HTTP path. |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `re` (stdlib) | — | `sk-or-` scrub regex (D-11) | Mirror the frontend regex `sk-or-v1-[A-Za-z0-9_-]+` → `[redacted-key]`. **Note:** CONTEXT D-11 specifies the broader `sk-or-[A-Za-z0-9_-]+` (matches `sk-or-v1-…` AND any future `sk-or-` prefix); use the broader form on the backend. |
| `pytest` | (in `backend/tests/`) | Validation gate — existing fixtures `mock_stream_chat_completion`, `mock_user_id`, `mock_langsmith_run` cover the chat loop | All new tests. See §Validation Architecture. |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Don't-call-`wrap_openai` gate (D-10) | `LANGSMITH_HIDE_INPUTS/OUTPUTS` env or per-call `langsmith_extra` anonymizer | `[CITED: docs.langchain.com/langsmith/mask-inputs-outputs]` Env-level hide is process-global (would disable owner-key tracing too); per-call anonymizer still ships metadata. The client-construction gate (skip the wrapper entirely for user keys) is the cleanest per D-10 and keeps owner/demo tracing intact. |
| Drain-and-accumulate usage from stream | `GET /api/v1/generation` post-hoc cost endpoint | `[CITED: openrouter.ai/docs/cookbook/administration/usage-accounting]` The generation endpoint has a propagation delay; the streamed `usage` object is immediate and authoritative. Drain-and-accumulate is correct for the multi-iteration loop. |

**Installation:** None — no new packages.

**Version verification (2026-06-22):**
- `openai` 1.74.0 — `[VERIFIED: backend/config.py-era pin; exception hierarchy confirmed at github.com/openai/openai-python]` `APIStatusError` base with `.status_code`/`.response`; `RateLimitError` = 429; **no 402 subclass**.
- `langsmith` 0.3.42 — `[VERIFIED: CLAUDE.md stack]` `wrap_openai` conditional-wrap pattern confirmed current.
- `cryptography` 46.0.5, `supabase` 2.13.0, `pydantic` 2.11.1 — `[VERIFIED: CLAUDE.md stack]` unchanged from Phases 9/10.

## Architecture Patterns

### System Architecture Diagram

```
POST /api/threads/{id}/messages  (useChat → apiStream, Supabase bearer JWT)
        │
        ▼
  send_message (chat.py)
        │  thread-ownership check (existing) → user_id bound to JWT sub
        ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │  _resolve_key_and_model(db, user_id, thread, body)   [NEW BLOCK] │
  │                                                                   │
  │   MODEL (three-tier, tolerates absent P13 schema):                │
  │     body.model? → thread.model? → user_pref.default_model?        │
  │                 → settings.llm_model (owner default)              │
  │       (each tier wrapped to swallow PostgREST 42703/42P01 →       │
  │        fall through; D-03)                                        │
  │                                                                   │
  │   KEY (fail-closed three-branch; NEVER user_key or owner_key):    │
  │     if user_api_keys row exists:                                  │
  │         api_key = decrypt_key(row.encrypted_key)  ← in-memory     │
  │         mode="user";  trace=False (D-10)                          │
  │     elif settings.demo_fallback_enabled:           ← GLOBAL FLAG  │
  │         api_key = settings.resolved_llm_api_key (owner)           │
  │         model  = settings.demo_fallback_model (:free, pinned)     │
  │         mode="demo"; trace=True                                   │
  │     else:                                                         │
  │         yield SSE error {error:"no_api_key", …}  → return  ◀── DEMO-03 fail-closed
  └─────────────────────────────────────────────────────────────────┘
        │ (api_key, model, mode, trace)
        ▼
  budget: fetch_model_context_length(model, api_key)   [SWITCH from settings.* — Pitfall 1]
        │
        ▼
  agentic while-loop (≤ chat_max_iterations=15)   [STRUCTURE UNCHANGED]
        │
        ├─► stream_chat_completion(msgs, …, api_key=, model=, trace=)   ← main
        │       └─ get_llm_client(api_key, trace) → OpenAI(...) [wrap_openai only if trace]
        │       └─ drain to stream end; accumulate `usage` (last chunk) ← D-04 / Pitfall 6
        │       └─ catch RateLimitError(429) / APIStatusError(402) → structured event ← D-12
        │
        ├─► execute_tool → rerank_service.rerank(…, api_key=, model=)     ← D-01 aux
        ├─► analyze_document → subagent_service(…, api_key=, model=)      ← D-01 aux
        └─► explore_kb → explorer_service(…, api_key=, model=)            ← D-01 aux
        │
        ▼
  SSE: content_delta… → done {message_id, content, usage?, mode?}   [usage/mode ADDED]
  on error: event:error {error:"rate_limit"|"payment_required"|<scrubbed str(e)>} ← D-11/D-12
        │
        ▼
  persist: messages.content + messages.tools_used + messages.usage(NEW col, migration 029)
```

### Recommended Project Structure

No new files required (all seams are existing). New artifacts:
```
backend/
├── services/
│   └── llm_service.py          # MODIFIED: get_llm_client(api_key, model, trace); stream usage capture; 402/429 catch
│   └── rerank_service.py       # MODIFIED: rerank(query, docs, api_key=, model=) threaded through
│   └── subagent_service.py     # MODIFIED: run_document_analysis(..., api_key=, model=)
│   └── explorer_service.py     # MODIFIED: run_exploration(..., api_key=, model=)
│   └── log_scrub.py            # NEW (optional): scrub_secrets(s) -> str  — sk-or- regex; reused by chat.py + log filter
├── routers/
│   └── chat.py                 # MODIFIED: _resolve_key_and_model(); thread params; scrub SSE error; usage persist; mode signal
├── config.py                   # MODIFIED: demo_fallback_enabled=False, demo_fallback_model=":free slug"
└── tests/
    └── test_key_model_resolution.py   # NEW: fail-closed branches, no-bleed, model fallthrough
    └── test_usage_capture.py          # NEW: trailing usage drained + summed across iterations
    └── test_error_surfacing.py        # NEW: 402/429 → structured codes; sk-or- scrub
    └── test_langsmith_gate.py         # NEW: wrap_openai NOT applied for user-key client
supabase/migrations/
└── 20240301000029_add_usage_to_messages.sql   # NEW: messages usage/cost column (D-04)
```

### Pattern 1: Fail-Closed Three-Branch Resolution (DEMO-03, Pitfall 5/7)

**What:** A single resolution helper that never short-circuits to `user_key or owner_key`. Three explicit branches; the `else` refuses.
**When to use:** Once per chat turn, before the budget build and agentic loop.
**Example:**
```python
# chat.py — NEW helper (in send_message scope or module-level taking db/user_id)
# Source: synthesized from .planning/research/ARCHITECTURE.md §"How the Agentic Chat Loop
#         Selects Key + Model" + PITFALLS.md Pitfall 7 + crypto_service.decrypt_key (Phase 9)
def _resolve_key_and_model(db, user_id: str, thread_row: dict, body) -> tuple[str | None, str, str, bool]:
    settings = get_settings()

    # MODEL — three-tier, each tier tolerant of absent P13 schema (D-03).
    model = (
        getattr(body, "model", None)              # optional per-message override (future)
        or _safe_thread_model(thread_row)         # thread.model — column may not exist yet
        or _safe_user_default_model(db, user_id)  # user_preferences.default_model — table may not exist
        or settings.llm_model                     # owner default — always present
    )

    # KEY — fail-closed; NEVER `user_key or owner_key`.
    key_row = (
        db.table("user_api_keys").select("encrypted_key")
          .eq("user_id", user_id).maybe_single().execute()
    )
    if key_row and key_row.data:
        api_key = decrypt_key(key_row.data["encrypted_key"])  # in-memory, this turn only
        return api_key, model, "user", False                  # trace=False (D-10)
    if settings.demo_fallback_enabled:                        # GLOBAL flag, default OFF (D-09)
        model = settings.demo_fallback_model or model         # pin a free model (D-06)
        return settings.resolved_llm_api_key, model, "demo", True
    return None, model, "no_key", True                        # caller emits no_api_key, returns
```
The caller checks `mode == "no_key"` and yields the structured SSE error (Pattern 3) then `return`s.

### Pattern 2: Defensive Read of Absent P13 Schema (D-03)

**What:** Reading `thread.model` (column doesn't exist) and `user_preferences.default_model` (table doesn't exist) must NOT crash — fall through to the next tier.
**When to use:** Inside the model-resolution tiers.
**Why:** PostgREST returns a structured error, not a Python exception that the supabase-py client always raises cleanly — `[VERIFIED: WebSearch supabase docs]` an absent column raises Postgres `42703` (undefined_column) and an absent table raises `42P01` (undefined_table / relation does not exist). supabase-py surfaces these as an `APIError`. The robust approach is to **read the column off the already-fetched `thread_row` dict** (no extra query — `thread.data` is already a `SELECT *`, so an absent `model` key is just a missing dict key, never a DB error), and to **wrap the `user_preferences` query in a narrow try/except** that swallows the APIError and returns `None`.
**Example:**
```python
# thread_row is the existing `db.table("threads").select("*")...` result.data —
# absent `model` column = absent dict key, NOT a DB error. Cheapest defensive read.
def _safe_thread_model(thread_row: dict) -> str | None:
    return thread_row.get("model") if thread_row else None

def _safe_user_default_model(db, user_id: str) -> str | None:
    # user_preferences table does not exist until P13 → swallow APIError and fall through.
    try:
        r = (db.table("user_preferences").select("default_model")
               .eq("user_id", user_id).maybe_single().execute())
        return r.data.get("default_model") if r and r.data else None
    except Exception as e:        # APIError 42P01 (relation does not exist) pre-P13
        logger.debug(f"user_preferences not available (pre-P13): {scrub_secrets(str(e))}")
        return None
```
**Anti-pattern:** Querying `threads.select("model")` explicitly — that WOULD raise `42703` until P13 adds the column. Prefer reading off the existing `SELECT *` row.

### Pattern 3: LangSmith Wrapper Gated at Client Construction (D-10, Pitfall 1)

**What:** `get_llm_client()` gains a `trace: bool` param; `wrap_openai` is applied ONLY when `trace` is True. User-key calls pass `trace=False`.
**When to use:** Every LLM client built for a chat turn.
**Why client-level not per-request:** `[VERIFIED: WebSearch langchain forum/docs]` `wrap_openai` instruments the client object at construction; the trace happens because the client is wrapped. The clean gate is to **not wrap** when the key is a user key — this is a client-construction decision, exactly matching D-10's "build the client without the wrapper." Per-call `langsmith_extra` or env `LANGSMITH_HIDE_*` are process-global or still-ship-metadata alternatives (rejected — see Alternatives table).
**Example:**
```python
# llm_service.py — MODIFIED
def get_llm_client(api_key: str | None = None, trace: bool = True) -> OpenAI:
    settings = get_settings()
    client = OpenAI(
        api_key=api_key or settings.resolved_llm_api_key,  # per-user OR owner fallback
        base_url=settings.llm_base_url,
    )
    if trace and wrap_openai and settings.langsmith_api_key:
        client = wrap_openai(client)                       # owner/demo only (D-10)
    return client
```

### Pattern 4: Drain-and-Accumulate Streaming Usage (D-04, Pitfall 6)

**What:** OpenRouter puts the `usage` object in the **last SSE message, always** — `[VERIFIED: openrouter.ai/docs/cookbook/administration/usage-accounting]` the `stream_options:{include_usage:true}` and `usage:{include:true}` params are now **deprecated no-ops; usage is automatic**. Today `stream_chat_completion` does `return` on `finish_reason == "tool_calls"` (line 148) and never sees the trailing chunk. Restructure to keep draining the stream after emitting the `tool_call` event, capture `chunk.usage` when present, and yield it as a final event.
**When to use:** In `stream_chat_completion`; the caller sums `usage` across all loop iterations.
**Example:**
```python
# llm_service.py stream loop — MODIFIED (do NOT `return` on tool_calls; drain to end)
usage_obj = None
emitted_tool_call = False
for chunk in stream:
    # capture usage whenever present — it rides the LAST chunk (often choices==[])
    if getattr(chunk, "usage", None):
        usage_obj = chunk.usage

    choice = chunk.choices[0] if chunk.choices else None
    if choice:
        delta = choice.delta
        if delta.content:
            yield {"type": "text_delta", "text": delta.content}
        if delta.tool_calls:
            ...  # accumulate as today
        if choice.finish_reason == "tool_calls" and not emitted_tool_call:
            yield {"type": "tool_call", "tool_calls": list(tool_calls_acc.values())}
            emitted_tool_call = True
            # DO NOT return — keep draining so the trailing usage chunk is seen
# stream exhausted
if usage_obj is not None:
    yield {"type": "usage", "usage": _usage_to_dict(usage_obj)}  # cost, prompt/completion/total tokens
yield {"type": "done"}
```
The chat.py loop accumulates: `turn_usage["cost"] += ev["usage"].get("cost", 0)` etc. across iterations, then persists to the new `messages` column on the `done` event. **Note:** a known LiteLLM bug report `[CITED: github.com/BerriAI/litellm/issues/16112]` flags occasional token-count inaccuracy with tool definitions — treat OpenRouter `cost` as authoritative and tolerate occasionally-absent token sub-fields defensively.

### Pattern 5: Distinct 402 vs 429 Surfacing (D-12, Pitfall 8)

**What:** Catch `RateLimitError` (429) and `APIStatusError` with `.status_code == 402` separately and emit distinct structured SSE error codes.
**Why the catch order matters:** `[VERIFIED: github.com/openai/openai-python]` `RateLimitError` is a subclass of `APIStatusError` (429). There is **no `PaymentRequiredError` / 402 subclass** — 402 arrives as a bare `APIStatusError` with `.status_code == 402`. So you MUST catch `RateLimitError` BEFORE the generic `APIStatusError`, then branch the generic catch on `.status_code`.
**Example:**
```python
# chat.py event_generator — around the stream_chat_completion loop
import openai
try:
    for event in stream_chat_completion(current_messages, ..., api_key=api_key, model=model, trace=trace):
        ...
except openai.RateLimitError:                                   # 429
    yield _sse_error("rate_limit",
        "This model hit its rate limit. Wait a minute or pick another model / connect credits.")
    return
except openai.APIStatusError as e:                              # 402 has NO subclass
    if e.status_code == 402:
        yield _sse_error("payment_required",
            "This model needs credits. Connect your OpenRouter account or add credits.")
    else:
        yield _sse_error("upstream_error", "The assistant ran into a problem. Try again.")
    return
```
Free-model relevance (Pitfall 8/11): the 15-iteration loop fires many requests per turn, so free-model per-minute caps (20 RPM / 50 RPD per `[VERIFIED: WebSearch]`) trip mid-turn → 429; negative owner balance → 402 even on `:free`.

### Anti-Patterns to Avoid

- **`api_key = user_key or owner_key`:** The fail-OPEN one-liner. Bills the owner for every keyless/anon user. Use the explicit three-branch (Pattern 1). `[CITED: PITFALLS.md Pitfall 7]`
- **Caching the LLM client at module scope / `@lru_cache` on a key-bearing function:** Cross-tenant bleed under FastAPI async interleaving. `get_llm_client()` must build fresh per call (it already does — keep it that way). `[CITED: PITFALLS.md Pitfall 8]`
- **`db.table("threads").select("model")` before P13:** Raises Postgres `42703`. Read `model` off the existing `SELECT *` row instead (Pattern 2).
- **`yield {"error": str(e)}` unscrubbed:** `str(e)` from an OpenRouter SDK error can echo the key. Always route through `scrub_secrets()` (D-11).
- **`return` on `finish_reason == "tool_calls"`:** Discards the trailing usage chunk. Drain to stream end (Pattern 4).
- **Leaving `wrap_openai` on for user-key calls:** Ships the user's key + full prompt to LangSmith. Gate at construction (Pattern 3). `[CITED: PITFALLS.md Pitfall 1]`

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Decrypt the stored key | Custom Fernet/AES handling | `crypto_service.decrypt_key()` (Phase 9, MultiFernet) | `[VERIFIED: backend/services/crypto_service.py]` Handles multi-key rotation decrypt; reads secret at call time. |
| 402 vs 429 classification | Parse error strings / status from `str(e)` | `openai.RateLimitError` + `openai.APIStatusError.status_code` | `[VERIFIED: github.com/openai/openai-python]` Typed exceptions; string-parsing is brittle and risks leaking the key into the parse. |
| Streaming usage extraction | Re-compute cost = price × tokens | OpenRouter's automatic `usage` object on the last chunk (incl. `cost`) | `[CITED: openrouter.ai/docs/cookbook/administration/usage-accounting + PITFALLS.md Pitfall 12]` Local recompute drifts from real billing (native tokenizer, caching, BYOK provider deltas). |
| Per-request client isolation | A custom client pool keyed by user | A fresh `OpenAI(...)` per `get_llm_client()` call (status quo) | `[VERIFIED: llm_service.py]` FastAPI request scope already isolates; building fresh is correct and simplest (SEC-04). |
| Secret scrub regex | A new bespoke matcher | Mirror the shipped frontend regex `sk-or-v1-[A-Za-z0-9_-]+` (broaden to `sk-or-[A-Za-z0-9_-]+` per D-11) | `[VERIFIED: frontend/src/lib/sentry.ts:31]` One regex, consistent across FE/BE. |
| Token budget context-length | Hardcode per model | `budget_service.fetch_model_context_length(model, api_key)` (switch to resolved values) | `[VERIFIED: budget_service.py:83]` Already exists; just feed it the resolved key+model. |

**Key insight:** This phase touches secret-custody and concurrency — the two areas where hand-rolling is most dangerous. Every primitive (decrypt, typed errors, usage object, per-request client, scrub regex) already exists in the codebase or the SDK. The work is wiring, not building.

## Runtime State Inventory

> This is a code-seam modification, not a rename/refactor. The five categories are answered for completeness; most are N/A.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | `user_api_keys` rows (Phase 10, dev): ciphertext + `key_label` + `connected_at`, PK=`user_id`. P11 READS these (decrypt path, first exercised). `messages` rows gain a new nullable usage column. | Code edit (read path) + data migration is **additive nullable** (no backfill — old messages keep `usage = NULL`; Phase 14 tolerates null). |
| Live service config | LangSmith prod project — currently traces ALL chat calls (owner key today). After P11, user-key calls must STOP appearing. No config lives in git; it's the `wrap_openai` gate in code. | Code edit (D-10 gate). **Validate against the prod LangSmith project during planning** (STATE.md Phase 11 research flag) — confirm no user-key run appears post-gate. |
| OS-registered state | None. No Task Scheduler / pm2 / systemd state embeds key or model. | None — verified by absence in repo + STATE.md. |
| Secrets / env vars | NEW env vars: `DEMO_FALLBACK_ENABLED` (default off), `DEMO_FALLBACK_MODEL` (default `:free` slug). `KEY_ENCRYPTION_SECRET` (Phase 9) is READ via `decrypt_key()` — name unchanged. Dual-env: dev `.env`, prod `.env.prod` (separate `KEY_ENCRYPTION_SECRET` per env). | Add two config fields (code) + document env vars. `demo_fallback_enabled` stays OFF in BOTH dev and prod this phase (D-09; prod enable is Phase 15). |
| Build artifacts | None. No compiled artifact embeds the key/model. | None. |

**Migration ordering note:** The new `messages` usage column (migration **029**) is independent of the absent P13 schema (`thread.model`, `user_preferences`). P11 creates ZERO P13 schema (D-03) — the three-tier resolver tolerates their absence and lights up when P13 ships. No migration-ordering coupling.

## Common Pitfalls

### Pitfall 1: Budget lookup still uses the owner key after BYOK lands
**What goes wrong:** `chat.py:590` calls `fetch_model_context_length(settings.llm_model, settings.resolved_llm_api_key)`. If left unchanged, the context-length probe hits OpenRouter with the OWNER key and the OWNER's default model while the actual turn runs on the user's key+model — wrong context window, and an owner-key request attributed to a user turn.
**Why it happens:** It's a second, easy-to-miss read of `settings.resolved_llm_api_key` outside `llm_service` (Pitfall 8 in milestone research explicitly calls this out).
**How to avoid:** Switch line 590–591 to `fetch_model_context_length(model, api_key)` using the resolved values from the resolution block. The block must run BEFORE the budget build (it does — budget build is ~line 582, resolution slots in just before it).
**Warning signs:** Budget log line `"Using dynamic context length … for {settings.llm_model}"` shows the owner default model when a user picked a different one.

### Pitfall 2: `str(e)` leaks the key into SSE/log before the scrub is wired
**What goes wrong:** chat.py:907 `yield {"event":"error","data": json.dumps({"error": str(e)})}` and the many `logger.error(..., exc_info=True)` calls. An OpenRouter/OpenAI SDK error string, or a stack-local in `exc_info`, can contain `sk-or-…`.
**Why it happens:** The v1.1 error path predates BYOK; `str(e)` was harmless when the only key was the owner's env key.
**How to avoid:** Route every `str(e)` that reaches SSE or a log through `scrub_secrets()` (D-11). For `logger.error(..., exc_info=True)`, a log filter that scrubs the formatted record is the most thorough (stack frames can hold the key in locals); at minimum scrub the message string. The structured 402/429 events (Pattern 5) use FIXED copy with no `str(e)` — preferred.
**Warning signs:** Grep your own logs/Sentry for `sk-or`. Any 500 SSE error whose payload contains a long token.

### Pitfall 3: Demo fallback fires when it shouldn't (fail-open regression)
**What goes wrong:** A refactor collapses the three branches back to `user_key or owner_key`, or the `elif settings.demo_fallback_enabled` check is dropped, so keyless/anon users silently bill the owner.
**Why it happens:** Fail-open "just works" in a demo and looks friendlier.
**How to avoid:** The `else: refuse` branch is mandatory and tested (a keyless user with the flag OFF must get `no_api_key`, never a completion). `demo_fallback_enabled` defaults OFF in dev AND prod this phase (D-09). Test asserts: flag OFF + no key → `no_api_key` SSE error AND no LLM call made.
**Warning signs:** Owner OpenRouter spend rises with the flag off; an anon user gets a full chat response with no key connected.

### Pitfall 4: Aux call sites silently keep using the owner key/model
**What goes wrong:** `rerank_service`, `subagent_service`, `explorer_service` each call `get_llm_client()` (no args) and read `settings.llm_model`. If only `stream_chat_completion` is threaded, the user pays for the main completion but the OWNER subsidizes rerank/sub-agents — a partial, invisible leak that defeats D-01.
**Why it happens:** Three separate files, each with its own `get_llm_client()` and `settings.llm_model` reads (rerank_service.py:22,29; subagent_service.py:137,140; explorer_service.py:218,237,138).
**How to avoid:** Thread `api_key` + `model` into all three service entry points and every internal `client.chat.completions.create(model=…)` call within them. `chat.py` passes the resolved values when dispatching `explore_kb` / `analyze_document` / and into `execute_tool` (which calls `search_documents` → `rerank`). Grep for `settings.llm_model` and `get_llm_client(` across the four files to confirm zero unthreaded sites remain.
**Warning signs:** A test that asserts the user key reaches rerank/subagent/explorer fails; owner-key spend during a BYOK user's tool-heavy turn.

### Pitfall 5: `maybe_single()` on an absent key row raises instead of returning None
**What goes wrong:** supabase-py `.maybe_single()` historically could raise on zero rows in some versions; the resolution must treat "no key row" as the demo/refuse path, not an exception.
**Why it happens:** The existing code uses `.maybe_single()` for the thread check (chat.py:486) and keys status (keys.py:84) successfully, so the pattern is proven in this version (2.13.0) — but the resolution block adds a new call site that MUST handle the empty case as the fail-closed branch.
**How to avoid:** `if key_row and key_row.data:` — both guards. The Phase 10 `keys.py status` handler already uses exactly `if not row or not row.data:` — mirror it.
**Warning signs:** A keyless user gets a 500 instead of a clean `no_api_key` refusal.

## Code Examples

### Example 1: Structured SSE error helper (scrubbed) — D-11/D-12
```python
# chat.py — reused by the no_api_key, rate_limit, payment_required paths
# Source: synthesized from chat.py:905-908 (existing error event) + sentry.ts:31 regex + D-11
import re
_OR_KEY = re.compile(r"sk-or-[A-Za-z0-9_-]+")
def scrub_secrets(s: str) -> str:
    return _OR_KEY.sub("[redacted-key]", s) if isinstance(s, str) else s

def _sse_error(code: str, detail: str) -> dict:
    # detail is FIXED copy (no str(e)); scrub anyway as defense-in-depth.
    return {"event": "error", "data": json.dumps({"error": code, "detail": scrub_secrets(detail)})}
```
The frontend `useChat.ts` already throws on `parsed.error !== undefined` (line 192) → existing error bubble + toast. `error === "no_api_key"` is the special-case the FE will render as a Connect CTA (FE special-casing is light-touch this phase; the in-band path already exists). `[VERIFIED: frontend/src/hooks/useChat.ts:192-197]`

### Example 2: Existing fresh-client construction proves no SEC-04 singleton exists
```python
# llm_service.py:11-20 (CURRENT) — a fresh OpenAI(...) every call, no module global, no cache.
# This is WHY SEC-04 is an additive change, not a singleton-removal refactor.
def get_llm_client() -> OpenAI:
    settings = get_settings()
    client = OpenAI(api_key=settings.resolved_llm_api_key, base_url=settings.llm_base_url)
    if wrap_openai and settings.langsmith_api_key:
        client = wrap_openai(client)
    return client
```
`[VERIFIED: backend/services/llm_service.py]` No `_client = None` global, no `@lru_cache` on this function. The only cache is `@lru_cache get_settings()` (config.py:147) — owner/global config, correctly cacheable; the per-request key+model are NEVER cached there.

### Example 3: Mirror the proven empty-row guard for fail-closed
```python
# keys.py:87 (Phase 10, PROVEN) — mirror this exact guard shape in the resolution block.
row = get_supabase().table("user_api_keys").select("key_label, connected_at") \
        .eq("user_id", user_id).maybe_single().execute()
if not row or not row.data:
    return {"connected": False}
```
`[VERIFIED: backend/routers/keys.py:79-93]`

### Example 4: Frontend Sentry scrub already shipped — mirror its regex on the backend
```typescript
// frontend/src/lib/sentry.ts:31 (Phase 10, SHIPPED)
const OR_KEY = /sk-or-v1-[A-Za-z0-9_-]+/g
```
`[VERIFIED: frontend/src/lib/sentry.ts:31]` Backend uses the broader `sk-or-[A-Za-z0-9_-]+` per D-11 (catches `sk-or-v1-…` and any future `sk-or-` prefix).

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `stream_options:{include_usage:true}` / `usage:{include:true}` to opt into streaming usage | Usage is **automatic** in the last SSE chunk; those params are deprecated no-ops | OpenRouter "Live Usage Accounting" rollout | `[VERIFIED: openrouter.ai/docs/cookbook/administration/usage-accounting]` Do NOT add `stream_options` — just drain the stream and read `chunk.usage`. Saves a request param and avoids the LiteLLM tool-def token-count bug surface. |
| Owner single-key in `settings`, global client | Per-request key+model threaded from `send_message` | This phase | The defining architectural seam of v1.2 BYOK (SEC-04). |
| LangSmith traces every call | Trace gated off for user-key calls | This phase (D-10) | User secrets/prompts stay inside the trust boundary (SEC-01). |

**Deprecated/outdated:**
- `stream_options: {include_usage: true}` for OpenRouter — deprecated no-op; usage is automatic. `[VERIFIED: usage-accounting doc]`
- Treating 402 as catchable via a dedicated SDK exception — there is none; use `APIStatusError.status_code == 402`. `[VERIFIED: openai-python repo]`

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `meta-llama/llama-3.3-70b-instruct:free` is the recommended default `demo_fallback_model` | Stack / D-06 | LOW — verified live 2026-06-22 `[VERIFIED: costgoat free-models list + buldrr guide]`. Free-model roster rotates; executor should re-confirm at build time via `openrouter.ai/models` with the `:free` filter (D-06 already says "executor confirms a current free slug"). `demo_fallback_enabled` is OFF by default so a stale slug cannot bill anyone until Phase 15. |
| A2 | supabase-py 2.13.0 `.maybe_single()` returns `None`/empty `.data` for zero rows rather than raising | Pitfall 5 | LOW — the Phase 10 `keys.py status` handler relies on exactly this and is green in tests. The defensive `if not row or not row.data` guard makes the resolution correct regardless. |
| A3 | An absent `user_preferences` table raises a catchable `APIError` (Postgres 42P01) from supabase-py, swallowed by the try/except | Pattern 2 / D-03 | LOW — `42P01`/`42703` confirmed as the Postgres codes `[VERIFIED: WebSearch supabase docs]`; the broad `except Exception` in `_safe_user_default_model` catches whatever supabase-py raises. The `thread.model` tier avoids the risk entirely by reading off the existing `SELECT *` row (no query). |
| A4 | OpenRouter emits `usage` (incl. `cost`) on the last streamed chunk even when the turn ended in `tool_calls` mid-loop, for EACH iteration's completion | Pattern 4 / D-04 | MEDIUM — usage-on-last-chunk is verified `[CITED: usage-accounting doc]`, but per-iteration behavior in a multi-call tool loop is inferred. Mitigation: accumulate defensively (`usage or {}`), tolerate a missing iteration's usage as `0`, and treat `cost` as the authoritative summed field. Phase 14 renders; a slightly-low sum is non-fatal and beats crashing. |
| A5 | The cleanest LangSmith gate is "do not call `wrap_openai`" at client construction for user keys | Pattern 3 / D-10 | LOW-MEDIUM — matches D-10's own wording and the existing conditional-wrap code. **Must be validated against the prod LangSmith project during planning** (STATE.md flag): confirm zero user-key runs appear after the gate. This is the highest-blast-radius verification. |

**If this table is empty:** It is not — A1–A5 above need executor/planner attention, especially A4 (usage summing) and A5 (prod LangSmith validation).

## Open Questions

1. **Where does the `mode:"demo"` + `usage` signal ride — the `done` event or a dedicated SSE event?**
   - What we know: The `done` event today carries `{message_id, content}` (chat.py:889-895). `useChat.ts` keys on `parsed.message_id` for the done path (line 185).
   - What's unclear: Whether to extend `done` with `mode` + `usage` (one-line FE change) or add a dedicated event.
   - Recommendation: Extend the `done` event payload with optional `mode` and `usage` — minimal FE change, no new event-type handling, and `useChat.ts` already ignores unknown keys on the done branch. Claude's Discretion per CONTEXT D-08.

2. **Should the `sk-or-` scrub be a logging.Filter (covers `exc_info` stack locals) or just inline `scrub_secrets()` at the SSE/log call sites?**
   - What we know: `logger.error(..., exc_info=True)` ships stack frames whose locals could hold the decrypted key (it's a local in the resolution block + passed to `OpenAI(api_key=…)`).
   - What's unclear: Whether a global `logging.Filter` is in scope for P11 or if scrubbing the message string + using fixed structured-error copy is sufficient.
   - Recommendation: Inline `scrub_secrets()` on every `str(e)` reaching SSE/logs PLUS prefer fixed-copy structured errors (no `str(e)`) for the 402/429/no_api_key paths. A `logging.Filter` is the belt-and-suspenders upgrade; flag it for the planner as a small, high-value add. The decrypted key is a short-lived local — minimize its lifetime (decrypt → pass to `OpenAI()` → drop).

3. **Does `decrypt_key()` raise if `KEY_ENCRYPTION_SECRET` is unset, and is that path reachable in P11 tests?**
   - What we know: `crypto_service._multifernet()` raises a clear `RuntimeError` when the secret is empty (crypto_service.py:29).
   - What's unclear: Whether the resolution block should pre-check or let it raise (caught by the chat error path → scrubbed generic error).
   - Recommendation: Let it raise; the existing `except Exception` in `event_generator` catches it and (post-D-11) yields a scrubbed generic error. Tests set `KEY_ENCRYPTION_SECRET` via monkeypatch (test_crypto_service.py already does). No new handling needed.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `openai` SDK | Per-request client, 402/429 exceptions | ✓ | 1.74.0 | — |
| `langsmith` | `wrap_openai` gate | ✓ | 0.3.42 | ImportError fallback already in code (`wrap_openai = None`) |
| `cryptography` (MultiFernet) | `decrypt_key()` | ✓ | 46.0.5 | — |
| `supabase` (python) | service-role read of `user_api_keys`, write `messages.usage` | ✓ | 2.13.0 | — |
| `httpx` | budget context-length lookup | ✓ | (transitive, used directly) | `settings.model_context_length` fallback already in code |
| Supabase dev project (`.env`) | migration 029 apply + `user_api_keys` read | ✓ | — | — |
| `KEY_ENCRYPTION_SECRET` (dev) | decrypt path | ✓ (Phase 9, dev) | — | RuntimeError if unset (clear message) |
| OpenRouter `:free` model availability | `demo_fallback_model` default | ✓ (`meta-llama/llama-3.3-70b-instruct:free` live 2026-06-22) | — | Roster rotates; re-confirm at build. Flag OFF by default makes a stale slug harmless. |
| `pytest` + fixtures | Validation gate | ✓ | (`backend/tests/conftest.py`) | — |

**Missing dependencies with no fallback:** None — every dependency is present.

**Missing dependencies with fallback:** None blocking.

## Validation Architecture

> `workflow.nyquist_validation` is not explicitly false in `.planning/config.json` → section included.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | `pytest` (in-repo; `backend/tests/`, FastAPI `TestClient` + `monkeypatch` + `MagicMock`) |
| Config file | none detected (no `pytest.ini`/`pyproject.toml` `[tool.pytest]`); `conftest.py` does `sys.path.insert` to `backend/` |
| Quick run command | `cd backend && venv\Scripts\python -m pytest tests/test_key_model_resolution.py -x -q` |
| Full suite command | `cd backend && venv\Scripts\python -m pytest tests/ -q` |

> Project rule (CLAUDE.md): Python backend must run in `venv`. On Windows the interpreter is `backend\venv\Scripts\python`.

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DEMO-03 | Keyless user + flag OFF → `no_api_key` SSE error, NO LLM call | unit | `pytest tests/test_key_model_resolution.py::test_no_key_flag_off_refuses -x` | ❌ Wave 0 |
| DEMO-03 | Keyless user + flag ON → owner key + `:free` model + `mode:"demo"` signal | unit | `pytest tests/test_key_model_resolution.py::test_demo_fallback_uses_free_model -x` | ❌ Wave 0 |
| SEC-04 | User-with-key turn uses the DECRYPTED user key (not owner) at all 4 call sites | unit | `pytest tests/test_key_model_resolution.py::test_user_key_threaded_to_all_call_sites -x` | ❌ Wave 0 |
| SEC-04 | Two concurrent resolutions with different users never cross key/model | unit | `pytest tests/test_key_model_resolution.py::test_no_cross_user_bleed -x` | ❌ Wave 0 |
| SEC-04 | `_resolve_key_and_model` never returns `user_key or owner_key` (fail-closed shape) | unit | `pytest tests/test_key_model_resolution.py::test_fail_closed_no_or_fallback -x` | ❌ Wave 0 |
| D-03 | Model resolves to owner default when `thread.model`/`user_preferences` absent (no crash) | unit | `pytest tests/test_key_model_resolution.py::test_model_fallthrough_absent_p13_schema -x` | ❌ Wave 0 |
| SEC-01 | `wrap_openai` NOT applied when `trace=False` (user key); applied for owner/demo | unit | `pytest tests/test_langsmith_gate.py::test_user_key_client_not_wrapped -x` | ❌ Wave 0 |
| SEC-01 | `str(e)` containing `sk-or-…` is scrubbed before SSE/log | unit | `pytest tests/test_error_surfacing.py::test_sk_or_scrubbed_in_sse_error -x` | ❌ Wave 0 |
| D-12 | 429 → `rate_limit` code; 402 → `payment_required` code (distinct) | unit | `pytest tests/test_error_surfacing.py::test_429_402_distinct_codes -x` | ❌ Wave 0 |
| D-04 | Trailing `usage` captured (not discarded on `tool_calls`) + summed across iterations | unit | `pytest tests/test_usage_capture.py::test_usage_summed_across_tool_loop -x` | ❌ Wave 0 |
| D-04 | `usage` persisted to the new `messages` column on `done` | unit | `pytest tests/test_usage_capture.py::test_usage_persisted_to_messages -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** the matching `pytest tests/test_<file>.py -x -q` (sub-second; mocked LLM + DB)
- **Per wave merge:** `cd backend && venv\Scripts\python -m pytest tests/ -q` (full backend suite)
- **Phase gate:** Full suite green + manual prod-LangSmith validation (A5/D-10) before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_key_model_resolution.py` — covers DEMO-03, SEC-04, D-03 (resolution helper + fail-closed + no-bleed + model fallthrough)
- [ ] `tests/test_langsmith_gate.py` — covers SEC-01 (D-10 wrap gate)
- [ ] `tests/test_error_surfacing.py` — covers SEC-01 (D-11 scrub) + D-12 (402/429)
- [ ] `tests/test_usage_capture.py` — covers D-04 (drain + sum + persist)
- [ ] Extend `conftest.py` `mock_stream_chat_completion` to optionally emit a trailing `{"type":"usage","usage":{…}}` event (the fixture today emits `system_content`/`tool_call`/`text_delta` only — add usage support for D-04 tests)
- [ ] Config tests: extend `tests/test_config.py` with `demo_fallback_enabled` default-False + env-override, `demo_fallback_model` default-slug + env-override (mirrors existing `key_encryption_secret` tests at test_config.py:35-47)

*(Framework install: none — pytest + fixtures already present and green.)*

## Security Domain

> `security_enforcement` not explicitly `false` → section included. This phase IS a security phase (SEC-01, SEC-04).

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | User bound to JWT `sub` via `Depends(get_user_id)` (existing); the resolution reads `user_api_keys` by that `user_id` only — key is bound to the authenticated user, never a request-body value. |
| V3 Session Management | no | No new session state; stateless completions (CLAUDE.md). |
| V4 Access Control | yes | `user_api_keys` read via service-role client; RLS + REVOKE (Phase 9) keep the Text-to-SQL tool out of the table — DO NOT undo. Resolution reads only the calling user's row. |
| V5 Input Validation | yes (light) | `body.model` (future override) must be treated as untrusted — but P11 resolves to owner default regardless; no model string is executed as code. PostgREST queries are parameterized via supabase-py. |
| V6 Cryptography | yes | NEVER hand-roll — `crypto_service.decrypt_key()` (MultiFernet, Phase 9). Decrypt in-memory, per request, drop immediately. |
| V7 Error Handling & Logging | yes | `sk-or-` scrub before every log line + SSE-error payload (D-11); fixed-copy structured errors (no `str(e)`) for 402/429/no_api_key. LangSmith gate (D-10). |
| V9 Data Protection | yes | Decrypted key is a short-lived local; never persisted, never returned, never traced for user keys, never logged. |

### Known Threat Patterns for {FastAPI + OpenRouter BYOK + LangSmith/Sentry}

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| User key exfiltrated to LangSmith via `wrap_openai` | Information Disclosure | Gate the wrapper OFF at client construction for user-key calls (D-10). `[CITED: PITFALLS.md Pitfall 1]` |
| User key in SSE-error payload / backend log via `str(e)` | Information Disclosure | `sk-or-` regex scrub before any log/SSE payload; fixed-copy structured errors (D-11). `[CITED: PITFALLS.md Pitfall 2]` |
| Cross-user key/model bleed under async interleaving | Tampering / Information Disclosure | Per-request key+model parameters; no module-level client singleton; no `@lru_cache` on key-bearing fns (SEC-04). `[CITED: PITFALLS.md Pitfall 8]` |
| Fail-open owner-key fallback bills owner for anon abuse | Denial of Service (cost) / Elevation | Fail-closed three-branch; `demo_fallback_enabled` default OFF; demo pinned to `:free` model (cost bounded structurally). `[CITED: PITFALLS.md Pitfall 7]` |
| Decrypted key lingers in memory / stack locals | Information Disclosure | Minimize lifetime (decrypt → `OpenAI()` → drop); scrub `exc_info`; never put it in a closure that outlives the turn. |
| Free-model 429/402 surfaced as generic error masks limit | (UX/availability, not strictly STRIDE) | Distinct `rate_limit`/`payment_required` codes (D-12). `[CITED: PITFALLS.md Pitfall 11]` |

## Sources

### Primary (HIGH confidence)
- Existing codebase (read directly 2026-06-22): `backend/services/llm_service.py`, `backend/routers/chat.py`, `backend/config.py`, `backend/services/rerank_service.py`, `backend/services/subagent_service.py`, `backend/services/explorer_service.py`, `backend/services/budget_service.py`, `backend/services/crypto_service.py`, `backend/services/tracing.py`, `backend/routers/keys.py`, `backend/services/openrouter_service.py`, `frontend/src/hooks/useChat.ts`, `frontend/src/lib/sentry.ts`, `backend/tests/conftest.py`, `backend/tests/test_chat_cap.py`, `backend/tests/test_config.py`, `supabase/migrations/2024030100002[5,8]_*.sql`, `supabase/migrations/20240301000002_create_messages.sql`, `supabase/migrations/20240301000024_add_tools_used_to_messages.sql` — HIGH
- `.planning/research/ARCHITECTURE.md` §"How the Agentic Chat Loop Selects Key + Model", §"Per-request client construction", §"Model resolution order" — HIGH
- `.planning/research/PITFALLS.md` Pitfalls 1, 2, 7, 8, 11, 12 — HIGH
- `.planning/phases/09-…/09-CONTEXT.md`, `.planning/phases/10-…/10-CONTEXT.md`, `.planning/REQUIREMENTS.md`, `.planning/STATE.md` — HIGH
- OpenRouter usage accounting (streaming usage on last chunk; `stream_options`/`usage:{include}` deprecated no-ops; `cost` field): https://openrouter.ai/docs/cookbook/administration/usage-accounting — HIGH
- OpenAI Python SDK exception hierarchy (`APIStatusError` base + `.status_code`; `RateLimitError`=429; no 402 subclass): https://github.com/openai/openai-python — HIGH

### Secondary (MEDIUM confidence)
- OpenRouter free-model roster incl. `meta-llama/llama-3.3-70b-instruct:free` (live 2026-06-22): https://costgoat.com/pricing/openrouter-free-models and https://buldrr.com/openrouter-free-api-keys-free-models-simple-guide/ — MEDIUM (community lists; roster rotates — re-confirm at build via openrouter.ai/models `:free` filter)
- LangSmith conditional tracing / mask inputs-outputs (confirms client-construction gate is the clean approach): https://docs.langchain.com/langsmith/mask-inputs-outputs and https://forum.langchain.com/t/disable-tracing-for-specific-calls/2093 — MEDIUM
- Supabase PostgREST error codes 42703 (undefined_column) / 42P01 (relation does not exist): https://supabase.com/docs/guides/troubleshooting/resolving-42p01-relation-does-not-exist-error-W4_9-V — MEDIUM

### Tertiary (LOW confidence)
- LiteLLM streaming token-count-with-tools inaccuracy report (informs A4 defensive-summing caution, not a load-bearing claim): https://github.com/BerriAI/litellm/issues/16112 — LOW (third-party bug tracker; flagged as a tolerance note only)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all deps present in repo; versions verified; no new packages.
- Architecture (resolution seam, 4 call sites, budget lookup): HIGH — every seam read directly; line numbers confirmed.
- Usage capture mechanics: HIGH on "usage in last chunk, automatic" (verified); MEDIUM on per-iteration summing in the tool loop (inferred — A4, defensive mitigation specified).
- 402/429 detection: HIGH — SDK exception hierarchy verified; catch-order rule confirmed.
- LangSmith gate: HIGH on the mechanism (don't-wrap); MEDIUM on prod-project behavior (A5 — must validate live during planning).
- Pitfalls: HIGH — grounded in this repo's actual code + milestone PITFALLS.md.
- Free-model slug: MEDIUM — verified live today; roster rotates, flag-OFF-by-default neutralizes staleness risk.

**Research date:** 2026-06-22
**Valid until:** 2026-07-22 (stable seam; the one fast-moving item is the `:free` model roster — re-confirm `demo_fallback_model` at build time, ~7-day freshness)

## RESEARCH COMPLETE

**Phase:** 11 - Per-Request Key + Model Resolution (chat-loop seam)
**Confidence:** HIGH

### Key Findings
- **SEC-04 is an additive change, not a refactor:** `get_llm_client()` already builds a fresh `OpenAI(...)` per call with NO module-level singleton and NO `@lru_cache` on any key-bearing function (only on `get_settings()`). The fix is threading `api_key`+`model` params; the cross-user-bleed risk is already structurally avoided.
- **Four call sites must be threaded for D-01:** `stream_chat_completion` (main), `rerank_service:22`, `subagent_service:137`, `explorer_service:218/237/138` each call `get_llm_client()` and read `settings.llm_model` — plus the budget lookup at `chat.py:590` (the easy-to-miss fifth read of the owner key).
- **Usage is automatic on the last chunk:** OpenRouter's `stream_options:{include_usage}`/`usage:{include}` are deprecated no-ops; the fix is removing the `return` on `finish_reason=="tool_calls"` (llm_service.py:148) so the stream drains to the trailing `usage` chunk, then summing across loop iterations.
- **402 has no SDK exception class:** catch `openai.RateLimitError` (429) first, then `openai.APIStatusError` branching on `.status_code == 402` — string-parsing is wrong and risks leaking the key.
- **Defensive P13-schema read:** read `thread.model` off the existing `SELECT *` row (absent key, not a DB error) and wrap the `user_preferences` query in try/except (table raises `42P01` pre-P13). Zero P13 schema created in P11.
- **`meta-llama/llama-3.3-70b-instruct:free`** verified live 2026-06-22 as `demo_fallback_model` default; `demo_fallback_enabled` stays OFF in dev AND prod this phase.

### File Created
`.planning/phases/11-per-request-key-model-resolution-chat-loop-seam/11-RESEARCH.md`

### Confidence Assessment
| Area | Level | Reason |
|------|-------|--------|
| Standard Stack | HIGH | No new deps; all versions verified in-repo. |
| Architecture | HIGH | Every seam + line number read directly. |
| Pitfalls | HIGH | Grounded in actual code + milestone PITFALLS.md. |
| Usage capture | MEDIUM-HIGH | Last-chunk-usage verified; per-iteration summing inferred (A4 mitigation specified). |
| LangSmith gate | MEDIUM-HIGH | Mechanism verified; prod-project behavior must be validated live (A5). |

### Open Questions
- Where the `mode:"demo"`+`usage` signal rides (recommend: extend the `done` event) — Claude's Discretion.
- `sk-or-` scrub as a `logging.Filter` (covers `exc_info` stack locals) vs inline scrub — recommend inline + fixed-copy errors now, Filter as a flagged upgrade.
- Prod LangSmith validation of the `wrap_openai` gate (A5/D-10) — highest-blast-radius; must run during planning.

### Ready for Planning
Research complete. The planner can create PLAN.md files: the seam, the four call sites, the resolution helper, the usage migration (029), the error/scrub/gate work, and the Wave 0 test files are all specified with verified line numbers and confidence levels.
