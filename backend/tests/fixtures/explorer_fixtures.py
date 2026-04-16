"""Shared fixtures for explorer tests.

Provides:
  - make_tool_call(name, args, call_id): build OpenAI-compatible tool_call dict
  - mock_llm_client(scenarios): returns a MagicMock standing in for OpenAI client
    whose chat.completions.create() returns scripted responses one per call
  - EXPLORER_SCENARIOS: dict[str, list[dict]] of scripted multi-turn sequences
  - stub_db_chain(execute_return): recursively chainable MagicMock for Supabase
    query chains -- consumed by Plan 03 integration tests
"""
import json
from unittest.mock import MagicMock

TEST_USER_ID = "11111111-1111-1111-1111-111111111111"
BOARD_GAMES_ROOT_ID = "a0000000-0000-0000-0000-000000000001"


def make_tool_call(name: str, args: dict, call_id: str = "call_test"):
    """Build a tool_call object shaped like an OpenAI ChatCompletionMessageToolCall."""
    tc = MagicMock()
    tc.id = call_id
    tc.type = "function"
    tc.function = MagicMock()
    tc.function.name = name
    tc.function.arguments = json.dumps(args)
    tc.model_dump = lambda: {
        "id": call_id,
        "type": "function",
        "function": {"name": name, "arguments": json.dumps(args)},
    }
    return tc


def make_response(tool_calls=None, content=None, finish_reason=None):
    """Build a chat.completions.create() response."""
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message = MagicMock()
    response.choices[0].message.tool_calls = tool_calls
    response.choices[0].message.content = content
    response.choices[0].finish_reason = finish_reason or ("tool_calls" if tool_calls else "stop")
    response.usage = MagicMock(prompt_tokens=100, completion_tokens=50)
    return response


def mock_llm_client(scripted_responses: list):
    """Return a MagicMock client whose chat.completions.create yields scripted_responses in order."""
    client = MagicMock()
    client.chat.completions.create = MagicMock(side_effect=scripted_responses)
    return client


def stub_db_chain(execute_return=None):
    """Return a Supabase-style query-chain MagicMock.

    Every chain-builder attribute access (select/eq/in_/insert/update/delete/...)
    returns the same mock, so order-of-operations in production code doesn't
    matter. Only `.execute()` is meaningful; it returns a MagicMock whose
    `.data` attribute is `execute_return` (or None).

    Consumed by Plan 03 integration tests which need to patch
    `routers.chat.get_supabase` without binding the test to the router's
    exact chain ordering.

    Usage:
      db = stub_db_chain(execute_return={"id": "thread_1"})
      # db.table("x").select("*").eq("id", "1").maybe_single().execute().data
      # == {"id": "thread_1"}
    """
    m = MagicMock()

    def _chain(*_a, **_kw):
        return m

    for attr in (
        "table", "select", "insert", "update", "delete",
        "eq", "neq", "in_", "is_", "or_", "and_",
        "order", "limit", "single", "maybe_single", "range",
        "ilike", "like", "contains", "filter",
    ):
        setattr(m, attr, _chain)

    exec_result = MagicMock()
    exec_result.data = execute_return
    m.execute = MagicMock(return_value=exec_result)
    return m


# ----- Scripted scenarios -----

EXPLORER_SCENARIOS = {
    "summarize_catan": [
        # Turn 1: model calls kb_tree
        make_response(tool_calls=[make_tool_call("kb_tree", {"path": "Board Games/Catan", "depth": 2}, "call_1")]),
        # Turn 2: model calls kb_read
        make_response(tool_calls=[make_tool_call("kb_read", {"path": "Board Games/Catan/rules.md"}, "call_2")]),
        # Turn 3: model returns final structured JSON
        make_response(content=json.dumps({
            "mode": "summarize",
            "query": "Summarize Catan",
            "findings": [
                {"title": "Catan rules overview", "path": "Board Games/Catan/rules.md",
                 "excerpt": "Players collect resources...", "relevance": "Core mechanics"}
            ],
            "synthesis": "Catan is a resource-trading game where 3-4 players compete...",
            "tools_used": [],
            "iterations": 0,
            "budget_exhausted": False,
        })),
    ],
    "find_similar_azul": [
        make_response(tool_calls=[make_tool_call("kb_grep", {"pattern": "tile placement", "mode": "keyword"}, "call_a")]),
        make_response(tool_calls=[make_tool_call("kb_ls", {"path": "Board Games"}, "call_b")]),
        make_response(content=json.dumps({
            "mode": "find_similar",
            "query": "Games like Azul",
            "findings": [
                {"title": "Sagrada", "path": "Board Games/Sagrada/rules.md",
                 "excerpt": "Dice drafting and pattern building", "relevance": "Pattern building like Azul"},
                {"title": "Calico", "path": "Board Games/Calico/rules.md",
                 "excerpt": "Quilt-tile placement", "relevance": "Tile placement like Azul"},
            ],
            "synthesis": "Sagrada and Calico share Azul's pattern-building/tile-placement core.",
            "tools_used": [],
            "iterations": 0,
            "budget_exhausted": False,
        })),
    ],
    "budget_exhaustion_loop": [
        # Always returns a tool_call, never stops voluntarily -- used to test iteration cap
        *[make_response(tool_calls=[make_tool_call("kb_ls", {"path": "Board Games"}, f"call_{i}")]) for i in range(20)],
    ],
}
