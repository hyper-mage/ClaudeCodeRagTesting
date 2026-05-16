"""Tests for setup_tracing() — OBS-02 project-routing precedence (Pitfall 5).

Covers the three-tier precedence chain implemented in services/tracing.py:
  1. LANGSMITH_PROJECT env var (canonical SDK name) wins.
  2. LANGCHAIN_PROJECT env var (legacy name) used when canonical absent.
  3. settings.langsmith_project (pydantic-settings default) as final fallback.

Also asserts the no-op path (no LANGSMITH_API_KEY → zero env writes).
"""
import os
from unittest.mock import patch, MagicMock

import pytest

from services.tracing import setup_tracing


def _make_settings(api_key: str = "fake-key", project: str = "settings-default") -> MagicMock:
    """Build a MagicMock that mimics the Settings interface tracing reads."""
    settings = MagicMock()
    settings.langsmith_api_key = api_key
    settings.langchain_tracing_v2 = "true"
    settings.langsmith_project = project
    return settings


def test_setup_tracing_noop_when_api_key_missing(monkeypatch):
    """No LANGSMITH_API_KEY → setup_tracing returns early, writes no env vars."""
    monkeypatch.delenv("LANGCHAIN_PROJECT", raising=False)
    monkeypatch.delenv("LANGSMITH_PROJECT", raising=False)
    monkeypatch.delenv("LANGCHAIN_API_KEY", raising=False)
    monkeypatch.delenv("LANGCHAIN_TRACING_V2", raising=False)

    fake_settings = _make_settings(api_key="", project="boardgame-rag-dev")

    with patch("services.tracing.get_settings", return_value=fake_settings):
        setup_tracing()

    assert "LANGCHAIN_API_KEY" not in os.environ
    assert "LANGCHAIN_PROJECT" not in os.environ
    assert "LANGSMITH_PROJECT" not in os.environ
    assert "LANGCHAIN_TRACING_V2" not in os.environ


def test_setup_tracing_precedence_env_langsmith_wins(monkeypatch):
    """LANGSMITH_PROJECT env beats LANGCHAIN_PROJECT env AND settings default."""
    monkeypatch.setenv("LANGSMITH_PROJECT", "env-langsmith-wins")
    monkeypatch.setenv("LANGCHAIN_PROJECT", "env-langchain-loses")

    fake_settings = _make_settings(api_key="fake-key", project="settings-default")

    with patch("services.tracing.get_settings", return_value=fake_settings):
        setup_tracing()

    # Dual-write: both env-var aliases resolve to the SAME canonical value
    # (defense in depth — Pitfall 5).
    assert os.environ["LANGSMITH_PROJECT"] == "env-langsmith-wins"
    assert os.environ["LANGCHAIN_PROJECT"] == "env-langsmith-wins"
    assert os.environ["LANGCHAIN_API_KEY"] == "fake-key"
    assert os.environ["LANGCHAIN_TRACING_V2"] == "true"


def test_setup_tracing_falls_back_to_settings_when_no_env(monkeypatch):
    """Neither env var set → settings.langsmith_project becomes the value."""
    monkeypatch.delenv("LANGSMITH_PROJECT", raising=False)
    monkeypatch.delenv("LANGCHAIN_PROJECT", raising=False)

    fake_settings = _make_settings(api_key="fake-key", project="settings-default")

    with patch("services.tracing.get_settings", return_value=fake_settings):
        setup_tracing()

    assert os.environ["LANGSMITH_PROJECT"] == "settings-default"
    assert os.environ["LANGCHAIN_PROJECT"] == "settings-default"
    assert os.environ["LANGCHAIN_API_KEY"] == "fake-key"
    assert os.environ["LANGCHAIN_TRACING_V2"] == "true"


def test_setup_tracing_legacy_langchain_env_still_works(monkeypatch):
    """Legacy LANGCHAIN_PROJECT env (no canonical) gets promoted to both aliases."""
    monkeypatch.delenv("LANGSMITH_PROJECT", raising=False)
    monkeypatch.setenv("LANGCHAIN_PROJECT", "legacy-fallback")

    fake_settings = _make_settings(api_key="fake-key", project="settings-default")

    with patch("services.tracing.get_settings", return_value=fake_settings):
        setup_tracing()

    # Legacy env var resolved at tier 2; both aliases written to it (dual-write).
    assert os.environ["LANGSMITH_PROJECT"] == "legacy-fallback"
    assert os.environ["LANGCHAIN_PROJECT"] == "legacy-fallback"
