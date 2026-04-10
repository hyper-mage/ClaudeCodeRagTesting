---
phase: 03-kb-navigation-tools
plan: 02
subsystem: ui
tags: [react, tailwind, lucide-react, sse, typescript]

requires:
  - phase: 03-kb-navigation-tools
    provides: Tool definitions (Plan 01 provides tool names for TOOL_LABELS)
provides:
  - ToolCallCard component with collapsible output display
  - Updated SSE parsing for tool_start/tool_result protocol
  - call_id-based tool event correlation
affects: [03-03, chat-ui]

tech-stack:
  added: []
  patterns: [tool_start/tool_result SSE protocol, call_id correlation]

key-files:
  created:
    - frontend/src/components/ToolCallCard.tsx
  modified:
    - frontend/src/components/MessageBubble.tsx
    - frontend/src/hooks/useChat.ts
    - frontend/src/components/ChatContainer.tsx

key-decisions:
  - "Correlate tool events by call_id, not tool name (same tool can be called multiple times)"
  - "Legacy backward compat for old tool_event format without type field"
  - "ChatContainer ToolEvent interface updated to match for type safety"

patterns-established:
  - "Tool card pattern: collapsible cards with icon, status indicator, expandable output"
  - "SSE tool protocol: tool_start (running state) + tool_result (complete with output)"

requirements-completed: [TOOL-07, TOOL-08]

duration: 5min
completed: 2026-04-09
---

# Plan 03-02: Tool Call Card UI Summary

**Collapsible tool call cards replacing pill badges, with tool_start/tool_result SSE protocol and call_id correlation**

## Performance

- **Duration:** 5 min
- **Tasks:** 2
- **Files created:** 1
- **Files modified:** 3

## Accomplishments
- ToolCallCard component with all 9 tool labels/icons, emerald/gray/indigo color scheme
- Pill badges fully replaced with vertical card stack in MessageBubble
- SSE parsing handles tool_start (running), tool_result (complete with output), and legacy format
- TypeScript compiles clean across all affected files

## Task Commits

1. **Task 1: ToolCallCard component** - `ff56bf2` (feat)
2. **Task 2: MessageBubble + useChat updates** - `0a662cd` (feat)

## Files Created/Modified
- `frontend/src/components/ToolCallCard.tsx` - Collapsible card with icons, status, output
- `frontend/src/components/MessageBubble.tsx` - Uses ToolCallCard instead of pill badges
- `frontend/src/hooks/useChat.ts` - tool_start/tool_result SSE parsing with call_id
- `frontend/src/components/ChatContainer.tsx` - Updated ToolEvent interface

## Decisions Made
- Added backward compat for legacy tool_event format (no type field) so frontend works before Plan 03 backend updates
- Updated ChatContainer's ToolEvent interface to match new shape for type safety

## Deviations from Plan

### Auto-fixed Issues

**1. ChatContainer ToolEvent interface sync**
- **Found during:** Task 2 (TypeScript check)
- **Issue:** ChatContainer had its own ToolEvent interface missing new fields
- **Fix:** Updated to include output, call_id, subagent, status fields
- **Verification:** `npx tsc --noEmit` passes

---
**Total deviations:** 1 auto-fixed
**Impact on plan:** Necessary for TypeScript type safety. No scope creep.

## Issues Encountered
None.

## User Setup Required
None.

## Next Phase Readiness
- Frontend ready to display tool calls from any of the 9 tools
- Needs Plan 03-03 backend to emit tool_start/tool_result SSE events

---
*Phase: 03-kb-navigation-tools*
*Completed: 2026-04-09*
