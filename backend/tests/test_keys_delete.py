"""Tests for DELETE /api/keys (KEY-04, disconnect).

Wave 0 (Plan 10-02) — written BEFORE routers.keys exists, so on first run this
FAILS at the `from main import app` → `routers.keys` import (RED). It goes GREEN
once Task 3 ships the router.

Contract: DELETE removes the calling user's row via the service-role client
(.delete().eq("user_id", ...)) and returns 204. A subsequent /status is
connected:false (covered in test_keys_status.py::test_status_not_connected).

Patches mirror test_demo_bootstrap.py: patch("routers.keys.get_supabase") and
clear app.dependency_overrides in a finally.
"""
from unittest.mock import MagicMock, patch


def test_disconnect() -> None:
    """DELETE /api/keys calls .delete().eq("user_id", ...) on user_api_keys and
    returns 204."""
    from fastapi.testclient import TestClient

    from auth import get_user_id
    from main import app

    mock_db = MagicMock()

    app.dependency_overrides[get_user_id] = lambda: "user-uuid"
    try:
        with patch("routers.keys.get_supabase", return_value=mock_db):
            resp = TestClient(app).delete("/api/keys")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 204, f"expected 204, got {resp.status_code}: {resp.text}"

    # The delete must target the user_api_keys table, scoped to the calling user.
    mock_db.table.assert_any_call("user_api_keys")
    delete_eq = mock_db.table.return_value.delete.return_value.eq
    delete_eq.assert_called_once_with("user_id", "user-uuid")
    delete_eq.return_value.execute.assert_called_once()
