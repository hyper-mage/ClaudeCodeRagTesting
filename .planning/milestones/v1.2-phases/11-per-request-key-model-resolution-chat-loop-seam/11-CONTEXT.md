# Phase 11: Per-Request Key + Model Resolution (chat-loop seam) - Context

**Gathered:** 2026-06-22
**Status:** Ready for planning

<domain>
## Phase Boundary

Every chat turn resolves the correct key + model **per request** — the user's own decrypted key when connected, a gated owner-key fallback only when explicitly enabled, and a clean fail-closed refusal otherwise — with **no cross-user key bleed** and **no secret leaking into observability** (LangSmith / Sentry / logs / SSE).

**In scope (SEC-04, SEC-01 backend half, DEMO-03):**
- Key + model resolved as **explicit per-request parameters** threaded `send_message` → `stream_chat_completion` → `get_llm_client(api_key=…, model=…)`; every `settings.resolved_llm_api_key` / `settings.llm_model` read converted to the resolved per-request value (incl. the budget `fetch_model_context_length` lookup in `chat.py:~591`).
- **All chat-turn LLM calls run on the resolved user key** — main completion AND `rerank_service`, `analyze_document` (`subagent_service`), `explore_kb` (`explorer_service`). (`metadata_service` = ingestion-only, NOT a chat-turn call → unchanged.)
- Fail-closed resolution: `if user_has_key → user key + resolved model; elif demo_flag_on (+eligible) → owner key + free model; else → refuse with structured no_api_key SSE error`. NEVER `user_key or owner_key`.
- Three-tier **model** resolution (`thread.model` → `user_preferences.default_model` → owner default) implemented as a function that **tolerates absent P13 schema** and resolves to owner default until Phase 13 lights up the tiers.
- **SEC-01 backend half:** `wrap_openai` gated OFF for per-user-key calls; a `sk-or-` regex scrub runs before any log / SSE-error payload.
- OpenRouter **429 (rate-limit) vs 402 (payment)** surfaced distinctly, not folded into the generic error.
- Trailing **`usage` object captured** on the terminal non-tool-call turn (summed across tool-loop iterations) and **persisted** to a `messages` usage/cost column.

**Out of scope (later phases):**
- Per-message cost display, balance (`GET /api/keys/balance`), low-balance warning, settings/key-state UX, mid-chat 401/402/403 recovery — **Phase 14** (COST-*, PREF-01).
- Model catalog / free-paid tagging / picker — **Phase 12 / 15**.
- `thread.model` column, `user_preferences` table, theme, per-thread model UI/persistence — **Phase 13** (MODEL-05/06, PREF-02).
- Demo-mode banner UI + demo users **picking among** free models + enabling the demo flag in prod — **Phase 15** (DEMO-01/02, gated on SEC-03 / backlog 999.2).
- D-09-A `execute_readonly_query` `SET LOCAL role` RPC fix — stays deferred (separate plan; orthogonal to the BYOK seam).

</domain>

<decisions>
## Implementation Decisions

### Auxiliary chat-turn LLM calls — key + model (SEC-04)
- **D-01:** **All LLM calls within a chat turn run on the resolved user key** — not just `stream_chat_completion`, but also `rerank_service` (LLM rerank), `subagent_service` (`analyze_document`), and `explorer_service` (`explore_kb`'s multi-iteration loop). The user pays for their entire turn; the owner subsidizes nothing for BYOK users. Requires threading the resolved key (and model) into all three services' `get_llm_client()` call sites. (`metadata_service` runs only on ingestion → untouched.)
- **D-02:** **Aux model defaults to the single resolved turn model** (out-of-the-box: one model per turn). BUT the resolution seam is built to support an **optional "utility/aux model" override** — when set, it pins rerank + sub-agents to a cheaper model; when unset, aux falls through to the main resolved model. **P11 builds only the resolution plumbing + fallthrough.** The user-facing override (storage + picker) defers to **Phase 13 (prefs) / Phase 15 (picker)** — it lights up later with zero P11 rework.

### Model-tier resolution vs Phase 13 schema ordering
- **D-03:** **Graceful fallthrough.** P11 writes the full three-tier resolution function (`thread.model` → `user_preferences.default_model` → owner default), but each tier **tolerates absent columns/tables** (Phase 13 adds them). Today it resolves straight to the owner default; it auto-lights-up when P13 ships the schema. **Zero Phase-13 schema is created in P11** — no migration-ordering coupling, no rework in P13. The resolution seam ships complete and is tested against owner-default.

### Usage capture scope (boundary with Phase 14)
- **D-04:** **Capture + persist.** P11 captures the trailing `usage` object (summed across all tool-loop iterations of the turn) AND persists it to a new `messages` usage/cost column (adds a small migration). **Phase 14 only reads + renders.** No re-plumbing in P14, usage durable from day one, also aids debugging owner-key spend. Capture must read the **last** streamed chunk (today `stream_chat_completion` returns on `finish_reason == "tool_calls"` and discards the final chunk — see Pitfall 12).

### Demo-fallback shape + eligibility (DEMO-03)
- **D-05:** **Everyone is eligible** for the owner-key fallback when the flag is ON — including anonymous Try-demo users. There is **no eligibility narrowing**; the cost bound comes from the **model**, not from who's eligible.
- **D-06:** Owner-key fallback is **pinned to a free model.** Free models are $0 to the owner, so spend is bounded structurally. P11 pins to **one configured free-model slug** via a new `demo_fallback_model` config value (env-driven; default a known free slug, e.g. `meta-llama/llama-3.3-70b-instruct:free` — executor confirms a current free slug). Demo users **picking among** free models defers to Phase 12 catalog + Phase 15 free-only picker.
- **D-07:** Demo users retain the **Connect-OpenRouter** affordance (already built in Phase 10) — connecting their own key unlocks paid models exactly like a signed-in user.
- **D-08:** **Demo-mode signal exposed in P11** — the resolution emits a `mode: "demo"` (+ free-tier) indicator on the response/SSE so downstream can render a notice. **Notice copy:** "Demo mode — a free model is in use; it may be slower, less accurate, or temporarily rate-limited (no usage left)." The non-dismissible **banner UI** itself is Phase 15 (DEMO-01/02); P11 only guarantees the signal exists.
- **D-09:** `demo_fallback_enabled: bool = False` — new in `config.py`, env-driven, **OFF by default** (incl. dev). The fail-closed three-branch shape (`if user_key / elif demo_flag_on / else refuse`) is fully built + testable now; **enabling the flag in prod is Phase 15**, hard-gated on SEC-03 / backlog 999.2.

### Observability scrub (SEC-01 backend half)
- **D-10:** `wrap_openai` is **gated OFF for per-user-key calls** — build the client without the LangSmith wrapper when the key source is a user key (Pitfall 1). Owner-key/demo calls may still trace. Validate the disable-wrapper approach against the **prod LangSmith project** during planning (STATE.md Phase 11 research flag).
- **D-11:** A `sk-or-[A-Za-z0-9_-]+` regex scrub runs **before any log line OR SSE-error payload** in the backend. Today the SSE error path yields `{"error": str(e)}` (`chat.py:~907`) — `str(e)` can contain a leaked key; it MUST be scrubbed. Mirrors the frontend Sentry rule already shipped in Phase 10.

### Error surfacing (Pitfall 11)
- **D-12:** OpenRouter **429 vs 402** detected distinctly and surfaced as tailored structured SSE errors (rate-limit vs payment/credit), NOT folded into the generic `[An error occurred]`. Matters acutely for free-model demo users (free models hit per-minute caps + 402 on negative owner balance). Structured `no_api_key` error reuses the existing in-band error path `useChat.ts` already handles.

### Claude's Discretion
- Exact resolved-value parameter signatures (`get_llm_client(api_key=…, model=…)`, `stream_chat_completion(..., api_key=…, model=…)`), the `_resolve_key_and_model()` helper shape/location, the aux-model override parameter name, the `messages` usage/cost column name(s) + migration filename (next free number), the `demo_fallback_model` / `demo_fallback_enabled` config field names, structured-error code taxonomy (`no_api_key` / `rate_limit` / `payment_required` etc.), and where the `mode:"demo"` signal rides (done event vs a dedicated SSE event) — planner/executor decide, following existing conventions.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope & requirements
- `.planning/ROADMAP.md` — Phase 11 entry (goal, 4 success criteria, depends-on Phases 9 + 10)
- `.planning/REQUIREMENTS.md` — SEC-04, SEC-01, DEMO-03 (definitions + traceability); SEC-01 cross-cutting note (backend half enforced here)

### Research (milestone-level, milestone-aware)
- `.planning/research/ARCHITECTURE.md` §"How the Agentic Chat Loop Selects Key + Model (MODIFIED chat.py)" (lines ~334–398, resolution-block pseudocode) + §"Per-request client construction (MODIFIED llm_service.py)" (lines ~220–240) + §"Model resolution order" (lines ~182–184)
- `.planning/research/PITFALLS.md` — **Pitfall 1** (LangSmith `wrap_openai` traces per-user key — gate the wrapper), **Pitfall 2** (backend log/SSE `sk-or` scrub), **Pitfall 7** (demo/owner fallback cost blowout — fail-closed shape), **Pitfall 8** (cross-user / cached-singleton leakage — per-request params), **Pitfall 11** (429 vs 402 distinct surfacing), **Pitfall 12** (usage capture from final streamed chunk)
- `.planning/research/SUMMARY.md` — milestone synthesis / build order (Phases 1→2→3 critical path)

### Phase 9 + 10 foundations (what this phase consumes)
- `.planning/phases/09-crypto-encrypted-key-storage-foundation/09-CONTEXT.md` — `crypto_service` API (`decrypt_key()` is the decrypt path this phase exercises), `user_api_keys` table shape, SQL-tool lockdown (do NOT undo)
- `.planning/phases/10-oauth-pkce-backend-exchange-frontend-connect/10-CONTEXT.md` — connected-key shape (`user_api_keys` row: ciphertext + `key_version` + masked label + `connected_at`), `GET /api/keys/status`, exchange/upsert
- `.planning/phases/09-crypto-encrypted-key-storage-foundation/deferred-items.md` — **D-09-A** (`execute_readonly_query` `SET LOCAL role` 42501 on dev — tagged for P11 triage; this phase keeps it DEFERRED, see Deferred Ideas)
- `.planning/phases/09-crypto-encrypted-key-storage-foundation/KEY-ROTATION-RUNBOOK.md` — MultiFernet decrypt semantics behind `decrypt_key()`

### Code to modify / mirror
- `backend/services/llm_service.py` — `get_llm_client()` (line 11, add `api_key`/`model` params + `wrap_openai` gate at lines 18–19) and `stream_chat_completion()` (line 35, add `api_key`/`model` params; capture trailing chunk — the `finish_reason == "tool_calls"` early return at line 148 drops the final usage chunk)
- `backend/routers/chat.py` — `send_message` / `event_generator` (resolution block slots in before budget build ~line 581); convert `settings.resolved_llm_api_key` + `settings.llm_model` at lines 591/596; the agentic loop (lines ~616–882); the SSE `error` event at lines ~905–907 (scrub `str(e)`); the `done` event ~889 (usage)
- `backend/config.py` — `Settings` + `resolved_llm_api_key`/`llm_model` (lines 46, 135); add `demo_fallback_enabled` + `demo_fallback_model`; dual-env via `ENV_FILE`
- `backend/services/rerank_service.py` (line 22) / `backend/services/subagent_service.py` (line 137) / `backend/services/explorer_service.py` (lines 218, 136/238) — `get_llm_client()` + `settings.llm_model` call sites to thread the resolved key+model (D-01)
- `backend/services/crypto_service.py` (Phase 9) — `decrypt_key()` consumed in the resolution block
- `backend/database.py` — service-role `get_supabase()` (read `user_api_keys`, write usage to `messages`)
- `backend/services/tracing.py` — LangSmith wiring context for the `wrap_openai` gate (D-10)
- `frontend/src/hooks/useChat.ts` — existing in-band error handling (`parsed.error !== undefined`) that consumes `no_api_key` / `rate_limit` / `payment_required` and the `mode:"demo"` signal
- `frontend/src/lib/sentry.ts` — the frontend `sk-or-` scrub already shipped in Phase 10 (mirror its regex on the backend)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`crypto_service.decrypt_key()` (Phase 9)** — the decrypt path, exercised for the first time this phase (Phases 9/10 only encrypted + wrote). In-memory, per-request only.
- **`user_api_keys` row (Phase 10, dev)** — PK `user_id`, ciphertext + `key_version` + masked label + `connected_at`; read via service-role client in the resolution block.
- **`get_llm_client()` / `stream_chat_completion()` (`llm_service.py`)** — the exact seam; today both read global `settings`. Minimal, stable surface → extend with explicit params, don't rewrite.
- **Existing in-band SSE error path** — `useChat.ts` already throws on `parsed.error !== undefined` → error bubble + toast; `no_api_key` just special-cases the CTA. No new SSE plumbing needed for the refuse path.
- **`@lru_cache get_settings()`** — keep for owner/global config; the per-request key+model must NOT be cached here (Pitfall 8 — cached-singleton = cross-tenant bug).

### Established Patterns
- Backend touches `user_api_keys` via the **service-role client** (bypasses RLS); frontend never reads it. RLS + REVOKE + FROM-allowlist (Phase 9) stay intact — don't undo.
- Migrations sequentially numbered `20240301000NNN_*.sql`; next free number for the `messages` usage column (executor checks the latest applied — Phase 10 reached 028).
- Dual Supabase envs — dev (`.env`) for iteration; prod (`.env.prod`) at deploy. Separate `KEY_ENCRYPTION_SECRET` per env. See [[project_dual_supabase_envs]].
- Agentic tool-loop (`chat.py`) counter-bounded at `chat_max_iterations` (15) — each iteration is an LLM call on the resolved key; amplifies request count per user turn (relevant to free-model 429 caps, Pitfall 11).

### Integration Points
- Resolution block (`chat.py`) → `crypto_service.decrypt_key()` (user key) → threads key+model into `stream_chat_completion` + `rerank_service` + `subagent_service` + `explorer_service`.
- `get_llm_client(api_key=…)` → `wrap_openai` gate (LangSmith) keyed on key-source (user vs owner/demo).
- Resolution → `messages` usage/cost column (persist) ← Phase 14 reads.
- Resolution `demo_flag_on` branch → `settings.demo_fallback_model` (free slug) ← Phase 12 catalog / Phase 15 picker extend later.

</code_context>

<specifics>
## Specific Ideas

- Demo notice copy: "Demo mode — a free model is in use; it may be slower, less accurate, or temporarily rate-limited (no usage left)." (Banner UI = Phase 15; signal = P11.)
- Fail-closed resolution is explicitly three-branch (`if user_key / elif demo_flag_on / else refuse`) — never the `user_key or owner_key` one-liner (Pitfall 7).
- Default `demo_fallback_model` = a current OpenRouter **free** slug (`…:free` convention); executor confirms one that's live at build time.
- Aux/utility-model override is plumbing-only this phase — defaults to the single resolved model so behavior is "one model per turn" until P13/P15 surface the override.
- Usage must be read from the **last** streamed SSE chunk — restructure the `finish_reason == "tool_calls"` early-return so the final chunk's `usage` is not discarded (Pitfall 12).

</specifics>

<deferred>
## Deferred Ideas

- **D-09-A — `execute_readonly_query` `SET LOCAL role` (42501) fix** — tagged "triage in Phase 11" but kept DEFERRED here: orthogonal to the key/model seam (it's the RLS-context strategy inside a `SECURITY DEFINER` RPC, breaking Text-to-SQL *execution* on dev). Belongs in its own RPC-fix plan; verify the same probe against prod at deploy. See `.planning/phases/09-crypto-encrypted-key-storage-foundation/deferred-items.md`.
- **User-facing "utility/aux model" override** (pick a cheaper model for rerank/sub-agents) — P11 builds the resolution plumbing + fallthrough only; storage + picker UI → **Phase 13 / 15**.
- **Demo users picking among free models** (free-only catalog filter) → **Phase 12** (free/paid tagging) + **Phase 15** (picker).
- **Non-dismissible demo-mode banner UI** → **Phase 15** (DEMO-01/02). P11 ships the `mode:"demo"` signal only.
- **Per-message cost display, balance, low-balance warning, settings/key-state UX, mid-chat 401/402/403 recovery** → **Phase 14**.
- **Enabling `demo_fallback_enabled` in prod** → **Phase 15**, hard-gated on SEC-03 / backlog 999.2 (cost-guardrail trip-test + kill switch).

</deferred>

---

*Phase: 11-per-request-key-model-resolution-chat-loop-seam*
*Context gathered: 2026-06-22*
