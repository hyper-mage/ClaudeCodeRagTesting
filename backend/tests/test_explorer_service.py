"""Unit tests for explorer_service.run_exploration().

Wave 0 scaffolding: contract tests for ExplorerResult run NOW.
Plan 02 has un-skipped behavior tests (multi-step loop, tool dispatch, budget).
Plan 03 still owns find_similar_mode and recommendation_seed.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import json
import pytest
from unittest.mock import patch, MagicMock
from pydantic import ValidationError

from models.schemas import ExplorerResult, ExplorerFinding
from tests.fixtures.explorer_fixtures import (
    TEST_USER_ID, EXPLORER_SCENARIOS, mock_llm_client, make_response, make_tool_call,
)


def _make_fake_settings(**overrides):
    """Build a MagicMock matching every Settings field explorer_service reads.

    Override only what the test cares about; defaults mirror production.
    Keep this list in sync with backend/config.py whenever new explorer_* or
    llm_* fields are added.

    Patches `services.explorer_service.get_settings` directly (not env-vars +
    cache_clear) because the Settings class does not declare explicit env
    aliases -- pydantic-settings auto-mapping isn't guaranteed to round-trip
    the explorer_* fields, which would silently fall back to defaults and
    produce false-positive passes for the budget tests.
    """
    from config import get_settings as _real_get_settings
    real = _real_get_settings()
    fake = MagicMock()
    fake.explorer_max_iterations = overrides.get("explorer_max_iterations", 6)
    fake.explorer_max_tool_calls = overrides.get("explorer_max_tool_calls", 10)
    fake.explorer_max_summary_chars = overrides.get("explorer_max_summary_chars", 3000)
    fake.explorer_timeout = overrides.get("explorer_timeout", 120)
    fake.explorer_system_prompt = overrides.get(
        "explorer_system_prompt", real.explorer_system_prompt
    )
    fake.llm_model = overrides.get("llm_model", real.llm_model or "gpt-4o-mini")
    return fake


# ----- Contract tests (run NOW -- verifies Plan 01 work) -----

def test_explorer_result_rejects_oversized_synthesis():
    """EXPL-05: Pydantic enforces synthesis length cap."""
    with pytest.raises(ValidationError):
        ExplorerResult(mode="summarize", query="q", synthesis="x" * 2001)


def test_explorer_result_rejects_too_many_findings():
    """EXPL-05: Pydantic enforces findings count cap."""
    findings = [ExplorerFinding(title="t", excerpt="e", relevance="r") for _ in range(9)]
    with pytest.raises(ValidationError):
        ExplorerResult(mode="summarize", query="q", findings=findings, synthesis="ok")


def test_explorer_finding_rejects_oversized_excerpt():
    with pytest.raises(ValidationError):
        ExplorerFinding(title="t", excerpt="x" * 501, relevance="r")


def test_explorer_result_mode_pattern():
    """Only the three documented modes are accepted."""
    ExplorerResult(mode="deep_search", query="q", synthesis="s")
    ExplorerResult(mode="summarize", query="q", synthesis="s")
    ExplorerResult(mode="find_similar", query="q", synthesis="s")
    with pytest.raises(ValidationError):
        ExplorerResult(mode="invalid_mode", query="q", synthesis="s")


def test_output_size_cap():
    """EXPL-05: ExplorerResult rejects oversized synthesis (already covered above; alias)."""
    with pytest.raises(ValidationError):
        ExplorerResult(mode="summarize", query="q", synthesis="x" * 5000)


# ----- Behavior tests (Plan 02 implementation) -----

def test_multi_step_loop():
    """EXPL-01: Explorer drives a multi-turn tool loop and emits a final result."""
    from services import explorer_service
    client = mock_llm_client(EXPLORER_SCENARIOS["summarize_catan"])
    with patch.object(explorer_service, "get_llm_client", return_value=client), \
         patch.object(explorer_service, "kb_tree", return_value="Catan/\n  rules.md"), \
         patch.object(explorer_service, "kb_read", return_value="Players collect resources..."):
        from services.explorer_service import run_exploration
        events = list(run_exploration(TEST_USER_ID, "Summarize Catan", "summarize"))
    tool_starts = [e for e in events if e["type"] == "sub_tool_start"]
    tool_results = [e for e in events if e["type"] == "sub_tool_result"]
    result_events = [e for e in events if e["type"] == "result"]
    assert len(tool_starts) >= 2, f"Expected >=2 tool starts, got {len(tool_starts)}"
    assert len(tool_results) >= 2
    assert len(result_events) == 1
    assert result_events[0]["result"]["synthesis"]


def test_tool_dispatch():
    """EXPL-01: All 5 KB tools dispatched to kb_tools_service.* functions."""
    from services import explorer_service
    with patch.object(explorer_service, "kb_ls", return_value="LS_OUT") as ml, \
         patch.object(explorer_service, "kb_tree", return_value="TREE_OUT") as mt, \
         patch.object(explorer_service, "kb_read", return_value="READ_OUT"), \
         patch.object(explorer_service, "kb_grep", return_value="GREP_OUT"), \
         patch.object(explorer_service, "kb_glob", return_value="GLOB_OUT"):
        for fn_name, fn_args, expected in [
            ("kb_ls",   {"path": "/x"},                    "LS_OUT"),
            ("kb_tree", {"path": "/x", "depth": 2},        "TREE_OUT"),
            ("kb_read", {"path": "/x.md"},                 "READ_OUT"),
            ("kb_grep", {"pattern": "p", "mode": "keyword"}, "GREP_OUT"),
            ("kb_glob", {"pattern": "*.md"},               "GLOB_OUT"),
        ]:
            out_json = explorer_service._execute_explorer_tool(fn_name, fn_args, TEST_USER_ID)
            parsed = json.loads(out_json) if isinstance(out_json, str) else out_json
            assert parsed["tool"] == fn_name
            assert parsed["output"] == expected
    ml.assert_called_with(TEST_USER_ID, "/x")
    mt.assert_called_with(TEST_USER_ID, "/x", 2)


def test_summarize_mode():
    """EXPL-02: mode='summarize' returns ExplorerResult with non-empty synthesis."""
    from services import explorer_service
    client = mock_llm_client(EXPLORER_SCENARIOS["summarize_catan"])
    with patch.object(explorer_service, "get_llm_client", return_value=client), \
         patch.object(explorer_service, "kb_tree", return_value="x"), \
         patch.object(explorer_service, "kb_read", return_value="y"):
        events = list(explorer_service.run_exploration(TEST_USER_ID, "Summarize Catan", "summarize"))
    result = events[-1]["result"]
    assert result["mode"] == "summarize"
    assert result["synthesis"]


def test_find_similar_mode():
    """EXPL-03: mode='find_similar' assembles >=2 findings across multiple games."""
    from services import explorer_service
    # The scenario has 3 responses (2 tool-call turns + 1 voluntary stop).
    # _summarize_findings makes an additional call, so we append the summary
    # response (same JSON the voluntary-stop turn carried) as a 4th item.
    summary_json = json.dumps({
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
    })
    scenario = EXPLORER_SCENARIOS["find_similar_azul"] + [make_response(content=summary_json)]
    client = mock_llm_client(scenario)
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


def test_iteration_budget():
    """EXPL-05: Hitting max_iterations sets budget_exhausted=True.

    NOTE: patches `services.explorer_service.get_settings` directly (not
    os.environ + cache_clear). The Settings class does not declare explicit
    env-var aliases, so relying on pydantic-settings auto-mapping here
    would silently fall back to defaults and produce a false-positive pass.
    """
    from services import explorer_service
    fake = _make_fake_settings(explorer_max_iterations=2)
    client = mock_llm_client(EXPLORER_SCENARIOS["budget_exhaustion_loop"])
    with patch.object(explorer_service, "get_settings", return_value=fake), \
         patch.object(explorer_service, "get_llm_client", return_value=client), \
         patch.object(explorer_service, "kb_ls", return_value="ok"):
        events = list(explorer_service.run_exploration(TEST_USER_ID, "test", "deep_search"))
    result = events[-1]["result"]
    iters = [e for e in events if e["type"] == "sub_iteration"]
    assert len(iters) == 2, f"Expected exactly 2 iterations, got {len(iters)}"
    assert result["budget_exhausted"] is True


def test_tool_call_budget():
    """EXPL-05: Hitting max_tool_calls sets budget_exhausted=True.

    Same patching rationale as test_iteration_budget -- patch
    `services.explorer_service.get_settings` directly.
    """
    from services import explorer_service
    fake = _make_fake_settings(explorer_max_tool_calls=1)
    # Iteration 1 returns 3 tool calls; only first should run
    three_calls = make_response(tool_calls=[
        make_tool_call("kb_ls", {"path": "a"}, "c1"),
        make_tool_call("kb_ls", {"path": "b"}, "c2"),
        make_tool_call("kb_ls", {"path": "c"}, "c3"),
    ])
    summary = make_response(content=json.dumps({
        "mode": "deep_search", "query": "q", "findings": [],
        "synthesis": "done", "tools_used": [], "iterations": 0, "budget_exhausted": False,
    }))
    client = mock_llm_client([three_calls, summary])
    with patch.object(explorer_service, "get_settings", return_value=fake), \
         patch.object(explorer_service, "get_llm_client", return_value=client), \
         patch.object(explorer_service, "kb_ls", return_value="ok"):
        events = list(explorer_service.run_exploration(TEST_USER_ID, "test", "deep_search"))
    tool_starts = [e for e in events if e["type"] == "sub_tool_start"]
    assert len(tool_starts) == 1, f"Expected exactly 1 tool start, got {len(tool_starts)}"
    assert events[-1]["result"]["budget_exhausted"] is True


def test_rls_isolation():
    """All EXPL: explorer forwards user_id verbatim to kb tools (no swap, no strip)."""
    from services import explorer_service
    seen = []
    def fake_ls(uid, path):
        seen.append(uid)
        return "ok"
    with patch.object(explorer_service, "kb_ls", side_effect=fake_ls):
        explorer_service._execute_explorer_tool("kb_ls", {"path": "/x"}, "user_a")
        explorer_service._execute_explorer_tool("kb_ls", {"path": "/x"}, "user_b")
    assert seen == ["user_a", "user_b"]
