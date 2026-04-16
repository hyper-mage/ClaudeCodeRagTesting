"""Unit tests for the explorer's KB tool dispatcher.

Wave 0 scaffold. Plan 02 will replace skip markers with real assertions.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import pytest


@pytest.mark.skip(reason="Explorer tool dispatcher implemented in Plan 02")
def test_dispatch_kb_ls():
    """EXPL-01: explorer dispatches kb_ls calls correctly."""
    pass


@pytest.mark.skip(reason="Explorer tool dispatcher implemented in Plan 02")
def test_dispatch_kb_tree():
    """EXPL-01: explorer dispatches kb_tree calls correctly."""
    pass


@pytest.mark.skip(reason="Explorer tool dispatcher implemented in Plan 02")
def test_dispatch_kb_read():
    """EXPL-01: explorer dispatches kb_read calls correctly."""
    pass


@pytest.mark.skip(reason="Explorer tool dispatcher implemented in Plan 02")
def test_dispatch_kb_grep():
    """EXPL-01: explorer dispatches kb_grep calls correctly."""
    pass


@pytest.mark.skip(reason="Explorer tool dispatcher implemented in Plan 02")
def test_dispatch_kb_glob():
    """EXPL-01: explorer dispatches kb_glob calls correctly."""
    pass


@pytest.mark.skip(reason="Tool error handling in Plan 02")
def test_tool_dispatch_unknown_returns_error_json():
    """Explorer returns JSON error for unknown tool name (no exception)."""
    pass
