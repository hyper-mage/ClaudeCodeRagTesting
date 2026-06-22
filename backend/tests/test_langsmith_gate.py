"""Phase 11 Wave 0 scaffold — SEC-01 LangSmith wrap-gate (D-10).

Covers the `wrap_openai` gate (built in plan 11-03/11-04): when a turn runs on a
USER key, the OpenAI client MUST NOT be wrapped with LangSmith tracing (so a
user's key/traffic is never sent to the owner's LangSmith project). Owner/demo
turns ARE wrapped.

Wave 0 STUB: collected green now, un-skipped + implemented downstream. Function
name matches the RESEARCH Test Map verbatim.
"""
import pytest

_WAVE0 = "Wave 0 stub — turned green by plan 11-03/11-04"


@pytest.mark.skip(reason=_WAVE0)
def test_user_key_client_not_wrapped():
    """SEC-01: get_llm_client(trace=False) (user key) returns the bare OpenAI
    instance — wrap_openai is NOT applied; owner/demo (trace=True) IS wrapped."""
    raise NotImplementedError
