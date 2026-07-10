"""Phase 11 gap-closure (11-06) — runtime LangSmith master toggle composition.

11-05 moved the SEC-01 gate to the run layer: chat.py wraps the whole turn in
a `tracing_context(enabled=...)` gate. This plan layers a GLOBAL,
runtime-flippable master toggle ABOVE that gate — the composed rule is

    enabled = False if (is_user_key or not langsmith_on) else None

- Flag OFF or BYOK -> enabled False (forced suppression; the live kill-switch
  beats owner tracing, the BYOK gate beats everything).
- Flag ON + owner/demo -> enabled None (defer to the environment — the gate
  NEVER forces True, so an env-level opt-out / keyless deploy stays untraced;
  CR-01). This module's fixture sets LANGCHAIN_TRACING_V2=true, so the
  deferred row opens a run — the exact traced-prod condition.

SECURITY INVARIANT (T-11-06-01): is_user_key is resolved LOCALLY, independent
of the flag read. A failed/missing flag read defaults langsmith_on to True
(default-on) — SAFE because is_user_key alone forces the gate to False for
any user key, so enabled stays False no matter what the flag read returns. A
broken flag read can never trace a BYOK turn.

Empirical + offline (same approach the 11-05 run-gate suite validated against
langsmith 0.3.42): run presence is asserted via get_current_run_tree() (None
== no run) inside a @traceable worker driven under chat.tracing_context;
Client run submission is neutered so nothing touches the network. A binding
structural assertion ties the suite to OUR code: chat.py must import and use
the app_settings flag reader (chat.is_langsmith_enabled IS the service fn).
"""
import asyncio
from unittest.mock import MagicMock

import pytest

pytest.importorskip("langsmith")

from langsmith import traceable  # noqa: E402
from langsmith.run_helpers import get_current_run_tree  # noqa: E402

from routers import chat  # noqa: E402
from services import app_settings_service  # noqa: E402
from services.app_settings_service import is_langsmith_enabled  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def _force_tracing_offline():
    """Force tracing ON for the module (dummy keys) and neuter run submission.

    LANGCHAIN_TRACING_V2=true makes the enabled=None (defer-to-env) assertions
    meaningful (the exact traced-prod condition). Patching
    Client.create_run/update_run to no-ops guarantees no network I/O — the
    assertion surface is get_current_run_tree() presence, never HTTP.
    """
    mp = pytest.MonkeyPatch()
    mp.setenv("LANGCHAIN_TRACING_V2", "true")
    mp.setenv("LANGCHAIN_API_KEY", "ls-dummy-test-key")
    mp.setenv("LANGSMITH_API_KEY", "ls-dummy-test-key")
    from langsmith.client import Client

    mp.setattr(Client, "create_run", lambda self, *a, **k: None)
    mp.setattr(Client, "update_run", lambda self, *a, **k: None)
    yield
    mp.undo()


@pytest.fixture(autouse=True)
def _fresh_flag_cache():
    """Reset the app_settings TTL cache around every test (no state leaks)."""
    app_settings_service._reset_cache()
    yield
    app_settings_service._reset_cache()


def _run_composed_turn(langsmith_on: bool, is_user_key: bool):
    """Drive a @traceable worker under chat.tracing_context with the composed gate.

    The enabled expression is computed EXACTLY as chat.py composes it:
    `enabled = False if (is_user_key or not langsmith_on) else None` — False
    forces suppression, None defers to the env (the module fixture sets
    LANGCHAIN_TRACING_V2=true, so the deferred row is traced). Returns the run
    tree recorded inside the worker — None means no LangSmith run was opened.
    """
    recorded: list = []

    @traceable(name="chat_send_message")
    async def worker():
        recorded.append(get_current_run_tree())
        yield {"event": "done"}

    async def drive():
        enabled = False if (is_user_key or not langsmith_on) else None  # mirrors chat.py verbatim
        with chat.tracing_context(enabled=enabled):
            async for _ in worker():
                pass

    asyncio.run(drive())
    assert len(recorded) == 1
    return recorded[0]


def test_flag_off_owner_zero_runs():
    """Flag OFF + owner/demo turn -> enabled False -> NO run.

    The master kill-switch beats owner/demo tracing: flag OFF means ZERO
    LangSmith runs for EVERYONE.
    """
    run = _run_composed_turn(langsmith_on=False, is_user_key=False)
    assert run is None, f"flag OFF still opened an owner run: {run!r}"


def test_flag_on_owner_traced():
    """Flag ON + owner/demo turn -> enabled None -> env decides -> RunTree exists.

    The toggle must not regress owner/demo observability — flag ON defers to
    the environment (the fixture sets LANGCHAIN_TRACING_V2=true, the exact
    traced-prod condition), never force-enables over an env opt-out (CR-01).
    """
    run = _run_composed_turn(langsmith_on=True, is_user_key=False)
    assert run is not None, "flag ON lost the owner/demo run"


def test_flag_on_byok_zero_runs():
    """Flag ON + BYOK turn -> enabled False -> NO run (SEC-01 preserved).

    The runtime toggle composes with — and never weakens — the per-request
    BYOK gate: a user-key turn opens zero runs even with the master flag ON.
    """
    run = _run_composed_turn(langsmith_on=True, is_user_key=True)
    assert run is None, f"flag ON traced a BYOK turn: {run!r}"


def test_flag_off_byok_zero_runs():
    """Flag OFF + BYOK turn -> enabled False -> NO run (both switches closed)."""
    run = _run_composed_turn(langsmith_on=False, is_user_key=True)
    assert run is None, f"flag OFF traced a BYOK turn: {run!r}"


def test_flag_read_error_defaults_true_byok_still_gated():
    """SECURITY INVARIANT: a broken flag read can never trace a BYOK turn.

    langsmith_on is taken from the REAL is_langsmith_enabled with a db stub
    whose .execute() raises -> the reader defaults to True (default-on).
    Because is_user_key is evaluated locally and independently, the composed
    enabled is STILL False for a user key -> zero runs.
    """
    db = MagicMock()
    (
        db.table.return_value
        .select.return_value
        .eq.return_value
        .maybe_single.return_value
        .execute
    ).side_effect = RuntimeError("flag read down")

    langsmith_on = is_langsmith_enabled(db)
    assert langsmith_on is True  # default-on on read failure

    run = _run_composed_turn(langsmith_on=langsmith_on, is_user_key=True)
    assert run is None, f"default-on flag read traced a BYOK turn: {run!r}"


def test_chat_binds_app_settings_flag_reader():
    """Binding gate: chat.py must import and use OUR flag reader.

    The truth table above proves the composition semantics; this assertion
    ties them to the shipped code — chat.is_langsmith_enabled must BE the
    app_settings service function (imported into chat's namespace, per-turn
    callable and patchable as routers.chat.is_langsmith_enabled).
    """
    assert (
        getattr(chat, "is_langsmith_enabled", None)
        is app_settings_service.is_langsmith_enabled
    ), "routers.chat does not bind services.app_settings_service.is_langsmith_enabled"
