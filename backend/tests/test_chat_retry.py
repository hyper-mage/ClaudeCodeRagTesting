"""Tests for retry-aware POST /api/threads/{id}/messages (PORT-02, T-08-03).

Plan 08-03 Wave 1: backend retry-dedup hook.

- test_retry_deletes_prior_failed_assistant_row — ?retry=true deletes the orphan
  empty assistant row from the prior failed turn BEFORE streaming.
- test_retry_skips_user_message_insert         — ?retry=true does NOT re-insert
  the user message (it was preserved from the original failed send).
- test_non_retry_path_unchanged                — default POST path has no extra
  DELETE and behaves identically to today's handler.
"""
from unittest.mock import MagicMock


# ---------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------

def _reset_sse_app_status() -> None:
    """sse_starlette caches AppStatus.should_exit_event globally; reset per test
    so each TestClient gets a fresh asyncio.Event (mirrors test_chat_cap.py)."""
    try:
        from sse_starlette.sse import AppStatus
        AppStatus.should_exit_event = None
    except (ImportError, AttributeError):
        pass


def _build_fake_db(mock_user_id: str, prior_assistant_id: str = "asst-prior"):
    """Build a MagicMock supabase client wired for the chat send_message flow.

    - threads.select(...).maybe_single.execute -> thread owned by mock_user_id
    - messages.select(...).order().limit().execute -> data=[{"id": prior_assistant_id}]
      (used by the retry SELECT-then-DELETE pattern to locate the prior orphan row)
    - messages.insert(...).execute -> returns a row with id=m-new
    - messages.update(...).eq(...).execute -> no-op
    - messages.delete(...).eq(...).execute -> no-op (MagicMock auto-creates chain)
    - documents.select(...).eq(...).limit(1).execute -> data=None by default
      (handler treats absent .data as no docs path; assistant tools still wire)

    Returns the MagicMock; tests inspect call_args_list / .called.
    """
    fake_db = MagicMock()

    fake_thread = MagicMock()
    fake_thread.data = {"id": "t1", "user_id": mock_user_id, "title": "x"}

    # threads.select().eq().eq().maybe_single().execute() -> fake_thread
    fake_db.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value = fake_thread

    # insert(...).execute -> stub row id
    fake_db.table.return_value.insert.return_value.execute.return_value = MagicMock(
        data=[{"id": "m-new"}]
    )

    # SELECT-then-DELETE chain for retry:
    #   messages.select("id").eq().eq().eq().order().limit(1).execute()
    # Must return .data=[{"id": prior_assistant_id}] so the impl proceeds to delete.
    prior_select = MagicMock()
    prior_select.data = [{"id": prior_assistant_id}]
    fake_db.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = prior_select

    return fake_db


def _drain(resp) -> list[str]:
    """Drain an SSE stream (return all lines; assertion-only consumer)."""
    return list(resp.iter_lines())


# ---------------------------------------------------------------------
# Test 1: retry=true triggers a DELETE on the prior assistant row
# ---------------------------------------------------------------------

def test_retry_deletes_prior_failed_assistant_row(
    mock_stream_chat_completion, mock_user_id, monkeypatch
):
    """?retry=true must DELETE the prior empty/failed assistant row from messages
    BEFORE inserting the new placeholder. Scope: thread_id + user_id + role.
    """
    _reset_sse_app_status()
    from fastapi.testclient import TestClient
    from auth import get_user_id
    from fastapi import Request

    # Single iteration: text-only response, no tool calls -> voluntary stop.
    mock_stream_chat_completion.set_events([
        [{"type": "text_delta", "text": "retry-answer"}],
    ])

    fake_db = _build_fake_db(mock_user_id, prior_assistant_id="asst-prior")

    def _fake_get_user_id(request: Request):
        request.state.user_id = mock_user_id
        return mock_user_id

    monkeypatch.setattr("database.get_supabase", lambda: fake_db)
    monkeypatch.setattr("routers.chat.get_supabase", lambda: fake_db)

    from main import app
    app.dependency_overrides[get_user_id] = _fake_get_user_id

    client = TestClient(app)
    try:
        with client.stream(
            "POST",
            "/api/threads/t1/messages?retry=true",
            json={"content": "same user message"},
            headers={"Authorization": "Bearer fake"},
        ) as resp:
            assert resp.status_code == 200
            _drain(resp)

        # Assertion 1: messages.delete() was invoked (retry-dedup hook fired).
        assert fake_db.table.return_value.delete.called, (
            "retry path must call messages.delete() to remove prior orphan "
            f"assistant row; delete.called={fake_db.table.return_value.delete.called}"
        )

        # Assertion 2: new assistant placeholder insert still happens on retry.
        insert_calls = fake_db.table.return_value.insert.call_args_list
        assert any(
            call.args
            and isinstance(call.args[0], dict)
            and call.args[0].get("role") == "assistant"
            for call in insert_calls
        ), (
            f"new assistant placeholder must still be inserted on retry; "
            f"insert calls: {[c.args for c in insert_calls]}"
        )
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------
# Test 2: retry=true SKIPS the user-message insert
# ---------------------------------------------------------------------

def test_retry_skips_user_message_insert(
    mock_stream_chat_completion, mock_user_id, monkeypatch
):
    """On ?retry=true the frontend re-sends the SAME user content but the user
    row already exists from the prior failed send. Re-inserting would duplicate
    the user turn. Handler must guard the user-insert with `if not retry:`.
    """
    _reset_sse_app_status()
    from fastapi.testclient import TestClient
    from auth import get_user_id
    from fastapi import Request

    mock_stream_chat_completion.set_events([
        [{"type": "text_delta", "text": "ok"}],
    ])

    fake_db = _build_fake_db(mock_user_id)

    def _fake_get_user_id(request: Request):
        request.state.user_id = mock_user_id
        return mock_user_id

    monkeypatch.setattr("database.get_supabase", lambda: fake_db)
    monkeypatch.setattr("routers.chat.get_supabase", lambda: fake_db)

    from main import app
    app.dependency_overrides[get_user_id] = _fake_get_user_id

    client = TestClient(app)
    try:
        with client.stream(
            "POST",
            "/api/threads/t1/messages?retry=true",
            json={"content": "same user message"},
            headers={"Authorization": "Bearer fake"},
        ) as resp:
            assert resp.status_code == 200
            _drain(resp)

        # Inspect every insert() call's first positional arg (payload dict).
        # Assert NONE have role='user'.
        insert_calls = fake_db.table.return_value.insert.call_args_list
        user_role_inserts = [
            call for call in insert_calls
            if call.args
            and isinstance(call.args[0], dict)
            and call.args[0].get("role") == "user"
        ]
        assert not user_role_inserts, (
            "retry path must NOT insert a user-role row; "
            f"unexpected user inserts: {[c.args for c in user_role_inserts]}"
        )
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------
# Test 3: non-retry path unchanged — NO delete, user-row INSERT happens
# ---------------------------------------------------------------------

def test_non_retry_path_unchanged(
    mock_stream_chat_completion, mock_user_id, monkeypatch
):
    """Default POST (no ?retry param) behaves identically to the pre-08-03
    handler: NO DELETE on messages, user-row insert happens exactly once.
    """
    _reset_sse_app_status()
    from fastapi.testclient import TestClient
    from auth import get_user_id
    from fastapi import Request

    mock_stream_chat_completion.set_events([
        [{"type": "text_delta", "text": "ok"}],
    ])

    fake_db = _build_fake_db(mock_user_id)

    def _fake_get_user_id(request: Request):
        request.state.user_id = mock_user_id
        return mock_user_id

    monkeypatch.setattr("database.get_supabase", lambda: fake_db)
    monkeypatch.setattr("routers.chat.get_supabase", lambda: fake_db)

    from main import app
    app.dependency_overrides[get_user_id] = _fake_get_user_id

    client = TestClient(app)
    try:
        with client.stream(
            "POST",
            "/api/threads/t1/messages",  # no ?retry= param
            json={"content": "hello"},
            headers={"Authorization": "Bearer fake"},
        ) as resp:
            assert resp.status_code == 200
            _drain(resp)

        # Assertion 1: NO delete on messages table.
        assert not fake_db.table.return_value.delete.called, (
            "non-retry path must NOT call messages.delete(); "
            f"delete.called={fake_db.table.return_value.delete.called}"
        )

        # Assertion 2: exactly one user-role insert happened.
        insert_calls = fake_db.table.return_value.insert.call_args_list
        user_role_inserts = [
            call for call in insert_calls
            if call.args
            and isinstance(call.args[0], dict)
            and call.args[0].get("role") == "user"
        ]
        assert len(user_role_inserts) == 1, (
            "non-retry path must insert exactly one user-role row; "
            f"user inserts: {[c.args for c in user_role_inserts]}"
        )
        # Sanity: user payload contains expected content / thread / user.
        payload = user_role_inserts[0].args[0]
        assert payload.get("content") == "hello"
        assert payload.get("thread_id") == "t1"
        assert payload.get("user_id") == mock_user_id
    finally:
        app.dependency_overrides.clear()
