# Phase 16: Web Search Restoration - Research

**Researched:** 2026-07-11
**Domain:** External web-search tool integration (Tavily Search API) inside an existing agentic tool-loop
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01 (when to web-search):** Web search is a **fallback for external / current information not in the KB** — prefer the KB for game rules and mechanics; reach for `web_search` for things the KB can't answer: current prices, availability / where-to-buy, new or upcoming expansions, BGG rankings and community opinions, designer/publisher news. Encode this steer in the tool-selection guidance / system prompt so the agent doesn't web-search rules that already live in the KB. (Not "only after a KB miss" — the agent may judge a query as inherently external and go straight to web.)
- **D-02 (citation format, WSRCH-03):** Cite web sources as **inline markdown links where a fact is used, PLUS a short "Sources:" list at the end** of the answer. Update the citation guidance in the system prompt (currently only says "always cite your sources with URLs") to specify this format.
- **D-03 (failure UX, WSRCH-04):** On a web-search failure (invalid key, timeout, non-200): the **tool card shows a failed state**, the agent **briefly notes it couldn't reach the web**, then answers best-effort from the KB / its own knowledge. Not silent, not a hard refuse. Preserve the existing graceful `{"error": ...}` dict + `exc_info=True` log; ensure the error surfaces to the frontend tool card as a failed state and the agent is prompted to acknowledge it.
- **D-04 (search tuning):** Keep `include_answer=true` and `max_results=5` (already a setting). **Make `search_depth` env-configurable** — add a `web_search_depth` setting (default `"basic"`) rather than hardcoding, so the owner can raise it to `advanced` without a code change. Mirror the existing `web_search_max_results` settings pattern in `config.py`.

### Claude's Discretion
- Exact wording of the system-prompt / tool-guide edits (as long as it encodes D-01 and D-02).
- Whether the "couldn't reach the web" acknowledgement is injected via the tool-result payload the agent sees, or via prompt guidance — planner/researcher decides the cleanest seam.
- Prod key rollout mechanics (Fly secret name/value) — ops detail for the executor.

### Deferred Ideas (OUT OF SCOPE)
- Multiple / switchable web search providers (Brave, SearXNG) — WSRCH-F1, future milestone.
- User-facing per-thread web-search on/off toggle — WSRCH-F2, future milestone.
- Per-user BYOK web-search keys — explicitly out of scope (web search stays an owner-configured server tool).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| WSRCH-01 | User gets answers grounded in current web info via the restored `web_search` tool | Root cause found + verified: `_search_tavily` posts `api_key` in the JSON body; Tavily now requires header-only `Authorization: Bearer tvly-...`. Fix = switch auth transport. See Standard Stack + Code Examples. `[VERIFIED: docs.tavily.com]` |
| WSRCH-02 | Tool exposed only when a provider is configured; fail-closed otherwise | Already implemented — `settings.web_search_enabled` gates `tools.append(WEB_SEARCH_TOOL)` (chat.py:949) AND `search_web()` re-guards (web_search_service.py:12). Verify, don't rebuild. See Architecture Patterns. |
| WSRCH-03 | Agent cites source URLs from web search | Citation guidance lives in `settings.system_prompt` (config.py:95) injected via `stream_chat_completion` (llm_service.py:90). Edit the string per D-02. Tavily returns `results[].url` for the LLM to cite. |
| WSRCH-04 | Web search failures return a graceful error (no turn crash) and are logged | Service already returns `{"error": ...}` + logs `exc_info=True`. Gap: the frontend tool card has NO error state today (only `running`/`complete`) — a real code change on both ends is required. See Pitfall 1 + Failed-State Surface. |
</phase_requirements>

## Summary

This phase is a **surgical fix + config + verification**, not a build. The web-search feature is fully wired: a `WEB_SEARCH_TOOL` schema, conditional gating, an `execute_tool` dispatch branch, a `search_web()` service with a graceful-error path, and a frontend `ToolCallCard`. **One external fact is the whole ballgame:** the current `_search_tavily` posts the API key as `api_key` inside the JSON body, and Tavily's current API rejects that — it requires the key in an `Authorization: Bearer tvly-...` header. This is verified against Tavily's official API reference (2026-07-11): the request-body `api_key` form is no longer documented and authentication is header-only. Fixing the transport is WSRCH-01.

The remaining work is small and well-scoped. WSRCH-02 (fail-closed gating) is already correct — it needs verification, not code. WSRCH-03 is a one-string edit to `settings.system_prompt` to specify the D-02 citation format, plus a tool-selection steer (D-01) in `TOOL_SELECTION_GUIDE` / the tool description. D-04 adds one setting (`web_search_depth`, default `"basic"`) mirroring `web_search_max_results`, read into the request body. WSRCH-04's service layer already fails gracefully — but a genuine gap exists in the UI: **the frontend `ToolEvent.status` union is only `'running' | 'complete'`; there is no error state today.** The CONTEXT.md note that the card can "reuse its existing error rendering" is inaccurate — that rendering does not exist. Surfacing a failed state is a real (small) change on both the SSE emitter and the React card.

**Primary recommendation:** Change `_search_tavily` to send `Authorization: Bearer {web_search_api_key}` (header-only, drop `api_key` from the body) and read `search_depth` from a new `web_search_depth` setting; edit `system_prompt` for D-02 and `TOOL_SELECTION_GUIDE`/tool description for D-01; add an error status to the `tool_result` SSE event + an `'error'` case to `ToolCallCard`/`useChat` for D-03; verify the already-correct fail-closed gating; then live-verify in prod by setting the `WEB_SEARCH_API_KEY` Fly secret and running a current-info board-game query. Keep raw `httpx` — do NOT add `tavily-python`.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Tavily auth/transport fix (WSRCH-01) | API/Backend — `services/web_search_service.py` | — | HTTP call to an external API lives server-side; the owner key must never reach the client |
| Tool gating / fail-closed (WSRCH-02) | API/Backend — `routers/chat.py` + `config.py` property | — | Tool availability is decided server-side from settings; the client never sees the tool schema |
| When-to-search steer (D-01) | API/Backend — `TOOL_SELECTION_GUIDE` + `WEB_SEARCH_TOOL.description` | — | Prompt/tool guidance is assembled server-side per request in `llm_service` |
| Citation format (D-02 / WSRCH-03) | API/Backend — `settings.system_prompt` | Browser (renders markdown links) | System prompt owned by backend; the LLM emits citations into the streamed answer; `react-markdown` renders them |
| search_depth config (D-04) | API/Backend — `config.py Settings` | Ops (env / Fly secret) | Env-driven setting resolved server-side; `advanced` togglable without a code change |
| Failed-state tool card (D-03 / WSRCH-04) | API/Backend — `tool_result` SSE event classification | Browser — `ToolCallCard` + `useChat` render the error | Backend classifies the error and emits a status; frontend renders the red failed state |
| Prod key rollout (SC-5) | Ops — Fly secret `WEB_SEARCH_API_KEY` | API/Backend (`@lru_cache` settings re-read on restart) | Secret set + process restart flips `web_search_enabled` true in prod |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `httpx` | already installed (transitive, used directly) | Sync `POST` to `https://api.tavily.com/search` | Already the project's HTTP client for the embedding + rerank calls; project rule forbids new heavy deps `[VERIFIED: backend/requirements.txt + INTEGRATIONS.md]` |
| Tavily Search API | v1 endpoint `POST https://api.tavily.com/search` | RAG-oriented web search returning `answer` + ranked `results[]` | Owner-configured provider already chosen and wired; the only supported provider this milestone `[VERIFIED: docs.tavily.com]` |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `pydantic-settings` (`BaseSettings`) | 2.9.1 | Add `web_search_depth: str = "basic"` field | D-04 — mirror the `web_search_max_results` pattern in `config.py` `[VERIFIED: backend/config.py:128-131]` |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Raw `httpx` | `tavily-python` official SDK | The SDK exists and handles the Bearer header for you, but it adds a dependency and violates the project's "raw SDK/httpx only, no new heavy deps" rule. **Do NOT add it.** The fix is a two-line transport change — an SDK is overkill. `[VERIFIED: CLAUDE.md rule + docs.tavily.com]` |
| Header-only Bearer | Keep `api_key` in body too (belt-and-suspenders) | The body form is no longer documented and may be ignored or rejected. Cleaner and correct: header-only. `[CITED: docs.tavily.com/documentation/api-reference/endpoint/search]` |

**Installation:** No new packages. `httpx` and `pydantic-settings` are already present.

**Version verification:** No new package versions to verify — this phase adds no dependencies. `httpx` is already used directly by `web_search_service.py`, `embedding_service.py`, and `rerank_service.py`. `[VERIFIED: backend/requirements.txt — pytest==8.4.2, pytest-asyncio==0.23.8 present; no respx/pytest-httpx]`

### Tavily API contract (VERIFIED 2026-07-11)

`[VERIFIED: docs.tavily.com/documentation/api-reference/endpoint/search]`

**Endpoint:** `POST https://api.tavily.com/search` — Content-Type `application/json`. **(URL unchanged — the current code's endpoint is correct.)**

**Auth:** `Authorization: Bearer tvly-YOUR_API_KEY` header. **Header-only.** The request-body `api_key` field is no longer documented. This is the root-cause fix.

**Request body params relevant to this phase:**

| Param | Type | Default | Allowed / Range | This phase |
|-------|------|---------|-----------------|-----------|
| `query` | string | required | any string | pass `fn_args["query"]` |
| `search_depth` | string | `basic` | `basic`, `advanced`, `fast`, `ultra-fast` | read from new `web_search_depth` setting (D-04, default `basic`) |
| `max_results` | integer | 5 | 0–20 | keep `settings.web_search_max_results` (5) |
| `include_answer` | boolean/string | false | `true`/`false`/`basic`/`advanced` | keep `True` (D-04) |

**Response (200) shape used by the mapper:**
- Top-level: `query`, `answer` (present when `include_answer`), `results[]`, `response_time`, `request_id`, `usage`.
- Per result (`results[]`): `title`, `url`, `content` (short snippet), `score`, `raw_content` (only if requested), `favicon`.
- The current mapper — `answer`, and `results[].{title, url, content→snippet}` — matches this exactly. **No response-parsing change needed.** `[VERIFIED: docs.tavily.com]`

**Error status codes:** `401` invalid/missing key · `429` rate limit · `432` plan usage-limit exceeded · `433` pay-as-you-go limit · `400` bad params · `500` server error. `response.raise_for_status()` turns all of these into an `httpx.HTTPStatusError` caught by the broad `except Exception` → graceful `{"error": ...}`. `[VERIFIED: docs.tavily.com]`

**Timeout:** No official guidance from Tavily. The existing `timeout=30` is reasonable; `advanced` depth is slower than `basic`, so keep ≥ the current 30s (do not drop it aggressively). `[ASSUMED]`

## Architecture Patterns

### System Architecture Diagram

```
User query (chat SSE)
      │
      ▼
routers/chat.py  event_generator → _traced_turn
      │  builds tools list:
      │    KB tools (always) + doc tools (if user has docs) + SQL
      │    + WEB_SEARCH_TOOL  ── ONLY IF settings.web_search_enabled  ◄── WSRCH-02 gate (line 949)
      ▼
stream_chat_completion (llm_service.py)
      │  system_content = settings.system_prompt (+ TOOL_SELECTION_GUIDE)   ◄── D-01/D-02 edit targets
      ▼
LLM decides → finish_reason "tool_calls" → {name: "web_search", args:{query}}
      │
      ▼  emit SSE tool_start ──────────────────────────────► ToolCallCard (status running)
      │
      ▼
execute_tool("web_search", …)  (chat.py:714)  ── synchronous ──►  search_web(query)   (web_search_service.py:8)
      │                                                                 │  guard: web_search_enabled? else {"error":…}  ◄── WSRCH-02 2nd gate
      │                                                                 ▼
      │                                                    _search_tavily(query, settings)
      │                                                       httpx.POST https://api.tavily.com/search
      │                                                       Authorization: Bearer tvly-…   ◄── WSRCH-01 FIX (was api_key in body)
      │                                                       body: query, search_depth(setting), max_results, include_answer
      │                                                       ▲ Tavily API
      │                                                       │ 200 → {answer, results[{title,url,snippet}]}
      │                                                       │ 401/429/… → raise_for_status → except → {"error":…}+log(exc_info)  ◄── WSRCH-04
      ▼
tool_result dict → JSON → appended as role:"tool" message → fed back to LLM loop
      │  emit SSE tool_result (+ NEW error status when result has "error")  ◄── D-03 surface
      │                                                       └───────────► ToolCallCard (status complete | error)
      ▼
LLM composes answer with inline [markdown](url) links + "Sources:" list (D-02) → content_delta SSE → chat bubble
```

### Recommended change map (files & seams)

```
backend/
├── config.py
│   ├── Settings.web_search_depth: str = "basic"   # NEW — after web_search_max_results (~line 131)   [D-04]
│   └── Settings.system_prompt                       # EDIT citation guidance (~line 95-102)            [D-02/WSRCH-03]
├── services/web_search_service.py
│   └── _search_tavily()                             # Bearer header, drop body api_key, read depth     [WSRCH-01/D-04]
├── routers/chat.py
│   ├── WEB_SEARCH_TOOL.description (~line 401)       # optional D-01 nudge
│   ├── TOOL_SELECTION_GUIDE web_search entry (~631)  # D-01 steer (external-not-in-KB)
│   ├── gating (~line 949)                            # WSRCH-02 — VERIFY only
│   └── tool_result SSE emit (~line 1281)             # NEW: set status "error" when result has "error" [D-03]
frontend/src/
├── hooks/useChat.ts
│   ├── ToolEvent.status union (line 21)             # add 'error'                                      [D-03]
│   └── tool_result handler (line 206)               # map error flag → status 'error'                  [D-03]
└── components/ToolCallCard.tsx
    └── status render (line 120)                      # add 'error' branch (red X / red border)         [D-03]
```

### Pattern 1: Optional-tool gating (fail-closed) — WSRCH-02, ALREADY IN PLACE
**What:** A tool schema is appended to the loop's `tools` list only when its enabling setting is truthy; the service re-guards internally.
**When to use:** Any provider-keyed optional tool (mirrors rerank).
**Example:**
```python
# Source: backend/routers/chat.py:948-950  [VERIFIED: read in-repo]
tools.append(SQL_TOOL)
if settings.web_search_enabled:            # bool(web_search_api_key)  — config.py:191
    tools.append(WEB_SEARCH_TOOL)
```
```python
# Source: backend/services/web_search_service.py:12-13  — second, defense-in-depth guard
if not settings.web_search_enabled:
    return {"error": "Web search not configured", "results": []}
```
**Verify (don't rebuild):** with no key set, `WEB_SEARCH_TOOL` is absent from the schema list AND `search_web` returns the config error. That is fully fail-closed. `@lru_cache` on `get_settings()` means a prod key change requires a **process restart** to take effect.

### Pattern 2: Settings field mirroring `web_search_max_results` — D-04
**What:** Add a typed `pydantic-settings` field with an env override + a default.
**Example:**
```python
# Source: backend/config.py:128-131 (existing) → add the depth field the same way
# Web Search (optional — tool only available when API key is set)
web_search_provider: str = "tavily"
web_search_api_key: str = ""
web_search_max_results: int = 5
web_search_depth: str = "basic"   # NEW (D-04): "basic" | "advanced" | "fast" | "ultra-fast"
```
Env override is automatic via pydantic-settings: `WEB_SEARCH_DEPTH=advanced`.

### Pattern 3: Graceful per-tool failure — WSRCH-04, service layer ALREADY IN PLACE
**What:** Catch broadly, log with `exc_info=True`, return a JSON-serializable `{"error": ...}` the LLM can read and narrate — never raise into the SSE loop.
**Example:**
```python
# Source: backend/services/web_search_service.py:48-50 (existing — preserve)
except Exception as e:
    logger.error(f"Tavily search failed: {e}", exc_info=True)
    return {"error": str(e), "results": []}
```
The LLM sees this `{"error": ...}` in the `role:"tool"` message and can acknowledge it — this is the cleanest seam for the "couldn't reach the web" note (D-03 discretion): **no separate prompt injection is required for the agent to know it failed**, because the error is already in the tool result it consumes. A brief system-prompt nudge ("if a tool returns an error, briefly tell the user and answer best-effort") makes the behavior reliable.

### Anti-Patterns to Avoid
- **Adding `tavily-python`:** violates the raw-SDK/no-new-deps rule; the fix is a header change.
- **Building a retry/backoff layer:** out of scope; graceful single-attempt failure is the locked behavior (D-03). Tavily's own limits (429/432/433) are the caller's signal to degrade, not to hammer.
- **Introducing a provider abstraction / second provider:** explicitly deferred (WSRCH-F1).
- **Assuming the tool card already renders errors:** it does not (see Pitfall 1). Do not skip the frontend change.
- **Scrubbing the Tavily key with the existing `sk-or-` regex:** `services/log_scrub.py` only redacts `sk-or-` OpenRouter keys, not `tvly-` keys — see Security Domain.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Web search + result ranking | A scraper / search-engine client | Tavily `/search` (already wired) | Tavily returns RAG-ready `answer` + scored `results[]`; scraping HTML is brittle and out of scope |
| Bearer-auth transport | A custom auth-signing helper | One `httpx` header: `{"Authorization": f"Bearer {key}"}` | It's a single header; an SDK/helper is overkill |
| Citation extraction | Backend post-processing of URLs into the answer | Let the LLM cite from `results[].url` per the D-02 system-prompt guidance | The model already receives the URLs in the tool result; prompt-driven citation is the established pattern |
| Config plumbing for depth | A custom env parser | `pydantic-settings` field (`web_search_depth`) | Mirrors every other setting; free env override + type coercion |

**Key insight:** Almost everything here already exists and works. The single genuine bug is an auth transport mismatch; the rest is prompt copy, one setting, one UI status, and a prod key. Resist the urge to refactor the surrounding tool loop.

## Common Pitfalls

### Pitfall 1: The tool card has no error state today (D-03 is a real change, not a reuse)
**What goes wrong:** CONTEXT.md's code-context note says the frontend should "reuse its existing error rendering." There is no error rendering. `ToolEvent.status` is typed `'running' | 'complete'` (useChat.ts:21), the `tool_result` handler hardcodes `status: 'complete'` (useChat.ts:215), and `ToolCallCard` renders only a spinner (running) or a gray check (complete) (ToolCallCard.tsx:120-124). A web-search failure currently shows a **green/gray "complete" check** with the error buried in the expandable output.
**Why it happens:** The backend always sets `tool_entry["status"] = "complete"` (chat.py:1273) and the `tool_result` SSE event carries no error flag.
**How to avoid:** Three coordinated edits — (1) backend: when the tool result JSON contains `"error"`, set the tool entry status and add a field to the `tool_result` SSE event (e.g. `"is_error": true` or `"status": "error"`); (2) `useChat.ts`: widen the `status` union to include `'error'` and map the flag; (3) `ToolCallCard.tsx`: add an `'error'` branch (e.g. red `X`/`AlertTriangle` icon + red border). Generic — applies to any tool that returns `{"error": ...}`, so this also improves SQL/search failure UX.
**Warning signs:** A failed web search that looks successful in the UI.
`[VERIFIED: read frontend/src/hooks/useChat.ts + components/ToolCallCard.tsx + backend/routers/chat.py]`

### Pitfall 2: Leaving `api_key` in the JSON body "just in case"
**What goes wrong:** After adding the Bearer header, keeping `"api_key": ...` in the body invites confusion and may be rejected by Tavily (the field is undocumented now). If the header is missing but the body key remains, you get a silent 401 that looks like a "bad key."
**How to avoid:** Send the key **only** in the `Authorization` header; remove it from the body. Add a unit test asserting the request body has no `api_key` and the header is `Bearer …`.
`[VERIFIED: docs.tavily.com]`

### Pitfall 3: 401 vs 429 collapse into one generic error string
**What goes wrong:** `raise_for_status()` inside `except Exception` turns "invalid key" (401), "rate limited" (429), and "usage-limit exceeded" (432/433) all into the same opaque `str(e)`. For graceful degradation (D-03) that is acceptable, but the agent's "couldn't reach the web" note will be vague.
**How to avoid (optional, Claude's discretion):** Catch `httpx.HTTPStatusError` and map `response.status_code` to a short reason ("web search key rejected", "web search rate-limited") in the returned `error`. Keep the broad fallback for network/timeout errors. Not required by any REQ — nice-to-have.
`[VERIFIED: docs.tavily.com status codes]`

### Pitfall 4: `@lru_cache` settings hide the prod key until restart
**What goes wrong:** Setting the `WEB_SEARCH_API_KEY` Fly secret does not enable the tool on the running process — `get_settings()` is `@lru_cache`d and read once. The tool stays absent until the app restarts.
**How to avoid:** After `fly secrets set`, ensure the machine restarts (Fly restarts on secret change by default). Confirm `web_search_enabled` in the live process before UAT.
`[VERIFIED: backend/config.py:195 @lru_cache]`

### Pitfall 5: Synchronous `httpx.post` blocks the async SSE loop for up to `timeout` seconds
**What goes wrong:** `execute_tool` (and thus `search_web` → `httpx.post`) is called **synchronously** inside the async `event_generator` (chat.py:1237), so a slow Tavily call blocks the event loop up to the 30s timeout.
**Why it's acceptable here:** This is the **pre-existing pattern for every non-subagent tool** (`search_documents`, `query_database`, all `kb_*`). Changing it is out of scope for a restoration phase. Note it; optionally consider a shorter timeout (e.g. 15–20s) so a hung provider degrades faster. Do not re-architect the loop.
`[VERIFIED: backend/routers/chat.py:1236-1244]`

## Code Examples

Verified patterns from the codebase + Tavily docs.

### The WSRCH-01 fix — Bearer header + configurable depth (`_search_tavily`)
```python
# Source: backend/services/web_search_service.py:21-50 (current) with the auth transport fixed.
# Tavily contract: docs.tavily.com/documentation/api-reference/endpoint/search
def _search_tavily(query: str, settings) -> dict:
    """Tavily search API — purpose-built for RAG."""
    try:
        response = httpx.post(
            "https://api.tavily.com/search",
            headers={"Authorization": f"Bearer {settings.web_search_api_key}"},  # WSRCH-01 fix
            json={
                # NOTE: no "api_key" here anymore — auth is header-only.
                "query": query,
                "max_results": settings.web_search_max_results,   # 5
                "include_answer": True,                            # D-04 keep
                "search_depth": settings.web_search_depth,         # D-04: "basic" (default) | "advanced" | ...
            },
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        results = [
            {"title": r.get("title", ""), "url": r.get("url", ""), "snippet": r.get("content", "")}
            for r in data.get("results", [])
        ]
        return {"answer": data.get("answer", ""), "results": results}
    except Exception as e:
        logger.error(f"Tavily search failed: {e}", exc_info=True)   # WSRCH-04 preserve
        return {"error": str(e), "results": []}
```

### D-02 citation guidance edit (`settings.system_prompt`)
```python
# Source: backend/config.py:95-102 — replace the single-line "cite ... with URLs" clause.
# Example wording (Claude's discretion on exact copy — must encode D-02):
"When you use web_search results, cite sources as inline markdown links at the point each "
"fact is used — e.g. [BGG](https://boardgamegeek.com/...) — AND end the answer with a short "
"\"Sources:\" list of the links you used. Prefer the knowledge base for game rules and "
"mechanics; use web_search for current/external facts the KB can't answer (prices, "
"availability, upcoming expansions, BGG rankings, designer/publisher news)."
```

### D-01 tool-selection steer (`TOOL_SELECTION_GUIDE`)
```python
# Source: backend/routers/chat.py:630-631 — expand the "External" web_search line.
"**External** -- Information outside the KB:\n"
"- web_search: current/external info NOT in the KB — prices, where-to-buy, availability, "
"new & upcoming expansions, BGG rankings & community sentiment, designer/publisher news. "
"Do NOT web-search game rules/mechanics that live in the KB.\n"
```

### D-03 backend error surface on the `tool_result` SSE event
```python
# Source: backend/routers/chat.py:1271-1292 — classify + flag the error.
_is_error = '"error"' in tool_result  # tool_result is the JSON string returned by execute_tool
tool_entry["status"] = "error" if _is_error else "complete"
tool_entry["output"] = tool_output_preview
# ... existing db update ...
yield {
    "event": "tool_event",
    "data": json.dumps({
        "tool_event": True,
        "type": "tool_result",
        "tool": fn_name,
        "call_id": tc["id"],
        "output": tool_output_preview,
        "is_error": _is_error,                 # NEW — frontend maps to status 'error'
        **({"subagent": True} if is_subagent else {}),
    }),
}
```
*(A more robust classifier parses `json.loads(tool_result).get("error")` — but the substring guard is safe because all tool errors serialize an `"error"` key. Planner's discretion.)*

### D-03 frontend — `useChat.ts` + `ToolCallCard.tsx`
```typescript
// useChat.ts:15-23 — widen the union
export interface ToolEvent {
  tool: string; args_preview: string; output?: string; call_id?: string
  subagent?: boolean
  status: 'running' | 'complete' | 'error'   // + 'error'
  subEvents?: SubEvent[]
}
// useChat.ts:206-220 — map the flag in the tool_result branch
? { ...t, status: (parsed.is_error ? 'error' : 'complete') as const, output: parsed.output }
```
```tsx
// ToolCallCard.tsx:120-124 — add an error branch (red icon/border)
{status === 'running'
  ? <span className="...animate-spin" />
  : status === 'error'
    ? <AlertTriangle className="w-3.5 h-3.5 text-red-500" />   // import from lucide-react
    : <Check className="w-3.5 h-3.5 text-gray-500" />}
// and derive borderColor red when status === 'error'
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Tavily `api_key` in the JSON request body | `Authorization: Bearer tvly-...` header (header-only) | Tavily standardized on Bearer auth across all endpoints; the body-key form is no longer documented | The exact break this phase fixes — the code was written against the legacy body form `[VERIFIED: docs.tavily.com]` |
| `search_depth` only `basic`/`advanced` | Now also `fast` and `ultra-fast` | Current Tavily API | `web_search_depth` can accept the new fast tiers later; default `basic` remains valid `[VERIFIED: docs.tavily.com]` |

**Deprecated/outdated:**
- Passing `api_key` in the POST body to `/search` — undocumented/deprecated; use the header. `[VERIFIED: docs.tavily.com]`

## Runtime State Inventory

Not applicable — this is a fix + config + verification phase, not a rename/refactor/migration. No stored data keys, collection names, or IDs change. The only new runtime state is:
- **Secrets/env vars:** a new **read** of `WEB_SEARCH_DEPTH` (optional; defaults to `basic`) and the existing `WEB_SEARCH_API_KEY` which must be **set in prod** (Fly secret) for SC-5. No key is renamed. — *verified against config.py and INTEGRATIONS.md.*
- Nothing else — no build artifacts, OS-registered state, or datastore migrations. — *verified: the change is code + one setting + prompt copy.*

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | 30s httpx timeout is adequate; Tavily gives no official timeout guidance | Tavily API contract / Pitfall 5 | Low — `advanced` depth could exceed it on rare queries; graceful `{"error"}` still fires, just later |
| A2 | Substring `'"error"' in tool_result` reliably flags tool failures | Code Examples (D-03) | Low — all tools serialize an `"error"` key on failure; a `json.loads(...).get("error")` classifier removes even this small risk |
| A3 | Fly restarts the machine on `secrets set`, re-reading `@lru_cache` settings | Pitfall 4 / Env Availability | Low — standard Fly behavior; executor confirms `web_search_enabled` live before UAT |

## Open Questions (RESOLVED)

1. **How should the agent's "couldn't reach the web" acknowledgement be triggered (D-03 discretion)?**
   - What we know: the LLM already receives the `{"error": ...}` in the tool message, so it *can* narrate the failure without extra plumbing.
   - What's unclear: whether prompt reliability needs an explicit system-prompt nudge ("if a tool returns an error, briefly tell the user, then answer best-effort").
   - Recommendation: add a one-sentence nudge to `system_prompt` for reliability; rely on the existing error-in-tool-result payload for the mechanism (no separate injection).
   - **RESOLVED:** Plan 16-02 T2 adds the one-sentence system-prompt error-ack nudge; mechanism stays the existing error-in-tool-result payload (no separate injection).

2. **Should 401/429/432/433 be mapped to friendlier error text?**
   - What we know: all collapse to `str(e)` today; graceful degradation still works.
   - What's unclear: whether the vague message is acceptable for the tool card + agent note.
   - Recommendation: optional status-code mapping (Pitfall 3); not required by any REQ. Planner's call on scope.
   - **RESOLVED:** Deliberately omitted — not required by any WSRCH requirement; CONTEXT D-03 leaves it to planner discretion. Left for a future enhancement if desired.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `httpx` | Tavily HTTP call | ✓ | installed (used directly by 3 services) | — |
| `pytest` + `pytest-asyncio` | Wave 0 unit tests | ✓ | 8.4.2 / 0.23.8 | — |
| Tavily API key (dev) `WEB_SEARCH_API_KEY` | Local `web_search_enabled` + dev smoke | ✗ unknown — not in repo (secret) | — | Unit-test with mocked `httpx.post`; live smoke needs a real key |
| Tavily API key (prod) `WEB_SEARCH_API_KEY` Fly secret | SC-5 live prod verify (WSRCH-01/03) | ✗ must be set | — | **No fallback — required for the live prod gate** |

**Missing dependencies with no fallback:**
- **Prod `WEB_SEARCH_API_KEY` Fly secret** — must be set (owner-configured) for the SC-5 live verification. Ops step for the executor; then restart the machine so `@lru_cache` settings re-read.

**Missing dependencies with fallback:**
- **Dev Tavily key** — all WSRCH-01/02/04 unit tests mock `httpx.post` (no key needed). Only the optional dev live-smoke and the prod gate need a real `tvly-` key.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.4.2 + pytest-asyncio 0.23.8 |
| Config file | `backend/pytest.ini` (`testpaths = tests`, `asyncio_mode = auto`, `--strict-markers`, `integration` marker registered) |
| Quick run command | `cd backend && python -m pytest tests/test_web_search.py -x` |
| Full suite command | `cd backend && python -m pytest -q` |

Mocking convention (no `respx`/`pytest-httpx` in the project): `monkeypatch.setattr` on the module's symbol + `unittest.mock.MagicMock`, or construct real `httpx.Request`/`httpx.Response` objects (as `tests/test_error_surfacing.py` does for status errors). For `_search_tavily`, monkeypatch `web_search_service.httpx.post` to return a `MagicMock` whose `.json()` yields a canned Tavily body and whose `.raise_for_status()` is a no-op (or raises `httpx.HTTPStatusError` for the failure cases). `[VERIFIED: read tests/conftest.py, test_model_catalog.py, test_error_surfacing.py]`

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| WSRCH-01 | `_search_tavily` sends `Authorization: Bearer <key>` header, **no** `api_key` in body, `search_depth` from settings; maps 200 body to `{answer, results:[{title,url,snippet}]}` | unit | `pytest tests/test_web_search.py::test_tavily_bearer_auth -x` | ❌ Wave 0 |
| WSRCH-02 | `web_search_enabled` false → `WEB_SEARCH_TOOL` NOT in tools list AND `search_web` returns `{"error":"Web search not configured"}`; true → tool present | unit | `pytest tests/test_web_search.py::test_gating_fail_closed -x` | ❌ Wave 0 |
| WSRCH-02 | `Settings.web_search_depth` defaults to `"basic"`; `WEB_SEARCH_DEPTH` env overrides (mirror `test_config.py` pattern) | unit | `pytest tests/test_config.py::test_web_search_depth_default -x` | ❌ Wave 0 (add to existing file) |
| WSRCH-03 | `Settings().system_prompt` contains the D-02 citation-format guidance (inline links + Sources list) | unit (string assert) | `pytest tests/test_web_search.py::test_system_prompt_citation_guidance -x` | ❌ Wave 0 |
| WSRCH-04 | On `httpx.post` raising / 401 / 429, `search_web` returns an `{"error": ...}` dict (no exception) and `logger.error(..., exc_info=True)` fires | unit | `pytest tests/test_web_search.py::test_graceful_failure_logs -x` | ❌ Wave 0 |
| WSRCH-04 | Tool-loop marks the `tool_result` SSE event `is_error: true` and `tool_entry.status == "error"` when `search_web` returns an error | unit | `pytest tests/test_web_search.py::test_tool_result_error_status -x` | ❌ Wave 0 |
| WSRCH-01/03 | **Live prod verify (SC-5):** set `WEB_SEARCH_API_KEY` Fly secret → restart → ask a current-info board-game query (e.g. "current price / latest expansion of Catan") → assert a web-grounded answer with inline links + Sources list and a Web Search tool card | manual (prod smoke) | manual — real `tvly-` key required | n/a |
| WSRCH-04 | **Live failure verify:** temporarily set an invalid `tvly-` key (or block network) → confirm the tool card shows the failed state and the agent notes it couldn't reach the web, then answers best-effort | manual (prod/dev smoke) | manual | n/a |

Frontend (D-03 UI) has no test framework configured (no runner in `frontend/package.json`) — verify the failed-state card via browser testing per CLAUDE.md's "Validate" step (use a browser MCP). `[VERIFIED: CLAUDE.md + frontend/package.json has no test script]`

### Sampling Rate
- **Per task commit:** `cd backend && python -m pytest tests/test_web_search.py -x` (+ `tests/test_config.py` for the depth field)
- **Per wave merge:** `cd backend && python -m pytest -q` (full backend suite green)
- **Phase gate:** Full suite green before `/gsd-verify-work`, then the two manual prod smokes (SC-5 success + failure paths).

### Wave 0 Gaps
- [ ] `backend/tests/test_web_search.py` — new file; covers WSRCH-01, WSRCH-02 (gating + service guard), WSRCH-03 (prompt string), WSRCH-04 (graceful failure + error-status surface). No `conftest` change needed — reuse `monkeypatch` + `MagicMock`.
- [ ] `backend/tests/test_config.py` — add `test_web_search_depth_default` / `test_web_search_depth_env_override` (mirror the existing `chat_max_iterations` tests).
- [ ] Framework install: none — pytest + pytest-asyncio already present.
- [ ] Real `tvly-` key provisioned for the dev live-smoke (optional) and the prod Fly secret (required for SC-5).

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Tavily auth is a server-held API key, not user auth; chat auth unchanged (Supabase JWT) |
| V3 Session Management | no | No sessions touched |
| V4 Access Control | yes | Web search is an owner-configured server tool; no per-user keys (locked out of scope). Existing RLS untouched. |
| V5 Input Validation | yes | `query` is the LLM's own tool argument, forwarded to Tavily as a POST body param (not concatenated into SQL/HTML) — parameterized by construction. No new user-controlled sink. |
| V6 Cryptography | yes | The `tvly-` key is a secret — never log it, never send it to the client. Transport is HTTPS (`https://api.tavily.com`). Do not hand-roll the Bearer scheme beyond the single header. |
| V9 Communications | yes | HTTPS-only endpoint; `httpx` verifies TLS by default (do not disable verification). |

### Known Threat Patterns for {Tavily httpx integration}

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| API key leakage into logs / SSE / tool card | Information Disclosure | The key rides an `Authorization` header, not the body/output — it is not in `str(e)` for an `HTTPStatusError` (which echoes method+URL only). **Caveat:** `services/log_scrub.py` scrubs `sk-or-` (OpenRouter) keys but **NOT** `tvly-` keys — if a future change ever interpolates the key into a message, it would not be redacted. Keep the key out of any interpolated string; optionally extend `scrub_secrets` to also match `tvly-`. `[VERIFIED: read services/log_scrub.py regex]` |
| Sending the owner key to the browser | Information Disclosure | Tool executes server-side only; the frontend never receives the key or the raw request — only the mapped `{answer, results}` / `{error}`. `[VERIFIED: execute_tool → search_web server path]` |
| SSRF via the search URL | Tampering / SSRF | Endpoint is a hardcoded constant (`https://api.tavily.com/search`); only the `query` string is variable — no user-controlled URL. No SSRF surface. |
| TLS downgrade / MITM | Tampering | Fixed `https://` endpoint; `httpx` verifies certs by default — do not pass `verify=False`. |
| DoS via slow provider blocking the event loop | Denial of Service | Bounded `timeout` on `httpx.post` (see Pitfall 5); graceful `{"error"}` on timeout. Consider lowering from 30s. |

## Sources

### Primary (HIGH confidence)
- `docs.tavily.com/documentation/api-reference/endpoint/search` — auth (Bearer header, body `api_key` undocumented), endpoint, full request params (`search_depth` values, `max_results` range, `include_answer` options), response schema (`answer`, `results[].{title,url,content,score}`), status codes (401/429/432/433/400/500). Fetched 2026-07-11.
- In-repo (read directly): `backend/services/web_search_service.py`, `backend/routers/chat.py` (tool def, gating, execute_tool, TOOL_SELECTION_GUIDE, SSE tool_result emit), `backend/config.py`, `backend/services/llm_service.py`, `frontend/src/components/ToolCallCard.tsx`, `frontend/src/hooks/useChat.ts`, `backend/pytest.ini`, `backend/tests/conftest.py`, `backend/tests/test_config.py`, `backend/tests/test_error_surfacing.py`, `.planning/codebase/INTEGRATIONS.md`, `CLAUDE.md`.

### Secondary (MEDIUM confidence)
- WebSearch (Tavily auth) — cross-confirmed the Bearer-header requirement against multiple sources (help.tavily.com, tavily-mcp README, agentsapis.com guide) before verifying the full contract on the official docs page.

### Tertiary (LOW confidence)
- None relied upon.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new deps; `httpx` + Tavily contract verified against official docs.
- Architecture / seams: HIGH — every edit target read directly in-repo with line numbers.
- Tavily API contract (WSRCH-01 root cause): HIGH — verified on docs.tavily.com 2026-07-11; the body-`api_key`→Bearer-header break is confirmed.
- Frontend failed-state gap (D-03): HIGH — confirmed by reading the actual `status` union and render code (no error state exists; CONTEXT.md's "reuse existing error rendering" is inaccurate).
- Pitfalls: HIGH — derived from read code + verified docs.

**Research date:** 2026-07-11
**Valid until:** ~2026-08-10 for the codebase seams (stable); Tavily API contract is fast-moving — re-verify the auth/params against docs.tavily.com if planning slips past ~2026-07-25.
