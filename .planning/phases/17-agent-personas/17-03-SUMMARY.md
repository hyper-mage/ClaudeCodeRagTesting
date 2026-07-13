---
phase: 17-agent-personas
plan: 03
subsystem: testing
tags: [vitest, testing-library, react, persona, red-scaffold, frontend]

# Dependency graph
requires:
  - phase: 15-model-picker (v1.2)
    provides: DefaultModelSelector.test.tsx harness (renderWithProviders, makeApiMock, dropdown/listbox query pattern) cloned minus the key-gate machinery
provides:
  - RED baseline pinning PERS-01 (PersonaSelector → onSelect(personaId)) at the component boundary
  - RED baseline pinning PERS-04 (DefaultPersonaSelector → PUT /api/preferences {default_persona}) at the component boundary
  - The "no key gate for persona" invariant pinned in both pickers (a keyless user can pick/set a persona)
affects: [17-09 (persona picker components turn these GREEN)]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Persona-picker RED scaffold = DefaultModelSelector.test.tsx MINUS the useKeyStatus mock + keyless-gate test (persona has no key/cost/demo surface)"

key-files:
  created:
    - frontend/src/components/PersonaSelector.test.tsx
    - frontend/src/components/DefaultPersonaSelector.test.tsx
  modified: []

key-decisions:
  - "Both picker tests deliberately OMIT the useKeyStatus/useKeyGate mock — persona has no key/cost surface, so a keyless pick must flow straight through (no gate to drive)"
  - "Pinned the dropdown contract as trigger button + role=option items (mirrors ModelSelector a11y), and placeholder 'Select a persona' — the shape 17-09 must satisfy"
  - "Mocked ../lib/api in BOTH files (network-free suite); PersonaSelector never asserts on it (parent owns the PATCH), DefaultPersonaSelector asserts the self-PUT body"

patterns-established:
  - "RED-for-the-right-reason: unresolved component import fails at collection (cannot-resolve), not on a query assertion"

requirements-completed: []

# Metrics
duration: 2min
completed: 2026-07-13
---

# Phase 17 Plan 03: Persona Picker RED Test Scaffolds Summary

**Two RED vitest scaffolds that pin the persona chat picker (PERS-01 → onSelect(id)) and settings default picker (PERS-04 → PUT /api/preferences {default_persona}) at the component boundary, both asserting NO key gate — failing on cannot-resolve until 17-09 authors the components.**

## Performance

- **Duration:** 2 min
- **Started:** 2026-07-13T14:26:40Z
- **Completed:** 2026-07-13T14:28:54Z
- **Tasks:** 2
- **Files modified:** 2 (both created)

## Accomplishments
- `PersonaSelector.test.tsx` — 4 `it()` blocks: renders both persona options, `onSelect('general_assistant')` on option click (PERS-01), current-value reflection on the trigger, and the keyless no-gate invariant.
- `DefaultPersonaSelector.test.tsx` — 3 `it()` blocks: `PUT /api/preferences` with the exact body `{default_persona: 'general_assistant'}` (PERS-04), `onChange('board_game_expert')`, and a keyless user can still set a default (PUT fires, no gate modal).
- Both suites fail RED at collection for the correct reason — `Failed to resolve import "./PersonaSelector"` / `"./DefaultPersonaSelector"` (components authored in 17-09).
- Zero production/source code touched; only the two `.test.tsx` files exist for these names.

## Task Commits

Each task was committed atomically:

1. **Task 1: RED scaffold — PersonaSelector.test.tsx** - `e40eefa` (test)
2. **Task 2: RED scaffold — DefaultPersonaSelector.test.tsx** - `e5816b3` (test)

_No production code; both are pure RED test commits (no GREEN/refactor pair — those land in 17-09)._

## Files Created/Modified
- `frontend/src/components/PersonaSelector.test.tsx` - RED scaffold for the chat persona picker (onSelect + value reflection + no-gate); imports the not-yet-existent `./PersonaSelector`.
- `frontend/src/components/DefaultPersonaSelector.test.tsx` - RED scaffold for the settings default persona picker (self-PUT `{default_persona}` + onChange + no-gate); imports the not-yet-existent `./DefaultPersonaSelector`.

## Decisions Made
- Omitted the `useKeyStatus`/`useKeyGate` mock entirely (contrast `DefaultModelSelector.test.tsx` L16-21) — persona carries no key/cost/demo surface, so the keyless-gate branch of the model analog is dropped and replaced with an affirmative "no gate" assertion in each file.
- Pinned the eventual component contract via the tests: a lightweight dropdown with a trigger `<button>` (placeholder `Select a persona`, or the selected label when set) and `role="option"` items — mirroring `ModelSelector`'s accessible listbox convention so 17-09 has an unambiguous target.
- Mocked `../lib/api` in both files to keep the suite network-free; `PersonaSelector` never asserts on `apiFetch` (ChatPage owns the PATCH per the interfaces), while `DefaultPersonaSelector` asserts the fire-and-forget self-PUT body.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None. Git reported a benign LF→CRLF autocrlf warning on both `.test.tsx` files (Windows); no impact on content or test collection.

## Known Stubs
None. The two files are intentional RED test scaffolds whose "missing component" import is by-design and resolved by 17-09 (a documented `key_links` entry in the plan: `DefaultPersonaSelector.test.tsx` → `DefaultPersonaSelector.tsx` "unresolved until 17-09"). No stub data flows to any UI.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- RED baseline is in place for the two persona pickers; 17-09 turns them GREEN by authoring `PersonaSelector.tsx` and `DefaultPersonaSelector.tsx` to satisfy the pinned contracts (trigger + `role="option"` dropdown, `onSelect`/`onChange`, self-PUT `{default_persona}`, no gate).
- PERS-01 / PERS-04 traceability stays Pending until 17-09 (component authoring) — per the same Wave-0-RED pattern used by 17-01/17-02.

## Self-Check: PASSED

- FOUND: frontend/src/components/PersonaSelector.test.tsx
- FOUND: frontend/src/components/DefaultPersonaSelector.test.tsx
- FOUND commit: e40eefa (Task 1)
- FOUND commit: e5816b3 (Task 2)
- Both suites RED for the correct reason (cannot-resolve component import); no `useKeyStatus`/`useKeyGate` mock or import; no source/component files created.

---
*Phase: 17-agent-personas*
*Completed: 2026-07-13*
