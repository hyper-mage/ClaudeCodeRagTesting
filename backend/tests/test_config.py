"""Phase 6 SEC-05 + SEC-04 config defaults."""
import pytest


def test_chat_max_iterations_default():
    """Settings.chat_max_iterations defaults to 15 (D-08, D-09)."""
    from config import Settings
    s = Settings()
    assert s.chat_max_iterations == 15


def test_chat_max_iterations_env_override(monkeypatch):
    """CHAT_MAX_ITERATIONS env var overrides default."""
    monkeypatch.setenv("CHAT_MAX_ITERATIONS", "7")
    from config import Settings
    s = Settings()
    assert s.chat_max_iterations == 7


def test_chat_rate_limit_default():
    """Settings.chat_rate_limit defaults to '20/minute' (D-05)."""
    from config import Settings
    s = Settings()
    assert s.chat_rate_limit == "20/minute"


def test_chat_rate_limit_env_override(monkeypatch):
    """CHAT_RATE_LIMIT env var overrides default."""
    monkeypatch.setenv("CHAT_RATE_LIMIT", "5/minute")
    from config import Settings
    s = Settings()
    assert s.chat_rate_limit == "5/minute"


def test_key_encryption_secret_default():
    """Settings.key_encryption_secret defaults to empty string (D-04)."""
    from config import Settings
    s = Settings()
    assert s.key_encryption_secret == ""


def test_key_encryption_secret_env_override(monkeypatch):
    """KEY_ENCRYPTION_SECRET env var overrides default."""
    monkeypatch.setenv("KEY_ENCRYPTION_SECRET", "abc")
    from config import Settings
    s = Settings()
    assert s.key_encryption_secret == "abc"


# ---------------------------------------------------------------------
# Phase 11 SEC-01 / DEMO-03: demo-fallback config + scrub_secrets helper
# ---------------------------------------------------------------------


def test_demo_fallback_enabled_default():
    """Settings.demo_fallback_enabled defaults to False — fail-closed in dev AND
    prod this phase (D-09). The owner-key spend branch is structurally gated OFF."""
    from config import Settings
    s = Settings()
    assert s.demo_fallback_enabled is False


def test_demo_fallback_enabled_env_override(monkeypatch):
    """DEMO_FALLBACK_ENABLED env var overrides default to True."""
    monkeypatch.setenv("DEMO_FALLBACK_ENABLED", "true")
    from config import Settings
    s = Settings()
    assert s.demo_fallback_enabled is True


def test_demo_fallback_model_default():
    """Settings.demo_fallback_model defaults to a non-empty `:free` slug (D-06)."""
    from config import Settings
    s = Settings()
    assert s.demo_fallback_model
    assert s.demo_fallback_model.endswith(":free")


def test_demo_fallback_model_env_override(monkeypatch):
    """DEMO_FALLBACK_MODEL env var overrides default."""
    monkeypatch.setenv("DEMO_FALLBACK_MODEL", "x/y:free")
    from config import Settings
    s = Settings()
    assert s.demo_fallback_model == "x/y:free"


def test_scrub_secrets_redacts():
    """scrub_secrets redacts any sk-or- prefixed key to [redacted-key] (SEC-01)."""
    from services.log_scrub import scrub_secrets
    out = scrub_secrets("err sk-or-v1-ABC123def_-")
    assert "sk-or-" not in out
    assert "[redacted-key]" in out


def test_scrub_secrets_passthrough():
    """scrub_secrets passes non-str values through unchanged."""
    from services.log_scrub import scrub_secrets
    assert scrub_secrets(123) == 123


# ---------------------------------------------------------------------
# Phase 12 MODEL-04 / D-03: model cache TTL config
# ---------------------------------------------------------------------


def test_model_cache_ttl_default():
    """Settings.model_cache_ttl_seconds defaults to 86400 (24h TTL, D-03)."""
    from config import Settings
    s = Settings()
    assert s.model_cache_ttl_seconds == 86400


def test_model_cache_ttl_env_override(monkeypatch):
    """MODEL_CACHE_TTL_SECONDS env var overrides default (injectable for MODEL-04 tests)."""
    monkeypatch.setenv("MODEL_CACHE_TTL_SECONDS", "0")
    from config import Settings
    s = Settings()
    assert s.model_cache_ttl_seconds == 0
