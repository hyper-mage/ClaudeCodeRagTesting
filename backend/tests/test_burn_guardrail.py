"""SEC-03 (no-spend half) — pure-logic unit tests for the owner-key burn script.

These tests exercise the PURE, importable helpers of
``backend/scripts/burn_owner_guardrail.py`` with ZERO network calls and ZERO
real-money spend. They pin the three independent safety bounds the live trip
(Plan 02) relies on:

  - ``-k abort``    : ``should_abort`` hard-aborts at the $0.25 ceiling (D-06) and
                      at the MAX_CALLS=300 call ceiling.
  - ``-k classify`` : ``classify_status`` maps 402/403 -> blocked, 429 ->
                      rate_limited, everything else -> unexpected (D-04 / RESEARCH
                      Open Q1 — 402 vs 403 left ambiguous on purpose).
  - ``-k spend``    : ``next_batch_size`` never plans a batch whose worst-case
                      added cost crosses the $0.25 hard abort, returns >= 1, and
                      shrinks toward 1 as the running total approaches the $0.10
                      trip target (Pitfall 3 — bound the overshoot).
  - ``-k scrub``    : ``format_block_record`` routes its output through
                      ``scrub_secrets`` so a synthetic ``sk-or-…`` token in a
                      provider error body is redacted, never echoed (SEC-01).

Run: cd backend && venv/Scripts/python.exe -m pytest tests/test_burn_guardrail.py -x
"""
import httpx
import openai

# RED until Plan 999.2-01 Task 2 creates the module — this import IS the RED state.
from scripts.burn_owner_guardrail import (
    should_abort,
    classify_status,
    next_batch_size,
    format_block_record,
    TRIP_TARGET,
    HARD_ABORT,
    MAX_CALLS,
)


def _status_error(status_code: int, message: str) -> openai.APIStatusError:
    """Construct a real openai.APIStatusError (or RateLimitError) with a status_code.

    Copied verbatim from tests/test_error_surfacing.py:122-127 so the burn-script
    classifier is tested against the SAME typed-error objects the chat path sees.
    """
    req = httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
    resp = httpx.Response(status_code, request=req)
    cls = openai.RateLimitError if status_code == 429 else openai.APIStatusError
    return cls(message, response=resp, body=None)


# ---------------------------------------------------------------------
# Constants sanity — the three bounds are pinned to their D-06 values.
# ---------------------------------------------------------------------

def test_constants_match_d06_bounds():
    assert TRIP_TARGET == 0.10
    assert HARD_ABORT == 0.25
    assert MAX_CALLS == 300


# ---------------------------------------------------------------------
# -k abort — hard abort at the $0.25 ceiling AND the MAX_CALLS ceiling.
# ---------------------------------------------------------------------

def test_should_abort_thresholds():
    # Below both ceilings → keep going.
    assert should_abort(0.0, 0) is None
    assert should_abort(0.10, 50) is None
    assert should_abort(0.249, 299) is None

    # At/over the $0.25 hard abort → BLOCKER (guardrail did NOT trip in time).
    assert should_abort(0.25, 0) == "BLOCKER_NO_TRIP_AT_ABORT"
    assert should_abort(0.30, 5) == "BLOCKER_NO_TRIP_AT_ABORT"

    # At/over the call ceiling → BLOCKER (too many calls without a trip).
    assert should_abort(0.0, 300) == "BLOCKER_CALL_CEILING"
    assert should_abort(0.05, 301) == "BLOCKER_CALL_CEILING"

    # Spend ceiling takes priority when both are crossed.
    assert should_abort(0.25, 300) == "BLOCKER_NO_TRIP_AT_ABORT"


# ---------------------------------------------------------------------
# -k classify — 402/403 blocked, 429 rate_limited, else unexpected.
# ---------------------------------------------------------------------

def test_classify_status_maps_codes():
    assert classify_status(402) == "blocked"
    assert classify_status(403) == "blocked"
    assert classify_status(429) == "rate_limited"
    assert classify_status(400) == "unexpected"
    assert classify_status(401) == "unexpected"
    assert classify_status(500) == "unexpected"


def test_classify_status_from_real_typed_errors():
    """Assert against the .status_code of real openai typed errors (the loop reads
    e.status_code, so prove the classifier agrees on the genuine objects)."""
    assert classify_status(_status_error(402, "payment required").status_code) == "blocked"
    assert classify_status(_status_error(403, "forbidden").status_code) == "blocked"
    assert classify_status(_status_error(429, "rate limited").status_code) == "rate_limited"
    assert classify_status(_status_error(500, "server error").status_code) == "unexpected"


# ---------------------------------------------------------------------
# -k spend — adaptive batch sizing never overshoots the $0.25 hard abort
# and shrinks toward 1 as the running total approaches the $0.10 trip.
# ---------------------------------------------------------------------

def test_spend_sizing_never_exceeds_hard_ceiling():
    # Worst-case added cost (size * max_cost_per_call) must never cross HARD_ABORT,
    # and the batch must always be at least one call.
    pairs = [
        (0.0, 0.005),
        (0.05, 0.005),
        (0.09, 0.005),
        (0.099, 0.005),
        (0.0, 0.01),
        (0.20, 0.01),
        (0.0, 0.05),
    ]
    for running_total, max_cost in pairs:
        size = next_batch_size(running_total, max_cost)
        assert size >= 1, (running_total, max_cost, size)
        worst_case = running_total + size * max_cost
        assert worst_case <= HARD_ABORT + 1e-9, (running_total, max_cost, size, worst_case)


def test_spend_sizing_shrinks_toward_one_near_trip_target():
    far = next_batch_size(0.0, 0.005)        # plenty of headroom
    near = next_batch_size(0.09, 0.005)      # close to the $0.10 trip
    closest = next_batch_size(0.099, 0.005)  # essentially at the trip

    assert far >= near >= closest >= 1
    assert closest == 1  # at the trip target, probe one call at a time


# ---------------------------------------------------------------------
# -k scrub — a synthetic sk-or-… in a provider body is redacted (SEC-01).
# ---------------------------------------------------------------------

def test_scrub_redacts_key_in_block_record():
    leaked = "sk-or-v1-LEAKEDSECRETKEY1234567890"
    body = f'{{"error":{{"message":"blocked by guardrail with key {leaked}"}}}}'

    record = format_block_record(403, body, 0.11)

    assert "sk-or-" not in record, f"sk-or- leaked into block record: {record}"
    assert "[redacted-key]" in record
    # The non-secret context survives the scrub.
    assert "403" in record
