# Phase 14: Usage/Cost Display + Settings/Key-State UX - Context

**Gathered:** 2026-06-25
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 14 delivers the **read + render + settings-consolidation side** of cost/usage and key-state UX. The backend capture side already exists (Phase 11: `messages.usage` JSONB persisted, summed across the tool loop; `done` SSE event carries `usage` + `mode:"demo"`; structured error taxonomy `no_api_key` / `rate_limit` / `payment_required`). The `/settings` stub (connect/status/disconnect + masked label + `connected_at`) exists from Phase 10. P14 surfaces all of it and grows the settings page.

In scope (COST-01, COST-02, COST-03, COST-04, PREF-01):
- **Per-message cost display** — muted cost+token line under each assistant bubble; read from persisted `messages.usage` / `done` event. Shown as reported, never recomputed.
- **Per-thread running cost total** — in the thread header; summed from persisted `messages.usage` across the thread (survives reload).
- **Balance** — NEW `GET /api/keys/balance` proxying OpenRouter `GET /api/v1/key`; tolerates null `limit_remaining` (pay-as-you-go). Fetched on demand (settings open / after a turn).
- **Low-balance warning** — configurable threshold; surfaced via amber header key indicator + settings warning line.
- **Settings/account page (PREF-01)** — grow the P10 `/settings` stub into the full page: OpenRouter (tri-state key status + masked label + balance + disconnect), Default model, Theme. Absorbs P13's temporary inline default-model + theme controls.
- **Mid-chat key-failure recovery (SC#4)** — 401/402/403 surfaced as in-thread recoverable actions.

Out of scope (other phases):
- Rich model picker (favorites/pinning, key-gated selection, demo banner UI) — **Phase 15** (MODEL-08, KEY-05, SEC-03, DEMO-01/02).
- Enabling `demo_fallback_enabled` in prod — **Phase 15**, gated on SEC-03 / backlog 999.2.
- Backend usage *capture* / persistence — **done in Phase 11** (migration 029). P14 only reads.

Requirements: COST-01 (per-message cost), COST-02 (balance), COST-03 (low-balance warning), COST-04 (per-thread total), PREF-01 (settings/account page).
</domain>

<decisions>
## Implementation Decisions

### Cost display placement (COST-01, COST-04)
- **D-01:** **Per-message cost = an always-visible muted line under each assistant bubble** (e.g. `$0.0021 · 1.2k tok`). Not hover-only — maximum transparency. Read from `messages.usage` (persisted) and from the live `done` SSE event mid-stream.
- **D-02:** **Per-thread running total lives in the thread header** (e.g. `Σ $0.0142`), always visible. **Computed by summing persisted `messages.usage.cost` across the thread** so it is correct on reload — not a session-only live accumulator. (Live turn updates may add to it optimistically, but the source of truth is the persisted sum.)
- Display cost exactly as OpenRouter reports it (`usage.cost`), never recomputed client-side (locked by ROADMAP SC#1 + Phase 11 D-04).

### Low-balance warning (COST-02, COST-03)
- **D-03:** **Threshold is configurable** — a backend config field (e.g. `LOW_BALANCE_THRESHOLD_USD`, default `1.00`). Warn when remaining credit `< threshold`.
- **D-04:** **Null `limit_remaining` (pay-as-you-go, no cap) → no warning.** There is no "remaining" to measure for uncapped accounts; skip the warning entirely rather than inventing one. `GET /api/keys/balance` must tolerate null `limit_remaining` gracefully (ROADMAP SC#2).
- **D-05:** **Warning surfaces two non-intrusive ways:** (1) the always-visible header key indicator turns **amber/warning-colored** when low; (2) the settings page shows a clear warning line near the balance (e.g. `⚠ Balance low: $0.40 — add credits`). No toast spam, no blocking banner.

### Settings page composition (PREF-01)
- **D-06:** **Move both the default-model control AND the theme toggle into the Settings page** as proper sections; **remove their temporary inline mounts** (`ChatPage.tsx:176` `<DefaultModelSelector>`, `ChatPage.tsx:179` `<ThemeToggle>`). This fulfills Phase 13 D-04 ("temporary spot until P14 absorbs it"). Settings page sections: **OpenRouter** (tri-state key status + masked label + balance + disconnect) · **Default model** · **Theme**.
- **D-07:** **The per-thread model selector STAYS in the thread header** — it is a distinct control from the default-model setting and does not move to Settings.
- **D-08:** **Tri-state key status copy** on the Settings OpenRouter section (locked by ROADMAP SC#4): `"Demo mode"` vs `"Your key: connected"` (+ masked label + `connected_since` + balance) vs `"No key — connect to chat"`. The `mode:"demo"` signal already rides the SSE/response from Phase 11 D-08 — read it, don't re-derive.

### Mid-chat key-failure recovery (PREF-01, SC#4)
- **D-09:** **Surface 401/402/403 as an in-thread `ErrorMessageBubble` with action button(s) keyed to the error type**: `no_api_key`/401 → **[Reconnect]**; `payment_required`/402 → **[Add credits ⇗]** (link to OpenRouter) + **[Reconnect]**; 403 → **[Reconnect]** / **[Use demo]**. Persists in thread history, survives reload, reuses the existing structured error taxonomy (Phase 11 D-12) and the in-thread error component. **NOT** a toast (ephemeral) or blocking modal.
- ⚠ **Implementation note for planner:** `ErrorMessageBubble` currently only accepts `{ onRetry, isStreaming }` with a single generic retry button (`frontend/src/components/ErrorMessageBubble.tsx:3-15`). P14 must extend it (or add a typed variant) to render error-type-specific copy + the mapped action buttons above.

### Claude's Discretion
- Exact `LOW_BALANCE_THRESHOLD_USD` config field name + default value; `GET /api/keys/balance` response shape and the `useKeyStatus`/new-hook surface for balance; settings-section ordering and visual layout; precise copy wording; whether per-thread total is a separate selector vs derived in `useChat`; exact amber color token; whether balance refresh-after-turn is debounced/cached — planner/executor decide following existing conventions.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope & requirements
- `.planning/ROADMAP.md` § "Phase 14: Usage/Cost Display + Settings/Key-State UX" — goal + 4 success criteria (SC#1 cost-as-reported, SC#2 null-`limit_remaining` tolerance, SC#3 low-balance + per-thread total, SC#4 tri-state key status + mid-chat recovery).
- `.planning/REQUIREMENTS.md` — COST-01, COST-02, COST-03, COST-04, PREF-01 (definitions + traceability table assigning them to Phase 14).

### Upstream phase decisions this phase reads/renders
- `.planning/phases/11-per-request-key-model-resolution-chat-loop-seam/11-CONTEXT.md` — D-04 (usage capture/persist contract — P14 reads), D-08 (`mode:"demo"` signal + demo notice copy), D-12 (429 vs 402 structured error taxonomy `no_api_key`/`rate_limit`/`payment_required`).
- `.planning/phases/10-oauth-pkce-backend-exchange-frontend-connect/10-CONTEXT.md` — `/settings` stub (D-01), masked-label + `connected_at` (D-03), disconnect/reconnect (D-08/09), header connection dot. P14 grows the stub and recolors the dot.
- `.planning/phases/13-preferences-per-thread-model/13-CONTEXT.md` — D-04 (default-model control is in a temp spot "until P14 absorbs it"), theme (D-01/02), per-thread selector (D-03).

### Live code to read / modify / mirror
- `supabase/migrations/20240301000029_add_usage_to_messages.sql` — the `messages.usage` JSONB column P14 reads (prompt/completion/total tokens + `cost`).
- `backend/routers/chat.py:106-119` (`_accumulate_usage`), `:757`, `:918-921`, `:1169-1189` — usage summed across the tool loop, written to the assistant message + carried on the `done` event.
- `backend/routers/keys.py` — existing `/openrouter/exchange`, `/status`, `DELETE` endpoints; ADD `GET /api/keys/balance` here (proxy OpenRouter `GET /api/v1/key` via `httpx` using the decrypted key; tolerate null `limit_remaining`).
- `backend/config.py` — `Settings`; add the configurable low-balance threshold field.
- `frontend/src/pages/SettingsPage.tsx` — the P10 stub to grow (currently OpenRouter connect/status/disconnect only).
- `frontend/src/pages/ChatPage.tsx:176,179` — temp `<DefaultModelSelector>` + `<ThemeToggle>` mounts to REMOVE (relocate to SettingsPage per D-06).
- `frontend/src/components/ErrorMessageBubble.tsx` — extend for typed recovery actions (D-09).
- `frontend/src/hooks/useKeyStatus.ts` — key-status hook to extend for balance / amber-low state.
- `frontend/src/hooks/useChat.ts` — consumes the `done` SSE event (line ~232) + structured errors; per-message usage + mid-chat error actions wire here.
- `frontend/src/components/MessageBubble.tsx` — where the per-message cost line attaches.
- `frontend/src/components/IconSidebar.tsx` / chat header — the persistent key indicator dot (recolor amber when low).

No external/vendor specs beyond OpenRouter's `GET /api/v1/key` balance endpoint — requirements fully captured above.
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`messages.usage` JSONB (migration 029, Phase 11)** — durable per-turn usage incl. `cost`. Per-message display (D-01) and per-thread sum (D-02) both read this. No backend re-plumbing.
- **`done` SSE event + `_accumulate_usage` (chat.py)** — carries the summed live usage to the frontend for the just-completed turn.
- **Structured error taxonomy (Phase 11 D-12)** — `no_api_key` / `rate_limit` / `payment_required`; `useChat.ts` already handles the in-band error path. D-09 maps these to action buttons.
- **`/settings` stub + `useKeyStatus` + masked label + `connected_at` (Phase 10)** — grown, not rebuilt.
- **`DefaultModelSelector` + `ThemeToggle` components (Phase 13)** — relocate into SettingsPage (D-06); components exist, only their mount point moves.
- **`ErrorMessageBubble`, `ConfirmDialog`, `DemoPill`, `ToastProvider`** — existing UI primitives.
- **`httpx` (backend)** — used for the new balance proxy call to OpenRouter.

### Established Patterns
- New backend endpoints: `@router` + `Depends(get_user_id)` + service-role `get_supabase()`; balance endpoint decrypts the user's key via Phase 9 `crypto_service` and calls OpenRouter server-side (key never crosses to the browser).
- Per-user RLS already covers `messages` / `user_api_keys`; balance is fetched live, not stored.
- Frontend: `apiFetch` (Supabase bearer), hooks return destructured objects, Tailwind v4 with theme variables from Phase 13.
- Config via `pydantic-settings` `Settings` + `.env` (dual dev/prod envs).

### Integration Points
- `messages.usage` → per-message line (MessageBubble) + per-thread header total (sum in useChat/thread view).
- `GET /api/keys/balance` → `useKeyStatus` (or sibling hook) → settings balance + header amber-low state.
- Structured SSE errors → `useChat` → `ErrorMessageBubble` typed actions.
- ChatPage temp mounts removed → SettingsPage sections added.
</code_context>

<specifics>
## Specific Ideas

- Per-message line format direction: `$0.0021 · 1.2k tok` (muted, under the assistant bubble).
- Thread-header total: `Σ $0.0142`.
- Low-balance settings copy: `⚠ Balance low: $0.40 — add credits`; header dot goes amber.
- Recovery copy by type: 402 → `Your key is out of credit (402).` + `[Add credits ⇗] [Reconnect]`.
- Tri-state key copy: `Demo mode` / `Your key: connected` / `No key — connect to chat`.
- **Phase has a UI hint (ROADMAP "UI hint: yes")** — consider `/gsd:ui-phase 14` after planning to produce a UI-SPEC for the settings page + cost lines + recovery bubble + amber indicator.
</specifics>

<deferred>
## Deferred Ideas

- **Rich model picker** (favorites/pinning, key-gated selection that launches OAuth inline, demo banner UI) — **Phase 15** (MODEL-08, KEY-05, SEC-03, DEMO-01/02).
- **Enabling `demo_fallback_enabled` in prod** — **Phase 15**, gated on SEC-03 / backlog 999.2 (cost-guardrail trip-test + kill switch).
- **Profile section on settings** (name/avatar beyond key/model/theme) — not required by PREF-01's core; only the key/model/theme/profile-status surface is in scope. Richer profile editing deferred unless a later requirement asks.

None of the discussion strayed outside the Phase 14 boundary; the above were explicitly scoped to their owning phases.
</deferred>

---

*Phase: 14-usage-cost-display-settings-key-state-ux*
*Context gathered: 2026-06-25*
