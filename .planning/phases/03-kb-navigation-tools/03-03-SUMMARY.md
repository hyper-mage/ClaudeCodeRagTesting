---
phase: 03-kb-navigation-tools
plan: 03
subsystem: api, ui
tags: [fastapi, sse, openai-function-calling, supabase, react]

requires:
  - phase: 03-kb-navigation-tools
    provides: KB tool functions (Plan 01), ToolCallCard UI (Plan 02)
provides:
  - Full chat loop integration for all 9 tools with tool_start/tool_result SSE protocol
  - Tool selection guide in system prompt
  - Persistent tool call cards saved to messages table
  - Hide/show toggle for tool cards
affects: [chat-ui, chat-loop]

tech-stack:
  added: []
  patterns: [tool_start/tool_result SSE protocol, call_id correlation, JSONB tool persistence]

key-files:
  created:
    - supabase/migrations/024_add_tools_used_to_messages.sql
  modified:
    - backend/routers/chat.py
    - backend/services/llm_service.py
    - backend/models/schemas.py
    - frontend/src/hooks/useChat.ts
    - frontend/src/components/MessageBubble.tsx

key-decisions:
  - "KB tools always available (not gated by doc_check) since default KB always exists"
  - "All 9 tools use unified tool_start/tool_result SSE protocol with call_id"
  - "Tool events persisted as JSONB in messages table for cross-session card display"
  - "Pass native Python list to Supabase JSONB column (no json.dumps)"

patterns-established:
  - "Unified SSE tool protocol: tool_start before execution, tool_result after, correlated by call_id"
  - "Tool persistence: accumulate tool events during chat loop, save with assistant message"
  - "Tool selection guide appended to system prompt when tools available"

requirements-completed: [TOOL-01, TOOL-02, TOOL-03, TOOL-04, TOOL-05, TOOL-06, TOOL-07, TOOL-08]

duration: 10min
completed: 2026-04-09
---

# Plan 03-03: Chat Loop Integration Summary

**9-tool chat loop with tool_start/tool_result SSE, persistent tool cards in DB, and tool selection guide in system prompt**

## Performance

- **Duration:** 10 min
- **Tasks:** 3 (2 auto + 1 human-verify)
- **Files created:** 1
- **Files modified:** 5

## Accomplishments
- 5 KB tool definitions wired into chat loop with execute_tool dispatch
- Unified tool_start/tool_result SSE protocol for all 9 tools (replacing old mixed approach)
- Tool selection guide categorized by purpose appended to system prompt
- Tool events persisted in messages.tools_used JSONB column
- Hide/show toggle on tool cards for user control
- Human-verified: KB tools render as emerald cards, persist across chat switches

## Task Commits

1. **Task 1: KB tools + SSE protocol in chat.py** - `de7a459` (feat)
2. **Task 2: Tool guide in llm_service.py** - `28525d6` (feat)
3. **Task 3: Persistent cards + hide/show toggle** - `c22fa19` (feat)
4. **Fix: JSONB double-encoding** - `cfac159` (fix)

## Files Created/Modified
- `supabase/migrations/024_add_tools_used_to_messages.sql` - tools_used JSONB column
- `backend/routers/chat.py` - KB tool definitions, dispatch, SSE protocol, persistence
- `backend/services/llm_service.py` - tool_guide parameter on stream_chat_completion
- `backend/models/schemas.py` - tools_used field on MessageResponse
- `frontend/src/hooks/useChat.ts` - Load persisted tools_used from API
- `frontend/src/components/MessageBubble.tsx` - Hide/show toggle for tool cards

## Decisions Made
- Added tool persistence (migration 024) during human verification — user requested cards survive page reload
- Native Python list passed to JSONB column (not json.dumps) to avoid double-encoding

## Deviations from Plan

### Auto-fixed Issues

**1. Tool card persistence (user feedback during checkpoint)**
- **Found during:** Task 3 (human verification)
- **Issue:** Tool cards only existed in React state, disappeared on page reload or chat switch
- **Fix:** Added tools_used JSONB column, backend persistence, frontend loading, hide/show toggle
- **Files modified:** 5 files + 1 new migration
- **Verification:** User confirmed cards persist across chat switches

**2. JSONB double-encoding**
- **Found during:** Testing persistence
- **Issue:** json.dumps() before Supabase insert caused string storage instead of array
- **Fix:** Pass native list to Supabase JSONB column directly
- **Verification:** User confirmed it works after fix

---
**Total deviations:** 2 (1 user-requested enhancement, 1 bug fix)
**Impact on plan:** Enhancement improves UX. No scope creep — persistence is natural extension of the card feature.

## Issues Encountered
None beyond the deviations above.

## User Setup Required
Apply migrations 022, 023, and 024 via Supabase SQL Editor.

## Next Phase Readiness
- All 5 KB tools fully integrated end-to-end
- Tool cards persist and are toggleable
- Ready for Phase 4 (File Manager UI)

---
*Phase: 03-kb-navigation-tools*
*Completed: 2026-04-09*
