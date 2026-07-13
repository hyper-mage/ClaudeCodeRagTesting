---
phase: 17-agent-personas
plan: 10
subsystem: frontend
tags: [react, persona, wiring, chat-header, settings, optimistic-patch, no-key-gate, pers-05]

# Dependency graph
requires:
  - phase: 17-agent-personas (17-06)
    provides: "GET /api/personas catalog [{id,label,is_default}] — the list both pickers render (D-07)"
  - phase: 17-agent-personas (17-07)
    provides: "PATCH /api/threads/{id} {persona} (exclude_unset, IDOR re-check) + PUT/GET /api/preferences default_persona — the write/read targets the wiring hits"
  - phase: 17-agent-personas (17-08)
    provides: "applied migration 035 (threads.persona + user_preferences.default_persona) so the PATCH/PUT persist and the thread read returns persona"
  - phase: 17-agent-personas (17-09)
    provides: "PersonaSelector {value,onSelect,personas} + DefaultPersonaSelector {value,onChange,personas} — the gate-free pickers this plan mounts"
provides:
  - "ChatPage owns the persona catalog fetch + optimistic no-gate PATCH handler (handleThreadPersonaChange) + Thread.persona, passed through to ChatContainer (PERS-01/PERS-05)"
  - "ChatContainer renders PersonaSelector beside ModelSelector in the per-thread header row (Σ cost placement intact)"
  - "SettingsPage renders DefaultPersonaSelector seeded from GET /api/preferences.default_persona over the fetched catalog (PERS-04 live)"
affects: [17-11 (end-to-end human UAT validates the wired persona chain)]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Persona pin mirrors the v1.2 model-pin wiring MINUS useKeyGate: the optimistic setThreads + PATCH handler is passed DIRECTLY to the picker (persona has no key/cost surface, so no gate/modal)"
    - "Catalog fetched once per page (ChatPage + SettingsPage each Array.isArray-guard GET /api/personas) and passed down as a prop — never hardcoded (D-07), same idiom as the /api/models mount fetch"
    - "PERS-05 restore rides the existing loadThreads() read: ThreadResponse.persona seeds the header picker via activeThread?.persona ?? null (no extra fetch, no per-message badge — picker-only D-12)"

key-files:
  created: []
  modified:
    - frontend/src/pages/ChatPage.tsx
    - frontend/src/components/ChatContainer.tsx
    - frontend/src/pages/SettingsPage.tsx
    - frontend/src/components/ChatContainer.test.tsx

key-decisions:
  - "handleThreadPersonaChange is passed DIRECTLY to ChatContainer (onThreadPersonaChange={handleThreadPersonaChange}) — NOT via guardedSelect/useKeyGate. The model path keeps its gate; persona deliberately has none (grep: onApply:handleThreadPersonaChange == 0). A keyless/anon user can pin a persona (T-17-31 accept)."
  - "ChatContainer's threadPersona + onThreadPersonaChange are REQUIRED props (mirroring the required model props); personas is optional. This forced a Rule-1 compile fix to the pre-existing ChatContainer.test.tsx render sites (tsc -b type-checks test files)."
  - "PERS-05 marked complete here: the restore-on-reopen is delivered by this plan (loadThreads -> ThreadResponse.persona -> header picker seed). PERS-01/PERS-04 were already closed at the component boundary by 17-09; this plan makes them live end-to-end. 17-11 is human UAT (validation), not implementation."

patterns-established:
  - "Two-picker catalog fan-out: one GET /api/personas per page hydrates a parent-owned `personas` prop shared by the chat-header picker and (on settings) the default picker — the component never fetches or hardcodes the list"

requirements-completed: [PERS-05]  # PERS-01/PERS-04 were closed by 17-09; this plan wires all three live end-to-end. 17-11 validates.

# Metrics
duration: 12min
completed: 2026-07-13
---

# Phase 17 Plan 10: Persona Picker Wiring Summary

**Wired the two gate-free persona pickers into the running app: ChatPage now fetches GET /api/personas once, owns an optimistic no-key-gate `handleThreadPersonaChange` (PATCH /api/threads/{id} {persona}), carries `persona` on the Thread interface, and seeds the header picker from the thread read on reopen (PERS-05); ChatContainer renders PersonaSelector beside ModelSelector in the per-thread header row (Σ cost intact); and SettingsPage renders DefaultPersonaSelector seeded from GET /api/preferences.default_persona — this is the last implementation wave, end-to-end UAT is 17-11.**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-07-13T22:02:06Z
- **Completed:** 2026-07-13
- **Tasks:** 3
- **Files modified:** 4 (0 created; 3 planned + 1 test compile-fix)

## Accomplishments
- **ChatPage.tsx (Task 1)** — added `persona: string | null` to the `Thread` interface (beside `model`, PERS-05); a `personas` state (`PersonaOption[] | undefined`) hydrated by a one-time `apiFetch('/api/personas')` mount effect (Array.isArray-guarded, silent on failure — mirrors the `/api/models` fetch, D-07); `handleThreadPersonaChange` = an optimistic `setThreads` on the active thread's `persona` then `PATCH /api/threads/{id} {persona}` with Sentry.captureException + the "Couldn't update the persona for this chat. Try again." toast on failure. Crucially the handler carries **no useKeyGate** and is passed DIRECTLY (`onThreadPersonaChange={handleThreadPersonaChange}`), alongside `threadPersona={activeThread?.persona ?? null}` and `personas={personas}`.
- **ChatContainer.tsx (Task 2)** — extended `Props` with `threadPersona: string | null`, `onThreadPersonaChange: (personaId: string) => void` (required, mirroring the model props) + `personas?: PersonaOption[]`; rendered `<PersonaSelector value={threadPersona} onSelect={onThreadPersonaChange} personas={personas} />` beside `<ModelSelector>` in the same `activeThreadId !== null` shrink-0 `h-12` header row, with a "Persona" caption (added to the locked `THREAD_SELECTOR_COPY`). The ModelSelector render and the per-thread `Σ ${threadCost}` (ml-auto) caption are unchanged.
- **SettingsPage.tsx (Task 3)** — added a `personas` state + one-time `apiFetch('/api/personas')` mount fetch (Array.isArray-guarded, mirrors the page's `/api/models` fetch) and a `defaultPersona` state seeded by **extending the existing `/api/preferences` GET effect** to also read `prefs.default_persona` (no extra request); rendered `<DefaultPersonaSelector value={defaultPersona} onChange={setDefaultPersona} personas={personas} />` in a new section beside the `DefaultModelSelector` block. The component supplies its own LOCKED heading/helper, so no duplicate heading was added; the OpenRouter/Model/Theme sections are untouched.

## Task Commits

Each task was committed atomically:

1. **Task 1: ChatPage — persona state + catalog fetch + no-gate PATCH handler + prop pass-through** — `f2e2b86` (feat)
2. **Task 2: ChatContainer — render PersonaSelector in the header row (+ test compile-fix)** — `6a9c944` (feat)
3. **Task 3: SettingsPage — render DefaultPersonaSelector seeded from preferences** — `0b9f8f8` (feat)

## Files Created/Modified
- `frontend/src/pages/ChatPage.tsx` — `Thread.persona`; `personas` state + `/api/personas` mount fetch; `handleThreadPersonaChange` (optimistic + PATCH, no gate); passes `threadPersona`/`onThreadPersonaChange`/`personas` to ChatContainer.
- `frontend/src/components/ChatContainer.tsx` — persona props on `Props` + destructure; renders `PersonaSelector` beside `ModelSelector`; `personaHeading` added to the locked copy const; Σ cost placement intact.
- `frontend/src/pages/SettingsPage.tsx` — `personas` + `defaultPersona` state; `/api/personas` fetch; `default_persona` read folded into the existing prefs seed effect; renders `DefaultPersonaSelector`.
- `frontend/src/components/ChatContainer.test.tsx` — added `threadPersona`/`onThreadPersonaChange` to every `<ChatContainer>` render site (Rule 1 compile-fix; see Deviations).

## Decisions Made
- **No gate on the persona handler (test-and-grep asserted).** `handleThreadPersonaChange` is passed straight to the picker; `grep -c "onApply: handleThreadPersonaChange"` == 0 and the persona handler never routes through `guardedSelect`. The three `useKeyGate` occurrences in ChatPage all belong to the model path (import + hook call + `guardedSelect`) — none wrap persona (T-17-31 accept: a keyless user can pin a persona).
- **Required persona props on ChatContainer.** Matched the existing required model props (`threadModel`/`onThreadModelChange`) rather than making them optional, so a caller that forgets to wire the picker fails the type-check. The cost was a mechanical test-props addition (below).
- **PERS-05 completed by this plan; PERS-01/PERS-04 already complete.** REQUIREMENTS.md already showed PERS-01/PERS-04 Complete (17-09 closed them at the component boundary). This plan wires all three live and closes PERS-05 (restore-on-reopen via `loadThreads -> ThreadResponse.persona -> activeThread?.persona ?? null`). 17-11 is human UAT, which validates rather than implements.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] ChatContainer.test.tsx render sites missing the new required props**
- **Found during:** Task 2 (`npm run build`)
- **Issue:** Adding the required `threadPersona`/`onThreadPersonaChange` props to `ChatContainer.Props` broke `tsc -b`, which type-checks the test file: all 11 `<ChatContainer .../>` render sites (8 inline + 2 with a shared `onThreadModelChange` var + the `renderContainer` helper) errored `TS2739: missing threadPersona, onThreadPersonaChange`. Directly caused by this task's contract change (in scope), not pre-existing.
- **Fix:** Added `threadPersona={null}` + `onThreadPersonaChange={vi.fn()}` to each render site (and the shared `renderContainer` helper defaults). No behavioral assertion changed — the test file only constructs Props. This mirrors the mock-signature fixes 17-06/17-07 applied when their call-site signatures changed.
- **Files modified:** `frontend/src/components/ChatContainer.test.tsx`
- **Verification:** `npx vitest run src/components/ChatContainer.test.tsx` → 17/17 GREEN; full suite 133/133.
- **Commit:** `6a9c944` (Task 2 commit)

**Total deviations:** 1 auto-fixed (a test-props compile-fix caused by this plan's required-prop addition). No production-behavior deviation; the plan's three source files were wired exactly as written.

## Issues Encountered
- **Interdependent parent/child commit boundary (informational):** ChatPage (Task 1) and ChatContainer (Task 2) are a coupled parent/child pair — the combined `npm run build` only goes green once both are edited, so the Task-1-only commit does not type-check in isolation. This is inherent to file-atomic commits of tightly-coupled React files; I verified the combined build/tests green before committing either, and the post-Task-2 tree is fully green. The plan's task order (ChatPage first) was followed.
- **Pre-existing frontend lint baseline (out of scope):** `npm run lint` reports 5 pre-existing errors, confirmed present on the clean tree via `git stash` (WITHOUT the wiring). None are introduced by this plan — the only one in a file I touched is `ChatPage.tsx:66` (`react-hooks/set-state-in-effect` on the pre-existing `loadThreads()` effect, not my new `/api/personas` effect). Logged to `.planning/phases/17-agent-personas/deferred-items.md`; left untouched per the scope boundary.
- The `npm run build` >500 kB chunk-size notice is the pre-existing project-wide warning (out of scope).

## Known Stubs
None. Both pickers render the parent-supplied server-fetched catalog; `threadPersona`/`defaultPersona` are seeded from real reads (thread row / GET /api/preferences). No empty/mock data is hardcoded to flow to the UI. The pickers' "No personas available." branch is a legitimate empty-state (only if the catalog fetch returns nothing), not a stub.

## Threat Flags
None. This plan introduces no new security surface — it consumes the already-mitigated auth-gated GET /api/personas (T-17-30 accept: only id/label/is_default cross the wire) and the ownership-re-checked PATCH /api/threads / PUT /api/preferences (T-17-29 mitigate: server enforces .eq id .eq user_id -> 404 + registry validation; the client is not the enforcement point). No gate on the pickers is the deliberate, accepted T-17-31 disposition.

## User Setup Required
None - no external service configuration required. (Carry-forward from 17-06/17-08: the `SYSTEM_PROMPT` `.env`/`.env.prod` shadow must be removed at deploy so the operational base + persona voice reach the running app — a deploy-time step, not a code change.)

## Verification
- `cd frontend && npm run build` → **succeeds** (all three edited files + the test-props fix type-check under strict mode).
- `cd frontend && npx vitest run` → **133/133 GREEN** across 14 test files (PersonaSelector 4, DefaultPersonaSelector 3, ChatContainer 17 all green; no regression).
- Acceptance greps: `handleThreadPersonaChange` == 2 in ChatPage (def + prop pass); `onApply: handleThreadPersonaChange` == 0 (no gate wrap); `PersonaSelector` rendered in ChatContainer with `<ModelSelector>` (1) and `Σ` (2) intact; `DefaultPersonaSelector` rendered in SettingsPage with `DefaultModelSelector` (3) intact.
- `npm run lint` fails only on the 5 pre-existing baseline errors (confirmed via `git stash`) — zero introduced by the wiring.

## Next Plan Readiness
- The persona pickers are live end-to-end: chat header (per-thread PATCH, no gate, restore-on-reopen) and settings (default PUT), both fed by GET /api/personas and seeded from the thread/preferences reads. This closes the last implementation wave of Phase 17.
- **17-11 (end-to-end human UAT):** validate the full persona chain — pick a persona in a chat, confirm the reply voice changes and the pin survives reopen (PERS-05); set a default persona in settings and confirm new threads inherit it (PERS-04); confirm a keyless/anon user can still pick (no gate). Reminder: remove the `SYSTEM_PROMPT` `.env` shadow before the live smoke or the persona/base composition will not reach the running app.

## Self-Check: PASSED

- FOUND: frontend/src/pages/ChatPage.tsx
- FOUND: frontend/src/components/ChatContainer.tsx
- FOUND: frontend/src/pages/SettingsPage.tsx
- FOUND commit: f2e2b86 (Task 1)
- FOUND commit: 6a9c944 (Task 2)
- FOUND commit: 0b9f8f8 (Task 3)
- Build green; full FE suite 133/133; acceptance greps pass; no new lint errors.

---
*Phase: 17-agent-personas*
*Completed: 2026-07-13*
