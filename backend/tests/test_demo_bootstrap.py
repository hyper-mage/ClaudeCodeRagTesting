"""Tests for /api/demo/bootstrap (PORT-01).

Test plan:
- test_sample_doc_file_exists           — REAL test (Plan 08-00 Wave 0): sample doc reachable via fixture
- test_seed_idempotent                  — Plan 08-02 Wave 1 Task 1: re-running seed for same user is a no-op
- test_seed_skips_permanent_user        — Plan 08-02 Wave 1 Task 2: router-level guard for permanent JWT
- test_bootstrap_endpoint_calls_seed_and_schedules_purge — Plan 08-02 Wave 1 Task 2: router wiring
"""
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


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


@pytest.mark.skip(reason="Wave 1 Task 2 stub — implemented later in Plan 08-02")
def test_seed_skips_permanent_user() -> None:
    pass


@pytest.mark.skip(reason="Wave 1 Task 2 stub — implemented later in Plan 08-02")
def test_bootstrap_endpoint_calls_seed_and_schedules_purge() -> None:
    pass
