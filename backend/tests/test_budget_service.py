"""Unit tests for budget_service.py (Phase 6 Plan 01).

Covers:
- count_tokens / count_message_tokens
- TokenBudget tracking + truncation
- infer_source_scope (D-01, D-02)
- parse_scope_hint (D-08, D-09)
- fetch_model_context_length (D-05)
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import json
import pytest
from unittest.mock import patch, MagicMock

from services.budget_service import (
    TokenBudget,
    count_tokens,
    count_message_tokens,
    fetch_model_context_length,
    infer_source_scope,
    parse_scope_hint,
)


# =========================
# count_tokens
# =========================
class TestCountTokens:
    def test_non_empty_string_returns_positive_int(self):
        result = count_tokens("hello world")
        assert isinstance(result, int)
        assert result > 0

    def test_empty_string_returns_zero(self):
        assert count_tokens("") == 0

    def test_longer_text_has_more_tokens(self):
        assert count_tokens("hello world this is a longer string") > count_tokens("hello")


# =========================
# count_message_tokens
# =========================
class TestCountMessageTokens:
    def test_single_message_includes_overhead(self):
        msg_tokens = count_message_tokens([{"role": "user", "content": "hello"}])
        content_only = count_tokens("hello")
        # 4 per-msg overhead + 2 priming => at least content + 6
        assert msg_tokens >= content_only + 6

    def test_empty_list_returns_two(self):
        # Only reply priming
        assert count_message_tokens([]) == 2

    def test_tool_calls_are_counted(self):
        tool_calls = [
            {
                "id": "call_1",
                "type": "function",
                "function": {"name": "search_documents", "arguments": '{"q": "x"}'},
            }
        ]
        with_tc = count_message_tokens(
            [{"role": "assistant", "content": "", "tool_calls": tool_calls}]
        )
        without_tc = count_message_tokens([{"role": "assistant", "content": ""}])
        assert with_tc > without_tc


# =========================
# TokenBudget
# =========================
class TestTokenBudget:
    def test_available_computation(self):
        b = TokenBudget(context_length=8000, response_reserve=2000, safety_margin=0.0, tool_schema_tokens=0)
        assert b.available == 6000

    def test_safety_margin_reduces_available(self):
        b = TokenBudget(context_length=10000, response_reserve=2000, safety_margin=0.05, tool_schema_tokens=0)
        # int(10000 * 0.95) - 2000 = 9500 - 2000 = 7500
        assert b.available == 7500

    def test_tool_schema_tokens_subtracted(self):
        b = TokenBudget(context_length=8000, response_reserve=2000, safety_margin=0.0, tool_schema_tokens=500)
        assert b.available == 5500

    def test_set_system_updates_used(self):
        b = TokenBudget(context_length=8000, response_reserve=2000, safety_margin=0.0, tool_schema_tokens=0)
        before = b.used
        b.set_system("this is the system prompt")
        assert b.used > before

    def test_set_history_counts_only_non_tool_messages(self):
        b = TokenBudget(context_length=8000, response_reserve=2000, safety_margin=0.0, tool_schema_tokens=0)
        messages = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi"},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "x", "arguments": "{}"}}],
            },
            {"role": "tool", "tool_call_id": "c1", "content": "res"},
        ]
        b.set_history(messages)
        # Only user + assistant(no tool_calls) counted
        plain_only = count_message_tokens(messages[:2])
        assert b._history_tokens == plain_only

    def test_add_tool_result_pair_updates_used(self):
        b = TokenBudget(context_length=8000, response_reserve=2000, safety_margin=0.0, tool_schema_tokens=0)
        assistant_msg = {
            "role": "assistant",
            "content": "",
            "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "kb_ls", "arguments": "{}"}}],
        }
        tool_msg = {"role": "tool", "tool_call_id": "c1", "content": "result data"}
        before = b.used
        b.add_tool_result_pair(assistant_msg, tool_msg)
        assert b.used > before
        assert len(b._tool_result_pairs) == 1

    def test_is_over_returns_true_when_used_exceeds_available(self):
        b = TokenBudget(context_length=100, response_reserve=10, safety_margin=0.0, tool_schema_tokens=0)
        b.set_system("x " * 500)  # will blow past 90
        assert b.is_over() is True

    def test_is_over_returns_false_when_within_budget(self):
        b = TokenBudget(context_length=100000, response_reserve=2000, safety_margin=0.0, tool_schema_tokens=0)
        b.set_system("short prompt")
        assert b.is_over() is False

    def test_truncate_oldest_tool_results_removes_fifo(self):
        b = TokenBudget(context_length=100000, response_reserve=2000, safety_margin=0.0, tool_schema_tokens=0)
        a1 = {"role": "assistant", "content": "", "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "kb_ls", "arguments": "{}"}}]}
        t1 = {"role": "tool", "tool_call_id": "c1", "content": "first result"}
        a2 = {"role": "assistant", "content": "", "tool_calls": [{"id": "c2", "type": "function", "function": {"name": "kb_read", "arguments": "{}"}}]}
        t2 = {"role": "tool", "tool_call_id": "c2", "content": "second result"}
        messages = [
            {"role": "user", "content": "hi"},
            a1, t1, a2, t2,
        ]
        b.add_tool_result_pair(a1, t1)
        b.add_tool_result_pair(a2, t2)
        assert len(b._tool_result_pairs) == 2

        new_messages = b.truncate_oldest_tool_results(messages)
        # a1 / t1 removed, a2 / t2 kept
        ids_remaining = [m.get("tool_call_id") for m in new_messages if m.get("role") == "tool"]
        assert "c1" not in ids_remaining
        assert "c2" in ids_remaining
        # assistant with c1 tool call must also be gone
        has_c1_assistant = any(
            m.get("role") == "assistant"
            and any(tc.get("id") == "c1" for tc in (m.get("tool_calls") or []))
            for m in new_messages
        )
        assert has_c1_assistant is False
        assert len(b._tool_result_pairs) == 1

    def test_truncate_does_not_remove_plain_history(self):
        b = TokenBudget(context_length=100000, response_reserve=2000, safety_margin=0.0, tool_schema_tokens=0)
        a1 = {"role": "assistant", "content": "", "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "kb_ls", "arguments": "{}"}}]}
        t1 = {"role": "tool", "tool_call_id": "c1", "content": "first result"}
        messages = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi"},
            a1, t1,
        ]
        b.add_tool_result_pair(a1, t1)
        new_messages = b.truncate_oldest_tool_results(messages)
        # user + plain assistant still present
        assert any(m.get("role") == "user" and m.get("content") == "hello" for m in new_messages)
        assert any(m.get("role") == "assistant" and m.get("content") == "hi" and "tool_calls" not in m for m in new_messages)

    def test_truncate_single_pair_brings_under_budget(self):
        b = TokenBudget(context_length=1000, response_reserve=100, safety_margin=0.0, tool_schema_tokens=0)
        # 900 available
        big_content = "x " * 1000
        a1 = {"role": "assistant", "content": "", "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "kb_read", "arguments": "{}"}}]}
        t1 = {"role": "tool", "tool_call_id": "c1", "content": big_content}
        messages = [{"role": "user", "content": "hi"}, a1, t1]
        b.set_system("short")
        b.set_history([{"role": "user", "content": "hi"}])
        b.add_tool_result_pair(a1, t1)
        assert b.is_over() is True
        b.truncate_oldest_tool_results(messages)
        assert b.is_over() is False


# =========================
# infer_source_scope
# =========================
class TestInferSourceScope:
    def test_game_query_with_private_docs_returns_both(self):
        assert infer_source_scope("What are the rules of Catan?", has_private_docs=True) == "both"

    def test_game_query_without_private_docs_returns_default_kb(self):
        assert infer_source_scope("What are the rules of Catan?", has_private_docs=False) == "default_kb"

    def test_uploaded_phrase_returns_private(self):
        assert infer_source_scope("Summarize my uploaded document", has_private_docs=True) == "private"

    def test_my_uploads_returns_private(self):
        assert infer_source_scope("my uploads about strategy", has_private_docs=True) == "private"

    def test_generic_board_game_question_default_kb_when_no_private(self):
        assert infer_source_scope("tell me about board games", has_private_docs=False) == "default_kb"

    def test_mixed_signals_returns_both(self):
        assert infer_source_scope("compare Catan with my notes", has_private_docs=True) == "both"


# =========================
# parse_scope_hint
# =========================
class TestParseScopeHint:
    def test_only_search_extracts_folder_hint(self):
        result = parse_scope_hint("only search Catan")
        assert result.get("folder_hint") == "Catan"

    def test_my_uploads_extracts_source_hint(self):
        result = parse_scope_hint("look in my uploads only")
        assert result.get("source_hint") == "private"

    def test_folder_path_pattern(self):
        result = parse_scope_hint("search Board Games/Catan/")
        assert "folder_hint" in result
        assert "Catan" in result["folder_hint"]

    def test_no_scope_hint_returns_empty(self):
        assert parse_scope_hint("what is a board game") == {}


# =========================
# fetch_model_context_length
# =========================
class TestFetchModelContextLength:
    def test_returns_context_length_from_api(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "data": [
                {"id": "anthropic/claude-3.5-sonnet", "context_length": 200000},
                {"id": "openai/gpt-4o", "context_length": 128000},
            ]
        }
        mock_resp.raise_for_status.return_value = None
        with patch("services.budget_service.httpx.get", return_value=mock_resp):
            result = fetch_model_context_length("openai/gpt-4o", "fake-key")
            assert result == 128000

    def test_returns_none_on_exception(self):
        with patch("services.budget_service.httpx.get", side_effect=Exception("boom")):
            assert fetch_model_context_length("openai/gpt-4o", "fake-key") is None

    def test_returns_none_when_model_not_found(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"data": [{"id": "other/model", "context_length": 1000}]}
        mock_resp.raise_for_status.return_value = None
        with patch("services.budget_service.httpx.get", return_value=mock_resp):
            assert fetch_model_context_length("openai/gpt-4o", "fake-key") is None
