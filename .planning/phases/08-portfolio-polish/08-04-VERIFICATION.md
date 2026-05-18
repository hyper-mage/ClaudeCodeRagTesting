---
phase: "08"
plan: "04"
status: in_progress
date: 2026-05-18
uat_run: 1
---

# Plan 08-04 — Deployed UAT Run #1 (PARTIAL PASS — gap-fix landed)

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

## Run #2 — What to redo

After backend redeploy with the Dockerfile + path patch:

1. Re-test items 3 + 4 only (expect PASS — welcome thread + doc visible after Try-demo click on fresh anon user).
2. Run items 7-10 against the corrected `LLM_API_KEY` env var.
3. Skip item 11 (officially dropped).
4. Re-confirm item 12 Retry button mobile parity once item 10 yields a visible Retry button.

Run #2 results overwrite this VERIFICATION; if 11/11 PASS, mark `status: complete` and proceed to USER-5.
