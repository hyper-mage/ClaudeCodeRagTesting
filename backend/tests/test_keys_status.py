"""Tests for GET /api/keys/status (KEY-03, SEC-01).

Wave 0 (Plan 10-02) — written BEFORE routers.keys exists, so on first run these
FAIL at the `from main import app` → `routers.keys` import (RED). They go GREEN
once Task 3 ships the router.

Security contract (T-10-03): /status returns {connected, masked_label,
connected_at} only — encrypted_key (and any full sk-or-v1 value) NEVER appears
in the response.

Patches mirror test_demo_bootstrap.py: patch("routers.keys.get_supabase") and
clear app.dependency_overrides in a finally.
"""
from unittest.mock import MagicMock, patch


def test_status_returns_masked_only() -> None:
    """GET /status with a row {key_label, connected_at}: returns
    {connected:true, masked_label, connected_at}; encrypted_key never appears."""
    from fastapi.testclient import TestClient

    from auth import get_user_id
    from main import app

    mock_db = MagicMock()
    # Status select chain: db.table(..).select(..).eq(..).maybe_single().execute()
    status_chain = (
        mock_db.table.return_value.select.return_value.eq.return_value.maybe_single.return_value
    )
    status_chain.execute.return_value = MagicMock(
        data={"key_label": "sk-or-v1-…wXyZ", "connected_at": "2026-06-19T20:00:00+00:00"}
    )

    app.dependency_overrides[get_user_id] = lambda: "user-uuid"
    try:
        with patch("routers.keys.get_supabase", return_value=mock_db):
            resp = TestClient(app).get("/api/keys/status")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200, f"expected 200, got {resp.status_code}: {resp.text}"
    body = resp.json()
    assert body["connected"] is True
    assert body["masked_label"] == "sk-or-v1-…wXyZ"
    assert body["connected_at"] == "2026-06-19T20:00:00+00:00"
    # T-10-03: ciphertext column must never be in the response.
    assert "encrypted_key" not in resp.text


def test_status_not_connected() -> None:
    """GET /status with maybe_single() returning data=None: {connected:false}."""
    from fastapi.testclient import TestClient

    from auth import get_user_id
    from main import app

    mock_db = MagicMock()
    status_chain = (
        mock_db.table.return_value.select.return_value.eq.return_value.maybe_single.return_value
    )
    status_chain.execute.return_value = MagicMock(data=None)

    app.dependency_overrides[get_user_id] = lambda: "user-uuid"
    try:
        with patch("routers.keys.get_supabase", return_value=mock_db):
            resp = TestClient(app).get("/api/keys/status")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200, f"expected 200, got {resp.status_code}: {resp.text}"
    body = resp.json()
    assert body["connected"] is False
    # masked_label / connected_at default to None when not connected.
    assert body.get("masked_label") is None
    assert body.get("connected_at") is None


# ----- Phase 15 DEMO-01: demo_enabled must ride BOTH status branches -----
#
# The keyless early return (routers/keys.py) is the trap branch (RESEARCH
# Pitfall 3): keyless users are exactly the demo audience, so relying on the
# Pydantic default would hide the flag from them. The flag is controlled by
# patching routers.keys.get_settings (env-driven demo_fallback_enabled).

def _status_db(row: dict | None) -> MagicMock:
    """Fake supabase whose user_api_keys select chain returns `row` (or None)."""
    db = MagicMock()
    chain = (
        db.table.return_value.select.return_value.eq.return_value.maybe_single.return_value
    )
    chain.execute.return_value = MagicMock(data=row)
    return db


def test_status_keyless_carries_demo_enabled_true() -> None:
    """KEYLESS branch + flag ON → {"connected": false, "demo_enabled": true}.

    Pins the keys.py early-return trap (Pitfall 3 / T-15-01): the keyless branch
    must set demo_enabled EXPLICITLY, never via the Pydantic default."""
    from fastapi.testclient import TestClient

    from auth import get_user_id
    from main import app

    app.dependency_overrides[get_user_id] = lambda: "user-uuid"
    try:
        with patch("routers.keys.get_supabase", return_value=_status_db(None)), \
             patch(
                 "routers.keys.get_settings",
                 return_value=MagicMock(demo_fallback_enabled=True),
             ):
            resp = TestClient(app).get("/api/keys/status")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200, f"expected 200, got {resp.status_code}: {resp.text}"
    body = resp.json()
    assert body["connected"] is False
    assert body["demo_enabled"] is True, f"keyless branch dropped demo_enabled: {body}"


def test_status_connected_carries_demo_enabled_true() -> None:
    """CONNECTED branch + flag ON → connected true AND demo_enabled true."""
    from fastapi.testclient import TestClient

    from auth import get_user_id
    from main import app

    row = {"key_label": "sk-or-v1-…wXyZ", "connected_at": "2026-06-19T20:00:00+00:00"}

    app.dependency_overrides[get_user_id] = lambda: "user-uuid"
    try:
        with patch("routers.keys.get_supabase", return_value=_status_db(row)), \
             patch(
                 "routers.keys.get_settings",
                 return_value=MagicMock(demo_fallback_enabled=True),
             ):
            resp = TestClient(app).get("/api/keys/status")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200, f"expected 200, got {resp.status_code}: {resp.text}"
    body = resp.json()
    assert body["connected"] is True
    assert body["demo_enabled"] is True, f"connected branch dropped demo_enabled: {body}"


def test_status_demo_enabled_false_by_default() -> None:
    """Flag OFF (the config.py default) → demo_enabled false in BOTH branches."""
    from fastapi.testclient import TestClient

    from auth import get_user_id
    from main import app

    settings_off = MagicMock(demo_fallback_enabled=False)
    row = {"key_label": "sk-or-v1-…wXyZ", "connected_at": "2026-06-19T20:00:00+00:00"}

    app.dependency_overrides[get_user_id] = lambda: "user-uuid"
    try:
        with patch("routers.keys.get_supabase", return_value=_status_db(None)), \
             patch("routers.keys.get_settings", return_value=settings_off):
            keyless = TestClient(app).get("/api/keys/status")
        with patch("routers.keys.get_supabase", return_value=_status_db(row)), \
             patch("routers.keys.get_settings", return_value=settings_off):
            connected = TestClient(app).get("/api/keys/status")
    finally:
        app.dependency_overrides.clear()

    assert keyless.status_code == 200 and connected.status_code == 200
    assert keyless.json()["demo_enabled"] is False
    assert connected.json()["demo_enabled"] is False
