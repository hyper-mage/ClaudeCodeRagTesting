---
phase: 15-options-ui-capstone-demo-gating
plan: 04
subsystem: ui
tags: [react, vitest, fuzzy-search, combobox, a11y, model-picker, testing-library]
requires:
  - phase: 15-01
    provides: "GET /api/preferences returns favorite_models: string[] (read once at picker mount)"
provides:
  - "frontend/src/lib/fuzzy.ts — hand-rolled scorer (fuzzyScore/matchModel), locked ranking: substring > boundary > subsequence span, null = removed"
  - "ModelSelector as a sectioned searchable combobox: Favorites → Popular → All models (D-06), Popular chip on every ranked instance (D-07, closes B-1/MODEL-03)"
  - "LOCKED combobox a11y contract live: input focus on open, aria-autocomplete/aria-controls/aria-activedescendant, header-skipping arrow-nav (closes W-1/MODEL-01)"
affects:
  - "15-06 (favorite star toggle + PUT + Shift+Enter land on these sectioned rows)"
  - "15-05/15-07 (both picker surfaces share this one component)"
tech-stack:
  added: []
  patterns:
    - "Section-scoped React keys/DOM ids (`${section}:${id}` / `-opt-${section}-${index}`) for deliberate row duplication across sections"
    - "Sync fireEvent + act(vi.advanceTimersByTime) for debounce tests — RTL 16 async wrapper hangs under vitest fake timers (jest-only detection)"
key-files:
  created:
    - frontend/src/lib/fuzzy.ts
    - frontend/src/lib/fuzzy.test.ts
  modified:
    - frontend/src/components/ModelSelector.tsx
    - frontend/src/components/ModelSelector.test.tsx
key-decisions:
  - "Empty sections render nothing generally (header with zero rows is meaningless); Favorites hidden-when-empty is the LOCKED case"
  - "Seed effect deps are [open, state] (not options.length) — lazy-fetch open still seeds the selected row, keystrokes never re-seed (Pitfall 2)"
  - "activeIndex reset/clamp happens inside the 150ms debounce tick alongside setDebouncedQuery (avoids a setState-in-effect chain)"
  - "Query resets on every open (cmdk convention) — both live and applied values, so a stale filter can never flash"
duration: ~35min active (split across a session-limit pause)
completed: 2026-07-06
---

# Phase 15 Plan 04: Sectioned + Searchable ModelSelector Summary

**Sectioned, fuzzily-searchable ModelSelector combobox: hand-rolled typo-tolerant scorer (D-08, zero deps), Favorites → Popular → All sections (D-06), Popular chip mirroring the Free tag (D-07), and the locked input-focus a11y contract with aria-activedescendant (MODEL-01/MODEL-03).**

## What Was Built

### Task 1 — fuzzy.ts scorer + locked-ranking tests (TDD)
- `fuzzyScore(query, target)`: substring tier `10000 + 1000 boundary bonus − index`; subsequence tier `1000 − (span − query.length)`; `BOUNDARY = /[\s/\-.:]/`; non-subsequence → `null`; empty query → `0`; case-insensitive.
- `matchModel(query, id, name)`: best of id/name; null name falls back to id-only; both null → null. Tie-breaking (alphabetical by label) deliberately left to the caller's sort.
- 15 unit tests covering every locked ranking tier, the `'lama33'` → `'llama-3.3'` typo-tolerance case, null (non-subsequence) removal, and matchModel fallbacks.
- RED commit `93e2848` (tests fail: module absent) → GREEN commit `c96675d` (15/15). No refactor needed. Zero new dependencies; `package.json` untouched.

### Task 2 — Sections + Popular chip + favorites read + section-scoped keys
- Flat options array restructured into (a) a NAVIGABLE array of selectable options only (activeIndex indexes this; headers never navigable) and (b) a RENDER list interleaving `role="presentation"` headers with option rows.
- Section order: extraOption row (outside sections) → Favorites (intersection with catalog, alphabetical, ENTIRELY ABSENT when empty — LOCKED) → Popular (`popularity_rank` ascending) → All models (complete catalog alphabetical).
- Keys `${section}:${m.id}`, DOM ids `${listboxId}-opt-${section}-${index}` (Pitfall 1); selected blue-600 check renders in every duplicate instance (test asserts 3/3).
- Popular chip in `ModelHint`: sibling span whenever `popularity_rank != null`, classes mirroring the Free tag exactly (`rounded bg-gray-200 px-1 text-gray-700 dark:bg-gray-700 dark:text-gray-200`), order `[Free|price] [Popular] [context]` — renders in EVERY section instance (closes audit B-1 / MODEL-03).
- Favorites read once at mount via `apiFetch('/api/preferences')` with the silent array-guard pattern; read-only this plan (star toggle + PUT = plan 15-06).
- Commit `f758ebd`.

### Task 3 — Search input + fuzzy wiring + combobox focus migration
- Pinned `h-11` search row as the first element in the open panel: Search icon 14px, LOCKED placeholder `Search models…`, `border-b`, no side borders, no focus ring inside the panel (cmdk convention).
- 150ms debounced query → `matchModel` filter → ONE flat score-ranked list (ties alphabetical), headers and extraOption hidden, non-matches removed; LOCKED `No models match your search.` (text-xs) on no-match; clearing restores sections.
- LOCKED focus model: open focuses the input (supersedes UL focus); input carries `aria-autocomplete="list"`, `aria-controls={listboxId}`, `aria-activedescendant` of the active navigable row; ArrowUp/Down skip headers structurally; Enter selects; Esc closes back to the trigger; Tab trapped; Home/End keep native caret; Shift+Enter deliberately NOT implemented (needs the favorite toggle, plan 15-06).
- `PANEL_MAX` 320 → 370 so the drop-up estimate covers the search row (settings sidebar-footer selector relies on drop-up).
- Commit `7903b05`. All 22 component tests + 15 fuzzy tests green; `npm run build` exit 0.

## Verification

- `npx vitest run src/lib/fuzzy.test.ts src/components/ModelSelector.test.tsx` → 37/37 green
- `npm run build` → exit 0
- Plan files lint clean (`npx eslint` on all 4 files → exit 0); full-repo `npm run lint` exits 1 with exactly the 5 pre-existing D-15-03-A errors (untouched files — see deferred-items.md)
- `package.json`/`package-lock.json` diff empty (zero new deps); `components.json` absent (shadcn NOT initialized — STATE.md todo superseded by UI-SPEC `Tool: none`)
- Full FE suite (`npm run test`) is the wave-2 merge gate per plan — deliberately not run inside this parallel worktree

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Worktree lacked `frontend/node_modules`**
- **Found during:** Task 1 (vitest could not start)
- **Fix:** `npm ci` in `frontend/` (lockfile-pinned, no repo file changes) — wave-1 precedent (15-03)
- **Files modified:** none

**2. [Rule 3 - Blocking] All `await user.*` calls hang forever under vitest fake timers**
- **Found during:** Task 3 (4 new debounce/keyboard tests timed out at 5s each)
- **Issue:** RTL 16's async event wrapper drains the microtask queue via `setTimeout(0)` and only auto-advances the clock when it detects **jest** fake timers (`typeof jest !== 'undefined'`); under vitest fake timers the drain timer never fires, hanging every awaited userEvent call. A timed-out test's `finally` never runs, so the fake clock leaked and cascaded into subsequent tests.
- **Fix:** the three debounce tests drive the input with the SYNC `fireEvent` API (controlled-input `change`) + `act(() => vi.advanceTimersByTime(150))` — the plan-sanctioned `vi.useFakeTimers + advanceTimersByTime(150)` flow; a mount-microtask drain (`await act(async () => {})`) keeps favorites-fetch state updates inside act. Keyboard-nav tests (real timers) keep userEvent.
- **Files modified:** frontend/src/components/ModelSelector.test.tsx
- **Commit:** 7903b05

**3. [Rule 1 - Bug] Test fixture could never match the locked 'lama33' case**
- **Found during:** Task 3 test design
- **Issue:** the plan's locked test types `'lama33'` and expects the llama fixture to match, but the existing fixture (`meta/llama-free` / `Llama Free`) contains no digits — no subsequence match is possible.
- **Fix:** fixture renamed to `meta/llama-3.3-free` / `Llama 3.3 Free` (mirrors the real slug family); all fixture references updated.
- **Files modified:** frontend/src/components/ModelSelector.test.tsx
- **Commit:** 7903b05

### Implementation notes (within plan intent)

- **Seed effect deps:** plan says "remove the options.length dependency"; implemented as `[open, state]` so the lazy-fetch open path still seeds the selected row when the catalog lands (locked behavior), while keystrokes never re-seed (the Pitfall-2 goal). `state` only flips on fetch transitions.
- **Empty non-Favorites sections:** a header with zero rows renders nothing for ANY section (a rowless "Popular" header would be a visual bug); Favorites hidden-when-empty remains the LOCKED case.
- **Full-repo lint:** pre-existing 5-error debt (D-15-03-A) makes `npm run lint` exit 1 repo-wide; the plan's own 4 files lint clean. No new entries added.

## Known Stubs

- **Favorites are read-only by design this plan** (`ModelSelector.tsx` — favorites state renders the section; no star button, no PUT). Explicitly scoped to plan 15-06 by the plan's `<interfaces>` note ("The star toggle + PUT land in plan 15-06"). Not a defect; the Favorites section is fully functional for users who already have favorites persisted.

## Self-Check: PASSED

- `frontend/src/lib/fuzzy.ts` — FOUND
- `frontend/src/lib/fuzzy.test.ts` — FOUND
- `frontend/src/components/ModelSelector.tsx` (contains "Search models", `role="presentation"`, `PANEL_MAX = 370`, section-scoped `${section}:` keys) — FOUND
- `frontend/src/components/ModelSelector.test.tsx` — FOUND
- Commits `93e2848`, `c96675d`, `f758ebd`, `7903b05` — FOUND in `git log`
- 37/37 tests green; build exit 0; plan files lint clean — VERIFIED
