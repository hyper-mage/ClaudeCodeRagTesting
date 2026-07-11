---
phase: 16
slug: web-search-restoration
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-11
---

# Phase 16 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from 16-RESEARCH.md "Validation Architecture". Planner refines the Per-Task map once plans exist.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + pytest-asyncio (backend). Frontend: no test runner installed — verification is `npm run build` (tsc + vite) + manual browser smoke (16-04). |
| **Config file** | backend: `backend/tests/conftest.py`; frontend: vitest config in `frontend/` |
| **Quick run command** | `cd backend && venv/Scripts/python -m pytest tests/test_web_search.py -q` |
| **Full suite command** | `cd backend && venv/Scripts/python -m pytest -q` |
| **Estimated runtime** | ~backend suite existing (278 tests); new web-search unit tests ~a few seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_web_search.py -q`
- **After every plan wave:** Run backend full suite `pytest -q` (and `npm run build` for frontend edits)
- **Before `/gsd-verify-work`:** Full suite green + SC-5 live prod check performed
- **Max feedback latency:** ~30 seconds (unit); live prod gate is manual

---

## Per-Task Verification Map

> Planner fills exact task IDs. Requirement → test-type mapping below is the contract.

| Requirement | Secure/Expected Behavior | Test Type | Automated Command | File Exists | Status |
|-------------|--------------------------|-----------|-------------------|-------------|--------|
| WSRCH-01 | `_search_tavily` sends `Authorization: Bearer <key>` header (not body `api_key`); returns `{answer, results[].{title,url,snippet}}` | unit (monkeypatch httpx.post, assert header) | `pytest tests/test_web_search.py -q` | ❌ W0 | ⬜ pending |
| WSRCH-02 | Tool absent from loop when `web_search_enabled` is false; `search_web()` re-guards returning `{"error"}`; chat turn completes | unit (settings with empty key → tool not appended / error dict) | `pytest tests/test_web_search.py -q` | ❌ W0 | ⬜ pending |
| WSRCH-03 | System prompt instructs inline links + "Sources:" list; agent receives results with `url` | source assertion (`config.py` system_prompt contains updated citation guidance) + unit | `pytest tests/test_web_search.py -q` | ❌ W0 | ⬜ pending |
| WSRCH-04 | Provider error (401/timeout/non-200) → graceful `{"error"}` to agent, `logger.error(exc_info=True)`, SSE tool_result carries error flag; `ToolCallCard` renders failed state | unit (force httpx raise → error dict) + frontend build + component assertion | `pytest tests/test_web_search.py -q` && `cd frontend && npm run build` | ❌ W0 | ⬜ pending |
| D-04 | `web_search_depth` setting default "basic", passed to Tavily `search_depth` | unit (settings default + request body assertion) | `pytest tests/test_web_search.py -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_web_search.py` — new test module (does not exist yet); covers WSRCH-01..04 + D-04 via `monkeypatch`/`MagicMock` on `httpx.post` (no respx dependency)
- [ ] Reuse existing `backend/tests/conftest.py` fixtures (fake settings pattern)

*No new framework install needed — pytest + vitest already present.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live web-grounded answer on prod | WSRCH-01 / SC-5 | Requires real Tavily key + live Fly prod deployment (`WEB_SEARCH_API_KEY` secret set + process restart due to `@lru_cache` settings) | Set Fly secret, redeploy/restart, ask a current-info question in prod chat, confirm `web_search` tool card fires and answer cites live sources |
| Fail-closed with no key on prod | WSRCH-02 | Environment-dependent | With key unset, confirm tool absent and chat still answers |

---

## Validation Sign-Off

- [ ] All tasks have automated verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers the MISSING `test_web_search.py` reference
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s (unit)
- [ ] `nyquist_compliant: true` set in frontmatter (after planner refines task IDs)

**Approval:** pending
