"""Unit tests for the explorer's KB tool dispatcher.

Plan 02 implementation: replaces Wave 0 skip markers with real assertions.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import json
from unittest.mock import patch
from tests.fixtures.explorer_fixtures import TEST_USER_ID


def _dispatch(fn_name, fn_args, **patches):
    from services import explorer_service
    with patch.multiple(explorer_service, **patches):
        return explorer_service._execute_explorer_tool(fn_name, fn_args, TEST_USER_ID)


def test_dispatch_kb_ls():
    """EXPL-01: explorer dispatches kb_ls calls correctly."""
    out = _dispatch("kb_ls", {"path": "/p"}, kb_ls=lambda u, p: "LS_SENTINEL")
    assert json.loads(out) == {"tool": "kb_ls", "output": "LS_SENTINEL"}


def test_dispatch_kb_tree():
    """EXPL-01: explorer dispatches kb_tree calls correctly."""
    out = _dispatch("kb_tree", {"path": "/p", "depth": 3},
                    kb_tree=lambda u, p, d: f"TREE_{d}")
    assert json.loads(out)["output"] == "TREE_3"


def test_dispatch_kb_read():
    """EXPL-01: explorer dispatches kb_read calls correctly."""
    out = _dispatch("kb_read", {"path": "/p.md", "lines": "1-10"},
                    kb_read=lambda u, p, lines=None: f"READ_{lines}")
    assert json.loads(out)["output"] == "READ_1-10"


def test_dispatch_kb_grep():
    """EXPL-01: explorer dispatches kb_grep calls correctly."""
    out = _dispatch("kb_grep", {"pattern": "x", "mode": "regex", "path": "/p"},
                    kb_grep=lambda u, pattern, mode="keyword", path=None: f"GREP_{mode}_{path}")
    assert json.loads(out)["output"] == "GREP_regex_/p"


def test_dispatch_kb_glob():
    """EXPL-01: explorer dispatches kb_glob calls correctly."""
    out = _dispatch("kb_glob", {"pattern": "**/*.md"},
                    kb_glob=lambda u, pattern: f"GLOB_{pattern}")
    assert json.loads(out)["output"] == "GLOB_**/*.md"


def test_tool_dispatch_unknown_returns_error_json():
    """Explorer returns JSON error for unknown tool name (no exception)."""
    from services import explorer_service
    out = explorer_service._execute_explorer_tool("kb_bogus", {}, TEST_USER_ID)
    parsed = json.loads(out)
    assert "error" in parsed
    assert "Unknown tool" in parsed["error"]
