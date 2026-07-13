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


# ---------------------------------------------------------------------
# Phase 16 WSRCH-02 / D-04: web_search_depth config + tvly- scrub (RED until 16-02)
# ---------------------------------------------------------------------


def test_web_search_depth_default():
    """Settings.web_search_depth defaults to 'basic' (D-04). RED — the field does not
    exist yet (added by plan 16-02 Task 1); accessing it raises AttributeError."""
    from config import Settings
    s = Settings()
    assert s.web_search_depth == "basic"


def test_web_search_depth_env_override(monkeypatch):
    """WEB_SEARCH_DEPTH env var overrides default (owner can raise to 'advanced'
    without a code change)."""
    monkeypatch.setenv("WEB_SEARCH_DEPTH", "advanced")
    from config import Settings
    s = Settings()
    assert s.web_search_depth == "advanced"


def test_scrub_secrets_redacts_tavily():
    """scrub_secrets redacts a tvly- prefixed Tavily key to [redacted-key] (Phase 16
    security). RED — log_scrub only matches sk-or- today, so tvly- passes through."""
    from services.log_scrub import scrub_secrets
    out = scrub_secrets("err tvly-ABC123def_-")
    assert "tvly-" not in out
    assert "[redacted-key]" in out


# ---------------------------------------------------------------------
# Phase 17 D-02 / D-03 — system_prompt split into operational base + persona voice
# (RED until 17-04 strips config.system_prompt to the persona-agnostic base).
# Env-isolated via monkeypatch.delenv("SYSTEM_PROMPT") — mirrors test_web_search's
# citation-guidance test — so a local .env override cannot mask the shipped default.
# ---------------------------------------------------------------------


def test_system_prompt_operational_base_keeps_citation(monkeypatch):
    """D-02: the operational base RETAINS the citation guidance ("Sources:" + inline)
    after the base/voice split — this keeps test_web_search::test_system_prompt_citation
    _guidance GREEN. Passes today (regression guard); must stay GREEN through 17-04."""
    import config  # ensures load_dotenv has run before we drop the override
    monkeypatch.delenv("SYSTEM_PROMPT", raising=False)
    prompt = config.Settings().system_prompt
    assert "Sources:" in prompt
    assert "inline" in prompt.lower()


def test_system_prompt_operational_base_drops_kb_first_bias(monkeypatch):
    """D-03: the KB-first bias ("Prefer the knowledge base") moves OUT of the base and
    INTO the Expert voice_block — the operational base no longer carries it. RED today
    (the current bundled system_prompt still contains the bias)."""
    import config
    monkeypatch.delenv("SYSTEM_PROMPT", raising=False)
    prompt = config.Settings().system_prompt
    assert "Prefer the knowledge base" not in prompt


def test_system_prompt_operational_base_drops_opener(monkeypatch):
    """Pattern A1: the "You are a helpful assistant" opener moves into each persona
    voice_block (exactly one "You are…" leads the composed prompt) — the base no longer
    opens with it. RED today (the current base still starts with the opener)."""
    import config
    monkeypatch.delenv("SYSTEM_PROMPT", raising=False)
    prompt = config.Settings().system_prompt
    assert not prompt.startswith("You are a helpful assistant")
