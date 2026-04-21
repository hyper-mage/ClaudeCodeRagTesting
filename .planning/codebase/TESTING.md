# Testing Patterns

**Analysis Date:** 2026-04-03

## Test Framework

**Runner:**
- No formal test framework (no pytest, unittest, jest, vitest configured)
- Tests are custom Python scripts run as modules via `python -m`
- No test runner config files exist (`pytest.ini`, `setup.cfg`, `conftest.py`, `jest.config.*`, `vitest.config.*`)

**Assertion Library:**
- Python built-in `assert` statements with custom error messages
- No assertion library (no pytest assertions, no chai, etc.)

**Run Commands:**
```bash
# Backend unit + integration tests (record manager)
cd backend && python -m tests.test_record_manager

# Backend E2E tests (sub-agent, requires running server)
cd backend && python -m tests.test_e2e_subagent

# Frontend — no tests exist
# (no test script in package.json)
```

## Test File Organization

**Location:**
- Backend tests live in `backend/tests/` directory (separate from source)
- No frontend tests exist at all

**Naming:**
- `test_{module}.py` for unit/integration tests: `backend/tests/test_record_manager.py`
- `test_e2e_{feature}.py` for end-to-end tests: `backend/tests/test_e2e_subagent.py`

**Structure:**
```
backend/
  tests/
    test_record_manager.py    # Unit + integration tests for record manager
    test_e2e_subagent.py      # E2E tests for sub-agent feature
```

## Test Structure

**Suite Organization (custom pattern, not pytest):**
```python
"""Module docstring explaining test purpose and usage."""

# --- Unit tests (no DB) ---

def test_hash_deterministic():
    h1 = hash_content(b"hello world")
    h2 = hash_content(b"hello world")
    assert h1 == h2, "hash_content not deterministic"
    print("  PASS hash_content is deterministic")

# --- Integration tests (hit DB) ---

def test_check_duplicate_integration(user_id: str):
    """Test with live DB, takes user_id as param."""
    # setup, test, assert, cleanup
    print("  PASS check_duplicate finds completed doc with matching hash")

# --- Main runner ---
if __name__ == "__main__":
    print("\n=== Unit Tests ===")
    test_hash_deterministic()
    # ...

    print("\n=== Integration Tests ===")
    uid = get_test_user_id()
    test_check_duplicate_integration(uid)

    print("\nOK: All tests passed!")
```

**Key patterns:**
- Tests are plain functions, not classes
- Unit tests take no parameters; integration tests take `user_id`
- Each test prints its own PASS/FAIL message
- Tests are called sequentially in `if __name__ == "__main__"` block
- `sys.path.insert(0, ...)` used to fix imports from `tests/` subdirectory

**E2E test pattern (from `backend/tests/test_e2e_subagent.py`):**
```python
def run_test(num, desc, message, expected_tool, token):
    """Run a single E2E test case."""
    thread_id = create_thread(token, f"E2E Test {num}")
    result = send_and_collect(token, thread_id, message)
    tools_used = [te["tool"] for te in result["tool_events"]]
    passed = expected_tool in tools_used
    status = "PASS" if passed else "FAIL"
    print(f"\n  {status}")
    return passed

def main():
    token = get_token()
    tests = [
        (1, "Summarize known doc", "Summarize Calico_Rulebook.pdf", "analyze_document"),
        # ...more test cases
    ]
    results = []
    for num, desc, msg, expected in tests:
        passed = run_test(num, desc, msg, expected, token)
        results.append((num, desc, passed))
```

## Mocking

**Framework:** None. No mocking is used.

**What is tested without mocks:**
- Pure functions tested directly (hash functions, diff logic)
- Integration tests hit the live Supabase database
- E2E tests hit the running backend server at `http://localhost:8000`

**What NOT to mock (project philosophy):**
- The project uses live services for all testing -- no mock layer exists
- Test credentials hardcoded: `ragtest1@gmail.com` / `testpass123`

## Fixtures and Factories

**Test Data:**
```python
def get_test_user_id():
    """Sign in with test credentials and return user_id."""
    from supabase import create_client
    client = create_client(settings.supabase_url_resolved, settings.vite_supabase_anon_key)
    auth = client.auth.sign_in_with_password({
        "email": "ragtest1@gmail.com",
        "password": "testpass123"
    })
    return auth.user.id

def cleanup_test_docs(user_id: str, filename: str):
    """Delete all documents with given filename for the test user."""
    db = get_supabase()
    docs = db.table("documents").select("id, storage_path").eq("user_id", user_id).eq("filename", filename).execute()
    for doc in docs.data:
        db.table("documents").delete().eq("id", doc["id"]).execute()
```

**Location:**
- Helper functions defined inline in test files (no shared fixtures directory)
- Test data uses `__test_` prefixed filenames to avoid collision: `__test_dup.txt`, `__test_prev.txt`

## Coverage

**Requirements:** None enforced. No coverage tool configured.

**No coverage commands available.**

## Test Types

**Unit Tests:**
- Found in: `backend/tests/test_record_manager.py` (lines with "Unit tests" section)
- Scope: Pure functions with no I/O (hashing, diffing)
- Pattern: Call function, assert result, print PASS
- Count: 6 unit tests

**Integration Tests:**
- Found in: `backend/tests/test_record_manager.py` (lines with "Integration tests" section)
- Scope: Functions that hit live Supabase DB
- Pattern: Setup test data, call function, assert result, cleanup
- Requires: Valid `.env` with Supabase credentials
- Count: 2 integration tests

**E2E Tests:**
- Found in: `backend/tests/test_e2e_subagent.py`
- Scope: Full request/response cycle through running API server
- Pattern: Authenticate, create thread, send message via SSE, parse response, verify tool usage
- Requires: Running backend server at `localhost:8000` + valid `.env`
- Count: 6 E2E test cases

**Frontend Tests:**
- None. No test files, no test framework, no test script in `package.json`.

## Common Patterns

**Authentication in tests:**
```python
def get_token():
    r = httpx.post(
        f"{SUPABASE_URL}/auth/v1/token?grant_type=password",
        headers={"apikey": ANON_KEY},
        json={"email": "ragtest1@gmail.com", "password": "testpass123"},
    )
    return r.json()["access_token"]
```

**SSE stream parsing in E2E tests:**
```python
def send_and_collect(token: str, thread_id: str, content: str) -> dict:
    tool_events = []
    text_parts = []
    with httpx.Client(timeout=httpx.Timeout(300.0)) as client, client.stream(
        "POST", f"{API}/api/threads/{thread_id}/messages",
        headers={"Authorization": f"Bearer {token}"},
        json={"content": content},
    ) as response:
        # Parse SSE events from stream
        for chunk in response.iter_text():
            # parse event: and data: lines
    return {"tool_events": tool_events, "content": "".join(text_parts)}
```

**Cleanup pattern:**
```python
# Setup
cleanup_test_docs(user_id, "__test_dup.txt")

# Insert test data
db.table("documents").insert({...}).execute()

# Test
found = check_duplicate(user_id, ch)
assert found is not None

# Cleanup
db.table("documents").delete().eq("id", doc_id).execute()
```

## What Is NOT Tested

**Backend gaps:**
- No tests for `backend/routers/chat.py` (SSE streaming, tool dispatch loop)
- No tests for `backend/routers/threads.py` (CRUD operations)
- No tests for `backend/routers/documents.py` (upload, delete)
- No tests for `backend/services/ingestion_service.py` (chunking, embedding pipeline)
- No tests for `backend/services/retrieval_service.py` (vector search, hybrid search, RRF)
- No tests for `backend/services/llm_service.py` (streaming, client creation)
- No tests for `backend/services/embedding_service.py`
- No tests for `backend/services/rerank_service.py`
- No tests for `backend/services/metadata_service.py`
- No tests for `backend/services/sql_service.py`
- No tests for `backend/services/parsing_service.py`
- No tests for `backend/auth.py` (JWT verification)

**Frontend gaps:**
- No tests for any component, hook, context, or utility
- No test framework installed

## Recommendations for Adding Tests

**If adopting pytest (recommended for Python backend):**
1. Add `pytest` to `backend/requirements.txt`
2. Create `backend/conftest.py` with shared fixtures
3. Rename test functions to start with `test_` (already done)
4. Migrate `print("PASS")` assertions to plain `assert` statements
5. Use `pytest-httpx` for mocking external HTTP calls

**If adopting Vitest (recommended for frontend):**
1. Add `vitest` and `@testing-library/react` to `frontend/package.json` devDependencies
2. Add `"test": "vitest"` to scripts
3. Create test files co-located with components: `ChatContainer.test.tsx`

---

*Testing analysis: 2026-04-03*
