"""Phase 11 Wave 0 scaffold — SEC-01 scrub + D-12 distinct error codes.

Covers the error-surfacing path (built in plan 11-04):
  - SEC-01: a str(e) carrying `sk-or-…` is scrubbed before it reaches the SSE
            error payload AND before it reaches any log line (incl. the exc_info
            traceback, via the `_ScrubFilter` logging.Filter — RESEARCH Open Q2).
  - D-12:   upstream 429 surfaces a `rate_limit` code; 402 a `payment_required`
            code — distinct, so the UI can disambiguate.

Wave 0 STUBS: collected green now; un-skipped + implemented by plan 11-04
(test_logging_filter_scrubs_exc_info is the SEC-01 "never in logs" closure,
implemented in plan 11-04 Task 2). Function names match the RESEARCH Test Map
verbatim.
"""
import pytest

_WAVE0 = "Wave 0 stub — turned green by plan 11-04"


@pytest.mark.skip(reason=_WAVE0)
def test_sk_or_scrubbed_in_sse_error():
    """SEC-01: an exception whose str() contains `sk-or-…` is scrubbed (via
    scrub_secrets) before it is yielded as an SSE error event — no sk-or- bleed."""
    raise NotImplementedError


@pytest.mark.skip(reason=_WAVE0)
def test_429_402_distinct_codes():
    """D-12: an upstream 429 surfaces code 'rate_limit'; a 402 surfaces
    'payment_required' — the two codes are distinct."""
    raise NotImplementedError


@pytest.mark.skip(reason=_WAVE0)
def test_logging_filter_scrubs_exc_info():
    """SEC-01 (logs closure): the _ScrubFilter (plan 11-04 Task 2) scrubs the
    FORMATTED record including the exc_info traceback — not just getMessage().
    Build a LogRecord with exc_info from an exception carrying `sk-or-v1-…`, pass
    it through the filter/handler, assert output has [redacted-key] and no sk-or-."""
    raise NotImplementedError
