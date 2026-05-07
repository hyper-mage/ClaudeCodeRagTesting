---
phase: 05-explorer-sub-agent
plan: 03
type: execute
wave: 3
depends_on:
  - "05-02"
files_modified:
  - backend/routers/chat.py
  - backend/services/explorer_service.py
  - backend/tests/test_explorer_service.py
  - backend/tests/test_explorer_integration.py
autonomous: true
requirements:
  - EXPL-01
  - EXPL-02
  - EXPL-03
  - EXPL-04
  - EXPL-06
must_haves:
  truths:
    - "Parent chat agent has a new explore_kb tool advertised in its tools list"
    - "When parent calls explore_kb, the SSE stream emits typed sub_event rows under a parent_call_id"
    - "Explorer's three modes (deep_search, summarize, find_similar) each receive a tailored seed prompt"
    - "Final tool_result event carries an ExplorerResult JSON dict back to the parent LLM"
  artifacts:
    - path: backend/routers/chat.py
      provides: "EXPLORE_KB_TOOL constant + streaming dispatcher branch in event_generator"
      contains: "EXPLORE_KB_TOOL"
    - path: backend/services/explorer_service.py
      provides: "Mode-specific system-prompt overlays (already partly in Plan 02; Plan 03 enriches find_similar + summarize)"
      contains: "MODE_HINTS"
    - path: backend/tests/test_explorer_integration.py
      provides: "Activated SSE-emission tests using FastAPI TestClient + StreamingResponse iteration + stub_db_chain"
      contains: "test_sub_events_emitted"
  key_links:
    - from: backend/routers/chat.py
      to: backend/services/explorer_service.py
      via: "from services.explorer_service import run_exploration (lazy import inside event_generator)"
      pattern: "from services.explorer_service import run_exploration"
    - from: backend/routers/chat.py (event_generator)
      to: SSE tool_event channel
      via: "type='sub_event' payload with parent_call_id"
      pattern: '"type": "sub_event"'
    - from: backend/routers/chat.py
      to: tools list inside event_generator
      via: "tools.append(EXPLORE_KB_TOOL)"
      pattern: "EXPLORE_KB_TOOL"
    - from: backend/tests/test_explorer_integration.py
      to: backend/tests/fixtures/explorer_fixtures.py
      via: "from tests.fixtures.explorer_fixtures import stub_db_chain"
      pattern: "stub_db_chain"
---

<objective>
Wire the explorer service into the parent chat loop and finalize the three modes (deep_search, summarize, find_similar). After this plan: a user-facing chat message that triggers explore_kb produces a fully streaming SSE flow with nested sub_event rows under the parent's tool_event card, and the parent LLM receives a structured ExplorerResult back.

Purpose: Plan 02 built the explorer in isolation; this plan exposes it to the user.

Output:
- `EXPLORE_KB_TOOL` schema in backend/routers/chat.py
- Streaming dispatcher branch in `event_generator()` that consumes `run_exploration()` and emits SSE sub_event rows
- Tools list includes `EXPLORE_KB_TOOL` always (KB always exists)
- Updated TOOL_SELECTION_GUIDE with explore_kb guidance
- Mode-specific guidance reinforced for `summarize` and `find_similar` (EXPL-02, EXPL-03)
- Recommendation seeding pattern documented and verified (EXPL-04: parent passes resolved seed in `query`)
- Unit tests in test_explorer_service.py for `find_similar` + `recommendation_seed` modes activated (Task 2)
- Integration tests in test_explorer_integration.py activated using the shared `stub_db_chain` helper (Task 3)
</objective>

<execution_context>
@.claude/get-shit-done/workflows/execute-plan.md
@.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@.planning/phases/05-explorer-sub-agent/05-RESEARCH.md
@.planning/phases/05-explorer-sub-agent/05-VALIDATION.md
@.planning/phases/05-explorer-sub-agent/05-01-SUMMARY.md
@.planning/phases/05-explorer-sub-agent/05-02-SUMMARY.md
@backend/routers/chat.py
@backend/services/explorer_service.py
@backend/services/subagent_service.py
@backend/tests/fixtures/explorer_fixtures.py
@backend/tests/test_folders_api.py

<interfaces>
<!-- Explorer service contract (built in Plan 02) -->

```python
# backend/services/explorer_service.py
def run_exploration(user_id: str, query: str, mode: str = "deep_search") -> Iterator[dict]:
    """Yields:
        {"type": "sub_iteration", "iteration": int}
        {"type": "sub_tool_start", "call_id": str, "tool": str, "args_preview": str}
        {"type": "sub_tool_result", "call_id": str, "tool": str, "output": str}
        {"type": "result", "result": dict}   # FINAL — must be last yield
    """
```

<!-- Existing parent loop pattern (chat.py:484-566) -->

```python
for tc in event["tool_calls"]:
    fn_name = tc["function"]["name"]
    fn_args = json.loads(tc["function"]["arguments"])
    args_preview = _build_args_preview(fn_name, fn_args)
    tool_entry = {"tool": fn_name, "args_preview": args_preview, "call_id": tc["id"], "status": "running"}
    if fn_name == "analyze_document":
        tool_entry["subagent"] = True
    tools_used_acc.append(tool_entry)
    yield {"event": "tool_event", "data": json.dumps({...tool_start...})}
    tool_result = execute_tool(fn_name, fn_args, user_id)   # <-- this becomes branched
    ...
    yield {"event": "tool_event", "data": json.dumps({...tool_result...})}
```

<!-- Shared DB-chain stub (built in Plan 01, consumed by Task 3) -->

```python
# backend/tests/fixtures/explorer_fixtures.py
def stub_db_chain(execute_return=None):
    """Recursively chainable MagicMock matching Supabase's query-builder surface.
       Every attribute access (table/select/eq/insert/...) returns self; only
       .execute() resolves, returning MagicMock(data=execute_return).
       Use this instead of hand-rolling chain mocks — decouples tests from
       chat.py's exact chain ordering."""
```

<!-- New SSE payload shape (consumed by Plan 04 frontend) -->

```jsonc
// parent tool_start (existing shape, with subagent:true)
{ "tool_event": true, "type": "tool_start", "tool": "explore_kb",
  "subagent": true, "call_id": "call_abc", "args_preview": "mode=\"summarize\" query=\"...\"" }

// each sub-iteration / sub-tool (NEW)
{ "tool_event": true, "type": "sub_event", "subagent": true,
  "parent_call_id": "call_abc",
  "sub_event": { "type": "sub_tool_start", "call_id": "call_xyz", "tool": "kb_tree", "args_preview": "depth=2" } }

// parent tool_result (existing shape, output is ExplorerResult JSON)
{ "tool_event": true, "type": "tool_result", "tool": "explore_kb", "subagent": true,
  "call_id": "call_abc", "output": "<ExplorerResult JSON, possibly clipped>" }
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Register EXPLORE_KB_TOOL on parent chat loop + streaming dispatcher branch</name>
  <read_first>
    - backend/routers/chat.py (full — especially lines 110-265 for tool constant style, 267-289 for guide, 444-566 for event_generator)
    - backend/services/explorer_service.py (full — Plan 02 output)
    - .planning/phases/05-explorer-sub-agent/05-RESEARCH.md (lines 540-577 — EXPLORE_KB_TOOL schema; lines 493-537 — dispatcher pattern)
    - .planning/phases/05-explorer-sub-agent/05-02-SUMMARY.md (verify sub_event field shapes)
  </read_first>
  <files>
    - backend/routers/chat.py
  </files>
  <behavior>
    - `EXPLORE_KB_TOOL` constant defined in chat.py with mode enum {deep_search, summarize, find_similar} and required {mode, query}
    - `tools.append(EXPLORE_KB_TOOL)` happens unconditionally in event_generator (KB always exists — same gating logic as KB_*_TOOL)
    - TOOL_SELECTION_GUIDE updated with an "Explore" subsection mentioning explore_kb's three modes and when NOT to use it (single lookups stay with kb_*)
    - When fn_name == "explore_kb": dispatcher branch consumes `run_exploration` generator, emits one SSE row per `sub_*` yield as `type: sub_event` with `parent_call_id=tc["id"]` and `subagent: True`, captures the final `result` yield as the tool_result content
    - Parent tool_start event for explore_kb tagged `subagent: True` (matches analyze_document convention)
    - Parent tool_result event for explore_kb carries the ExplorerResult dict (json-encoded inside the existing `output` field) and tagged `subagent: True`
    - tools_used accumulator entry for explore_kb tagged `subagent: True` so it persists with the existing schema
    - The OTHER 9 tools continue to flow through `execute_tool()` unchanged (no regression)
  </behavior>
  <action>
    1) In `backend/routers/chat.py`, append a new TOOL constant AFTER the existing `KB_GLOB_TOOL = {...}` definition (~ line 265):
       ```python
       EXPLORE_KB_TOOL = {
           "type": "function",
           "function": {
               "name": "explore_kb",
               "description": (
                   "Spawn an explorer sub-agent for complex, multi-step exploration of the knowledge base. "
                   "Use when a single tool call cannot answer the question -- for example: "
                   "(1) summarizing an entire folder's contents, "
                   "(2) finding cross-references across multiple games, "
                   "(3) recommending games similar to one mentioned by the user. "
                   "DO NOT use for simple lookups -- kb_ls, kb_read, kb_grep are faster. "
                   "When using mode='find_similar', resolve the seed game in `query` first "
                   "(e.g. 'Find games similar to Catan. Focus on trading and resource management.')."
               ),
               "parameters": {
                   "type": "object",
                   "properties": {
                       "mode": {
                           "type": "string",
                           "enum": ["deep_search", "summarize", "find_similar"],
                           "description": (
                               "deep_search: multi-step search across the KB. "
                               "summarize: produce a synthesis of a folder's contents. "
                               "find_similar: find games with mechanics similar to a given game."
                           ),
                       },
                       "query": {
                           "type": "string",
                           "description": "The question or task for the explorer. Be specific; include any folder paths or game names.",
                       },
                   },
                   "required": ["mode", "query"],
               },
           },
       }
       ```

    2) Update `TOOL_SELECTION_GUIDE` (the multi-line string at ~line 267). Append a new section BEFORE the trailing 'Always start with kb_tree...' line:
       ```
       **Deep exploration** -- Multi-step KB traversal (use sparingly):
       - explore_kb (mode='summarize'): coherent synthesis of a folder's contents
       - explore_kb (mode='find_similar'): cross-reference games with similar mechanics (resolve seed game in the query)
       - explore_kb (mode='deep_search'): broad multi-step search when one tool isn't enough

       ```
       (Keep formatting consistent with the existing sections.)

    3) In `event_generator()` (around line 453), update the tools list construction:
       ```python
       # KB navigation tools -- always available (default KB always exists)
       tools = [KB_LS_TOOL, KB_TREE_TOOL, KB_READ_TOOL, KB_GREP_TOOL, KB_GLOB_TOOL, EXPLORE_KB_TOOL]
       ```

    4) In `event_generator()`, REPLACE the existing per-tool dispatch (the line `tool_result = execute_tool(fn_name, fn_args, user_id)`, around line 534) with a branched dispatch. Locate the block from `# Emit tool_start SSE event` through the `# Emit tool_result SSE event` block (~lines 521-563) and modify so that:

       - Tool entry is tagged `subagent=True` for both `analyze_document` AND `explore_kb`
       - Parent tool_start payload is tagged `subagent: True` for both
       - When `fn_name == "explore_kb"`: import + drive `run_exploration`, emit a `sub_event` SSE row per yield, capture the final result. Use `asyncio.to_thread` to call the sync generator from the async event_generator (Pitfall 3).
       - When fn_name != "explore_kb": unchanged behavior via `execute_tool(fn_name, fn_args, user_id)`

       Concretely, replace the inner section with:
       ```python
       # Build args preview for display
       args_preview = _build_args_preview(fn_name, fn_args)

       # Accumulate tool event for persistence
       tool_entry = {
           "tool": fn_name,
           "args_preview": args_preview,
           "call_id": tc["id"],
           "status": "running",
       }
       is_subagent = fn_name in ("analyze_document", "explore_kb")
       if is_subagent:
           tool_entry["subagent"] = True
       tools_used_acc.append(tool_entry)

       # Emit tool_start SSE event
       yield {
           "event": "tool_event",
           "data": json.dumps({
               "tool_event": True,
               "type": "tool_start",
               "tool": fn_name,
               "call_id": tc["id"],
               "args_preview": args_preview,
               **({"subagent": True} if is_subagent else {}),
           }),
       }

       # Dispatch
       if fn_name == "explore_kb":
           import asyncio
           from services.explorer_service import run_exploration

           # Drive the sync generator via to_thread to avoid blocking the event loop.
           # We run the whole generator on a worker thread, but yield SSE events as
           # the generator emits them by using a queue.
           import queue as _queue
           q: _queue.Queue = _queue.Queue()
           SENTINEL = object()

           def _drive():
               try:
                   for ev in run_exploration(
                       user_id=user_id,
                       query=fn_args["query"],
                       mode=fn_args.get("mode", "deep_search"),
                   ):
                       q.put(ev)
               except Exception as ex:
                   q.put({"type": "error", "error": str(ex)})
               finally:
                   q.put(SENTINEL)

           task = asyncio.create_task(asyncio.to_thread(_drive))
           final_result_dict = None
           while True:
               sub_ev = await asyncio.to_thread(q.get)
               if sub_ev is SENTINEL:
                   break
               if sub_ev.get("type") == "result":
                   final_result_dict = sub_ev["result"]
                   continue
               if sub_ev.get("type") == "error":
                   final_result_dict = {
                       "mode": fn_args.get("mode", "deep_search"),
                       "query": fn_args["query"],
                       "findings": [],
                       "synthesis": f"Explorer failed: {sub_ev['error']}",
                       "tools_used": [],
                       "iterations": 0,
                       "budget_exhausted": True,
                   }
                   continue
               # sub_iteration / sub_tool_start / sub_tool_result -> SSE sub_event row
               yield {
                   "event": "tool_event",
                   "data": json.dumps({
                       "tool_event": True,
                       "type": "sub_event",
                       "subagent": True,
                       "parent_call_id": tc["id"],
                       "sub_event": sub_ev,
                   }),
               }
           await task
           if final_result_dict is None:
               final_result_dict = {
                   "mode": fn_args.get("mode", "deep_search"),
                   "query": fn_args["query"],
                   "findings": [],
                   "synthesis": "Explorer produced no result.",
                   "tools_used": [],
                   "iterations": 0,
                   "budget_exhausted": True,
               }
           tool_result = json.dumps({"tool": "explore_kb", **final_result_dict})
       else:
           tool_result = execute_tool(fn_name, fn_args, user_id)

       current_messages.append({
           "role": "tool",
           "tool_call_id": tc["id"],
           "content": tool_result,
       })

       # Update accumulated tool entry with result
       tool_output_preview = tool_result[:2000] if len(tool_result) > 2000 else tool_result
       tool_entry["status"] = "complete"
       tool_entry["output"] = tool_output_preview

       # Persist tool events incrementally
       db.table("messages").update({
           "tools_used": tools_used_acc,
       }).eq("id", assistant_msg_id).execute()

       # Emit tool_result SSE event
       yield {
           "event": "tool_event",
           "data": json.dumps({
               "tool_event": True,
               "type": "tool_result",
               "tool": fn_name,
               "call_id": tc["id"],
               "output": tool_output_preview,
               **({"subagent": True} if is_subagent else {}),
           }),
       }
       ```

       Critical: keep the existing surrounding control flow (`for tc in event["tool_calls"]:` outer, the `tool_call_happened = True`, the message append for `role: assistant + tool_calls`) UNCHANGED. Only the inner per-call dispatch block changes.
  </action>
  <acceptance_criteria>
    - `grep -n "EXPLORE_KB_TOOL" backend/routers/chat.py` returns ≥3 matches (definition + tools list append + maybe schema)
    - `grep -n "explore_kb" backend/routers/chat.py` returns ≥4 matches (description, dispatch branch, sub_event emission)
    - `grep -n "from services.explorer_service import run_exploration" backend/routers/chat.py` returns a match
    - `grep -n '"type": "sub_event"' backend/routers/chat.py` returns a match
    - `grep -n "parent_call_id" backend/routers/chat.py` returns a match
    - `grep -n "asyncio.to_thread" backend/routers/chat.py` returns ≥1 match (Pitfall 3 mitigation)
    - `grep -n "Deep exploration" backend/routers/chat.py` returns a match (TOOL_SELECTION_GUIDE updated)
    - `cd backend && venv/Scripts/python -c "from routers.chat import EXPLORE_KB_TOOL; assert EXPLORE_KB_TOOL['function']['name']=='explore_kb'; assert set(EXPLORE_KB_TOOL['function']['parameters']['properties']['mode']['enum']) == {'deep_search','summarize','find_similar'}; print('OK')"` exits 0
    - Existing tests in test_folders_api.py still pass (no regression): `cd backend && venv/Scripts/python -m pytest tests/test_folders_api.py -q` exits 0
  </acceptance_criteria>
  <verify>
    <automated>cd backend && venv/Scripts/python -c "from routers.chat import EXPLORE_KB_TOOL, KB_LS_TOOL; assert EXPLORE_KB_TOOL['function']['name']=='explore_kb'; assert sorted(EXPLORE_KB_TOOL['function']['parameters']['properties']['mode']['enum'])==['deep_search','find_similar','summarize']; from services.explorer_service import run_exploration; print('OK')" && cd backend && venv/Scripts/python -m pytest tests/test_folders_api.py -q</automated>
  </verify>
  <done>
    explore_kb is a fully registered tool on the parent loop with a streaming dispatcher; sync-generator-in-async pattern handled via to_thread + queue; existing tools unchanged; no test regressions.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Activate find_similar + recommendation_seed unit tests (mocked LLM, no HTTP layer)</name>
  <read_first>
    - backend/tests/test_explorer_service.py (after Plan 02 — imports + activated tests already in place)
    - backend/tests/fixtures/explorer_fixtures.py (EXPLORER_SCENARIOS["find_similar_azul"])
    - backend/services/explorer_service.py (after Task 1 — mode gating)
  </read_first>
  <files>
    - backend/tests/test_explorer_service.py
  </files>
  <behavior>
    - test_find_similar_mode: drives explorer with `mode="find_similar"` using EXPLORER_SCENARIOS["find_similar_azul"]; asserts result.mode=="find_similar" and ≥2 findings, each with non-empty path and relevance
    - test_recommendation_seed: passes a multi-sentence parent-resolved seed query (e.g. "Find games similar to Catan. Focus on trading."), asserts that string is included verbatim in the user message sent to the LLM (proves parent-resolved seed pattern; EXPL-04)
    - No HTTP layer, no DB mocking — these tests drive the explorer directly with patched kb_* + mocked LLM client
  </behavior>
  <action>
    In `backend/tests/test_explorer_service.py`:
    - REMOVE skip markers from `test_find_similar_mode` and `test_recommendation_seed`. Replace bodies:

    ```python
    def test_find_similar_mode():
        """EXPL-03: mode='find_similar' assembles ≥2 findings across multiple games."""
        from services import explorer_service
        client = mock_llm_client(EXPLORER_SCENARIOS["find_similar_azul"])
        with patch.object(explorer_service, "get_llm_client", return_value=client), \
             patch.object(explorer_service, "kb_grep", return_value="match snippets"), \
             patch.object(explorer_service, "kb_ls", return_value="Sagrada/\nCalico/"):
            events = list(explorer_service.run_exploration(
                TEST_USER_ID, "Find games similar to Azul. Focus on tile placement.", "find_similar"))
        result = events[-1]["result"]
        assert result["mode"] == "find_similar"
        assert len(result["findings"]) >= 2
        for f in result["findings"]:
            assert f["path"] and f["relevance"]


    def test_recommendation_seed():
        """EXPL-04: explorer receives parent-resolved seed query verbatim in its user message."""
        from services import explorer_service
        seed = "Find games similar to Catan. Focus on trading and resource management."
        captured: list[list[dict]] = []
        def _capture_create(**kwargs):
            captured.append(kwargs["messages"])
            from tests.fixtures.explorer_fixtures import make_response
            # Stop immediately by returning no tool calls
            return make_response(content="", finish_reason="stop")
        client = MagicMock()
        client.chat.completions.create = MagicMock(side_effect=_capture_create)
        with patch.object(explorer_service, "get_llm_client", return_value=client):
            list(explorer_service.run_exploration(TEST_USER_ID, seed, "find_similar"))
        assert captured, "LLM not called"
        # First call's user message must contain the seed
        user_msgs = [m for m in captured[0] if m["role"] == "user"]
        assert any(seed in m["content"] for m in user_msgs)
    ```
  </action>
  <acceptance_criteria>
    - `cd backend && venv/Scripts/python -m pytest tests/test_explorer_service.py -q` exits 0 (all tests now active and passing)
    - `grep -c "@pytest.mark.skip" backend/tests/test_explorer_service.py` returns 0
    - `grep -n "test_find_similar_mode" backend/tests/test_explorer_service.py` returns a match (and is NOT skip-marked: `grep -B 1 "def test_find_similar_mode" backend/tests/test_explorer_service.py | grep -c "skip"` returns 0)
    - `grep -n "test_recommendation_seed" backend/tests/test_explorer_service.py` returns a match (not skip-marked)
  </acceptance_criteria>
  <verify>
    <automated>cd backend && venv/Scripts/python -m pytest tests/test_explorer_service.py -q</automated>
  </verify>
  <done>
    Find-similar mode and recommendation-seed pattern verified by unit tests; full explorer-service unit-test file green with zero skips remaining.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: Activate SSE integration tests — TestClient end-to-end, consumes stub_db_chain helper</name>
  <read_first>
    - backend/tests/test_explorer_integration.py (Plan 01 scaffold)
    - backend/tests/test_folders_api.py (lines 1-100 — TestClient + dependency_overrides pattern)
    - backend/routers/chat.py (after Task 1 — understand the dispatch branch + sub_event emission ordering)
    - backend/tests/fixtures/explorer_fixtures.py (stub_db_chain helper from Plan 01)
  </read_first>
  <files>
    - backend/tests/test_explorer_integration.py
  </files>
  <behavior>
    - test_explore_kb_tool_registered: imports EXPLORE_KB_TOOL from routers.chat, asserts schema shape (mode enum + required fields)
    - test_sub_events_emitted: uses FastAPI TestClient + dependency_overrides to call POST /api/threads/{id}/messages with a message that triggers explore_kb (mocked stream_chat_completion returns an explore_kb tool_call), patches run_exploration to yield a controlled event sequence, parses SSE response and asserts ≥4 rows with `"type": "sub_event"` and `"parent_call_id"` present
    - test_final_tool_result: same setup, asserts the LAST tool_event with type=tool_result for explore_kb has an `output` field that contains an ExplorerResult JSON dict (parseable, has mode/query/synthesis fields)
    - test_parent_call_id_links_subevents: asserts every sub_event's parent_call_id matches the call_id of the preceding tool_start
    - ALL DB interactions use the shared `stub_db_chain` helper from explorer_fixtures — do NOT hand-roll ad-hoc chain mocks (fragile to chat.py reordering, W1 fix)
  </behavior>
  <action>
    Replace `backend/tests/test_explorer_integration.py` contents with:

    ```python
    """Integration tests for explore_kb wired into the parent chat loop.

    These drive the full FastAPI request path with a mocked LLM and a mocked
    Supabase client. DB interactions use the shared `stub_db_chain` helper
    (backend/tests/fixtures/explorer_fixtures.py::stub_db_chain) to decouple
    the tests from chat.py's exact query-builder ordering.
    """
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

    import json
    import pytest
    from unittest.mock import patch, MagicMock
    from fastapi.testclient import TestClient

    from main import app
    from auth import get_user_id
    from tests.fixtures.explorer_fixtures import TEST_USER_ID, stub_db_chain

    pytestmark = pytest.mark.integration


    @pytest.fixture(autouse=True)
    def _override_auth():
        app.dependency_overrides[get_user_id] = lambda: TEST_USER_ID
        yield
        app.dependency_overrides.clear()


    def _make_explore_tool_call_stream():
        """Mock stream_chat_completion to yield exactly one explore_kb tool_call then done."""
        def _stream(messages, tools=None, tool_guide=None):
            # First "turn": tool_call for explore_kb
            yield {
                "type": "tool_call",
                "tool_calls": [{
                    "id": "call_parent_1",
                    "type": "function",
                    "function": {
                        "name": "explore_kb",
                        "arguments": json.dumps({"mode": "summarize", "query": "Summarize Catan"}),
                    },
                }],
            }
            # Second "turn" (after tool result fed back): final text, no more tool_calls
            yield {"type": "text_delta", "text": "Done."}
            yield {"type": "done"}
        return _stream


    def _fake_explorer_events():
        """Generator returning the canonical explorer event sequence."""
        yield {"type": "sub_iteration", "iteration": 1}
        yield {"type": "sub_tool_start", "call_id": "sub_1", "tool": "kb_tree", "args_preview": 'path="Board Games/Catan"'}
        yield {"type": "sub_tool_result", "call_id": "sub_1", "tool": "kb_tree", "output": "Catan/\n  rules.md"}
        yield {"type": "sub_iteration", "iteration": 2}
        yield {"type": "sub_tool_start", "call_id": "sub_2", "tool": "kb_read", "args_preview": 'path="Board Games/Catan/rules.md"'}
        yield {"type": "sub_tool_result", "call_id": "sub_2", "tool": "kb_read", "output": "Players collect..."}
        yield {"type": "result", "result": {
            "mode": "summarize", "query": "Summarize Catan",
            "findings": [{"title": "Rules", "path": "Board Games/Catan/rules.md",
                          "excerpt": "Players collect resources",
                          "relevance": "Core mechanics"}],
            "synthesis": "Catan is a resource-trading game.",
            "tools_used": ["kb_tree", "kb_read"],
            "iterations": 2,
            "budget_exhausted": False,
        }}


    def test_explore_kb_tool_registered():
        """Parent advertises EXPLORE_KB_TOOL with the documented schema."""
        from routers.chat import EXPLORE_KB_TOOL
        assert EXPLORE_KB_TOOL["function"]["name"] == "explore_kb"
        params = EXPLORE_KB_TOOL["function"]["parameters"]
        assert sorted(params["properties"]["mode"]["enum"]) == ["deep_search", "find_similar", "summarize"]
        assert "query" in params["required"]
        assert "mode" in params["required"]


    def _collect_sse_lines(response):
        """Read a streaming SSE response into a list of (event, data_dict) tuples."""
        events = []
        current_event = None
        buf = ""
        for chunk in response.iter_text():
            buf += chunk
            while "\n" in buf:
                line, buf = buf.split("\n", 1)
                line = line.strip()
                if line.startswith("event:"):
                    current_event = line.split(":", 1)[1].strip()
                elif line.startswith("data:"):
                    try:
                        events.append((current_event, json.loads(line.split(":", 1)[1].strip())))
                    except json.JSONDecodeError:
                        continue
        return events


    def _post_message_collect(client_obj):
        """POST a message and return collected SSE events.

        Uses stub_db_chain to decouple DB mocking from chat.py's exact
        query-builder ordering. The terminal `.data` value is chosen so that:
          - thread lookups return a valid thread row for TEST_USER_ID
          - message inserts return the newly created assistant message id
          - document / chunk lookups return empty (no RETRIEVAL/ANALYZE tools appended)
        If chat.py evolves and a branch needs a different .data shape, swap in
        a custom-per-call stub or add side_effect logic — but start simple.
        """
        # A single data blob that happens to satisfy the common shapes:
        #   - iterables for list-returning queries: seen as [] iterable of that dict
        #   - dict for .maybe_single()/.single(): valid thread row
        # For .insert(...).execute() returning [{"id": ...}] we need a separate stub
        # because the caller indexes [0]["id"]. We provide two helpers.

        thread_row = {"id": "thread_1", "user_id": TEST_USER_ID, "title": None}
        message_insert_rows = [{"id": "msg_assistant_1"}]

        # Primary stub — returns the thread row for single-record lookups
        # and an empty list otherwise (when chat.py indexes .data as a list).
        # The stub_db_chain helper's .execute() returns MagicMock(data=...), and
        # chat.py tolerates data being dict OR list for the relevant branches.
        primary = stub_db_chain(execute_return=thread_row)
        # For the insert path we need a chain whose execute returns a list
        insert_chain = stub_db_chain(execute_return=message_insert_rows)

        # Route select/update/delete through `primary`, insert through `insert_chain`.
        # We achieve this by making db.table() return a chain whose builder methods
        # all point back to `primary`, but whose .insert() method returns `insert_chain`.
        db = MagicMock()
        primary.insert = MagicMock(return_value=insert_chain)
        db.table = MagicMock(return_value=primary)

        with patch("routers.chat.get_supabase", return_value=db), \
             patch("routers.chat.stream_chat_completion", side_effect=_make_explore_tool_call_stream()), \
             patch("services.explorer_service.run_exploration", side_effect=lambda **kw: _fake_explorer_events()):
            with client_obj.stream("POST", "/api/threads/thread_1/messages",
                                   json={"content": "Summarize Catan"}) as r:
                return _collect_sse_lines(r)


    def test_sub_events_emitted():
        """EXPL-06: SSE stream contains type='sub_event' rows with parent_call_id."""
        with TestClient(app) as client_obj:
            events = _post_message_collect(client_obj)
        sub_events = [d for (e, d) in events if d.get("type") == "sub_event"]
        assert len(sub_events) >= 4, f"Expected >=4 sub_event rows, got {len(sub_events)}: {sub_events}"
        for se in sub_events:
            assert se["parent_call_id"] == "call_parent_1"
            assert se["subagent"] is True
            assert "sub_event" in se


    def test_final_tool_result():
        """EXPL-06: tool_result event for explore_kb carries an ExplorerResult JSON dict."""
        with TestClient(app) as client_obj:
            events = _post_message_collect(client_obj)
        explore_results = [d for (e, d) in events
                           if d.get("type") == "tool_result" and d.get("tool") == "explore_kb"]
        assert len(explore_results) == 1
        output_str = explore_results[0]["output"]
        # output is a JSON string wrapping {"tool": "explore_kb", ...ExplorerResult fields...}
        parsed = json.loads(output_str)
        assert parsed["tool"] == "explore_kb"
        assert parsed["mode"] == "summarize"
        assert parsed["synthesis"]
        assert isinstance(parsed["findings"], list)


    def test_parent_call_id_links_subevents():
        """Every sub_event's parent_call_id matches the preceding parent tool_start call_id."""
        with TestClient(app) as client_obj:
            events = _post_message_collect(client_obj)
        parent_starts = [d for (e, d) in events
                         if d.get("type") == "tool_start" and d.get("tool") == "explore_kb"]
        assert len(parent_starts) == 1
        parent_id = parent_starts[0]["call_id"]
        sub_events = [d for (e, d) in events if d.get("type") == "sub_event"]
        assert sub_events
        assert all(se["parent_call_id"] == parent_id for se in sub_events)
    ```
  </action>
  <acceptance_criteria>
    - `cd backend && venv/Scripts/python -m pytest tests/test_explorer_integration.py -q` exits 0
    - `grep -c "@pytest.mark.skip" backend/tests/test_explorer_integration.py` returns 0
    - `grep -n "from tests.fixtures.explorer_fixtures import .* stub_db_chain" backend/tests/test_explorer_integration.py` returns a match (consumes shared helper, W1 fix)
    - `grep -c "db.table.return_value.select.return_value" backend/tests/test_explorer_integration.py` returns 0 (no hand-rolled chain mocks)
    - `grep -n "test_sub_events_emitted" backend/tests/test_explorer_integration.py` returns a match
    - `grep -n "test_final_tool_result" backend/tests/test_explorer_integration.py` returns a match
    - `grep -n "test_parent_call_id_links_subevents" backend/tests/test_explorer_integration.py` returns a match
  </acceptance_criteria>
  <verify>
    <automated>cd backend && venv/Scripts/python -m pytest tests/test_explorer_integration.py -q</automated>
  </verify>
  <done>
    SSE integration tests prove the streaming dispatcher emits well-formed sub_event rows linked to the parent tool_start; ExplorerResult JSON reaches the parent agent intact; DB mocking uses the shared stub_db_chain helper so the tests survive internal chat.py chain-reorderings.
  </done>
</task>

</tasks>

<verification>
- `cd backend && venv/Scripts/python -m pytest tests/test_explorer_service.py tests/test_explorer_tools.py tests/test_explorer_integration.py -q` all green
- Existing tests don't regress: `cd backend && venv/Scripts/python -m pytest tests/ -q --ignore=tests/test_e2e_subagent.py` exits 0
- explore_kb appears in the parent's tools list
- TOOL_SELECTION_GUIDE has Deep exploration section
- Pitfall 3 mitigated via asyncio.to_thread + queue (sync generator does not block the async event loop)
- Integration tests consume the shared `stub_db_chain` helper from Plan 01 (no ad-hoc chain mocks)
</verification>

<success_criteria>
- Phase success criteria #1 (multi-step KB lookups handled autonomously) MET via explore_kb tool
- Phase success criteria #2 (folder summary) MET via mode='summarize'
- Phase success criteria #3 (similar games with reasoning) MET via mode='find_similar' returning findings with `relevance` strings
- Phase success criteria #4 (progress streamed) backend portion MET — frontend wiring is Plan 04
- EXPL-01..EXPL-04, EXPL-06 fully exercised by automated tests
</success_criteria>

<output>
After completion, create `.planning/phases/05-explorer-sub-agent/05-03-SUMMARY.md` documenting:
- Final EXPLORE_KB_TOOL schema
- The exact SSE row shapes the frontend (Plan 04) must parse: tool_start, sub_event (with sub_event.type values), tool_result
- The asyncio.to_thread + queue pattern used (and why) — note for future maintainers
- TOOL_SELECTION_GUIDE diff
- Test coverage matrix updated for EXPL-01..EXPL-04, EXPL-06
- Notes on `stub_db_chain` usage in integration tests — future test authors should reuse it rather than hand-roll mocks
</output>
</output>
