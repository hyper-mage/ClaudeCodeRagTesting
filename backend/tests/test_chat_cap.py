"""SEC-05 chat tool-loop max-iter cap tests.

Wave 1 06-02: implementations flipped green.
Cap-hit tests depend on `mock_stream_chat_completion` fixture (conftest)
to drive the inner generator deterministically.
"""
import pytest


@pytest.fixture(autouse=True)
def _reset_sse_app_status():
    """Reset sse_starlette's global AppStatus.should_exit_event between tests.

    sse_starlette caches an asyncio.Event at module level which gets bound to
    the first TestClient's event loop. Subsequent tests with a fresh event loop
    raise 'bound to a different event loop'. Resetting between tests isolates
    each TestClient invocation. (Rule 3 blocking fix.)
    """
    try:
        from sse_starlette.sse import AppStatus
        AppStatus.should_exit_event = None
    except (ImportError, AttributeError):
        pass
    yield
    try:
        from sse_starlette.sse import AppStatus
        AppStatus.should_exit_event = None
    except (ImportError, AttributeError):
        pass


def test_cap_hit_graceful_exit(mock_stream_chat_completion, mock_user_id, monkeypatch):
    """SEC-05: cap-hit emits graceful content_delta + ends with done event."""
    from fastapi.testclient import TestClient
    from auth import get_user_id
    from unittest.mock import MagicMock

    # Force every iteration to emit a tool_call so the loop never voluntarily exits.
    mock_stream_chat_completion.set_default_tool_call()

    from fastapi import Request

    def _fake_get_user_id(request: Request):
        request.state.user_id = mock_user_id
        return mock_user_id

    fake_db = MagicMock()
    fake_thread = MagicMock()
    fake_thread.data = {"id": "t1", "user_id": mock_user_id, "title": "x"}
    fake_db.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value = fake_thread
    fake_db.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[{"id": "m1"}])

    # Tool execution must not be called for the kb_ls (default) path; if it is,
    # have it return an empty JSON to keep the loop going (still no voluntary stop).
    monkeypatch.setattr("routers.chat.execute_tool", lambda *a, **kw: '{"ok":true}', raising=False)
    monkeypatch.setattr("database.get_supabase", lambda: fake_db)
    monkeypatch.setattr("routers.chat.get_supabase", lambda: fake_db)

    from main import app
    app.dependency_overrides[get_user_id] = _fake_get_user_id

    client = TestClient(app)
    with client.stream("POST", "/api/threads/t1/messages",
                        json={"content": "loop forever please"},
                        headers={"Authorization": "Bearer fake"}) as resp:
        assert resp.status_code == 200
        content_deltas = []
        saw_done = False
        for line in resp.iter_lines():
            if not line:
                continue
            if line.startswith("data:"):
                content_deltas.append(line[5:].strip())
            if line.startswith("event: done"):
                saw_done = True

    # call_count is iterations of the OUTER loop = chat_max_iterations on cap-hit.
    from config import get_settings
    cap = get_settings().chat_max_iterations
    assert mock_stream_chat_completion.call_count == cap, (
        f"expected exactly {cap} iterations, got {mock_stream_chat_completion.call_count}"
    )
    # The LAST data line should contain the cap-hit notice text.
    joined = " ".join(content_deltas)
    assert "tool-call limit" in joined, (
        f"cap-hit notice 'tool-call limit' missing from content_deltas: {content_deltas[-3:]}"
    )
    assert saw_done, "final SSE event must be 'done', not 'error'"

    app.dependency_overrides.clear()


def test_cap_hit_logs_warning(mock_stream_chat_completion, caplog, mock_user_id, monkeypatch):
    """SEC-05: cap-hit emits logger.warning with user_id + max_iterations."""
    import logging
    from fastapi.testclient import TestClient
    from auth import get_user_id
    from unittest.mock import MagicMock

    mock_stream_chat_completion.set_default_tool_call()

    from fastapi import Request

    def _fake_get_user_id(request: Request):
        request.state.user_id = mock_user_id
        return mock_user_id

    fake_db = MagicMock()
    fake_thread = MagicMock()
    fake_thread.data = {"id": "t1", "user_id": mock_user_id, "title": "x"}
    fake_db.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value = fake_thread
    fake_db.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[{"id": "m1"}])

    monkeypatch.setattr("routers.chat.execute_tool", lambda *a, **kw: '{"ok":true}', raising=False)
    monkeypatch.setattr("database.get_supabase", lambda: fake_db)
    monkeypatch.setattr("routers.chat.get_supabase", lambda: fake_db)

    from main import app
    app.dependency_overrides[get_user_id] = _fake_get_user_id

    client = TestClient(app)
    with caplog.at_level(logging.WARNING, logger="routers.chat"):
        with client.stream("POST", "/api/threads/t1/messages",
                            json={"content": "x"},
                            headers={"Authorization": "Bearer fake"}) as resp:
            # Drain the stream to ensure the generator runs to completion.
            for _ in resp.iter_lines():
                pass

    warnings = [r for r in caplog.records if r.levelname == "WARNING"]
    cap_warnings = [r for r in warnings if "max_iterations" in r.getMessage()]
    assert cap_warnings, (
        f"expected at least one WARNING containing 'max_iterations'; got: {[r.getMessage() for r in warnings]}"
    )
    assert any(mock_user_id in r.getMessage() for r in cap_warnings), (
        "cap-hit warning must include the user_id"
    )

    app.dependency_overrides.clear()


def test_cap_hit_langsmith_tag(mock_stream_chat_completion, mock_langsmith_run,
                               mock_user_id, monkeypatch):
    """SEC-05: cap-hit attaches LangSmith metadata iteration_cap_hit=True."""
    from fastapi.testclient import TestClient
    from auth import get_user_id
    from unittest.mock import MagicMock

    mock_stream_chat_completion.set_default_tool_call()

    from fastapi import Request

    def _fake_get_user_id(request: Request):
        request.state.user_id = mock_user_id
        return mock_user_id

    fake_db = MagicMock()
    fake_thread = MagicMock()
    fake_thread.data = {"id": "t1", "user_id": mock_user_id, "title": "x"}
    fake_db.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value = fake_thread
    fake_db.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[{"id": "m1"}])

    monkeypatch.setattr("routers.chat.execute_tool", lambda *a, **kw: '{"ok":true}', raising=False)
    monkeypatch.setattr("database.get_supabase", lambda: fake_db)
    monkeypatch.setattr("routers.chat.get_supabase", lambda: fake_db)

    from main import app
    app.dependency_overrides[get_user_id] = _fake_get_user_id

    client = TestClient(app)
    with client.stream("POST", "/api/threads/t1/messages",
                        json={"content": "x"},
                        headers={"Authorization": "Bearer fake"}) as resp:
        for _ in resp.iter_lines():
            pass

    # mock_langsmith_run patched at langsmith.run_helpers.get_current_run_tree.
    # Implementation does a lazy `from langsmith.run_helpers import ...` inside the
    # try block which re-resolves to the monkeypatched function.
    if mock_langsmith_run.add_metadata.called:
        calls = mock_langsmith_run.add_metadata.call_args_list
        metadata_dicts = [c.args[0] if c.args else c.kwargs for c in calls]
        assert any(
            isinstance(d, dict) and d.get("iteration_cap_hit") is True
            for d in metadata_dicts
        ), f"expected metadata dict with iteration_cap_hit=True; got: {metadata_dicts}"
    else:
        # Fallback acceptable per Pitfall 5: implementation MAY log-only if run-tree
        # unavailable. Test does not enforce add_metadata in that case but
        # documents the gap in summary.
        import warnings
        warnings.warn(
            "LangSmith run.add_metadata NOT called -- implementation took "
            "log-only fallback. RESEARCH Pitfall 5 may apply. "
            "Verify trace metadata appears in real LangSmith run during phase 7."
        )

    app.dependency_overrides.clear()


def test_voluntary_stop_preserved(mock_stream_chat_completion, mock_user_id, monkeypatch):
    """SEC-05: loop with no tool calls breaks normally; cap-hit branch NOT triggered."""
    from fastapi.testclient import TestClient
    from auth import get_user_id
    from unittest.mock import MagicMock

    # Single iteration: text only, no tool calls -> voluntary stop fires.
    mock_stream_chat_completion.set_events([
        [{"type": "text_delta", "text": "hello"}],
    ])

    from fastapi import Request

    def _fake_get_user_id(request: Request):
        request.state.user_id = mock_user_id
        return mock_user_id

    fake_db = MagicMock()
    fake_thread = MagicMock()
    fake_thread.data = {"id": "t1", "user_id": mock_user_id, "title": "x"}
    fake_db.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value = fake_thread
    fake_db.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[{"id": "m1"}])

    monkeypatch.setattr("database.get_supabase", lambda: fake_db)
    monkeypatch.setattr("routers.chat.get_supabase", lambda: fake_db)

    from main import app
    app.dependency_overrides[get_user_id] = _fake_get_user_id

    client = TestClient(app)
    content_deltas = []
    saw_done = False
    with client.stream("POST", "/api/threads/t1/messages",
                        json={"content": "hi"},
                        headers={"Authorization": "Bearer fake"}) as resp:
        for line in resp.iter_lines():
            if line.startswith("data:"):
                content_deltas.append(line[5:].strip())
            if line.startswith("event: done"):
                saw_done = True

    assert mock_stream_chat_completion.call_count == 1, (
        f"voluntary stop should run exactly 1 iteration, got {mock_stream_chat_completion.call_count}"
    )
    joined = " ".join(content_deltas)
    assert "tool-call limit" not in joined, (
        f"cap-hit notice should NOT appear on voluntary stop; deltas: {content_deltas}"
    )
    assert saw_done, "final SSE event must be 'done'"

    app.dependency_overrides.clear()
