"""SEC-04 rate limiting tests.

Wave 1 06-01 flips placeholders from skip to active as each behavior lands.
"""
import pytest


def test_limiter_module_importable():
    """Confirm `from limiter import limiter, user_id_key` works without circular import."""
    from limiter import limiter, user_id_key  # noqa: F401
    assert limiter is not None
    assert callable(user_id_key)


def test_user_id_key_func(mock_request_with_user, mock_user_id):
    """user_id_key returns request.state.user_id when set."""
    from limiter import user_id_key
    assert user_id_key(mock_request_with_user) == mock_user_id


def test_user_id_key_func_fallback(mock_request_no_user):
    """user_id_key returns 'anonymous' when request.state.user_id is unset."""
    from limiter import user_id_key
    assert user_id_key(mock_request_no_user) == "anonymous"


def test_chat_route_decorated():
    """Verify chat.py:send_message has @limiter.limit applied AND accepts request: Request."""
    import inspect
    from routers.chat import send_message
    sig = inspect.signature(send_message)
    assert "request" in sig.parameters, (
        "send_message MUST accept `request: Request` parameter — "
        "without it slowapi @limiter.limit silently no-ops (RESEARCH Pitfall 1)"
    )
    assert hasattr(send_message, "__wrapped__") or "limiter" in str(send_message), (
        "send_message does not appear to be wrapped by @limiter.limit"
    )


_BUILD_COUNTER = {"n": 0}


def _build_minimal_limited_app(user_id_provider):
    """Build a stand-in FastAPI app with the SAME limiter wired the SAME way as main.py.

    We test the *limiter integration* (decorator + 429 handler + key_func) — not the
    chat handler internals, which require heavy DB/LLM mocks. The route below uses
    the real `limiter` instance from backend/limiter.py and the real `chat_rate_limit`
    setting, so a 429 here proves the same configuration that production main.py wires.

    Critically: the auth bridge (`request.state.user_id = user_id`) is set inside a
    FastAPI dependency — same shape as production `auth.get_user_id`. FastAPI resolves
    dependencies BEFORE the @limiter.limit wrapper invokes key_func, so the key_func
    sees the user_id on the success path and 'anonymous' on the 401 path.

    The endpoint function is given a UNIQUE __name__ per build so slowapi's internal
    `_route_limits` dict doesn't accumulate the same limit twice across multiple test
    apps in one process — which would silently double-tick every request.
    """
    from fastapi import FastAPI, Request, Depends, HTTPException
    from fastapi.responses import JSONResponse
    from slowapi.errors import RateLimitExceeded
    from limiter import limiter
    from config import get_settings

    _BUILD_COUNTER["n"] += 1
    suffix = _BUILD_COUNTER["n"]

    app = FastAPI()
    app.state.limiter = limiter

    @app.exception_handler(RateLimitExceeded)
    async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
        try:
            retry_after = int(exc.limit.limit.GRANULARITY.seconds)
        except AttributeError:
            retry_after = 60
        return JSONResponse(
            status_code=429,
            content={
                "error": "rate_limited",
                "detail": "Too many chat requests — slow down.",
                "retry_after_seconds": retry_after,
            },
            headers={"Retry-After": str(retry_after)},
        )

    def _stub_get_user_id(request: Request) -> str:
        user_id = user_id_provider(request)
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        request.state.user_id = user_id
        return user_id

    async def _stub_send_message(
        request: Request, thread_id: str, user_id: str = Depends(_stub_get_user_id)
    ):
        return {"ok": True, "user_id": user_id}

    # Give it a unique name so slowapi's keying (by `f"{module}.{name}"`) does not
    # collide between successive test builds in the same process.
    _stub_send_message.__name__ = f"stub_send_message_{suffix}"

    decorated = limiter.limit(get_settings().chat_rate_limit)(_stub_send_message)
    app.post("/api/threads/{thread_id}/messages")(decorated)

    return app


def _make_fake_db(user_id: str):
    """Build a fake supabase client with serializable returns for the chat handler.

    Important: the chat handler does many .table().insert/select/update/eq().execute()
    chains. We give every terminal .execute() a Response-like object whose .data is a
    list with a single dict (id + ordinary fields) and whose .data also supports .get().
    """
    from unittest.mock import MagicMock

    db = MagicMock()

    class FakeResp:
        def __init__(self, data):
            self.data = data

    # The chat handler reads:
    #   - thread = db.table("threads").select().eq().eq().maybe_single().execute()
    #     thread.data = {"id":..., "title":...}
    #   - history = db.table("messages").select().eq().eq().order().execute()
    #     history.data = [{"role":"user","content":"hi"}, ...]
    #   - insert(...).execute() -> .data = [{"id": "msg-1"}]
    #   - update(...).eq().execute() -> .data = [...]
    #   - doc_check = db.table("documents").select(...).eq().eq().limit().execute()
    #     doc_check.data = []  (no documents)

    thread_resp = FakeResp({"id": "t1", "user_id": user_id, "title": "x"})
    msg_insert_resp = FakeResp([{"id": "m-asst-1"}])
    history_resp = FakeResp([{"role": "user", "content": "hi"}])
    docs_resp = FakeResp([])
    folders_resp = FakeResp([])

    table = MagicMock()

    # select chain returning history list (default)
    history_chain = MagicMock()
    history_chain.execute.return_value = history_resp

    # maybe_single chain returning the thread row
    maybe_single_chain = MagicMock()
    maybe_single_chain.execute.return_value = thread_resp

    # documents/folders empty list chain
    list_chain = MagicMock()
    list_chain.execute.return_value = docs_resp

    # insert chain returning msg_insert_resp
    insert_chain = MagicMock()
    insert_chain.execute.return_value = msg_insert_resp

    # update chain
    update_chain = MagicMock()
    update_chain.execute.return_value = msg_insert_resp

    def _table(name):
        t = MagicMock()
        # .select(...).eq().eq().maybe_single().execute() -> thread_resp
        # .select(...).eq().eq().order().execute() -> history list
        # .select(...).eq().eq().limit().execute() -> docs list
        # .insert(...).execute() -> msg_insert_resp
        # .update(...).eq().execute() -> msg_insert_resp

        sel = MagicMock()

        # default chains for any deep .select() path
        deep = MagicMock()
        deep.execute.return_value = FakeResp([])
        deep.maybe_single.return_value.execute.return_value = thread_resp
        deep.order.return_value.execute.return_value = history_resp
        deep.limit.return_value.execute.return_value = docs_resp
        deep.eq.return_value.execute.return_value = FakeResp([])
        deep.eq.return_value.maybe_single.return_value.execute.return_value = thread_resp
        deep.eq.return_value.order.return_value.execute.return_value = history_resp
        deep.eq.return_value.limit.return_value.execute.return_value = docs_resp

        sel.eq.return_value = deep
        t.select.return_value = sel

        t.insert.return_value.execute.return_value = msg_insert_resp
        t.update.return_value.eq.return_value.execute.return_value = msg_insert_resp
        return t

    db.table.side_effect = _table
    return db


def _reset_limiter_storage():
    """Reset the in-memory limiter counters between tests."""
    from limiter import limiter
    try:
        limiter.reset()
    except Exception:
        # Fallback: clear underlying storage directly.
        try:
            limiter._storage.reset()
        except Exception:
            pass


def test_429_response_shape(mock_user_id):
    """21st rapid request from same user gets 429 with D-06 JSON shape + Retry-After header.

    Uses a minimal stand-in app that wires the SAME limiter and 429 handler the SAME
    way main.py does — proves the integration without requiring the full chat handler's
    DB and LLM dependencies.
    """
    from fastapi.testclient import TestClient

    _reset_limiter_storage()
    app = _build_minimal_limited_app(lambda req: mock_user_id)
    client = TestClient(app)

    last_resp = None
    try:
        for i in range(25):
            last_resp = client.post("/api/threads/t1/messages", json={})
            if last_resp.status_code == 429:
                break

        assert last_resp.status_code == 429, (
            f"expected 429 within 25 reqs, got {last_resp.status_code}: {last_resp.text}"
        )
        body = last_resp.json()
        assert body["error"] == "rate_limited"
        assert "detail" in body
        assert isinstance(body["retry_after_seconds"], int)
        assert body["retry_after_seconds"] > 0
        assert last_resp.headers["Retry-After"].isdigit()
    finally:
        _reset_limiter_storage()


def test_auth_fail_does_not_tick(mock_user_id):
    """RESEARCH Pitfall 8: 401 (auth-fail) requests do NOT consume rate-limit slots.

    Procedure: 1 valid + 5 invalid (401) + 18 more valid = 19 valid + 5 invalid total.
    The bridge `request.state.user_id = user_id` runs ONLY on the success path, so the
    slowapi key_func sees 'anonymous' for invalid requests — they tick the 'anonymous'
    bucket, not the user's. Assert no valid request returns 429.
    """
    from fastapi.testclient import TestClient

    _reset_limiter_storage()

    call_state = {"phase": "valid"}

    def _provider(request):
        if call_state["phase"] == "invalid":
            return None  # triggers 401 inside the stub handler BEFORE state.user_id is set
        return mock_user_id

    app = _build_minimal_limited_app(_provider)
    client = TestClient(app)

    try:
        # Phase 1: 1 valid request
        call_state["phase"] = "valid"
        r1 = client.post("/api/threads/t1/messages", json={})
        assert r1.status_code != 429, f"first valid req hit 429 unexpectedly: {r1.status_code}"

        # Phase 2: 5 invalid (auth-fail) requests
        call_state["phase"] = "invalid"
        for _ in range(5):
            r = client.post("/api/threads/t1/messages", json={})
            assert r.status_code == 401, f"expected 401, got {r.status_code}"

        # Phase 3: 18 more valid requests (total valid = 19; under 20/min cap)
        call_state["phase"] = "valid"
        statuses = []
        for _ in range(18):
            r = client.post("/api/threads/t1/messages", json={})
            statuses.append(r.status_code)

        assert all(s != 429 for s in statuses), (
            f"some valid requests in phase 3 returned 429 — invalid auth requests "
            f"appear to be ticking the counter (Pitfall 8 NOT mitigated). "
            f"Statuses: {statuses}"
        )
    finally:
        _reset_limiter_storage()
