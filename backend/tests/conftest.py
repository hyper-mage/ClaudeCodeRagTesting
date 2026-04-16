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
