# Phase 3: KB Navigation Tools - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md -- this log preserves the alternatives considered.

**Date:** 2026-04-08
**Phase:** 03-kb-navigation-tools
**Areas discussed:** Tool output transparency, Path conventions, Coexistence with existing tools, Read tool behavior, Grep behavior, Tree depth and output, System prompt guidance, SSE event format

---

## Tool Output Transparency

| Option | Description | Selected |
|--------|-------------|----------|
| Collapsible cards | Each tool call gets a card with tool name + icon, arguments shown, output in a collapsible section. Replaces current pill-only display for ALL tools. | ✓ |
| Inline badges + expandable | Keep current pill badges for tool name, add 'Show details' toggle below. | |
| Terminal-style output | Tool calls rendered like terminal commands with monospace output blocks. | |

**User's choice:** Collapsible cards
**Notes:** Applies to ALL tools (all 9), not just KB tools. Cards collapsed by default.

---

## Card Scope (follow-up)

| Option | Description | Selected |
|--------|-------------|----------|
| All tools | Upgrade all tool displays to collapsible cards. Consistent UI. | ✓ |
| KB tools only | Only 5 new KB tools get cards. Existing tools keep pill-badge display. | |

**User's choice:** All tools

---

## Path Conventions

| Option | Description | Selected |
|--------|-------------|----------|
| Human-readable paths | Agent uses paths like 'Board Games/Catan/rules.md'. Backend resolves to IDs internally. | ✓ |
| Path + ID hybrid | Display paths for humans, tool schemas accept both paths and IDs. | |
| ID-based with path display | Tools use internal IDs in arguments. Output shows human-readable paths. | |

**User's choice:** Human-readable paths
**Notes:** Backend handles all path-to-ID resolution.

---

## User Document Paths (follow-up)

| Option | Description | Selected |
|--------|-------------|----------|
| My Documents/ prefix | User uploads appear under 'My Documents/'. Two top-level roots. | ✓ |
| Flat (no prefix) | User docs appear at root level alongside Board Games. | |
| You decide | Claude picks based on Phase 1 folder structure. | |

**User's choice:** My Documents/ prefix

---

## Coexistence with Existing Tools

| Option | Description | Selected |
|--------|-------------|----------|
| Replace search_documents | Remove search_documents. KB tools are a superset. | |
| Keep both, agent decides | Keep search_documents alongside KB tools. 9 total tools. | ✓ |
| Replace + keep semantic search | Bake semantic search into kb_grep as a mode. | |

**User's choice:** Keep both, agent decides
**Notes:** 9 total tools. Agent uses tool selection guide to pick.

---

## Analyze Document (follow-up)

| Option | Description | Selected |
|--------|-------------|----------|
| Keep analyze_document | analyze_document does LLM-powered analysis. kb_read returns raw content. Different purposes. | ✓ |
| Remove, kb_read replaces it | Agent reads with kb_read and reasons inline. | |
| You decide | Claude determines based on implementation. | |

**User's choice:** Keep analyze_document

---

## Read Tool Behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Full reassembled content | Reassemble all chunks. Support optional line-range parameter. | ✓ |
| Chunked with metadata | Return individual chunks with chunk index and metadata. | |
| Smart truncation | Full content up to token limit, then truncate with indicator. | |

**User's choice:** Full reassembled content

---

## Read Safety Limits (follow-up)

| Option | Description | Selected |
|--------|-------------|----------|
| Auto-truncate with hint | If document exceeds ~200 lines, return first N lines + truncation hint. | ✓ |
| No limit, full content always | Always return everything. Context budget is Phase 6's job. | |
| You decide | Claude picks based on typical document sizes. | |

**User's choice:** Auto-truncate with hint

---

## Grep Behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Regex on chunk text | True regex matching using PostgreSQL regex (~* operator). | |
| Keyword full-text search | PostgreSQL ts_vector full-text search. | |
| Both modes via flag | Supports 'mode' parameter: 'regex' or 'keyword'. Agent picks. | ✓ |

**User's choice:** Both modes via flag

---

## Grep Output Format (follow-up)

| Option | Description | Selected |
|--------|-------------|----------|
| Matched lines + context | Show matching lines with 1-2 lines of surrounding context, file path and line number. Ripgrep-style. | ✓ |
| File matches with snippets | Show matched files with brief snippet around first match. | |
| You decide | Claude picks output format for collapsible card UI. | |

**User's choice:** Matched lines + context

---

## Tree Depth and Output

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, with default depth | depth parameter, defaults to 2. Agent can increase for deeper exploration. | ✓ |
| Always full tree | Show everything. KB is bounded, full tree should be manageable. | |
| You decide | Claude picks based on expected KB size. | |

**User's choice:** Yes, with default depth of 2

---

## System Prompt Guidance

| Option | Description | Selected |
|--------|-------------|----------|
| Tool selection guide in prompt | Concise decision guide categorized by purpose (orientation, find files, find content, read, external). | ✓ |
| Minimal guidance | Just list tools with descriptions. LLM picks from function descriptions. | |
| You decide | Claude designs system prompt guidance. | |

**User's choice:** Tool selection guide in prompt

---

## SSE Event Format

| Option | Description | Selected |
|--------|-------------|----------|
| Separate start/result events | Emit tool_start (name + args) then tool_result (output). Frontend shows loading state. | ✓ |
| Single combined event | One event after tool completes with all data. No loading state. | |
| You decide | Claude picks based on existing SSE infrastructure. | |

**User's choice:** Separate start/result events

---

## Claude's Discretion

- Exact tool function names
- PostgreSQL implementation details for regex and glob matching
- Chunk reassembly strategy for kb_read
- Line number tracking across chunks
- SSE event field names and JSON structure
- Glob pattern matching implementation
- Context line count around grep matches
- Read truncation threshold

## Deferred Ideas

None -- discussion stayed within phase scope
