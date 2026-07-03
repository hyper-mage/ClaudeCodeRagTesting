# Phase 15: Options UI Capstone + Demo Gating - Research

**Researched:** 2026-07-02
**Domain:** React picker UX (fuzzy search / sections / favorites), OAuth-gated model selection with resume, demo-fallback enablement (FastAPI + Supabase + OpenRouter)
**Confidence:** HIGH — every integration seam was read from live code this session; the two external dependencies (OpenRouter demo-slug liveness, PostgREST array columns) were verified against live sources.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### Key-gated selection (KEY-05)
- **D-01:** Keyless user picks a **paid** model → **confirm modal, then OAuth**: small dialog ("Paid models need your OpenRouter key") with [Connect] launching the existing `startOpenRouterConnect()` PKCE helper and [Cancel] keeping the current model. Reuses the `ConfirmDialog` pattern. No instant redirect, no disabled/locked rows.
- **D-02:** **Auto-apply after connect.** The pending model selection is stashed in `sessionStorage` beside the PKCE verifier/state; after a successful exchange the originating surface's action is applied (thread PATCH or default-model PUT) + a small confirmation toast. The user's original intent completes without re-picking.
- **D-03:** **Keyless selectable set depends on the demo flag.** Demo ON: free models are selectable (picker filters via the existing, currently-unused `GET /api/models?free_only=true` param) and demo turns run the **picked** free model — this implements the deferred "demo users picking among free models" plan from Phases 11/12. Paid rows → connect modal (D-01). Demo OFF: **every** selection → connect modal (chat is fail-closed anyway).
  - **Server-side guard (non-negotiable):** the demo resolution branch must validate the selected model is actually free against `model_cache` (never trust the frontend); non-free or unknown → fall back to the pinned `demo_fallback_model`. Owner spend stays $0 structurally.
- **D-04:** **Gate applies to BOTH selection surfaces** — thread-header `ModelSelector` and settings `DefaultModelSelector` — via one shared gate hook/util (same modal, same auto-apply resume). No inconsistent keyless UX between chat and settings.

#### Picker upgrade (MODEL-08 + B-1 + W-1)
- **D-05:** **Favorites stored on `user_preferences`** — new `favorite_models` array column (migration 033, next free number). Reuses the existing GET/PUT `/api/preferences` partial-upsert + RLS; no new table, no new endpoint. Read once at picker mount.
- **D-06:** **Sectioned picker: Favorites → Popular → All (alphabetical).** Section headers inside the dropdown; Popular block preserves curated `POPULAR_MODELS` order (`popularity_rank`).
- **D-07:** **Popular marking renders as a "Popular" badge chip on the row** (in addition to the Popular section), mirroring the existing "Free" tag styling at `ModelSelector.tsx:320-323`. This closes audit blocker B-1 (MODEL-03).
- **D-08:** **Search is fuzzy, client-side** over the already-fetched catalog (match on model id + name), debounced input pinned atop the dropdown. Typo-tolerant matching chosen over plain substring. Implementation (hand-rolled subsequence scorer vs a micro-dep like `fuzzysort`) is Claude's discretion — bias to hand-rolled to respect the v1.2 "minimal new FE dep surface" posture. Closes audit W-1 (MODEL-01 "searchable").

#### Demo rollout & banner (DEMO-01/02, SEC-03)
- **D-09:** **Enable `demo_fallback_enabled=true` in prod at this phase's deploy step.** SEC-03 gate is discharged: 999.2 finding PASS (guardrail 403-blocked at $0.1026, kill-switch tests green, no-email outcome accepted). Demo runs free models only (D-03 guard), so structural owner cost is $0. This closes DEMO-01 + SEC-03. Flag stays env-driven (no admin UI — project rule).
- **D-10:** **Banner = slim, non-dismissible strip at the top of the chat pane**, rendered whenever the `mode:"demo"` signal (Phase 11 D-08) is present. Copy is LOCKED from Phase 11: "Demo mode — a free model is in use; it may be slower, less accurate, or temporarily rate-limited (no usage left)." Not a pill, not a header-bar banner.
- **D-11:** **[Use demo] lights up on the 403/no-key error bubble when the flag is ON** — wire the existing dead `demoEligible`/`onUseDemo` props (`ErrorMessageBubble` ← `ChatContainer.tsx:122`) to demo-flag state; clicking retries the turn in demo mode.

### Claude's Discretion
- Fuzzy-match implementation (hand-rolled scorer vs micro-dep) per D-08.
- Exact modal copy/layout, toast copy, section-header styling, badge color token, sessionStorage key names for the pending selection, gate hook naming (`useKeyGate` or similar).
- How the frontend learns the demo flag state (ride `GET /api/keys/status`, a config endpoint, or the `mode` signal) — pick the smallest seam.
- Migration 033 exact shape (TEXT[] vs JSONB) following existing user_preferences conventions.
- Whether the Favorites section shows an empty-state hint or hides when empty.

> Note: the approved 15-UI-SPEC.md has since **resolved** most discretion items and LOCKED them: gate-modal copy, `useKeyGate` name, `or_pending_selection` stash key + JSON shape, `demo_enabled` riding `GET /api/keys/status`, `TEXT[]` recommendation, Favorites hidden-when-empty, hand-rolled fuzzy matcher with a locked ranking spec, and a full picker a11y contract. The UI-SPEC is a canonical input to planning alongside this research.

### Deferred Ideas (OUT OF SCOPE)
- **W-3 (notice dedup + live visibility)** — deprecated-model notice duplicates + invisible during live turn; separate fix, not picker surface (backlog / quick task).
- **FU-A/FU-B/FU-D (Phase 14 follow-ups)** — balance semantics, post-turn balance refresh, light-mode bubble polish; own track.
- **Aux/utility-model override UI** — plumbing exists since P11 D-02; still deferred (no requirement this milestone).
- **MODEL-F1 "New" badge / MODEL-F2 keyboard-heavy picker nav** — Future Requirements (post-v1.2).
- **SEC-01 human gates + prod migration catch-up** — run alongside this phase's deploy, tracked by the audit, not phase-15 build scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| KEY-05 | Selecting a model with no connected key triggers the OAuth connect flow (key-gated) | Pattern 1 (`useKeyGate` decision table), Pattern 2 (pending-selection stash + `OAuthCallbackPage` resume), `ConfirmDialog` variant extension (Code Examples), verified PKCE seam in `pkce.ts:34-45` |
| MODEL-08 | User can favorite/pin models to the top of the picker | Migration 033 `TEXT[]` shape (Code Examples), `preferences.py` GET/PUT extension, star sub-element + Favorites section (Pattern 3), PostgREST array support [VERIFIED] |
| DEMO-01 | Owner can enable/disable an owner-key demo fallback via a global flag (default OFF) | Flag exists at `config.py:37` (default False); enablement = deploy-step Fly secret `DEMO_FALLBACK_ENABLED=true` (Deploy Step pattern); demo branch at `chat.py:196-204` gains the D-03 free-guard |
| DEMO-02 | When demo fallback is active for a user, a clear, non-dismissible "demo mode" banner is shown | `mode:"demo"` already emitted on the done event (`chat.py:1190-1191`, currently unread by FE); banner render condition + `useKeyStatus` `demo_enabled` seam (Pattern 5); banner snippet (Code Examples) |
| SEC-03 | Owner-key cost exposure is bounded before demo fallback is enabled in prod | 999.2 finding PASS (403 block at $0.1026; both kill switches proven); existing killswitch tests in `test_key_model_resolution.py` must stay green; server-side free-guard keeps owner spend structurally $0; deploy note: verify Fly `LLM_API_KEY` is the owner `sk-or…` key before flipping the flag |
| MODEL-03 (fold-in B-1) | Popular models are marked (curated) in the picker — data reaches FE unrendered | `popularity_rank` declared at `ModelSelector.tsx:16`, never rendered; Popular chip mirrors the Free tag at `ModelSelector.tsx:320-323` (Pattern 3) |
| MODEL-01 (fold-in W-1) | User can browse a **searchable** list of models — "searchable" unmet | Hand-rolled fuzzy subsequence scorer (Code Examples), search input pinned in dropdown, flat ranked result list while searching (Pattern 3) |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

Directives that bind this phase's plans:

- **Stack fixed:** React+Vite+Tailwind frontend, Python+FastAPI backend, Supabase. No new frameworks.
- **No LangChain/LangGraph** — raw SDK calls only (untouched this phase).
- **Pydantic for structured outputs / API models** — `MessageCreate`, `PreferencesUpdate`, `KeyStatusResponse` extensions must be Pydantic-validated.
- **RLS on all tables** — `user_preferences` own-row RLS already exists; migration 033 is additive to that table (no new policies needed).
- **SSE streaming for chat** — the `mode:"demo"` signal and `use_demo` override ride the existing SSE plumbing.
- **No admin UI** — `demo_fallback_enabled` stays env-driven only (matches D-09).
- **Python backend uses `backend/venv`** — test commands below use the venv interpreter.
- **Plans → `.agent/plans/`** naming/complexity rules apply if any ad-hoc plan is written outside GSD phase plans (GSD phase plans live in `.planning/phases/15-*/`).
- **GSD workflow enforcement** — execution goes through `/gsd:execute-phase`.
- **House security style (SEC-01):** never interpolate a caught error, HTTP body, or `sk-or-` fragment into UI copy, logs without scrub, or SSE payloads. All new copy is locked strings; `${model}` (display name) is the only interpolation the UI-SPEC allows.
- **Frontend deps minimal** — this phase adds **zero** npm packages (fuzzy matcher hand-rolled per D-08).

## Summary

Phase 15 is a capstone that touches five frontend surfaces and three backend seams, but **every seam already exists and was explicitly left for this phase**: `GET /api/models?free_only=true` shipped in Phase 12 with zero consumers, `demoEligible`/`onUseDemo` are dead props on `ErrorMessageBubble`, the `mode:"demo"` done-event field is emitted but unread, `popularity_rank` reaches the FE interface unrendered, and the demo branch in `_resolve_key_and_model` pins `demo_fallback_model` awaiting the D-03 picked-free-model upgrade. The work is therefore mostly *wiring and extending*, not inventing — the risk concentrates in (a) restructuring `ModelSelector`'s flat listbox into a searchable, sectioned combobox without breaking its locked behaviors, and (b) the resolution-order change in `chat.py` that must preserve the SEC-03 fail-closed posture.

Two external facts were verified live: the pinned demo model `meta-llama/llama-3.3-70b-instruct:free` is currently a live OpenRouter slug with one tool-capable endpoint (Venice, fp8, 65,536 context, ~88% 1-day uptime) [VERIFIED: openrouter.ai endpoints API, 2026-07-02], and PostgREST accepts JSON arrays for `text[]` columns, so `favorite_models TEXT[]` works through the existing supabase-py upsert [VERIFIED: postgrest.org docs]. No new dependencies are needed anywhere — lucide-react 0.577.0 already contains all four new icons (`Search`, `Star`, `KeyRound`, `Info`) [VERIFIED: node_modules].

One stale instruction must be neutralized: STATE.md's pending todo "shadcn init is a Phase 15 prerequisite" was **superseded** by the approved UI-SPEC (`shadcn_initialized: false`, "Do not run `npx shadcn init` in Phase 15"). The picker stays hand-rolled. Plans must not act on the stale todo.

**Primary recommendation:** Structure plans in three build waves — (1) backend seams first (migration 033, preferences/keys/chat.py extensions — all independently testable), (2) picker rebuild (fuzzy util → sectioned/searchable ModelSelector → favorites), (3) gate + resume + demo UX (useKeyGate, ConfirmDialog variant, OAuthCallbackPage resume, banner, [Use demo]) — then a deploy/ops plan (prod migrations 029–033, Fly secrets, flag ON, CF rebuild) as the final human-gated step.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Fuzzy search, sections, Popular chip, star affordance | Browser (React `ModelSelector`) | — | Pure presentation over the already-fetched catalog; catalog is ~400 rows, client-side filtering is trivial |
| Favorites persistence | API (`PUT /api/preferences`) + DB (`user_preferences.favorite_models`) | Browser (optimistic local state) | Per-user data behind own-row RLS; optimistic fire-and-forget PUT is the established house style |
| Key-gate decision (which selection opens the modal) | Browser (`useKeyGate`) | API (send-time resolution re-validates) | Gate is UX only; enforcement is the server's fail-closed resolution — a bypassed gate still cannot spend |
| Pending-selection stash + resume | Browser (`sessionStorage`) | API (thread PATCH / prefs PUT apply) | Must survive the full-page OAuth redirect round-trip; sessionStorage is the proven Phase-10 mechanism |
| Demo eligibility + free-model guard | API (`chat.py _resolve_key_and_model`) | DB (`model_cache.is_free`) | Never trust the frontend (D-03 non-negotiable); owner spend bounded server-side |
| Demo flag exposure to FE | API (`GET /api/keys/status` + `demo_enabled`) | Browser (`useKeyStatus` shared store) | Smallest seam (UI-SPEC resolved); zero new endpoints, zero new fetches |
| Demo banner + [Use demo] retry | Browser (`ChatContainer`, `useChat`, `ErrorMessageBubble`) | API (`mode:"demo"` done signal, `use_demo` body flag) | FE renders server signals; retry override honored server-side only when flag ON |
| Flag enablement (DEMO-01) | Ops (Fly secrets, env-driven) | — | No admin UI (project rule); provider budget guardrail is the cost backstop (999.2) |
| Migration 033 | Database (Supabase migration) | — | Additive column on an RLS'd table; dev first, prod at deploy |

## Standard Stack

**Zero new dependencies.** Everything reuses installed, verified versions.

### Core (existing, verified in package.json / requirements.txt / node_modules)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| react | ^19.2.4 | All five FE surfaces | Installed [VERIFIED: package.json] |
| lucide-react | ^0.577.0 | `Search`, `Star`, `KeyRound`, `Info` (+ existing icons) | All four new icons present in installed package [VERIFIED: node_modules/lucide-react/dist/esm/icons/] |
| tailwindcss | ^4.2.2 | All new styling (CSS-first config, class-strategy dark mode) | Established pattern; UI-SPEC locks exact classes |
| fastapi | 0.115.12 | Router extensions (keys, preferences, chat) | Installed [VERIFIED: requirements.txt via CLAUDE.md stack] |
| pydantic | 2.11.1 | `MessageCreate.use_demo`, `PreferencesUpdate.favorite_models`, `KeyStatusResponse.demo_enabled` | Installed; project rule |
| supabase (py) | 2.13.0 | `model_cache` free-check read; `user_preferences` upsert with array | Installed; PostgREST accepts JSON arrays for `text[]` [VERIFIED: postgrest.org] |
| vitest | ^4.1.9 | FE component/unit tests | Installed; harness from 999.1 [VERIFIED: vitest.config.ts] |
| @testing-library/react + user-event + jest-dom | ^16.3.2 / ^14.6.1 / ^6.9.1 | Picker/gate/banner tests | Installed [VERIFIED: package.json] |
| pytest | (backend venv) | Backend seam tests | Existing suite of 38 test files [VERIFIED: backend/tests/] |

### Supporting (in-repo assets, not packages)
| Asset | Location | Purpose | When to Use |
|-------|----------|---------|-------------|
| `startOpenRouterConnect()` | `frontend/src/lib/pkce.ts:34` | PKCE launch | Called as-is by the gate modal's [Connect] |
| `ConfirmDialog` | `frontend/src/components/ConfirmDialog.tsx` | Gate modal | Extend with `variant?: 'danger' \| 'primary'` (default `'danger'` → zero call-site changes) |
| `useKeyStatus` shared store | `frontend/src/hooks/useKeyStatus.ts` | `connected` + new `demo_enabled` | Gate hook, banner, error bubble all read one store |
| `ToastContext` | `frontend/src/contexts/ToastContext.tsx` | Auto-apply toasts | `success` and `warning` variants already exist; bottom-right, 4s auto-dismiss |
| `model_cache.is_free` | migration 030 / `model_catalog_service._to_cache_row` | Server-side free-guard | Precomputed column — the demo guard is a one-row SELECT, not a recompute |
| `GET /api/models?free_only=true` | `backend/routers/models.py:36` | Server-verified free set | Available as a test aid / guard sibling; NOT a display contract (UI-SPEC resolution) |
| vitest harness | `frontend/src/test/utils.tsx` | `renderWithProviders`, `makeApiMock`, `makeAuthMock`, `mockSSEResponse` | All new FE tests |
| resolution test scaffolding | `backend/tests/test_key_model_resolution.py` | `_fake_settings()`, `_db_with_key_row()` | Extend for free-guard + `use_demo` tests |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Hand-rolled fuzzy scorer (~40 lines) | `fuzzysort` (~5 kB micro-dep) | fuzzysort is battle-tested, but D-08 locks the bias to hand-rolled (minimal-dep posture); UI-SPEC locks the exact ranking so the hand-rolled scorer has a precise spec to test against |
| Hand-rolled combobox extension | shadcn/ui Combobox (cmdk) | **Rejected — LOCKED.** UI-SPEC gate result: `Tool: none`; initializing shadcn to use none of its components adds dead dependency surface. The stale STATE.md todo saying otherwise is superseded |
| `TEXT[] NOT NULL DEFAULT '{}'` | `JSONB` | TEXT[] matches "array of slugs" semantics and the plain-TEXT non-FK convention of `default_model`; JSONB adds no value for a string list. UI-SPEC recommends TEXT[]; final call is the planner's (D-05 discretion) |
| `demo_enabled` on `GET /api/keys/status` | New `/api/config` endpoint | Status ride-along is the smallest seam (UI-SPEC resolved): zero new endpoints, and every consumer (gate, banner, bubble) already reads the shared `useKeyStatus` store |

**Installation:** none. `npm install` / `pip install` steps are not required for this phase.

## Architecture Patterns

### System Architecture Diagram

```
SELECTION FLOW (KEY-05, D-01/02/04)
                                        ┌────────────────────────────────────────────┐
  Thread header ─ ModelSelector ──┐     │ useKeyGate(onApply)                        │
  (ChatPage → ChatContainer)      ├────▶│  reads useKeyStatus: {connected,           │
  Settings ─ DefaultModelSelector ┘     │  demo_enabled}                             │
  (SettingsPage)                        │  connected ────────────────▶ apply now     │──▶ PATCH /api/threads/{id} {model}
                                        │  keyless+demoON+is_free ───▶ apply now     │    or PUT /api/preferences {default_model}
                                        │  keyless+demoON+paid ──┐                   │
                                        │  keyless+demoOFF ──────┤                   │
                                        └────────────────────────┼───────────────────┘
                                                                 ▼
                                    ConfirmDialog variant='primary' ("Connect OpenRouter?")
                                        [Cancel] → close, selection unchanged
                                        [Connect] → sessionStorage.or_pending_selection = {kind, modelId, threadId?, returnTo}
                                                  → startOpenRouterConnect()  (writes or_pkce_verifier/state, full-page redirect)
                                                                 │
                     openrouter.ai/auth ─── user approves ───────┘
                                                                 ▼
                                    OAuthCallbackPage (fresh page load)
                                        exchange POST /api/keys/openrouter/exchange
                                        success + stash present → apply pending (PATCH/PUT)
                                          → clear stash → combined success toast → navigate(returnTo)
                                        success + no stash → existing behavior ('OpenRouter connected.' → /settings)
                                        apply fails → clear stash → warning toast → still navigate

CHAT/DEMO FLOW (DEMO-01/02, D-03/09/10/11, SEC-03)
  useChat.sendMessage ──▶ POST /api/threads/{id}/messages {content, use_demo?}
      │                        │
      │                        ▼
      │              _resolve_key_and_model (chat.py)
      │                 1. use_demo && flag ON ─────▶ demo branch (override, D-11)
      │                 2. user key row exists ─────▶ ("user", decrypted key)
      │                 3. flag ON (keyless) ───────▶ demo branch (D-03)
      │                 4. else ────────────────────▶ ("no_key") → SSE no_api_key, NO LLM call
      │              demo branch: model_cache.is_free(picked)? ─ yes → run picked free model
      │                                                        └ no/unknown → demo_fallback_model
      │                        │
      │                        ▼ owner key, mode="demo"
      │              stream … done event {message_id, usage?, mode:"demo"}
      ▼                        │
  useChat: parsed.mode==='demo' → lastTurnWasDemo=true
      │
      ▼
  ChatContainer banner: (!connected && demo_enabled) || lastTurnWasDemo  → amber strip (D-10)
  ErrorMessageBubble (403): demoEligible={demo_enabled} + onUseDemo → retry with {use_demo:true} (D-11)

FLAG EXPOSURE                                   DEPLOY (DEMO-01/SEC-03 ops)
  config.py demo_fallback_enabled (env)          prod supabase db push (migrations 029–033)
      └▶ GET /api/keys/status {connected,        verify Fly secret LLM_API_KEY = owner sk-or… key
          masked_label?, connected_at?,          fly secrets set DEMO_FALLBACK_ENABLED=true
          demo_enabled}                          CF Pages rebuild (push master:main)
      └▶ useKeyStatus shared store (no polling)
```

### Recommended Project Structure (new/extended files only)

```
frontend/src/
├── lib/
│   ├── fuzzy.ts                      # NEW — hand-rolled subsequence scorer (D-08)
│   └── pkce.ts                       # unchanged (stash written by useKeyGate, not here)
├── hooks/
│   ├── useKeyGate.tsx                # NEW — shared gate hook + modal state (D-04; locked name)
│   ├── useKeyStatus.ts               # EXTEND — KeyStatus gains demo_enabled
│   └── useChat.ts                    # EXTEND — lastTurnWasDemo + use_demo retry option
├── components/
│   ├── ModelSelector.tsx             # EXTEND — search input, sections, Popular chip, star
│   ├── DefaultModelSelector.tsx      # EXTEND — route handleSelect through useKeyGate
│   ├── ChatContainer.tsx             # EXTEND — demo banner first shrink-0 child; wire demoEligible/onUseDemo
│   ├── ConfirmDialog.tsx             # EXTEND — variant ('danger'|'primary') + light shell tokens
│   └── ErrorMessageBubble.tsx        # unchanged (props already exist, dead by design)
├── pages/
│   ├── OAuthCallbackPage.tsx         # EXTEND — pending-selection resume (D-02)
│   ├── ChatPage.tsx                  # EXTEND — gate wraps handleThreadModelChange
│   └── SettingsPage.tsx              # minimal — gate lives inside DefaultModelSelector/useKeyGate
backend/
├── routers/
│   ├── keys.py                       # EXTEND — status returns demo_enabled (both branches)
│   ├── preferences.py                # EXTEND — favorite_models in GET select + PUT echo
│   └── chat.py                       # EXTEND — use_demo override + D-03 free-guard in demo branch
├── models/schemas.py                 # EXTEND — MessageCreate.use_demo, PreferencesUpdate/Response.favorite_models, KeyStatusResponse.demo_enabled
supabase/migrations/
└── 20240301000033_add_favorite_models.sql   # NEW — additive TEXT[] column
```

### Pattern 1: Shared key-gate hook (`useKeyGate`)

**What:** One hook owning the gate decision + modal state, wrapping the apply callback of BOTH surfaces.
**When to use:** Every model selection (thread header and settings default).

Decision table (UI-SPEC locked):

| State | Selection | Action |
|-------|-----------|--------|
| connected | any | apply immediately (existing PATCH/PUT path) |
| keyless, demo ON | `m.is_free === true` | apply immediately (demo turns run the picked free model) |
| keyless, demo ON | paid | open gate modal, paid body |
| keyless, demo OFF | any | open gate modal, demo-OFF body |
| any | `extraOption` clear row (`value: null`) | recommend: apply immediately, no gate (clearing a pin needs no key; send stays fail-closed server-side) — flagged in Open Questions |

Key facts from live code:
- `ChatPage.handleThreadModelChange` (`ChatPage.tsx:92-109`) is the thread apply path — optimistic local mirror + `PATCH /api/threads/{id} {model}` with error toast. The gate wraps this.
- `DefaultModelSelector.handleSelect` (`DefaultModelSelector.tsx:30-40`) self-PUTs fire-and-forget. The gate must intercept BEFORE `onChange`/PUT fire — a keyless pick must not optimistically update the default.
- `useKeyStatus` is a module-level shared store with in-flight dedup — the gate reads `status?.connected` and the new `demo_enabled` with zero extra fetches. While `status` is null (first load), treat as not-connected-unknown: the gate should not open a modal until status resolves (avoid a flash-gate on slow status; simplest: fall through to gate only when `status !== null`).
- Row-level `is_free` is server-computed and rendered verbatim (`ModelSelector.tsx:6-8` doc comment) — the gate branches on `m.is_free`; the server re-validates at send time (D-03 guard). **Full catalog always rendered; no `free_only` display filter** (UI-SPEC D-03 interpretation — a free-only display would make KEY-05's trigger unreachable in the shipped demo-ON config).

**Structural note:** `ModelSelector` receives `onSelect` from its parent. The cleanest gate placement is in the *callers* (ChatPage handler + DefaultModelSelector), both delegating to one `useKeyGate({ kind, threadId?, onApply })` that returns `{ guardedSelect, gateModal }`. The gate needs the full `ModelResponse` (for `is_free` + display name) — `onSelect` currently passes only `modelId: string | null`, so either (a) extend `ModelSelector`'s `onSelect` signature to pass the model object, or (b) have the gate look up the model in the `models` catalog it already has. Option (b) avoids touching the `onSelect` contract but requires the catalog in the caller (ChatPage/SettingsPage already hold `models`); either is acceptable — planner's call.

### Pattern 2: Pending-selection stash with one-shot lifecycle (D-02)

**What:** `sessionStorage['or_pending_selection']` = `{ kind: 'thread' | 'default', modelId: string, threadId?: string, returnTo: string }` (UI-SPEC locked key + shape), written by `useKeyGate` immediately before `startOpenRouterConnect()`.

Lifecycle (all transitions verified against `OAuthCallbackPage.tsx` current code):
- **Written:** on gate-modal [Connect], beside `or_pkce_verifier`/`or_pkce_state` (`pkce.ts:38-39`) — same survives-hard-refresh semantics (Phase 10 D-07: sessionStorage, NOT localStorage).
- **Consumed (one-shot):** in `OAuthCallbackPage` after the existing successful exchange (`OAuthCallbackPage.tsx:40-47`), before navigate. Remove the key FIRST, then apply — guarantees one-shot even if apply throws.
- **Preserved across Retry:** the failure screen's Retry calls `startOpenRouterConnect()` (`OAuthCallbackPage.tsx:76`), which rewrites only verifier/state — the stash survives naturally. No code needed.
- **Cleared on abandon:** "Back to settings" (`OAuthCallbackPage.tsx:81-87`) must gain an explicit `sessionStorage.removeItem('or_pending_selection')`.
- **StrictMode-safe:** the `ranRef` guard (`OAuthCallbackPage.tsx:23-27`) already prevents double-run in the same mount; the resume rides inside the same guarded effect, so no double-apply.
- **Toast rule (locked):** when a pending selection applies, fire ONLY the combined toast (`Connected — ${model} is set for this chat.` / `…is now your default model.`), NOT `OpenRouter connected.` as well. Apply failure → `Connected, but your model pick didn't apply — pick it again.` (warning variant) and still navigate — never render the failure screen for an apply error (the connection succeeded).
- **Post-connect state:** the OAuth round-trip is a full page reload (`window.location.assign`), so every `useKeyStatus` instance remounts and refetches — no `notifyKeyStatusChanged()` broadcast needed on the resume path (verified: the store's own doc comment at `useKeyStatus.ts:22-26` records this).

### Pattern 3: Sectioned, searchable listbox (combobox-with-list-popup)

**What:** `ModelSelector`'s current flat `options` array (`ModelSelector.tsx:96-100`) becomes a render-row list of headers + options; a search input becomes the focus target on open (replacing `listRef.current?.focus()` at `:167-172`).

Structure that preserves the existing keyboard machinery with minimal surgery:

```
rows to render = [extraOption? (hidden while searching)]
               + (searching
                   ? [flat score-ranked option rows, no headers]
                   : [hdr Favorites]+[fav rows]   (section absent when empty — locked)
                   + [hdr Popular]+[popular rows sorted by popularity_rank]
                   + [hdr All models]+[all rows alphabetical by label])
```

Load-bearing implementation facts:
- **Duplication is deliberate** (a model can appear in Favorites + Popular + All). React keys and option DOM ids must be section-scoped: `key={`${section}:${m.id}`}`, `id={`${listboxId}-opt-${section}-${idx}`}` — plain `m.id` keys will collide and `aria-activedescendant` will point at the wrong instance.
- **Selected check + star state render identically in every duplicate instance** (locked).
- **Arrow-nav must skip headers.** Keep a flat *navigable* array (options only) for `activeIndex` and map to render rows; headers get `role="presentation"`.
- **The active-index seeding effect** (`ModelSelector.tsx:146-152`) currently re-seeds on `[open, options.length]` — with live filtering the length changes per keystroke and would yank the active row back to the selected model. Re-seed on open; on filter change, clamp/reset `activeIndex` to 0 instead.
- **Focus model change** (locked a11y contract): trigger unchanged; on open focus moves to the input (`aria-autocomplete="list"`, `aria-controls={listboxId}`, `aria-activedescendant={activeOptionId}`); ArrowUp/Down move active row, Enter selects, **Shift+Enter toggles favorite on the active row**, Esc closes to trigger, Tab trapped, printable keys type into the filter, Home/End operate on the input caret (native). This is the cmdk/shadcn search-in-popup pattern, hand-rolled.
- **`PANEL_MAX` estimate at `ModelSelector.tsx:139` bumps 320 → ~370** to keep drop-up math honest with the `h-11` search row (locked consistency requirement — the settings sidebar-footer selector relies on drop-up).
- **Existing locked behaviors must survive:** lazy fetch on open (`:102-118`), `Loading models…`/error-retry/`No models available.` states, outside-click close (`:155-164`), `max-h-72` list scroll, ≥44px rows, selected check at `left-1.5`, empty-`models`-prop-means-unfetched semantics (`:75-78`).
- **Popular chip:** render in `ModelHint` (`:315-330`) whenever `popularity_rank != null`, classes mirroring the Free tag exactly (`rounded bg-gray-200 px-1 text-gray-700 dark:bg-gray-700 dark:text-gray-200`), order `[Free] [Popular] 128K context`. Renders in every section instance, including search results (closes B-1).
- **Favorite star:** button `absolute right-0 inset-y-0 w-11`, `tabIndex={-1}`, `stopPropagation()` on click — toggles without selecting or closing; row content gains `pr-12`. Favorited `text-blue-600 fill-blue-600`; unfavorited outline `text-gray-400 dark:text-gray-500`. NOT on the extraOption row.
- **Favorites data:** read once at picker mount via existing `GET /api/preferences` (UI-SPEC sanctioned); render the *intersection* of `favorite_models` with the catalog (a stale slug persists in storage but renders nothing); alphabetical within the section. Toggle = optimistic local set + fire-and-forget `PUT /api/preferences {favorite_models: [...]}` (whole-array replace via the existing partial upsert); no revert on failure, no toast (house style, mirrors `DefaultModelSelector`).
- **Search:** 150ms debounce (locked), matches `id` AND `name`, non-matching rows removed (never disabled), empty state `No models match your search.`, extraOption hidden while searching.

### Pattern 4: Server-side demo free-guard + `use_demo` override (D-03/D-11)

**What:** Two additive changes to `_resolve_key_and_model` (`chat.py:152-207`) that preserve its fail-closed three-branch shape.

Current demo branch (`chat.py:196-204`) returns `settings.demo_fallback_model or model` — it PINS the fallback and ignores the picked model. D-03 changes it to: *resolve the model tier normally (thread pin → user default → owner default), then run the picked model only if `model_cache` says it is free; otherwise the pinned `demo_fallback_model`*. The check is a one-row read of the precomputed `is_free` column (migration 030; `_to_cache_row` writes it — verified) — never recompute freeness from pricing in chat.py, and never trust an FE-supplied flag.

D-11 adds a `use_demo` request override for users who HAVE a key that got 403-rejected: `MessageCreate` gains `use_demo: bool = False`; when `body.use_demo and settings.demo_fallback_enabled`, resolution short-circuits to the demo branch BEFORE the user-key branch. When the flag is OFF the override is inert (falls through to normal resolution — the SEC-03 kill switch stays intact; existing tests `test_sec03_killswitch_no_owner_spend_when_flag_off`, `test_no_key_flag_off_refuses`, `test_fail_closed_no_or_fallback` must stay green).

Resolution order after the change: `use_demo+flagON → demo` › `user key → user` › `flagON keyless → demo` › `no_key`.

Emission is already done: the done event carries `mode:"demo"` (`chat.py:1181-1195`) and `useChat.ts:251-261` keys only on `message_id`, so the extra field is inert until read. The FE change is a one-line read (`parsed.mode === 'demo'`) plus a `lastTurnWasDemo` state.

### Pattern 5: Demo-flag exposure via `GET /api/keys/status` (smallest seam — UI-SPEC resolved)

**What:** `KeyStatusResponse` (schemas.py:122-131) gains `demo_enabled: bool = False`; `keys.py status()` (`keys.py:82-99`) sets it from `get_settings().demo_fallback_enabled` **in BOTH return branches** (the no-row early return at `:93-94` is exactly the keyless audience the demo serves — leaving it to the pydantic default would hide the flag from them). FE `KeyStatus` interface (`useKeyStatus.ts:5-9`) gains `demo_enabled?: boolean`. Zero new endpoints, zero new fetches; the shared no-poll store already serves the gate hook, banner, and error bubble. Keep the silent-on-error, broadcast-refresh contract untouched.

Banner render condition (locked): `(!keyStatus.connected && demoEnabled) || lastTurnWasDemo` — proactive for keyless users under the flag, guaranteed after any observed `mode:"demo"`. While status is still loading, `demo_enabled` is undefined → condition is false → no flash. Banner is the FIRST `shrink-0` child of `ChatContainer`'s root flex column (above the thread-header row, present with or without an active thread), `role="status"`, non-interactive, both themes.

### Pattern 6: Migration 033 + preferences extension (D-05)

**What:** Additive `favorite_models TEXT[] NOT NULL DEFAULT '{}'` on `user_preferences` (next free number 033 — verified: migrations end at `20240301000032`). Follows the `default_model` plain-TEXT non-FK convention (a favorited model may leave the catalog; the stored slug must persist harmlessly). Existing own-row RLS covers the new column automatically; no policy changes. `preferences.py` must add `favorite_models` to BOTH selects (GET at `:44` and the PUT echo at `:78`) and both response dict literals; `PreferencesResponse` gains `favorite_models: list[str] = []`, `PreferencesUpdate` gains `favorite_models: list[str] | None = None` (partial-upsert `exclude_unset` keeps a theme-only PUT from clobbering favorites — the existing pattern extends cleanly). Whole-array replace semantics (client sends the complete new list), which is idempotent and race-tolerant enough for a single user's favorites.

Dev first, prod at deploy — prod is currently at migration 028 (memory: 029–032 unapplied), so this phase's deploy step pushes 029–033 together.

### Pattern 7: Deploy step (DEMO-01 enablement + SEC-03 discharge)

Ordered ops checklist (operator-run, final plan of the phase, human-gated):
1. `supabase db push` against prod (`.env.prod` project) → applies 029–033. Contingency: if push replays old migrations ("already exists"), run `supabase migration repair --status applied` for the prior range first (established repair pattern from Phase 9).
2. Verify Fly prod secret `LLM_API_KEY` is the OpenRouter **owner** key (`sk-or…` prefix) — the 999.2 trip-test authenticated via local `.env.prod`; deployed prod must carry the same key or the demo branch mints no completions (SEC-03 finding deployment note, verbatim requirement).
3. `fly secrets set DEMO_FALLBACK_ENABLED=true` (pydantic-settings reads env case-insensitively) → Fly restarts the machine.
4. Re-verify the demo slug is live at deploy time (see State of the Art — verified 2026-07-02, single-endpoint model, re-check if the deploy slips more than a week).
5. Frontend: CF Pages builds `main`; push `master:main` (established mechanics — fly repo-root Dockerfile for the backend, CF for the frontend).
6. Post-enable smoke: keyless account → picker shows full catalog → pick a free model → send → banner renders → turn streams on the picked free model; pick a paid model → gate modal → Connect round-trip → auto-apply toast.

### Anti-Patterns to Avoid

- **Filtering the picker to free-only for keyless users:** hides every paid row → KEY-05's gate trigger becomes unreachable in the shipped demo-ON config. The UI-SPEC resolves D-03's tension explicitly: full catalog always rendered; `is_free` drives the gate branch. Any override toward free-only display must be escalated, not silently implemented.
- **Recomputing `is_free` client-side** (e.g. from pricing or `:free` suffix): the FE renders server-computed fields verbatim (Phase 12 contract, `ModelSelector.tsx:6-8`).
- **Disabled/locked rows for keyless users:** D-01 forbids them — every row is clickable; the gate is a modal, not a lock.
- **`localStorage` for the pending selection:** breaks tab-scoping and the Phase-10 CSRF/hard-refresh semantics; sessionStorage only.
- **Trusting `use_demo` or the picked model server-side:** the flag must be a no-op when `demo_fallback_enabled` is False, and the model must pass the `model_cache.is_free` check or fall back — otherwise a crafted request runs a paid model on the owner key.
- **Polling for the demo flag:** ride the existing status store; no new intervals, no Realtime.
- **`npx shadcn init`:** superseded stale todo; do not initialize (UI-SPEC gate result: `Tool: none`).
- **Toasting favorite toggles or reverting failed favorite PUTs:** house style is optimistic fire-and-forget, silent.
- **Interpolating anything but `${model}` (display name) into new copy:** SEC-01 house style; locked strings only.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| OAuth PKCE launch/exchange | Any new OAuth plumbing | `startOpenRouterConnect()` + existing exchange endpoint, as-is | Verifier/state/CSRF/hard-refresh semantics were hardened in Phase 10; the gate only *calls* it |
| Modal | A new dialog component | `ConfirmDialog` + additive `variant` prop | Portal, Esc, overlay-click, focus behavior already proven; `danger` default = zero regression risk for disconnect/docs dialogs |
| Toast/notification | Any new toast surface | `ToastContext` (`success`/`warning` variants exist) | Bottom-right 4s contract is locked |
| Free/paid tagging | Client-side freeness logic | `model_cache.is_free` (server) / `m.is_free` (render) | Single source of truth; `tag_is_free` handles `:free` suffix + zero-pricing edge cases |
| Favorites CRUD | New table/endpoint | `user_preferences` + existing GET/PUT partial upsert | RLS, JWT-binding, `exclude_unset` semantics all inherited |
| Demo-turn signal | New SSE event type | Existing `mode:"demo"` field on the done event | Already emitted since Phase 11; FE just reads it |
| Demo flag transport | New config endpoint or polling | `demo_enabled` on `GET /api/keys/status` | Shared store dedups fetches across all consumers |
| Key-status distribution | Per-component fetches | `useKeyStatus` module store | In-flight dedup + broadcast refresh already solved (WR-02) |

**Key insight:** this phase's one *sanctioned* hand-roll is the fuzzy matcher (D-08 locked bias, ~40 lines, fully specified ranking). Everything else that looks buildable — OAuth, modals, toasts, freeness, upserts, SSE signals — already exists in-repo and was built to be consumed by exactly this phase.

## Common Pitfalls

### Pitfall 1: Section duplication breaks React keys and `aria-activedescendant`
**What goes wrong:** A model appearing in Favorites + Popular + All with `key={m.id}` triggers duplicate-key warnings and renders stale rows; duplicate DOM ids make `aria-activedescendant` ambiguous.
**Why it happens:** The current flat option list (`ModelSelector.tsx:96-100`) assumes one row per model.
**How to avoid:** Section-scoped keys/ids (`fav:${id}` / `pop:${id}` / `all:${id}`); selected-check and star state computed per model id so all instances stay in sync.
**Warning signs:** React key warnings in test output; VoiceOver/tests reading the wrong active row.

### Pitfall 2: Active-row seeding fights the live filter
**What goes wrong:** Typing in search yanks the highlighted row back to the selected model on every keystroke, or crashes on out-of-range `activeIndex`.
**Why it happens:** The seed effect re-fires on `options.length` change (`ModelSelector.tsx:146-152`), which now changes per keystroke.
**How to avoid:** Seed to the selected row on OPEN only; on query change, reset active to the first navigable option and clamp when the filtered list shrinks.
**Warning signs:** Flaky arrow-nav tests; `options[activeIndex]` undefined.

### Pitfall 3: `demo_enabled` silently false for exactly the users who need it
**What goes wrong:** Keyless users (the demo audience) never see the banner or free-row fast-path even with the flag ON in prod.
**Why it happens:** `keys.py status()` has an early return `{"connected": False}` (`keys.py:93-94`); relying on the pydantic default leaves `demo_enabled=False` on that branch.
**How to avoid:** Set `demo_enabled=get_settings().demo_fallback_enabled` explicitly in BOTH return branches; pin with a test asserting the keyless branch carries the flag.
**Warning signs:** Banner renders in dev (connected dev account, `lastTurnWasDemo` path) but never for a fresh keyless account.

### Pitfall 4: `use_demo` override weakens the fail-closed posture
**What goes wrong:** A crafted `{use_demo: true}` request runs an owner-key completion while the flag is OFF, or runs a paid model on the owner key.
**Why it happens:** Override checked before the flag, or the free-guard skipped on the override path.
**How to avoid:** Gate the override on `settings.demo_fallback_enabled` first; route BOTH demo entries (override + keyless) through the same free-guard helper. Keep the three SEC-03 kill-switch tests green and add flag-OFF-override-inert + paid-pick-falls-back tests.
**Warning signs:** Any resolution path returning `settings.resolved_llm_api_key` without `demo_fallback_enabled` in its condition.

### Pitfall 5: Demo guard crashes or mis-falls-back on cache edge cases
**What goes wrong:** An empty/mid-refresh `model_cache`, a `maybe_single()` returning None, or a non-dict row crashes the turn or lets an unknown model through.
**Why it happens:** `maybe_single()` returns `None` data for no-row; the deprecation check at `chat.py:820-852` already documents this class of bug (T-13-CRASH).
**How to avoid:** Mirror the existing defensive shape: `row and isinstance(row.data, dict) and row.data.get("is_free") is True` → picked model; ANY other outcome (including exceptions, logged scrubbed) → pinned `demo_fallback_model`. Unknown ≠ free.
**Warning signs:** Demo turns 500ing when the cache is cold; a model absent from the cache running on the owner key.

### Pitfall 6: Stash double-apply, orphan, or leak across flows
**What goes wrong:** The pending selection applies twice (StrictMode/refresh), applies after the user abandoned the flow, or a stale stash from a cancelled gate applies on an unrelated connect from Settings.
**Why it happens:** sessionStorage outlives navigation; multiple entry points call `startOpenRouterConnect()` (Settings CTA, error-bubble Reconnect, callback Retry).
**How to avoid:** One-shot: `removeItem` FIRST in the callback resume, then apply. Clear on gate [Cancel]? No — the stash is only *written* on [Connect], so Cancel never writes. But the Settings "Connect OpenRouter" CTA and error-bubble [Reconnect] do NOT write a stash — a leftover stash from an earlier abandoned gate flow could then auto-apply on those connects. Mitigate: clear any existing `or_pending_selection` at the START of `startOpenRouterConnect()` callers that aren't the gate, or (simpler) have `useKeyGate` be the only writer and accept the residual-apply as benign… it is NOT benign (surprise model change). Recommended: `startOpenRouterConnect()` stays pure; the gate writes the stash; SettingsPage CTA + ErrorMessageBubble Reconnect + OAuthCallbackPage Retry-with-no-prior-stash paths each `removeItem('or_pending_selection')` before launching — EXCEPT the callback Retry, which must PRESERVE it (locked). Planner should encode this as an explicit per-call-site table.
**Warning signs:** A toast `Connected — X is set for this chat.` after a plain Settings connect.

### Pitfall 7: Gate intercepts too late on the settings surface
**What goes wrong:** A keyless pick optimistically updates the default (parent `onChange` + fire-and-forget PUT) and THEN shows the gate — cancel leaves a half-applied default.
**Why it happens:** `DefaultModelSelector.handleSelect` (`DefaultModelSelector.tsx:30-40`) applies before any gate can run if the gate is bolted on after.
**How to avoid:** The gate decision runs BEFORE `onChange`/PUT; on gate-open, the trigger keeps showing the prior model (selection unchanged until Connect round-trip applies it).
**Warning signs:** Settings shows the picked model after Cancel; a PUT fires for a keyless pick.

### Pitfall 8: Focus-model migration breaks the existing test suite (expected, contract-sanctioned)
**What goes wrong:** `ModelSelector.test.tsx` asserts the UL-focus model (list focused on open, list-level keydown); moving focus to the search input fails those assertions.
**Why it happens:** Locked a11y contract change (combobox pattern supersedes listbox-focus).
**How to avoid:** Update the tests to the input-focus model in the SAME plan/wave that changes the component — the UI-SPEC explicitly sanctions this. Do not weaken the ≥44px, LOCKED-copy, and role assertions while updating.
**Warning signs:** A plan that changes ModelSelector without touching its test file.

### Pitfall 9: Demo model single-endpoint fragility mistaken for a phase defect
**What goes wrong:** Live verification of demo turns intermittently fails (rate-limit / in-band SSE provider error) and gets chased as a phase bug.
**Why it happens:** `meta-llama/llama-3.3-70b-instruct:free` currently has ONE endpoint (Venice, fp8) at ~88% 1-day uptime [VERIFIED 2026-07-02]; `:free` models rate-limit aggressively — precedent: D-999.1-LLM-A (a different `:free` model failing with HTTP 200 + in-band SSE error, ruled NOT a phase defect).
**How to avoid:** The banner copy already warns ("temporarily rate-limited"); the error taxonomy (rate_limit / model_unavailable) already renders recovery UI. Verify demo mechanics with mocked provider responses in tests; treat live free-model flakiness as environmental. If the slug is dead at execution time, pick a live `:free` slug with `tools` in `supported_parameters` (the agent loop always sends tools).
**Warning signs:** Retry-until-green loops against a live free model in CI or verification.

### Pitfall 10: Prod deploy ordering breaks the flag flip
**What goes wrong:** Flag flips ON while prod DB lacks migrations 029–032 (usage column, model_cache, user_preferences) → demo resolution or favorites 500 in prod.
**Why it happens:** Prod is 4 migrations behind (verified project memory); this phase adds a 5th.
**How to avoid:** Deploy plan order: migrations 029–033 → verify `LLM_API_KEY` Fly secret (owner `sk-or…`) → `DEMO_FALLBACK_ENABLED=true` → backend deploy → CF rebuild → smoke. Migration-history repair contingency documented (Pattern 7).
**Warning signs:** `relation "user_preferences" does not exist` / `model_cache` errors in prod logs after the flip.

### Pitfall 11: Banner breaks the chat flex layout or double-renders with DemoPill
**What goes wrong:** The banner as a non-`shrink-0` child compresses the scroll area; or confusion with the existing amber `DemoPill` (anon-session badge — a DIFFERENT "demo" concept).
**Why it happens:** `ChatContainer` root is `flex-1 flex flex-col h-full` (`ChatContainer.tsx:58`); the thread-header row is `shrink-0` and the message list `flex-1 overflow-y-auto`. DemoPill (`DemoPill.tsx`) marks anonymous sessions, not demo-fallback turns.
**How to avoid:** Banner = FIRST `shrink-0` sibling (locked). Leave DemoPill untouched; both may legitimately show for an anon keyless user under the flag.
**Warning signs:** Chat input pushed off-screen; anyone "deduplicating" DemoPill with the banner.

### Pitfall 12: Favorites PUT clobbers other preference fields (or vice versa)
**What goes wrong:** A favorites toggle nulls `default_model`, or a theme PUT wipes favorites.
**Why it happens:** Misusing full-object PUTs instead of the established partial upsert.
**How to avoid:** `PreferencesUpdate.favorite_models: list[str] | None = None` + `exclude_unset` (existing pattern at `preferences.py:70-75`); clients send ONLY the field they change. Add a regression test: theme-only PUT preserves favorites; favorites-only PUT preserves theme + default_model.
**Warning signs:** Any FE call sending `{default_model, theme, favorite_models}` together.

## Code Examples

Verified patterns from the live codebase + locked specs.

### Fuzzy matcher (hand-rolled, matches the UI-SPEC locked ranking)
```typescript
// frontend/src/lib/fuzzy.ts — NEW. No deps (D-08 locked bias).
// Ranking (UI-SPEC locked): exact substring > match starting at a word boundary
// (/, -, ., space, :) > tighter subsequence gap span; ties alphabetical by label
// (ties resolved by the caller's sort). Case-insensitive over id AND name.
const BOUNDARY = /[\s/\-.:]/

export function fuzzyScore(query: string, target: string): number | null {
  const q = query.toLowerCase()
  const t = target.toLowerCase()
  if (q.length === 0) return 0
  const sub = t.indexOf(q)
  if (sub >= 0) {
    const atBoundary = sub === 0 || BOUNDARY.test(t[sub - 1])
    return 10000 + (atBoundary ? 1000 : 0) - sub // substring tier; boundary + earlier wins
  }
  // subsequence tier: query chars in order, gaps allowed (typo-tolerance per spec:
  // 'lama33' matches 'llama-3.3')
  let ti = 0
  let first = -1
  let last = -1
  for (let qi = 0; qi < q.length; qi++) {
    ti = t.indexOf(q[qi], ti)
    if (ti === -1) return null // not a subsequence → no match, row removed
    if (first === -1) first = ti
    last = ti
    ti++
  }
  const span = last - first + 1
  return 1000 - (span - q.length) // tighter span scores higher
}

// Per model: best of id/name; caller sorts desc, ties alphabetical by label.
export function matchModel(query: string, id: string, name: string | null): number | null {
  const a = fuzzyScore(query, id)
  const b = name ? fuzzyScore(query, name) : null
  if (a === null) return b
  if (b === null) return a
  return Math.max(a, b)
}
```

### Demo branch free-guard + `use_demo` override (chat.py)
```python
# backend/routers/chat.py — replaces the body of the demo branch in
# _resolve_key_and_model (currently :196-204) and adds the override entry.
# Source: mirrors the defensive maybe_single shape at chat.py:181-190 and the
# T-13-CRASH tolerance at chat.py:848-852.

def _demo_model_for(db, model: str, settings) -> str:
    """D-03 server-side guard: run the picked model ONLY when model_cache says it
    is free; non-free, unknown, or any read failure -> pinned demo_fallback_model.
    Never trusts the frontend; unknown is NOT free."""
    try:
        row = (
            db.table("model_cache")
            .select("is_free")
            .eq("model_id", model)
            .maybe_single()
            .execute()
        )
        if row and isinstance(row.data, dict) and row.data.get("is_free") is True:
            return model
    except Exception as e:  # cache read must never crash the turn
        logger.warning(f"demo free-check failed; using pinned fallback: {scrub_secrets(str(e))}")
    return settings.demo_fallback_model

# inside _resolve_key_and_model, ordering: override -> user key -> keyless demo -> no_key
    # D-11 [Use demo] override — honored ONLY when the flag is ON (kill switch intact).
    if getattr(body, "use_demo", False) and settings.demo_fallback_enabled:
        return settings.resolved_llm_api_key, _demo_model_for(db, model, settings), "demo", False

    # ... existing user-key branch unchanged (chat.py:181-194) ...

    if settings.demo_fallback_enabled:
        return settings.resolved_llm_api_key, _demo_model_for(db, model, settings), "demo", False
```

### MessageCreate + KeyStatusResponse + preferences schema extensions
```python
# backend/models/schemas.py — additive fields only.
class MessageCreate(BaseModel):
    content: str
    # D-11 [Use demo] retry override — server honors it ONLY when
    # demo_fallback_enabled (fail-closed preserved when OFF).
    use_demo: bool = False

class KeyStatusResponse(BaseModel):
    connected: bool
    masked_label: str | None = None
    connected_at: str | None = None
    # Phase 15: env-driven demo flag surfaced read-only (never settable via API).
    demo_enabled: bool = False

class PreferencesResponse(BaseModel):
    default_model: str | None = None
    theme: str = "dark"
    favorite_models: list[str] = []

class PreferencesUpdate(BaseModel):
    default_model: str | None = None
    theme: Literal["light", "dark"] | None = None
    # Whole-array replace; exclude_unset keeps theme-only PUTs from clobbering it.
    favorite_models: list[str] | None = None
```

### keys.py status — flag in BOTH branches (Pitfall 3)
```python
# backend/routers/keys.py — status() extension.
@router.get("/status", response_model=KeyStatusResponse)
async def status(user_id: str = Depends(get_user_id)):
    demo_enabled = get_settings().demo_fallback_enabled
    row = ( ... existing select ... )
    if not row or not row.data:
        return {"connected": False, "demo_enabled": demo_enabled}
    return {
        "connected": True,
        "masked_label": row.data["key_label"],
        "connected_at": row.data["connected_at"],
        "demo_enabled": demo_enabled,
    }
```

### Migration 033
```sql
-- supabase/migrations/20240301000033_add_favorite_models.sql
-- Phase 15 (MODEL-08, D-05) — additive, single statement, no backfill.
-- TEXT[] of OpenRouter slugs; deliberately NOT a FK to model_cache (same
-- deprecation-tolerance rationale as default_model, migration 032). Existing
-- own-row RLS on user_preferences covers the new column automatically.
ALTER TABLE user_preferences
  ADD COLUMN favorite_models TEXT[] NOT NULL DEFAULT '{}';
```
PostgREST/supabase-py note: send/receive as a plain JSON array — `{"favorite_models": ["a/b", "c/d:free"]}` upserts into `TEXT[]` directly [VERIFIED: postgrest.org data-types docs — both `{a,b}` string form and JSON arrays accepted for 1-D arrays].

### OAuthCallbackPage resume (D-02, one-shot)
```typescript
// frontend/src/pages/OAuthCallbackPage.tsx — inside the existing try, after the
// exchange succeeds and verifier/state are cleared (:40-45), replacing the fixed
// toast+navigate (:46-47). ranRef already guards StrictMode double-run.
interface PendingSelection {
  kind: 'thread' | 'default'
  modelId: string
  threadId?: string
  returnTo: string
}

const raw = sessionStorage.getItem('or_pending_selection')
if (raw) {
  sessionStorage.removeItem('or_pending_selection') // one-shot BEFORE apply
  let pending: PendingSelection | null = null
  try { pending = JSON.parse(raw) as PendingSelection } catch { pending = null }
  if (pending) {
    const label = modelLabelFor(pending.modelId) // display name ?? id — the ONLY interpolation
    try {
      if (pending.kind === 'thread' && pending.threadId) {
        await apiFetch(`/api/threads/${pending.threadId}`, {
          method: 'PATCH',
          body: JSON.stringify({ model: pending.modelId }),
        })
        showToast(`Connected — ${label} is set for this chat.`, 'success')
      } else {
        await apiFetch('/api/preferences', {
          method: 'PUT',
          body: JSON.stringify({ default_model: pending.modelId }),
        })
        showToast(`Connected — ${label} is now your default model.`, 'success')
      }
    } catch {
      // Connection succeeded — NEVER the failure screen for an apply error.
      showToast("Connected, but your model pick didn't apply — pick it again.", 'warning')
    }
    navigate(pending.returnTo || '/settings', { replace: true })
    return
  }
}
// no stash (or unparseable) → existing behavior unchanged:
showToast('OpenRouter connected.', 'success')
navigate('/settings', { replace: true })
```

### Demo banner (locked classes + copy)
```tsx
// frontend/src/components/ChatContainer.tsx — FIRST shrink-0 child of the root
// flex column (above the thread-header row). Non-interactive, both themes.
{showDemoBanner && (
  <div
    role="status"
    className="shrink-0 flex items-center gap-2 px-4 py-2 text-xs border-b bg-amber-500/10 border-amber-500/30 text-amber-700 dark:text-amber-300"
  >
    <Info size={14} className="text-amber-500 shrink-0" aria-hidden="true" />
    <span>
      Demo mode — a free model is in use; it may be slower, less accurate, or temporarily rate-limited (no usage left).
    </span>
  </div>
)}
```

### useChat demo signal + demo retry (D-10/D-11 FE half)
```typescript
// frontend/src/hooks/useChat.ts — done-event branch (:251-261) gains one read:
} else if (parsed.message_id) {
  if (parsed.mode === 'demo') setLastTurnWasDemo(true)
  // ...existing id/usage update unchanged
}
// sendMessage opts gain useDemo; body becomes:
body: JSON.stringify({ content, ...(opts?.useDemo ? { use_demo: true } : {}) })
// retry path for [Use demo] mirrors retryLastUserMessage (:354-362) with
// { retry: true, useDemo: true } — strips error bubbles, re-sends last user turn.
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Roadmap note: "only new FE dep surface is shadcn/ui Combobox"; STATE todo: "shadcn init is a Phase 15 prerequisite" | **Superseded:** hand-rolled listbox shipped in Phase 12; UI-SPEC gate resolved `Tool: none`, "Do not run `npx shadcn init`" | 2026-07-02 (UI-SPEC approved) | Plans must NOT initialize shadcn; the stale STATE.md todo should be closed at phase completion |
| Demo branch pins `demo_fallback_model`, ignores picked model (`chat.py:201`) | D-03: picked model runs when `model_cache.is_free` verifies it; pinned slug is the fallback | This phase | Implements the deferred Phases 11/12 "demo users pick among free models" plan |
| `demoEligible={false}` hard-coded (`ChatContainer.tsx:122`) | Real flag via `useKeyStatus.demo_enabled` | This phase | Dead-by-design props go live (D-11) |
| `mode:"demo"` emitted, unread (`chat.py:1190`, comment cites "Phase 15") | Read into `lastTurnWasDemo` | This phase | Banner render condition (D-10) |

**Demo model liveness (volatile fact, re-verify at deploy):** `meta-llama/llama-3.3-70b-instruct:free` is live on OpenRouter as of 2026-07-02 — one endpoint (provider Venice, fp8 quant), `context_length` 65,536, `supported_parameters` includes `tools` and `tool_choice` (required — the chat loop always sends tools), `uptime_last_1d` ≈ 88.2% [VERIFIED: `GET openrouter.ai/api/v1/models/meta-llama/llama-3.3-70b-instruct:free/endpoints`]. The 65K context (vs the 128K config default) is handled by the existing dynamic context lookup (`chat.py:861-868`). The config comment at `config.py:38-42` mandates exactly this re-validation at Phase 15 — done; re-check if deploy slips >1 week (single-provider free endpoints churn).

**Deprecated/outdated:** nothing else — all other patterns in play (PKCE flow, SSE taxonomy, partial upsert, shared status store) are current as of Phase 14/999.x.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | supabase-py (2.13.0) passes a Python `list[str]` through as a JSON array that PostgREST writes into `TEXT[]` (PostgREST side verified; the py-client serialization step specifically is from training knowledge) `[ASSUMED]` | Pattern 6 / Code Examples | Favorites PUT 400s in dev — caught immediately by the first roundtrip test against the dev DB; fallback is trivial (JSONB column instead) |
| A2 | Anonymous (isAnon) Supabase sessions pass `get_user_id` and receive `{connected:false, demo_enabled:…}` from `/api/keys/status`, so the banner/gate work for anon users `[ASSUMED — inferred from AuthContext isAnon + auth-gated routers, not traced end-to-end]` | Pattern 5 | Anon users miss the demo UX; verify during live smoke (note: anon bootstrap itself is broken — D-999.1-DEMO-A — so anon-path verification may be blocked regardless) |
| A3 | The gate reading `status !== null` before gating never deadlocks (status fetch is silent-on-error and may keep `status` null offline) `[ASSUMED]` | Pattern 1 | Keyless-offline edge: picks apply without a gate — harmless (server fail-closed); planner may prefer gating on `loading === false` instead |

**All other claims** in this research are `[VERIFIED]` against live repo code read this session, or `[CITED]` from the named planning documents (CONTEXT, UI-SPEC, SEC-03 finding, audit, STATE, REQUIREMENTS).

## Open Questions (RESOLVED)

All five questions were resolved during planning; the adopted resolution is marked inline and encoded in the plan noted.

1. **Does the `extraOption` clear row ("Use my default model") pass through the gate? (RESOLVED)**
   - What we know: the UI-SPEC decision table covers "select of model m"; the clear row passes `value: null` and carries no `is_free`. The user's *default* may itself be a paid model.
   - What's unclear: gating a *clear* action feels wrong (it selects nothing), but post-clear the thread resolves to a possibly-paid default for a keyless user — which the server fail-closed/demo branch already handles at send time.
   - Recommendation: clear bypasses the gate (apply immediately). Document in the plan so the checker doesn't flag it as a gap.
   - **RESOLVED → plan 15-05** (Task 2 behavior: `modelId null` → onApply immediately, never gated — the clear row bypasses the gate; the server stays fail-closed at send time).

2. **`lastTurnWasDemo` reset semantics. (RESOLVED)**
   - What we know: locked render condition `(!connected && demoEnabled) || lastTurnWasDemo`; the proactive branch continuously covers keyless users. `useChat` state resets naturally on thread switch today.
   - What's unclear: whether a connected user's [Use demo] turn should keep the banner up after switching threads.
   - Recommendation: keep it simple — per-hook state, reset on thread switch (the demo turn's banner accompanied the turn; the proactive branch owns the persistent case). Planner discretion.
   - **RESOLVED → plan 15-07** (Task 1: `lastTurnWasDemo` resets to false on thread switch, per-hook state; the proactive `!connected && demo_enabled` branch owns the persistent case).

3. **Validation bounds for `favorite_models`. (RESOLVED)**
   - What we know: `PreferencesUpdate` currently has no size bounds on any field; the column is unbounded TEXT[].
   - What's unclear: locked decisions don't specify a cap.
   - Recommendation: add modest Pydantic bounds (e.g. `max_length≈200` items) as cheap abuse insurance; not a requirement, planner's call.
   - **RESOLVED → plan 15-01** (Task 1: `PreferencesUpdate.favorite_models` declared with `Field(default=None, max_length=200)`).

4. **Prod migration-history state at deploy. (RESOLVED)**
   - What we know: prod applied through 028; 029–032 pending; the Phase-9 deploy needed `supabase migration repair --status applied` before `db push`.
   - What's unclear: whether prod's migration table needs another repair for the 025–028 range before pushing 029–033.
   - Recommendation: deploy plan includes a dry-run/`supabase migration list` check + the repair contingency as an explicit conditional step.
   - **RESOLVED → plan 15-08** (Task 1: read-only `supabase migration list` drift check records whether the 025–028 range needs repair; Task 3 executes `supabase migration repair --status applied` as an explicit conditional step before the push).

5. **Anon demo verification path is pre-broken. (RESOLVED)**
   - What we know: `POST /api/demo/bootstrap` fails in dev (D-999.1-DEMO-A, pre-existing, different "demo" = anon sessions) — it may block live verification of the banner via an anon session.
   - Recommendation: verify demo-fallback UX with a signed-in keyless test account (e.g. fresh account, no OpenRouter connect) instead of the anon path; do not scope-creep into fixing bootstrap.
   - **RESOLVED → plan 15-08** (Task 4: live smoke uses a SIGNED-IN keyless prod account, explicitly not the anon path; the bootstrap fix stays out of scope).

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Node.js | FE build/tests | ✓ | v24.15.0 | — |
| npm | FE scripts | ✓ | 11.12.1 | — |
| Backend venv Python | pytest, uvicorn | ✓ | `backend/venv/Scripts/python.exe` present | — |
| supabase CLI | prod `db push` (deploy step) | ✓ | 2.95.4 | Supabase dashboard SQL editor (manual) |
| flyctl | Fly secrets + deploy (deploy step) | ✓ | present on PATH | Fly.io dashboard |
| OpenRouter public API | demo-slug verification, live catalog | ✓ | endpoints API responded 2026-07-02 | — |
| `.env.prod` / `fly.toml` / `Dockerfile` | deploy mechanics | ✓ | repo root | — |
| Dev Supabase project | migration 033 apply + live checks | ✓ (per project memory: dev = `.env`) | — | — |

**Missing dependencies with no fallback:** none.
**Missing dependencies with fallback:** none blocking — all deploy tooling present.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework (FE) | vitest 4.1.9 + @testing-library/react 16.3.2 + jsdom (config: `frontend/vitest.config.ts`, setup `src/test/setup.ts`, shared harness `src/test/utils.tsx`) |
| Framework (BE) | pytest via `backend/venv` (conftest at `backend/tests/conftest.py`) |
| Quick run (FE) | `cd frontend && npx vitest run src/components/ModelSelector.test.tsx` (per-file) |
| Full suite (FE) | `cd frontend && npm run test` (= `vitest run`) |
| Quick run (BE) | `cd backend && venv/Scripts/python.exe -m pytest tests/test_key_model_resolution.py -x -q` |
| Full suite (BE) | `cd backend && venv/Scripts/python.exe -m pytest tests/ -q` (known pre-existing debt: 2 `test_record_manager.py` fixture errors — out of scope, do not fix here) |
| Static gates | `cd frontend && npm run build` (tsc -b + vite) and `npm run lint` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| KEY-05 | Gate decision table (connected / keyless×demoON free / keyless×demoON paid / keyless×demoOFF); modal open/cancel keeps selection; [Connect] writes stash + launches PKCE | component | `npx vitest run src/hooks/useKeyGate.test.tsx` | ❌ Wave 0 |
| KEY-05 | Callback resume: stash → PATCH/PUT + combined toast + navigate(returnTo); apply-failure → warning toast, still navigates; no stash → legacy behavior | component | `npx vitest run src/pages/OAuthCallbackPage.test.tsx` | ❌ Wave 0 |
| MODEL-01 (W-1) | Fuzzy ranking spec (substring > boundary > span; subsequence typo-tolerance; null on non-subsequence) | unit | `npx vitest run src/lib/fuzzy.test.ts` | ❌ Wave 0 |
| MODEL-01 (W-1) | Search input filters/flattens sections, empty state, extraOption hidden while searching, input-focus a11y model | component | `npx vitest run src/components/ModelSelector.test.tsx` | ✅ extend (focus-model update is contract-sanctioned) |
| MODEL-03 (B-1) | Popular chip renders whenever `popularity_rank != null`, in every section instance, classes mirror Free tag | component | `npx vitest run src/components/ModelSelector.test.tsx` | ✅ extend |
| MODEL-08 | Sections order + hidden-empty Favorites; star toggle (stopPropagation, no close, Shift+Enter); optimistic PUT payload | component | `npx vitest run src/components/ModelSelector.test.tsx` | ✅ extend |
| MODEL-08 | `favorite_models` roundtrip: GET default `[]`, partial PUT preserves other fields, JWT-bound user_id | unit (BE) | `venv/Scripts/python.exe -m pytest tests/test_preferences_api.py -x -q` | ✅ extend |
| DEMO-01 / SEC-03 | Free-guard: picked-free runs picked; paid/unknown/cache-error falls back to pinned; `use_demo` inert when flag OFF; existing 3 killswitch tests stay green | unit (BE) | `venv/Scripts/python.exe -m pytest tests/test_key_model_resolution.py -x -q` | ✅ extend (scaffolding `_fake_settings`/`_db_with_key_row` ready) |
| DEMO-01 | `/api/keys/status` carries `demo_enabled` in BOTH branches (keyless + connected) | unit (BE) | `venv/Scripts/python.exe -m pytest tests/test_keys_status.py -x -q` | ✅ extend |
| DEMO-02 | Banner render condition (keyless+flag / lastTurnWasDemo / neither), locked copy, non-interactive, first shrink-0 child | component | `npx vitest run src/components/ChatContainer.test.tsx` | ✅ extend |
| DEMO-02 / D-11 | `useChat` reads `mode:"demo"` from done event (mockSSEResponse); demo retry sends `{use_demo:true}` | component | `npx vitest run src/hooks/useChat.test.tsx` | ✅ extend |
| KEY-05 (D-11 adjacency) | ErrorMessageBubble 403 + demoEligible shows [Use demo] wired to retry | component | `npx vitest run src/components/ChatContainer.test.tsx` | ✅ extend |
| DEMO-01 (prod flip) | Live prod smoke: keyless pick-free→banner+stream; pick-paid→gate→connect→auto-apply | manual-only | — (human-gated deploy checkpoint; live provider + OAuth account required) | n/a |

### Sampling Rate
- **Per task commit:** the focused file command for the seam touched (FE per-file vitest run or BE per-file pytest) + `npm run lint` for FE tasks.
- **Per wave merge:** both full suites (`npm run test`; `pytest tests/ -q`) + `npm run build`.
- **Phase gate:** full suites green (modulo the 2 documented pre-existing record_manager errors) + build + lint before `/gsd-verify-work`; deploy plan's live smoke is the final human gate.

### Wave 0 Gaps
- [ ] `frontend/src/lib/fuzzy.test.ts` — covers MODEL-01 ranking spec
- [ ] `frontend/src/hooks/useKeyGate.test.tsx` — covers KEY-05 decision table + stash write
- [ ] `frontend/src/pages/OAuthCallbackPage.test.tsx` — covers KEY-05 resume lifecycle (no test file exists for this page today)
- [ ] Framework install: none — both harnesses fully operational

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | Existing OAuth PKCE (Web Crypto, S256) reused untouched; JWT `Depends(get_user_id)` on every new/extended endpoint |
| V3 Session Management | yes | `sessionStorage` (tab-scoped) for the pending-selection stash — contains only `{kind, modelId, threadId, returnTo}`, zero secret material; one-shot lifecycle (Pitfall 6) |
| V4 Access Control | yes | `user_preferences` own-row RLS (migration 032) covers `favorite_models` automatically; `user_id` bound from JWT sub, never the body (existing preferences.py pattern) |
| V5 Input Validation | yes | Pydantic: `use_demo: bool` (coerced/rejected by FastAPI), `favorite_models: list[str] \| None` (recommend size bounds — Open Q3), `Literal` theme untouched |
| V6 Cryptography | yes | Fernet key encryption untouched; decrypted keys remain short-lived per-turn locals (existing SEC-04 discipline — no new key-handling code paths) |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| FE-forged "free" model runs paid on owner key | Tampering | D-03 non-negotiable server guard: `model_cache.is_free is True` or pinned fallback; unknown ≠ free (Pitfall 5) |
| `use_demo:true` while flag OFF mints owner-key spend | Elevation of privilege | Override gated on `settings.demo_fallback_enabled` FIRST; SEC-03 killswitch tests pinned green (Pitfall 4) |
| Key/exception leakage via new UI copy or toasts | Information disclosure | Locked strings only; `${model}` display name is the ONLY interpolation; never a caught error/HTTP body/`sk-or-` fragment (SEC-01 house style, enforced across all Phase 10-14 surfaces) |
| Owner-key cost blowout when flag flips ON | Denial of service (cost) | Bounded both sides (999.2 PASS): app-level flag OFF switch + provider budget guardrail (403 at ~$0.10); demo structurally free-models-only |
| Cross-user favorites write | Tampering | `user_id` from JWT sub in the upsert payload server-side (existing `preferences.py:70-72` pattern); own-row RLS backstop |
| Unbounded favorites array abuse | Denial of service | Recommend Pydantic `max_length` on `favorite_models` (Open Q3) |
| Stash-injected navigation (`returnTo`) | Tampering | `returnTo` is written only by our gate and consumed via `navigate()` (SPA-internal path, not `window.location`); recommend constraining to known paths (`/`, `/settings`) at read time — one-line allowlist |

## Sources

### Primary (HIGH confidence — read/executed this session)
- Live repo code: `ModelSelector.tsx`, `DefaultModelSelector.tsx`, `ConfirmDialog.tsx`, `ErrorMessageBubble.tsx`, `ChatContainer.tsx`, `ChatPage.tsx`, `SettingsPage.tsx`, `OAuthCallbackPage.tsx`, `pkce.ts`, `useKeyStatus.ts`, `useChat.ts`, `ToastContext.tsx`, `DemoPill.tsx`, `chat.py` (resolution :152-207, deprecation :807-852, done event :1181-1195, error taxonomy :1196-1290), `keys.py`, `preferences.py`, `models.py`, `config.py`, `schemas.py`, `model_catalog_service.py` (signatures), migration `20240301000032`, `vitest.config.ts`, `test/utils.tsx`, `ModelSelector.test.tsx`, `test_key_model_resolution.py`
- `GET https://openrouter.ai/api/v1/models/meta-llama/llama-3.3-70b-instruct:free/endpoints` — live curl 2026-07-02 (slug live; Venice endpoint; tools supported; 65,536 context; uptime_last_1d 88.17)
- Tool probes: node v24.15.0, npm 11.12.1, supabase CLI 2.95.4, flyctl present, backend venv present; lucide icons (search/star/key-round/info) present in node_modules; greps confirming `or_pending_selection`/`useKeyGate`/`favorite_models` do not pre-exist
- Planning canon: `15-CONTEXT.md`, `15-UI-SPEC.md` (approved), `999.2-SEC-03-FINDING.md` (PASS), `REQUIREMENTS.md`, `STATE.md`

### Secondary (MEDIUM confidence — official docs via search)
- PostgREST "Working with PostgreSQL data types" (postgrest.org) — 1-D array columns accept JSON arrays and `{a,b}` string form in request bodies ([docs v12](https://docs.postgrest.org/en/v12/how-tos/working-with-postgresql-data-types.html), [stable](https://postgrest.org/en/stable/how-tos/working-with-postgresql-data-types.html))

### Tertiary (LOW confidence, flagged)
- supabase-py list→JSON-array serialization specifically (A1 — near-certain but not executed against a live table this session)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — zero new deps; every reused asset read from disk
- Architecture: HIGH — all seams verified in live code; UI-SPEC locks the contested surface (D-03 display-vs-gate tension) explicitly
- Pitfalls: HIGH — majority derived from concrete code shapes (early returns, effect deps, upsert semantics) rather than general lore; demo-model fragility grounded in a live probe + documented precedent (D-999.1-LLM-A)
- Deploy/ops: MEDIUM-HIGH — mechanics match project memory (repair pattern, dual envs, Fly/CF split); prod migration-history state itself is unverified until the deploy dry-run (Open Q4)

**Research date:** 2026-07-02
**Valid until:** 2026-08-01 for code seams and stack (stable, in-repo); **2026-07-09 for the demo-slug liveness fact** (single-provider free endpoint — re-verify at deploy)
