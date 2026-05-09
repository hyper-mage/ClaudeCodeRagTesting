"""Shared pytest fixtures for backend tests."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from tests.fixtures.explorer_fixtures import (
    TEST_USER_ID,
    BOARD_GAMES_ROOT_ID,
    make_tool_call,
    make_response,
    mock_llm_client,
    stub_db_chain,
    EXPLORER_SCENARIOS,
)

__all__ = [
    "TEST_USER_ID", "BOARD_GAMES_ROOT_ID",
    "make_tool_call", "make_response", "mock_llm_client",
    "stub_db_chain", "EXPLORER_SCENARIOS",
]


@pytest.fixture
def test_user_id():
    return TEST_USER_ID


@pytest.fixture
def explorer_scenarios():
    return EXPLORER_SCENARIOS


# ---------------------------------------------------------------------
# Phase 6 Wave 0 fixtures: rate limiting (SEC-04) + chat cap (SEC-05)
# ---------------------------------------------------------------------
from unittest.mock import MagicMock
from typing import Iterator


@pytest.fixture
def mock_user_id() -> str:
    """Stable user_id for slowapi key_func + chat cap-hit tests."""
    return "11111111-1111-1111-1111-111111111111"


@pytest.fixture
def mock_jwt(mock_user_id: str) -> str:
    """Opaque token string used in Authorization headers.

    Tests that need REAL JWT decoding should mock auth.get_user_id directly
    (e.g. via monkeypatch). This fixture is for tests that just need a
    non-empty Bearer string in the request.
    """
    return f"test-jwt-for-{mock_user_id}"


@pytest.fixture
def mock_request_with_user(mock_user_id: str):
    """A FastAPI Request mock with .state.user_id pre-populated.

    Used by SEC-04 tests of the slowapi key_func, which reads
    request.state.user_id WITHOUT going through the auth dependency.
    """
    req = MagicMock()
    req.state.user_id = mock_user_id
    return req


@pytest.fixture
def mock_request_no_user():
    """A FastAPI Request mock with no user_id set on .state.

    Used to verify the key_func fallback to 'anonymous' when auth dep
    has not yet populated request.state (e.g. during 401 path).
    """
    req = MagicMock()
    # Simulate 'attribute does not exist' via spec; getattr fallback path.
    del req.state.user_id  # MagicMock: removes the auto-attribute
    return req


@pytest.fixture
def mock_stream_chat_completion(monkeypatch):
    """Patch services.llm_service.stream_chat_completion with a programmable generator.

    CRITICAL for SEC-05 cap-hit test: must drive the OUTER while-loop in
    routers/chat.py:event_generator deterministically. Each call yields
    a configurable sequence of events. Default behavior: emit one tool_call
    event per invocation (forces tool_call_happened=True every iteration ->
    loop never voluntarily exits -> cap MUST trigger).

    Returns a controller object with:
      - .set_events(events_per_call: list[list[dict]]) - set per-call event list
      - .set_default_tool_call() - emits one tool_call event forever (cap-hit driver)
      - .call_count - number of times stream_chat_completion was invoked
    """
    controller = MagicMock()
    controller.call_count = 0
    controller._events_per_call: list[list[dict]] = []
    controller._default_tool_call_mode = False

    def _default_tool_call_event() -> list[dict]:
        return [
            {"type": "system_content", "content": "sys"},
            {
                "type": "tool_call",
                "tool_calls": [
                    {
                        "id": f"call_{controller.call_count}",
                        "type": "function",
                        "function": {"name": "kb_ls", "arguments": "{}"},
                    }
                ],
            },
        ]

    def _fake_stream_chat_completion(*args, **kwargs) -> Iterator[dict]:
        idx = controller.call_count
        controller.call_count += 1
        if controller._default_tool_call_mode:
            events = _default_tool_call_event()
        elif idx < len(controller._events_per_call):
            events = controller._events_per_call[idx]
        else:
            # Fallback: voluntary stop (no tool calls) -> outer loop breaks.
            events = [{"type": "text_delta", "text": "done"}]
        for ev in events:
            yield ev

    def _set_events(events_per_call: list[list[dict]]) -> None:
        controller._events_per_call = events_per_call
        controller._default_tool_call_mode = False

    def _set_default_tool_call() -> None:
        controller._default_tool_call_mode = True

    controller.set_events = _set_events
    controller.set_default_tool_call = _set_default_tool_call

    # Patch at the module that routers/chat.py imports FROM.
    # routers/chat.py does: `from services.llm_service import stream_chat_completion`
    # so we must patch the symbol IN routers.chat (the imported reference),
    # not at services.llm_service (which would be too late after import).
    monkeypatch.setattr(
        "routers.chat.stream_chat_completion",
        _fake_stream_chat_completion,
    )
    return controller


@pytest.fixture
def mock_langsmith_run(monkeypatch):
    """Patch langsmith.run_helpers.get_current_run_tree to return a recordable mock.

    SEC-05 LangSmith tag test asserts run.add_metadata({"iteration_cap_hit": True, ...})
    was called with the expected dict.
    """
    run = MagicMock()
    run.add_metadata = MagicMock()

    def _get_current_run_tree():
        return run

    try:
        monkeypatch.setattr(
            "langsmith.run_helpers.get_current_run_tree",
            _get_current_run_tree,
        )
    except (ImportError, AttributeError):
        # langsmith not importable in test env - fixture still exposes the mock
        # so test can xfail gracefully.
        pass
    return run
