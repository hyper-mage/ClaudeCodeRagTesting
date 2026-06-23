"""Phase 11 Wave 0 scaffold — D-04 usage capture (drain + sum + persist).

Covers the token-usage capture path (built in plan 11-03/11-04):
  - The trailing `usage` event is captured (NOT discarded when the same response
    also carried tool_calls) and SUMMED across every iteration of the tool loop.
  - The summed usage is PERSISTED to the new additive `messages.usage` JSONB
    column on the `done` event.

test_usage_summed_across_tool_loop is un-skipped + implemented in plan 11-03 (it
asserts the drain-and-capture restructure in stream_chat_completion). The persist
half (test_usage_persisted_to_messages) stays a Wave 0 stub for plan 11-04.
Function names match the RESEARCH Test Map verbatim.
"""
from unittest.mock import MagicMock, patch

import pytest

from services import llm_service

_WAVE0 = "Wave 0 stub — turned green by plan 11-04"


def _delta_chunk(content=None, tool_calls=None, finish_reason=None):
    """A streaming chunk with one choice (text/tool_calls/finish)."""
    chunk = MagicMock()
    chunk.usage = None
    choice = MagicMock()
    choice.delta = MagicMock()
    choice.delta.content = content
    choice.delta.tool_calls = tool_calls
    choice.finish_reason = finish_reason
    chunk.choices = [choice]
    return chunk


def _usage_chunk(usage: dict):
    """A trailing usage-only chunk: choices == [] (skipped by `if not choice`)."""
    chunk = MagicMock()
    chunk.choices = []
    chunk.usage = usage
    return chunk


def _tool_call_delta(call_id="call_1", name="kb_ls", arguments="{}"):
    tc = MagicMock()
    tc.index = 0
    tc.id = call_id
    tc.function = MagicMock()
    tc.function.name = name
    tc.function.arguments = arguments
    return tc


def test_usage_summed_across_tool_loop():
    """D-04: a trailing usage event emitted alongside tool_calls is captured (not
    discarded) and summed across all tool-loop iterations.

    Here we assert the in-stream half: when a single streamed response carries a
    `finish_reason == "tool_calls"` chunk AND a trailing usage-only chunk, the
    early `return` is gone so the stream drains and a `{"type":"usage",...}` event
    is yielded BEFORE `{"type":"done"}` (the chat.py loop sums across iterations).
    """
    usage_payload = {
        "prompt_tokens": 120,
        "completion_tokens": 30,
        "total_tokens": 150,
        "cost": 0.0012,
    }
    stream_chunks = [
        _delta_chunk(tool_calls=[_tool_call_delta()]),
        _delta_chunk(finish_reason="tool_calls"),
        _usage_chunk(usage_payload),
    ]

    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = iter(stream_chunks)

    fake_settings = MagicMock()
    fake_settings.system_prompt = "sys"
    fake_settings.llm_model = "owner/model"

    with patch.object(llm_service, "get_llm_client", return_value=fake_client), \
         patch.object(llm_service, "get_settings", return_value=fake_settings):
        events = list(
            llm_service.stream_chat_completion(
                [{"role": "user", "content": "hi"}],
                tools=[{"type": "function", "function": {"name": "kb_ls"}}],
            )
        )

    types = [e["type"] for e in events]

    # The tool_call event still fires.
    assert "tool_call" in types

    # The trailing usage chunk was captured (the early `return` is gone).
    usage_events = [e for e in events if e["type"] == "usage"]
    assert len(usage_events) == 1, f"expected exactly one usage event, got {types}"
    assert usage_events[0]["usage"]["cost"] == pytest.approx(0.0012)
    assert usage_events[0]["usage"]["total_tokens"] == 150

    # Ordering: usage must come BEFORE done.
    assert "done" in types
    assert types.index("usage") < types.index("done")


def test_usage_persisted_to_messages(monkeypatch):
    """D-04: the summed usage is persisted to the new messages.usage column on done.

    Drives the real send_message SSE endpoint with a stream that yields a usage
    event on EACH of two tool-loop iterations; asserts (a) the final messages.update
    payload carries the SUMMED usage in `usage`, and (b) the done SSE event carries
    the same summed usage. Uses the conftest mock_stream_chat_completion (set_usage)
    so the chat loop's _accumulate_usage runs across iterations.
    """
    import json as _json

    _reset_sse_app_status()
    from fastapi.testclient import TestClient
    from fastapi import Request
    from auth import get_user_id

    user_id = "11111111-1111-1111-1111-111111111111"

    # ---- programmable stream: iter 0 = tool_call (+usage), iter 1 = text (+usage)
    controller = MagicMock()
    controller.call_count = 0
    events_per_call = [
        [
            {"type": "system_content", "content": "sys"},
            {
                "type": "tool_call",
                "tool_calls": [
                    {"id": "call_0", "type": "function",
                     "function": {"name": "kb_ls", "arguments": "{}"}},
                ],
            },
        ],
        [{"type": "text_delta", "text": "final answer"}],
    ]
    usage_per_call = [
        {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120, "cost": 0.001},
        {"prompt_tokens": 50, "completion_tokens": 10, "total_tokens": 60, "cost": 0.0005},
    ]

    def _fake_stream(*args, **kwargs):
        idx = controller.call_count
        controller.call_count += 1
        for ev in events_per_call[idx]:
            yield ev
        yield {"type": "usage", "usage": usage_per_call[idx]}

    # ---- db mock recording messages.update payloads -------------------------
    update_payloads: list[dict] = []
    fake_db = MagicMock()

    def _table(name: str):
        tbl = MagicMock()
        if name == "threads":
            res = MagicMock()
            res.data = {"id": "t1", "user_id": user_id, "title": "x"}
            tbl.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value = res
        elif name == "documents":
            res = MagicMock()
            res.data = None
            tbl.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = res
        elif name == "user_api_keys":
            res = MagicMock()
            res.data = {"encrypted_key": "ENCRYPTED"}
            tbl.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = res
        elif name == "messages":
            tbl.insert.return_value.execute.return_value = MagicMock(data=[{"id": "m-new"}])

            def _update(payload):
                update_payloads.append(payload)
                chain = MagicMock()
                chain.eq.return_value.execute.return_value = MagicMock()
                return chain

            tbl.update.side_effect = _update
        return tbl

    fake_db.table.side_effect = _table

    monkeypatch.setattr("database.get_supabase", lambda: fake_db)
    monkeypatch.setattr("routers.chat.get_supabase", lambda: fake_db)
    monkeypatch.setattr("routers.chat.stream_chat_completion", _fake_stream)
    monkeypatch.setattr("routers.chat.decrypt_key", lambda c: "sk-or-v1-USERKEY")
    # execute_tool would call out to services; stub it to a trivial JSON result.
    monkeypatch.setattr("routers.chat.execute_tool", lambda *a, **k: _json.dumps({"tool": "kb_ls"}))

    def _fake_get_user_id(request: Request):
        request.state.user_id = user_id
        return user_id

    from main import app
    app.dependency_overrides[get_user_id] = _fake_get_user_id
    client = TestClient(app)
    try:
        with client.stream(
            "POST",
            "/api/threads/t1/messages",
            json={"content": "hi"},
            headers={"Authorization": "Bearer fake"},
        ) as resp:
            assert resp.status_code == 200
            lines = list(resp.iter_lines())
    finally:
        app.dependency_overrides.clear()

    expected = {
        "prompt_tokens": 150,
        "completion_tokens": 30,
        "total_tokens": 180,
        "cost": pytest.approx(0.0015),
    }

    # (a) The final content-bearing update persisted the SUMMED usage.
    usage_updates = [p for p in update_payloads if "usage" in p]
    assert usage_updates, f"no messages.update carried a usage key: {update_payloads}"
    persisted = usage_updates[-1]["usage"]
    assert persisted["prompt_tokens"] == expected["prompt_tokens"]
    assert persisted["completion_tokens"] == expected["completion_tokens"]
    assert persisted["total_tokens"] == expected["total_tokens"]
    assert persisted["cost"] == expected["cost"]

    # (b) The done SSE event carried the same summed usage.
    done_payload = _done_payload(lines)
    assert "usage" in done_payload, f"done event missing usage: {done_payload}"
    assert done_payload["usage"]["total_tokens"] == 180
    assert done_payload["usage"]["cost"] == expected["cost"]


def _reset_sse_app_status() -> None:
    try:
        from sse_starlette.sse import AppStatus
        AppStatus.should_exit_event = None
    except (ImportError, AttributeError):
        pass


def _done_payload(lines: list) -> dict:
    """Extract the JSON `data:` payload of the SSE `done` event from raw lines."""
    import json as _json
    saw_done = False
    for raw in lines:
        line = raw.decode() if isinstance(raw, bytes) else raw
        if line.startswith("event:") and line.split(":", 1)[1].strip() == "done":
            saw_done = True
        elif line.startswith("data:") and saw_done:
            return _json.loads(line.split(":", 1)[1].strip())
    raise AssertionError(f"no SSE done event found in lines: {lines}")
