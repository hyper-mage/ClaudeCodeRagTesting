---
phase: "08"
plan: "04"
subsystem: "frontend"
tags: [portfolio, ui, anon-auth, error-handling, retry, demo-onboarding]
requires:
  - "Plan 08-02 backend: POST /api/demo/bootstrap router (merged on master e8c51b4/8662224)"
  - "Plan 08-03 backend: POST /api/threads/{id}/messages?retry=true contract (merged on master e8c51b4)"
  - "Plan 08-01 backend: anon JWT acceptance via auth.py (merged on master 633a407)"
provides:
  - "AuthContext.isAnon: boolean — derived from user.is_anonymous"
  - "DemoPill — amber identity badge component"
  - "ErrorMessageBubble — in-thread red-wash error bubble with Retry button"
  - "useChat.retryLastUserMessage — callback that POSTs ?retry=true"
  - "LoginPage Try-demo CTA — anonymous-signin onboarding flow"
affects:
  - "frontend chat surface (ChatContainer + useChat error path)"
  - "frontend identity affordance (IconSidebar + MobileTopBar)"
  - "frontend login (LoginPage)"
tech-stack:
  added: []
  patterns:
    - "Anonymous Supabase auth via supabase.auth.signInAnonymously()"
    - "Sentry explicit captureException for caught errors (RESEARCH Pitfall 4)"
    - "Optimistic UI with role-replacement (assistant placeholder → error bubble in place)"
    - "Sibling-component pattern for distinct visual variant (ErrorMessageBubble vs MessageBubble)"
key-files:
  created:
    - "frontend/src/components/DemoPill.tsx"
    - "frontend/src/components/ErrorMessageBubble.tsx"
  modified:
    - "frontend/src/contexts/AuthContext.tsx"
    - "frontend/src/components/IconSidebar.tsx"
    - "frontend/src/components/MobileTopBar.tsx"
    - "frontend/src/pages/LoginPage.tsx"
    - "frontend/src/hooks/useChat.ts"
    - "frontend/src/components/ChatContainer.tsx"
    - "frontend/src/pages/ChatPage.tsx"
decisions:
  - "Used sibling-component path for the error bubble (UI-SPEC § Open Questions Q1 recommendation) — keeps MessageBubble role union narrow and isolates the icon+body+button structural delta."
  - "sendMessage signature extended with optional `{ retry?: boolean }` opts (rather than a separate retrySendMessage function) — single source of truth for the SSE stream lifecycle, no duplicated abort/decoder/dispatch logic."
  - "retryLastUserMessage strips role==='error' from messages state BEFORE the retry fires — the failed turn disappears the moment the new attempt starts; clean visual transition."
  - "ChatContainer's local Message interface duplicated the role union extension from useChat.ts. Did not promote to shared export (kept the existing per-file shape convention)."
metrics:
  duration: "~71 minutes"
  tasks_complete: 3
  tasks_deferred: 1
  files_created: 2
  files_modified: 7
  commits: 3
  completed: "2026-05-18"
---

# Phase 08 Plan 04: Frontend PORT-01 + PORT-02 Summary

One-liner: Anonymous Supabase auth onboarding (Try-demo CTA + Demo identity pill) plus graceful chat-stream error UX (in-thread red bubble + 4s toast + Sentry capture + manual Retry against backend's retry-aware POST), all frontend, zero new npm deps.

## What Was Built

**ALL TASKS COMPLETE (2026-05-18).** Tasks 1-3 code merged 2026-05-17. Task 4 (deployed UAT) completed 2026-05-18 across 3 runs against deployed CF Pages — final outcome **11/11 PASS** (item 11 DROPPED per Tavily-not-configured gap-fix). See `08-04-VERIFICATION.md` for full run-by-run record. Two gap-fixes landed during UAT cycle:
- `b5392f7` — bundle sample doc into Docker image + robust SAMPLE_DOC_PATH (items 3+4)
- `cb1a0d7` — useChat handles SSE `event: error` in-band data (item 8)

### Task 1 — AuthContext.isAnon + DemoPill + sidebar/topbar wiring (commit `a3fbda1`)

- `frontend/src/contexts/AuthContext.tsx`:
  - Extended `AuthContextType` with `isAnon: boolean`.
  - Computed `const isAnon = user?.is_anonymous ?? false` in the provider body.
  - Added `isAnon` to the Provider value object. No other shape change.
- `frontend/src/components/DemoPill.tsx` (NEW):
  - Default export, reads `isAnon` via `useAuth()`, returns `null` when `!isAnon`.
  - Locked Tailwind classes per UI-SPEC § Color: `inline-flex items-center justify-center px-2 py-0.5 rounded-full text-xs font-semibold bg-amber-500/15 text-amber-300 border border-amber-500/30`.
  - `role="status"`, `aria-label="Demo account"`, native `title` tooltip carrying the locked 7-day clarifier copy.
  - Label `Demo` — single word, verbatim.
- `frontend/src/components/IconSidebar.tsx`:
  - Imported `DemoPill` from `./DemoPill`.
  - Inserted `<DemoPill />` in BOTH render locations: desktop block (between the `flex-1` spacer and the LogOut button) and the drawer's `IconNavRow` block (same relative position).
- `frontend/src/components/MobileTopBar.tsx`:
  - Imported `DemoPill`.
  - Replaced the dead `<div className="h-11 w-11" />` right spacer with `<div className="h-11 w-11 flex items-center justify-center"><DemoPill /></div>` — wrapper preserves layout balance whether the pill renders or returns null.

### Task 2 — LoginPage Try-demo CTA (commit `eb768c7`)

- `frontend/src/pages/LoginPage.tsx`:
  - Added `import { apiFetch } from '../lib/api'`.
  - Added `handleTryDemo` async function mirroring `handleSubmit` shape: `setError('')` → `setLoading(true)` → `supabase.auth.signInAnonymously()` (throw on `error` or missing `session`) → `apiFetch('/api/demo/bootstrap', { method: 'POST' })` → `navigate('/', { replace: true })`. On any failure, sets the locked "Couldn't start the demo. Please try again." error. `setLoading(false)` in finally.
  - Inserted the CTA block BEFORE the existing `<form>`:
    - Primary CTA button: `type="button"`, `onClick={handleTryDemo}`, `disabled={loading}`, classes `w-full py-3 bg-blue-600 hover:bg-blue-700 rounded font-semibold disabled:opacity-50` (py-3 clears the ≥44px touch target per UI-SPEC § Spacing).
    - Label `{loading ? 'Setting up your demo…' : 'Try the demo'}` — note the single `…` character, not `...`.
    - Sub-label `<p className="text-xs text-gray-500 mt-2 text-center">No signup. Your demo session expires after 7 days.</p>`.
    - Divider block per UI-SPEC: horizontal rule with `or sign in with email` text floated on top via absolute positioning.
- All locked copy strings appear verbatim. No new state hooks (reuses existing `loading` and `error`).

### Task 3 — ErrorMessageBubble + useChat catch rewrite + ChatContainer wiring (commit `94a078c`)

- `frontend/src/components/ErrorMessageBubble.tsx` (NEW):
  - Imports `AlertCircle` + `RotateCw` from `lucide-react`.
  - Props: `{ onRetry: () => void; isStreaming: boolean }`.
  - Outer wrapper `<div className="flex justify-start mb-4">` (mirrors MessageBubble assistant-side alignment).
  - Inner container: `role="alert"` + `className="max-w-[85%] md:max-w-[70%] px-4 py-3 rounded-lg bg-red-950/40 border border-red-700 text-gray-100"` (mobile max-width expansion per UI-SPEC § Mobile behavior).
  - Two-row content: top = `AlertCircle` (size 16, text-red-400) + locked body `"The assistant ran into a problem. Try again, or rephrase your question."` in a `<p className="text-sm leading-[1.5]">`. Bottom = Retry button with `RotateCw` icon + `Retry` label, classes `inline-flex items-center gap-1 px-3 py-2.5 md:py-1.5 rounded text-sm font-semibold bg-blue-600 hover:bg-blue-700 text-white disabled:opacity-50 disabled:cursor-not-allowed` (`py-2.5` on mobile = ~44px touch, `py-1.5` on desktop = ~32px), `disabled={isStreaming}`.
- `frontend/src/hooks/useChat.ts`:
  - Imported `* as Sentry from '@sentry/react'` and `useToast` from `../contexts/ToastContext`.
  - Extended `Message.role` union to `'user' | 'assistant' | 'error'`.
  - Pulled `const { showToast } = useToast()` inside the hook.
  - `sendMessage` accepts optional `{ retry?: boolean }` opts. When `retry === true`: skips the optimistic user-message insert AND suffixes the POST URL with `?retry=true` so the backend (Plan 08-03 contract on master) deletes the orphan empty assistant row and skips re-inserting the user row.
  - Catch block rewrite — preserves the existing `AbortError` early-return; ADD `Sentry.captureException(err)` (RESEARCH Pitfall 4 — Sentry global handlers don't capture caught exceptions); REPLACES the empty assistant placeholder with a role='error' Message carrying the locked body copy; calls `showToast` with the locked toast copy + `'error'` variant.
  - New `retryLastUserMessage` callback: guards `isStreaming`, finds the most recent user message via `[...messages].reverse().find(m => m.role === 'user')`, strips all role==='error' messages, calls `sendMessage(lastUser.content, { retry: true })`.
  - Hook return expanded to include `retryLastUserMessage`.
- `frontend/src/components/ChatContainer.tsx`:
  - Imported `ErrorMessageBubble` and `useAuth`.
  - Extended local `Message.role` union to include `'error'`.
  - Added `onRetry: () => void` to Props.
  - Read `const { isAnon } = useAuth()` inside the component.
  - Empty-state copy now branches on `isAnon`: anon users see the locked `"Ask me about the board games in the library, or about the sample D&D 5e quick-reference that's already attached."` copy; non-anon retain `"Send a message to start the conversation."`.
  - `messages.map` now branches: `msg.role === 'error'` → `<ErrorMessageBubble key={msg.id} onRetry={onRetry} isStreaming={isStreaming} />`; else → existing `<MessageBubble />` (TypeScript narrows the role for the MessageBubble branch).
- `frontend/src/pages/ChatPage.tsx`:
  - Destructure now pulls `retryLastUserMessage` out of `useChat(activeThreadId)`.
  - `<ChatContainer ... onRetry={retryLastUserMessage} />` threads the callback down.

### Task 4 (COMPLETE 2026-05-18 — 11/11 PASS over 3 UAT runs)

12-point browser UAT executed against https://boardgame-rag-prod.pages.dev. Item 11 officially DROPPED (Tavily not provisioned). Final outcome **11/11 PASS**. Two gap-fixes landed during UAT cycle (committed before progressing):

- **Run #1 (initial):** items 1, 2, 5, 6 PASS; items 3, 4, 7, 8, 9, 10, 11 FAIL. Three root causes surfaced.
- **Run #2 (post Dockerfile + path patch `b5392f7`):** items 3, 4 PASS; item 8 still failed (frontend silent-swallow of SSE error event).
- **Run #3 (post useChat patch `cb1a0d7`):** items 7, 8, 9, 10 PASS — full 11/11 achieved.

See `08-04-VERIFICATION.md` for run-by-run detail + root-cause analysis. Wave 3 (Plan 08-06 asset capture) unblocked.

## Verification

### Build (PLAN.md §verification mandate — code-only verification)

```
> frontend@0.0.0 build
> tsc -b && vite build

vite v6.4.2 building for production...
transforming...
✓ 2321 modules transformed.
rendering chunks...
computing gzip size...
dist/index.html                   0.47 kB │ gzip:   0.30 kB
dist/assets/index-Ca5ksyZb.css   44.20 kB │ gzip:   7.88 kB
dist/assets/index-Cx5TZmI4.js   709.97 kB │ gzip: 213.05 kB │ map: 3,745.08 kB
(!) Some chunks are larger than 500 kB after minification. [non-blocking warning]
✓ built in 6.01s
```

**Zero TypeScript errors.** Bundle size warning is non-blocking and pre-existing.

### Lint

`npm run lint` reports **4 pre-existing errors only** (verified pre-existing — present on master prior to this plan's work; my edits did not touch the offending lines):

1. `frontend/src/components/FileUpload.tsx:5:56` — `@typescript-eslint/no-explicit-any`.
2. `frontend/src/contexts/AuthContext.tsx:48:17` — `react-refresh/only-export-components` (the existing `useAuth` named export coexisting with `AuthProvider`). My edits only modified the `AuthContextType` interface and provider value; the offending line just shifted from 45 → 48 due to the new `isAnon` lines.
3. `frontend/src/contexts/ToastContext.tsx:96:17` — same pattern, pre-existing.
4. `frontend/src/pages/ChatPage.tsx:37:5` — `react-hooks/set-state-in-effect`. Pre-existing; line just shifted from 36 → 37 because my destructure now spans two lines.

Tracked in `.planning/phases/08-portfolio-polish/deferred-items.md`. Out of scope for this plan per executor scope-boundary rule.

### Grep assertions (PLAN.md §verification — all PASS)

| Pattern | File | Expected | Got |
|---------|------|----------|-----|
| `isAnon` | `frontend/src/contexts/AuthContext.tsx` | ≥2 (type + value) | 3 |
| `from './DemoPill'` | `frontend/src/components/{IconSidebar,MobileTopBar}.tsx` | 2 files | 2 files |
| `bg-amber-500/15` | `frontend/src/components/DemoPill.tsx` | ≥1 | 1 |
| `import { apiFetch }` | `frontend/src/pages/LoginPage.tsx` | ≥1 | 1 |
| `signInAnonymously` | `frontend/src/pages/LoginPage.tsx` | ≥1 | 1 |
| `/api/demo/bootstrap` | `frontend/src/pages/LoginPage.tsx` | ≥1 | 1 |
| `Try the demo` | `frontend/src/pages/LoginPage.tsx` | ≥2 | 3 |
| `Setting up your demo…` (single `…`) | `frontend/src/pages/LoginPage.tsx` | ≥1 | 1 |
| `No signup. Your demo session expires after 7 days.` | `frontend/src/pages/LoginPage.tsx` | ≥1 | 1 |
| `or sign in with email` | `frontend/src/pages/LoginPage.tsx` | ≥1 | 1 |
| `Couldn't start the demo. Please try again.` | `frontend/src/pages/LoginPage.tsx` | ≥1 | 1 |
| `role="alert"` | `frontend/src/components/ErrorMessageBubble.tsx` | ≥1 | 1 |
| `bg-red-950/40` | `frontend/src/components/ErrorMessageBubble.tsx` | ≥1 | 1 |
| `AlertCircle` | `frontend/src/components/ErrorMessageBubble.tsx` | ≥1 | 2 (import + JSX) |
| `RotateCw` | `frontend/src/components/ErrorMessageBubble.tsx` | ≥1 | 2 (import + JSX) |
| `import * as Sentry from '@sentry/react'` | `frontend/src/hooks/useChat.ts` | ≥1 | 1 |
| `useToast` | `frontend/src/hooks/useChat.ts` | ≥1 | 2 (import + call) |
| `Sentry.captureException(err)` | `frontend/src/hooks/useChat.ts` | ≥1 | 1 |
| `'user' \| 'assistant' \| 'error'` | `frontend/src/hooks/useChat.ts` | ≥1 | 1 |
| `retryLastUserMessage` | `frontend/src/hooks/useChat.ts` | ≥2 | 2 (def + return) |
| `retry=true` | `frontend/src/hooks/useChat.ts` | ≥1 | 1 |
| `The assistant ran into a problem. Try again, or rephrase your question.` | `frontend/src/hooks/useChat.ts` | ≥1 | 1 |
| `The assistant didn't respond. Tap the message to retry.` | `frontend/src/hooks/useChat.ts` | ≥1 | 1 |
| `ErrorMessageBubble` | `frontend/src/components/ChatContainer.tsx` | ≥1 | 2 (import + JSX) |
| `isAnon` | `frontend/src/components/ChatContainer.tsx` | ≥1 | 2 (destructure + branch) |
| `sample D&D 5e quick-reference` | `frontend/src/components/ChatContainer.tsx` | ≥1 | 1 |
| `role === 'error'` | `frontend/src/components/ChatContainer.tsx` | ≥1 | 1 |
| `onRetry` | `frontend/src/components/ChatContainer.tsx` | ≥2 | 3 (Props + destructure + JSX prop) |

### No new npm dependencies

`git diff HEAD --stat -- frontend/package.json frontend/package-lock.json` is empty. The `@sentry/react`, `@supabase/supabase-js`, `lucide-react`, ToastContext, and apiFetch/apiStream APIs all pre-existed.

## Threat Model Status

All five threats from PLAN.md `<threat_model>` are mitigated or accepted as specified:

| Threat ID | Disposition | Status |
|-----------|-------------|--------|
| T-08-04-PII | mitigate | DONE — `Sentry.captureException(err)` uses the existing `lib/sentry.ts` init from Phase 7. `beforeSend` strips Authorization headers + zeroes `event.user`. No `Sentry.setUser()` call introduced. |
| T-08-04-XSS | accept | DONE — body copy is a static string literal, React auto-escapes, no `dangerouslySetInnerHTML`. |
| T-08-04-RETRY-DOS | mitigate | DONE — Retry button `disabled={isStreaming}`; `retryLastUserMessage` guards `if (isStreaming) return`. Existing per-user `/api/chat` rate-limit (Phase 6) still applies. No auto-retry. |
| T-08-04-ANON-LEAK | accept | DONE — Demo pill is intentional; tooltip discloses 7-day cleanup. |
| T-08-04-COPY | mitigate | DONE — all error/CTA copy verbatim from UI-SPEC § Copywriting Contract; greps confirm no provider names / no HTTP codes. |

## Deviations from Plan

Plan executed exactly as written. No Rule 1/2/3 auto-fixes were necessary during Task 1/2/3 implementation. Lint pre-existing errors are out of scope (scope-boundary rule); logged to `deferred-items.md`.

The only mid-execution incident was a self-recovered worktree path drift on Task 1's first Edit/Write batch — the initial Edit/Write tool calls landed in the main repo rather than the worktree. Detected via `git status` mismatch immediately after the build call. Recovered by `cp`-ing the correct file contents into the worktree and `git checkout --` reverting the 3 modified files in main repo plus `rm`-ing the misplaced `DemoPill.tsx`. Main repo verified clean post-recovery; worktree HEAD verified on `worktree-agent-a46f37256e4d8e583` per the per-commit safety assertion. All subsequent Task 1/2/3 edits used worktree-prefixed absolute paths and landed correctly (verified via dual `git status` after each Edit/Write).

## Caveat on Anon Auth End-to-End Correctness

Per orchestrator dispatch, **the anon flow's end-to-end correctness depends on Plan 08-00 Task 1 confirming `aud="authenticated"` empirically** in a real prod anon JWT. The current `backend/auth.py` (on master) requires `aud="authenticated"`. If the user reports the prod anon JWT actually carries `aud="anon"` or some other value, a one-line widening of `auth.py` to `audience=["authenticated", "anon"]` lands separately + redeploys — the **frontend code here is unaffected**. No backend files touched in this plan.

## Self-Check: PASSED

**Files claimed created — verified exist:**
- `frontend/src/components/DemoPill.tsx` — FOUND
- `frontend/src/components/ErrorMessageBubble.tsx` — FOUND

**Files claimed modified — verified diffed from HEAD:**
- `frontend/src/contexts/AuthContext.tsx` — FOUND (committed in a3fbda1)
- `frontend/src/components/IconSidebar.tsx` — FOUND (committed in a3fbda1)
- `frontend/src/components/MobileTopBar.tsx` — FOUND (committed in a3fbda1)
- `frontend/src/pages/LoginPage.tsx` — FOUND (committed in eb768c7)
- `frontend/src/hooks/useChat.ts` — FOUND (committed in 94a078c)
- `frontend/src/components/ChatContainer.tsx` — FOUND (committed in 94a078c)
- `frontend/src/pages/ChatPage.tsx` — FOUND (committed in 94a078c)

**Commits claimed — verified in git log:**
- `a3fbda1` — FOUND (Task 1 commit)
- `eb768c7` — FOUND (Task 2 commit)
- `94a078c` — FOUND (Task 3 commit)
