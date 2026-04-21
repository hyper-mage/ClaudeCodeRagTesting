# Phase 6: Agent Intelligence and Polish - Research

**Researched:** 2026-04-21
**Domain:** LLM context management, query routing, token budgeting
**Confidence:** HIGH

## Summary

This phase adds four capabilities to the existing agentic chat loop: (1) LLM-inferred source routing that automatically picks default KB vs private docs vs both, (2) token budget management preventing context window exhaustion, (3) natural language scope controls, and (4) sub-agent SSE event alignment between analyze_document and explore_kb.

The existing codebase already has strong patterns to build on -- the explorer sub-agent has budget enforcement (max_iterations, max_tool_calls, clip chars), tool result clipping, and structured SSE events. The parent chat loop in `chat.py` has no token management at all -- it sends the full system prompt + entire chat history + all accumulated tool results with no limit. This is the primary risk this phase addresses.

**Primary recommendation:** Use tiktoken 0.12.0 for token counting (cl100k_base encoding as reasonable cross-model approximation), query OpenRouter `/api/v1/models` endpoint at startup to get model-specific context_length, and implement budget tracking as a new `budget_service.py` that wraps around the existing `stream_chat_completion` call path.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Agent uses LLM-inferred source routing -- analyzes query intent to pick sources automatically. No user action needed.
- **D-02:** When source intent is ambiguous, agent defaults to searching both default KB and private docs. No clarification questions.
- **D-03:** Source scope visible in tool cards via args_preview pattern -- no new UI component.
- **D-04:** Track token usage across system prompt, chat history, tool results, and reserve space for response. Truncate oldest tool results first.
- **D-05:** Budget limits derived via model-aware auto-detection from OpenRouter API or config. Dynamic computation.
- **D-06:** Truncation strategy: oldest tool results removed first. Recent tool results and chat history preserved.
- **D-07:** Token counting via lightweight method (character-based estimation or tiktoken).
- **D-08:** Users narrow search scope via natural language in their message -- agent parses intent. No special syntax.
- **D-09:** Scope persistence is Claude's discretion.
- **D-10:** Align analyze_document and explore_kb: shared SSE event format, consistent budget tracking, similar error handling.
- **D-11:** analyze_document stays focused on single-document analysis. No KB tool access.
- **D-12:** Both sub-agents use consistent SSE sub_event format.

### Claude's Discretion
- Token counting method (tiktoken vs character estimation vs API-reported usage)
- Model context window detection strategy (OpenRouter API headers, model registry, or config fallback)
- How source routing hints are passed to tool calls (system prompt injection vs tool parameter)
- Scope persistence approach (per-message vs sticky)
- Exact budget allocation ratios (system prompt vs history vs tool results vs response reserve)
- How to align analyze_document SSE events with explorer pattern (refactor vs adapter)

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| AGNT-01 | Agent automatically selects appropriate sources based on query intent | Source routing via system prompt augmentation with intent classification; scope indicator in args_preview |
| AGNT-02 | Agent manages a token budget when assembling context, preventing context window exhaustion | tiktoken-based counting + OpenRouter model registry for context_length; truncation of oldest tool results |
| AGNT-03 | Token budget tracks usage across system prompt, chat history, tool results, and reserves space for response | Budget tracker class with per-category accounting; configurable allocation ratios |
| AGNT-04 | User can manually narrow search scope to specific folders or games via chat interface | Natural language scope parsing via system prompt guidance; scope passed as tool parameter hints |
| AGNT-05 | Agent uses existing sub-agent pattern consistently with new tool set | SSE event alignment for analyze_document to emit sub_event format; shared error handling patterns |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| tiktoken | 0.12.0 | Token counting for budget management | OpenAI's official tokenizer; fast BPE; cl100k_base covers GPT-4/Claude approximation |
| httpx | (already installed) | Query OpenRouter /api/v1/models endpoint | Already in project for embedding API calls |
| pydantic | 2.11.1 (already installed) | Budget config models | Already the project standard for structured data |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pydantic-settings | 2.9.1 (already installed) | New budget-related env vars | Add token_budget_*, model_context_length settings |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| tiktoken | Character-based estimation (chars/4) | Simpler, no new dep, but 10-20% inaccurate; tiktoken is ~200KB and fast |
| OpenRouter /models API | Hardcoded model registry | Less maintenance but stale; API is one HTTP call at startup |

**Installation:**
```bash
pip install tiktoken==0.12.0
```

**Version verification:** tiktoken 0.12.0 confirmed available on PyPI (checked 2026-04-21).

## Architecture Patterns

### Recommended Changes (no new project structure -- modifications to existing files)

```
backend/
  services/
    budget_service.py      # NEW: token counting, budget tracking, truncation
  config.py                # MODIFY: add budget-related settings
  services/
    llm_service.py         # MODIFY: integrate budget checks before API call
  routers/
    chat.py                # MODIFY: source routing, scope parsing, budget tracking in event_generator
  services/
    subagent_service.py    # MODIFY: align SSE events with explorer pattern
```

### Pattern 1: Token Budget Tracker

**What:** A class that tracks token usage across four categories (system prompt, chat history, tool results, response reserve) and provides truncation when budget is exceeded.

**When to use:** Called in the while loop of `event_generator()` before each `stream_chat_completion()` call.

**Example:**
```python
# Source: Project-specific pattern based on explorer_service.py budget enforcement
from services.budget_service import TokenBudget

budget = TokenBudget(
    model_context_length=settings.model_context_length,  # from OpenRouter or config
    response_reserve=settings.response_reserve_tokens,
)

# Before each LLM call, ensure we're within budget
budget.set_system(system_content)
budget.set_history(current_messages)  # chat history messages only
budget.set_tool_results(tool_result_messages)  # tool role messages

if budget.is_over():
    budget.truncate_oldest_tool_results()  # removes oldest tool results first
```

### Pattern 2: Source Routing via System Prompt Injection

**What:** Analyze the user's latest message to infer source intent (default KB, private docs, or both), then inject routing hints into the system prompt before the LLM call.

**When to use:** At the start of each chat turn in `event_generator()`, before building the tools list.

**Example:**
```python
# Source: Project-specific design
def infer_source_scope(user_message: str, has_private_docs: bool) -> str:
    """Return source scope hint based on query analysis.
    
    Returns: "default_kb", "private", or "both"
    """
    # Keyword-based heuristics (no LLM call needed):
    # - References to specific board game names -> "default_kb"
    # - "my documents", "my uploads", "uploaded" -> "private"
    # - Ambiguous -> "both"
    private_signals = ["my document", "my upload", "uploaded", "my file"]
    msg_lower = user_message.lower()
    
    if any(sig in msg_lower for sig in private_signals):
        return "private"
    
    if not has_private_docs:
        return "default_kb"
    
    return "both"  # D-02: default to both when ambiguous
```

### Pattern 3: Sub-Agent SSE Alignment

**What:** Wrap `run_document_analysis()` to emit SSE sub_events matching the explore_kb pattern (sub_iteration, sub_tool_start, sub_tool_result).

**When to use:** In `event_generator()` when dispatching analyze_document tool.

**Example:**
```python
# Before: analyze_document is a single synchronous call, no sub-events
# After: wrap it to emit progress events matching explorer pattern

# In chat.py event_generator(), for analyze_document:
yield {
    "event": "tool_event",
    "data": json.dumps({
        "tool_event": True,
        "type": "sub_event",
        "subagent": True,
        "parent_call_id": tc["id"],
        "sub_event": {"type": "sub_iteration", "iteration": 1},
    }),
}
# ... then execute and yield result
```

### Anti-Patterns to Avoid
- **Calling the LLM to classify source intent:** Adds latency and token cost for every message. Use keyword heuristics instead -- they cover the 90% case (D-01 says "invisible").
- **Exact token counting for every message:** Over-engineering. cl100k_base approximation is sufficient (D-07 says exact accuracy less important than preventing exhaustion).
- **Truncating chat history before tool results:** Violates D-06. Always truncate oldest tool results first, then oldest chat history only if still over budget.
- **Caching model context_length with lru_cache forever:** Model could change between restarts. Cache per settings instance (same lifecycle as existing get_settings).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Token counting | Character division approximation | tiktoken cl100k_base | Consistent, fast, handles edge cases (CJK, special tokens) |
| Model metadata lookup | Hardcoded context_length map | OpenRouter `/api/v1/models` API + config fallback | Stays current as models change; fallback ensures offline works |
| SSE event formatting | New event format per sub-agent | Existing sub_event pattern from explore_kb | Already works in frontend ToolCallCard; consistency is the goal |

**Key insight:** The explorer_service.py already solved most of the hard problems (budget enforcement, result clipping, SSE events). This phase generalizes those patterns to the parent agent level and aligns analyze_document to match.

## Common Pitfalls

### Pitfall 1: Context Window Math Off-by-Hundreds
**What goes wrong:** Token count estimate doesn't account for system message overhead, tool schema serialization, or message role tokens. Budget appears fine but API returns context_length_exceeded.
**Why it happens:** tiktoken counts content tokens but not the ~4 tokens per message for role/name/separator that OpenAI adds.
**How to avoid:** Add a per-message overhead of 4 tokens. Add a safety margin (e.g., 5% of total budget). The response_reserve should be generous (at least 4096 tokens).
**Warning signs:** Intermittent 400 errors from OpenRouter on long conversations.

### Pitfall 2: Tool Schema Tokens Not Counted
**What goes wrong:** The tools JSON schema is sent with every request but not counted in the budget, eating into available context.
**Why it happens:** Tool schemas are passed as a separate parameter to the API, but they consume context window tokens.
**How to avoid:** Estimate tool schema tokens once at startup (they're static) and subtract from available budget. With 10 tools, this is roughly 2000-3000 tokens.
**Warning signs:** Budget math says 80% used but API says context exceeded.

### Pitfall 3: Truncation Breaks Tool Call Continuity
**What goes wrong:** Removing an old tool result message orphans the corresponding assistant message with tool_calls, causing API validation errors.
**Why it happens:** OpenAI API requires tool messages to follow their corresponding assistant tool_call messages.
**How to avoid:** When truncating tool results, always remove the paired (assistant tool_call + tool result) messages together. Never remove a tool result without its parent assistant message.
**Warning signs:** API 400 errors about "tool_call_id not found" or "messages out of order".

### Pitfall 4: Source Routing Overrides User Intent
**What goes wrong:** Heuristic wrongly classifies a query as "private only" when user wants both, or vice versa.
**Why it happens:** Keyword matching is imperfect. "What games are similar to my favorite Catan?" has "my" but means default KB.
**How to avoid:** Make routing a hint in the system prompt, not a hard filter on tools. The LLM still has access to all tools -- the routing just provides guidance. D-02 says default to "both" when ambiguous.
**Warning signs:** Agent consistently misses relevant results from one source.

### Pitfall 5: Model Context Length Fetch Fails Silently
**What goes wrong:** OpenRouter API is down or model ID format changes, context_length defaults to 0 or very small value.
**Why it happens:** No fallback for the API call.
**How to avoid:** Config-based fallback (`model_context_length` setting with sensible default like 128000). Only use API result if > 0. Log warnings on fetch failure.
**Warning signs:** Budget immediately exhausted on first message.

### Pitfall 6: analyze_document SSE Alignment Breaks Frontend
**What goes wrong:** New sub_event format from analyze_document doesn't match what ToolCallCard expects.
**Why it happens:** ToolCallCard parses sub_event types (sub_iteration, sub_tool_start, sub_tool_result) specifically.
**How to avoid:** Use the EXACT same event types and field names as explore_kb. The frontend code (`useChat.ts` and `ToolCallCard.tsx`) already handles these types -- just emit matching shapes.
**Warning signs:** Tool card shows spinner forever or crashes on analyze_document calls.

## Code Examples

### Token Counting with tiktoken
```python
# Source: tiktoken docs + OpenAI cookbook
import tiktoken

# cl100k_base works for GPT-4, GPT-3.5, and is a reasonable approximation
# for Claude and other models on OpenRouter
_encoding = tiktoken.get_encoding("cl100k_base")

def count_tokens(text: str) -> int:
    """Count tokens in a text string."""
    return len(_encoding.encode(text))

def count_message_tokens(messages: list[dict]) -> int:
    """Count tokens for a list of chat messages.
    
    Each message has ~4 token overhead for role/separators.
    """
    total = 0
    for msg in messages:
        total += 4  # role + separators overhead
        content = msg.get("content", "")
        if content:
            total += count_tokens(content)
        # Tool calls in assistant messages
        if "tool_calls" in msg:
            total += count_tokens(json.dumps(msg["tool_calls"]))
    total += 2  # reply priming
    return total
```

### OpenRouter Model Context Length Lookup
```python
# Source: OpenRouter /api/v1/models endpoint (verified 2026-04-21)
import httpx

def fetch_model_context_length(model_id: str, api_key: str) -> int | None:
    """Query OpenRouter for a model's context_length.
    
    Returns None on failure (caller should use config fallback).
    Model entry structure confirmed: {"id": "...", "context_length": 1000000, ...}
    """
    try:
        resp = httpx.get(
            "https://openrouter.ai/api/v1/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10,
        )
        resp.raise_for_status()
        for model in resp.json().get("data", []):
            if model["id"] == model_id:
                return model.get("context_length")
    except Exception:
        return None
    return None
```

### Budget Allocation Pattern
```python
# Source: Project-specific design extending explorer_service.py patterns
class TokenBudget:
    """Track token usage across categories and truncate when over budget."""
    
    def __init__(self, context_length: int, response_reserve: int = 4096):
        self.context_length = context_length
        self.response_reserve = response_reserve
        self.tool_schema_tokens = 0  # set once at init
        self._system_tokens = 0
        self._history_tokens = 0
        self._tool_result_messages: list[tuple[int, int]] = []  # (index, tokens)
    
    @property
    def available(self) -> int:
        return self.context_length - self.response_reserve - self.tool_schema_tokens
    
    @property
    def used(self) -> int:
        tool_total = sum(t for _, t in self._tool_result_messages)
        return self._system_tokens + self._history_tokens + tool_total
    
    def is_over(self) -> bool:
        return self.used > self.available
    
    def truncate_oldest_tool_results(self, messages: list[dict]) -> list[dict]:
        """Remove oldest tool result + its parent assistant message pair."""
        # Find oldest tool result message, remove it and its paired assistant msg
        # ... implementation details
        pass
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| No token management | Token budget tracking | This phase | Prevents context window crashes on long conversations |
| All tools always available | Source-routed tool guidance | This phase | Better result quality, less noise |
| analyze_document: single call, no SSE | Aligned sub_event SSE format | This phase | Consistent frontend display |

**Deprecated/outdated:**
- tiktoken versions < 0.8.0 lack cl100k_base support for newer models -- use 0.12.0

## Open Questions

1. **Exact budget allocation ratios**
   - What we know: Need system prompt, history, tool results, response reserve categories
   - What's unclear: Optimal percentages. System prompt + tool schemas are fixed cost (~3000-4000 tokens). Response reserve of 4096 is standard. Rest split between history and tool results.
   - Recommendation: Start with response_reserve=4096, tool_schema_budget estimated once at startup, remaining split dynamically (no fixed ratio -- just track and truncate when over)

2. **Scope persistence**
   - What we know: D-09 says per-message vs sticky is implementer's choice
   - What's unclear: User expectations
   - Recommendation: Per-message (stateless). Each message is analyzed independently. Simpler, no hidden state, matches the stateless completions model (CLAUDE.md: "store and send chat history yourself"). If user wants persistent scope, they include it in each message.

3. **tiktoken accuracy for non-OpenAI models**
   - What we know: cl100k_base is an approximation for Claude/Mistral/etc. on OpenRouter
   - What's unclear: How far off it can be (estimated 5-15% variance)
   - Recommendation: The 5% safety margin on total budget absorbs this. D-07 explicitly says "exact accuracy less important than preventing context window exhaustion."

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.2.2 |
| Config file | None (implicit, `backend/tests/` dir) |
| Quick run command | `cd backend && python -m pytest tests/ -x -q` |
| Full suite command | `cd backend && python -m pytest tests/ -v` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| AGNT-01 | Source routing infers correct scope from query | unit | `cd backend && python -m pytest tests/test_budget_service.py::test_source_routing -x` | Wave 0 |
| AGNT-02 | Budget prevents context window exhaustion | unit | `cd backend && python -m pytest tests/test_budget_service.py::test_budget_truncation -x` | Wave 0 |
| AGNT-03 | Budget tracks all four categories | unit | `cd backend && python -m pytest tests/test_budget_service.py::test_budget_categories -x` | Wave 0 |
| AGNT-04 | Scope narrowing from natural language | unit | `cd backend && python -m pytest tests/test_budget_service.py::test_scope_parsing -x` | Wave 0 |
| AGNT-05 | analyze_document SSE events match explorer format | unit | `cd backend && python -m pytest tests/test_subagent_alignment.py -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `cd backend && python -m pytest tests/ -x -q`
- **Per wave merge:** `cd backend && python -m pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_budget_service.py` -- covers AGNT-01, AGNT-02, AGNT-03, AGNT-04
- [ ] `tests/test_subagent_alignment.py` -- covers AGNT-05
- [ ] Install tiktoken: `pip install tiktoken==0.12.0`

## Project Constraints (from CLAUDE.md)

- **No LangChain, no LangGraph** -- raw SDK calls only. Token counting must use tiktoken directly, not LangChain's token counting utilities.
- **Use Pydantic for structured LLM outputs** -- budget config should use pydantic-settings pattern.
- **Stream chat responses via SSE** -- budget tracking must work within the existing SSE event_generator pattern.
- **Module 2+ uses stateless completions** -- store and send chat history yourself. Budget management must handle the full history re-send pattern.
- **All tables need RLS** -- any new database tables (unlikely for this phase) must have RLS.
- **Config via env vars** -- new budget settings go in Settings class via pydantic-settings.
- **Python backend must use venv** -- tiktoken must be installed in the backend venv.

## Sources

### Primary (HIGH confidence)
- OpenRouter `/api/v1/models` endpoint -- verified response structure includes `context_length` field (fetched 2026-04-21)
- tiktoken 0.12.0 on PyPI -- confirmed available, cl100k_base encoding for cross-model approximation
- Existing codebase: `backend/routers/chat.py`, `backend/services/explorer_service.py`, `backend/services/subagent_service.py`, `backend/config.py` -- direct code review

### Secondary (MEDIUM confidence)
- [OpenAI Cookbook - How to count tokens with tiktoken](https://cookbook.openai.com/examples/how_to_count_tokens_with_tiktoken) -- message overhead formula (4 tokens/message + 2 reply priming)
- [OpenRouter API Reference](https://openrouter.ai/docs/api/reference/overview) -- API structure and headers

### Tertiary (LOW confidence)
- tiktoken accuracy for non-OpenAI models (cl100k_base as approximation) -- estimated 5-15% variance, mitigated by safety margin

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- tiktoken is the only new dependency, well-understood
- Architecture: HIGH -- extends existing patterns (explorer budget, SSE events, pydantic settings)
- Pitfalls: HIGH -- derived from direct code review of current implementation gaps

**Research date:** 2026-04-21
**Valid until:** 2026-05-21 (stable domain, no fast-moving dependencies)
