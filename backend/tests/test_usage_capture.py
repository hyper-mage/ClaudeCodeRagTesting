"""Phase 11 Wave 0 scaffold — D-04 usage capture (drain + sum + persist).

Covers the token-usage capture path (built in plan 11-03/11-04):
  - The trailing `usage` event is captured (NOT discarded when the same response
    also carried tool_calls) and SUMMED across every iteration of the tool loop.
  - The summed usage is PERSISTED to the new additive `messages.usage` JSONB
    column on the `done` event.

test_usage_summed_across_tool_loop is un-skipped + implemented in plan 11-03 (it
asserts the drain-and-capture restructure in stream_chat_completion). The persist
half (test_usage_persisted_to_messages) stays a Wave 0 stub for plan 11-04.
Function names match the RESEARCH Test Map verbatim.
"""
from unittest.mock import MagicMock, patch

import pytest

from services import llm_service

_WAVE0 = "Wave 0 stub — turned green by plan 11-04"


def _delta_chunk(content=None, tool_calls=None, finish_reason=None):
    """A streaming chunk with one choice (text/tool_calls/finish)."""
    chunk = MagicMock()
    chunk.usage = None
    choice = MagicMock()
    choice.delta = MagicMock()
    choice.delta.content = content
    choice.delta.tool_calls = tool_calls
    choice.finish_reason = finish_reason
    chunk.choices = [choice]
    return chunk


def _usage_chunk(usage: dict):
    """A trailing usage-only chunk: choices == [] (skipped by `if not choice`)."""
    chunk = MagicMock()
    chunk.choices = []
    chunk.usage = usage
    return chunk


def _tool_call_delta(call_id="call_1", name="kb_ls", arguments="{}"):
    tc = MagicMock()
    tc.index = 0
    tc.id = call_id
    tc.function = MagicMock()
    tc.function.name = name
    tc.function.arguments = arguments
    return tc


def test_usage_summed_across_tool_loop():
    """D-04: a trailing usage event emitted alongside tool_calls is captured (not
    discarded) and summed across all tool-loop iterations.

    Here we assert the in-stream half: when a single streamed response carries a
    `finish_reason == "tool_calls"` chunk AND a trailing usage-only chunk, the
    early `return` is gone so the stream drains and a `{"type":"usage",...}` event
    is yielded BEFORE `{"type":"done"}` (the chat.py loop sums across iterations).
    """
    usage_payload = {
        "prompt_tokens": 120,
        "completion_tokens": 30,
        "total_tokens": 150,
        "cost": 0.0012,
    }
    stream_chunks = [
        _delta_chunk(tool_calls=[_tool_call_delta()]),
        _delta_chunk(finish_reason="tool_calls"),
        _usage_chunk(usage_payload),
    ]

    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = iter(stream_chunks)

    fake_settings = MagicMock()
    fake_settings.system_prompt = "sys"
    fake_settings.llm_model = "owner/model"

    with patch.object(llm_service, "get_llm_client", return_value=fake_client), \
         patch.object(llm_service, "get_settings", return_value=fake_settings):
        events = list(
            llm_service.stream_chat_completion(
                [{"role": "user", "content": "hi"}],
                tools=[{"type": "function", "function": {"name": "kb_ls"}}],
            )
        )

    types = [e["type"] for e in events]

    # The tool_call event still fires.
    assert "tool_call" in types

    # The trailing usage chunk was captured (the early `return` is gone).
    usage_events = [e for e in events if e["type"] == "usage"]
    assert len(usage_events) == 1, f"expected exactly one usage event, got {types}"
    assert usage_events[0]["usage"]["cost"] == pytest.approx(0.0012)
    assert usage_events[0]["usage"]["total_tokens"] == 150

    # Ordering: usage must come BEFORE done.
    assert "done" in types
    assert types.index("usage") < types.index("done")


@pytest.mark.skip(reason=_WAVE0)
def test_usage_persisted_to_messages():
    """D-04: the summed usage is persisted to the new messages.usage column on done."""
    raise NotImplementedError
