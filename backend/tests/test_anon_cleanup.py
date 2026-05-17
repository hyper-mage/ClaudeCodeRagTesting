"""Tests for purge_stale_anon_users (PORT-01 cleanup half).

Test plan:
- test_purge_filters_correctly       — Plan 08-02 Wave 1: only anon users older than threshold are deleted
- test_cascade_order                 — Plan 08-02 Wave 1: chunks → documents → storage → auth user order respected
- test_purge_swallows_per_user_errors — Plan 08-02 Wave 1: a single failed user does not abort the whole sweep
"""
import pytest


@pytest.mark.skip(reason="Wave 1 stub — implemented in Plan 08-02")
def test_purge_filters_correctly() -> None:
    pass


@pytest.mark.skip(reason="Wave 1 stub — implemented in Plan 08-02")
def test_cascade_order() -> None:
    pass


@pytest.mark.skip(reason="Wave 1 stub — implemented in Plan 08-02")
def test_purge_swallows_per_user_errors() -> None:
    pass
