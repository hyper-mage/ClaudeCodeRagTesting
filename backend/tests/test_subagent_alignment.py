"""Tests that run_document_analysis emits SSE sub_events matching the
explore_kb contract so the frontend ToolCallCard renders both sub-agents
consistently (Phase 6, D-10/D-11/D-12).
"""
from unittest.mock import MagicMock, patch

import pytest

from services import subagent_service
from services.subagent_service import run_document_analysis


ALLOWED_TYPES = {"sub_iteration", "sub_tool_start", "sub_tool_result", "result"}


@pytest.fixture
def mock_doc():
    return {"id": "doc-1", "filename": "test.md", "status": "completed"}


@pytest.fixture
def mock_llm_analysis():
    """Patch the OpenAI client used inside run_document_analysis to return a
    predictable analysis response. Returns the created MagicMock."""
    with patch.object(subagent_service, "get_llm_client") as gc:
        client = MagicMock()
        msg = MagicMock()
        msg.content = "Analysis result."
        choice = MagicMock()
        choice.message = msg
        response = MagicMock()
        response.choices = [choice]
        client.chat.completions.create.return_value = response
        gc.return_value = client
        yield client


@pytest.fixture
def happy_path(mock_doc, mock_llm_analysis):
    """Patch resolve_document and get_full_document_text for a successful run."""
    with patch.object(subagent_service, "resolve_document", return_value=mock_doc), \
         patch.object(
             subagent_service,
             "get_full_document_text",
             return_value="hello\n\nworld",
         ):
        yield


class TestSubagentAlignment:
    def test_yields_sub_iteration_events(self, happy_path):
        events = list(run_document_analysis("u", "test.md", "summarize"))
        sub_iterations = [e for e in events if e["type"] == "sub_iteration"]
        assert len(sub_iterations) >= 1
        assert sub_iterations[0]["iteration"] == 1
        assert "description" in sub_iterations[0]

    def test_yields_sub_tool_start_and_result(self, happy_path):
        events = list(run_document_analysis("u", "test.md", "summarize"))
        starts = [e for e in events if e["type"] == "sub_tool_start"]
        results = [e for e in events if e["type"] == "sub_tool_result"]
        assert len(starts) >= 1
        assert len(results) >= 1
        assert starts[0]["tool"] == "read_document"
        assert results[0]["tool"] == "read_document"

    def test_final_event_is_result(self, happy_path):
        events = list(run_document_analysis("u", "test.md", "summarize"))
        assert events[-1]["type"] == "result"
        payload = events[-1]["result"]
        assert "document" in payload
        assert payload["document"] == "test.md"
        assert "analysis" in payload

    def test_not_found_yields_error_result(self, mock_llm_analysis):
        with patch.object(subagent_service, "resolve_document", return_value=None):
            events = list(run_document_analysis("u", "missing.md", "summarize"))
        assert events[-1]["type"] == "result"
        assert "error" in events[-1]["result"]
        # No tool_start/tool_result when the document doesn't resolve.
        assert not any(e["type"] == "sub_tool_start" for e in events)

    def test_multiple_matches_yields_error_with_matches(self, mock_llm_analysis):
        ambiguous = {"multiple": True, "matches": ["a.md", "b.md"]}
        with patch.object(subagent_service, "resolve_document", return_value=ambiguous):
            events = list(run_document_analysis("u", "a", "summarize"))
        assert events[-1]["type"] == "result"
        assert "error" in events[-1]["result"]
        assert events[-1]["result"]["matches"] == ["a.md", "b.md"]

    def test_event_types_match_explorer_contract(self, happy_path):
        events = list(run_document_analysis("u", "test.md", "summarize"))
        for e in events:
            assert e["type"] in ALLOWED_TYPES, f"unexpected event type: {e['type']}"

    def test_timeout_yields_error_result(self, mock_doc):
        import openai

        with patch.object(subagent_service, "resolve_document", return_value=mock_doc), \
             patch.object(
                 subagent_service,
                 "get_full_document_text",
                 return_value="hello",
             ), \
             patch.object(subagent_service, "get_llm_client") as gc:
            client = MagicMock()
            client.chat.completions.create.side_effect = openai.APITimeoutError(
                "timed out"
            )
            gc.return_value = client
            events = list(run_document_analysis("u", "test.md", "summarize"))

        assert events[-1]["type"] == "result"
        assert "error" in events[-1]["result"]
        assert "timed out" in events[-1]["result"]["error"].lower()
