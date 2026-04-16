"""Unit tests for explorer_service.run_exploration().

Wave 0 scaffolding: contract tests for ExplorerResult run NOW.
Behavior tests are marked skip until Plan 02 implements run_exploration().
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from unittest.mock import patch, MagicMock
from pydantic import ValidationError

from models.schemas import ExplorerResult, ExplorerFinding
from tests.fixtures.explorer_fixtures import (
    TEST_USER_ID, EXPLORER_SCENARIOS, mock_llm_client,
)


# ----- Contract tests (run NOW -- verifies Task 1) -----

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


# ----- Behavior tests (Plan 02 implementation gates these) -----

@pytest.mark.skip(reason="Explorer service implemented in Plan 02")
def test_multi_step_loop():
    """EXPL-01: Explorer completes a multi-step traversal using KB tools."""
    pass


@pytest.mark.skip(reason="Explorer service implemented in Plan 02")
def test_tool_dispatch():
    """EXPL-01: Explorer dispatches kb_tree, kb_ls, kb_read, kb_grep, kb_glob correctly."""
    pass


@pytest.mark.skip(reason="Explorer service implemented in Plan 02")
def test_summarize_mode():
    """EXPL-02: mode='summarize' produces ExplorerResult with non-empty synthesis."""
    pass


@pytest.mark.skip(reason="Explorer modes wired in Plan 03")
def test_find_similar_mode():
    """EXPL-03: mode='find_similar' assembles findings across multiple games."""
    pass


@pytest.mark.skip(reason="Explorer modes wired in Plan 03")
def test_recommendation_seed():
    """EXPL-04: Explorer accepts conversation-derived seed query."""
    pass


@pytest.mark.skip(reason="Explorer service implemented in Plan 02")
def test_iteration_budget():
    """EXPL-05: Budget exhaustion on max_iterations sets budget_exhausted=True."""
    pass


@pytest.mark.skip(reason="Explorer service implemented in Plan 02")
def test_tool_call_budget():
    """EXPL-05: Budget exhaustion on max_tool_calls sets budget_exhausted=True."""
    pass


def test_output_size_cap():
    """EXPL-05: ExplorerResult rejects oversized synthesis (already covered above; alias)."""
    with pytest.raises(ValidationError):
        ExplorerResult(mode="summarize", query="q", synthesis="x" * 5000)


@pytest.mark.skip(reason="Explorer service implemented in Plan 02")
def test_rls_isolation():
    """All EXPL: Explorer respects RLS -- user A cannot see user B's private docs."""
    pass
