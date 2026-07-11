---
phase: 14-usage-cost-display-settings-key-state-ux
plan: 02
subsystem: ui
tags: [react, hooks, typescript, sse, usage, cost, byok, balance, error-handling]

# Dependency graph
requires:
  - phase: 14-01
    provides: "MessageResponse.usage on history load; GET /api/keys/balance proxy returning {connected, limit_remaining, is_low}; mid-stream 401->no_api_key / 403->forbidden SSE codes"
  - phase: 11-byok-usage-capture
    provides: "messages.usage JSONB (cost+tokens summed across the tool loop); done SSE event carries usage; structured error taxonomy"
provides:
  - "useChat: exported Usage interface; Message.usage (live done.usage + reloaded) + Message.errorType (typed key-failure code)"
  - "useChat: typed key-failures (no_api_key|payment_required|forbidden) stamp errorType + empty content + suppress the toast; generic/network errors keep copy + toast"
  - "useKeyStatus: exported Balance interface; on-demand balance fetch + derived isLow + balanceLoading + balanceError; refreshBalance; no-poll/no-Realtime preserved"
affects: [14-03, 14-04, 14-05, frontend-usage-cost-display, frontend-key-state-ux, frontend-balance-indicator]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Typed SSE error code -> structured Message.errorType (never render parsed.detail) for the typed recovery bubble"
    - "On-demand balance fetch gated on session+connected, silent-on-error keeps last-known value, derived isLow read straight from the server is_low (no FE threshold)"

key-files:
  created: []
  modified:
    - frontend/src/hooks/useChat.ts
    - frontend/src/hooks/useKeyStatus.ts

key-decisions:
  - "Used the exact cross-plan contract names Wave 3 expects (isLow, balance.limit_remaining, balanceLoading, balanceError) so Plans 04/05 bind with no change"
  - "balanceLoading is a raw in-flight flag; the UI-SPEC 'Checking balance…' state is the consumer-side combination balanceLoading && balance === null"
  - "Balance fetch gated on connected so a no-key state never triggers a pointless OpenRouter round-trip; broadcast handler re-fetches BOTH status and balance so a post-turn poke refreshes balance even when connection state is unchanged"
  - "isLow defaults to false when balance is unknown / on transient failure — never clobbers the green dot (D-03/D-04)"

patterns-established:
  - "Typed key-failure path in useChat: stamp errorType, empty content, suppress toast (single in-thread surface, D-09); generic path keeps the dual-surface bubble+toast"
  - "Sibling on-demand fetch-into-state in useKeyStatus mirroring refresh (gate on session, silent-on-error, set loading in finally, no poll/Realtime)"

requirements-completed: [COST-01, COST-02, COST-03, COST-04, PREF-01]

# Metrics
duration: ~15min
completed: 2026-06-29
---

# Phase 14 Plan 02: Read-Hook Contract Layer (useChat usage/errorType + useKeyStatus balance/isLow) Summary

**Extended the two FE read hooks so per-message `usage` (live `done.usage` + reloaded), a typed key-failure `errorType` (no toast on that path), and an on-demand OpenRouter `balance` + derived `isLow` + loading/error are available to every Wave 3 render surface — the contract layer Plans 04/05 bind to.**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-06-29 (approx)
- **Completed:** 2026-06-29
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- `useChat`: added an exported `Usage` interface (`prompt_tokens?`, `completion_tokens?`, `total_tokens?`, `cost?`); `Message` now carries `usage?: Usage` and `errorType?: 'no_api_key' | 'payment_required' | 'forbidden'`.
- `useChat`: the `done` branch captures `usage: parsed.usage ?? m.usage` on the `message_id` swap; `loadMessages` maps `m.usage` so persisted usage survives a reload (D-02 source-of-truth).
- `useChat`: the outer `catch` detects the typed key-failure codes and stamps `{ role:'error', errorType, content:'' }` WITHOUT firing the toast (the in-thread bubble is the single surface, D-09); every other error (rate_limit, upstream_error, network) keeps the generic copy + 4s toast unchanged. AbortError early-return and `Sentry.captureException` preserved.
- `useKeyStatus`: added an exported `Balance` interface and an on-demand `refreshBalance` fetch (gated on `session` + `connected`), exposing `balance`, derived `isLow`, `balanceLoading`, `balanceError`, plus `refreshBalance`. No polling, no Realtime; `notifyKeyStatusChanged()` broadcast preserved and extended to re-fetch balance too.

## Hook contract / field names (CROSS-PLAN — Wave 3 binds to these VERBATIM)

The final exported names match the assumed Wave 3 contract exactly — **NO deviation, Plans 04 and 05 bind with no change required.**

`useKeyStatus()` returns:

```ts
{
  status: KeyStatus | null,
  loading: boolean,            // status-fetch loading (pre-existing)
  refresh: () => Promise<void>,
  balance: Balance | null,     // { connected, limit_remaining, is_low } or null
  isLow: boolean,              // = balance?.is_low ?? false  (server is_low; false when unknown)
  balanceLoading: boolean,     // true while a balance fetch is in flight
  balanceError: boolean,       // true when the last balance fetch threw (last-known balance kept)
  refreshBalance: () => Promise<void>,
}
```

Exported `Balance` interface:

```ts
export interface Balance {
  connected: boolean
  limit_remaining: number | null   // null = pay-as-you-go (uncapped); D-04
  is_low: boolean                   // server-computed; null remaining -> false
}
```

- **`isLow`** — name matches. Read straight from `balance.is_low`; defaults `false` when balance is null/unknown. (Plan 04 amber dot.)
- **`balance.limit_remaining`** — name matches; `number | null` (null = pay-as-you-go). (Plan 05 balance line.)
- **`balanceLoading`** — name matches; raw in-flight flag. For the UI-SPEC "Checking balance…" state, Plan 05 should use `balanceLoading && balance === null` (don't flash the spinner over an already-resolved value).
- **`balanceError`** — name matches; true when the fetch threw. For the "Balance unavailable right now." line, Plan 05 should use `balanceError && balance === null`.

`useChat()` `Message` additions consumed by Wave 3:

```ts
Message.usage?: Usage   // Usage = { prompt_tokens?, completion_tokens?, total_tokens?, cost? }
Message.errorType?: 'no_api_key' | 'payment_required' | 'forbidden'
```

## Task Commits

Each task was committed atomically:

1. **Task 1: Extend useChat — usage capture + typed errorType** - `45897af` (feat)
2. **Task 2: Extend useKeyStatus — balance fetch + derived isLow + loading/error state** - `d1f522c` (feat)

## Files Created/Modified
- `frontend/src/hooks/useChat.ts` - Added exported `Usage`; `Message.usage` + `Message.errorType`; `done.usage` capture; `loadMessages` usage map; typed-error stamping with toast suppression on the key-failure path.
- `frontend/src/hooks/useKeyStatus.ts` - Added exported `Balance`; `refreshBalance` on-demand fetch gated on session+connected; derived `isLow`; `balanceLoading`/`balanceError`; broadcast handler extended to re-fetch balance; no poll/Realtime.

## Decisions Made
- Chose the exact Wave 3 contract names (`isLow`, `balance.limit_remaining`, `balanceLoading`, `balanceError`) — zero rebind cost for Plans 04/05.
- `balanceLoading` kept as a raw in-flight flag (not "in-flight AND no resolved data"); the consumer composes the loading/failed states with `&& balance === null` so an existing value isn't masked during a refetch. Documented above for Plan 05.
- Balance fetch gated on `connected` (not just session) to avoid a pointless OpenRouter round-trip on the no-key state; broadcast handler re-fetches both status and balance so a post-turn poke refreshes balance even when connection is unchanged.

## Deviations from Plan

None - plan executed exactly as written. Field names match the assumed Wave 3 contract, so no rebind is required by Plans 04/05.

## Issues Encountered
- The worktree `frontend/` had no `node_modules` (and no `.bin/tsc`/`eslint`), so `npm run build`/`npm run lint` failed with "not recognized". Resolved by creating a Windows directory junction `frontend/node_modules -> <main checkout>/frontend/node_modules` (analogous to Wave 1's venv reuse). `node_modules` is gitignored, so it does not pollute git status or the commits. With the junction, `npm run build` (tsc strict + vite) and the two-file lint both run clean.

## Deferred Issues (pre-existing, out of scope)
`npm run lint` reports 5 errors, ALL in files NOT touched by this plan (verified pre-existing on base `caf3dec`; the two hook files I modified lint clean, exit 0). Logged to `deferred-items.md`:
- `src/components/FileUpload.tsx:5:56` — `@typescript-eslint/no-explicit-any`
- `src/contexts/AuthContext.tsx:48:17` — `react-refresh/only-export-components`
- `src/contexts/ToastContext.tsx:96:17` — `react-refresh/only-export-components`
- `src/pages/ChatPage.tsx:52:5` — `react-hooks/set-state-in-effect`
- `src/test/themeBootstrap.test.ts:24:17` — `@typescript-eslint/no-unused-vars`

`npm run build` (the harder strict-tsc gate) passes fully. The plan acceptance bar ("no NEW errors") is met.

## Security (threat model verification)
- T-14-08 (Information Disclosure, useChat error rendering): the typed path stores only the structured `errorType` code and sets `content: ''` — `parsed.detail` / raw error is never written to `content`. Mitigated.
- T-14-09 (Information Disclosure, balance in client state): the hook stores only `{connected, limit_remaining, is_low}` from the Plan-01 secret-free response. Accepted per plan.
- T-14-10 (DoS/quota, balance fetch frequency): on-demand only (mount + broadcast), gated on connected; no `setInterval`, no polling loop, no Supabase `.channel(`/Realtime. Mitigated.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- The hook contract is complete and the field names are locked + recorded above. Wave 3 surfaces can bind directly:
  - Plan 04 (amber dot / cost caption): read `Message.usage.cost`, `useKeyStatus().isLow`.
  - Plan 05 (settings balance line): read `balance`, `balance.limit_remaining`, `balanceLoading`, `balanceError`.
  - Typed recovery bubble: read `Message.errorType`.
- No blockers introduced. STATE.md/ROADMAP.md intentionally NOT modified (worktree mode — orchestrator owns those writes after the wave).

## Self-Check: PASSED

Both modified files exist on disk (`frontend/src/hooks/useChat.ts`, `frontend/src/hooks/useKeyStatus.ts`); the SUMMARY and `deferred-items.md` exist; both task commits are reachable (`45897af`, `d1f522c`). `npm run build` passes; the two hook files lint clean.

---
*Phase: 14-usage-cost-display-settings-key-state-ux*
*Completed: 2026-06-29*
