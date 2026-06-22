"""Phase 11 Wave 0 scaffold — DEMO-03 + SEC-04 + D-03 per-request key/model resolution.

Covers the `_resolve_key_and_model` seam (built in plan 11-04):
  - DEMO-03: keyless user fail-closed (flag OFF) vs owner-key + `:free` demo (flag ON)
  - SEC-04: decrypted user key threaded to all call sites; no cross-user bleed;
            fail-closed shape (never `user_key or owner_key`)
  - D-03:   model fall-through to owner default when thread/user_preferences absent

Every function below is a Wave 0 STUB: created + collected green now, un-skipped and
implemented by plan 11-04. Function names MUST match the RESEARCH Test Map verbatim
so plan 11-04's `<verify>` commands resolve.

Config-touching tests (when un-skipped) MUST follow each `monkeypatch.setenv(...)`
on a cached settings field with `get_settings.cache_clear()` (mirror
test_crypto_service.py:11-20) — get_settings() is @lru_cache'd.
"""
from unittest.mock import MagicMock, patch

import pytest

_WAVE0 = "Wave 0 stub — turned green by plan 11-04"

# A resolved per-user turn: the DECRYPTED user key + the resolved model. The owner
# key/model must NOT appear at any aux call site when these are supplied (D-01/SEC-04).
_USER_KEY = "sk-or-v1-USERKEY"
_RESOLVED_MODEL = "anthropic/claude-3.5-sonnet"


@pytest.mark.skip(reason=_WAVE0)
def test_no_key_flag_off_refuses():
    """DEMO-03: keyless user + demo_fallback_enabled=False → mode=='no_key',
    api_key is None; caller yields structured no_api_key SSE error, makes NO LLM call."""
    raise NotImplementedError


@pytest.mark.skip(reason=_WAVE0)
def test_demo_fallback_uses_free_model():
    """DEMO-03: keyless user + demo_fallback_enabled=True → owner key +
    settings.demo_fallback_model (:free slug), mode=='demo', is_user_key False."""
    raise NotImplementedError


def test_user_key_threaded_to_all_call_sites():
    """SEC-04 / D-01: a user-with-key turn uses the DECRYPTED user key (not owner)
    at the aux call sites (rerank, subagent, explorer). Each builds its client via
    get_llm_client(api_key=<user key>, trace=False) and issues create(model=<resolved
    model>). The owner key/model is NOT used when a user key is supplied.

    The main-loop site (stream_chat_completion) is covered by test_langsmith_gate /
    test_usage_capture; this test pins the three aux sites that plan 11-03 threads.
    """
    from services import rerank_service, subagent_service, explorer_service

    # ---- rerank_with_llm ----------------------------------------------------
    rerank_client = MagicMock()
    rerank_resp = MagicMock()
    rerank_resp.choices = [MagicMock()]
    rerank_resp.choices[0].message.content = '{"score": 0.9}'
    rerank_client.chat.completions.create.return_value = rerank_resp

    fake_settings = MagicMock()
    fake_settings.llm_model = "owner/model"  # must NOT be used when model= is passed
    fake_settings.rerank_top_k = 5

    with patch.object(rerank_service, "get_llm_client", return_value=rerank_client) as rk_gc, \
         patch.object(rerank_service, "get_settings", return_value=fake_settings):
        rerank_service.rerank_with_llm(
            "query", [{"id": "c1", "content": "passage"}],
            api_key=_USER_KEY, model=_RESOLVED_MODEL, trace=False,
        )
    rk_gc.assert_called_once_with(api_key=_USER_KEY, trace=False)
    assert rerank_client.chat.completions.create.call_args.kwargs["model"] == _RESOLVED_MODEL

    # ---- run_document_analysis ----------------------------------------------
    subagent_client = MagicMock()
    sub_resp = MagicMock()
    sub_resp.choices = [MagicMock()]
    sub_resp.choices[0].message.content = "analysis"
    subagent_client.chat.completions.create.return_value = sub_resp

    sub_settings = MagicMock()
    sub_settings.llm_model = "owner/model"
    sub_settings.subagent_max_context_chars = 100000
    sub_settings.subagent_max_tokens = 1000
    sub_settings.subagent_timeout = 60
    sub_settings.subagent_system_prompt = "sys"

    with patch.object(subagent_service, "get_llm_client", return_value=subagent_client) as sa_gc, \
         patch.object(subagent_service, "get_settings", return_value=sub_settings), \
         patch.object(subagent_service, "resolve_document",
                      return_value={"id": "doc-1", "filename": "test.md", "status": "completed"}), \
         patch.object(subagent_service, "get_full_document_text", return_value="hello\n\nworld"):
        list(subagent_service.run_document_analysis(
            "u", "test.md", "summarize",
            api_key=_USER_KEY, model=_RESOLVED_MODEL, trace=False,
        ))
    sa_gc.assert_called_once_with(api_key=_USER_KEY, trace=False)
    assert subagent_client.chat.completions.create.call_args.kwargs["model"] == _RESOLVED_MODEL

    # ---- run_exploration (loop create + _summarize_findings._try) -----------
    explorer_client = MagicMock()

    def _make_response(tool_calls=None, content=None):
        resp = MagicMock()
        resp.choices = [MagicMock()]
        resp.choices[0].message.tool_calls = tool_calls
        resp.choices[0].message.content = content
        return resp

    # Turn 1: voluntary stop (no tool calls) -> straight to summary.
    # Then the summary tier-1 call returns a valid ExplorerResult JSON.
    import json as _json
    summary_json = _json.dumps({
        "mode": "deep_search", "query": "q",
        "findings": [], "synthesis": "done",
        "tools_used": [], "iterations": 0, "budget_exhausted": False,
    })
    explorer_client.chat.completions.create.side_effect = [
        _make_response(tool_calls=None, content="stopping"),  # loop iteration 1
        _make_response(content=summary_json),                  # _summarize_findings tier 1
    ]

    exp_settings = MagicMock()
    exp_settings.llm_model = "owner/model"
    exp_settings.explorer_max_iterations = 6
    exp_settings.explorer_max_tool_calls = 10
    exp_settings.explorer_max_summary_chars = 3000
    exp_settings.explorer_timeout = 120
    exp_settings.explorer_system_prompt = "sys"

    with patch.object(explorer_service, "get_llm_client", return_value=explorer_client) as ex_gc, \
         patch.object(explorer_service, "get_settings", return_value=exp_settings), \
         patch.object(explorer_service, "_explorer_tool_schemas", return_value=[]):
        list(explorer_service.run_exploration(
            "u", "q", mode="deep_search",
            api_key=_USER_KEY, model=_RESOLVED_MODEL, trace=False,
        ))
    ex_gc.assert_called_once_with(api_key=_USER_KEY, trace=False)
    # ALL explorer create() calls (loop + summary) must use the resolved model,
    # never the owner default (Pitfall 4 — three read sites).
    for call in explorer_client.chat.completions.create.call_args_list:
        assert call.kwargs["model"] == _RESOLVED_MODEL


@pytest.mark.skip(reason=_WAVE0)
def test_no_cross_user_bleed():
    """SEC-04: two concurrent resolutions for different users never cross
    key/model (per-request resolution is NOT cached — Pitfall 8)."""
    raise NotImplementedError


@pytest.mark.skip(reason=_WAVE0)
def test_fail_closed_no_or_fallback():
    """SEC-04: _resolve_key_and_model never returns `user_key or owner_key`
    (fail-closed shape — a missing user key does NOT silently fall back to owner)."""
    raise NotImplementedError


@pytest.mark.skip(reason=_WAVE0)
def test_model_fallthrough_absent_p13_schema():
    """D-03: model resolves to the owner default when thread.model /
    user_preferences are absent (no crash on the not-yet-present P13 schema)."""
    raise NotImplementedError
