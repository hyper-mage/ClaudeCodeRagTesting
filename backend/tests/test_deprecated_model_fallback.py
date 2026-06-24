"""Wave 0 (Plan 13-01) RED scaffolds for the deprecated-model fallback — SC#4 (D-06).

Written BEFORE the deprecation check + notice-insert + history-filter land (Plan 13-04),
so on first run these FAIL on the missing behavior (no notice row inserted; the deprecated
model is passed straight through; the notice row leaks into LLM history) — RED. They go
GREEN once Plan 13-04 adds the at-send deprecation check that:
  - detects thread.model absent from model_cache,
  - inserts a messages row with role "notice" (the persisted deprecation line, D-06),
  - falls back to the user/owner default model for the actual LLM call,
  - excludes 'notice' rows from the history map sent to the LLM.

Contract under test:
  - test_inserts_notice_and_falls_back — thread.model = a slug ABSENT from model_cache →
        a role "notice" messages row is inserted AND the model passed to
        stream_chat_completion is the user default, NOT the deprecated slug; no exception.
  - test_notice_excluded_from_history  — a stored 'notice' row never appears in the
        messages list passed to stream_chat_completion (history filters to user/assistant).

Patching mirrors test_chat_retry.py (routers.chat.get_supabase, _resolve_key_and_model
stub, mock_stream_chat_completion). A capturing wrapper records the `messages`/`model`
that the handler hands to stream_chat_completion.
"""
from unittest.mock import MagicMock

_USER = "11111111-1111-1111-1111-111111111111"
_DEPRECATED = "deprecated/old-model"
_DEFAULT = "owner/default-model"


def _reset_sse_app_status() -> None:
    """sse_starlette caches AppStatus.should_exit_event globally; reset per test."""
    try:
        from sse_starlette.sse import AppStatus
        AppStatus.should_exit_event = None
    except (ImportError, AttributeError):
        pass


def _build_fake_db(thread_model: str | None, history_rows: list[dict],
                   model_cache_rows: list[dict]):
    """Fake supabase routed by table name for the chat send + deprecation flow.

    - threads.select().eq().eq().maybe_single().execute() -> a thread owned by _USER
      carrying `model = thread_model`.
    - messages.select("role, content").eq().eq().order().execute() -> history_rows.
    - model_cache.select(...).execute() -> model_cache_rows (used by the deprecation
      check to decide whether thread.model is still a live model).
    - messages.insert(...).execute() -> stub row (records role 'notice' inserts).
    - documents.select(...).limit(1).execute() -> data=None (no docs path).
    """
    db = MagicMock()

    def _table(name: str):
        tbl = MagicMock()
        if name == "threads":
            row = {"id": "t1", "user_id": _USER, "title": "x", "model": thread_model}
            tbl.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(data=row)
        elif name == "messages":
            # history load: select("role, content").eq().eq().order().execute()
            tbl.select.return_value.eq.return_value.eq.return_value.order.return_value.execute.return_value = MagicMock(data=history_rows)
            tbl.insert.return_value.execute.return_value = MagicMock(data=[{"id": "m-new"}])
            tbl.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
        elif name == "model_cache":
            tbl.select.return_value.execute.return_value = MagicMock(data=model_cache_rows)
            tbl.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
                data=(model_cache_rows[0] if model_cache_rows else None)
            )
        elif name == "documents":
            tbl.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(data=None)
            tbl.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(data=None)
        elif name == "user_preferences":
            tbl.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
                data={"default_model": _DEFAULT, "theme": "dark"}
            )
        else:
            tbl.select.return_value.eq.return_value.execute.return_value = MagicMock(data=None)
        return tbl

    db.table.side_effect = _table
    return db


def _drain(resp) -> list[str]:
    return list(resp.iter_lines())


def _install_capturing_stream(monkeypatch) -> dict:
    """Patch routers.chat.stream_chat_completion with a generator that RECORDS the
    `messages` and `model` it receives, then yields a single text delta. Returns the
    capture dict so tests can assert against the model + the message roles passed in."""
    capture: dict = {"calls": []}

    def _fake_stream(*args, **kwargs):
        # stream_chat_completion signature in this codebase passes messages + model;
        # capture from kwargs first, falling back to positional for robustness.
        messages = kwargs.get("messages")
        model = kwargs.get("model")
        if messages is None and args:
            messages = args[0]
        capture["calls"].append({"messages": messages, "model": model, "kwargs": kwargs})
        yield {"type": "text_delta", "text": "ok"}

    monkeypatch.setattr("routers.chat.stream_chat_completion", _fake_stream)
    return capture


def test_inserts_notice_and_falls_back(mock_user_id, monkeypatch) -> None:
    """SC#4 / D-06: a thread pinned to a model ABSENT from model_cache → at send time a
    role 'notice' messages row is inserted AND stream_chat_completion is called with the
    user default model (NOT the deprecated slug); the turn completes without exception."""
    _reset_sse_app_status()
    from fastapi.testclient import TestClient
    from auth import get_user_id
    from fastapi import Request

    # model_cache holds ONLY the default — the deprecated pin is NOT present.
    db = _build_fake_db(
        thread_model=_DEPRECATED,
        history_rows=[{"role": "user", "content": "hi"}],
        model_cache_rows=[{"model_id": _DEFAULT, "is_free": False}],
    )
    capture = _install_capturing_stream(monkeypatch)

    def _fake_get_user_id(request: Request):
        request.state.user_id = _USER
        return _USER

    monkeypatch.setattr("database.get_supabase", lambda: db)
    monkeypatch.setattr("routers.chat.get_supabase", lambda: db)
    # Resolve to the user-default model (NOT the deprecated pin) once deprecation logic
    # rewrites it; the resolver returns the default so the fallback target is unambiguous.
    monkeypatch.setattr(
        "routers.chat._resolve_key_and_model",
        lambda db, user_id, thread_row, body: ("sk-or-v1-OWNER", _DEFAULT, "user", True),
    )

    from main import app
    app.dependency_overrides[get_user_id] = _fake_get_user_id

    client = TestClient(app)
    try:
        with client.stream(
            "POST",
            "/api/threads/t1/messages",
            json={"content": "use the deprecated model"},
            headers={"Authorization": "Bearer fake"},
        ) as resp:
            assert resp.status_code == 200
            _drain(resp)
    finally:
        app.dependency_overrides.clear()

    # A role 'notice' row MUST have been inserted (the persisted deprecation line, D-06).
    notice_inserts = [
        c.args[0]
        for c in db.table("messages").insert.call_args_list
        if c.args and isinstance(c.args[0], dict) and c.args[0].get("role") == "notice"
    ]
    assert notice_inserts, "deprecation 'notice' row was not inserted (SC#4 not implemented)"

    # The model handed to the LLM is the fallback default, NEVER the deprecated slug.
    assert capture["calls"], "stream_chat_completion was never called"
    models_used = {c["model"] for c in capture["calls"]}
    assert _DEPRECATED not in models_used, f"deprecated model leaked to LLM: {models_used}"
    assert _DEFAULT in models_used, f"fallback default not used: {models_used}"


def test_notice_excluded_from_history(mock_user_id, monkeypatch) -> None:
    """SC#4 / D-06: a stored 'notice' row must NEVER appear in the messages list passed
    to stream_chat_completion — the history map filters role to ('user','assistant')."""
    _reset_sse_app_status()
    from fastapi.testclient import TestClient
    from auth import get_user_id
    from fastapi import Request

    # History includes a 'notice' row that must be filtered out of the LLM payload.
    db = _build_fake_db(
        thread_model=None,  # no deprecation path needed; we only test history filtering
        history_rows=[
            {"role": "user", "content": "first"},
            {"role": "notice", "content": "Model X was deprecated; using your default."},
            {"role": "assistant", "content": "answer"},
        ],
        model_cache_rows=[{"model_id": _DEFAULT, "is_free": False}],
    )
    capture = _install_capturing_stream(monkeypatch)

    def _fake_get_user_id(request: Request):
        request.state.user_id = _USER
        return _USER

    monkeypatch.setattr("database.get_supabase", lambda: db)
    monkeypatch.setattr("routers.chat.get_supabase", lambda: db)
    monkeypatch.setattr(
        "routers.chat._resolve_key_and_model",
        lambda db, user_id, thread_row, body: ("sk-or-v1-OWNER", _DEFAULT, "user", True),
    )

    from main import app
    app.dependency_overrides[get_user_id] = _fake_get_user_id

    client = TestClient(app)
    try:
        with client.stream(
            "POST",
            "/api/threads/t1/messages",
            json={"content": "next question"},
            headers={"Authorization": "Bearer fake"},
        ) as resp:
            assert resp.status_code == 200
            _drain(resp)
    finally:
        app.dependency_overrides.clear()

    assert capture["calls"], "stream_chat_completion was never called"
    # No 'notice' role may appear in ANY messages list handed to the LLM.
    for call in capture["calls"]:
        roles = {m.get("role") for m in (call["messages"] or [])}
        assert "notice" not in roles, (
            f"'notice' row leaked into LLM history (must filter to user/assistant): {roles}"
        )
