"""Phase 11 Wave 0 scaffold — SEC-01 LangSmith wrap-gate (D-10).

Covers the `wrap_openai` gate (built in plan 11-03/11-04): when a turn runs on a
USER key, the OpenAI client MUST NOT be wrapped with LangSmith tracing (so a
user's key/traffic is never sent to the owner's LangSmith project). Owner/demo
turns ARE wrapped.

Un-skipped + implemented in plan 11-03. Function name matches the RESEARCH Test
Map verbatim.
"""
from unittest.mock import MagicMock, patch

from openai import OpenAI

from services import llm_service


def test_user_key_client_not_wrapped():
    """SEC-01: get_llm_client(trace=False) (user key) returns the bare OpenAI
    instance — wrap_openai is NOT applied; owner/demo (trace=True) IS wrapped."""
    # A wrapper that tags whatever it receives so we can detect application.
    wrapped_sentinel = MagicMock(name="wrapped_client")

    def _fake_wrap(client):
        return wrapped_sentinel

    fake_settings = MagicMock()
    fake_settings.resolved_llm_api_key = "sk-or-v1-owner"
    fake_settings.llm_base_url = "https://openrouter.ai/api/v1"
    fake_settings.langsmith_api_key = "ls-test-key"

    with patch.object(llm_service, "wrap_openai", _fake_wrap), \
         patch.object(llm_service, "get_settings", return_value=fake_settings):
        # User-key call (trace=False) → wrapper SKIPPED → bare client.
        user_client = llm_service.get_llm_client(api_key="sk-or-v1-userkey", trace=False)
        assert isinstance(user_client, OpenAI)
        assert user_client is not wrapped_sentinel

        # Owner/demo call (trace=True) with langsmith key set → wrapper APPLIED.
        owner_client = llm_service.get_llm_client(trace=True)
        assert owner_client is wrapped_sentinel
