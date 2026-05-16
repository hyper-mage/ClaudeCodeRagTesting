"""Verify OBS-02: prod chat traces land in boardgame-rag-prod, NOT boardgame-rag-dev.

This script is the live-deploy regression check for the LangSmith project-routing
fix (RESEARCH §Pitfall 5). It is intentionally a real end-to-end probe — it mints
a Supabase JWT for the documented test account, POSTs a chat to the deployed prod
Fly URL, drains the SSE response, then queries the LangSmith API to assert that
(a) at least one completed run landed in boardgame-rag-prod within a 90s window,
and (b) zero runs leaked into boardgame-rag-dev for the same time window.

Usage:
    cd backend && venv/Scripts/python.exe scripts/verify_langsmith_routing.py

Requires LANGSMITH_API_KEY, SUPABASE_URL, and VITE_SUPABASE_ANON_KEY in the loaded
.env (config.py handles loading). Exits 0 on PASS, non-zero on any assertion
failure, with a clear stderr message.

Run AFTER Wave 3 (07-04 / 07-05) confirms the Fly secret rename + redeploy:
    flyctl secrets unset LANGCHAIN_PROJECT \
        && flyctl secrets set LANGSMITH_PROJECT=boardgame-rag-prod \
        && fly deploy
"""

import sys
import os
import time
import datetime

# Add backend directory to sys.path so imports work when run as a module.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import httpx
from langsmith import Client

from config import get_settings


# --- Module-level config constants ---------------------------------------

FLY_URL = "https://boardgame-rag-prod.fly.dev"
PROD_PROJECT = "boardgame-rag-prod"
DEV_PROJECT = "boardgame-rag-dev"
POLL_TIMEOUT_S = 90
POLL_INTERVAL_S = 5

# Test account documented in CLAUDE.md — public, test-only credentials.
TEST_EMAIL = "ragtest1@gmail.com"
TEST_PASSWORD = "testpass123"


# --- Helpers -------------------------------------------------------------


def get_test_jwt() -> str:
    """Mint a Supabase access token for the documented test account.

    Mirrors backend/scripts/_lib/get_test_jwt.sh but in pure Python so the
    verify script works cross-platform (Windows/Linux/macOS) without bash.
    """
    settings = get_settings()
    supabase_url = settings.supabase_url_resolved
    anon_key = settings.vite_supabase_anon_key

    if not supabase_url:
        sys.exit("FAIL: SUPABASE_URL (or VITE_SUPABASE_URL) not set in env")
    if not anon_key:
        sys.exit("FAIL: VITE_SUPABASE_ANON_KEY not set in env")

    resp = httpx.post(
        f"{supabase_url}/auth/v1/token?grant_type=password",
        headers={
            "apikey": anon_key,
            "Content-Type": "application/json",
        },
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
        timeout=10.0,
    )
    resp.raise_for_status()
    token = resp.json().get("access_token")
    if not token:
        sys.exit("FAIL: Supabase auth response missing access_token")
    return token


def send_chat() -> tuple[datetime.datetime, str]:
    """Send a real chat round-trip to the deployed prod Fly URL.

    Returns (t0, thread_id) where t0 is the UTC datetime captured BEFORE the
    message POST — used as the lower bound for the LangSmith list_runs filter
    so we only see runs created by this probe.
    """
    jwt = get_test_jwt()
    headers = {
        "Authorization": f"Bearer {jwt}",
        "Content-Type": "application/json",
    }

    # 1. Create a thread.
    thread_resp = httpx.post(
        f"{FLY_URL}/api/threads",
        headers=headers,
        json={"title": "OBS-02 verify"},
        timeout=15.0,
    )
    thread_resp.raise_for_status()
    thread_id = thread_resp.json()["id"]

    # 2. Capture lower-bound timestamp BEFORE sending — guarantees the run we
    #    want to find has start_time >= t0.
    t0 = datetime.datetime.now(datetime.timezone.utc)

    # 3. POST the user message and drain the SSE stream (we don't parse, just
    #    keep the connection open until the server finishes producing the run).
    with httpx.stream(
        "POST",
        f"{FLY_URL}/api/threads/{thread_id}/messages",
        headers=headers,
        json={"content": "What is the simplest board game in the KB?"},
        timeout=60.0,
    ) as stream:
        for _line in stream.iter_lines():
            pass

    return t0, thread_id


def assert_routing(t0: datetime.datetime) -> None:
    """Assert ≥1 completed run in PROD_PROJECT and 0 runs in DEV_PROJECT.

    Polls LangSmith for up to POLL_TIMEOUT_S seconds (runs take a few seconds
    to flush from the SDK send buffer to the server-side index).
    """
    client = Client()

    # --- 1. Wait for ≥1 completed run in prod project ---------------------
    deadline = time.monotonic() + POLL_TIMEOUT_S
    completed: list = []
    while time.monotonic() < deadline:
        prod_runs = list(
            client.list_runs(
                project_name=PROD_PROJECT,
                start_time=t0,
                error=False,
                limit=10,
            )
        )
        # Defensive client-side filter — Run.end_time is None until the trace
        # is fully flushed.
        completed = [r for r in prod_runs if r.end_time is not None]
        if completed:
            print(
                f"PASS: {len(completed)} completed run(s) found in {PROD_PROJECT}"
            )
            break
        time.sleep(POLL_INTERVAL_S)
    else:
        sys.exit(
            f"FAIL: no completed runs in {PROD_PROJECT} within {POLL_TIMEOUT_S}s"
        )

    # --- 2. Assert NO leakage into dev project ----------------------------
    dev_runs = list(
        client.list_runs(
            project_name=DEV_PROJECT,
            start_time=t0,
            limit=10,
        )
    )
    if dev_runs:
        sys.exit(
            f"FAIL: {len(dev_runs)} run(s) leaked into {DEV_PROJECT} "
            f"within the verification window — routing is broken"
        )
    print(f"PASS: 0 runs leaked into {DEV_PROJECT}")


def main() -> int:
    """Two-step verification: send chat, then poll LangSmith for routing proof."""
    settings = get_settings()
    if not settings.langsmith_api_key:
        sys.exit("FAIL: LANGSMITH_API_KEY not set in env")

    print(f"[1/2] Sending test chat to {FLY_URL} ...")
    t0, thread_id = send_chat()
    print(f"      thread_id={thread_id} t0={t0.isoformat()}")

    print(f"[2/2] Polling LangSmith (timeout {POLL_TIMEOUT_S}s) ...")
    assert_routing(t0)

    print("OBS-02 VERIFY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
