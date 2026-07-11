---
phase: 13-preferences-per-thread-model
plan: 05
status: complete
autonomous: true
requirements_completed: [MODEL-05, MODEL-06, PREF-02]
key_files:
  created:
    - frontend/src/lib/themeBootstrap.ts
    - frontend/src/test/themeBootstrap.test.ts
    - frontend/src/components/ModelSelector.tsx
    - frontend/src/components/ModelSelector.test.tsx
    - frontend/src/components/ThemeToggle.tsx
    - frontend/src/components/ThemeToggle.test.tsx
  modified:
    - frontend/index.html
    - frontend/src/index.css
---

# 13-05 SUMMARY — Frontend primitives + theming mechanism

Reusable, theme-aware primitives with NO consumers wired yet (Plan 06 wires them into the real surfaces). All hand-rolled Tailwind — no shadcn (gated to Phase 15).

> **Resumed across a session-limit interruption.** Task 1 was committed before the cut (`30bba58`); Task 2 (ModelSelector) was on disk uncommitted with 2 failing tests; Task 3 (ThemeToggle) was unstarted. Resolved inline on resume — see "Resume notes" below.

## What was built

**Task 1 — Flash-free theme bootstrap (`30bba58`):**
- `frontend/index.html` — inline `<head>` script that toggles `<html>.dark` from `localStorage.theme` BEFORE the module bundle, for flash-free first paint (D-02 / RESEARCH Pattern 4, Pitfall 5).
- `frontend/src/index.css` — Tailwind v4 `@custom-variant dark (&:where(.dark,.dark *))` class strategy + core-surface light/dark palette tokens (D-01).
- `frontend/src/lib/themeBootstrap.ts` — `applyStoredTheme(storage, root, mql)`: the testable source of truth the inline script mirrors. Treats any stored value other than `"dark"` as light (T-13-THEME — tampered localStorage can't poison paint). `themeBootstrap.test.ts` covers it under jsdom.

**Task 2 — ModelSelector (`2f5f743`):**
- Hand-rolled accessible listbox dropdown over `GET /api/models` (Phase-12 `ModelResponse` shape). LOCKED a11y contract: `aria-haspopup="listbox"` + `aria-expanded` trigger; `role="listbox"`/`"option"`; arrow/Home/End nav; Enter/Space select; Esc closes + returns focus; outside-click close; focus trap; ≥44px (`min-h-11`) rows; selected row marked with a `blue-600` check. Free rows show the `Free` tag; paid show the price hint; context line omitted when `context_length` null. Renders Phase-12-precomputed fields — never recomputes `is_free`. `onSelect` is a prop (Plan 06 supplies the PATCH/PUT). Optional `extraOption` (the "Use my default model" clear row → `null`) and optional pre-fetched `models` prop. Locked copy: `Loading models…`, `Couldn't load models. Tap to retry.`
- 8/8 a11y tests green.

**Task 3 — ThemeToggle (`1e3123e`):**
- Neutral (NOT blue-600) lucide Sun/Moon icon button, `aria-pressed` + locked labels (`Switch to light theme` / `Switch to dark theme`). Initial state read from the current `<html>` class. On click: write `localStorage.theme` (paint truth, D-02) → `applyStoredTheme()` to flip `<html>.dark` → fire-and-forget `apiFetch PUT /api/preferences {theme}` (`.catch` swallowed; a rejected PUT never reverts the applied class).
- 4/4 tests green (incl. the fire-and-forget non-revert case).

## Verification
- `cd frontend && npm test` → **7 files / 41 tests passed** (no regression to the prior 999.1 suite).
- `npx tsc -b --noEmit` → exit 0.
- `npx eslint` on all 13-05 touched files → clean.

## Resume notes (deviation log)
The session-limit cut left ModelSelector at 6/8 tests. Root cause: the closed trigger resolved the selected model's display name from the (lazily fetched-on-open) catalog, so a **preselected `value` showed the placeholder instead of the model name**. Resolution (real-world-correct): the selector now **fetches the catalog on mount when a `value` is preselected and no `models` prop is supplied**, so the closed trigger shows the model name; lazy fetch-on-open is preserved when `value` is null. The two value-set tests now `await screen.findByRole(...)` for the trigger label since the name resolves after the async fetch. No behavior change for the Plan-06 consumer (which passes a pre-fetched `models` list → name resolves synchronously).

## Hand-off to Plan 06
ModelSelector + ThemeToggle + `applyStoredTheme` are ready to wire: per-thread selector header row in ChatContainer (PATCH), DefaultModelSelector wrapper + ThemeToggle in the sidebar/MobileDrawer (PUT), and the post-login theme reconcile. Nothing in this plan touches a real surface yet.
