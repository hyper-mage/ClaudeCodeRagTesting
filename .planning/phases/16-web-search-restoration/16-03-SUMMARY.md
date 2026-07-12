---
phase: 16-web-search-restoration
plan: 03
subsystem: chat-ui
tags: [frontend, tool-card, sse, is_error, failed-state, react, typescript, d-03]

# Dependency graph
requires:
  - phase: 16-web-search-restoration
    plan: 02
    provides: "is_error boolean on every tool_result SSE event + 'error' tool_entry status — the backend contract this plan consumes"
provides:
  - "frontend/src/hooks/useChat.ts — 'error' member in the ToolEvent.status union + is_error→status mapping in the tool_result handler"
  - "frontend/src/components/ToolCallCard.tsx — red failed-state render (AlertTriangle + red border) keyed on status === 'error'"
  - "The at-a-glance failed-tool UX (SC-4 / WSRCH-04 / D-03) that plan 16-04's failure smoke visually confirms"
affects: [16-04, web-search-restoration, chat-ui, tool-card]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Generic-by-construction failed-state: the red branch keys on ToolEvent.status, so ANY tool returning {\"error\": ...} turns its card red — not web_search-specific"
    - "Union widening spans two coupled files (useChat.ts ToolEvent + ToolCallCard Props); the type gate is the atomic pair, verified by the full `npm run build` (tsc -b)"

key-files:
  created:
    - .planning/phases/16-web-search-restoration/16-03-SUMMARY.md
  modified:
    - frontend/src/hooks/useChat.ts
    - frontend/src/components/ToolCallCard.tsx

key-decisions:
  - "Cast the mapped status with `as ToolEvent['status']` rather than the plan's `as const` — a `const` assertion is illegal on a ternary expression (TS1355); the union-cast preserves the exact `? 'error' : 'complete'` shape and type-checks"
  - "borderColor gives status === 'error' precedence over the subagent (indigo) case, so a failed explorer sub-agent card still reads red at-a-glance"

patterns-established:
  - "Status-keyed failed-state render — reusable for any future tool that can fail"

requirements-completed: [WSRCH-04]

# Metrics
duration: 3min
completed: 2026-07-12
---

# Phase 16 Plan 03: Web-Search Frontend Failed-State Summary

**Two coordinated frontend edits deliver the D-03 / WSRCH-04 failed-tool UX: `ToolEvent.status` (and `ToolCallCard`'s matching `Props.status`) gains an `'error'` member, the `tool_result` SSE handler maps the backend `is_error` flag (plan 16-02) to `'error'` (else `'complete'`), and `ToolCallCard` renders a red `AlertTriangle` + red border on `status === 'error'` instead of the gray success check — so a failed web search (or any tool that returns `{"error": ...}`) is now unmistakable at a glance.**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-07-12T00:13:03Z
- **Completed:** 2026-07-12T00:16:02Z
- **Tasks:** 2
- **Files modified:** 2 (both production frontend)

## Accomplishments

- **Task 1 — `useChat.ts` (status union + is_error mapping):** Widened `ToolEvent.status` from `'running' | 'complete'` to `'running' | 'complete' | 'error'`. In the `tool_result` branch, changed the matched card's status assignment from the hardcoded `'complete'` to `(parsed.is_error ? 'error' : 'complete')`, keeping `output: parsed.output` and the `call_id` match intact. A missing/false `is_error` maps to `'complete'`, so loaded history, successful calls, and pre-16-02 payloads are unaffected. The `tool_start` ('running') and `sub_event` branches were left unchanged.
- **Task 2 — `ToolCallCard.tsx` (red failed-state):** Added `AlertTriangle` to the lucide-react import, widened `Props.status` to match `ToolEvent`, made the status-icon render a three-way (`running` → spinner; `error` → red `AlertTriangle` `text-red-500`; else → gray `Check`), and made `borderColor` `border-red-600` when `status === 'error'` (giving error precedence over the subagent/indigo and default/gray cases). The expand/collapse behavior, args-preview render, explorer sub-event block, and the raw-payload `<pre>` were all left untouched — the red header is the at-a-glance signal; the `<pre>` still exposes the `{"error": ...}` detail on expand.

## Task Commits

Each task was committed atomically:

1. **Task 1: is_error → 'error' ToolEvent status mapping** — `ac3c37e` (feat)
2. **Task 2: red AlertTriangle + red border failed-state on ToolCallCard** — `ca2c766` (feat)

**Plan metadata:** docs commit — this SUMMARY + STATE/ROADMAP/REQUIREMENTS.

## Files Created/Modified

- `frontend/src/hooks/useChat.ts` — `ToolEvent.status` union widened to include `'error'`; the `tool_result` handler maps `parsed.is_error` to the status (`? 'error' : 'complete'`), cast `as ToolEvent['status']`.
- `frontend/src/components/ToolCallCard.tsx` — `AlertTriangle` import; `Props.status` widened to match; three-way status icon; `border-red-600` on the error state.

## Verification

- `cd frontend && npm run build` → **exit 0** (`tsc -b` strict + `vite build`, 2332 modules transformed). The widened union type-checks across all three `ToolEvent` consumers — `useChat.ts`, `ToolCallCard.tsx`, and `MessageBubble.tsx` (which flows `t.status` into the card). The only build note is the pre-existing >500 kB chunk-size warning (out of scope, unchanged by this plan).
- `grep -q "status === 'error'" frontend/src/components/ToolCallCard.tsx && grep -q "parsed.is_error" frontend/src/hooks/useChat.ts` → both halves of the D-03 wiring present.
- Task acceptance greps (all PASS): union widened in both files, `parsed.is_error` consumed, `? 'error' : 'complete'` mapping present (defaults to complete), `AlertTriangle` imported + used, `status === 'error'` branch present, red styling (`text-red-500` / `border-red-600`) present.
- Visual confirmation of the red failed state is deferred to plan 16-04's failure smoke (the frontend has no test runner — VALIDATION §Manual-Only).

## Decisions Made

- **`as ToolEvent['status']` instead of the plan's `as const`.** The plan's interfaces suggested `(parsed.is_error ? 'error' : 'complete') as const`, but a `const` assertion is only valid on literal references, not a ternary expression — `tsc` raised TS1355. Casting to the union type (`ToolEvent['status']`) is the correct, minimal fix; it preserves the exact `? 'error' : 'complete'` shape the acceptance grep expects and type-checks cleanly. (See Deviations — Rule 1.)
- **Error takes precedence over subagent in `borderColor`.** A failed `explore_kb` sub-agent card should still read red, so `status === 'error'` is checked before the subagent (indigo) case.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed an illegal `as const` on a ternary in the plan's suggested snippet**
- **Found during:** Task 1 verification (`npx tsc --noEmit`).
- **Issue:** The plan's interface note prescribed `(parsed.is_error ? 'error' : 'complete') as const`. TypeScript rejects `as const` on a conditional expression (TS1355: "A 'const' assertions can only be applied to references to enum members, or string, number, boolean, array, or object literals"). The mapping would never compile as written.
- **Fix:** Changed the assertion to `(parsed.is_error ? 'error' : 'complete') as ToolEvent['status']`. Same runtime behavior, same `? 'error' : 'complete'` shape (grep-compatible), type-clean.
- **Files modified:** `frontend/src/hooks/useChat.ts`
- **Commit:** `ac3c37e`

### Execution note (not a code deviation)

- **Task 1's isolated `npx tsc --noEmit` could not exit 0 on its own** — the widened `ToolEvent.status` immediately fails to flow into `MessageBubble.tsx`'s `<ToolCallCard status={t.status} />` while `ToolCallCard.Props.status` is still narrow. This is inherent to an atomic two-file union widening (the plan itself notes the union "type-checks across useChat.ts + ToolCallCard.tsx"). `MessageBubble` is the third `ToolEvent` consumer that bridges the two. Task 2 widened `Props.status`, and the full `npm run build` (`tsc -b`) — the real type gate — passes clean. No extra files were touched to force Task 1's isolated check green.

## User Setup Required

None — pure frontend render change. No env vars, migrations, or deps. (Web search still requires `WEB_SEARCH_API_KEY` to activate the tool, an existing ops step unchanged by this plan; when the tool is enabled and a search fails, the card now shows the red state.)

## Known Stubs

None — `status` is a real computed value driven by the backend `is_error` flag; no hardcoded empty value flows to the UI.

## Issues Encountered

None beyond the Rule 1 `as const` bug documented above. The build's >500 kB chunk-size advisory is pre-existing and out of scope.

## Threat Surface

No new security-relevant surface beyond the plan's `<threat_model>`. T-16-10 (secret in the failed card) stays mitigated upstream — the `tool_result` payload carries only the output preview + `is_error`; the card adds no new data source, so no key reaches the DOM. T-16-11 (XSS) stays accepted — the error text still renders as escaped text in `<pre>{output}</pre>` via React (no `dangerouslySetInnerHTML`); the added red branch introduces no new injection surface.

## Next Phase Readiness

- The frontend now consumes the `is_error` contract end-to-end. Plan 16-04 (failure smoke) can visually confirm the red `AlertTriangle` + red border on a live web-search error.
- No blockers.

## Self-Check: PASSED

---
*Phase: 16-web-search-restoration*
*Completed: 2026-07-12*
