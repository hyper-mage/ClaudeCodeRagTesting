"""Phase 6 SEC-05 + SEC-04 config defaults.

Placeholders for Wave 0. Wave 1 06-01/06-02 flip green when fields land
in backend/config.py:Settings.
"""
import pytest


@pytest.mark.skip(reason="Wave 1 06-02: chat_max_iterations field added")
def test_chat_max_iterations_default():
    """Settings.chat_max_iterations defaults to 15 (D-08, D-09)."""
    from config import Settings
    s = Settings()
    assert s.chat_max_iterations == 15


@pytest.mark.skip(reason="Wave 1 06-02: chat_max_iterations env override")
def test_chat_max_iterations_env_override(monkeypatch):
    """CHAT_MAX_ITERATIONS env var overrides default."""
    monkeypatch.setenv("CHAT_MAX_ITERATIONS", "7")
    from config import Settings
    s = Settings()
    assert s.chat_max_iterations == 7


@pytest.mark.skip(reason="Wave 1 06-01: chat_rate_limit field added")
def test_chat_rate_limit_default():
    """Settings.chat_rate_limit defaults to '20/minute' (D-05)."""
    from config import Settings
    s = Settings()
    assert s.chat_rate_limit == "20/minute"


@pytest.mark.skip(reason="Wave 1 06-01: chat_rate_limit env override")
def test_chat_rate_limit_env_override(monkeypatch):
    """CHAT_RATE_LIMIT env var overrides default."""
    monkeypatch.setenv("CHAT_RATE_LIMIT", "5/minute")
    from config import Settings
    s = Settings()
    assert s.chat_rate_limit == "5/minute"
