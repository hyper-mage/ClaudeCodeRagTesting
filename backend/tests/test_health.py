"""Tests for /api/health (OBS-04): DB-reachability probe + 503 envelope + limiter exemption."""
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def _build_mock_db_chain(raise_on_execute: bool = False) -> MagicMock:
    """Build a MagicMock matching the supabase-py call chain used by /api/health.

    Chain: db.table("documents").select("id", count="exact", head=True).limit(1).execute()
    """
    mock_db = MagicMock()
    execute_mock = mock_db.table.return_value.select.return_value.limit.return_value.execute
    if raise_on_execute:
        execute_mock.side_effect = Exception("connection refused")
    else:
        execute_mock.return_value = MagicMock()
    return mock_db


def test_health_ok():
    """Returns 200 + {"status": "ok"} when supabase-py call succeeds."""
    mock_db = _build_mock_db_chain(raise_on_execute=False)
    with patch("main.get_supabase", return_value=mock_db):
        resp = client.get("/api/health")
    assert resp.status_code == 200, f"expected 200, got {resp.status_code}"
    assert resp.json() == {"status": "ok"}


def test_health_degraded_when_supabase_raises():
    """Returns 503 + locked degraded envelope when DB probe raises any Exception."""
    mock_db = _build_mock_db_chain(raise_on_execute=True)
    with patch("main.get_supabase", return_value=mock_db):
        resp = client.get("/api/health")
    assert resp.status_code == 503, f"expected 503, got {resp.status_code}"
    assert resp.json() == {"status": "degraded", "db": "unreachable"}


def test_health_actually_calls_supabase_documents_table():
    """Pins the locked DB probe shape: documents/select(id, count=exact, head=True)/limit(1).execute.

    Defends T-07-11 (refactor silently weakens probe to a no-op).
    """
    mock_db = _build_mock_db_chain(raise_on_execute=False)
    with patch("main.get_supabase", return_value=mock_db):
        resp = client.get("/api/health")
    assert resp.status_code == 200

    # .table("documents")
    assert mock_db.table.called, "handler did not call db.table(...)"
    assert mock_db.table.call_args.args == ("documents",), (
        f"expected table('documents'), got {mock_db.table.call_args.args!r}"
    )

    # .select("id", count="exact", head=True)
    select_mock = mock_db.table.return_value.select
    assert select_mock.called, "handler did not call .select(...)"
    assert select_mock.call_args.args == ("id",), (
        f"expected select('id', ...), got args {select_mock.call_args.args!r}"
    )
    assert select_mock.call_args.kwargs == {"count": "exact", "head": True}, (
        f"expected kwargs count='exact', head=True; got {select_mock.call_args.kwargs!r}"
    )

    # .limit(1)
    limit_mock = mock_db.table.return_value.select.return_value.limit
    assert limit_mock.called, "handler did not call .limit(...)"
    assert limit_mock.call_args.args == (1,), (
        f"expected limit(1), got {limit_mock.call_args.args!r}"
    )

    # .execute()
    execute_mock = (
        mock_db.table.return_value.select.return_value.limit.return_value.execute
    )
    assert execute_mock.called, "handler did not call .execute()"


def test_health_route_has_no_limiter_decorator():
    """Pins the rate-limit-exempt invariant (RESEARCH Pitfall 7 + CONTEXT decision 2).

    Two-pronged assertion:
    1. Inspect the registered FastAPI route's endpoint for slowapi attributes
    2. Source-grep main.py for a @limiter.limit / @limiter.exempt decorator immediately
       above the health handler.
    """
    # 1) Route-level inspection: find /api/health and assert no slowapi attrs
    health_route = next(
        (r for r in app.routes if getattr(r, "path", None) == "/api/health"),
        None,
    )
    assert health_route is not None, "expected /api/health route to be registered"
    endpoint = health_route.endpoint
    assert not hasattr(endpoint, "_rate_limits"), (
        "endpoint has slowapi _rate_limits attribute — health route is decorated"
    )

    # 2) Source-grep: look at the lines above `async def health` for a decorator
    main_py = Path(__file__).resolve().parent.parent / "main.py"
    source = main_py.read_text(encoding="utf-8").splitlines()
    health_line_idx = next(
        (i for i, line in enumerate(source) if line.strip().startswith("async def health")),
        None,
    )
    assert health_line_idx is not None, "could not locate `async def health` in main.py"

    # Inspect the 3 lines above the function signature for limiter decorators.
    # Skip the @app.get(...) decorator line — only flag slowapi decorations.
    for offset in (1, 2, 3):
        idx = health_line_idx - offset
        if idx < 0:
            break
        line = source[idx]
        assert "@limiter.limit" not in line, (
            f"main.py line {idx + 1} contains @limiter.limit above health handler: {line!r}"
        )
        assert "@limiter.exempt" not in line, (
            f"main.py line {idx + 1} contains @limiter.exempt above health handler: {line!r}"
        )
