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

# Add backend directory to sys.path so imports work when run as a module.
# (Mirrors scripts/verify_langsmith_routing.py:23-34.)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import get_settings  # load_dotenv(.env or .env.prod) fires HERE (keyed on ENV_FILE)
from services.log_scrub import scrub_secrets


# --- Module-level safety bounds (D-06) -----------------------------------

TRIP_TARGET = 0.10   # the configured guardrail threshold we expect to trip
HARD_ABORT = 0.25    # 2.5x the trip target — if no block by here, SEC-03 BLOCKER
MAX_CALLS = 300      # third bound: a call ceiling beside the dollar abort (Pitfall 2)
PAID_MODEL = "openai/gpt-4o-mini"  # deliberately PAID (D-06) — a free model can't trip a $ cap


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

    # The live pre-flight poll + serial adaptive burn loop land in Task 3, all behind
    # this gate so nothing spends without --confirm + ENV_FILE=.env.prod.
    return 0


if __name__ == "__main__":
    sys.exit(main())
