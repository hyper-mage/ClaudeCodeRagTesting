"""Tests for /api/demo/bootstrap (PORT-01).

Test plan:
- test_sample_doc_file_exists           — REAL test (Plan 08-00 Wave 0): sample doc reachable via fixture
- test_seed_idempotent                  — Plan 08-02 Wave 1: re-running seed for same user does not duplicate rows
- test_seed_skips_permanent_user        — Plan 08-02 Wave 1: bootstrap refuses to seed if caller's JWT lacks is_anonymous=True
- test_bootstrap_endpoint_calls_seed_and_schedules_purge — Plan 08-02 Wave 1: router wiring
"""
from pathlib import Path

import pytest


def test_sample_doc_file_exists(seed_sample_doc_path: Path) -> None:
    """Sample doc exists, is non-empty, and is markdown text."""
    assert seed_sample_doc_path.exists(), f"missing sample doc: {seed_sample_doc_path}"
    assert seed_sample_doc_path.is_file()
    assert seed_sample_doc_path.suffix == ".md"
    size = seed_sample_doc_path.stat().st_size
    assert 0 < size <= 2_097_152, f"sample doc size {size} outside (0, 2 MB]"


@pytest.mark.skip(reason="Wave 1 stub — implemented in Plan 08-02")
def test_seed_idempotent() -> None:
    pass


@pytest.mark.skip(reason="Wave 1 stub — implemented in Plan 08-02")
def test_seed_skips_permanent_user() -> None:
    pass


@pytest.mark.skip(reason="Wave 1 stub — implemented in Plan 08-02")
def test_bootstrap_endpoint_calls_seed_and_schedules_purge() -> None:
    pass
