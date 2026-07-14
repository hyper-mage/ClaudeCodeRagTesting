---
phase: 17-agent-personas
reviewed: 2026-07-13T00:00:00Z
depth: standard
files_reviewed: 3
files_reviewed_list:
  - frontend/src/pages/ChatPage.tsx
  - frontend/src/hooks/useChat.ts
  - frontend/src/components/ChatContainer.tsx
findings:
  critical: 1
  warning: 1
  info: 3
  total: 5
status: issues_found
---

# Phase 17: Code Review Report

**Reviewed:** 2026-07-13T00:00:00Z
**Depth:** standard
**Files Reviewed:** 3
**Status:** issues_found

## Summary

Reviewed the phase-17 GAP-CLOSURE diff (plans 17-12 + 17-13) across `ChatPage.tsx`,
`useChat.ts`, and `ChatContainer.tsx`, diffed from base `6933755`.

Verified the two constraints called out in the scope note and both hold:

- **Display-only persona resolver (Gap 1) does NOT auto-PATCH.** The effective-persona
  fallback `activeThread?.persona ?? userDefaultPersona ?? personas?.find(p => p.is_default)?.id ?? null`
  only feeds `PersonaSelector`'s `value` prop; `handleThreadPersonaChange` (the only PATCH
  writer) fires exclusively from the user-click `onSelect` path. `userDefaultPersona` is
  captured from `GET /api/preferences` and never written back. No write leaks from the
  display path.
- **Sentinel single source of truth.** `INTERRUPTED_CONTENT = '[Response interrupted]'`
  (useChat.ts:55) matches the backend stamp `chat.py:1586` verbatim, and `ChatContainer`
  imports it rather than re-hardcoding. Grep confirms the literal appears once in source.
- **useEffect deps are correct.** The preferences effect (`[]`) reads only stable setters;
  `retryLastUserMessage`/`retryWithDemo` deps (`[messages, isStreaming, sendMessage, threadId]`)
  are complete — no stale-closure risk in the changed code.

One BLOCKER was found: the new interrupted-turn Retry card renders on **every** persisted
interrupted assistant row, but the Retry action always targets the **last** user turn and the
backend deletes the **most-recent** assistant row — so retrying a non-terminal interrupted
row resubmits the wrong turn and destroys a later good response. Details below.

## Critical Issues

### CR-01: Retry on a non-terminal interrupted row resends the wrong turn and deletes a good response

**File:** `frontend/src/components/ChatContainer.tsx:187-215` (render branch) and `frontend/src/hooks/useChat.ts:379-391` (`retryLastUserMessage`)

**Issue:**
The Gap-2 Retry card renders on **any** assistant row whose content equals the sentinel:

```tsx
) : msg.role === 'assistant' && msg.content === INTERRUPTED_CONTENT ? (
```

But the wired handler (`onRetry` → `retryLastUserMessage`) is position-agnostic — it always
retries the *latest* user message and strips *all* interrupted rows:

```ts
const lastUser = [...messages].reverse().find(m => m.role === 'user')  // ALWAYS the last user turn
...
prev.filter(m => m.role !== 'error' && !(m.role === 'assistant' && m.content === INTERRUPTED_CONTENT))
```

An interrupted row can be **non-terminal**: a user may abandon a retry and simply send a new
message, leaving history as `[userA, interruptedA, userB, goodB]`. On reload the Retry card is
rendered on `interruptedA` (mid-history). Clicking it:

1. FE: `lastUser` resolves to `userB` (not `userA`), strips `interruptedA`, and re-sends
   `userB` with `retry:true`.
2. Backend (`chat.py:895-907`, confirmed): deletes the **most-recent** assistant row —
   `goodB`, a successful response — and skips the user insert. The completion then regenerates
   the last turn, not the interrupted one the user clicked.

Net effect: the user intends to retry `userA`, but `goodB` is permanently deleted (data loss),
`userB` is regenerated, and the `interruptedA` marker vanishes. This is incorrect behavior with
a data-loss consequence.

**Fix:**
Only render the Retry card when the interrupted row is the **terminal** message, matching both
`retryLastUserMessage`'s last-user targeting and the backend's delete-most-recent-assistant
semantics. Expose the index in the map and guard the branch:

```tsx
{messages.map((msg, i) =>
  msg.role === 'error' ? (
    ...
  ) : msg.role === 'notice' ? (
    ...
  ) : msg.role === 'assistant'
      && msg.content === INTERRUPTED_CONTENT
      && i === messages.length - 1 ? (   // only the terminal interrupted turn is retryable
    <div key={msg.id} className="flex justify-start mb-4"> ... </div>
  ) : (
    <MessageBubble ... />
  )
)}
```

Non-terminal interrupted rows then fall through to the existing render (no actionable Retry),
which cannot delete a later good turn. (If a non-terminal interrupted row should show a
non-actionable "interrupted" note, render a variant without the button.)

## Warnings

### WR-01: Persona picker cannot distinguish "pinned" from "following default" and offers no clear-to-default

**File:** `frontend/src/pages/ChatPage.tsx:265`, `frontend/src/components/ChatContainer.tsx:129-133`, `frontend/src/components/PersonaSelector.tsx:19`

**Issue:**
The new resolver now shows the effective default persona as the picker's selected value even
when the thread has **no** pinned persona (`activeThread.persona === null`). But `PersonaSelector`
renders the resolved value with a checkmark identical to a genuine pin, and its `onSelect`
signature is `(personaId: string) => void` — there is **no** null/clear option (unlike
`ModelSelector`, which is given `extraOption={{ label: 'Use my default model', value: null }}`
and a distinct `'Default model'` sub-state).

Consequences of the asymmetry, sharpened by the Gap-1 display change:
- A user who never pinned a persona now sees one "selected," implying a pin that does not exist.
- Selecting the shown default (or any persona) calls `handleThreadPersonaChange`, which PATCHes
  a concrete id — **permanently pinning** the thread with no UI path back to "follow my default."

**Fix:**
Mirror the model selector: give `PersonaSelector` a clear-to-default option and widen
`onSelect` to `(personaId: string | null) => void`, routing `null` through
`handleThreadPersonaChange` (which should PATCH `{ persona: null }` to un-pin). Optionally
distinguish the "following default" sub-state from an explicit pin in the trigger label so the
displayed default is not mistaken for a pin.

## Info

### IN-01: Interrupted Retry card duplicates ErrorMessageBubble's generic markup

**File:** `frontend/src/components/ChatContainer.tsx:194-214`

**Issue:** The interrupted card hand-rolls the same red-wash bubble + Retry button as
`ErrorMessageBubble`'s generic variant (`ErrorMessageBubble.tsx:55-79`), re-hardcoding the
identical Tailwind classes instead of reusing the shared `BTN_BASE`/`BTN_PRIMARY` constants or
a shared card component. The two will drift on any future copy/style change.

**Fix:** Extract the red-wash recovery card (icon + message + single Retry button) into a small
shared component used by both the generic `ErrorMessageBubble` branch and the interrupted
branch, parameterized on the message text.

### IN-02: Interrupted render branch drops the row's persisted tool cards

**File:** `frontend/src/components/ChatContainer.tsx:187-215`

**Issue:** On reload, an interrupted assistant row may carry persisted `toolsUsed`
(mapped from `tools_used` in `loadMessages`, useChat.ts:86-92). The interrupted branch renders
only the Retry card and never passes `msg.toolsUsed` through, so any tool activity that ran
before the interruption is hidden — a minor context regression versus the prior `MessageBubble`
render of that row.

**Fix:** If preserving pre-interruption tool context is desired, render the tool cards
(or a collapsed summary) alongside the Retry card, or fall through to `MessageBubble` for rows
that have `toolsUsed`.

### IN-03: retryWithDemo does not strip interrupted rows (latent inconsistency)

**File:** `frontend/src/hooks/useChat.ts:396-402`

**Issue:** `retryLastUserMessage` was updated to strip both `role==='error'` rows and interrupted
assistant rows, but the sibling `retryWithDemo` still strips only `role==='error'`:

```ts
setMessages(prev => prev.filter(m => m.role !== 'error'))
```

This is currently harmless because `[Use demo]` renders only on the forbidden (403) error
bubble, never on the interrupted card — so `retryWithDemo` is never invoked against an
interrupted row. It is a latent inconsistency: if demo recovery is ever wired to interrupted
turns, a stale interrupted row would linger after the demo retry.

**Fix:** Factor the strip predicate into one shared helper used by both retry paths so they
stay in sync.

---

_Reviewed: 2026-07-13T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
