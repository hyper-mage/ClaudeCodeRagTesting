---
phase: 13-preferences-per-thread-model
plan: 06
status: complete
subsystem: ui
tags: [react, vite, tailwind, model-selector, theme, vitest, sse, preferences]

requires:
  - phase: 13-03
    provides: GET/PUT /api/preferences + PATCH /api/threads/{id} {model} endpoints
  - phase: 13-04
    provides: at-send deprecated-model fallback writing role='notice' rows
  - phase: 13-05
    provides: ModelSelector + ThemeToggle primitives + applyStoredTheme + index.css core-surface tokens
provides:
  - Per-thread model selector header row in ChatContainer (PATCH /api/threads/{id}, 'Default model' sub-state, set/null-clear)
  - DefaultModelSelector wrapper (PUT /api/preferences {default_model}) + ThemeToggle in sidebar footer + mobile drawer
  - DeprecationNotice render for role='notice' message rows (quiet system line, not a bubble, not red)
  - Post-login theme reconcile (GET /api/preferences vs localStorage — server wins)
  - D-01 light-mode tokens applied to the four core surfaces (chat, sidebar, login, composer)
affects: [phase-14-usage-cost-settings, phase-15-rich-picker]

tech-stack:
  added: []
  patterns:
    - "Self-contained PUT in the control (DefaultModelSelector mirrors ThemeToggle's fire-and-forget PUT)"
    - "Shared catalog fetched once in ChatPage and passed as a `models` prop so selectors resolve names synchronously (no per-selector fetch)"
    - "Optimistic local-state mirror on PATCH per-thread model; the echo row is authoritative on reload"
    - "Server-wins theme reconcile via applyStoredTheme after GET /api/preferences (one-frame snap acceptable, D-02)"

key-files:
  created:
    - frontend/src/components/DeprecationNotice.tsx
    - frontend/src/components/DeprecationNotice.test.tsx
    - frontend/src/components/DefaultModelSelector.tsx
    - frontend/src/components/DefaultModelSelector.test.tsx
  modified:
    - frontend/src/components/ChatContainer.tsx
    - frontend/src/components/ChatContainer.test.tsx
    - frontend/src/components/ThreadSidebar.tsx
    - frontend/src/components/MobileDrawer.tsx
    - frontend/src/pages/ChatPage.tsx
    - frontend/src/hooks/useChat.ts

key-decisions:
  - "DefaultModelSelector self-PUTs /api/preferences {default_model} (cohesion, mirroring ThemeToggle) and also notifies the parent via onChange so ChatPage's inline value stays in sync without a refetch."
  - "ChatPage fetches /api/models once and threads the catalog into both the per-thread and default selectors as a `models` prop — names resolve synchronously, no duplicate fetches."
  - "Per-thread model change is optimistic (local threads[] mirror) then PATCH; a failed PATCH surfaces a generic toast + Sentry, house-style copy."
  - "[Rule 1] ChatPage only setModels when the /api/models payload is an array — a malformed/non-array response previously crashed ModelSelector's rows.map."

patterns-established:
  - "Notice rows: role='notice' is carried through useChat.loadMessages unchanged (already spreads role/content) and rendered via a dedicated ChatContainer branch — no special server handling."
  - "Header row is a shrink-0 sibling above the flex-1 scroll area so ChatContainer's flex-1 flex flex-col h-full layout is preserved."

requirements-completed: [MODEL-05, MODEL-06, PREF-02]

duration: ~25min
completed: 2026-06-25
---

# Phase 13 Plan 06: Per-Thread + Default Model Selectors, Theme Toggle, Deprecation Notice Summary

**Wired the Plan-05 primitives into real surfaces — a new ChatContainer header row hosting the per-thread ModelSelector (PATCH /api/threads/{id} with the 'Default model' sub-state), a DefaultModelSelector + ThemeToggle in the sidebar footer + mobile drawer (PUT /api/preferences), DeprecationNotice rendering for role='notice' rows, post-login server-wins theme reconcile, and the D-01 light palette on the four core surfaces — all jsdom-testable behaviors green. Ends at a blocking human-verify checkpoint for the visual/FOUC/live-PATCH behaviors jsdom cannot assert.**

> STATUS: AUTONOMOUS TASKS COMPLETE — PLAN NOT YET COMPLETE. Tasks 1-3 (all wiring + unit
> suites) are done and committed. Task 4 is a **blocking human-verify checkpoint** (light-mode
> coherence on the four core surfaces, FOUC-free hard reload, live PATCH/PUT wiring) that a real
> browser is required for. The phase UI side is NOT marked complete until the human approves.

## Performance

- **Duration:** ~25 min (autonomous tasks)
- **Started:** 2026-06-25T09:50:00Z (approx)
- **Completed (autonomous tasks):** 2026-06-25T10:00:00Z (approx)
- **Tasks:** 3 of 4 (Task 4 = pending human-verify checkpoint)
- **Files modified:** 10 (4 created, 6 modified)

## Accomplishments

- **DeprecationNotice (D-06/SC#4):** role='notice' rows render as a quiet centered Info-icon + Caption line — NOT a bubble, NOT red, theme-aware (light gray-100/gray-700, dark gray-800/gray-300). Escaped React text only (no dangerouslySetInnerHTML — T-13-XSS-NOTICE). Message role unions extended ('notice') in both useChat and ChatContainer.
- **Per-thread selector header row (MODEL-06/D-05):** new shrink-0 h-12 row in ChatContainer (only when activeThreadId set), 'Model for this chat' label + ModelSelector with the 'Use my default model' clear row. Trigger shows 'Default model' sub-state when threadModel is null; select → onThreadModelChange(id) → ChatPage PATCH /api/threads/{id} {model}; clear → PATCH {model:null}. Preserves the flex-1 flex flex-col h-full layout.
- **DefaultModelSelector + ThemeToggle (D-04):** the default-model control (LOCKED heading + helper, self-PUTs /api/preferences {default_model}) and the theme toggle live in the desktop sidebar footer and the mobile drawer.
- **Theme reconcile (Pitfall 6):** ChatPage GETs /api/preferences on mount; if the server theme differs from the localStorage-painted theme, the server wins (re-write localStorage + applyStoredTheme). The default_model hydrates from the same GET.
- **D-01 light palette:** core-surface light tokens applied to chat (ChatContainer/ChatPage), sidebar (ThreadSidebar), mobile drawer, and the controls — no orphan gray-950 panels in the wired surfaces. (LoginPage light styling + live visual coherence verified at the checkpoint.)
- **Suite:** full frontend suite 9 files / 54 tests green (was 7/41); `npm run build` (tsc strict + vite) clean.

## Task Commits

1. **Task 1: DeprecationNotice + role 'notice' render** - `3cbeb99` (feat) — RED+GREEN combined; DeprecationNotice.test.tsx 5 green.
2. **Task 2: per-thread header row + DefaultModelSelector + ThemeToggle + theme reconcile** - `b6e6700` (feat) — DefaultModelSelector.test.tsx 3 green; npm run build clean.
3. **Task 3: extend ChatContainer suite + catalog payload guard** - `5712a8d` (test) — ChatContainer 5 new cases; full suite 54 green; includes the Rule 1 array-guard fix.

**Task 4:** pending — blocking human-verify checkpoint (no commit; the phase metadata commit / STATE+ROADMAP advance is deferred until approval).

## Files Created/Modified

- `frontend/src/components/DeprecationNotice.tsx` - quiet persisted system notice line (Info icon + Caption), theme-aware, escaped text.
- `frontend/src/components/DeprecationNotice.test.tsx` - 5 cases (verbatim copy, info icon, not-bubble, not-red, XSS-inert).
- `frontend/src/components/DefaultModelSelector.tsx` - default-model control (heading + helper) self-PUTting /api/preferences {default_model}, notifies parent via onChange.
- `frontend/src/components/DefaultModelSelector.test.tsx` - 3 cases (heading/helper copy, PUT body, onChange).
- `frontend/src/components/ChatContainer.tsx` - new per-thread header row (shrink-0 h-12), 'notice' render branch, D-01 chat-area light tokens, new props (activeThreadId/threadModel/onThreadModelChange/models).
- `frontend/src/components/ChatContainer.test.tsx` - existing renders updated for new props + 5 new MODEL-06/notice cases; api boundary mocked.
- `frontend/src/components/ThreadSidebar.tsx` - optional footer slot + D-01 light-surface tokens (gray-50/gray-200).
- `frontend/src/components/MobileDrawer.tsx` - panel D-01 light-surface tokens.
- `frontend/src/pages/ChatPage.tsx` - Thread.model; one-time /api/models + /api/preferences fetch; server-wins theme reconcile; handleThreadModelChange PATCH; mount prefs controls in sidebar footer + drawer; root light token; array-guard on catalog payload.
- `frontend/src/hooks/useChat.ts` - Message role union extended with 'notice'.

## Decisions Made

See key-decisions frontmatter. Notable: the catalog is fetched once in ChatPage and threaded down as a `models` prop (synchronous name resolution, no duplicate /api/models fetches); the per-thread PATCH is optimistic with a generic-toast+Sentry failure path.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Guard the /api/models catalog payload to an array before setModels**
- **Found during:** Task 3 (full-suite wave-merge gate).
- **Issue:** ChatPage's catalog effect did `setModels(data ?? [])`. When the response was a non-nullish non-array (e.g. `{messages:[]}` returned by ChatPage.test.tsx Test 5's catch-all mock for unrouted paths like /api/models), `models` became a non-array object and ModelSelector crashed on `rows.map` — failing a pre-existing 999.1 ChatPage test.
- **Fix:** Only `setModels(...)` when `Array.isArray(data)`; otherwise leave `models` undefined so each ModelSelector falls back to its own lazy fetch + error UI. Defensive per T-13-CRASH.
- **Files modified:** frontend/src/pages/ChatPage.tsx
- **Verification:** ChatPage.test.tsx 8/8 green; full suite 54 green; tsc strict clean.
- **Committed in:** `5712a8d` (Task 3 commit).

---

**Total deviations:** 1 auto-fixed (1 bug).
**Impact on plan:** The fix is a correctness/robustness requirement (a malformed catalog response must never crash the chat surface). No scope creep.

## Issues Encountered

- The new required ChatContainer props broke the existing ChatContainer.test.tsx renders — updated all four existing render calls with the new props (Task 2), then added the 5 new MODEL-06/notice cases (Task 3).
- The role='notice' bubble-exclusion assertion initially over-matched (the composer's blue-600 Send CTA lives inside ChatContainer) — scoped the assertion to the notice line element instead of the whole container.

## Known Stubs

None — all controls are wired to real endpoints (PATCH /api/threads/{id}, PUT/GET /api/preferences, GET /api/models). The catalog/prefs/theme all hydrate from live fetches.

## Pending Checkpoint (Task 4 — blocking human-verify)

The jsdom-unobservable behaviors require a real browser. After `npm run dev` (frontend) + backend, logged in (test creds in CLAUDE.md):

1. **THEME:** toggle to light via the sidebar ThemeToggle; inspect chat area, sidebar, composer (ChatInput), and login page for coherent light styling, AA-readable muted text, and NO orphan dark (gray-950) panels bleeding through (D-01). Toggle back to dark and confirm it still reads correctly.
2. **FOUC:** with light selected, hard-refresh (Ctrl/Cmd-R), ideally throttled — confirm NO dark flash before first paint (the inline index.html script applies the class pre-mount; Pitfall 5).
3. **CROSS-DEVICE (optional):** confirm theme persists after reload (localStorage) and GET /api/preferences reconcile would win on a fresh device (one-frame snap acceptable per D-02).
4. **PER-THREAD MODEL:** open an active thread, pick a model in the header selector → trigger updates and (network tab) PATCH /api/threads/{id} {model} fires; pick 'Use my default model' → PATCH {model:null} and the trigger shows 'Default model'.
5. **DEFAULT MODEL:** set a default via the sidebar control → PUT /api/preferences {default_model}; reload → the selector shows the persisted default.

NOTE: the live LLM round-trip on a chosen model is separately deferred (D-999.1-LLM-A — :free-model provider error). Do NOT block this checkpoint on a streamed answer; verify the PATCH/PUT + resolution wiring, not necessarily a completed completion.

**Resume signal:** type "approved" once light-mode coherence + FOUC-free reload + the PATCH/PUT wiring are confirmed, or describe issues (e.g. a dark panel bleeds through, a flash on reload) to fix.

## Next Phase Readiness

- On approval: this completes the MODEL-05 / MODEL-06 / PREF-02 UI side; Phase 14 absorbs the temporary default-model + theme placements into the settings page and adds usage/cost display.
- Blocker (carried): live LLM round-trip on the :free model deferred (D-999.1-LLM-A) — orthogonal to this plan's PATCH/PUT wiring.

## Self-Check: PASSED

- Created files all FOUND: DeprecationNotice.tsx, DeprecationNotice.test.tsx, DefaultModelSelector.tsx, DefaultModelSelector.test.tsx.
- Task commits all FOUND: `3cbeb99`, `b6e6700`, `5712a8d`.

---
*Phase: 13-preferences-per-thread-model*
*Autonomous tasks completed: 2026-06-25 — Task 4 human-verify checkpoint pending*

---

## Human-verify outcome (2026-06-25) — APPROVED

The user ran the live stack and **approved** Task 4. Three issues were found during verification and fixed inline before approval (all on master, full fe suite stayed green):

1. **Dropdown clipped behind the UI** (`a8dcf9b`) — `ModelSelector` opened downward only, so the sidebar-footer default-model selector spilled off-screen. Now measures the trigger on open and renders the panel **above** it (`bottom-full`) when there isn't room below; the chat-header selector still drops down.
2. **Light mode only covered chat surfaces** (`77bcf1a`) — extended the light palette to the persistent `IconSidebar` rail, `DocumentsPage` + tree sidebar, `DocumentList`, and `MobileTopBar` (converted hardcoded dark classes to the light-default + `dark:` override pattern). NOTE: the `/settings` page content itself is **Phase 14** (PREF-01) — only the rail's Settings button is themed here.
3. **Silent-empty dropdown** (`3eed48a`) — `ChatPage` seeds `models` to `[]` and passes it down before its one-time fetch resolves; `[]` is truthy, so `ModelSelector` pinned a message-less `loaded` state and never lazy-fetched. Now treats an empty `models` prop as "no catalog" (lazy-fetch on open) and renders an explicit `No models available.` empty-state. +2 regression tests (ModelSelector now 10 tests).

Post-fix: ModelSelector 10/10, full frontend suite 56 tests green, `tsc -b` + eslint clean. User confirmed the dropdown lists models and the per-thread/default selectors are usable. The live LLM round-trip on a chosen model remains separately deferred (D-999.1-LLM-A — `:free`-model provider error), per plan.
