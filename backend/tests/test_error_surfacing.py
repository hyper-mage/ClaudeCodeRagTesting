"""Phase 11 Wave 0 scaffold — SEC-01 scrub + D-12 distinct error codes.

Covers the error-surfacing path (built in plan 11-04):
  - SEC-01: a str(e) carrying `sk-or-…` is scrubbed before it reaches the SSE
            error payload AND before it reaches any log line (incl. the exc_info
            traceback, via the `_ScrubFilter` logging.Filter — RESEARCH Open Q2).
  - D-12:   upstream 429 surfaces a `rate_limit` code; 402 a `payment_required`
            code — distinct, so the UI can disambiguate.

Wave 0 STUBS turned green by plan 11-04 (Task 2). Function names match the
RESEARCH Test Map verbatim.
"""
import json
import logging
from unittest.mock import MagicMock

import httpx
import openai


# ---------------------------------------------------------------------
# Shared helpers — drive the real send_message SSE endpoint with a
# stream_chat_completion that RAISES, so the typed-catch / scrub path runs.
# ---------------------------------------------------------------------

_SK = "sk-or-v1-LEAKEDSECRETKEY1234567890"
_USER_ID = "11111111-1111-1111-1111-111111111111"


def _reset_sse_app_status() -> None:
    """sse_starlette caches AppStatus.should_exit_event globally; reset per test
    so each TestClient gets a fresh asyncio.Event (mirrors test_chat_retry.py)."""
    try:
        from sse_starlette.sse import AppStatus
        AppStatus.should_exit_event = None
    except (ImportError, AttributeError):
        pass


def _build_fake_db():
    """A MagicMock supabase client wired for the chat send_message flow with a
    stored user key (so _resolve_key_and_model returns mode=='user' and the loop
    reaches the stream call where our injected error fires)."""
    db = MagicMock()

    def _table(name: str):
        tbl = MagicMock()
        if name == "threads":
            res = MagicMock()
            res.data = {"id": "t1", "user_id": _USER_ID, "title": "x"}
            tbl.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value = res
        elif name == "documents":
            res = MagicMock()
            res.data = None  # no completed docs
            tbl.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = res
        elif name == "user_api_keys":
            res = MagicMock()
            res.data = {"encrypted_key": "ENCRYPTED"}
            tbl.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = res
        elif name == "messages":
            # insert -> row with id; update/select chains are no-ops via MagicMock.
            tbl.insert.return_value.execute.return_value = MagicMock(data=[{"id": "m-new"}])
        # threads.update / messages.update etc. auto-mock.
        return tbl

    db.table.side_effect = _table
    return db


def _drive_with_raising_stream(monkeypatch, exc: Exception) -> list[str]:
    """POST a chat turn whose stream_chat_completion raises `exc`; return SSE lines."""
    _reset_sse_app_status()
    from fastapi.testclient import TestClient
    from fastapi import Request
    from auth import get_user_id

    fake_db = _build_fake_db()

    def _raising_stream(*args, **kwargs):
        raise exc
        yield  # pragma: no cover — makes this a generator

    monkeypatch.setattr("database.get_supabase", lambda: fake_db)
    monkeypatch.setattr("routers.chat.get_supabase", lambda: fake_db)
    monkeypatch.setattr("routers.chat.stream_chat_completion", _raising_stream)
    # _resolve_key_and_model decrypts the stored row; make it deterministic.
    monkeypatch.setattr("routers.chat.decrypt_key", lambda c: _SK)

    def _fake_get_user_id(request: Request):
        request.state.user_id = _USER_ID
        return _USER_ID

    from main import app
    app.dependency_overrides[get_user_id] = _fake_get_user_id
    client = TestClient(app)
    try:
        with client.stream(
            "POST",
            "/api/threads/t1/messages",
            json={"content": "hello"},
            headers={"Authorization": "Bearer fake"},
        ) as resp:
            assert resp.status_code == 200
            lines = list(resp.iter_lines())
    finally:
        app.dependency_overrides.clear()
    return lines


def _sse_error_payload(lines: list[str]) -> dict:
    """Extract the JSON `data:` payload of the SSE `error` event from raw lines."""
    saw_error_event = False
    for raw in lines:
        line = raw.decode() if isinstance(raw, bytes) else raw
        if line.startswith("event:") and line.split(":", 1)[1].strip() == "error":
            saw_error_event = True
        elif line.startswith("data:") and saw_error_event:
            return json.loads(line.split(":", 1)[1].strip())
    raise AssertionError(f"no SSE error event found in lines: {lines}")


def _status_error(status_code: int, message: str) -> openai.APIStatusError:
    """Construct a real openai.APIStatusError (or RateLimitError) with a status_code."""
    req = httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
    resp = httpx.Response(status_code, request=req)
    cls = openai.RateLimitError if status_code == 429 else openai.APIStatusError
    return cls(message, response=resp, body=None)


# ---------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------

def test_sk_or_scrubbed_in_sse_error(monkeypatch):
    """SEC-01: an exception whose str() contains `sk-or-…` is scrubbed (via
    scrub_secrets) before it is yielded as an SSE error event — no sk-or- bleed."""
    exc = RuntimeError(f"upstream auth failed with key {_SK} — denied")
    lines = _drive_with_raising_stream(monkeypatch, exc)

    payload = _sse_error_payload(lines)
    blob = json.dumps(payload)
    assert "sk-or-" not in blob, f"sk-or- leaked into SSE error: {blob}"
    assert "[redacted-key]" in blob


def test_429_402_distinct_codes(monkeypatch):
    """D-12: an upstream 429 surfaces code 'rate_limit'; a 402 surfaces
    'payment_required' — the two codes are distinct."""
    # 429 → rate_limit
    lines_429 = _drive_with_raising_stream(
        monkeypatch, _status_error(429, "rate limited")
    )
    payload_429 = _sse_error_payload(lines_429)
    assert payload_429["error"] == "rate_limit"

    # 402 → payment_required
    lines_402 = _drive_with_raising_stream(
        monkeypatch, _status_error(402, "payment required")
    )
    payload_402 = _sse_error_payload(lines_402)
    assert payload_402["error"] == "payment_required"

    # The two codes are distinct (and neither is the generic upstream_error path).
    assert payload_429["error"] != payload_402["error"]
    assert payload_429["error"] not in ("upstream_error", "[An error occurred]")
    assert payload_402["error"] not in ("upstream_error", "[An error occurred]")


def test_unauthorized_code_on_401(monkeypatch):
    """SC#4 / D-09 (backend half): a mid-stream OpenRouter 401 (stored key rejected
    as invalid/revoked) surfaces the structured code `no_api_key` — the SAME code the
    pre-flight no-key path emits — so the FE [Reconnect] mapping is reused and the
    failure does NOT dead-end on the generic `upstream_error` bubble."""
    lines = _drive_with_raising_stream(monkeypatch, _status_error(401, "unauthorized"))
    payload = _sse_error_payload(lines)
    assert payload["error"] == "no_api_key"
    assert payload["error"] not in ("upstream_error", "[An error occurred]")


def test_forbidden_code_on_403(monkeypatch):
    """SC#4 / D-09 (backend half): a mid-stream OpenRouter 403 surfaces the distinct
    structured code `forbidden` — separate from payment_required (402), no_api_key
    (401), and the generic upstream_error (else)."""
    lines = _drive_with_raising_stream(monkeypatch, _status_error(403, "forbidden"))
    payload = _sse_error_payload(lines)
    assert payload["error"] == "forbidden"
    assert payload["error"] not in ("upstream_error", "[An error occurred]")


def test_logging_filter_scrubs_exc_info():
    """SEC-01 (logs closure): the _ScrubFilter (plan 11-04 Task 2) scrubs the
    FORMATTED record including the exc_info traceback — not just getMessage().

    END-TO-END: log through the REAL emitting logger (`routers.chat`) with a
    capturing handler attached to ROOT, and assert the captured sink output
    contains [redacted-key] and NO sk-or- substring. The key here lives in a
    stack-frame local of the raised exception's traceback — the path the inline
    message-string scrub at chat.py alone does NOT cover.
    """
    import io

    import routers.chat as chat  # import triggers _install_scrub_filter()

    # Capturing handler on ROOT. chat._install_scrub_filter() attaches the
    # _ScrubFilter to existing root handlers; re-run it so the filter binds to
    # this freshly-added handler too.
    buf = io.StringIO()
    sink = logging.StreamHandler(buf)
    sink.setFormatter(logging.Formatter("%(message)s"))

    root = logging.getLogger()
    prev_level = root.level
    root.addHandler(sink)
    root.setLevel(logging.DEBUG)
    chat._install_scrub_filter()
    try:
        emitter = logging.getLogger("routers.chat")
        # Raise so the key sits in a stack-frame local / traceback, then log with
        # exc_info — the message string itself ALSO carries the key for good measure.
        try:
            secret_local = _SK  # noqa: F841 — intentionally a traceback stack local
            raise RuntimeError(f"boom with {secret_local}")
        except RuntimeError:
            emitter.error(f"chat failed: {_SK}", exc_info=True)
    finally:
        root.removeHandler(sink)
        root.setLevel(prev_level)

    out = buf.getvalue()
    assert "sk-or-" not in out, f"key leaked into log sink:\n{out}"
    assert "[redacted-key]" in out, f"scrub did not run on the record:\n{out}"
    # The exc_info traceback path specifically must be scrubbed (not just the msg).
    assert "RuntimeError" in out, "exc_info traceback should still render (scrubbed)"
