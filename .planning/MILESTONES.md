# Milestones

## v1.0 KB Navigation & Agentic RAG (Shipped: 2026-04-23)

**Phases completed:** 7 phases, 21 plans, 40 tasks

**Key accomplishments:**

- ltree-based folders table with system user ownership, mixed-visibility RLS, and Board Games root seed
- Visibility columns, mixed-visibility RLS policies, and visibility-aware search RPCs for shared default KB + private user docs
- Rerunnable seed script that ingests 10 board game markdown files into Supabase as public documents under per-game subfolders, with content-hash idempotency
- 5 KB navigation tools (ls, tree, read, grep, glob) with Supabase RPCs for regex search and glob matching against hierarchical folder structure
- Collapsible tool call cards replacing pill badges, with tool_start/tool_result SSE protocol and call_id correlation
- 9-tool chat loop with tool_start/tool_result SSE, persistent tool cards in DB, and tool selection guide in system prompt
- LLM timeout protection, incremental tool persistence, and AbortController cleanup to prevent stalls and lost tool cards
- Fixed root-level My Documents file resolution using is_("folder_id", "null") and wrapped all 5 KB tool calls with try/except error handling
- Retroactive 03-VERIFICATION.md (status=passed) citing file:line evidence for TOOL-01..08, REQUIREMENTS.md traceability flipped to Complete for TOOL-06/07/08, and audit cross-check confirming v1.0 milestone gaps closed.
- 1. [Rule 1 — Bug] `renderIcon` helper instead of dynamic component tag
- 1. [Rule 1 - Bug] setState-in-effect lint error in ContextMenu positioning
- 1. [Rule 1 - Bug] Root-level folder creation silently cancelled
- Signature:
- Explorer sub-agent generator (run_exploration) wired to the Phase 3 KB tools, enforcing 3-axis budget caps and producing Pydantic-validated ExplorerResult via 3-tier structured-output fallback. 17 unit tests green.
- EXPLORE_KB_TOOL wired into parent chat loop with async-bridged streaming dispatcher emitting nested SSE sub_event rows; find_similar and recommendation_seed modes verified by unit tests; 4 integration tests proving end-to-end SSE flow.
- SubEvent SSE parsing and nested ToolCallCard rendering with real-time X/10 progress indicator for explore_kb sub-agent calls
- tiktoken-backed TokenBudget class plus source routing and scope parsing heuristics -- standalone, fully tested, ready to wire into the chat loop in Plan 02.
- Wired TokenBudget, source routing, scope parsing, and sub-agent SSE alignment into the live chat event_generator; analyze_document now emits explore_kb-style sub_events and tool cards surface a colored scope badge.

---
