"""Tests for backend/auth.py acceptance of Supabase anon JWTs (T-08-01, Pitfall 1).

Test plan:
- test_anon_jwt_accepted_by_get_user_id  — Plan 08-01 Wave 1: anon JWT passes verify_jwt → get_user_id returns sub
- test_permanent_jwt_still_accepted      — Plan 08-01 Wave 1: permanent JWT acceptance is not regressed by the widening
"""
import pytest


@pytest.mark.skip(reason="Wave 1 stub — implemented in Plan 08-01")
def test_anon_jwt_accepted_by_get_user_id() -> None:
    pass


@pytest.mark.skip(reason="Wave 1 stub — implemented in Plan 08-01")
def test_permanent_jwt_still_accepted() -> None:
    pass
