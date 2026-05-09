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


@pytest.mark.skip(reason="Wave 1 06-01 Task 1-3: 429 handler returns JSON with Retry-After")
def test_429_response_shape():
    """Hitting the rate limit returns JSON {error, detail, retry_after_seconds}."""
    raise NotImplementedError("Wave 1 06-01 Task 1-3 implements")


@pytest.mark.skip(reason="Wave 1 06-01 Task 1-3: auth-fail bypass verified (Pitfall 8)")
def test_auth_fail_does_not_tick():
    """RESEARCH Pitfall 8 verification: 401 path does NOT consume a rate-limit slot."""
    raise NotImplementedError("Wave 1 06-01 Task 1-3 implements + verifies")
