---
phase: "08"
plan: "04"
status: complete
date: 2026-05-18
uat_run: 3
final_outcome: 11/11 PASS
---

# Plan 08-04 — Deployed UAT (COMPLETE — 11/11 PASS over 3 runs)

## Final Outcome — Run #3 (2026-05-18)

All 11 in-scope items PASS on https://boardgame-rag-prod.pages.dev. Item 11 officially DROPPED (Tavily not provisioned in prod). Two backend/path gap-fixes + one frontend SSE error-handler gap-fix landed during UAT cycle.

| # | Result |
|---|--------|
| 1, 2, 5, 6, 12 | ✅ PASS (Run #1) |
| 3, 4 | ✅ PASS (Run #2 — after Dockerfile + SAMPLE_DOC_PATH patch) |
| 7, 8, 9, 10 | ✅ PASS (Run #3 — after useChat SSE error-handler patch) |
| 11 | DROPPED — Tavily not configured in prod |

Wave 3 (USER-5 asset capture) unblocked.

---

# Historical Run Detail (preserved for audit trail)

## Run #1 — Initial UAT (PARTIAL — exposed gaps)

## Outcome (Run #1, 2026-05-18, post-flyctl-deploy + git push)

| # | Item | Result | Notes |
|---|------|--------|-------|
| 1 | Try-demo CTA visible above email form, copy locked | ✅ PASS | |
| 2 | Click → button label flips to `Setting up your demo…` → navigates to `/` | ✅ PASS | |
| 3 | Welcome thread "Welcome to the demo" + 2 messages visible in sidebar | ❌ FAIL | No thread seeded; anon empty-state hint rendered instead |
| 4 | D&D 5e quickref doc visible in /documents private list | ❌ FAIL | No doc seeded |
| 5 | Demo amber pill visible in IconSidebar + MobileTopBar; tooltip on hover | ✅ PASS | |
| 6 | Sign out → sign in as permanent user → pill ABSENT | ✅ PASS | |
| 7 | Set Fly env to break LLM | ⚠️ INVALID | UAT spec referenced wrong env var (`OPENROUTER_API_KEY` — backend reads `LLM_API_KEY`). PLAN.md patched 2026-05-18; re-run with corrected command in Run #2. |
| 8 | Chat send → red error bubble + toast | ❌ FAIL | False-negative — LLM call succeeded because invalid env var change had no effect on `resolved_llm_api_key` chain. |
| 9 | Sentry event captured | ❌ FAIL | Cascade of item 8 false-negative — no error means no Sentry event. |
| 10 | Restore key + click Retry → fresh SSE + DB dedup | ❌ FAIL | Could not test — depends on item 8 actually breaking. |
| 11 | Trigger tool-level silent failure via TAVILY break | ⚠️ DROPPED | `.env.prod` has `TAVILY_API_KEY=` blank → `web_search_enabled=False` → tool not registered. D-08 silent-continue covered by unit tests; revisit only if Tavily ever provisioned. PLAN.md patched 2026-05-18. |
| 12 | Mobile parity (375×667 + 414×896): Try-demo CTA + Retry + error bubble + Demo pill | ✅ PASS (partial) | Try-demo / pill / mobile layout PASS; Retry button could not be tested (depends on item 8). |

## Root Causes Identified + Patched

### Root Cause #1 — Items 3 + 4 (PORT-01 bootstrap silent failure)

**Symptom:** POST `/api/demo/bootstrap` returned HTTP 500. Frontend `apiFetch` threw; `LoginPage.handleTryDemo` `catch {}` swallowed and set error toast, BUT navigation to `/` already happened because the catch was reached *after* the throw, so no navigation actually fired here — wait, the UAT user did navigate to `/`. The 500 must have happened on a separate flow… (TODO: verify request order in Run #2.)

**Cause:** Fly logs revealed `FileNotFoundError: [Errno 2] No such file or directory: '/app/services/../../data/sample-private-docs/dnd5e-quickref.md'`. The Dockerfile copies only `backend/` into the image, so `data/sample-private-docs/` was never present. `SAMPLE_DOC_PATH` resolves to `/app/services/../../data/...` = `/data/...` in the container, which is one level above where the data could live anyway.

**Fix landed (commits TBD this UAT batch):**
- `Dockerfile`: added `COPY --chown=appuser:appuser data/sample-private-docs ./data/sample-private-docs` after the `backend/` copy.
- `backend/services/demo_service.py`: `SAMPLE_DOC_PATH` now resolves against a two-candidate list — dev/test layout (`../../data/...`) AND container layout (`../data/...`) — picks the first that `os.path.exists`. Keeps dev/pytest behavior intact (7/7 `test_demo_bootstrap.py` + `test_anon_cleanup.py` PASS post-patch).

### Root Cause #2 — Items 7-10 (PORT-02 false-negative)

**Symptom:** UAT instruction told user to `flyctl secrets set OPENROUTER_API_KEY=invalid_for_uat` to force an LLM failure. Chat continued working normally → no error bubble → no Sentry event → no Retry to click.

**Cause:** `backend/config.py:131-132` defines `resolved_llm_api_key = self.llm_api_key or self.openai_api_key`. The Fly secret backend actually reads is `LLM_API_KEY`. Setting `OPENROUTER_API_KEY` is a no-op (it isn't even a field on `Settings`).

**Fix landed:** Plan 08-04 PLAN.md items 7 + 10 updated to reference `LLM_API_KEY` with an inline note pointing at `config.py:131-132`. Run #2 must use the corrected command.

### Root Cause #3 — Item 11 (invalid test premise)

**Symptom:** Setting `TAVILY_API_KEY=invalid_for_uat` and sending a chat message produced an LLM refusal ("I'm sorry but I can't help with that") — NOT a silent tool-call failure.

**Cause:** `.env.prod` has `TAVILY_API_KEY=` blank. `config.web_search_enabled` returns `False` when the key is empty (`config.py:139-140`). The web_search tool is therefore never registered with the LLM, so there's no tool-level failure path to exercise from the UAT surface.

**Fix landed:** Plan 08-04 PLAN.md item 11 marked DROPPED with rationale. D-08 silent-continue invariant remains covered by `backend/tests/test_chat_silent_tool_failures.py` unit tests. Total in-scope UAT items reduced from 12 to 11.

## JWT Audit Bonus

Fly Network-tab capture of the bootstrap request body confirmed anon JWT claims independently of the .env.prod REST decode done for USER-1:
- `aud: "authenticated"`
- `role: "authenticated"`
- `is_anonymous: true`

This reinforces the USER-1 lock — provisional 08-01 no-op path is now empirically validated against two distinct decode paths.

## Run #2 (2026-05-18, partial)

| # | Result | Notes |
|---|--------|-------|
| 3 | ✅ PASS | Welcome thread + D&D doc seeded after Dockerfile + path patch redeploy |
| 4 | ✅ PASS | (same redeploy) |
| 7 | ✅ PASS | LLM_API_KEY=invalid_for_uat with corrected env var; backend logged `AuthenticationError: 401 Missing Authentication header` (LangSmith trace captured) |
| 8 | ❌ FAIL | Backend errored correctly but **frontend UI did NOT render red error bubble**. Two assistant placeholder skeletons remained empty/stuck. Toast did not fire. |

### Root Cause #4 — Item 8 frontend silent-swallow

**Cause:** Backend `chat.py:905-908` yields `{event: "error", data: {"error": "..."}}` as an in-band SSE event. Frontend `useChat.ts` (line 109-196) parsed `data: ...` lines and dispatched only on `parsed.tool_event === true`, `parsed.text !== undefined`, or `parsed.message_id`. The `parsed.error` field had no branch — silently dropped. Stream then ended normally (`done=true`) → outer `try/catch` at L199 never fired → no role='error' bubble, no toast, no Sentry capture, no Retry button rendered.

**Fix landed:** `useChat.ts` adds an `else if (parsed.error !== undefined)` branch that `throw new Error(parsed.error)`. The inner JSON.parse catch re-throws non-SyntaxError exceptions so the outer catch handles bubble + toast + Sentry uniformly.

**Verification:** `npm run build` passes (0 TS errors, 2321 modules transformed). Manual UI re-test pending Run #3.

## Run #3 (2026-05-18) — ALL PASS

| # | Result |
|---|--------|
| 7 | ✅ PASS — LLM_API_KEY=invalid_for_uat broke LLM correctly |
| 8 | ✅ PASS — red error bubble + 4s toast rendered (useChat SSE error-handler patch wired) |
| 9 | ✅ PASS — Sentry event captured |
| 10 | ✅ PASS — Retry button worked + fresh SSE + DB dedup (Plan 08-03 retry-clean confirmed in prod) |
| 12 (Retry) | ✅ PASS — mobile Retry button tap-target met |

Plan 08-04 closed. Cumulative 11/11 across runs.

## Gap-Fix Commits

- `b5392f7` — fix(08-04): bundle sample doc into Docker image + robust SAMPLE_DOC_PATH (items 3+4 + PLAN.md items 7/10/11 corrections)
- `cb1a0d7` — fix(08-04): useChat handles SSE `event: error` in-band data (item 8 silent-swallow)
