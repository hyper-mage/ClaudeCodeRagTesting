# Phase 13: Preferences + Per-Thread Model - Context

**Gathered:** 2026-06-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 13 delivers the **persist + write + UI side** of user model/theme preferences. The chat-path *read* side already exists (Phase 11's schema-tolerant three-tier resolution).

In scope:
- `user_preferences` table (per-user row: `default_model`, `theme`) + per-user RLS — new schema.
- `threads.model` column — new schema.
- Backend: `GET`/`PUT /api/preferences`; `PATCH /api/threads/{id}` (set per-thread model).
- Frontend: default-model selector, per-thread model selector, light/dark theme toggle (persisted server-side + localStorage-mirrored for flash-free first paint).
- Deprecated-model fallback at send time with a user-visible notice (SC#4).

Out of scope (other phases):
- The **rich** model picker — favorites/pinning, key-gated selection — is **Phase 15** (MODEL-08, KEY-05, SEC-03). P13 ships a *minimal functional* selector only.
- The **settings/account page** (PREF-01) is **Phase 14**. P13 places the default-model control in a temporary inline spot until P14 absorbs it.
- Usage/cost display (COST-*) is Phase 14.

Requirements: MODEL-05 (set default model), MODEL-06 (per-thread model, persisted on thread), PREF-02 (toggle light/dark, persisted per user).
</domain>

<decisions>
## Implementation Decisions

### Theme scope (PREF-02)
- **D-01:** Ship a **usable light palette on the core surfaces** (chat, sidebar, login, composer) — wire the theme mechanism (root class / CSS variables) plus a real light palette where it matters. Pixel-polish on secondary UI is deferred. Rationale: app is currently dark-only (no `dark:` variants, hardcoded gray palette); a toggle that produces a broken/ugly light mode is bad UX, but full-app re-theming overlaps P14/P15 work. Meets SC#3 (persist + flash-free) with a toggle that looks right where users actually spend time.
- **D-02:** Theme persists server-side in `user_preferences.theme` AND mirrors to `localStorage` so first paint is flash-free (no FOUC) before the preferences fetch resolves.

### Model selector UX + placement
- **D-03:** Per-thread model selector = a **compact dropdown in the active thread's header**, reusing Phase 12 `model_cache` catalog data (searchable list, free/paid, price/context hints). Minimal, NOT the P15 rich picker (no favorites/pinning/key-gating here).
- **D-04:** Default-model control uses the **same minimal selector component in a small temporary inline spot** (sidebar/header menu) until the Phase 14 settings page exists and absorbs it.

### New-thread model inheritance
- **D-05:** On thread create, `threads.model` is left **null** → resolution falls through to `user_preferences.default_model` (matches the existing tolerant chain at `chat.py:174-175`). The thread always tracks the user's *current* default. The column is only written when the user **explicitly** picks a per-thread model. No snapshot of the default onto the row.

### Deprecated-model fallback notice (SC#4)
- **D-06:** When a thread is pinned to a model that is **absent from the Phase 12 `model_cache` at send time**, resolution falls back to the user's default and the user is told via an **inline thread notice message** (a non-AI system/notice line, e.g. "Model X is no longer available — using <default> instead"). Chosen over toast/banner because it persists in thread context and is visible on reload. Must not crash the thread.

### Claude's Discretion
- Preferences API row shape (single upsert row per user), exact migration split (one combined migration vs `user_preferences` + `threads.model` separately), CSS-variable vs Tailwind `dark:`-class strategy for theming, and the precise wording/styling of the deprecation notice line — planner/researcher decide.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope & requirements
- `.planning/ROADMAP.md` § "Phase 13: Preferences + Per-Thread Model" — goal + 4 success criteria (the SC#4 deprecation-fallback requirement is easy to miss).
- `.planning/REQUIREMENTS.md` — MODEL-05, MODEL-06, PREF-02 (and the traceability table assigning them to Phase 13).

### Upstream phase decisions this phase plugs into
- `.planning/phases/11-per-request-key-model-resolution-chat-loop-seam/11-CONTEXT.md` — the three-tier resolution contract P13 feeds.
- `.planning/phases/12-model-cache-catalog/12-CONTEXT.md` — `model_cache` shape; the catalog data the selectors reuse and the source of truth for "is this model deprecated".

### Live code that already reads these prefs (do NOT rebuild — verify + wire the write side)
- `backend/routers/chat.py:122-148` — `_safe_thread_model` + `_safe_user_default_model` (read `thread.model` / `user_preferences.default_model`, tolerant of the absent P13 schema).
- `backend/routers/chat.py:160-175` — `_resolve_key_and_model` three-tier order: `body.model? → thread.model? → user_preferences.default_model? → owner default`.
- `supabase/migrations/20240301000030_create_model_cache.sql` and `..._000031_allow_null_model_cache_name.sql` — model catalog source.

No external/vendor specs — requirements fully captured above.
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **Phase 12 `model_cache` + models router** (`backend/routers/models.py`, imported in `backend/main.py:9`): catalog source for both selectors AND the deprecation check (model absent from cache → deprecated).
- **`backend/routers/chat.py` resolution helpers** (`_safe_thread_model`, `_safe_user_default_model`, `_resolve_key_and_model`): already consume `threads.model` + `user_preferences.default_model`; P13 only needs to make the schema real and add the write endpoints — minimal-to-no change to resolution logic (verify the now-present table/column still resolve correctly).
- **`backend/routers/threads.py`**: thread read already does `SELECT *` (so `model` rides along for free once the column exists); add `PATCH /api/threads/{id}` for per-thread model.
- **Frontend chat surfaces** from Phase 999.1 — `frontend/src/pages/ChatPage.tsx`, `frontend/src/components/ChatContainer.tsx`, `frontend/src/hooks/useChat.ts`, thread sidebar/header, `ToastProvider`, `AuthContext` — integration points for the selectors, theme toggle, and the inline deprecation notice.

### Established Patterns
- **Per-user RLS on every table** (project rule) — `user_preferences` needs per-user RLS; `threads.model` inherits existing `threads` RLS.
- **Sequential timestamped migrations** — latest is `...000031`; next migrations continue the series.
- **Pydantic models + FastAPI `Depends(user_id)`** for API routes; backend uses the service-role client.
- **Tailwind v4** via `@tailwindcss/vite`; the app currently hardcodes a dark palette with **no `dark:` variants and no ThemeProvider** — theming is greenfield wiring.

### Integration Points
- Resolution chain (`chat.py`) — already wired; P13 supplies real data.
- Thread create path (Phase 999.1 auto-create-on-send) — must leave `threads.model` null per D-05.
- Send path — the deprecation check + inline notice (D-06) hooks in at send time against `model_cache`.
</code_context>

<specifics>
## Specific Ideas

- Deprecation notice copy direction: "Model X is no longer available — using <default> instead" as an inline thread notice line (not a toast).
- Theme must not flash (FOUC): localStorage mirror read on first paint, before the `/api/preferences` round-trip.
</specifics>

<deferred>
## Deferred Ideas

- **Rich model picker** (favorites/pinning, key-gated selection, demo banner) — **Phase 15** (MODEL-08, KEY-05, SEC-03, DEMO-01/02).
- **Settings/account page** consolidating key status + default model + theme + profile — **Phase 14** (PREF-01). P13's temporary default-model control migrates here.
- **Usage/cost display** (per-message cost, balance, low-balance warning, per-thread totals) — **Phase 14** (COST-01..04).

None of the discussion strayed outside the Phase 13 boundary; the above were explicitly scoped to their owning phases.
</deferred>

---

*Phase: 13-preferences-per-thread-model*
*Context gathered: 2026-06-24*
