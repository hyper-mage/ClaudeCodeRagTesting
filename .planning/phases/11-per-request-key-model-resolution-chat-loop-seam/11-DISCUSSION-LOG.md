# Phase 11: Per-Request Key + Model Resolution (chat-loop seam) - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-22
**Phase:** 11-per-request-key-model-resolution-chat-loop-seam
**Areas discussed:** Aux-call key, Aux model, Model tiers vs P13, Usage capture scope, Demo eligibility shape

> Seam shape pre-locked by research + ROADMAP success criteria (NOT discussed — carried as fixed): per-request key+model params; fail-closed `if user_key / elif demo_flag+eligible / else refuse`; `wrap_openai` off for BYOK; backend `sk-or-` scrub; 429≠402; trailing usage capture.

---

## Aux-call key (which key powers rerank + analyze_document + explore_kb)

| Option | Description | Selected |
|--------|-------------|----------|
| All on user key | Thread resolved user key+model through rerank + both sub-agents. User pays whole turn, owner subsidizes nothing. More threading (3 services). | ✓ |
| Main only, aux on owner | Only stream_chat_completion on user key; rerank + sub-agents on owner key — hidden owner cost for BYOK users. | |
| Main + sub-agents, rerank owner | User key for main + explore_kb/analyze_document; LLM rerank stays owner (cheap infra). | |

**User's choice:** All on user key (Recommended)
**Notes:** User pays for their entire turn; no owner subsidy for BYOK; closes the aux-call cost gap research didn't cover. `metadata_service` excluded (ingestion-only).

---

## Aux model (which model for the aux calls)

| Option | Description | Selected |
|--------|-------------|----------|
| Same resolved model | rerank + sub-agents use the same model the turn resolved. One model per turn, simplest. | (partial) |
| Pinned cheap model for aux | Main on resolved model; aux pinned to a cheap config default to bound explorer-loop cost. | (partial) |
| **Other (user free-text)** | Support BOTH — let the user optionally pin aux tasks to a cheaper model, else use one model. | ✓ |

**User's choice:** Other — "allow the user to pin tasks like that to a cheaper model, or use 1 model like in choice 1. I want the user to have options."
**Notes:** Build the seam so aux calls resolve their own model that **defaults to the single resolved turn model** (choice-1 behavior), with an optional **"utility/aux model" override** that pins rerank+sub-agents to a cheaper model when set. P11 builds resolution plumbing + fallthrough only; user-facing override storage + picker UI defer to Phase 13 / 15. User confirmed.

---

## Model tiers vs P13 (resolution before thread.model / user_preferences exist)

| Option | Description | Selected |
|--------|-------------|----------|
| Graceful fallthrough | Full 3-tier function tolerates absent columns/tables; resolves to owner-default now, lights up in P13. Zero P11 schema. | ✓ |
| Add minimal schema now | P11 creates thread.model + user_preferences.default_model (no UI); P13 adds writes/UI. Migration-ordering coupling. | |

**User's choice:** Graceful fallthrough (Recommended)
**Notes:** No P11/P13 schema coupling; seam ships complete, tested against owner-default.

---

## Usage capture scope (boundary with Phase 14 cost display)

| Option | Description | Selected |
|--------|-------------|----------|
| Capture + persist | Capture trailing usage (summed across tool-loop iterations) AND persist to messages usage/cost column. P14 just reads. Adds migration. | ✓ |
| Capture-only plumbing | Capture + log (scrubbed), no DB. P14 owns storage. Not durable until then. | |
| Capture + emit via SSE | Capture + emit on done event, no DB. Frontend could show live; P14 adds persistence. | |

**User's choice:** Capture + persist (Recommended)
**Notes:** No re-plumbing in P14; usage durable from day one; aids owner-key spend debugging. Must read the LAST streamed chunk (today the tool_calls early-return discards it — Pitfall 12).

---

## Demo eligibility shape (who gets owner-key fallback when flag ON)

| Option | Description | Selected |
|--------|-------------|----------|
| Exclude anon demo | Anonymous Try-demo NOT eligible; only signed-up accounts. Closes Pitfall 7 door. | |
| All authenticated eligible | Any JWT incl. anon eligible; frictionless demo, cost rides on SEC-06 guardrail. | (partial) |
| Defer predicate to P15 | P11 builds only user-key + refuse; eligibility entirely in P15. | |
| **Other (user free-text)** | Everyone eligible (like choice 2) BUT owner fallback restricted to FREE models; demo users can connect their own key for paid + pick among free models. | ✓ |

**User's choice:** Other — "demo users get fallback to owner's free models with the ability to connect their openrouter the same as if signed in. So kinda like choice 1 and 2 but the fallback options are only free models." + follow-up: "yes they pick among free models" + "make a note to demo account users that free models are in use and may be slower or less accurate or may have no usage left."
**Notes:** No eligibility narrowing — cost bound comes from the **model** (free = $0 to owner), not from who's eligible. P11 pins owner fallback to ONE configured free slug (`demo_fallback_model`); demo users picking among free models defers to Phase 12 (free tagging) + Phase 15 (free-only picker). Demo users keep the Phase-10 Connect affordance for paid via own key. P11 exposes `mode:"demo"` signal; non-dismissible banner UI = Phase 15. Notice copy captured. Flag stays OFF in dev; prod enable = Phase 15 (gated on SEC-03).

---

## Claude's Discretion

- Resolved-value parameter signatures, `_resolve_key_and_model()` helper shape/location, aux-model override param name, `messages` usage/cost column name(s) + migration filename, `demo_fallback_*` config field names, structured-error code taxonomy, and where the `mode:"demo"` signal rides — planner/executor decide following existing conventions.

## Deferred Ideas

- D-09-A `execute_readonly_query` `SET LOCAL role` (42501) fix — kept deferred (orthogonal to BYOK seam; own RPC-fix plan). User chose "Ready for context" over discussing it.
- User-facing utility/aux-model override storage + picker → Phase 13 / 15.
- Demo users picking among free models (free-only catalog filter) → Phase 12 + 15.
- Non-dismissible demo-mode banner UI → Phase 15.
- Per-message cost display, balance, low-balance warning, settings/key-state UX, mid-chat 401/402/403 recovery → Phase 14.
- Enabling `demo_fallback_enabled` in prod → Phase 15 (gated on SEC-03 / backlog 999.2).
