"""SEC-04 rate limiting tests.

Placeholders for Wave 0; Wave 1 will REMOVE the @pytest.mark.skip decorators
one test at a time as each behavior lands. Every test name is referenced
explicitly by an acceptance criterion in 06-01-PLAN.md tasks.
"""
import pytest


@pytest.mark.skip(reason="Wave 1 06-01: limiter module created")
def test_limiter_module_importable():
    """Confirm `from limiter import limiter, user_id_key` works without circular import."""
    from limiter import limiter, user_id_key  # noqa: F401
    # If we got here, no circular import. Limiter instance is configured.
    assert limiter is not None
    assert callable(user_id_key)


@pytest.mark.skip(reason="Wave 1 06-01: user_id_key implemented")
def test_user_id_key_func(mock_request_with_user, mock_user_id):
    """user_id_key returns request.state.user_id when set."""
    from limiter import user_id_key
    assert user_id_key(mock_request_with_user) == mock_user_id


@pytest.mark.skip(reason="Wave 1 06-01: user_id_key fallback")
def test_user_id_key_func_fallback(mock_request_no_user):
    """user_id_key returns 'anonymous' when request.state.user_id is unset.

    Guards against KeyError/AttributeError crash on un-authenticated path.
    """
    from limiter import user_id_key
    assert user_id_key(mock_request_no_user) == "anonymous"


@pytest.mark.skip(reason="Wave 1 06-01: chat route decorated with @limiter.limit and accepts request: Request")
def test_chat_route_decorated():
    """Verify chat.py:send_message has @limiter.limit applied AND accepts request: Request.

    Per RESEARCH Pitfall 1: slowapi silently no-ops without `request: Request` param.
    Both conditions MUST be true.
    """
    import inspect
    from routers.chat import send_message
    sig = inspect.signature(send_message)
    # Must accept a 'request' parameter typed as Request (or annotated).
    assert "request" in sig.parameters, (
        "send_message MUST accept `request: Request` parameter - "
        "without it slowapi @limiter.limit silently no-ops (RESEARCH Pitfall 1)"
    )
    # The wrapped function should bear evidence of slowapi's wrapper.
    # slowapi attaches limit metadata via __wrapped__ chain or a marker attribute.
    # Heuristic: introspect closure or repr; the canonical check is that
    # the decorator chain invokes Limiter.limit. We assert that the route
    # function's __wrapped__ attribute exists (slowapi wraps via functools.wraps).
    assert hasattr(send_message, "__wrapped__") or "limiter" in str(send_message), (
        "send_message does not appear to be wrapped by @limiter.limit"
    )


@pytest.mark.skip(reason="Wave 1 06-01: 429 handler returns JSON with Retry-After")
def test_429_response_shape():
    """Hitting the rate limit returns JSON {error, detail, retry_after_seconds}.

    Uses TestClient to fire 21 quick requests and asserts the 21st gets a 429
    with the D-06 JSON contract + Retry-After header.
    """
    # Implementation: spin up TestClient(app), monkeypatch get_user_id to
    # return mock_user_id, fire 21 POSTs to /api/threads/x/messages,
    # assert response.status_code == 429,
    # assert response.headers["Retry-After"].isdigit(),
    # assert response.json()["error"] == "rate_limited",
    # assert "retry_after_seconds" in response.json().
    raise NotImplementedError("Wave 1 06-01 implements")


@pytest.mark.skip(reason="Wave 1 06-01: auth-fail bypass verified (Pitfall 8)")
def test_auth_fail_does_not_tick():
    """RESEARCH Pitfall 8 verification: 401 path does NOT consume a rate-limit slot.

    4-line procedure: 1 valid req, 5 invalid (bad token) reqs, then 19 more
    valid reqs; the 20th valid req should still pass (auth-fails didn't tick).
    """
    # Implementation depends on Wave 1 wiring; placeholder for now.
    raise NotImplementedError("Wave 1 06-01 implements + verifies")
