"""Phase 11 gap-closure (11-05) — SEC-01 (a) run-LEVEL LangSmith gate.

The shipped Phase 11 gate (`test_langsmith_gate.py`) covers ONLY the inner
`wrap_openai` CLIENT spans (`get_llm_client(trace=False)`). It is structurally
blind to the OUTER run layer: a pre-existing `@traceable(name="chat_send_message")`
decorator on the endpoint plus a global `LANGCHAIN_TRACING_V2=true` opened an
ungated LangSmith run for EVERY turn — capturing `body.content` on entry — so a
BYOK user-key turn still landed the user's prompt/response in the OWNER's prod
LangSmith project. Two subagent `@traceable` sites (`subagent_explorer`,
`subagent_document_analysis`) leaked the same way on tool turns.

This module is the run-level regression coverage that gap could not provide:

- structural: the endpoint handler must NOT be `@traceable`-wrapped;
- behavioral: a full user-key turn — INCLUDING a tool-call dispatch to a child
  both directly and via `asyncio.to_thread` (the real explorer/doc-analysis
  pattern) — opens ZERO runs under `chat.tracing_context(enabled=not is_user_key)`;
- guardrail: owner/demo turns remain fully traced (observability NOT regressed),
  and the subagent sites stay `@traceable` so the single parent-seam contextvar
  provably covers them.

Deterministic + offline: run presence is asserted via `get_current_run_tree()`
only; `langsmith.client.Client` run submission is neutered so the owner-path
tests never make real HTTP calls. NO real OpenAI/Supabase involved.
"""
import asyncio

import pytest

pytest.importorskip("langsmith")

from langsmith import traceable  # noqa: E402
from langsmith.run_helpers import get_current_run_tree  # noqa: E402

from routers import chat  # noqa: E402
from services.explorer_service import run_exploration  # noqa: E402
from services.subagent_service import run_document_analysis  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def _force_tracing_offline():
    """Force tracing ON for the module (dummy keys) and neuter run submission.

    LANGCHAIN_TRACING_V2=true makes the owner-path assertions meaningful (that
    is the exact prod condition under which the leak shipped). Patching
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


def test_endpoint_handler_not_traceable():
    """SEC-01 (a) structural gate: send_message must NOT be @traceable-wrapped.

    The outer `@traceable(name="chat_send_message")` on the endpoint captured
    `body.content` on ENTRY — before is_user_key could possibly be known — so
    every BYOK turn's prompt landed in the owner's LangSmith project, ungated.
    The decorator must be gone from the endpoint; the traced region lives on an
    inner worker that opens only AFTER key resolution, inside the run gate.
    """
    assert getattr(chat.send_message, "__langsmith_traceable__", False) is False


def test_subagent_sites_remain_traceable():
    """Guardrail (green both ways): the subagent sites stay @traceable.

    The fix deliberately does NOT touch explorer_service / subagent_service —
    the single parent-seam `tracing_context(enabled=False)` contextvar
    suppresses ANY nested @traceable run (including across asyncio.to_thread).
    That guarantee only holds while these sites remain @traceable-wrapped; if
    someone swaps them to manual run creation, this test flags the assumption.
    """
    assert getattr(run_exploration, "__langsmith_traceable__", False) is True
    assert getattr(run_document_analysis, "__langsmith_traceable__", False) is True


def _run_probe_turn(is_user_key: bool) -> dict:
    """Drive a full probe turn under chat.tracing_context(enabled=not is_user_key).

    Mirrors the real chat seam: a @traceable async-generator parent (the
    _traced_turn worker shape) dispatches a @traceable child BOTH directly
    (execute_tool path) AND via asyncio.to_thread (the explorer/doc-analysis
    _drive pattern), recording get_current_run_tree() at every site.
    """
    recorded: dict = {}

    @traceable(name="subagent_explorer")
    def child(site: str) -> None:
        recorded[site] = get_current_run_tree()

    @traceable(name="chat_send_message")
    async def parent():
        recorded["parent"] = get_current_run_tree()
        child("child_direct")
        await asyncio.to_thread(child, "child_threaded")
        yield {"event": "done"}

    async def drive():
        # Binds to OUR code's gate symbol (routers.chat.tracing_context) — RED
        # with AttributeError until chat.py exposes it, GREEN once the run gate
        # exists at the parent seam.
        with chat.tracing_context(enabled=not is_user_key):
            async for _ in parent():
                pass

    asyncio.run(drive())
    return recorded


def test_user_key_turn_creates_zero_runs():
    """SEC-01 (a) behavioral gate: a BYOK user-key turn opens ZERO runs.

    Covers the full dispatch surface — parent run, direct child, AND the
    asyncio.to_thread child (the exact path test_langsmith_gate.py could not
    see) — so the user's prompt/response can never reach the owner's LangSmith
    project at ANY layer.
    """
    recorded = _run_probe_turn(is_user_key=True)
    assert set(recorded) == {"parent", "child_direct", "child_threaded"}
    for site, run in recorded.items():
        assert run is None, f"user-key turn opened a LangSmith run at {site!r}: {run!r}"


def test_owner_turn_still_traced():
    """Guardrail: owner/demo turns (is_user_key=False) remain FULLY traced.

    enabled=True must restore the parent run and both child runs (direct +
    threaded) so owner observability — including the cap-hit
    get_current_run_tree() metadata tag — is not regressed by the gate.
    """
    recorded = _run_probe_turn(is_user_key=False)
    assert set(recorded) == {"parent", "child_direct", "child_threaded"}
    for site, run in recorded.items():
        assert run is not None, f"owner turn lost its LangSmith run at {site!r}"
