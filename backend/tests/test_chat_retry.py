"""Tests for retry-aware POST /api/threads/{id}/messages (PORT-02, T-08-03).

Test plan:
- test_retry_deletes_prior_failed_assistant_row — Plan 08-03 Wave 1: ?retry=true deletes the orphan empty assistant row before streaming
- test_non_retry_path_unchanged                 — Plan 08-03 Wave 1: default POST path has no extra DELETE
"""
import pytest


@pytest.mark.skip(reason="Wave 1 stub — implemented in Plan 08-03")
def test_retry_deletes_prior_failed_assistant_row() -> None:
    pass


@pytest.mark.skip(reason="Wave 1 stub — implemented in Plan 08-03")
def test_non_retry_path_unchanged() -> None:
    pass
