# Phase 16: Web Search Restoration - Context

**Gathered:** 2026-07-11
**Status:** Ready for planning

<domain>
## Phase Boundary

Restore the agent's `web_search` tool end-to-end and prod-verify it. The service, tool wiring, and config seam already exist — this is a fix + hardening + verification, not a greenfield build. Deliver: live web-grounded answers with cited sources (WSRCH-01, WSRCH-03), the tool surfaced only when a provider key is configured / fail-closed otherwise (WSRCH-02), and graceful, logged failure handling (WSRCH-04).

Provider is Tavily only, owner-configured server-side key. No per-user search keys, no multi-provider abstraction, no new search capabilities (all locked out of scope in REQUIREMENTS.md).

</domain>

<decisions>
## Implementation Decisions

### When to web-search (tool-selection guidance)
- **D-01:** Web search is a **fallback for external / current information not in the KB** — prefer the KB for game rules and mechanics; reach for `web_search` for things the KB can't answer: current prices, availability / where-to-buy, new or upcoming expansions, BGG rankings and community opinions, designer/publisher news. Encode this steer in the tool-selection guidance / system prompt so the agent doesn't web-search rules that already live in the KB. (Not "only after a KB miss" — the agent may judge a query as inherently external and go straight to web.)

### Citation format (WSRCH-03)
- **D-02:** Cite web sources as **inline markdown links where a fact is used, PLUS a short "Sources:" list at the end** of the answer. Update the citation guidance in the system prompt (currently only says "always cite your sources with URLs") to specify this format.

### Failure UX (WSRCH-04)
- **D-03:** On a web-search failure (invalid key, timeout, non-200): the **tool card shows a failed state**, the agent **briefly notes it couldn't reach the web**, then answers best-effort from the KB / its own knowledge. Not silent, not a hard refuse. The existing service already returns a graceful `{"error": ...}` dict and logs with `exc_info=True` — preserve that; ensure the error surfaces to the frontend tool card as a failed state and the agent is prompted to acknowledge it.

### Search tuning
- **D-04:** Keep `include_answer=true` and `max_results=5` (already a setting). **Make `search_depth` env-configurable** — add a `web_search_depth` setting (default `"basic"`) rather than hardcoding, so the owner can raise it to `advanced` without a code change. Mirror the existing `web_search_max_results` settings pattern in `config.py`.

### Claude's Discretion
- Exact wording of the system-prompt / tool-guide edits (as long as it encodes D-01 and D-02).
- Whether the "couldn't reach the web" acknowledgement is injected via the tool-result payload the agent sees, or via prompt guidance — planner/researcher decides the cleanest seam.
- Prod key rollout mechanics (Fly secret name/value) — ops detail for the executor.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & roadmap
- `.planning/REQUIREMENTS.md` — WSRCH-01..04 (in scope) + Out of Scope table (Tavily-only, owner-configured key, no multi-provider)
- `.planning/ROADMAP.md` §"Phase 16: Web Search Restoration" — goal, depends-on, 4 success criteria

### Code seams (the fix surface)
- `backend/services/web_search_service.py` — `search_web()` + `_search_tavily()`. **Root cause lives here:** posts `api_key` in the JSON body; Tavily's current API expects an `Authorization: Bearer tvly-...` header. Also holds the graceful-error + `exc_info=True` log path (WSRCH-04 base).
- `backend/routers/chat.py` — `WEB_SEARCH_TOOL` def (~line 397); gating `if settings.web_search_enabled: tools.append(WEB_SEARCH_TOOL)` (~line 949); execution branch `elif fn_name == "web_search"` (~line 714); `TOOL_SELECTION_GUIDE` (~line 612, `web_search` entry ~line 631 — edit target for D-01).
- `backend/config.py` — `web_search_provider` / `web_search_api_key` / `web_search_max_results` (~line 129); `web_search_enabled` property (~line 191, gates WSRCH-02); `system_prompt` (~line 95 — citation guidance edit target for D-02). Add `web_search_depth` here (D-04).
- `backend/services/llm_service.py` — `stream_chat_completion` builds `system_content` (~line 90) and injects `tool_guide` (~line 92); per-request seam.

### Verification reference (mirror the pattern)
- `.planning/codebase/INTEGRATIONS.md` — external API integration map
- Prior prod-verify pattern: v1.1/v1.2 live gates (Fly prod deploy) — this phase's SC-5 needs a live prod check with the real Tavily key.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `_search_tavily()` in `web_search_service.py`: keep the shape (returns `{answer, results:[{title,url,snippet}]}`); only change the auth transport (Bearer header) and read `search_depth` from settings.
- `web_search_enabled` property + conditional `tools.append`: WSRCH-02 (fail-closed when unconfigured) is already implemented — verify, don't rebuild.
- Frontend `ToolCallCard`: already renders tool_start/tool_result; failed-state surface for D-03 should reuse its existing error rendering.

### Established Patterns
- Optional-tool gating: tool is added to the loop only when its enabling setting is truthy (mirrors rerank/web-search existing pattern).
- Settings pattern: `web_search_*` fields in `Settings` (pydantic-settings) + a derived `_enabled` property — add `web_search_depth` the same way.
- Graceful tool failure: `execute_tool` catches per-tool and returns JSON `{"error": ...}` to the LLM (project-wide convention) — D-03 builds on this.

### Integration Points
- Tavily HTTP call (`httpx.post`) — the only external dependency; auth change is the core fix.
- System prompt / tool guide — behavioral edits for D-01 (when to search) and D-02 (citation format).
- Prod env (Fly secrets) — `web_search_api_key` must be set in prod for SC-5.

</code_context>

<specifics>
## Specific Ideas

- Board-game-domain web use cases to bias the guidance toward: current prices / where-to-buy, availability, new & upcoming expansions, BGG rankings + community sentiment, designer/publisher news. These are the "external, not in KB" cases D-01 targets.
- Confirm Tavily's current auth contract during research/planning (Bearer header vs legacy body `api_key`) before writing the fix — this is the one external unknown.

</specifics>

<deferred>
## Deferred Ideas

- Multiple / switchable web search providers (Brave, SearXNG) — WSRCH-F1, future milestone.
- User-facing per-thread web-search on/off toggle — WSRCH-F2, future milestone.
- Per-user BYOK web-search keys — explicitly out of scope (web search stays an owner-configured server tool).

None of these are in Phase 16 scope. Discussion stayed within the fix boundary.

</deferred>

---

*Phase: 16-web-search-restoration*
*Context gathered: 2026-07-11*
