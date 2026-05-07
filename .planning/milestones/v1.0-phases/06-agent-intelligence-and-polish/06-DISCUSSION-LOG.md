# Phase 6: Agent Intelligence and Polish - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-21
**Phase:** 06-agent-intelligence-and-polish
**Areas discussed:** Source routing, Token budget, Scope controls, Sub-agent consistency

---

## Source Routing

### How should the agent decide which sources to search?

| Option | Description | Selected |
|--------|-------------|----------|
| LLM-inferred | Agent analyzes query intent and picks sources automatically | ✓ |
| Always search both | Every query hits both default KB and private docs | |
| User toggle in UI | Explicit toggle/dropdown in chat UI to pick source scope | |

**User's choice:** LLM-inferred
**Notes:** No additional notes

### When source intent is ambiguous, what should the agent do?

| Option | Description | Selected |
|--------|-------------|----------|
| Default to both | Search both default KB and private docs when intent unclear | ✓ |
| Ask user to clarify | Agent asks before searching | |
| Default to KB only | Ambiguous queries default to default KB | |

**User's choice:** Default to both
**Notes:** No additional notes

### Should source routing be visible to the user?

| Option | Description | Selected |
|--------|-------------|----------|
| Show in tool card | Add scope indicator to existing tool card args_preview | ✓ |
| No indicator | Agent just searches, user infers from results | |
| Chat message prefix | Agent says "Searching the default KB..." as text | |

**User's choice:** Show in tool card
**Notes:** No additional notes

---

## Token Budget

### How should the agent manage token budget?

| Option | Description | Selected |
|--------|-------------|----------|
| Track and truncate | Count tokens, truncate oldest tool results first | ✓ |
| Summarize old context | Summarize older tool results when budget low | |
| Hard cap per tool result | Each tool result gets max char limit | |

**User's choice:** Track and truncate
**Notes:** No additional notes

### Where should token budget limits come from?

| Option | Description | Selected |
|--------|-------------|----------|
| Config settings | Add settings to config.py, tunable via env vars | |
| Model-aware auto-detect | Detect model context window, compute budget dynamically | ✓ |
| Hardcoded defaults | Hardcode reasonable defaults | |

**User's choice:** Model-aware auto-detect
**Notes:** User chose dynamic detection over static config — supports varying OpenRouter models

### When budget is tight, what gets truncated first?

| Option | Description | Selected |
|--------|-------------|----------|
| Oldest tool results first | Keep recent, truncate oldest | ✓ |
| Largest tool results first | Truncate biggest regardless of age | |
| All tool results equally | Proportional truncation | |

**User's choice:** Oldest tool results first
**Notes:** No additional notes

---

## Scope Controls

### How should users narrow search scope?

| Option | Description | Selected |
|--------|-------------|----------|
| Natural language | User says "only search Catan" in message, agent parses | ✓ |
| Slash command | /scope Board Games/Catan syntax | |
| Chat prefix syntax | @Catan prefix like Slack/Discord | |

**User's choice:** Natural language
**Notes:** No additional notes

### Should scope persist across messages?

| Option | Description | Selected |
|--------|-------------|----------|
| Per-message only | Each message independent, no state tracking | |
| Sticky until changed | Persists until user broadens | |
| You decide | Claude picks during implementation | ✓ |

**User's choice:** You decide
**Notes:** Claude's discretion on persistence approach

---

## Sub-Agent Consistency

### How should analyze_document be updated?

| Option | Description | Selected |
|--------|-------------|----------|
| Align patterns | Keep both, align SSE events, budget tracking, error handling | ✓ |
| Merge into explorer | Remove analyze_document, explorer handles all | |
| Keep as-is | Don't change, just avoid conflicts | |

**User's choice:** Align patterns
**Notes:** No additional notes

### Should analyze_document gain KB tool access?

| Option | Description | Selected |
|--------|-------------|----------|
| No, keep single-doc | Stay focused on one document, explorer handles cross-ref | ✓ |
| Yes, add KB tools | Can reference other docs during analysis | |
| You decide | Claude picks during implementation | |

**User's choice:** No, keep single-doc
**Notes:** Clear separation — analyze_document for single-doc, explorer for cross-referencing

---

## Claude's Discretion

- Token counting method (tiktoken vs character estimation vs API-reported)
- Model context window detection strategy
- Source routing hint mechanism (system prompt vs tool parameter)
- Scope persistence approach (per-message vs sticky)
- Budget allocation ratios
- analyze_document SSE alignment approach

## Deferred Ideas

None — discussion stayed within phase scope
