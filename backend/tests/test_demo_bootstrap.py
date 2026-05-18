"""Tests for /api/demo/bootstrap (PORT-01).

Test plan:
- test_sample_doc_file_exists           — REAL test (Plan 08-00 Wave 0): sample doc reachable via fixture
- test_seed_idempotent                  — Plan 08-02 Wave 1 Task 1: re-running seed for same user is a no-op
- test_seed_skips_permanent_user        — Plan 08-02 Wave 1 Task 2: router-level guard for permanent JWT
- test_bootstrap_endpoint_calls_seed_and_schedules_purge — Plan 08-02 Wave 1 Task 2: router wiring
"""
from pathlib import Path
from unittest.mock import MagicMock, patch


def test_sample_doc_file_exists(seed_sample_doc_path: Path) -> None:
    """Sample doc exists, is non-empty, and is markdown text."""
    assert seed_sample_doc_path.exists(), f"missing sample doc: {seed_sample_doc_path}"
    assert seed_sample_doc_path.is_file()
    assert seed_sample_doc_path.suffix == ".md"
    size = seed_sample_doc_path.stat().st_size
    assert 0 < size <= 2_097_152, f"sample doc size {size} outside (0, 2 MB]"


def test_seed_idempotent() -> None:
    """Calling seed twice for the same user runs ingestion exactly once.

    First call: idempotency probe returns data=[] → full seed pipeline runs.
    Second call: idempotency probe returns one row → early return False;
    process_document must NOT have been called a second time.
    """
    from services.demo_service import seed_anon_user_content

    mock_db = MagicMock()

    # Idempotency probe chain: db.table("documents").select("id").eq(...).limit(1).execute()
    # First call returns data=[]; second call returns data=[{"id": "x"}].
    select_chain = mock_db.table.return_value.select.return_value.eq.return_value.limit.return_value
    select_chain.execute.side_effect = [
        MagicMock(data=[]),                # first call — proceed with seed
        MagicMock(data=[{"id": "x"}]),     # second call — idempotency hit
    ]

    # Generic insert chain returns a stable thread id so messages.insert anchors.
    mock_db.table.return_value.insert.return_value.execute.return_value = MagicMock(
        data=[{"id": "thread-uuid"}]
    )

    with patch("services.demo_service.get_supabase", return_value=mock_db), \
         patch("services.demo_service.check_duplicate", return_value=None), \
         patch("services.demo_service.process_document") as m_process:
        first = seed_anon_user_content("anon-uuid")
        second = seed_anon_user_content("anon-uuid")

    assert first is True, "first call should report True (seeded)"
    assert second is False, "second call should report False (idempotency hit)"
    assert m_process.call_count == 1, (
        f"process_document called {m_process.call_count} times — expected exactly 1"
    )


def test_bootstrap_endpoint_calls_seed_and_schedules_purge() -> None:
    """Anon-JWT POST: returns {seeded: True}, calls seed once, schedules purge."""
    from fastapi.testclient import TestClient

    from auth import get_user_id
    from main import app

    # Mock the supabase admin call to report the user as anonymous.
    anon_user_response = MagicMock()
    anon_user_response.user.is_anonymous = True
    mock_db = MagicMock()
    mock_db.auth.admin.get_user_by_id.return_value = anon_user_response

    app.dependency_overrides[get_user_id] = lambda: "anon-uuid"
    try:
        with patch("routers.demo.get_supabase", return_value=mock_db), \
             patch("routers.demo.seed_anon_user_content", return_value=True) as m_seed, \
             patch("routers.demo.purge_stale_anon_users") as m_purge:
            resp = TestClient(app).post("/api/demo/bootstrap")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200, f"expected 200, got {resp.status_code}: {resp.text}"
    assert resp.json() == {"seeded": True}, f"unexpected body: {resp.json()!r}"
    m_seed.assert_called_once_with("anon-uuid")
    # purge is dispatched as a BackgroundTask; TestClient runs it after the
    # response is sent, so it should also have been invoked exactly once.
    assert m_purge.call_count == 1, (
        f"purge_stale_anon_users called {m_purge.call_count} times — expected 1"
    )
    m_purge.assert_called_once_with(retention_days=7)


def test_seed_skips_permanent_user() -> None:
    """Permanent-JWT POST: returns {seeded: False}, seed NOT called (silent no-op)."""
    from fastapi.testclient import TestClient

    from auth import get_user_id
    from main import app

    permanent_user_response = MagicMock()
    permanent_user_response.user.is_anonymous = False
    mock_db = MagicMock()
    mock_db.auth.admin.get_user_by_id.return_value = permanent_user_response

    app.dependency_overrides[get_user_id] = lambda: "perm-uuid"
    try:
        with patch("routers.demo.get_supabase", return_value=mock_db), \
             patch("routers.demo.seed_anon_user_content", return_value=True) as m_seed, \
             patch("routers.demo.purge_stale_anon_users") as m_purge:
            resp = TestClient(app).post("/api/demo/bootstrap")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200, f"expected 200, got {resp.status_code}: {resp.text}"
    assert resp.json() == {"seeded": False}, f"unexpected body: {resp.json()!r}"
    m_seed.assert_not_called()
    m_purge.assert_not_called()
