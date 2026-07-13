---
phase: 17-agent-personas
plan: 09
subsystem: frontend
tags: [react, persona, picker, dropdown, no-key-gate, green, frontend]

# Dependency graph
requires:
  - phase: 17-03
    provides: "PersonaSelector.test.tsx + DefaultPersonaSelector.test.tsx RED scaffolds (the component contracts this plan turns GREEN)"
  - phase: 17-06
    provides: "GET /api/personas catalog (id/label/is_default; voice_block withheld) that the parent fetches to feed these pickers"
  - phase: 17-07
    provides: "PATCH /api/threads persona + PUT /api/preferences {default_persona} endpoints the pickers ultimately hit"
provides:
  - "PersonaSelector.tsx — chat-header persona dropdown (onSelect(id), parent owns the PATCH), no key gate (PERS-01)"
  - "DefaultPersonaSelector.tsx — settings default persona dropdown that self-PUTs /api/preferences {default_persona}, no key gate (PERS-04)"
  - "PersonaOption type ({id,label,is_default}) exported from PersonaSelector for reuse by parents/settings"
affects: [17-10 (chat/settings wiring consumes both pickers), 17-11 (validation)]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Persona picker = a lightweight hand-rolled dropdown (button trigger + role=listbox/option) — NOT ModelSelector: no ModelResponse shape, no search/favorites, and crucially NO useKeyGate (persona has no key/cost/demo surface)"
    - "Settings default picker self-PUTs a single-key partial preference ({default_persona}) fire-and-forget, mirroring DefaultModelSelector's {default_model} — never blocks UI, never reverts on failure"
    - "Catalog is prop-supplied (parent fetches GET /api/personas); the component never hardcodes the persona list (D-07)"

key-files:
  created:
    - frontend/src/components/PersonaSelector.tsx
    - frontend/src/components/DefaultPersonaSelector.tsx
  modified: []

key-decisions:
  - "Built PersonaSelector fresh rather than reusing/parameterising the 560-line ModelSelector — its ModelResponse shape, section/search/favorites machinery, and useKeyGate wrapper do not fit persona (which has no key/cost surface). PersonaSelector is presentation-only."
  - "DefaultPersonaSelector reuses PersonaSelector for its control (not an inline clone), adding only the LOCKED heading/helper + the self-PUT onSelect — one dropdown implementation, two placements."
  - "No key gate in either component (deliberate, test-asserted): a keyless user must be able to pick/set a persona; the 'Connect OpenRouter?' modal never renders."
  - "Picker-only attribution (D-12): neither component renders a per-message persona badge; no messages schema/column touched."

patterns-established:
  - "Persona pickers are gate-free by design — the no-key-gate invariant is pinned by the 17-03 tests and preserved here (grep -L useKeyGate confirms absence in both files)"

requirements-completed: [PERS-01, PERS-04]

# Metrics
duration: 2min
completed: 2026-07-13
---

# Phase 17 Plan 09: Persona Picker Components Summary

**Authored the two gate-free persona pickers — a chat-header `PersonaSelector` (reports the pick via `onSelect(id)`; the parent owns the PATCH) and a settings `DefaultPersonaSelector` that self-PUTs `/api/preferences {default_persona}` — both rendering a parent-supplied (server-fetched) catalog with NO key/cost gate, turning the 17-03 RED scaffolds fully GREEN (7/7).**

## Performance

- **Duration:** 2 min
- **Started:** 2026-07-13T21:53:01Z
- **Completed:** 2026-07-13T21:55:31Z
- **Tasks:** 2
- **Files modified:** 2 (both created)

## Accomplishments
- `PersonaSelector.tsx` — a lightweight accessible dropdown (button trigger + `role="listbox"`/`role="option"` items, lucide `Check`/`ChevronDown`, ChatContainer-header surface tokens). Trigger reflects the label of `value` (or a "Select a persona" placeholder); an option click calls `onSelect(persona.id)` and closes. Options render from the `personas` prop only — never hardcoded (D-07). No key gate, no modal (PERS-01). 4/4 tests GREEN.
- `DefaultPersonaSelector.tsx` — the settings default control: a LOCKED heading ("Default persona") + helper above a reused `PersonaSelector`. On select it calls `onChange?.(id)` then fires exactly one fire-and-forget `PUT /api/preferences` with body `{default_persona: <id>}` (`.catch(() => {})`, house style). No key gate — a keyless user can set a default persona (PERS-04). 3/3 tests GREEN.
- Exported `PersonaOption` (`{id,label,is_default}`) from `PersonaSelector` so the settings picker and future parents share one catalog-row type.

## Task Commits

Each task was committed atomically:

1. **Task 1: PersonaSelector.tsx — chat-header persona dropdown** - `fcbc710` (feat)
2. **Task 2: DefaultPersonaSelector.tsx — settings default persona dropdown with self-PUT** - `419b0ee` (feat)

_TDD note: the RED gate (`test(...)`) for both components was committed in 17-03 (`e40eefa`, `e5816b3`); this plan supplies the GREEN gate (`feat(...)`). No refactor commit was needed — the components landed clean against the pinned contracts._

## Files Created/Modified
- `frontend/src/components/PersonaSelector.tsx` - chat persona dropdown; `onSelect(id)` on click, value reflected on the trigger, catalog from the `personas` prop, no key gate. Exports `PersonaOption`.
- `frontend/src/components/DefaultPersonaSelector.tsx` - settings default persona dropdown; reuses `PersonaSelector`, adds the LOCKED heading/helper and the self-PUT `{default_persona}` (fire-and-forget) + `onChange` notify-up, no key gate.

## Decisions Made
- **Fresh component, not a ModelSelector clone.** The plan explicitly warns off the 560-line `ModelSelector` (its `ModelResponse` shape + `useKeyGate` do not fit). `PersonaSelector` is a self-contained ~120-line dropdown with only what personas need — no search, no favorites, no gate.
- **One dropdown, two placements.** `DefaultPersonaSelector` imports and renders `PersonaSelector` for its control rather than inlining a second dropdown, so the a11y/behavior contract is defined once.
- **Gate-free, test-asserted.** Neither file imports `useKeyGate`/`useKeyStatus` (`grep -L` confirms absence in both). The `Connect OpenRouter?` modal never appears for a persona pick/default — persona carries no key/cost/demo surface.
- **Catalog stays a prop.** Both pickers render `personas ?? []`; the list is fetched by the parent from `GET /api/personas` (D-07), never hardcoded in the component.

## Deviations from Plan

**1. [Rule 1 - Acceptance-criteria drift] Reworded a docstring token so `grep -L` confirms no key gate**
- **Found during:** Task 1 (post-write acceptance check)
- **Issue:** The first draft's docstring contained the literal word `useKeyGate` ("...so there is no useKeyGate here..."). Task 1's acceptance criterion verifies gate-absence via `grep -L "useKeyGate\|useKeyStatus"`, which would fail to list a file that mentions the token even in a comment.
- **Fix:** Reworded the comment to "no key gate" so the token appears nowhere in either component. Both files now return zero matches.
- **Files modified:** frontend/src/components/PersonaSelector.tsx (comment only; committed within Task 1's `fcbc710`)
- **Commit:** fcbc710

## Issues Encountered
None. Git reported the benign LF→CRLF autocrlf warning on both `.tsx` files (Windows); no impact on content or test/build outcomes. The `npm run build` chunk-size (>500 kB) warning is a pre-existing, project-wide notice unrelated to these components (out of scope).

## Known Stubs
None. Both components render the parent-supplied catalog; no empty/mock data is hardcoded to flow to the UI. The "No personas available." branch is a legitimate empty-state, not a stub — it appears only when the parent passes an empty list.

## User Setup Required
None - no external service configuration required.

## Verification
- `cd frontend && npx vitest run src/components/PersonaSelector.test.tsx src/components/DefaultPersonaSelector.test.tsx` → **7/7 GREEN** (PersonaSelector 4/4, DefaultPersonaSelector 3/3).
- `cd frontend && npm run build` → **succeeds** (TypeScript strict; the new components type-check).
- Neither component imports `useKeyGate`/`useKeyStatus` (`grep` → 0 matches in both); neither hardcodes the persona list.

## Next Phase Readiness
- Both persona pickers exist and satisfy their contracts; PERS-01 (chat picker → `onSelect(id)`) and PERS-04 (settings default → `PUT {default_persona}`) are code-complete at the component boundary.
- 17-10 can now wire `PersonaSelector` into the chat header (parent owns the PATCH via 17-07's endpoint, feeding the `personas` catalog from 17-06's `GET /api/personas`) and drop `DefaultPersonaSelector` into settings.
- The migration apply (17-08) + end-to-end validation (17-11) remain the closing steps for the phase.

## Self-Check: PASSED

- FOUND: frontend/src/components/PersonaSelector.tsx
- FOUND: frontend/src/components/DefaultPersonaSelector.tsx
- FOUND commit: fcbc710 (Task 1)
- FOUND commit: 419b0ee (Task 2)
- Both suites GREEN (7/7); production build succeeds; no `useKeyGate`/`useKeyStatus` import in either component.

---
*Phase: 17-agent-personas*
*Completed: 2026-07-13*
