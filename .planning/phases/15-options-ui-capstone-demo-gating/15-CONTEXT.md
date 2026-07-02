# Phase 15: Options UI Capstone + Demo Gating - Context

**Gathered:** 2026-07-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Close out v1.2: **key-gated model selection** (picking a model with no connected key triggers the OAuth connect flow — KEY-05), **favorite/pin models** (MODEL-08), **demo-fallback enablement + non-dismissible demo banner** (DEMO-01/02, closing SEC-03 on the 999.2 PASS finding), plus the two audit fold-ins living in the same picker surface: **render popular marking** (B-1 / MODEL-03 — data reaches the FE interface unrendered) and **catalog search** (W-1 / MODEL-01 — "searchable" qualifier unmet).

In scope: picker UX upgrade (sections, badges, search, favorites), shared key-gate on both selection surfaces, OAuth resume with pending selection, demo free-model choice for keyless users, demo banner, [Use demo] recovery action, `demo_fallback_enabled=true` prod enablement at the deploy step.

Out of scope: SEC-01 human gates (Phase 11 UAT — separate track), prod migration catch-up 029–032 (deploy-time ops, runs alongside this phase's deploy), FU-A/FU-B/FU-D Phase-14 follow-ups and W-3 notice dedup (backlog unless trivially adjacent), aux/utility-model override UI (deferred since P11), org/team features.

Requirements: KEY-05, MODEL-08, DEMO-01, DEMO-02, SEC-03 (+ MODEL-03/MODEL-01 audit remediation).
</domain>

<decisions>
## Implementation Decisions

### Key-gated selection (KEY-05)
- **D-01:** Keyless user picks a **paid** model → **confirm modal, then OAuth**: small dialog ("Paid models need your OpenRouter key") with [Connect] launching the existing `startOpenRouterConnect()` PKCE helper and [Cancel] keeping the current model. Reuses the `ConfirmDialog` pattern. No instant redirect, no disabled/locked rows.
- **D-02:** **Auto-apply after connect.** The pending model selection is stashed in `sessionStorage` beside the PKCE verifier/state; after a successful exchange the originating surface's action is applied (thread PATCH or default-model PUT) + a small confirmation toast. The user's original intent completes without re-picking.
- **D-03:** **Keyless selectable set depends on the demo flag.** Demo ON: free models are selectable (picker filters via the existing, currently-unused `GET /api/models?free_only=true` param) and demo turns run the **picked** free model — this implements the deferred "demo users picking among free models" plan from Phases 11/12. Paid rows → connect modal (D-01). Demo OFF: **every** selection → connect modal (chat is fail-closed anyway).
  - **Server-side guard (non-negotiable):** the demo resolution branch must validate the selected model is actually free against `model_cache` (never trust the frontend); non-free or unknown → fall back to the pinned `demo_fallback_model`. Owner spend stays $0 structurally.
- **D-04:** **Gate applies to BOTH selection surfaces** — thread-header `ModelSelector` and settings `DefaultModelSelector` — via one shared gate hook/util (same modal, same auto-apply resume). No inconsistent keyless UX between chat and settings.

### Picker upgrade (MODEL-08 + B-1 + W-1)
- **D-05:** **Favorites stored on `user_preferences`** — new `favorite_models` array column (migration 033, next free number). Reuses the existing GET/PUT `/api/preferences` partial-upsert + RLS; no new table, no new endpoint. Read once at picker mount.
- **D-06:** **Sectioned picker: Favorites → Popular → All (alphabetical).** Section headers inside the dropdown; Popular block preserves curated `POPULAR_MODELS` order (`popularity_rank`).
- **D-07:** **Popular marking renders as a "Popular" badge chip on the row** (in addition to the Popular section), mirroring the existing "Free" tag styling at `ModelSelector.tsx:320-323`. This closes audit blocker B-1 (MODEL-03).
- **D-08:** **Search is fuzzy, client-side** over the already-fetched catalog (match on model id + name), debounced input pinned atop the dropdown. Typo-tolerant matching chosen over plain substring. Implementation (hand-rolled subsequence scorer vs a micro-dep like `fuzzysort`) is Claude's discretion — bias to hand-rolled to respect the v1.2 "minimal new FE dep surface" posture. Closes audit W-1 (MODEL-01 "searchable").

### Demo rollout & banner (DEMO-01/02, SEC-03)
- **D-09:** **Enable `demo_fallback_enabled=true` in prod at this phase's deploy step.** SEC-03 gate is discharged: 999.2 finding PASS (guardrail 403-blocked at $0.1026, kill-switch tests green, no-email outcome accepted). Demo runs free models only (D-03 guard), so structural owner cost is $0. This closes DEMO-01 + SEC-03. Flag stays env-driven (no admin UI — project rule).
- **D-10:** **Banner = slim, non-dismissible strip at the top of the chat pane**, rendered whenever the `mode:"demo"` signal (Phase 11 D-08) is present. Copy is LOCKED from Phase 11: "Demo mode — a free model is in use; it may be slower, less accurate, or temporarily rate-limited (no usage left)." Not a pill, not a header-bar banner.
- **D-11:** **[Use demo] lights up on the 403/no-key error bubble when the flag is ON** — wire the existing dead `demoEligible`/`onUseDemo` props (`ErrorMessageBubble` ← `ChatContainer.tsx:122`) to demo-flag state; clicking retries the turn in demo mode.

### Claude's Discretion
- Fuzzy-match implementation (hand-rolled scorer vs micro-dep) per D-08.
- Exact modal copy/layout, toast copy, section-header styling, badge color token, sessionStorage key names for the pending selection, gate hook naming (`useKeyGate` or similar).
- How the frontend learns the demo flag state (ride `GET /api/keys/status`, a config endpoint, or the `mode` signal) — pick the smallest seam.
- Migration 033 exact shape (TEXT[] vs JSONB) following existing user_preferences conventions.
- Whether the Favorites section shows an empty-state hint or hides when empty.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope & gate evidence
- `.planning/ROADMAP.md` — Phase 15 entry (goal, requirements, depends-on 14 + 999.2)
- `.planning/REQUIREMENTS.md` — KEY-05, MODEL-08, DEMO-01, DEMO-02, SEC-03 definitions + traceability; SEC cross-cutting note (SEC-03 = hard gate on the demo flag, discharged by 999.2)
- `.planning/phases/999.2-cost-guardrail-burn-script/999.2-SEC-03-FINDING.md` — the PASS finding D-09 relies on (guardrail block behavior, kill switch, deployment note)
- `.planning/v1.2-MILESTONE-AUDIT.md` — B-1 (MODEL-03 unrendered popularity) + W-1 (MODEL-01 no search) fold-in evidence; W-2/W-3/FU-* explicitly NOT this phase unless adjacent

### Upstream phase contracts this phase consumes
- `.planning/phases/11-per-request-key-model-resolution-chat-loop-seam/11-CONTEXT.md` — D-05..D-09 (demo eligibility, pinned free model, `mode:"demo"` signal, LOCKED banner copy, flag default-OFF + "enabling is Phase 15"), D-12 error taxonomy
- `.planning/phases/14-usage-cost-display-settings-key-state-ux/14-CONTEXT.md` — settings-page composition (D-06/07), typed `ErrorMessageBubble` actions (D-09), tri-state key copy (D-08)
- `.planning/phases/10-oauth-pkce-backend-exchange-frontend-connect/10-CONTEXT.md` — PKCE sessionStorage semantics (verifier + CSRF state survive hard refresh) that D-02's pending-selection stash must coexist with

### Live code to modify / mirror
- `frontend/src/components/ModelSelector.tsx` — the picker (listbox, Free tag at :320-323, `popularity_rank` declared :16 unrendered); D-06/07/08 land here
- `frontend/src/components/DefaultModelSelector.tsx` — settings surface for the shared gate (D-04)
- `frontend/src/lib/pkce.ts` — `startOpenRouterConnect()` (D-01 launch, D-02 stash rides beside its sessionStorage writes)
- `frontend/src/pages/OAuthCallbackPage.tsx` — exchange success = D-02 resume point
- `frontend/src/components/ErrorMessageBubble.tsx` + `frontend/src/components/ChatContainer.tsx:122` — dead `demoEligible`/`onUseDemo` to wire (D-11); banner mount top of chat pane (D-10)
- `frontend/src/hooks/useKeyStatus.ts` — connected-state the gate reads; candidate carrier for demo-flag state
- `backend/routers/models.py` — `?free_only=true` param (built for this phase, unused)
- `backend/routers/chat.py` — demo resolution branch (~:798-852) for the D-03 server-side free-model guard
- `backend/routers/preferences.py` + `supabase/migrations/20240301000032_*.sql` — partial-upsert pattern + table migration 033 extends
- `backend/config.py` — `demo_fallback_enabled`, `demo_fallback_model`, `POPULAR_MODELS`

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `startOpenRouterConnect()` (pkce.ts) — complete PKCE launch; gate modal calls it as-is
- `ConfirmDialog` — existing modal primitive for D-01
- `useKeyStatus` — shared connected/balance store with broadcast refresh; gate reads `connected`
- `GET /api/models?free_only=true` — shipped in Phase 12 explicitly for this phase, zero consumers yet
- `demoEligible`/`onUseDemo` props on ErrorMessageBubble — dead by design, awaiting D-11
- `mode:"demo"` SSE signal + locked notice copy (Phase 11 D-08) — banner just renders it
- `user_preferences` GET/PUT partial-upsert + RLS — favorites column slots in
- vitest + component-test harness (999.1) — picker/gate/banner tests follow existing patterns

### Established Patterns
- Migrations sequential `20240301000NNN_*.sql` — next free: 033; dev first, prod at deploy (D-03 dual-env discipline)
- Backend never trusts FE model choice — resolution/validation server-side (Phase 11 fail-closed three-branch stays intact)
- No admin UI — flags env-driven only
- Frontend deps minimal — bias hand-rolled over new packages

### Integration Points
- Shared gate hook wraps both selectors → ConfirmDialog → pkce launch → OAuthCallbackPage resume → PATCH/PUT apply
- Demo branch in chat.py reads picked model → free-check against model_cache → run or fall back to `demo_fallback_model`
- Banner renders off `mode:"demo"` in useChat state; [Use demo] retry rides existing error-bubble action plumbing
- Deploy step: prod migrations 029–033 + Fly secrets (`DEMO_FALLBACK_ENABLED=true`) + CF rebuild

</code_context>

<specifics>
## Specific Ideas

- Gate modal copy direction: "Paid models need your OpenRouter key" + [Connect] / [Cancel].
- Picker sections labeled Favorites / Popular / All; Popular badge chip visually siblings the existing Free tag.
- Banner is a slim strip, not a pill — non-dismissible per DEMO-02; exact styling Claude's discretion in both themes.
- Fuzzy search: typo-tolerant (user explicitly chose fuzzy over substring); debounced; matches id + name.

</specifics>

<deferred>
## Deferred Ideas

- **W-3 (notice dedup + live visibility)** — deprecated-model notice duplicates + invisible during live turn; separate fix, not picker surface (backlog / quick task).
- **FU-A/FU-B/FU-D (Phase 14 follow-ups)** — balance semantics, post-turn balance refresh, light-mode bubble polish; own track.
- **Aux/utility-model override UI** — plumbing exists since P11 D-02; still deferred (no requirement this milestone).
- **MODEL-F1 "New" badge / MODEL-F2 keyboard-heavy picker nav** — Future Requirements (post-v1.2).
- **SEC-01 human gates + prod migration catch-up** — run alongside this phase's deploy, tracked by the audit, not phase-15 build scope.

</deferred>

---

*Phase: 15-options-ui-capstone-demo-gating*
*Context gathered: 2026-07-02*
