---
phase: 14-usage-cost-display-settings-key-state-ux
plan: 03
subsystem: ui
tags: [react, typescript, tailwind, cost-display, usage, byok, error-recovery, pkce]

# Dependency graph
requires:
  - phase: 14-02
    provides: "useChat exported Usage interface; Message.usage (live done.usage + reloaded) + Message.errorType (no_api_key|payment_required|forbidden); typed key-failure path with toast suppression"
  - phase: 14-01
    provides: "MessageResponse.usage on history load; mid-stream 401->no_api_key / 403->forbidden / 402->payment_required SSE codes"
provides:
  - "MessageBubble: always-visible muted per-message cost caption on assistant bubbles (null-cost / token-format safe)"
  - "ErrorMessageBubble: typed in-thread recovery variant keyed on errorType (401/402/403) with mapped action buttons (light+dark), generic Retry path preserved"
  - "ChatContainer: reload-stable per-thread Sigma total in the existing header row + usage/errorType passthrough; local Message dup replaced by the useChat type"
affects: [14-04, 14-05, frontend-usage-cost-display, frontend-key-state-ux]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Render-only cost surfaces: cost shown exactly as OpenRouter reports it (no client recomputation); persisted usage.cost sum is the per-thread source of truth (reload-stable)"
    - "Typed recovery bubble keyed on the structured errorType code (never the raw detail/error/sk-or fragment); [Reconnect] reuses the existing PKCE OAuth flow, [Add credits] is a static external link"

key-files:
  created: []
  modified:
    - frontend/src/components/MessageBubble.tsx
    - frontend/src/components/ErrorMessageBubble.tsx
    - frontend/src/components/ChatContainer.tsx

key-decisions:
  - "ChatContainer imports Message from useChat (deleted the local Message/ToolEvent dups) — single source of truth, satisfies tsc strict against the Plan-02 hook contract"
  - "CostLine joins a cost part and a tokens part with the locked ' · ' separator and filters out null parts, so a free turn renders '840 tok' and a cost-only turn still renders cleanly; renders nothing when neither is present"
  - "Added an optional onUseDemo handler prop to ErrorMessageBubble so the gated [Use demo] button has an action; it is never rendered this phase (demoEligible=false), Phase 15 owns enabling it"

requirements-completed: [COST-01, COST-04, PREF-01]

# Metrics
duration: ~12min
completed: 2026-06-29
---

# Phase 14 Plan 03: Cost Surfaces + Typed Mid-Chat Recovery Bubble Summary

**Rendered the three user-visible cost/recovery surfaces against the Plan-02 hook contract — a muted per-message cost caption on assistant bubbles, a reload-stable per-thread Σ total in the existing header row, and a typed in-thread `ErrorMessageBubble` recovery variant (401/402/403) with code-mapped action buttons — pure render + wiring, no new fetches and no client-side cost recomputation.**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-06-29 (approx)
- **Completed:** 2026-06-29
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments

- **MessageBubble (COST-01):** added an optional `usage?: Usage` prop (imported from `useChat`) and a muted `CostLine` rendered at the bottom of the assistant flex column **only** (never on user bubbles). Format is the locked `${cost} · ${tokens} tok` — `$0.0021` (cost to 4dp) and `1.2k tok`/`840 tok` via a `formatTokens` helper (`1.2k` for ≥1000 dropping a trailing `.0`, integer otherwise). The cost segment **and** the `·` separator are omitted when `usage.cost` is null/absent (free model → `840 tok`); the caption renders nothing when there is no displayable figure. Locked muted token `text-xs text-gray-600 dark:text-gray-400 mt-1` (not `gray-500` on white — Phase 13 contrast guardrail).
- **ErrorMessageBubble (PREF-01 / D-09):** extended `Props` with optional `type` (`no_api_key|payment_required|forbidden`), `demoEligible` (default `false`), and `onUseDemo`. When `type` is set, renders the typed variant with the locked sentence + mapped buttons; otherwise the existing generic Retry path is returned untouched. The typed container carries **both** light (`bg-red-50 border-red-300 text-gray-900`, icon `text-red-600`) and dark (`bg-red-950/40 border-red-700 text-gray-100`, icon `text-red-400`) tokens. Buttons: 401 → `[Reconnect]` (primary blue-600); 402 → `[Add credits ⇗]` (primary anchor, `target="_blank" rel="noopener noreferrer"` to `openrouter.ai/settings/credits`) + `[Reconnect]` (secondary neutral); 403 → `[Reconnect]` (primary) + `[Use demo]` (secondary, gated behind `demoEligible`, hidden this phase). `[Reconnect]` runs `startOpenRouterConnect()` (PKCE). Only the structured copy is rendered — no `parsed.detail` / caught error / `sk-or` fragment.
- **ChatContainer (COST-04):** deleted the local `Message`/`ToolEvent` duplicates and now `import type { Message } from '../hooks/useChat'` (single source of truth, satisfies tsc strict). Computes `threadCost = messages.reduce((s, m) => s + (m.usage?.cost ?? 0), 0)` and renders a muted `Σ $${threadCost.toFixed(4)}` caption right-aligned (`ml-auto`) inside the **existing** `h-12` header row, only when `> 0` (reload-stable from persisted usage; no second header row). Passes `usage={msg.usage}` to `MessageBubble` and `type={msg.errorType}` + `demoEligible={false}` to `ErrorMessageBubble` (the `onRetry`/`isStreaming` generic path stays intact).

## Task Commits

Each task was committed atomically:

1. **Task 1: Per-message cost caption in MessageBubble** - `b2c7b27` (feat)
2. **Task 2: Typed recovery variant of ErrorMessageBubble** - `28aa130` (feat)
3. **Task 3: Wire Σ total + usage/typed-error passthrough in ChatContainer** - `7ce1963` (feat)

## Files Created/Modified

- `frontend/src/components/MessageBubble.tsx` — `usage?: Usage` prop; `formatTokens` + `CostLine` helpers; assistant-only muted cost caption.
- `frontend/src/components/ErrorMessageBubble.tsx` — typed recovery variant (light+dark tokens, code-mapped sentences + buttons, external Add-credits link, gated Use-demo); generic Retry path preserved.
- `frontend/src/components/ChatContainer.tsx` — imports `Message` from `useChat`; `threadCost` reduce + `Σ` header caption; `usage`/`type`/`demoEligible` passthrough.

## Decisions Made

- **Import `Message` from `useChat` instead of widening the local dup.** Cleanest way to satisfy the plan's "interface widening must satisfy tsc strict against the Plan-02 hook contract" — the imported type already carries `usage` + `errorType`, and TS control-flow narrowing through the message-map ternary still types `role` to `'user' | 'assistant'` for `MessageBubble`.
- **`CostLine` builds from filtered parts.** `[costPart, tokensPart].filter(Boolean).join(' · ')` yields the locked `$… · … tok` when both exist, `840 tok` for a free turn (no `$`, no `·`), and nothing when neither is present — exactly the null-cost contract.
- **Added an optional `onUseDemo` prop (minor extension, see Deviations).** A button needs an action; the prop is forward-looking for Phase 15 and is never wired this phase because `[Use demo]` is gated behind `demoEligible={false}`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Repaired a corrupted shared `@eslint-community/eslint-utils@4.9.1` package so lint could run**
- **Found during:** Task verification (`npm run lint`).
- **Issue:** The shared (main-checkout) `frontend/node_modules`, reused by the worktree via a junction, had `@eslint-community/eslint-utils` stripped of its code files (`index.js`/`index.mjs`/`index.d.ts`/`index.d.mts` missing — only `package.json`, `README.md`, nested `node_modules/` remained; dir mtime `15:32` today). This is a typescript-eslint dependency, so **all** of ESLint failed to load (`Cannot find module …/eslint-utils/index.js`) — unrelated to my three files. No `node`/`npm` process was running and the mtime was stable (not an in-progress install I'd race with); a junction `rmdir` removes only the link, never the target, so my junction work did not cause it.
- **Fix:** `npm pack @eslint-community/eslint-utils@4.9.1` into a scratch dir, extracted, and copied the four missing `index.*` files back into the shared package (purely additive — no existing file overwritten, no git-tracked file touched; `node_modules` is gitignored). This restores the shared install to a healthy state for the sibling Wave-3 agents too.
- **Files modified:** none in-repo (only the gitignored shared `node_modules`).
- **Commit:** n/a (gitignored environment repair, not a code change).

**2. [Minor extension] Optional `onUseDemo?: () => void` prop on ErrorMessageBubble**
- **Found during:** Task 2.
- **Issue:** The plan specifies `type` + `demoEligible` props; the gated `[Use demo]` button needs a click action to be meaningful.
- **Fix:** Added an optional `onUseDemo` handler. It is never reachable this phase (`demoEligible={false}`); Phase 15 owns wiring it.
- **Files modified:** `frontend/src/components/ErrorMessageBubble.tsx`.
- **Commit:** `28aa130`.

## Verification

- `npm run build` (tsc -b strict + vite) — **exit 0** (the harder gate; validates the `Message`-import interface widening against the useChat contract). The chunk-size note is a pre-existing Vite warning, not an error.
- `npm run lint` — the three changed files (`MessageBubble.tsx`, `ErrorMessageBubble.tsx`, `ChatContainer.tsx`) are **clean**. The only 5 reported errors are the documented pre-existing ones in files this plan did not touch (`FileUpload.tsx`, `AuthContext.tsx`, `ToastContext.tsx`, `ChatPage.tsx`, `themeBootstrap.test.ts` — already logged in `deferred-items.md` by Plan 02).
- Source assertions met: `MessageBubble` caption uses `text-gray-600 dark:text-gray-400`/`text-xs` and `tok`; `ErrorMessageBubble` contains the exact strings `Connect your OpenRouter account to keep chatting.`, `Your key is out of credit (402).`, `Your key was rejected (403).`, `Reconnect`, `Add credits`, the `target="_blank" rel="noopener noreferrer"` anchor to `openrouter.ai/settings/credits`, both light (`red-50`/`red-300`) and dark (`red-950/40`/`red-700`) tokens, `startOpenRouterConnect`, and the preserved generic Retry path; `ChatContainer` has a `messages.reduce(` sum, the `Σ` caption gated on `threadCost > 0` with `ml-auto` in the existing `h-12` row, `usage={msg.usage}`, and `type={msg.errorType}`.

## Build Environment Note

The worktree has no `node_modules`; a junction to the main checkout's `frontend/node_modules` was created (via `node fs.symlinkSync(..., 'junction')` after the `mklink` form was rejected by cmd quoting), used for build/lint, then **removed** before writing this SUMMARY. `frontend/node_modules` is gone from the worktree and the shared target is intact (`typescript/bin/tsc` present).

## Deferred Issues (pre-existing, out of scope)

The 5 ESLint errors above are all in files NOT touched by this plan (already logged to `deferred-items.md` by Plan 02). Not addressed here — out of scope per the executor scope boundary.

## Security (threat model verification)

- **T-14-11 (Information Disclosure, recovery copy):** the typed bubble renders only the locked UI-SPEC sentences selected from `errorType`; no `parsed.detail`, caught error, HTTP body, or `sk-or` fragment is interpolated (the `(401)/(402)/(403)` parentheticals are the structured taxonomy codes). **Mitigated.**
- **T-14-12 (Tampering/Spoofing, [Add credits ⇗] link):** the external anchor uses `target="_blank" rel="noopener noreferrer"` (no `window.opener` access). **Mitigated.**
- **T-14-13 (Information Disclosure, cost caption / Σ total):** cost + token counts are non-secret display values, shown exactly as reported (no recomputation). **Accepted per plan.**

## Known Stubs

None. `[Use demo]` is intentionally gated off (`demoEligible={false}`) for this phase per D-09 / UI-SPEC; Phase 15 owns enabling demo fallback. All other surfaces are wired to live data (`Message.usage`, `Message.errorType`).

## User Setup Required

None.

## Next Phase Readiness

- Cost surfaces and the typed recovery bubble are live and bound to the Plan-02 hook contract. Plans 04 (amber status dot) and 05 (settings balance line) bind to the same `useKeyStatus` contract and are unaffected by these render-only changes.
- STATE.md / ROADMAP.md intentionally NOT modified (worktree mode — orchestrator owns those writes after the wave).

## Self-Check: PASSED

All three modified files exist on disk (`MessageBubble.tsx`, `ErrorMessageBubble.tsx`, `ChatContainer.tsx`); this SUMMARY exists; all three task commits are reachable (`b2c7b27`, `28aa130`, `7ce1963`). `npm run build` passes (exit 0); the three changed files lint clean. The `frontend/node_modules` junction was removed (worktree clean).

---
*Phase: 14-usage-cost-display-settings-key-state-ux*
*Completed: 2026-06-29*
