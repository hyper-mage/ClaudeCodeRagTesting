---
phase: 16-web-search-restoration
fixed_at: 2026-07-12T20:44:34Z
review_path: .planning/phases/16-web-search-restoration/16-REVIEW.md
iteration: 1
findings_in_scope: 3
fixed: 3
skipped: 0
status: all_fixed
---

# Phase 16: Code Review Fix Report

**Fixed at:** 2026-07-12T20:44:34Z
**Source review:** .planning/phases/16-web-search-restoration/16-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 3 (WR-01, WR-02, WR-03 — critical_warning scope; Info findings IN-01/IN-02 intentionally out of scope)
- Fixed: 3
- Skipped: 0

## Fixed Issues

### WR-01: `tool_result_is_error` substring classifier produces both false negatives and false positives

**Files modified:** `backend/routers/chat.py`
**Commit:** 2d7fcb3
**Applied fix:** Replaced the raw substring test (`'"error"' in tool_result`) with a structural JSON parse: the classifier now returns `True` only when the payload parses to a dict carrying a top-level `"error"` key, and swallows `ValueError`/`TypeError` (returns `False`) on non-JSON input. This closes both defects the review cited:
- False positive — a successful `query_database` row whose cell value or column alias is literally `error` no longer flips the card red (the token now has to be a top-level key, not a substring of user data).
- False negative — `explore_kb`'s failure fallbacks previously serialized no `"error"` key. I added an explicit top-level `"error"` key to **both** explorer failure fallbacks: the exception path (`synthesis: "Explorer failed: …"`, chat.py ~1165) and the produced-no-result path (chat.py ~1188). A genuinely failed exploration now renders the red failed-state card, matching `analyze_document`'s already-correct fallback and the classifier's stated contract. The docstring was rewritten to describe the structural guarantee.

**Verification note (logic change):** The classifier True/False behavior is covered by the phase's contract test `backend/tests/test_web_search.py::test_tool_result_error_status`, which stayed GREEN with no test edits required (the review's structural intent matches the test's existing assertions). The end-to-end rendering of the red card for a failed `explore_kb` run (backend `"error"` key -> SSE `is_error` -> frontend `ToolCallCard` red state) is an integration behavior not exercised by a unit test in this run; recommend a manual confirmation that a deliberately-failed exploration surfaces the red card in the UI.

### WR-02: `web_search`/`query_database` tool dispatch has no arg guard — a malformed tool call crashes the whole turn

**Files modified:** `backend/routers/chat.py`
**Commit:** 7dfdc51
**Applied fix:** Wrapped the `query_database` and `web_search` dispatch branches in `execute_tool` in `try/except`, mirroring the existing `search_documents`/`kb_*` branches. On exception each now returns `json.dumps({"tool": <name>, "error": str(e)})` and logs `logger.error(f"{name} failed: {e}", exc_info=True)`. A malformed tool call missing a required arg (e.g. `fn_args["query"]`/`fn_args["sql"]` raising `KeyError`) now surfaces as a graceful tool error (LLM-handleable, red card via the WR-01 classifier) instead of propagating uncaught to the generic turn-level `except` and aborting the entire turn.

### WR-03: Tool-result `output` reaches the SSE stream and DB unscrubbed

**Files modified:** `backend/routers/chat.py`
**Commit:** 2e41874
**Applied fix:** Routed the `tool_output_preview` (the truncated tool-result string emitted on the `tool_result` SSE event and persisted into the `tools_used` array) through `scrub_secrets(...)` — the same redaction chokepoint already used by `_sse_error` and the `_ScrubFilter` on logs. This closes the last backend->client/DB tool-output channel that bypassed the redaction chain the phase hardened for `tvly-` keys, so any future tool whose `str(e)` embeds a secret is redacted here too. The classifier at the same site still inspects the **raw** `tool_result`, so scrubbing does not affect error classification.

## Test Results

Ran the backend test suite from the backend venv against the fixed worktree code:
`python -m pytest -q` (289 tests collected) -> **288 passed, 1 failed, 2 errors**.

The 1 failure + 2 errors are the exact known pre-existing debt called out as unrelated to this fix:
- `tests/test_config.py::test_key_encryption_secret_default` — env-fragile (a `KEY_ENCRYPTION_SECRET` in the loaded `.env` violates the empty-default assertion; pre-existing, not caused by this fix).
- `tests/test_record_manager.py::test_check_duplicate_integration` — fixture `user_id` not found (pre-existing fixture debt).
- `tests/test_record_manager.py::test_find_previous_version_integration` — fixture `user_id` not found (pre-existing fixture debt).

Phase-16 contract tests are GREEN: `tests/test_web_search.py` (all 8, including `test_tool_result_error_status` which exercises the modified `tool_result_is_error` classifier) and `tests/test_config.py` (all except the pre-existing `test_key_encryption_secret_default`) pass. No contract-test assertions were changed.

## Skipped Issues

None — all 3 in-scope findings were fixed.

## Out-of-Scope (not addressed)

- **IN-01** (`backend/config.py:139` comment lists Tavily depth values the API rejects) — Info, out of critical_warning scope.
- **IN-02** (`backend/tests/test_config.py` default test is env-fragile) — Info, out of critical_warning scope. Note: this is the same env-fragility class that produced the `test_key_encryption_secret_default` pre-existing failure above.

---

_Fixed: 2026-07-12T20:44:34Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
