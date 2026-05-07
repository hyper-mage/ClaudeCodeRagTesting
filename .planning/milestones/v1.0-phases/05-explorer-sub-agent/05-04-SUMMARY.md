---
phase: 05-explorer-sub-agent
plan: 04
subsystem: ui
tags: [react, sse, streaming, sub-agent, toolcall, lucide]

# Dependency graph
requires:
  - phase: 05-03
    provides: SSE sub_event row format from explore_kb dispatcher
provides:
  - SubEvent type and sub_event SSE parsing branch in useChat.ts
  - Nested sub-event rendering with collapse/expand in ToolCallCard
  - Progress indicator (X/10) for explore_kb tool calls
  - explore_kb entry in TOOL_LABELS and TOOL_ICONS (Compass icon)
affects: [06-agent-intelligence]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Immutable subEvents array appended via setMessages map pattern"
    - "Sub-tool pairing by call_id for start/result grouping"
    - "Hardcoded EXPLORER_MAX_TOOL_CALLS constant synced manually with backend config"

key-files:
  created: []
  modified:
    - frontend/src/hooks/useChat.ts
    - frontend/src/components/ToolCallCard.tsx
    - frontend/src/components/MessageBubble.tsx

key-decisions:
  - "Hardcoded EXPLORER_MAX_TOOL_CALLS=10 in ToolCallCard rather than fetching from /api/config endpoint; manual sync with backend"
  - "subEvents NOT persisted to DB; on page reload parent card shows only final synthesis"
  - "Nested sub-step list collapsed by default (Pitfall 8 UX guideline)"

patterns-established:
  - "SubEvent interface exported from useChat.ts as the canonical type for nested tool progress"
  - "sub_event SSE branch routes by parent_call_id to attach nested events to parent ToolEvent"
  - "ToolCallCard dual expand state: main card expand + separate sub-steps expand"

requirements-completed: [EXPL-04, EXPL-06]

# Metrics
duration: ~15min
completed: 2026-04-21
---

# Phase 5 Plan 4: Frontend Streaming UI Summary

**SubEvent SSE parsing and nested ToolCallCard rendering with real-time X/10 progress indicator for explore_kb sub-agent calls**

## Performance

- **Duration:** ~15 min (Tasks 1-2 automated, Task 3 manual UAT)
- **Started:** 2026-04-21T15:00:00Z
- **Completed:** 2026-04-21T15:38:00Z
- **Tasks:** 3 (2 auto + 1 human-verify)
- **Files modified:** 3

## Accomplishments
- SubEvent type exported from useChat.ts; ToolEvent extended with optional subEvents array
- SSE parsing branch handles type=sub_event rows, attaching them to parent ToolEvent by parent_call_id
- ToolCallCard renders nested sub-step list for explore_kb with collapse/expand toggle
- Progress indicator shows "Exploring... (X/10)" using tool-call-count axis on both numerator and denominator
- explore_kb added to TOOL_LABELS ("Explore KB") and TOOL_ICONS (Compass from lucide-react)
- MessageBubble imports ToolEvent from useChat.ts (removed duplicate local interface) and passes subEvents prop through
- All 5 golden UAT scenarios passed: folder summary, find similar, multi-step search, recommendation, budget cap

## Task Commits

Each task was committed atomically:

1. **Task 1: Extend useChat.ts -- SubEvent type + sub_event SSE parsing branch** - `36b6d5a` (feat)
2. **Task 2: Extend ToolCallCard.tsx -- nested sub_event rendering + progress indicator** - `9cbcf89` (feat)
3. **Task 3: Human verification -- explorer UI flow end-to-end** - no commit (human-verify checkpoint, approved)

## Files Created/Modified
- `frontend/src/hooks/useChat.ts` - Added SubEvent interface, subEvents field on ToolEvent, sub_event SSE parsing branch
- `frontend/src/components/ToolCallCard.tsx` - Nested sub-event rendering, progress indicator, explore_kb in TOOL_LABELS/TOOL_ICONS, EXPLORER_MAX_TOOL_CALLS constant
- `frontend/src/components/MessageBubble.tsx` - Imports ToolEvent from useChat (removed duplicate), passes subEvents prop to ToolCallCard

## Decisions Made
- Hardcoded `EXPLORER_MAX_TOOL_CALLS = 10` in ToolCallCard.tsx rather than fetching from a /api/config endpoint. Must be kept in sync with `backend/config.py -> Settings.explorer_max_tool_calls`. A Phase 6 enhancement could expose this via API.
- subEvents are NOT persisted to the tools_used DB column. On page reload, the parent card shows only the final ExplorerResult synthesis. Sub-step replay is a potential Phase 6 enhancement.
- Nested sub-step list collapsed by default per Pitfall 8 UX guideline to avoid overwhelming the chat view.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## Known Stubs

None - all data flows are wired end-to-end. The non-persistence of subEvents is documented as a known limitation, not a stub.

## Known Limitations
- **subEvents not persisted:** On page reload, sub-step cards do not replay. The parent card still shows the final synthesis via its output field.
- **EXPLORER_MAX_TOOL_CALLS hardcoded:** Frontend constant (10) must be manually synced with backend config default. No runtime config endpoint yet.
- **Markdown tables in chat:** Pre-existing issue where markdown tables render as raw text. Not in Phase 5 scope.

## UAT Results

| Scenario | Query | Result |
|----------|-------|--------|
| 1. Folder summary (EXPL-02) | "Summarize the Catan folder" | Indigo Explore KB card, progress indicator, sub-steps visible, coherent synthesis |
| 2. Find similar (EXPL-03) | "What games are like Azul?" | find_similar mode, multiple candidates with reasoning |
| 3. Multi-step search (EXPL-01) | "Find all games with tile placement mechanics" | deep_search/find_similar, multiple games with justification |
| 4. Recommendation (EXPL-04) | "Tell me about Catan" then "What else might I like?" | explore_kb triggered with Catan context, recommendations returned |
| 5. Budget cap (EXPL-05) | Repeat query 1 with EXPLORER_MAX_ITERATIONS=2 | Completed gracefully, partial summary, no crash or hung spinner |

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Phase 5 is now complete (all 4 plans done)
- All 6 EXPL requirements proved end-to-end
- Ready for Phase 6: Agent Intelligence and Polish (token budget, source routing, scope controls)

---
*Phase: 05-explorer-sub-agent*
*Completed: 2026-04-21*
