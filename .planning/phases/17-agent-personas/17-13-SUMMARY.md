---
phase: 17-agent-personas
plan: 13
subsystem: ui
tags: [react, chat, sse, retry, error-recovery, vitest]

# Dependency graph
requires:
  - phase: 17-agent-personas (17-10)
    provides: ChatContainer onRetry prop wired to retryLastUserMessage; the retry:true send path in useChat
  - phase: 17-agent-personas (17-12)
    provides: ChatPage persona picker display fix (disjoint files; not regressed)
provides:
  - One-click Retry affordance on PERSISTED interrupted assistant turns ('[Response interrupted]')
  - Exported INTERRUPTED_CONTENT sentinel as the single source of truth for the interrupted-turn stamp
  - retryLastUserMessage now strips the interrupted assistant row before resubmitting the last user message
affects: [chat-error-recovery, agent-personas UAT re-run (17-11)]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Shared exported sentinel drives both a render branch and a state-strip filter (no duplicated literal)"
    - "New in-thread recovery card reuses the existing retry:true send path — no second send implementation"

key-files:
  created: []
  modified:
    - frontend/src/hooks/useChat.ts
    - frontend/src/components/ChatContainer.tsx
    - frontend/src/components/ChatContainer.test.tsx
    - frontend/src/hooks/useChat.test.tsx

key-decisions:
  - "Interrupted card mirrors ErrorMessageBubble's generic red-wash role='alert' variant (AlertCircle + RotateCw/Retry button, bg-blue-600, disabled:opacity-50) — inline in ChatContainer, ErrorMessageBubble untouched"
  - "Copy is 'This response was interrupted.' — the raw '[Response interrupted]' sentinel is never surfaced as body text"
  - "Hook test added to the existing useChat.test.tsx (plan named a NEW useChat.test.ts); a second file for the same module would be redundant and off-convention"

patterns-established:
  - "Gap-closure recovery affordances key off a single exported sentinel imported into both hook and view"

requirements-completed: []  # Intentionally empty — Gap 2 is a user-requested UX enhancement mapping to NO PERS requirement (17-VERIFICATION.md Gap 2 / plan frontmatter)

# Metrics
duration: ~10min
completed: 2026-07-13
---

# Phase 17 Plan 13: Interrupted-Turn Retry Affordance Summary

**One-click Retry card on persisted `[Response interrupted]` assistant turns that re-sends the last user message via the existing retry:true send path and strips the interrupted row — closing VERIFICATION Gap 2.**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-07-13T21:35Z (approx, first task edit)
- **Completed:** 2026-07-13T21:41Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments
- Exported `INTERRUPTED_CONTENT = '[Response interrupted]'` from useChat.ts as the single source of truth for the backend interrupted-turn stamp (chat.py L1586, verbatim match).
- `retryLastUserMessage` now strips BOTH `role==='error'` rows AND the persisted `role==='assistant'` interrupted row before resubmitting, so the interrupted bubble disappears the instant the new attempt starts (matching the backend's most-recent-assistant-row deletion on retry).
- ChatContainer renders a compact `role="alert"` red-wash recovery card for an interrupted assistant turn — a single Retry button wired `onClick={onRetry}` / `disabled={isStreaming}`, mirroring ErrorMessageBubble's generic variant. The other render branches (error / notice / MessageBubble) are untouched.
- Added 4 specs (3 ChatContainer + 1 useChat) pinning: the alert Retry card renders (not a plain sentinel bubble), Retry click calls onRetry once, the button is disabled while streaming, and retryLastUserMessage strips-and-resubmits to `/api/threads/t1/messages?retry=true` with `content:'Q'`.

## Task Commits

Each task was committed atomically:

1. **Task 1: useChat.ts — export sentinel + strip interrupted row on retry** - `42b4604` (feat)
2. **Task 2: ChatContainer.tsx — render Retry card on interrupted turns** - `97ee5b3` (feat)
3. **Task 3: Tests — interrupted Retry renders + strip-and-resubmit + validate** - `4958554` (test)

**Follow-up:** `f2e0334` (docs) — reworded ChatContainer comments so the raw sentinel literal appears 0 times (single-source-of-truth acceptance criterion; comment-only, build unaffected).

**Plan metadata:** _(this SUMMARY + STATE.md + ROADMAP.md commit)_

## Files Created/Modified
- `frontend/src/hooks/useChat.ts` - Exported `INTERRUPTED_CONTENT` constant; extended `retryLastUserMessage`'s strip filter to also drop the interrupted assistant row. `sendMessage`, `retryWithDemo`, and the abort branch unchanged.
- `frontend/src/components/ChatContainer.tsx` - Imported `INTERRUPTED_CONTENT` + `AlertCircle`/`RotateCw`; added a message-map branch (before the MessageBubble else) rendering the interrupted Retry card.
- `frontend/src/components/ChatContainer.test.tsx` - `describe('ChatContainer interrupted-turn Retry (Gap 2)')` with 3 its (renders/click/disabled); import extended to pull `INTERRUPTED_CONTENT`.
- `frontend/src/hooks/useChat.test.tsx` - `Interrupted:` spec proving retryLastUserMessage resubmits the last user turn to the retry endpoint and strips the interrupted row; import extended to pull `INTERRUPTED_CONTENT`.

## Decisions Made
- **Reused the shipped retry path.** Retry re-enters `retryLastUserMessage` → `sendMessage(..., { retry: true })`. No new send implementation was introduced (T-17-34 mitigation: the backend owns row deletion; the FE just re-sends the last `role==='user'` message with an explicit `threadId`).
- **Single sentinel source of truth.** The `[Response interrupted]` literal lives only in `useChat.ts` (`INTERRUPTED_CONTENT`); ChatContainer and both test files import it — the literal appears 0 times in ChatContainer.tsx.
- **Card copy vs. sentinel.** The card shows 'This response was interrupted.'; the raw sentinel is never rendered as body text (asserted by `it A`).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Hook test added to existing useChat.test.tsx instead of a new useChat.test.ts**
- **Found during:** Task 3 (Tests)
- **Issue:** The plan (frontmatter `files_modified` + Task 3 action) called for a NEW file `frontend/src/hooks/useChat.test.ts`. An established `frontend/src/hooks/useChat.test.tsx` already exists and comprehensively covers the hook (including the analogous `retryWithDemo` Demo 6–8 specs), using the exact `renderHook`/`ProvidersWrapper`/`mockSSEResponse`/apiStream-mock patterns the plan prescribes. Creating a second test file for the same module (differing only by `.ts` vs `.tsx`) would be redundant, confusing, and off-convention.
- **Fix:** Added the interrupted-retry spec to the existing `useChat.test.tsx`, mirroring the shipped Demo 6 pattern exactly. Behavior and assertions match the plan's Task 3 acceptance criteria verbatim (retry URL, `content:'Q'`, interrupted-row strip).
- **Files modified:** frontend/src/hooks/useChat.test.tsx (in place of the planned .ts)
- **Verification:** `npx vitest run src/hooks/useChat.test.tsx` GREEN; full suite 141/141 GREEN.
- **Committed in:** 4958554 (Task 3 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking / file-placement adjustment)
**Impact on plan:** No behavioral change from the plan's intent — same hook, same assertions, same coverage. The only difference is the spec lives in the pre-existing `.tsx` file rather than a new `.ts` sibling. No scope creep.

## Issues Encountered
None. Build passed on every task; targeted specs (36) and full suite (141: 137 prior + 4 new) GREEN.

## User Setup Required
None - frontend-only, additive change; no external service configuration.

## Next Phase Readiness
- Gap 2 (Retry affordance) is closed. Combined with 17-12 (Gap 1 picker display), both VERIFICATION gaps are addressed.
- **Next:** Re-run the 17-11 human UAT — SC-1/SC-3/SC-4 picker display, SC-2 tool call under General Assistant, cross-user bleed, and a live interrupted-turn Retry click.
- No new backend/schema surface introduced; the retry reuses the existing authenticated POST `/api/threads/{id}/messages?retry=true` path.

## Self-Check: PASSED

- Files exist: 17-13-SUMMARY.md, useChat.ts, ChatContainer.tsx, ChatContainer.test.tsx, useChat.test.tsx — all FOUND.
- Commits exist: 42b4604, 97ee5b3, 4958554, f2e0334 — all FOUND.
- `INTERRUPTED_CONTENT` appears 3× in useChat.ts (export + strip usage); the raw sentinel literal appears 0× in ChatContainer.tsx.
- Build GREEN; targeted specs 36 GREEN; full suite 141/141 GREEN.

---
*Phase: 17-agent-personas*
*Completed: 2026-07-13*
