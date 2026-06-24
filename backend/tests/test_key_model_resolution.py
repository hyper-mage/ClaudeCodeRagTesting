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
import inspect
from unittest.mock import MagicMock, patch

import pytest

_WAVE0 = "Wave 0 stub — turned green by plan 11-04"

# A resolved per-user turn: the DECRYPTED user key + the resolved model. The owner
# key/model must NOT appear at any aux call site when these are supplied (D-01/SEC-04).
_USER_KEY = "sk-or-v1-USERKEY"
_RESOLVED_MODEL = "anthropic/claude-3.5-sonnet"


def _fake_settings(**overrides):
    """Build a fake Settings-like object for _resolve_key_and_model.

    Defaults mirror a keyless owner-default config; override per test.
    """
    s = MagicMock()
    s.llm_model = "owner/default-model"
    s.resolved_llm_api_key = "sk-or-v1-OWNERKEY"
    s.demo_fallback_enabled = False
    s.demo_fallback_model = "meta-llama/llama-3.3-70b-instruct:free"
    for k, v in overrides.items():
        setattr(s, k, v)
    return s


def _db_with_key_row(encrypted_key: str | None, pref_model: str | None = None,
                     pref_raises: bool = False):
    """Build a fake supabase client for _resolve_key_and_model.

    - user_api_keys read returns a row (or none) carrying `encrypted_key`.
    - user_preferences read returns `pref_model` (or none), or raises when
      `pref_raises` is set (simulating the absent P13 table → Postgres 42P01).

    Each read is chained .table().select().eq().maybe_single().execute() → `.data`.
    """
    db = MagicMock()

    def _table(name: str):
        tbl = MagicMock()
        exec_result = MagicMock()
        if name == "user_api_keys":
            exec_result.data = (
                {"encrypted_key": encrypted_key} if encrypted_key else None
            )
            tbl.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = (
                exec_result
            )
        elif name == "user_preferences":
            if pref_raises:
                tbl.select.return_value.eq.return_value.maybe_single.return_value.execute.side_effect = (
                    RuntimeError('relation "user_preferences" does not exist (42P01)')
                )
            else:
                exec_result.data = (
                    {"default_model": pref_model} if pref_model else None
                )
                tbl.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = (
                    exec_result
                )
        else:
            exec_result.data = None
            tbl.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = (
                exec_result
            )
        return tbl

    db.table.side_effect = _table
    return db


def test_no_key_flag_off_refuses():
    """DEMO-03: keyless user + demo_fallback_enabled=False → mode=='no_key',
    api_key is None; caller yields structured no_api_key SSE error, makes NO LLM call."""
    from routers import chat

    db = _db_with_key_row(None)
    settings = _fake_settings(demo_fallback_enabled=False)
    body = MagicMock(spec=[])  # no .model attribute

    with patch.object(chat, "get_settings", return_value=settings):
        api_key, model, mode, is_user_key = chat._resolve_key_and_model(
            db, "user-1", {"id": "t1"}, body
        )

    assert api_key is None
    assert mode == "no_key"
    assert is_user_key is False
    assert model == "owner/default-model"  # still resolves a model for the error context


def test_demo_fallback_uses_free_model():
    """DEMO-03: keyless user + demo_fallback_enabled=True → owner key +
    settings.demo_fallback_model (:free slug), mode=='demo', is_user_key False."""
    from routers import chat

    db = _db_with_key_row(None)
    settings = _fake_settings(
        demo_fallback_enabled=True,
        demo_fallback_model="meta-llama/llama-3.3-70b-instruct:free",
    )
    body = MagicMock(spec=[])

    with patch.object(chat, "get_settings", return_value=settings):
        api_key, model, mode, is_user_key = chat._resolve_key_and_model(
            db, "user-1", {"id": "t1"}, body
        )

    assert api_key == "sk-or-v1-OWNERKEY"
    assert model == "meta-llama/llama-3.3-70b-instruct:free"
    assert model.endswith(":free")
    assert mode == "demo"
    assert is_user_key is False


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


def test_no_cross_user_bleed():
    """SEC-04: two concurrent resolutions for different users never cross
    key/model (per-request resolution is NOT cached — Pitfall 8)."""
    from routers import chat

    settings = _fake_settings()
    body = MagicMock(spec=[])

    # Each user has a DISTINCT stored (encrypted) key. decrypt_key is the identity
    # transform here so the decrypted value == the stored ciphertext per user.
    db_a = _db_with_key_row("sk-or-v1-CIPHER-A")
    db_b = _db_with_key_row("sk-or-v1-CIPHER-B")

    with patch.object(chat, "get_settings", return_value=settings), \
         patch.object(chat, "decrypt_key", side_effect=lambda c: c.replace("CIPHER", "PLAIN")):
        key_a, model_a, mode_a, is_user_a = chat._resolve_key_and_model(
            db_a, "user-A", {"id": "tA"}, body
        )
        key_b, model_b, mode_b, is_user_b = chat._resolve_key_and_model(
            db_b, "user-B", {"id": "tB"}, body
        )

    assert key_a == "sk-or-v1-PLAIN-A"
    assert key_b == "sk-or-v1-PLAIN-B"
    assert key_a != key_b  # no shared/cached state across calls
    assert mode_a == mode_b == "user"
    assert is_user_a is is_user_b is True


def test_fail_closed_no_or_fallback():
    """SEC-04: _resolve_key_and_model never returns `user_key or owner_key`
    (fail-closed shape — a missing user key does NOT silently fall back to owner)."""
    from routers import chat

    # Static-source assertion: the helper body must NOT contain a fail-open
    # `user_key or owner_key`-style one-liner; the three branches are explicit.
    src = inspect.getsource(chat._resolve_key_and_model)
    src_no_comments = "\n".join(
        line for line in src.splitlines() if not line.lstrip().startswith("#")
    )
    assert "user_key or owner_key" not in src_no_comments
    assert "resolved_llm_api_key or" not in src_no_comments

    # Behavioral assertion: keyless + flag OFF must refuse, never return the owner key.
    db = _db_with_key_row(None)
    settings = _fake_settings(demo_fallback_enabled=False)
    body = MagicMock(spec=[])
    with patch.object(chat, "get_settings", return_value=settings):
        api_key, _model, mode, is_user_key = chat._resolve_key_and_model(
            db, "user-1", {"id": "t1"}, body
        )
    assert api_key is None and api_key != settings.resolved_llm_api_key
    assert mode == "no_key"
    assert is_user_key is False


def test_model_fallthrough_absent_p13_schema():
    """D-03: model resolves to the owner default when thread.model /
    user_preferences are absent (no crash on the not-yet-present P13 schema)."""
    from routers import chat

    settings = _fake_settings()
    body = MagicMock(spec=[])  # no body.model override
    # thread_row has NO "model" key (column absent pre-P13) and the
    # user_preferences query RAISES (table absent pre-P13 → 42P01).
    db = _db_with_key_row("sk-or-v1-CIPHER", pref_raises=True)

    with patch.object(chat, "get_settings", return_value=settings), \
         patch.object(chat, "decrypt_key", side_effect=lambda c: "sk-or-v1-PLAIN"):
        api_key, model, mode, is_user_key = chat._resolve_key_and_model(
            db, "user-1", {"id": "t1"}, body  # thread_row dict has no "model"
        )

    assert model == "owner/default-model"  # fell through to owner default, no crash
    assert api_key == "sk-or-v1-PLAIN"
    assert mode == "user"
    assert is_user_key is True


def test_thread_model_wins_when_set():
    """MODEL-06: once the P13 threads.model column exists, a thread_row carrying
    model="thread/pinned" resolves to that pin OVER the user_preferences default —
    proving no regression in the model tier order once the column is live.

    The thread_row is the already-fetched SELECT * row (D-03 / Pattern 2): reading
    its "model" key is an in-memory dict read, not a DB query. The user_preferences
    default is DIFFERENT and must lose to the thread pin.
    """
    from routers import chat

    settings = _fake_settings()
    body = MagicMock(spec=[])  # no per-message override
    # thread_row carries a live per-thread pin; user_preferences default differs.
    db = _db_with_key_row("sk-or-v1-CIPHER", pref_model="user/default-pref")

    with patch.object(chat, "get_settings", return_value=settings), \
         patch.object(chat, "decrypt_key", side_effect=lambda c: "sk-or-v1-PLAIN"):
        api_key, model, mode, is_user_key = chat._resolve_key_and_model(
            db, "user-1", {"id": "t1", "model": "thread/pinned"}, body
        )

    assert model == "thread/pinned"  # the per-thread pin wins over the user default
    assert model != "user/default-pref"
    assert model != "owner/default-model"
    assert api_key == "sk-or-v1-PLAIN"
    assert mode == "user"
    assert is_user_key is True
