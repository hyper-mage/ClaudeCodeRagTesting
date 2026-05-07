---
phase: 05-explorer-sub-agent
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/tests/test_explorer_service.py
  - backend/tests/test_explorer_tools.py
  - backend/tests/test_explorer_integration.py
  - backend/tests/fixtures/__init__.py
  - backend/tests/fixtures/explorer_fixtures.py
  - backend/tests/conftest.py
  - backend/pytest.ini
  - backend/requirements.txt
  - backend/models/schemas.py
  - backend/config.py
autonomous: true
requirements:
  - EXPL-01
  - EXPL-02
  - EXPL-05
  - EXPL-06
must_haves:
  truths:
    - "Test files exist on disk so subsequent waves have automated verify targets"
    - "ExplorerResult and ExplorerFinding Pydantic models reject oversized output"
    - "Settings exposes explorer_max_iterations / max_tool_calls / max_summary_chars / timeout"
  artifacts:
    - path: backend/tests/test_explorer_service.py
      provides: "Unit-test scaffold + contract tests for explorer service"
      min_lines: 60
    - path: backend/tests/test_explorer_tools.py
      provides: "Unit-test scaffold for explorer tool dispatch"
      min_lines: 30
    - path: backend/tests/test_explorer_integration.py
      provides: "Integration-test scaffold for SSE sub_event emission"
      min_lines: 30
    - path: backend/tests/fixtures/explorer_fixtures.py
      provides: "Scripted LLM turn sequences + KB hierarchy fixtures + stub_db_chain helper"
      min_lines: 80
    - path: backend/models/schemas.py
      provides: "ExplorerResult, ExplorerFinding Pydantic models with hard caps"
      contains: "class ExplorerResult(BaseModel)"
    - path: backend/config.py
      provides: "Explorer budget knobs"
      contains: "explorer_max_iterations"
  key_links:
    - from: backend/tests/test_explorer_service.py
      to: backend/models/schemas.py
      via: "import ExplorerResult / ExplorerFinding"
      pattern: "from models.schemas import ExplorerResult"
    - from: backend/tests/conftest.py
      to: backend/tests/fixtures/explorer_fixtures.py
      via: "shared mock_llm_client + KB hierarchy fixtures + stub_db_chain"
      pattern: "from tests.fixtures.explorer_fixtures import"
---

<objective>
Stand up Wave 0 of Phase 5: the test files, fixtures, Pydantic contracts, and Settings knobs that every other plan will consume. This plan implements no explorer behavior — it implements the contracts and scaffolds against which Wave 2-4 will be verified.

Purpose: Without test files existing on disk, all downstream plans would have `MISSING — Wave 0` verify markers. Without Pydantic models, the explorer service has no structured-output target. Without Settings knobs, budget enforcement has nothing to read.

Output:
- ExplorerResult / ExplorerFinding Pydantic models in `backend/models/schemas.py`
- explorer_* Settings fields in `backend/config.py`
- Three test files (`test_explorer_service.py`, `test_explorer_tools.py`, `test_explorer_integration.py`) with skipif markers + contract assertions
- Shared fixtures (`backend/tests/fixtures/explorer_fixtures.py`) including `stub_db_chain` helper consumed by Plan 03 integration tests
- `backend/pytest.ini` for path/verbosity defaults
- pytest-asyncio added to requirements.txt
</objective>

<execution_context>
@.claude/get-shit-done/workflows/execute-plan.md
@.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@.planning/ROADMAP.md
@.planning/REQUIREMENTS.md
@.planning/phases/05-explorer-sub-agent/05-RESEARCH.md
@.planning/phases/05-explorer-sub-agent/05-VALIDATION.md
@backend/services/subagent_service.py
@backend/services/kb_tools_service.py
@backend/config.py
@backend/tests/test_folders_api.py
@backend/tests/test_e2e_subagent.py
@backend/requirements.txt

<interfaces>
<!-- Existing patterns the executor must follow -->

From backend/config.py (Settings class — extend, do not replace):
```python
class Settings(BaseSettings):
    # ...existing fields...
    subagent_system_prompt: str = "..."
    subagent_max_tokens: int = 4096
    subagent_max_context_chars: int = 100000
    subagent_timeout: int = 90
    # NEW explorer fields go in this same class
```

From backend/tests/test_folders_api.py (test pattern):
```python
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
TEST_USER_ID = "11111111-1111-1111-1111-111111111111"
BOARD_GAMES_ROOT_ID = "a0000000-0000-0000-0000-000000000001"
# patch get_supabase via unittest.mock.patch("services.kb_tools_service.get_supabase")
```

From backend/services/subagent_service.py (sub-agent pattern this phase extends):
```python
@traceable(name="subagent_document_analysis")
def run_document_analysis(user_id: str, document_name: str, analysis_query: str) -> dict:
    settings = get_settings()
    # ...non-streaming completion...
```

ExplorerResult contract (defined by THIS plan, consumed by Plan 02-04):
```python
class ExplorerFinding(BaseModel):
    title: str = Field(max_length=120)
    path: str | None = None
    excerpt: str = Field(max_length=500)
    relevance: str = Field(max_length=200)

class ExplorerResult(BaseModel):
    mode: str  # "deep_search" | "summarize" | "find_similar"
    query: str
    findings: list[ExplorerFinding] = Field(max_length=8)
    synthesis: str = Field(max_length=2000)
    tools_used: list[str] = Field(default_factory=list)
    iterations: int = 0
    budget_exhausted: bool = False
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Add ExplorerResult/ExplorerFinding Pydantic models + explorer_* Settings + pytest config</name>
  <read_first>
    - backend/models/schemas.py (full)
    - backend/config.py (full — keep existing field naming/style)
    - backend/requirements.txt
    - backend/tests/test_folders_api.py (lines 1-60 for sys.path pattern)
  </read_first>
  <files>
    - backend/models/schemas.py
    - backend/config.py
    - backend/requirements.txt
    - backend/pytest.ini
  </files>
  <behavior>
    - ExplorerResult rejects synthesis longer than 2000 chars (Pydantic ValidationError)
    - ExplorerResult rejects more than 8 findings (Pydantic ValidationError)
    - ExplorerFinding rejects excerpt longer than 500 chars
    - ExplorerResult.mode accepts "deep_search", "summarize", "find_similar"
    - get_settings() returns instance with explorer_max_iterations=6, explorer_max_tool_calls=10, explorer_max_summary_chars=3000, explorer_timeout=120 (defaults from research)
    - pytest discovers backend/tests/ when run from backend/ directory
  </behavior>
  <action>
    1) Edit `backend/models/schemas.py` — append (do not replace existing models):
       ```python
       class ExplorerFinding(BaseModel):
           title: str = Field(max_length=120)
           path: str | None = None
           excerpt: str = Field(max_length=500)
           relevance: str = Field(max_length=200)

       class ExplorerResult(BaseModel):
           mode: str = Field(pattern="^(deep_search|summarize|find_similar)$")
           query: str
           findings: list[ExplorerFinding] = Field(default_factory=list, max_length=8)
           synthesis: str = Field(max_length=2000)
           tools_used: list[str] = Field(default_factory=list)
           iterations: int = 0
           budget_exhausted: bool = False
       ```
       Ensure `from pydantic import BaseModel, Field` is present at top (extend existing import if needed).

    2) Edit `backend/config.py` — inside the `Settings` class, AFTER the existing `subagent_*` block and BEFORE the `# Timeouts (seconds)` comment, add:
       ```python
       # Explorer sub-agent (Phase 5)
       explorer_system_prompt: str = (
           "You are the KB Explorer -- a specialist sub-agent for deep, multi-step "
           "knowledge-base traversal. You have the KB navigation tools: kb_tree, kb_ls, "
           "kb_glob, kb_grep, kb_read. Start with kb_tree to orient yourself, narrow with "
           "kb_ls/kb_glob, then read only what you need. Return focused, well-cited "
           "evidence as a structured summary. Do NOT return raw tool output. Stop "
           "exploring the moment you have enough to answer."
       )
       explorer_max_iterations: int = 6
       explorer_max_tool_calls: int = 10
       explorer_max_summary_chars: int = 3000
       explorer_timeout: int = 120
       ```
       Do NOT change existing fields. Do NOT remove the `@lru_cache` decorator.

    3) Append to `backend/requirements.txt` ONE new line: `pytest-asyncio==0.23.8`. Keep existing pinning style. Leave the unpinned `pytest` entry alone.

    4) Create `backend/pytest.ini`:
       ```ini
       [pytest]
       testpaths = tests
       python_files = test_*.py
       addopts = -ra --strict-markers
       markers =
           integration: integration tests requiring running services
       asyncio_mode = auto
       ```
  </action>
  <acceptance_criteria>
    - `grep -n "class ExplorerResult" backend/models/schemas.py` returns a match
    - `grep -n "class ExplorerFinding" backend/models/schemas.py` returns a match
    - `grep -n "explorer_max_iterations" backend/config.py` returns a match
    - `grep -n "explorer_max_tool_calls" backend/config.py` returns a match
    - `grep -n "explorer_max_summary_chars" backend/config.py` returns a match
    - `grep -n "explorer_timeout" backend/config.py` returns a match
    - `grep -n "explorer_system_prompt" backend/config.py` returns a match
    - `grep -n "pytest-asyncio" backend/requirements.txt` returns a match
    - `backend/pytest.ini` exists and contains `testpaths = tests`
    - `cd backend && venv/Scripts/python -c "from models.schemas import ExplorerResult, ExplorerFinding; ExplorerResult(mode='summarize', query='x', synthesis='y')"` exits 0
    - `cd backend && venv/Scripts/python -c "from config import get_settings; s=get_settings(); assert s.explorer_max_iterations==6 and s.explorer_max_tool_calls==10"` exits 0
  </acceptance_criteria>
  <verify>
    <automated>cd backend && venv/Scripts/python -c "from models.schemas import ExplorerResult, ExplorerFinding; from pydantic import ValidationError; r=ExplorerResult(mode='summarize', query='q', synthesis='s'); assert r.findings==[]; assert r.iterations==0; print('OK')"</automated>
  </verify>
  <done>
    ExplorerResult/ExplorerFinding importable, all four explorer_* Settings present with documented defaults, pytest.ini in place, requirements.txt updated.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Create test scaffolds + fixtures (test_explorer_service.py, test_explorer_tools.py, test_explorer_integration.py, conftest.py, fixtures/)</name>
  <read_first>
    - backend/tests/test_folders_api.py (lines 1-100 — copy sys.path + override_auth + _make_query_chain pattern)
    - backend/tests/test_e2e_subagent.py (full — for SSE iteration pattern)
    - backend/services/subagent_service.py (full — explorer tool dispatch will mirror this)
    - backend/models/schemas.py (after Task 1 — for ExplorerResult import)
    - .planning/phases/05-explorer-sub-agent/05-RESEARCH.md (lines 670-705 — Wave 0 gaps + per-req test map)
  </read_first>
  <files>
    - backend/tests/conftest.py
    - backend/tests/fixtures/__init__.py
    - backend/tests/fixtures/explorer_fixtures.py
    - backend/tests/test_explorer_service.py
    - backend/tests/test_explorer_tools.py
    - backend/tests/test_explorer_integration.py
  </files>
  <behavior>
    - All three test files import successfully (no NameError, no ImportError)
    - Contract tests for ExplorerResult size caps PASS (these test work done in Task 1)
    - Behavior tests for explorer service (still missing) are marked `pytest.skip("Explorer service implemented in Plan 02")` so the file collects without failing the suite
    - SSE integration tests are marked `pytest.skip("Explorer integration in Plan 03")`
    - Fixtures expose: `mock_llm_client(scenarios)`, `make_tool_call(name, args)`, `EXPLORER_SCENARIOS` dict with at least 3 scripted sequences, `stub_db_chain(execute_return)` helper for Plan 03 integration tests
  </behavior>
  <action>
    1) Create `backend/tests/fixtures/__init__.py` — empty file.

    2) Create `backend/tests/fixtures/explorer_fixtures.py`:
       ```python
       """Shared fixtures for explorer tests.

       Provides:
         - make_tool_call(name, args, call_id): build OpenAI-compatible tool_call dict
         - mock_llm_client(scenarios): returns a MagicMock standing in for OpenAI client
           whose chat.completions.create() returns scripted responses one per call
         - EXPLORER_SCENARIOS: dict[str, list[dict]] of scripted multi-turn sequences
         - stub_db_chain(execute_return): recursively chainable MagicMock for Supabase
           query chains — consumed by Plan 03 integration tests
       """
       import json
       from unittest.mock import MagicMock

       TEST_USER_ID = "11111111-1111-1111-1111-111111111111"
       BOARD_GAMES_ROOT_ID = "a0000000-0000-0000-0000-000000000001"


       def make_tool_call(name: str, args: dict, call_id: str = "call_test"):
           """Build a tool_call object shaped like an OpenAI ChatCompletionMessageToolCall."""
           tc = MagicMock()
           tc.id = call_id
           tc.type = "function"
           tc.function = MagicMock()
           tc.function.name = name
           tc.function.arguments = json.dumps(args)
           tc.model_dump = lambda: {
               "id": call_id,
               "type": "function",
               "function": {"name": name, "arguments": json.dumps(args)},
           }
           return tc


       def make_response(tool_calls=None, content=None, finish_reason=None):
           """Build a chat.completions.create() response."""
           response = MagicMock()
           response.choices = [MagicMock()]
           response.choices[0].message = MagicMock()
           response.choices[0].message.tool_calls = tool_calls
           response.choices[0].message.content = content
           response.choices[0].finish_reason = finish_reason or ("tool_calls" if tool_calls else "stop")
           response.usage = MagicMock(prompt_tokens=100, completion_tokens=50)
           return response


       def mock_llm_client(scripted_responses: list):
           """Return a MagicMock client whose chat.completions.create yields scripted_responses in order."""
           client = MagicMock()
           client.chat.completions.create = MagicMock(side_effect=scripted_responses)
           return client


       def stub_db_chain(execute_return=None):
           """Return a Supabase-style query-chain MagicMock.

           Every chain-builder attribute access (select/eq/in_/insert/update/delete/...)
           returns the same mock, so order-of-operations in production code doesn't
           matter. Only `.execute()` is meaningful; it returns a MagicMock whose
           `.data` attribute is `execute_return` (or None).

           Consumed by Plan 03 integration tests which need to patch
           `routers.chat.get_supabase` without binding the test to the router's
           exact chain ordering.

           Usage:
             db = stub_db_chain(execute_return={"id": "thread_1"})
             # db.table("x").select("*").eq("id", "1").maybe_single().execute().data
             # == {"id": "thread_1"}
           """
           m = MagicMock()

           def _chain(*_a, **_kw):
               return m

           for attr in (
               "table", "select", "insert", "update", "delete",
               "eq", "neq", "in_", "is_", "or_", "and_",
               "order", "limit", "single", "maybe_single", "range",
               "ilike", "like", "contains", "filter",
           ):
               setattr(m, attr, _chain)

           exec_result = MagicMock()
           exec_result.data = execute_return
           m.execute = MagicMock(return_value=exec_result)
           return m


       # ----- Scripted scenarios -----

       EXPLORER_SCENARIOS = {
           "summarize_catan": [
               # Turn 1: model calls kb_tree
               make_response(tool_calls=[make_tool_call("kb_tree", {"path": "Board Games/Catan", "depth": 2}, "call_1")]),
               # Turn 2: model calls kb_read
               make_response(tool_calls=[make_tool_call("kb_read", {"path": "Board Games/Catan/rules.md"}, "call_2")]),
               # Turn 3: model returns final structured JSON
               make_response(content=json.dumps({
                   "mode": "summarize",
                   "query": "Summarize Catan",
                   "findings": [
                       {"title": "Catan rules overview", "path": "Board Games/Catan/rules.md",
                        "excerpt": "Players collect resources...", "relevance": "Core mechanics"}
                   ],
                   "synthesis": "Catan is a resource-trading game where 3-4 players compete...",
                   "tools_used": [],
                   "iterations": 0,
                   "budget_exhausted": False,
               })),
           ],
           "find_similar_azul": [
               make_response(tool_calls=[make_tool_call("kb_grep", {"pattern": "tile placement", "mode": "keyword"}, "call_a")]),
               make_response(tool_calls=[make_tool_call("kb_ls", {"path": "Board Games"}, "call_b")]),
               make_response(content=json.dumps({
                   "mode": "find_similar",
                   "query": "Games like Azul",
                   "findings": [
                       {"title": "Sagrada", "path": "Board Games/Sagrada/rules.md",
                        "excerpt": "Dice drafting and pattern building", "relevance": "Pattern building like Azul"},
                       {"title": "Calico", "path": "Board Games/Calico/rules.md",
                        "excerpt": "Quilt-tile placement", "relevance": "Tile placement like Azul"},
                   ],
                   "synthesis": "Sagrada and Calico share Azul's pattern-building/tile-placement core.",
                   "tools_used": [],
                   "iterations": 0,
                   "budget_exhausted": False,
               })),
           ],
           "budget_exhaustion_loop": [
               # Always returns a tool_call, never stops voluntarily — used to test iteration cap
               *[make_response(tool_calls=[make_tool_call("kb_ls", {"path": "Board Games"}, f"call_{i}")]) for i in range(20)],
           ],
       }
       ```

    3) Create `backend/tests/conftest.py` (or extend if it already exists — check first with `cat backend/tests/conftest.py 2>/dev/null`):
       ```python
       """Shared pytest fixtures for backend tests."""
       import sys
       import os
       sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

       import pytest
       from tests.fixtures.explorer_fixtures import (
           TEST_USER_ID,
           BOARD_GAMES_ROOT_ID,
           make_tool_call,
           make_response,
           mock_llm_client,
           stub_db_chain,
           EXPLORER_SCENARIOS,
       )

       __all__ = [
           "TEST_USER_ID", "BOARD_GAMES_ROOT_ID",
           "make_tool_call", "make_response", "mock_llm_client",
           "stub_db_chain", "EXPLORER_SCENARIOS",
       ]


       @pytest.fixture
       def test_user_id():
           return TEST_USER_ID


       @pytest.fixture
       def explorer_scenarios():
           return EXPLORER_SCENARIOS
       ```
       If `backend/tests/conftest.py` already exists, MERGE: keep existing fixtures, add the explorer-related imports/fixtures, do not duplicate.

    4) Create `backend/tests/test_explorer_service.py`:
       ```python
       """Unit tests for explorer_service.run_exploration().

       Wave 0 scaffolding: contract tests for ExplorerResult run NOW.
       Behavior tests are marked skip until Plan 02 implements run_exploration().
       """
       import sys
       import os
       sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

       import pytest
       from unittest.mock import patch, MagicMock
       from pydantic import ValidationError

       from models.schemas import ExplorerResult, ExplorerFinding
       from tests.fixtures.explorer_fixtures import (
           TEST_USER_ID, EXPLORER_SCENARIOS, mock_llm_client,
       )


       # ----- Contract tests (run NOW — verifies Task 1) -----

       def test_explorer_result_rejects_oversized_synthesis():
           """EXPL-05: Pydantic enforces synthesis length cap."""
           with pytest.raises(ValidationError):
               ExplorerResult(mode="summarize", query="q", synthesis="x" * 2001)


       def test_explorer_result_rejects_too_many_findings():
           """EXPL-05: Pydantic enforces findings count cap."""
           findings = [ExplorerFinding(title="t", excerpt="e", relevance="r") for _ in range(9)]
           with pytest.raises(ValidationError):
               ExplorerResult(mode="summarize", query="q", findings=findings, synthesis="ok")


       def test_explorer_finding_rejects_oversized_excerpt():
           with pytest.raises(ValidationError):
               ExplorerFinding(title="t", excerpt="x" * 501, relevance="r")


       def test_explorer_result_mode_pattern():
           """Only the three documented modes are accepted."""
           ExplorerResult(mode="deep_search", query="q", synthesis="s")
           ExplorerResult(mode="summarize", query="q", synthesis="s")
           ExplorerResult(mode="find_similar", query="q", synthesis="s")
           with pytest.raises(ValidationError):
               ExplorerResult(mode="invalid_mode", query="q", synthesis="s")


       # ----- Behavior tests (Plan 02 implementation gates these) -----

       @pytest.mark.skip(reason="Explorer service implemented in Plan 02")
       def test_multi_step_loop():
           """EXPL-01: Explorer completes a multi-step traversal using KB tools."""
           pass


       @pytest.mark.skip(reason="Explorer service implemented in Plan 02")
       def test_tool_dispatch():
           """EXPL-01: Explorer dispatches kb_tree, kb_ls, kb_read, kb_grep, kb_glob correctly."""
           pass


       @pytest.mark.skip(reason="Explorer service implemented in Plan 02")
       def test_summarize_mode():
           """EXPL-02: mode='summarize' produces ExplorerResult with non-empty synthesis."""
           pass


       @pytest.mark.skip(reason="Explorer modes wired in Plan 03")
       def test_find_similar_mode():
           """EXPL-03: mode='find_similar' assembles findings across multiple games."""
           pass


       @pytest.mark.skip(reason="Explorer modes wired in Plan 03")
       def test_recommendation_seed():
           """EXPL-04: Explorer accepts conversation-derived seed query."""
           pass


       @pytest.mark.skip(reason="Explorer service implemented in Plan 02")
       def test_iteration_budget():
           """EXPL-05: Budget exhaustion on max_iterations sets budget_exhausted=True."""
           pass


       @pytest.mark.skip(reason="Explorer service implemented in Plan 02")
       def test_tool_call_budget():
           """EXPL-05: Budget exhaustion on max_tool_calls sets budget_exhausted=True."""
           pass


       def test_output_size_cap():
           """EXPL-05: ExplorerResult rejects oversized synthesis (already covered above; alias)."""
           with pytest.raises(ValidationError):
               ExplorerResult(mode="summarize", query="q", synthesis="x" * 5000)


       @pytest.mark.skip(reason="Explorer service implemented in Plan 02")
       def test_rls_isolation():
           """All EXPL: Explorer respects RLS — user A cannot see user B's private docs."""
           pass
       ```

    5) Create `backend/tests/test_explorer_tools.py`:
       ```python
       """Unit tests for the explorer's KB tool dispatcher.

       Wave 0 scaffold. Plan 02 will replace skip markers with real assertions.
       """
       import sys, os
       sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
       import pytest


       @pytest.mark.skip(reason="Explorer tool dispatcher implemented in Plan 02")
       def test_dispatch_kb_ls():
           """EXPL-01: explorer dispatches kb_ls calls correctly."""
           pass


       @pytest.mark.skip(reason="Explorer tool dispatcher implemented in Plan 02")
       def test_dispatch_kb_tree():
           """EXPL-01: explorer dispatches kb_tree calls correctly."""
           pass


       @pytest.mark.skip(reason="Explorer tool dispatcher implemented in Plan 02")
       def test_dispatch_kb_read():
           """EXPL-01: explorer dispatches kb_read calls correctly."""
           pass


       @pytest.mark.skip(reason="Explorer tool dispatcher implemented in Plan 02")
       def test_dispatch_kb_grep():
           """EXPL-01: explorer dispatches kb_grep calls correctly."""
           pass


       @pytest.mark.skip(reason="Explorer tool dispatcher implemented in Plan 02")
       def test_dispatch_kb_glob():
           """EXPL-01: explorer dispatches kb_glob calls correctly."""
           pass


       @pytest.mark.skip(reason="Tool error handling in Plan 02")
       def test_tool_dispatch_unknown_returns_error_json():
           """Explorer returns JSON error for unknown tool name (no exception)."""
           pass
       ```

    6) Create `backend/tests/test_explorer_integration.py`:
       ```python
       """Integration tests: parent chat -> explorer tool call -> SSE sub_event stream.

       Wave 0 scaffold. Plan 03 will wire `explore_kb` into the parent chat router and
       Plan 04 will surface the events client-side; both produce the artifacts these
       tests assert against.
       """
       import sys, os
       sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
       import pytest

       pytestmark = pytest.mark.integration


       @pytest.mark.skip(reason="explore_kb wired into parent loop in Plan 03")
       def test_explore_kb_tool_registered():
           """Parent chat advertises EXPLORE_KB_TOOL in its tools list."""
           pass


       @pytest.mark.skip(reason="explore_kb wired into parent loop in Plan 03")
       def test_sub_events_emitted():
           """EXPL-06: event_generator emits SSE 'tool_event' rows with type='sub_event'."""
           pass


       @pytest.mark.skip(reason="explore_kb wired into parent loop in Plan 03")
       def test_final_tool_result():
           """EXPL-06: terminating tool_result event contains ExplorerResult JSON."""
           pass


       @pytest.mark.skip(reason="explore_kb wired into parent loop in Plan 03")
       def test_parent_call_id_links_subevents():
           """EXPL-06: every sub_event payload includes parent_call_id matching the parent tool_start."""
           pass
       ```
  </action>
  <acceptance_criteria>
    - `backend/tests/conftest.py` exists and contains `TEST_USER_ID` and `mock_llm_client`
    - `backend/tests/conftest.py` imports `stub_db_chain` from the fixtures module
    - `backend/tests/fixtures/__init__.py` exists (can be empty)
    - `backend/tests/fixtures/explorer_fixtures.py` exists and contains `EXPLORER_SCENARIOS = {`
    - `grep -n "def stub_db_chain" backend/tests/fixtures/explorer_fixtures.py` returns a match
    - `grep -n "summarize_catan" backend/tests/fixtures/explorer_fixtures.py` returns a match
    - `grep -n "find_similar_azul" backend/tests/fixtures/explorer_fixtures.py` returns a match
    - `grep -n "budget_exhaustion_loop" backend/tests/fixtures/explorer_fixtures.py` returns a match
    - `backend/tests/test_explorer_service.py` exists and contains both contract tests AND skip-marked behavior tests
    - `backend/tests/test_explorer_tools.py` exists with skip-marked dispatch tests
    - `backend/tests/test_explorer_integration.py` exists with skip-marked SSE tests
    - `cd backend && venv/Scripts/python -m pytest tests/test_explorer_service.py -q --collect-only` lists ≥10 test nodes (4 contract + skip-marked)
    - `cd backend && venv/Scripts/python -m pytest tests/test_explorer_service.py -q -k "contract or output_size or mode_pattern or rejects"` exits 0 (4 tests must PASS — these are contract tests that should run NOW)
    - `cd backend && venv/Scripts/python -c "from tests.fixtures.explorer_fixtures import stub_db_chain; c = stub_db_chain({'id':'x'}); assert c.table('t').select('*').eq('id','1').maybe_single().execute().data == {'id':'x'}; print('OK')"` exits 0
  </acceptance_criteria>
  <verify>
    <automated>cd backend && venv/Scripts/python -m pytest tests/test_explorer_service.py -q -k "rejects or mode_pattern or output_size_cap"</automated>
  </verify>
  <done>
    Three test files importable; conftest.py exposes shared fixtures (including stub_db_chain for Plan 03); EXPLORER_SCENARIOS provides scripted multi-turn sequences for `summarize`, `find_similar`, and budget-exhaustion paths; contract tests for Pydantic caps PASS; behavior tests SKIP with explanatory reasons; pytest collection emits no errors.
  </done>
</task>

</tasks>

<verification>
- All three test files collect without errors via `pytest --collect-only`
- The 4 contract tests for ExplorerResult/ExplorerFinding caps PASS
- All other tests SKIP with explanatory `reason` strings pointing to Plan 02/03
- ExplorerResult/ExplorerFinding importable from `models.schemas`
- Settings exposes the four documented explorer_* fields with the documented defaults
- `pytest.ini` discovered by pytest (no warnings about strict-markers)
- `stub_db_chain` helper is importable and a trivial chain call round-trips the preset `execute_return`
</verification>

<success_criteria>
- Wave 0 test scaffold ready: downstream plans can implement against existing test files instead of creating them
- Pydantic contract enforced: oversized output rejected at validation time, not silently truncated downstream
- Settings knobs available so Plan 02 can read them via `get_settings()`
- pytest-asyncio installed so Plan 03's SSE integration tests can be `async def`
- `stub_db_chain` helper available so Plan 03 integration tests don't hand-roll fragile chain mocks
</success_criteria>

<output>
After completion, create `.planning/phases/05-explorer-sub-agent/05-01-SUMMARY.md` documenting:
- ExplorerResult / ExplorerFinding shape (final field names, caps)
- Settings field names + defaults added
- Files created and what each holds (so Plan 02-04 know where to look)
- Skip-marked tests grouped by which downstream plan owns them
- `stub_db_chain` helper signature + intended Plan 03 consumer
</output>
</output>
