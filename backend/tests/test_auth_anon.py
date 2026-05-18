"""Tests for backend/auth.py acceptance of Supabase anon JWTs (T-08-01, Pitfall 1).

Plan 08-01 Wave 1 — landed by no-op path (provisional 08-00 SUMMARY: aud == "authenticated").

Coverage:
- test_anon_jwt_accepted_by_get_user_id  — anon JWT passes verification; get_user_id returns sub
- test_permanent_jwt_still_accepted      — permanent JWT acceptance is not regressed
- test_invalid_aud_rejected              — InvalidTokenError surface → HTTPException(401) "Invalid token"
- test_missing_sub_claim_rejected        — payload lacking `sub` → HTTPException(401) "Invalid token: no sub claim"

All tests are offline: jwt.decode + jwt.get_unverified_header are patched; no JWKS HTTP roundtrip.
"""
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException, Request

from config import Settings


def _build_request(token: str = "fake.jwt.token") -> Request:
    """Build a minimal Starlette/FastAPI Request with an Authorization header and a writable state.

    `auth.get_user_id` reads `request.headers.get("Authorization")` and writes `request.state.user_id`.
    A minimal ASGI scope is enough to exercise both paths without booting a TestClient.
    """
    scope = {
        "type": "http",
        "headers": [(b"authorization", f"Bearer {token}".encode("ascii"))],
        "state": {},
    }
    return Request(scope)


def _build_settings_stub() -> Settings:
    """A Settings stand-in carrying just `supabase_jwt_secret` — the only attr the HS256 branch reads."""
    settings = MagicMock(spec=Settings)
    settings.supabase_jwt_secret = "dummy-test-secret"
    return settings


def test_anon_jwt_accepted_by_get_user_id(anon_jwt: str, mock_user_id: str) -> None:
    """Anon JWT (is_anonymous=True, role=authenticated) flows through get_user_id without 401.

    Patches jwt.decode to simulate a valid anon payload; asserts:
      - return value equals the decoded `sub` claim,
      - request.state.user_id is set (SEC-04 slowapi key-func bridge — Phase 6 D-04).
    """
    from auth import get_user_id

    anon_payload = {
        "sub": mock_user_id,
        "aud": "authenticated",  # post-Plan-08-00 verification: anon shares "authenticated"
        "role": "authenticated",
        "is_anonymous": True,
    }

    request = _build_request(token=anon_jwt)
    settings = _build_settings_stub()

    with patch("auth.jwt.get_unverified_header", return_value={"alg": "HS256"}), \
         patch("auth.jwt.decode", return_value=anon_payload):
        result = get_user_id(request, settings)

    assert result == mock_user_id, f"expected get_user_id to return sub={mock_user_id!r}, got {result!r}"
    assert getattr(request.state, "user_id", None) == mock_user_id, (
        "request.state.user_id was not set — SEC-04 slowapi key-func bridge is broken"
    )


def test_permanent_jwt_still_accepted(permanent_jwt: str, mock_user_id: str) -> None:
    """Permanent (email/password) JWT continues to be accepted — no regression from Plan 08-01.

    Same shape as the anon test but with is_anonymous=False; behavior must be identical.
    """
    from auth import get_user_id

    permanent_payload = {
        "sub": mock_user_id,
        "aud": "authenticated",
        "role": "authenticated",
        "is_anonymous": False,
    }

    request = _build_request(token=permanent_jwt)
    settings = _build_settings_stub()

    with patch("auth.jwt.get_unverified_header", return_value={"alg": "HS256"}), \
         patch("auth.jwt.decode", return_value=permanent_payload):
        result = get_user_id(request, settings)

    assert result == mock_user_id, f"expected get_user_id to return sub={mock_user_id!r}, got {result!r}"
    assert getattr(request.state, "user_id", None) == mock_user_id


def test_invalid_aud_rejected() -> None:
    """A JWT whose `aud` does not match the verifier policy must yield HTTPException(401).

    auth.py catches `jwt.InvalidTokenError` (parent class of InvalidAudienceError) and raises
    HTTPException(401, detail="Invalid token"). We simulate by raising InvalidTokenError directly.
    """
    import jwt as pyjwt
    from auth import get_user_id

    request = _build_request(token="invalid.aud.token")
    settings = _build_settings_stub()

    with patch("auth.jwt.get_unverified_header", return_value={"alg": "HS256"}), \
         patch("auth.jwt.decode", side_effect=pyjwt.InvalidTokenError("audience mismatch")):
        with pytest.raises(HTTPException) as excinfo:
            get_user_id(request, settings)

    assert excinfo.value.status_code == 401, (
        f"expected 401 on invalid aud, got {excinfo.value.status_code}"
    )
    assert excinfo.value.detail == "Invalid token", (
        f"expected detail='Invalid token', got {excinfo.value.detail!r}"
    )


def test_missing_sub_claim_rejected() -> None:
    """A decoded payload without a `sub` claim must yield HTTPException(401, 'Invalid token: no sub claim').

    Defends against silently returning None / empty string as a user_id — which would corrupt
    RLS scoping downstream (request.state.user_id is consumed by slowapi key_func + DB queries).
    """
    from auth import get_user_id

    payload_no_sub = {"aud": "authenticated"}  # no `sub` key

    request = _build_request(token="no.sub.token")
    settings = _build_settings_stub()

    with patch("auth.jwt.get_unverified_header", return_value={"alg": "HS256"}), \
         patch("auth.jwt.decode", return_value=payload_no_sub):
        with pytest.raises(HTTPException) as excinfo:
            get_user_id(request, settings)

    assert excinfo.value.status_code == 401, (
        f"expected 401 on missing sub claim, got {excinfo.value.status_code}"
    )
    assert excinfo.value.detail == "Invalid token: no sub claim", (
        f"expected detail='Invalid token: no sub claim', got {excinfo.value.detail!r}"
    )
