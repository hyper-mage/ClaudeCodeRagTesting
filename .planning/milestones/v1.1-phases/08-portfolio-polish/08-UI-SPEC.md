---
phase: "08"
slug: portfolio-polish
status: draft
shadcn_initialized: false
preset: none
created: 2026-05-17
---

# Phase 08 — UI Design Contract

> Visual and interaction contract for Phase 8 (Portfolio Polish). Scope is limited to the two UI-visible surfaces called out in Phase 8 success criterion #5: the **"Try demo" CTA** on the LoginPage (PORT-01) and the **graceful chat error surface** — inline error bubble plus simultaneous toast with manual Retry (PORT-02). README / architecture diagram / screenshots / badges (PORT-03/04) are documentation work and intentionally not specified here.

---

## Scope (in / out)

**In scope (this contract):**
- LoginPage: "Try demo" CTA element (placement, copy, visual treatment, loading + error states, mobile behavior).
- Chat error surface: in-thread error bubble variant of `MessageBubble`, simultaneous toast via the existing `ToastProvider`, manual **Retry** button wiring and copy.
- Anon-mode "Demo" badge in the sidebar / mobile top bar (small footprint polish so a visitor always knows they are in the ephemeral demo identity).

**Out of scope (handled elsewhere or explicitly silent):**
- Tool-level failures (rerank, web_search, analyze_document subagent) — locked **silent, no UI** by CONTEXT.md D-08. Do not add per-tool warning chips.
- Demo-mode UI gating (read-only mode, hidden uploads, etc.) — explicitly rejected (D-05). Anon users get the full app.
- Anon-cleanup bootstrap call and starter-content seeding flow — backend / planner concern; no visible UI other than the standard `useDocuments` Supabase Realtime status (already wired) for the seeded sample PDF.
- README / `docs/MASTERCLASS.md` / architecture asset / screenshots / badges — documentation deliverables (PORT-03/04), not UI-SPEC.

---

## Design System

| Property | Value |
|----------|-------|
| Tool | none (manual Tailwind, no shadcn) |
| Preset | not applicable (`components.json` does not exist; Tailwind 4 zero-config via `@import "tailwindcss"` in `frontend/src/index.css`) |
| Component library | none — bespoke React components in `frontend/src/components/` |
| Icon library | `lucide-react` ^0.577.0 (already imported in `IconSidebar`, `MobileTopBar`, `FileUpload`, etc.) |
| Font | system default (no `font-family` declared in `index.css`; inherits browser/UA stack) |

**Toast primitive:** Reuse the existing `ToastProvider` at `frontend/src/contexts/ToastContext.tsx` and its `useToast()` hook. It already exposes `error | warning | success | info` variants, auto-dismisses at 4000 ms, and renders fixed bottom-right with `aria-live="polite"`. **Do not add a new toast library** (e.g. sonner, react-hot-toast) — the existing primitive is sufficient for D-06.

---

## Spacing Scale

Declared values (multiples of 4, mirrors Tailwind's default 4px base — these are the values this phase will use, not a new scale invention):

| Token | Value | Tailwind class | Usage in this phase |
|-------|-------|----------------|---------------------|
| xs | 4px | `p-1` / `gap-1` | Icon-to-text gap inside Try-demo CTA, inside error bubble |
| sm | 8px | `p-2` / `gap-2` / `mb-2` | Vertical stack between Try-demo CTA and the "or sign in" divider; toast item gap |
| md | 16px | `p-4` / `gap-4` / `mb-4` | Default padding inside the LoginPage card body block; spacing between Try-demo block and email/password form |
| lg | 24px | `p-6` / `mb-6` | Outer LoginPage card padding (already `p-6` in current code) |
| xl | 32px | `p-8` | Not used in this phase |
| 2xl | 48px | `h-12` | Mobile top bar height (already locked in Phase 06.1) |
| 3xl | 64px | `h-16` | Not used in this phase |

**Exceptions:**
- **Touch targets: minimum 44px square** (`h-11 w-11`) for any interactive element on mobile. This already applies to `MobileTopBar`'s hamburger; the Try-demo CTA inherits the existing form button height pattern (`py-2`, which on the current `text-base` produces ~40px — bump to `py-3` to clear 44px on the demo button specifically since it's the most-clicked element on the page).
- **Error bubble max-width: 70%** (matches existing `MessageBubble.tsx` line 19 `max-w-[70%]`).

---

## Typography

The codebase has no formal type scale today. This contract declares one based on what is already used, kept to 4 sizes + 2 weights:

| Role | Size | Weight | Line Height | Tailwind |
|------|------|--------|-------------|----------|
| Display | 24px | 700 (bold) | 1.2 | `text-2xl font-bold` (LoginPage title — unchanged) |
| Heading | 16px | 600 (semibold) | 1.2 | `text-base font-semibold` (MobileTopBar title; "Try demo" button label inherits this) |
| Body | 14px | 400 (regular) | 1.5 | `text-sm` (toast bodies, error bubble copy, inline form errors, secondary text) |
| Label | 12px | 400 (regular) | 1.4 | `text-xs` (button captions like "Hide tools", auxiliary hints like the demo-mode badge) |

**Hard constraints:**
- Maximum **4** sizes total. No `text-lg`, `text-xl`, `text-3xl`, etc. in new code for this phase.
- Maximum **2** weights total: 400 (regular) and 600/700 (semibold/bold). No `font-medium`, `font-extrabold`. Display uses 700 because the existing `font-bold` on the login page already does; if a checker flags this as a third weight, the resolution is to convert Display to `font-semibold` (600) and match Heading.
- Body line-height **1.5** is required for any multi-line error bubble copy and the toast body (improves readability of the generic error sentence).

---

## Color

The existing palette is **dark-only**, anchored on Tailwind's `gray-*` and `blue-*` ramps, with red used for errors. The 60/30/10 split below matches what is already in production:

| Role | Value | Tailwind | Usage |
|------|-------|----------|-------|
| Dominant (60%) | `#030712` | `bg-gray-950` | LoginPage background, app body background |
| Secondary (30%) | `#111827` / `#1f2937` | `bg-gray-900` / `bg-gray-800` | `bg-gray-900` for IconSidebar / MobileTopBar / form inputs / cards; `bg-gray-800` for the assistant message bubble and active-nav-pill states |
| Accent (10%) | `#2563eb` | `bg-blue-600` (hover `bg-blue-700`) | **Reserved for primary action only** — see list below |
| Destructive (error) | `#b91c1c` border `#ef4444` | `bg-red-700` border `border-red-500` text `text-white` | Toast `error` variant (existing), error message bubble background |
| Destructive (subtle text) | `#f87171` | `text-red-400` | Inline form error under the Try-demo CTA on signin failure (matches existing LoginPage `text-red-400` pattern) |
| Anon-mode hint | `#f59e0b` | `text-amber-500` / `bg-amber-500/15 text-amber-300 border-amber-500/30` | **Reserved for the "Demo" identity badge only** — see "Anon-mode badge" below |

**Accent (`bg-blue-600`) reserved for, in this phase, exactly:**
1. The **"Try demo"** primary CTA button on `LoginPage`.
2. The existing **"Sign In" / "Sign Up"** submit button on the same form (unchanged).
3. The **Retry** button inside the error bubble (so the recovery action reads as the primary path forward).
4. Markdown link color in assistant messages (`text-blue-400`, unchanged).

It is **not** used for: the sidebar active state (that stays `bg-gray-800`), the toast info variant (stays `bg-gray-800`), the anon-mode badge (uses amber), or any decorative element.

**Destructive (`bg-red-*`) reserved for, in this phase, exactly:**
1. The chat **error message bubble** background.
2. The **error toast** that fires simultaneously with the bubble (already implemented in `ToastProvider.VARIANT_STYLES.error`).
3. The inline `text-red-400` line that appears under the Try-demo button if `signInAnonymously()` rejects.

**Amber (`amber-500` family) reserved for, in this phase, exactly:**
1. The **"Demo" pill / badge** rendered inside `IconSidebar` (desktop, near the bottom above Sign Out) and inside `MobileTopBar` (mobile, to the right of the title, replacing the current right-side spacer). Shown only when `user.is_anonymous === true`. Copy: `Demo`.

No other colors enter this phase. Specifically: no green (no success state for chat success — success is the absence of error), no purple, no teal, no custom hex.

---

## Copywriting Contract

All copy must be **specific, non-technical, and free of provider names or HTTP codes** per CONTEXT.md D-09.

| Element | Copy | Notes |
|---------|------|-------|
| Try demo CTA — button label | **Try the demo** | Verb + noun phrase. NOT "Try demo" alone (less clear) and NOT "Login as guest" (visitor isn't a guest, they're trying a product). |
| Try demo CTA — sub-label below button | No signup. Your demo session expires after 7 days. | One-line clarifier. Sets expectation that data is ephemeral without scaring the user. The 7-day window mirrors the opportunistic-purge in D-03. |
| Try demo CTA — divider | or sign in with email | Lowercase, sits between the demo block and the email/password form. |
| Try demo CTA — loading state | Setting up your demo… | Replaces button label while `signInAnonymously()` + `/api/demo/bootstrap` are in flight. Trailing ellipsis (single character `…`, not three dots). |
| Try demo CTA — error state (inline, `text-red-400 text-sm` under button) | Couldn't start the demo. Please try again. | No provider name, no HTTP code, no Supabase mention. |
| Chat error bubble — body | The assistant ran into a problem. Try again, or rephrase your question. | Generic per D-09. "Ran into a problem" reads as a momentary hiccup, not a system failure. "Or rephrase" gives the user agency without blaming them. |
| Chat error bubble — Retry button label | Retry | Single word. The button is the primary action inside the bubble; copy stays minimal because the bubble context already explains what's being retried. |
| Chat error toast — body | The assistant didn't respond. Tap the message to retry. | Slightly different wording than the bubble so the two surfaces are not literal duplicates. Toast disappears in 4 s (existing `AUTO_DISMISS_MS`); the bubble persists until the user retries or sends a new message. |
| Chat error toast — variant | `error` | Use `showToast(msg, 'error')` — red ramp. |
| Anon-mode badge | Demo | Single word, amber pill. Tooltip on hover (desktop): `You're using a temporary demo account. Data is cleared after 7 days.` |
| Chat empty state (when anon user lands and has 0 messages in seeded thread) | Ask me about the board games in the library, or about the sample D&D 5e quick-reference that's already attached. | Replaces the current generic "Send a message to start the conversation." (ChatContainer.tsx:32) for anon users only. The sample-PDF mention surfaces the cross-domain RAG pitch from CONTEXT.md `<specifics>`. Non-anon users keep the existing empty-state copy. |

**Destructive actions in this phase:** none. The Try-demo flow is additive; the Retry flow re-sends a message (recoverable, not destructive); the existing Sign Out, Delete Thread, and Delete Document flows already in the app are not touched by this phase. No new confirmation modals required.

---

## Surface 1 — Try Demo CTA (PORT-01)

**Location:** `frontend/src/pages/LoginPage.tsx`, **above** the email/password form (locked by D-04).

**Visual structure (top to bottom inside the existing `max-w-sm p-6` card):**

```
┌────────────────────────────────────┐  ← w-full max-w-sm, p-6, bg-gray-950
│  Try the demo                      │  ← bg-blue-600 hover:bg-blue-700
│  (full-width, h≈48px, py-3)        │     text-white font-semibold text-base
├────────────────────────────────────┤  ← text-xs text-gray-500 mt-2, centered
│  No signup. Your demo session …    │
├────────────────────────────────────┤  ← my-6 horizontal rule: border-gray-800
│  or sign in with email             │     with text-xs text-gray-500 centered
├────────────────────────────────────┤
│  [ Email input ]                   │  ← existing form, unchanged
│  [ Password input ]                │
│  [ Sign In ]                       │
└────────────────────────────────────┘
```

**Interaction:**
- Click → `setLoading(true)` → call `supabase.auth.signInAnonymously()` → on success, call `POST /api/demo/bootstrap` (planner-defined endpoint) → on bootstrap success, `navigate('/', { replace: true })`. On either failure, render inline error copy under the button and re-enable.
- Disabled state mirrors existing Sign In button: `disabled:opacity-50`, `cursor-not-allowed`.
- The button is the **first** focusable element on the page (focus order: Try demo → Email → Password → Sign In → mode-toggle link).

**Mobile (≤768px):**
- No layout change. The `max-w-sm` card already fits a 375px viewport with 12px breathing room on each side. The CTA is full-width within the card.
- Touch target height = 48px (`py-3` + `text-base` line-height ≈ 24px). Clears the 44px minimum.

**Loading affordance:** Inline label swap, no spinner SVG. Same pattern as existing `{loading ? 'Loading...' : ...}` line, but using the locked copy `Setting up your demo…`.

---

## Surface 2 — Graceful Chat Error (PORT-02)

**Trigger:** Any failure in `useChat.sendMessage` after the assistant placeholder has been added — i.e. the SSE stream errors, returns non-OK, the `apiStream` rejects, the reader throws, or the `done` event never arrives before the connection closes. (Today the catch block at `useChat.ts:188–195` swallows this with `console.error` and removes the placeholder. That branch is the dispatch point.)

**Dual surface (locked by D-06):**

### Inline error bubble (replaces the empty assistant placeholder, in-thread)

- New `MessageBubble` variant: extend the existing `role: 'user' | 'assistant'` prop to also accept `'error'`, OR sibling-render an `<ErrorMessageBubble />`. Planner chooses; UI requirements below are equivalent for both shapes.
- Visual treatment:
  - Container: `max-w-[70%]` (matches existing bubble width), `px-4 py-3`, `rounded-lg`, `bg-red-950/40` background with `border border-red-700` (subtle red wash — not the loud `bg-red-700` of the toast, because the bubble persists in the thread and full-saturation red would dominate the scroll).
  - Aligned **left** (same side as assistant bubbles) so the visitor reads it as "the assistant tried and failed", not as a user-side message.
  - Icon: `AlertCircle` from `lucide-react`, size 16, `text-red-400`, inline-flex with the body copy. 8px gap.
  - Body copy: the locked sentence from the Copywriting table, `text-sm text-gray-100`, line-height 1.5.
  - Retry button: appears as a second row inside the bubble. `inline-flex items-center gap-1 px-3 py-1.5 rounded text-sm font-semibold bg-blue-600 hover:bg-blue-700 text-white`. Optional `RotateCw` lucide icon at size 14 on the left. Label: `Retry`.
- **Persistence:** the bubble stays in `messages` array until either (a) the user clicks Retry (which removes it and re-fires `sendMessage` with the last user content), or (b) the user sends a new message (which pushes it up the scroll like any other message).

### Toast (simultaneous, ephemeral)

- Reuse `useToast()`. In the same `catch` block that dispatches the bubble, call:
  ```ts
  showToast("The assistant didn't respond. Tap the message to retry.", 'error')
  ```
- Auto-dismisses at 4 s via existing `AUTO_DISMISS_MS`.
- Positioned bottom-right (existing fixed positioning); no change to ToastProvider.

### Retry behavior (locked by D-07)

- Click handler:
  1. Find the last `role: 'user'` message in `messages` (this is the trigger that caused the failure).
  2. Remove the error bubble from `messages`.
  3. Call `sendMessage(lastUserMessage.content)` again on the same thread.
- **No auto-retry.** No backoff. No retry counter UI. If the second attempt also fails, the same bubble + toast pair re-appears.
- Retry button is **disabled while `isStreaming` is true** (so a user can't double-fire while a fresh attempt is mid-stream).

### Mobile behavior (≤768px)

- Error bubble: width expands to `max-w-[85%]` on mobile (`max-w-[70%] md:max-w-[70%]` → `max-w-[85%] md:max-w-[70%]`) so the copy + Retry button comfortably fit on a 375px viewport.
- Retry button: must clear 44px touch target. `py-1.5` + `text-sm` gives ~32px → bump to `py-2.5` on mobile (`py-2.5 md:py-1.5`). Or use `min-h-11 md:min-h-0`.
- Toast: existing `fixed bottom-4 right-4 max-w-sm` already mobile-safe; no change. Confirm the toast does not collide with the open mobile drawer (drawer has `z-50` — toast already at `z-50`, drawer takes priority; acceptable since drawer-open state is a deliberate user action).

### Tool-failure handling (locked silent by D-08)

- **No UI element** for rerank / web_search / analyze_document failures. The agent loop continues without the failed tool's result.
- The existing per-tool `try/except` in `backend/routers/chat.py` already returns `{error: ...}` to the LLM; do not surface that JSON to the frontend in any visible way for this phase.
- LangSmith (backend) and Sentry (frontend) already capture these silently per Phase 7.

---

## Surface 3 — Anon-Mode "Demo" Badge (auxiliary polish)

**Why this surface exists:** CONTEXT.md says demo-mode UI gating is rejected (D-05), but it does *not* forbid a passive identity hint. A visitor who clicked "Try the demo" and lands in chat has no current way to know they're on a throwaway account vs. a permanent one. A small badge prevents the "wait, did I sign up by accident?" moment that a portfolio reviewer would otherwise hit when they see uploads / threads / delete buttons.

**Data source:** `useAuth()` already exposes `user`. Supabase's `User` object includes `is_anonymous: boolean` for anon sessions. Add a derived `isAnon = user?.is_anonymous ?? false` value to `AuthContext` (or read it inline in components — planner chooses; CONTEXT.md `<canonical_refs>` already flags `AuthContext.tsx` as needing this).

**Render locations:**

1. **Desktop IconSidebar** (`frontend/src/components/IconSidebar.tsx`): immediately above the `<LogOut />` button (i.e. between the `flex-1` spacer and the logout). Pill shape:
   - `inline-flex items-center justify-center px-2 py-0.5 rounded-full text-xs font-semibold bg-amber-500/15 text-amber-300 border border-amber-500/30`
   - Label: `Demo`
   - Tooltip on hover (native `title` attribute is fine — matches existing IconSidebar pattern): `You're using a temporary demo account. Data is cleared after 7 days.`
   - Hidden if `isAnon === false`.

2. **Mobile MobileTopBar** (`frontend/src/components/MobileTopBar.tsx`): replace the current right-side spacer `<div className="h-11 w-11" />` (line 32) with the same pill when `isAnon === true`, sized to fit (44px touch area is not needed because the pill is non-interactive on mobile — it's display-only; keep `h-11` for layout balance but content sits centered).
   - When `isAnon === false`, keep the existing spacer so the title stays visually centered.

3. **Drawer top row** (`IconNavRow` in `IconSidebar.tsx`): same pill, rendered after the existing `<div className="flex-1" />` so it sits between the spacer and the Logout button. Mirrors the desktop layout.

**Not rendered on:** LoginPage (the user obviously knows they're trying to log in — no need), ToolCallCard, MessageBubble, or anywhere inside the chat scroll surface.

---

## Component Inventory (this phase)

| Component | Path | New / Modified | Purpose |
|-----------|------|----------------|---------|
| `LoginPage` | `frontend/src/pages/LoginPage.tsx` | **Modified** | Add Try-demo CTA block above existing form. |
| `MessageBubble` | `frontend/src/components/MessageBubble.tsx` | **Modified** OR new sibling `ErrorMessageBubble.tsx` (planner choice) | Render error variant with red wash + Retry button. |
| `ChatContainer` | `frontend/src/components/ChatContainer.tsx` | **Modified** | Pass `onRetry` callback down to error bubbles; update empty-state copy for anon users. |
| `useChat` | `frontend/src/hooks/useChat.ts` | **Modified** | Replace `console.error` swallow at L188–195 with: insert error-variant message into `messages` array + call `showToast('…', 'error')`. Expose a `retryLastUserMessage()` callback. |
| `IconSidebar` (+ `IconNavRow`) | `frontend/src/components/IconSidebar.tsx` | **Modified** | Render Demo pill above Sign Out when `isAnon`. |
| `MobileTopBar` | `frontend/src/components/MobileTopBar.tsx` | **Modified** | Render Demo pill in right slot when `isAnon`. |
| `AuthContext` | `frontend/src/contexts/AuthContext.tsx` | **Modified** | Surface `isAnon: boolean` derived from `user.is_anonymous`. |
| `ToastProvider` / `useToast` | `frontend/src/contexts/ToastContext.tsx` | **Reused, NOT modified** | Already supports `'error'` variant; no API change. |

**No new npm dependencies.** All visual primitives are built from Tailwind utilities + `lucide-react` icons already in the bundle. No `framer-motion`, no `sonner`, no `react-hot-toast`, no shadcn registry items.

---

## Accessibility

- **Try-demo CTA:** native `<button type="button">`. Default focus-visible ring (Tailwind 4 ships one). `aria-label` not required — the visible label is unambiguous.
- **Error bubble:** wrap in `role="alert"` so screen readers announce it when it appears. Retry button is a real `<button>` with text content — no `aria-label` needed.
- **Toast:** existing `ToastProvider` already declares `aria-live="polite" aria-atomic="true"` on the container and `role="status"` on each toast. Reuse as-is.
- **Anon-mode badge:** add `aria-label="Demo account"` to the pill since "Demo" alone is ambiguous without context for screen-reader users.
- **Keyboard:** Retry button must be Tab-focusable. The error bubble itself is not focusable (it's a static container).
- **Color contrast:** all combinations above clear WCAG AA (`text-white` on `bg-blue-600` = 4.55:1, `text-gray-100` on `bg-red-950/40` over `bg-gray-950` = >7:1, `text-amber-300` on `bg-amber-500/15` over `bg-gray-900` = ~4.6:1). Spot-check during implementation with browser devtools contrast checker.

---

## Registry Safety

| Registry | Blocks Used | Safety Gate |
|----------|-------------|-------------|
| shadcn official | none | not applicable (project does not use shadcn; `components.json` not present) |
| third-party | none | not applicable |

No registry vetting required for this phase. All components are bespoke and live in `frontend/src/components/` per the project's existing convention.

---

## Open Questions for Planner / Developer

These do not block the contract but are explicitly handed off:

1. **Error-bubble component shape** (locked open by CONTEXT.md "Claude's Discretion"): extend `MessageBubble` with an `'error'` role, OR add a sibling `ErrorMessageBubble.tsx`. Both satisfy this contract. Recommendation: sibling component — the existing `MessageBubble.tsx` already branches on role for layout (`justify-end` vs `justify-start`) and content rendering (markdown vs plain text); adding a third branch for a structurally different element (icon + body + button) is more code than a new 30-line component.
2. **Where the Retry handler lives:** simplest is to lift `messages` state up so `ChatContainer` can call `useChat.retryLastUserMessage()`. Planner decides whether to expose a new callback from `useChat` or have the error bubble accept an `onRetry` prop wired by `ChatContainer`.
3. **Sample empty-state copy gating:** the anon-specific empty state ("Ask me about… the sample D&D 5e quick-reference") assumes the seeded sample PDF lands successfully. If seeding is async and may not be done by the time the user reaches the chat, the empty-state copy should fall back to a generic version for anon users with no docs yet. Planner to confirm seeding timing.

---

## Checker Sign-Off

- [ ] Dimension 1 Copywriting: PASS
- [ ] Dimension 2 Visuals: PASS
- [ ] Dimension 3 Color: PASS
- [ ] Dimension 4 Typography: PASS
- [ ] Dimension 5 Spacing: PASS
- [ ] Dimension 6 Registry Safety: PASS (N/A — no registry)

**Approval:** pending
