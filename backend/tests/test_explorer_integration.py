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


@pytest.fixture(autouse=True)
def _reset_sse_app_status():
    """Reset sse_starlette's AppStatus event between tests to avoid
    'bound to a different event loop' errors when TestClient creates
    fresh event loops per test."""
    import asyncio
    from sse_starlette.sse import AppStatus
    yield
    AppStatus.should_exit_event = asyncio.Event()


def _make_explore_tool_call_streams():
    """Return a side_effect list: first call yields tool_call, second yields text."""
    call_count = 0

    def _stream(messages, tools=None, tool_guide=None):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
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
        else:
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
    query-builder ordering. We route different table() calls to different
    stubs so each query path receives the correct .data shape.
    """
    thread_row = {"id": "thread_1", "user_id": TEST_USER_ID, "title": None}
    history_rows = [{"role": "user", "content": "Summarize Catan"}]
    assistant_insert_rows = [{"id": "msg_assistant_1"}]

    # Threads table: select -> thread_row dict (for maybe_single())
    threads_chain = stub_db_chain(execute_return=thread_row)

    # Messages table needs to handle multiple operations:
    #  - select (history query) -> list of message dicts
    #  - insert (user msg) -> doesn't matter
    #  - insert (assistant msg) -> [{"id": "..."}]
    #  - update (tool persistence, final content) -> doesn't matter
    messages_select_chain = stub_db_chain(execute_return=history_rows)
    messages_insert_chain = stub_db_chain(execute_return=assistant_insert_rows)
    messages_update_chain = stub_db_chain(execute_return=None)

    # Build messages chain that routes by operation
    messages_chain = MagicMock()
    messages_chain.select = MagicMock(return_value=messages_select_chain)
    messages_chain.insert = MagicMock(return_value=messages_insert_chain)
    messages_chain.update = MagicMock(return_value=messages_update_chain)

    # Documents table: select -> empty list (no completed docs)
    docs_chain = stub_db_chain(execute_return=[])

    def _table(name):
        if name == "threads":
            return threads_chain
        if name == "documents":
            return docs_chain
        return messages_chain

    db = MagicMock()
    db.table = MagicMock(side_effect=_table)

    with patch("routers.chat.get_supabase", return_value=db), \
         patch("routers.chat.stream_chat_completion", side_effect=_make_explore_tool_call_streams()), \
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
