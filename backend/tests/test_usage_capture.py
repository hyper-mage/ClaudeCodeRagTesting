"""Phase 11 Wave 0 scaffold — D-04 usage capture (drain + sum + persist).

Covers the token-usage capture path (built in plan 11-03/11-04):
  - The trailing `usage` event is captured (NOT discarded when the same response
    also carried tool_calls) and SUMMED across every iteration of the tool loop.
  - The summed usage is PERSISTED to the new additive `messages.usage` JSONB
    column on the `done` event.

Wave 0 STUBS: collected green now; un-skipped + implemented downstream. The
conftest `mock_stream_chat_completion` fixture is extended (this plan, Task 2) to
optionally emit a trailing `{"type":"usage","usage":{…}}` event so these tests can
drive it. Function names match the RESEARCH Test Map verbatim.
"""
import pytest

_WAVE0 = "Wave 0 stub — turned green by plan 11-03/11-04"


@pytest.mark.skip(reason=_WAVE0)
def test_usage_summed_across_tool_loop():
    """D-04: a trailing usage event emitted alongside tool_calls is captured (not
    discarded) and summed across all tool-loop iterations."""
    raise NotImplementedError


@pytest.mark.skip(reason=_WAVE0)
def test_usage_persisted_to_messages():
    """D-04: the summed usage is persisted to the new messages.usage column on done."""
    raise NotImplementedError
