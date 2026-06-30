"""Tests for GET /api/keys/balance (COST-02, COST-03, SEC-01 / T-14-01).

Wave 0 (Plan 14-01) — written BEFORE the /balance endpoint, BalanceResponse, and
the low_balance_threshold_usd config field exist, so on first run the new
assertions FAIL (the endpoint 404s). They go GREEN once Task 3 ships the handler.

Security contract (T-14-01 / SEC-01): /balance returns {connected, limit_remaining,
is_low} only — the decrypted sk-or-… key and the raw OpenRouter body NEVER appear
in the response.

Patches mirror test_keys_status.py: override get_user_id, patch
routers.keys.get_supabase, clear app.dependency_overrides in a finally.
Additionally patch routers.keys.decrypt_key (create=True so the patch is clean
before the import lands in Task 3) and httpx.get (build a real httpx.Response the
way test_error_surfacing._status_error does). Function names match the RESEARCH
Test Map verbatim.
"""
import logging
from unittest.mock import MagicMock, patch

import httpx


def _balance_db(row_data):
    """A MagicMock supabase client whose user_api_keys select chain
    (.select('encrypted_key').eq().maybe_single().execute()) returns `row_data`."""
    mock_db = MagicMock()
    chain = (
        mock_db.table.return_value.select.return_value.eq.return_value.maybe_single.return_value
    )
    chain.execute.return_value = MagicMock(data=row_data)
    return mock_db


def _key_response(status_code: int, data: dict | None = None) -> httpx.Response:
    """A real httpx.Response shaped like OpenRouter GET /api/v1/key ({"data": {…}})."""
    req = httpx.Request("GET", "https://openrouter.ai/api/v1/key")
    if data is not None:
        return httpx.Response(status_code, json={"data": data}, request=req)
    return httpx.Response(status_code, request=req)


def _get_balance(mock_db, httpx_mock):
    """Drive GET /api/keys/balance with the supplied db + httpx.get mock."""
    from fastapi.testclient import TestClient

    from auth import get_user_id
    from main import app

    app.dependency_overrides[get_user_id] = lambda: "user-uuid"
    try:
        with patch("routers.keys.get_supabase", return_value=mock_db), \
             patch("routers.keys.decrypt_key", return_value="sk-or-v1-FAKE", create=True), \
             patch("httpx.get", httpx_mock):
            return TestClient(app).get("/api/keys/balance")
    finally:
        app.dependency_overrides.clear()


def test_balance_returns_remaining() -> None:
    """Capped account: limit_remaining echoed as reported; is_low False above the
    1.00 default threshold. The decrypted sk-or-… key never rides the response (SEC-01)."""
    mock_db = _balance_db({"encrypted_key": "ENCRYPTED"})
    httpx_mock = MagicMock(return_value=_key_response(200, {"limit_remaining": 5.0}))

    resp = _get_balance(mock_db, httpx_mock)

    assert resp.status_code == 200, f"expected 200, got {resp.status_code}: {resp.text}"
    body = resp.json()
    assert body["connected"] is True
    assert body["limit_remaining"] == 5.0
    assert body["is_low"] is False
    # SEC-01: the decrypted key must never appear in the balance response.
    assert "sk-or-" not in resp.text


def test_balance_no_key() -> None:
    """No stored key row → {connected:false} AND httpx.get is NEVER called."""
    mock_db = _balance_db(None)
    httpx_mock = MagicMock(return_value=_key_response(200, {"limit_remaining": 5.0}))

    resp = _get_balance(mock_db, httpx_mock)

    assert resp.status_code == 200, f"expected 200, got {resp.status_code}: {resp.text}"
    body = resp.json()
    assert body["connected"] is False
    # No connected key → no outbound OpenRouter call.
    httpx_mock.assert_not_called()


def test_balance_null_uncapped() -> None:
    """limit_remaining null (pay-as-you-go) → is_low False, limit_remaining None (D-04)."""
    mock_db = _balance_db({"encrypted_key": "ENCRYPTED"})
    httpx_mock = MagicMock(return_value=_key_response(200, {"limit_remaining": None}))

    resp = _get_balance(mock_db, httpx_mock)

    assert resp.status_code == 200, f"expected 200, got {resp.status_code}: {resp.text}"
    body = resp.json()
    assert body["connected"] is True
    assert body["limit_remaining"] is None
    assert body["is_low"] is False


def test_balance_is_low() -> None:
    """limit_remaining 0.40 < default threshold 1.00 → is_low True (server-computed)."""
    mock_db = _balance_db({"encrypted_key": "ENCRYPTED"})
    httpx_mock = MagicMock(return_value=_key_response(200, {"limit_remaining": 0.40}))

    resp = _get_balance(mock_db, httpx_mock)

    assert resp.status_code == 200, f"expected 200, got {resp.status_code}: {resp.text}"
    body = resp.json()
    assert body["connected"] is True
    assert body["limit_remaining"] == 0.40
    assert body["is_low"] is True


def test_balance_provider_error_scrubbed() -> None:
    """OpenRouter call fails → 502 with a fixed generic detail; the sk-or-… key
    never appears in the response body (SEC-01). The raised exception embeds the
    key on purpose to prove the handler scrubs the log line and never echoes it."""
    mock_db = _balance_db({"encrypted_key": "ENCRYPTED"})
    httpx_mock = MagicMock(
        side_effect=httpx.ConnectError("connect failed for key sk-or-v1-FAKE")
    )

    resp = _get_balance(mock_db, httpx_mock)

    assert resp.status_code == 502, f"expected 502, got {resp.status_code}: {resp.text}"
    # SEC-01: neither the key nor a raw provider message leaks into the response detail.
    assert "sk-or-" not in resp.text


def _bad_json_response(status_code: int = 200) -> httpx.Response:
    """A 2xx OpenRouter response whose body is NOT JSON, so resp.json() raises
    json.JSONDecodeError (a ValueError subclass)."""
    req = httpx.Request("GET", "https://openrouter.ai/api/v1/key")
    return httpx.Response(status_code, content=b"<html>not json</html>", request=req)


def test_balance_malformed_body(caplog) -> None:
    """CR-01: a malformed-but-2xx provider body must map to the fixed generic 502 —
    NOT an unhandled 500 whose exc_info traceback would carry the still-live decrypted
    sk-or-… key from the handler frame's locals (T-14-02). The key appears in NEITHER
    the response NOR the logs on this parse-failure path."""
    mock_db = _balance_db({"encrypted_key": "ENCRYPTED"})
    httpx_mock = MagicMock(return_value=_bad_json_response(200))

    with caplog.at_level(logging.WARNING):
        resp = _get_balance(mock_db, httpx_mock)

    assert resp.status_code == 502, f"expected 502, got {resp.status_code}: {resp.text}"
    # SEC-01 / T-14-02: the decrypted key leaks into neither the response nor the logs.
    assert "sk-or-" not in resp.text
    assert "sk-or-" not in caplog.text
