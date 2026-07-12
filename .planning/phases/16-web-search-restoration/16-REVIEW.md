---
phase: 16-web-search-restoration
reviewed: 2026-07-12T00:00:00Z
depth: standard
files_reviewed: 8
files_reviewed_list:
  - backend/config.py
  - backend/routers/chat.py
  - backend/services/log_scrub.py
  - backend/services/web_search_service.py
  - backend/tests/test_config.py
  - backend/tests/test_web_search.py
  - frontend/src/components/ToolCallCard.tsx
  - frontend/src/hooks/useChat.ts
findings:
  critical: 0
  warning: 3
  info: 2
  total: 5
status: issues_found
---

# Phase 16: Code Review Report

**Reviewed:** 2026-07-12
**Depth:** standard
**Files Reviewed:** 8
**Status:** issues_found

## Summary

The web-search restoration is largely sound. The Tavily transport correctly moves auth to an `Authorization: Bearer` header (removing the key from the JSON body, and — importantly — keeping it out of `str(e)` on the error path since httpx exceptions reference the URL, not headers). `search_depth` is now env-configurable, the `tvly-` scrub regex is correct, and the frontend status-union widening is safe (verified no exhaustive-switch consumers). The `is_error` SSE flag and red failed-state card are wired end-to-end and survive history reload.

No blockers. The issues below concern the **error classifier's precision** and **error-handling asymmetry** for the restored tool.

## Warnings

### WR-01: `tool_result_is_error` substring classifier produces both false negatives and false positives

**File:** `backend/routers/chat.py:81-89` (classifier), `1285-1286` (status assignment)
**Issue:** The classifier is a raw substring test — `return '"error"' in tool_result`. Two concrete defects:

1. **False negative (deterministic):** The docstring claims "explore_kb/analyze_document fallbacks" serialize an `"error"` key, but the `explore_kb` failure path does not. On explorer failure the result is assembled as `{"mode":…, "synthesis": "Explorer failed: …", "budget_exhausted": True, …}` (chat.py:1165-1174, serialized at :1198) with **no `"error"` key**. So a genuinely failed exploration renders a green check, not the red failed-state this phase added. (`analyze_document` failures at :1220/:1246 *do* carry `"error"`, so the two subagents are inconsistent.)
2. **False positive:** Any successful `query_database` result whose data contains the quoted token `"error"` flips the card red. This is easily reachable via a column alias — `SELECT status AS error …` yields rows serialized as `{"error": "completed"}` — or any cell whose value is exactly `error`. `execute_sql` success returns `{"success": True, "rows": […], …}` (sql_service.py:149-154), so the substring rides in user data.

The docstring is therefore inaccurate about its own guarantee.
**Fix:** Classify structurally instead of by substring. Either have the executor return an explicit flag, or parse and check the top-level key:
```python
def tool_result_is_error(tool_result: str) -> bool:
    try:
        obj = json.loads(tool_result)
    except (ValueError, TypeError):
        return False
    return isinstance(obj, dict) and "error" in obj
```
Then give `explore_kb`'s failure fallback an explicit `"error"` key (or a dedicated `failed: True` flag) so it matches the stated contract.

### WR-02: `web_search`/`query_database` tool dispatch has no arg guard — a malformed tool call crashes the whole turn instead of surfacing a graceful tool error

**File:** `backend/routers/chat.py:722-728`
**Issue:** `search_documents` and every `kb_*` branch wrap execution in `try/except` and return `{"tool": …, "error": str(e)}` so the LLM (and the new red card) can handle a failure. The `web_search` and `query_database` branches do not. `search_web` itself never raises (it catches internally), but `fn_args["query"]` / `fn_args["sql"]` will raise `KeyError` if the model emits a tool call missing a required arg — which LLMs occasionally do despite the schema. That `KeyError` propagates uncaught out of `execute_tool` and the `else:` dispatch at :1249, up to the generic `except Exception` at :1452, aborting the entire turn (generic error bubble, tool card stuck in `running`). For the tool this phase is restoring, that means the failure surface the phase built (red card) is bypassed entirely on a malformed call.
**Fix:** Mirror the other branches:
```python
elif fn_name == "web_search":
    try:
        result = search_web(query=fn_args["query"])
        return json.dumps({"tool": "web_search", **result})
    except Exception as e:
        logger.error(f"web_search failed: {e}", exc_info=True)
        return json.dumps({"tool": "web_search", "error": str(e)})
```
(Apply the same to `query_database`.)

### WR-03: Tool-result `output` reaches the SSE stream and DB unscrubbed, inconsistent with the phase's own scrub intent

**File:** `backend/routers/chat.py:1284`, `1301-1306` (SSE emit); `1290-1292` (DB persist)
**Issue:** `scrub_secrets` is applied at the other backend→client trust boundaries (`_sse_error` at :100, and the `_ScrubFilter` on logs), and this phase specifically extended the scrub to `tvly-` keys "as defense-in-depth." But the `tool_result` SSE event's `output` field and the persisted `tools_used` array carry raw `tool_result` (i.e. any tool's `str(e)`) with **no scrub**. This is not exploitable today — with header-based Tavily auth the key is absent from `str(e)`, and OpenAI/OpenRouter SDK errors do not echo the Authorization header — so no current leak. But it is the one tool-output channel to the FE/DB that bypasses the redaction chokepoint the phase just hardened, so any future tool whose exception text embeds a secret would leak here silently.
**Fix:** Run the preview through the same chokepoint before emit/persist:
```python
tool_output_preview = scrub_secrets(tool_result[:2000] if len(tool_result) > 2000 else tool_result)
```

## Info

### IN-01: `web_search_depth` comment lists values Tavily's API does not accept

**File:** `backend/config.py:139`
**Issue:** The comment documents `"basic"|"advanced"|"fast"|"ultra-fast"` as valid `search_depth` values. Per Tavily's documented `/search` API, `search_depth` accepts only `"basic"` and `"advanced"`. An operator who sets `WEB_SEARCH_DEPTH=fast` on the strength of this comment would get a 400 from Tavily on every web search (caught and degraded to a generic web-search error, but a permanent silent failure).
**Fix:** Correct the comment to the supported set: `# Tavily search depth: "basic"|"advanced" (env: WEB_SEARCH_DEPTH)`.

### IN-02: New default-asserting config test is env-fragile

**File:** `backend/tests/test_config.py:126-131`
**Issue:** `test_web_search_depth_default` instantiates `Settings()` and asserts `web_search_depth == "basic"`, but `config.py:10` runs `load_dotenv` at import, so a repo `.env` containing `WEB_SEARCH_DEPTH=advanced` would fail this test. The sibling test `test_system_prompt_citation_guidance` (test_web_search.py:148) already guards against exactly this class of leak with `monkeypatch.delenv(...)`, so the new default test is inconsistent with the file's own hardened pattern.
**Fix:** Add `monkeypatch.delenv("WEB_SEARCH_DEPTH", raising=False)` (and take `monkeypatch` as a param) before instantiating, matching the citation-guidance test.

---

_Reviewed: 2026-07-12_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
