---
phase: 15-options-ui-capstone-demo-gating
plan: 06
subsystem: ui
tags: [react, vitest, favorites, model-picker, optimistic-update, a11y, testing-library]
requires:
  - phase: 15-01
    provides: "PUT /api/preferences accepts {favorite_models: string[]} — whole-array replace, partial upsert (never clobbers theme/default_model)"
  - phase: 15-04
    provides: "Sectioned ModelSelector (Favorites → Popular → All), favorites useState seeded by mount GET, navigable-array keyboard machinery on the search input"
provides:
  - "MODEL-08 write side: always-visible favorite star on every catalog row (sections AND flat search results, never extraOption), both picker surfaces via the one shared component"
  - "toggleFavorite: optimistic local set + fire-and-forget PUT /api/preferences {favorite_models} whole-array replace — silent, no revert, no toast (D-05 house style)"
  - "Shift+Enter toggles favorite on the active row (before the plain-Enter select branch); star click stopPropagation — no select, no close"
affects:
  - "15-07 (thread-header picker surface inherits the star automatically — one shared ModelSelector)"
  - "15-08 (phase verification: MODEL-08 closes)"
tech-stack:
  added: []
  patterns:
    - "Optimistic fire-and-forget PUT (DefaultModelSelector house style) applied to an array toggle: compute next → setState → void apiFetch(...).catch(() => {})"
    - "Const-narrowed `model` local inside the row map so the star's onClick closure keeps TS narrowing across the function boundary"
key-files:
  created: []
  modified:
    - frontend/src/components/ModelSelector.tsx
    - frontend/src/components/ModelSelector.test.tsx
key-decisions:
  - "pr-12 clearance applied conditionally (`model ? 'pr-12' : 'pr-3'`) — the extraOption row has no star so it keeps the original pr-3"
  - "Star state derived from the favorites array per model id at render, so every duplicate section instance (up to 3) flips identically on one toggle"
  - "Shift+Enter skips the extraOption row structurally (model is null there) rather than special-casing an index"
  - "REQUIREMENTS.md MODEL-08 checkbox left to the orchestrator (worktree precedent: 15-04/15-05 SUMMARY-only metadata commits)"
duration: ~20min active (split across a session-limit pause)
completed: 2026-07-06
---

# Phase 15 Plan 06: Favorite Star + Optimistic Persistence Summary

**MODEL-08 closed: always-visible favorite star on every picker row toggling `user_preferences.favorite_models` via optimistic fire-and-forget whole-array PUT — click (stopPropagation, no close) and Shift+Enter paths, identical across both picker surfaces.**

## What Was Built

### Task 1 — Star sub-element + optimistic toggle + Shift+Enter (TDD)
- RED commit `a211f9a`: 3 failing behavior tests (star click → exact whole-array PUT payload + listbox stays open + onSelect uncalled; Shift+Enter toggles while plain Enter selects; extraOption row starless while every catalog instance carries one) plus a `preferencesPutBodies()` helper parsing PUT `/api/preferences` bodies. Verified failing 3/25 with all 22 existing 15-04 tests green.
- GREEN commit `053aaee`:
  - Star button on every catalog row (sections AND flat search results — rendered per-row wherever `opt.model` is non-null, so search mode gets it for free), never the extraOption row: `absolute right-0 inset-y-0 w-11 flex items-center justify-center`, `tabIndex={-1}`, lucide `Star` size 16, `focus-visible:ring-2 focus-visible:ring-blue-500`. Favorited `text-blue-600 fill-blue-600`; unfavorited outline `text-gray-400 dark:text-gray-500`. Always visible (no hover-gating — touch parity). Row content gains `pr-12` clearance.
  - `onClick`: `e.stopPropagation()` → `toggleFavorite(model.id)` — never selects, never closes (users can star several in one open).
  - `toggleFavorite(id)`: `next = includes ? without : [...favorites, id]` → `setFavorites(next)` optimistically → `void apiFetch('/api/preferences', { method: 'PUT', body: JSON.stringify({ favorite_models: next }) }).catch(() => {})` — whole-array replace, `favorite_models` the ONLY body key, silent, no revert, NO toast (house style per DefaultModelSelector).
  - Keyboard: Shift+Enter branch added BEFORE the plain-Enter select in the input's keydown — toggles the active navigable row, skipping extraOption (null model). Plain Enter behavior unchanged.
  - `aria-label` flips between the locked strings `Add ${label} to favorites` / `Remove ${label} from favorites` with `${label} = name ?? id` (= `opt.label`).

### Task 2 — Star behavior tests + focused regression
- Commit `9fafcb1`: 4 more tests completing the plan's 7-item list:
  - starring adds the model to the Favorites section in the same open session (header appears, row under it);
  - un-starring the only favorite hides the Favorites section (PUT body `{favorite_models: []}` asserted);
  - PUT rejection: star stays favorited (no revert), Favorites section persists, no toast (`role="status"` absent);
  - aria-label flips between the two locked strings with `fill-blue-600` tracking it across all 3 duplicate section instances (and back to outline on un-star).
- Focused file 29/29 green; `npm run build` exit 0; plan files eslint-clean. Full FE suite deferred to the wave-3 merge gate per plan.

## Verification

- `npx vitest run src/components/ModelSelector.test.tsx` → 29/29 green (22 pre-existing 15-04 tests untouched and green — zero regressions across search/sections)
- `npm run build` → exit 0 (tsc strict + vite; chunk-size warning pre-existing/informational)
- `npx eslint src/components/ModelSelector.tsx src/components/ModelSelector.test.tsx` → exit 0; full-repo `npm run lint` exits 1 with exactly the 5 pre-existing D-15-03-A errors in untouched files (see deferred-items.md — no new entries)
- Acceptance greps: `fill-blue-600` (1), `tabIndex={-1}` (2 — trigger-adjacent star instances in sections/search render paths share one JSX site; count includes none besides the star), `stopPropagation` (1), `pr-12` (1), `favorite_models` (5) in ModelSelector.tsx
- A test asserts the PUT body deep-equals `{favorite_models: [...]}` via `toEqual` on the parsed body — no `default_model`/`theme` keys possible
- Full FE suite (`npm run test`) is the wave-3 merge gate per plan — deliberately not run inside this parallel worktree
- Live spot-check (star → reload → persists across surfaces) is listed in plan `<verification>` as a dev-environment check; not executable in this worktree (no running stack) — favorites-persist-across-remount is covered by the mount-GET seed path already tested in 15-04 plus the PUT payload assertions here

## TDD Gate Compliance

- RED gate: `a211f9a` `test(15-06): add failing tests for favorite star toggle` (verified failing 3/25 before implementation)
- GREEN gate: `053aaee` `feat(15-06): favorite star with optimistic whole-array persistence` (25/25 green)
- REFACTOR: not needed — no cleanup commit

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Worktree lacked `frontend/node_modules`**
- **Found during:** Task 1 setup (vitest could not start)
- **Fix:** junction to the main checkout's node_modules (`cmd /c mklink /J`) — the 15-05-preferred approach, faster than `npm ci`
- **Files modified:** none (junction is gitignored)

### Implementation notes (within plan intent)

- **Full-repo lint:** pre-existing 5-error debt (D-15-03-A) makes `npm run lint` exit 1 repo-wide; both plan files lint clean in isolation (same posture as 15-03/15-04). No new deferred entries.
- **Task split under TDD:** Task 1 is `tdd="true"` while Task 2 owns the test file — the 7-test list was split 3 (RED, the behavior contract) + 4 (Task 2, section-integration/failure-path), totaling 7 new star tests in the file as required.
- **15-04's Known Stub resolved:** "Favorites are read-only by design this plan" is closed — favorites are now writable via star click and Shift+Enter.

## Known Stubs

None — the star is fully wired to persistence; no placeholder copy, no dead props.

## Threat Flags

None — the only security-relevant surface (browser → PUT /api/preferences) is already in the plan's threat model; mitigations (JWT-bound user_id, Pydantic max_length=200) live server-side from plan 15-01, and the FE sends only the slug array.

## Self-Check: PASSED

- `frontend/src/components/ModelSelector.tsx` (contains `fill-blue-600`, `tabIndex={-1}`, `stopPropagation`, `pr-12`, `favorite_models`) — FOUND
- `frontend/src/components/ModelSelector.test.tsx` (7 new star tests + `preferencesPutBodies` helper) — FOUND
- Commits `a211f9a`, `053aaee`, `9fafcb1` — FOUND in `git log`
- 29/29 focused tests green; build exit 0; plan files lint clean — VERIFIED
