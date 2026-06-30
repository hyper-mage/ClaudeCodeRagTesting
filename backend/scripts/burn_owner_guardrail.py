r"""SEC-03 live trip-test — burn the PROD owner OpenRouter account to its $0.10 guardrail.

DANGER: this script spends REAL money. It deliberately mints PAID
``openai/gpt-4o-mini`` completions on the PROD owner/demo-funding account (the
account behind ``settings.resolved_llm_api_key`` in ``.env.prod`` — D-01) until
OpenRouter's pre-configured $0.10 cost guardrail (D-05b) BLOCKS further calls,
recording the observed HTTP status + scrubbed body as the SEC-03 evidence.

It is SAFE BY DEFAULT: it refuses to run (exit non-zero, ZERO network) unless BOTH
``--confirm`` is passed AND ``ENV_FILE`` resolves to ``.env.prod``. Three independent
spend bounds cap exposure (D-06): the ``--confirm`` + prod-env gate, a $0.25 HARD
abort (2.5x the trip target), and a MAX_CALLS=300 ceiling, with serial small
batches sized so worst-case overshoot is bounded.

This module is also imported by tests/test_burn_guardrail.py for its PURE helpers
(should_abort / classify_status / next_batch_size / format_block_record) — those run
with ZERO spend and ZERO network. The live burn is Plan 02, a human-gated operator
run; nothing here runs automatically.

Run (prod target, D-01) — set ENV_FILE in the shell BEFORE launch:
    cd backend && ENV_FILE=.env.prod venv/Scripts/python.exe scripts/burn_owner_guardrail.py --confirm
    # PowerShell: $env:ENV_FILE=".env.prod"; venv\Scripts\python.exe scripts\burn_owner_guardrail.py --confirm
"""
import argparse
import os
import sys
import time

# Add backend directory to sys.path so imports work when run as a module.
# (Mirrors scripts/verify_langsmith_routing.py:23-34.)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import httpx
import openai

from config import get_settings  # load_dotenv(.env or .env.prod) fires HERE (keyed on ENV_FILE)
from services.llm_service import get_llm_client
from services.log_scrub import scrub_secrets


# --- Module-level safety bounds (D-06) -----------------------------------

TRIP_TARGET = 0.10   # the configured guardrail threshold we expect to trip
HARD_ABORT = 0.25    # 2.5x the trip target — if no block by here, SEC-03 BLOCKER
MAX_CALLS = 300      # third bound: a call ceiling beside the dollar abort (Pitfall 2)
PAID_MODEL = "openai/gpt-4o-mini"  # deliberately PAID (D-06) — a free model can't trip a $ cap

# Burn-loop tuning: a sizeable prompt + high max_tokens so each paid call costs enough
# to reach $0.10 in a bounded number of calls (Pitfall 2 — tiny calls cost ~$0.0001).
BIG_PROMPT = (
    "Write an extremely long, exhaustively detailed essay — do not stop early. Cover the "
    "complete history, core mechanics, strategy, and cultural impact of modern hobby board "
    "games, with multiple deep paragraphs each on Catan, Carcassonne, Ticket to Ride, "
    "Pandemic, Gloomhaven, and Terraforming Mars, plus comparisons and worked strategy "
    "examples. Be as verbose and thorough as you possibly can."
)
MAX_TOKENS = 8000           # high output so each call's usage.cost is non-trivial (Pitfall 2)
SEED_COST_PER_CALL = 0.01   # conservative starting per-call estimate; adapted from usage.cost
RATE_LIMIT_BACKOFF_S = 5    # 429 back-off — rate limiting is NOT a guardrail trip
INTER_BATCH_SLEEP_S = 2     # let server-side usage catch up before the between-batch reconcile


# --- Pure, importable helpers (zero spend, zero network) -----------------

def should_abort(running_total: float, calls: int) -> str | None:
    """Return a BLOCKER reason if a safety bound is crossed, else None (D-06).

    The dollar abort takes priority over the call ceiling so the operator sees the
    more alarming reason first. A non-None result means the guardrail did NOT trip
    in time → SEC-03 BLOCKER (do NOT enable the demo fallback in prod).
    """
    if running_total >= HARD_ABORT:
        return "BLOCKER_NO_TRIP_AT_ABORT"
    if calls >= MAX_CALLS:
        return "BLOCKER_CALL_CEILING"
    return None


def classify_status(code: int) -> str:
    """Classify an OpenRouter HTTP status into the burn loop's three outcomes (D-04).

    402 AND 403 both count as a guardrail block: OpenRouter's own docs disagree on
    which one a budget limit returns (RESEARCH Open Q1), so do NOT pin a single code.
    429 is rate-limiting (back off, NOT a trip). Everything else is unexpected.
    """
    if code in (402, 403):
        return "blocked"
    if code == 429:
        return "rate_limited"
    return "unexpected"


def next_batch_size(running_total: float, max_cost_per_call: float, base_batch: int = 5) -> int:
    """Plan the next serial batch size, bounded so worst-case spend stays safe (D-06).

    Never returns a size where ``running_total + size * max_cost_per_call`` could
    cross ``HARD_ABORT``, always returns at least 1 (so the loop keeps probing for
    the guardrail), and shrinks toward 1 as the running total approaches
    ``TRIP_TARGET`` so the natural overshoot past $0.10 is about a single call
    (Pitfall 3 — bound the overshoot).
    """
    if max_cost_per_call <= 0:
        # Cost is effectively free this call — nothing to bound by; use the base batch.
        return max(1, base_batch)

    # Hard bound: never plan a batch that could cross the $0.25 abort ceiling.
    abort_headroom = HARD_ABORT - running_total
    max_by_abort = int(abort_headroom / max_cost_per_call) if abort_headroom > 0 else 0

    # Soft bound: as we near the $0.10 trip target, shrink toward 1 so we overshoot
    # the trip by at most ~one call.
    trip_headroom = TRIP_TARGET - running_total
    max_by_trip = int(trip_headroom / max_cost_per_call) if trip_headroom > 0 else 0

    size = min(base_batch, max_by_abort, max(max_by_trip, 1))
    return max(1, size)


def format_block_record(code: int, body: str, running_total: float) -> str:
    """Build a single, fully-scrubbed one-line guardrail-block record (SEC-01).

    Routes BOTH the provider body and the assembled line through ``scrub_secrets`` so
    a leaked ``sk-or-…`` token can never survive into stdout/logs.
    """
    safe_body = scrub_secrets(body)
    line = (
        f"SEC-03 BLOCK CONFIRMED: status={code} "
        f"running_total=${running_total:.4f} body={safe_body}"
    )
    return scrub_secrets(line)


# --- Live spend poll (mirror routers/keys.py:135-165 — scrubbed, no traceback log) ----

def poll_key_usage(owner_key: str) -> tuple[float | None, float | None]:
    """Read cumulative spend + (informational) remaining limit from GET /api/v1/key.

    Mirrors routers/keys.py:135-165 — a scrubbed warning with NO error-traceback
    logging (a traceback could capture the Bearer key, T-999.2-04) and ``del key`` in ``finally``
    so the plaintext key can't ride a later failure into stack-frame locals. Returns
    ``(usage_usd, limit_remaining)``; either may be ``None``.
    """
    key = owner_key
    usage = None
    remaining = None
    try:
        resp = httpx.get(
            "https://openrouter.ai/api/v1/key",
            headers={"Authorization": f"Bearer {key}"},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json().get("data") or {}
        usage = data.get("usage")
        remaining = data.get("limit_remaining")
        if remaining is not None and not isinstance(remaining, (int, float)):
            remaining = None
    except (httpx.HTTPError, ValueError, TypeError, AttributeError) as e:
        # NO error-traceback logging — a traceback could capture the Bearer header / key (T-999.2-04).
        print(scrub_secrets(f"WARNING: /api/v1/key poll failed: {e}"))
    finally:
        # Drop the plaintext key from this frame ASAP (mirror keys.py:162-165).
        del key
    return usage, remaining


# --- Safety gate (no repo analog — stdlib argparse; refuse-by-default) ----

def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "SEC-03 burn test: spend REAL money on the PROD owner OpenRouter account "
            "until its $0.10 guardrail trips. Safe by default — requires --confirm AND "
            "ENV_FILE=.env.prod."
        ),
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Acknowledge that this spends REAL money on the prod owner account (D-01).",
    )
    return parser


def assert_safe_to_spend(confirm: bool) -> None:
    """Refuse to spend unless BOTH ``--confirm`` is passed AND ENV_FILE == ".env.prod".

    Raises ``SystemExit`` with a scrubbed, non-zero message and makes ZERO network
    calls (T-999.2-03). This is the first of three independent spend bounds (D-01/D-06);
    it MUST run before any client build or paid call.
    """
    if not confirm:
        raise SystemExit(scrub_secrets(
            "REFUSING TO RUN: this script spends REAL money on the prod owner account. "
            "Re-run with --confirm to acknowledge."
        ))
    env_file = os.environ.get("ENV_FILE")
    if env_file != ".env.prod":
        raise SystemExit(scrub_secrets(
            "REFUSING TO RUN: ENV_FILE must be '.env.prod' (D-01 targets the prod owner "
            f"account); got {env_file!r}. Set ENV_FILE=.env.prod in the shell BEFORE launch."
        ))


def main() -> int:
    args = _build_arg_parser().parse_args()

    # Gate first: ZERO network until BOTH --confirm and the prod env are present.
    assert_safe_to_spend(args.confirm)

    # --- Everything below this line spends REAL money (behind the gate) ---------

    settings = get_settings()
    owner_key = settings.resolved_llm_api_key  # @property — BARE, never logged
    if not owner_key:
        print(scrub_secrets("REFUSING TO RUN: no owner key resolved from .env.prod."))
        return 1

    # trace=False keeps burn traffic OUT of the prod LangSmith project (Pitfall 5).
    client = get_llm_client(api_key=owner_key, trace=False)

    # PRE-FLIGHT (D-03 defensive + Pitfall 6): read the STARTING cumulative spend
    # BEFORE any paid call so Plan 02 measures the delta from a known baseline.
    start_usage, start_remaining = poll_key_usage(owner_key)
    print(scrub_secrets(
        f"pre-flight baseline: usage=${start_usage} limit_remaining={start_remaining}"
    ))
    # If the key reports a remaining limit below the $0.25 abort headroom, the account
    # may hit an account-empty 402 BEFORE the guardrail (Pitfall 6) — abort first.
    if isinstance(start_remaining, (int, float)) and start_remaining < HARD_ABORT:
        print(scrub_secrets(
            f"ABORT: limit_remaining=${start_remaining} < ${HARD_ABORT} hard-abort headroom — "
            "the account may hit account-empty 402 before the guardrail; top up before running."
        ))
        return 1

    running_total = 0.0
    calls = 0
    observed_max_cost = SEED_COST_PER_CALL  # adapt upward from the real per-call usage.cost

    while True:
        abort = should_abort(running_total, calls)
        if abort is not None:
            # SEC-03 BLOCKER: the guardrail did NOT trip within the safety bounds.
            print(scrub_secrets(
                f"SEC-03 BLOCKER ({abort}): spent ${running_total:.4f} over {calls} calls "
                "with NO guardrail block — DO NOT enable the demo fallback in prod."
            ))
            return 1

        batch = next_batch_size(running_total, observed_max_cost)
        for _ in range(batch):
            try:
                resp = client.chat.completions.create(
                    model=PAID_MODEL,
                    messages=[{"role": "user", "content": BIG_PROMPT}],
                    max_tokens=MAX_TOKENS,
                )
            except openai.APIStatusError as e:
                code = getattr(e, "status_code", None)
                # Scrub the body so neither the key nor an echoed token survives; the
                # body text also lets the operator tell a guardrail block apart from an
                # account-empty 402 (Pitfall 6). NO error-traceback logging anywhere (T-999.2-04).
                body = scrub_secrets(
                    getattr(getattr(e, "response", None), "text", "") or str(e)
                )
                kind = classify_status(code) if isinstance(code, int) else "unexpected"
                if kind == "blocked":
                    # 402/403 — the SEC-03 trip signal (PASS for the block condition).
                    print(format_block_record(code, body, running_total))
                    print(scrub_secrets(
                        f"SEC-03 PASS (block): guardrail BLOCKED at status={code} after "
                        f"${running_total:.4f} over {calls} calls. Operator: check the "
                        "OpenRouter account inbox for an email (D-04 #3 — 'no email' is an "
                        "ACCEPTED finding)."
                    ))
                    return 0
                if kind == "rate_limited":
                    # 429 — back off and keep probing; NOT the cost guardrail.
                    print(scrub_secrets(
                        f"rate-limited (status={code}) — backing off {RATE_LIMIT_BACKOFF_S}s "
                        "(NOT a guardrail trip)"
                    ))
                    time.sleep(RATE_LIMIT_BACKOFF_S)
                    continue
                # unexpected (400/401/404/5xx) — surface scrubbed and stop.
                print(scrub_secrets(f"UNEXPECTED status={code}: {body}"))
                return 1

            usage = getattr(resp, "usage", None)
            call_cost = getattr(usage, "cost", 0.0) or 0.0  # USD, always present now
            running_total += call_cost
            calls += 1
            observed_max_cost = max(observed_max_cost, call_cost)
            print(scrub_secrets(
                f"call {calls}: cost=${call_cost:.5f} running_total=${running_total:.4f}"
            ))

            # In-batch safety re-check so a cost spike can't blow past the bounds.
            if should_abort(running_total, calls) is not None:
                break

        # Between-batch reconciliation cross-check against the server-side total.
        server_usage, _ = poll_key_usage(owner_key)
        print(scrub_secrets(
            f"reconcile: per-call sum=${running_total:.4f} server usage=${server_usage}"
        ))
        time.sleep(INTER_BATCH_SLEEP_S)


if __name__ == "__main__":
    sys.exit(main())
