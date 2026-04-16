"""Integration tests: parent chat -> explorer tool call -> SSE sub_event stream.

Wave 0 scaffold. Plan 03 will wire `explore_kb` into the parent chat router and
Plan 04 will surface the events client-side; both produce the artifacts these
tests assert against.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import pytest

pytestmark = pytest.mark.integration


@pytest.mark.skip(reason="explore_kb wired into parent loop in Plan 03")
def test_explore_kb_tool_registered():
    """Parent chat advertises EXPLORE_KB_TOOL in its tools list."""
    pass


@pytest.mark.skip(reason="explore_kb wired into parent loop in Plan 03")
def test_sub_events_emitted():
    """EXPL-06: event_generator emits SSE 'tool_event' rows with type='sub_event'."""
    pass


@pytest.mark.skip(reason="explore_kb wired into parent loop in Plan 03")
def test_final_tool_result():
    """EXPL-06: terminating tool_result event contains ExplorerResult JSON."""
    pass


@pytest.mark.skip(reason="explore_kb wired into parent loop in Plan 03")
def test_parent_call_id_links_subevents():
    """EXPL-06: every sub_event payload includes parent_call_id matching the parent tool_start."""
    pass
