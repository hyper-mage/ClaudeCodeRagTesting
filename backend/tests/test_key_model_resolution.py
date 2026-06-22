"""Phase 11 Wave 0 scaffold — DEMO-03 + SEC-04 + D-03 per-request key/model resolution.

Covers the `_resolve_key_and_model` seam (built in plan 11-04):
  - DEMO-03: keyless user fail-closed (flag OFF) vs owner-key + `:free` demo (flag ON)
  - SEC-04: decrypted user key threaded to all call sites; no cross-user bleed;
            fail-closed shape (never `user_key or owner_key`)
  - D-03:   model fall-through to owner default when thread/user_preferences absent

Every function below is a Wave 0 STUB: created + collected green now, un-skipped and
implemented by plan 11-04. Function names MUST match the RESEARCH Test Map verbatim
so plan 11-04's `<verify>` commands resolve.

Config-touching tests (when un-skipped) MUST follow each `monkeypatch.setenv(...)`
on a cached settings field with `get_settings.cache_clear()` (mirror
test_crypto_service.py:11-20) — get_settings() is @lru_cache'd.
"""
import pytest

_WAVE0 = "Wave 0 stub — turned green by plan 11-04"


@pytest.mark.skip(reason=_WAVE0)
def test_no_key_flag_off_refuses():
    """DEMO-03: keyless user + demo_fallback_enabled=False → mode=='no_key',
    api_key is None; caller yields structured no_api_key SSE error, makes NO LLM call."""
    raise NotImplementedError


@pytest.mark.skip(reason=_WAVE0)
def test_demo_fallback_uses_free_model():
    """DEMO-03: keyless user + demo_fallback_enabled=True → owner key +
    settings.demo_fallback_model (:free slug), mode=='demo', is_user_key False."""
    raise NotImplementedError


@pytest.mark.skip(reason=_WAVE0)
def test_user_key_threaded_to_all_call_sites():
    """SEC-04: a user-with-key turn uses the DECRYPTED user key (not owner) at
    all 4 call sites (main loop, retrieval, subagent, explorer)."""
    raise NotImplementedError


@pytest.mark.skip(reason=_WAVE0)
def test_no_cross_user_bleed():
    """SEC-04: two concurrent resolutions for different users never cross
    key/model (per-request resolution is NOT cached — Pitfall 8)."""
    raise NotImplementedError


@pytest.mark.skip(reason=_WAVE0)
def test_fail_closed_no_or_fallback():
    """SEC-04: _resolve_key_and_model never returns `user_key or owner_key`
    (fail-closed shape — a missing user key does NOT silently fall back to owner)."""
    raise NotImplementedError


@pytest.mark.skip(reason=_WAVE0)
def test_model_fallthrough_absent_p13_schema():
    """D-03: model resolves to the owner default when thread.model /
    user_preferences are absent (no crash on the not-yet-present P13 schema)."""
    raise NotImplementedError
