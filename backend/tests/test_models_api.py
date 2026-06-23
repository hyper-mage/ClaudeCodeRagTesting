"""Route-level tests for GET /api/models (MODEL-01 / MODEL-04, D-02 / D-04 / D-05).

Wave 0 (Plan 12-03) — written BEFORE routers.models exists, so on first run these
FAIL at the `from main import app` → `routers.models` import (RED). They go GREEN
once Task 2 ships the router + ModelResponse schema + main.py wiring.

Contract under test (the router COMPOSES the plan-01 pure functions, never reimplements):
  - test_free_only_filter            — ?free_only=true returns only is_free models (D-02),
                                        filtered server-side; gpt-4o-mini + openrouter/auto excluded.
  - test_first_request_populate      — an empty model_cache populates synchronously on the first
                                        read (never empty, D-05); fetch_catalog is invoked.
  - test_serve_stale_on_fetch_failure — stale rows present + fetch raises → the route serves the
                                        existing stale rows, status 200, no 5xx (D-04).

Patches mirror test_keys_status.py exactly:
  - app.dependency_overrides[get_user_id] = lambda: "user-uuid"   (auth gate, A4)
  - patch("routers.models.get_supabase", return_value=mock_db)
  - clear app.dependency_overrides in a finally.

Cache state is driven through the mock_db `.table("model_cache").select("*").execute().data`
chain. The upstream fetch is monkeypatched at the symbol the SERVICE imports it through
(`services.model_catalog_service.fetch_catalog`) since the router composes refresh_if_stale,
which calls fetch_catalog from that module. model_cache_ttl_seconds is forced to 0 (monkeypatch
on get_settings) so the populate/refresh tests always take the stale path.
"""
import json
import os
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

FIXTURE_PATH = os.path.join(
    os.path.dirname(__file__), "fixtures", "openrouter_models_sample.json"
)


def _load_fixture() -> list[dict]:
    """The 4 real-shape rows: gpt-4o-mini (paid), a :free model, openrouter/auto (-1
    sentinel), and a missing-pricing edge — reused from the plan 12-01 offline fixture."""
    with open(FIXTURE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)["data"]


def _cache_rows_from_fixture() -> list[dict]:
    """Map the raw fixture objects into model_cache row shape (model_id PK + is_free
    precomputed + fetched_at) so a within-cache select can return ready-to-serve rows."""
    now = datetime.now(timezone.utc).isoformat()
    rows = []
    for m in _load_fixture():
        mid = m.get("id", "")
        pricing = m.get("pricing") or {}
        is_free = mid.endswith(":free") or (
            pricing.get("prompt") == "0" and pricing.get("completion") == "0"
        )
        rows.append(
            {
                "model_id": mid,
                "name": m.get("name"),
                "context_length": m.get("context_length"),
                "pricing": pricing,
                "is_free": is_free,
                "raw": m,
                "fetched_at": now,
            }
        )
    return rows


def _force_ttl_zero(monkeypatch) -> None:
    """Force every read stale by setting the injectable TTL to 0 (MODEL-04 knob).

    refresh_if_stale + build_model_response read get_settings() at call time, so we
    patch the cached settings object's attribute rather than time-traveling.
    """
    from config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "model_cache_ttl_seconds", 0, raising=False)


def test_free_only_filter(monkeypatch) -> None:
    """GET /api/models?free_only=true returns ONLY is_free models, filtered server-side
    (D-02). The :free fixture row qualifies; gpt-4o-mini (paid) and openrouter/auto
    (-1 sentinel, not free) are excluded."""
    from fastapi.testclient import TestClient

    from auth import get_user_id
    from main import app

    # A fresh (within-TTL) cache so the route serves rows without a fetch.
    cache_rows = _cache_rows_from_fixture()
    mock_db = MagicMock()
    mock_db.table.return_value.select.return_value.execute.return_value = MagicMock(
        data=cache_rows
    )

    app.dependency_overrides[get_user_id] = lambda: "user-uuid"
    try:
        with patch("routers.models.get_supabase", return_value=mock_db):
            resp = TestClient(app).get("/api/models?free_only=true")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200, f"expected 200, got {resp.status_code}: {resp.text}"
    body = resp.json()
    assert len(body) > 0, "free_only filter returned nothing"
    ids = {m["id"] for m in body}
    # Every returned row is free; the paid + sentinel rows are gone.
    assert all(m["is_free"] is True for m in body), f"non-free model leaked: {body}"
    assert "meta-llama/llama-3.3-70b-instruct:free" in ids
    assert "openai/gpt-4o-mini" not in ids
    assert "openrouter/auto" not in ids


def test_first_request_populate(monkeypatch) -> None:
    """An empty model_cache populates synchronously on the first read (never empty, D-05).

    select returns [] (empty cache) → the route fetches via the monkeypatched
    fetch_catalog and serves the freshly upserted rows (>0). fetch_catalog IS invoked."""
    from fastapi.testclient import TestClient

    from auth import get_user_id
    from main import app

    _force_ttl_zero(monkeypatch)

    populated_rows = _cache_rows_from_fixture()
    fetch_called = {"count": 0}

    def _fake_fetch_catalog() -> list[dict]:
        fetch_called["count"] += 1
        return _load_fixture()

    monkeypatch.setattr(
        "services.model_catalog_service.fetch_catalog", _fake_fetch_catalog
    )

    # First select() = empty cache; the post-upsert re-select returns the populated rows.
    mock_db = MagicMock()
    select_exec = mock_db.table.return_value.select.return_value.execute
    select_exec.side_effect = [
        MagicMock(data=[]),               # initial select: cache empty
        MagicMock(data=populated_rows),   # re-select after upsert
    ]

    app.dependency_overrides[get_user_id] = lambda: "user-uuid"
    try:
        with patch("routers.models.get_supabase", return_value=mock_db):
            resp = TestClient(app).get("/api/models")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200, f"expected 200, got {resp.status_code}: {resp.text}"
    body = resp.json()
    assert len(body) > 0, "first-request populate returned an empty catalog (D-05 violated)"
    assert fetch_called["count"] == 1, "fetch_catalog was not invoked on an empty cache"


def test_serve_stale_on_fetch_failure(monkeypatch) -> None:
    """Stale rows present + fetch_catalog raises → the route serves the existing stale
    rows, status 200, no 5xx (D-04 — availability > freshness)."""
    from fastapi.testclient import TestClient

    from auth import get_user_id
    from main import app

    _force_ttl_zero(monkeypatch)  # force the stale path even though rows exist

    stale_rows = _cache_rows_from_fixture()

    def _boom() -> list[dict]:
        raise RuntimeError("upstream OpenRouter down")

    monkeypatch.setattr("services.model_catalog_service.fetch_catalog", _boom)

    # Cache HAS rows (stale per TTL=0); the fetch raises so the route serves these.
    mock_db = MagicMock()
    mock_db.table.return_value.select.return_value.execute.return_value = MagicMock(
        data=stale_rows
    )

    app.dependency_overrides[get_user_id] = lambda: "user-uuid"
    try:
        with patch("routers.models.get_supabase", return_value=mock_db):
            resp = TestClient(app).get("/api/models")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200, f"expected 200 (serve stale), got {resp.status_code}: {resp.text}"
    body = resp.json()
    assert len(body) == len(stale_rows), "serve-stale did not return the existing rows (D-04 violated)"
