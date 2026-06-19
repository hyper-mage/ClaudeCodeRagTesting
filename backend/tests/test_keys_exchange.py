"""Tests for POST /api/keys/openrouter/exchange (KEY-01, SEC-01).

Wave 0 (Plan 10-02) — written BEFORE routers.keys exists, so on first run these
FAIL at the `from main import app` → `routers.keys` import (RED). They go GREEN
once Task 3 ships the router.

Security contract (T-10-03 / T-10-04 / SEC-01):
- the exchanged sk-or-v1-… key is NEVER in any response body (resp.text);
- encrypt_key runs before the upsert;
- the upsert is .upsert (one key per user, reconnect overwrites);
- connected_at is set EXPLICITLY in the payload (ON CONFLICT skips defaults);
- a 403/error from OpenRouter surfaces a generic detail, never the body/key.

Patches mirror test_demo_bootstrap.py: names are patched AS IMPORTED INTO
routers.keys (patch("routers.keys.X")), and app.dependency_overrides is cleared
in a finally.
"""
from unittest.mock import MagicMock, patch

import httpx


def test_exchange_upserts_and_hides_key() -> None:
    """POST exchange: 200, key absent from body, encrypt called once, upsert once
    with provider='openrouter', a key_label ending in the last-4 tail, and an
    EXPLICIT connected_at."""
    from fastapi.testclient import TestClient

    from auth import get_user_id
    from main import app

    plaintext_key = "sk-or-v1-PLAINTEXTwXyZ"
    mock_db = MagicMock()

    app.dependency_overrides[get_user_id] = lambda: "user-uuid"
    try:
        with patch("routers.keys.get_supabase", return_value=mock_db), \
             patch("routers.keys.exchange_code", return_value=plaintext_key) as m_ex, \
             patch("routers.keys.encrypt_key", return_value="ciphertext") as m_enc:
            resp = TestClient(app).post(
                "/api/keys/openrouter/exchange",
                json={"code": "the-code", "code_verifier": "the-verifier"},
            )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200, f"expected 200, got {resp.status_code}: {resp.text}"
    # SEC-01: the key must NEVER appear in the response body (plaintext or tail-of-key).
    assert "sk-or-v1" not in resp.text, f"key leaked into response: {resp.text!r}"
    assert plaintext_key not in resp.text

    m_ex.assert_called_once_with("the-code", "the-verifier")
    m_enc.assert_called_once_with(plaintext_key)

    upsert = mock_db.table.return_value.upsert
    upsert.assert_called_once()
    payload = upsert.call_args.args[0]
    assert payload["provider"] == "openrouter"
    assert payload["encrypted_key"] == "ciphertext"
    # masked label is the non-secret last-4 tail of the key.
    assert payload["key_label"].endswith(plaintext_key[-4:])
    assert "sk-or-v1" not in str(payload["encrypted_key"])
    # connected_at set EXPLICITLY (Pitfall 4 — ON CONFLICT skips defaults).
    assert payload.get("connected_at"), "connected_at must be set explicitly in the upsert payload"


def test_exchange_403_generic_error() -> None:
    """A 403 from OpenRouter (exchange_code raises HTTPStatusError) surfaces a
    generic error whose body contains NO sk-or and NOT the raw OpenRouter text."""
    from fastapi.testclient import TestClient

    from auth import get_user_id
    from main import app

    # Simulate a 403 whose body carries a key (the worst case to leak).
    leaky_body = "forbidden: sk-or-v1-LEAKEDfromOpenRouter"
    request = httpx.Request("POST", "https://openrouter.ai/api/v1/auth/keys")
    response = httpx.Response(403, text=leaky_body, request=request)
    err = httpx.HTTPStatusError("403 Forbidden", request=request, response=response)

    mock_db = MagicMock()
    app.dependency_overrides[get_user_id] = lambda: "user-uuid"
    try:
        with patch("routers.keys.get_supabase", return_value=mock_db), \
             patch("routers.keys.exchange_code", side_effect=err), \
             patch("routers.keys.encrypt_key", return_value="ciphertext"):
            resp = TestClient(app).post(
                "/api/keys/openrouter/exchange",
                json={"code": "c", "code_verifier": "v"},
            )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code >= 400, f"expected an error status, got {resp.status_code}"
    assert resp.status_code != 200
    # SEC-01 / T-10-04: neither the key nor the raw OpenRouter body may surface.
    assert "sk-or" not in resp.text, f"key/body leaked into error: {resp.text!r}"
    assert "LEAKED" not in resp.text
    assert leaky_body not in resp.text


def test_reconnect_upserts() -> None:
    """Two sequential exchanges for the same user both call .upsert (NOT .insert)
    so the prior row is overwritten (one key per user); connected_at is set in both."""
    from fastapi.testclient import TestClient

    from auth import get_user_id
    from main import app

    mock_db = MagicMock()
    client = TestClient(app)

    app.dependency_overrides[get_user_id] = lambda: "user-uuid"
    try:
        with patch("routers.keys.get_supabase", return_value=mock_db), \
             patch("routers.keys.exchange_code", side_effect=["sk-or-v1-FIRSTaaaa", "sk-or-v1-SECONDbbbb"]), \
             patch("routers.keys.encrypt_key", side_effect=["ct1", "ct2"]):
            r1 = client.post(
                "/api/keys/openrouter/exchange",
                json={"code": "c1", "code_verifier": "v1"},
            )
            r2 = client.post(
                "/api/keys/openrouter/exchange",
                json={"code": "c2", "code_verifier": "v2"},
            )
    finally:
        app.dependency_overrides.clear()

    assert r1.status_code == 200, r1.text
    assert r2.status_code == 200, r2.text

    upsert = mock_db.table.return_value.upsert
    assert upsert.call_count == 2, f"expected 2 upserts (reconnect overwrites), got {upsert.call_count}"
    # .insert must never be used — that would create a second row per user.
    mock_db.table.return_value.insert.assert_not_called()
    for call in upsert.call_args_list:
        payload = call.args[0]
        assert payload["user_id"] == "user-uuid"
        assert payload.get("connected_at"), "every reconnect must re-stamp connected_at explicitly"
