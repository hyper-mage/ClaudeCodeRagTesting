---
phase: 16-web-search-restoration
plan: 04
subsystem: ops-verification
tags: [prod, fly, tavily, web-search, live-smoke, sc-5, verification, checkpoint]

# Dependency graph
requires:
  - phase: 16-web-search-restoration
    plan: 02
    provides: "Bearer-auth Tavily transport + is_error SSE flag + tvly- scrub — the backend under live test"
  - phase: 16-web-search-restoration
    plan: 03
    provides: "red failed-state tool card — the frontend confirmed by the failure smoke"
provides:
  - "Live prod confirmation of SC-1..SC-5: web_search fires against the real Tavily key, returns a cited web-grounded answer, and fails gracefully with a red card"
  - "Prod ops state: WEB_SEARCH_API_KEY Fly secret set (Deployed, v36), SYSTEM_PROMPT secret unset so the shipped D-01/D-02/D-03 system_prompt default applies"
affects: [web-search-restoration, prod-ops]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "@lru_cache get_settings() is process-lifetime — a Fly secret change only takes effect after the machine restarts (confirmed: web_search_enabled flipped true only on the post-secret restart)"
    - "Prod system prompt precedence: a SYSTEM_PROMPT Fly secret overrides the config.py default; unsetting it is required for shipped prompt edits (D-01/D-02/D-03) to reach the running app"

key-files:
  created:
    - .planning/phases/16-web-search-restoration/16-04-SUMMARY.md
  modified: []

key-decisions:
  - "Unset the prod SYSTEM_PROMPT Fly secret (owner decision) rather than editing it — lets the shipped config.py system_prompt default (with the D-01 when-to-search steer + D-02 citation format + D-03 error-ack) take effect in prod"
  - "Batched the WEB_SEARCH_API_KEY set (--stage) with the SYSTEM_PROMPT unset so a single restart applied both"
  - "Ran the failure smoke on prod with a temporary invalid key, then restored the real key — confirmed the restore reached Deployed (digest feca87ad, v36, both machines) before closing"

patterns-established:
  - "Owner-gated prod verification for owner-held-secret features: executor discovers app + drafts exact commands + confirms post-hoc state; owner supplies the key, approves the deploy, and does the visual smoke"

requirements-completed: [WSRCH-01, WSRCH-02, WSRCH-03, WSRCH-04]

# Metrics
duration: 1h
completed: 2026-07-12
---

# Phase 16 Plan 04: Web-Search Prod Verification Summary

**The restored `web_search` tool was verified end-to-end on live prod (`boardgame-rag-prod`) against the owner's real Tavily key. The phase-16 backend (Bearer-auth transport, `is_error` SSE flag) and frontend (red failed-state card) were deployed to prod, `WEB_SEARCH_API_KEY` was set as a Fly secret (and `SYSTEM_PROMPT` unset so the shipped citation guidance applies), the machine restarted so `@lru_cache` settings re-read and `web_search_enabled` flipped true. The success smoke returned a cited, web-grounded answer with a visible Web Search tool card; the failure smoke (temporary invalid key) showed the red failed-state card + an agent acknowledgement + a best-effort answer with no crash; the valid key was then restored and confirmed Deployed.**

## Performance

- **Duration:** ~1 h (owner-gated: deploy + secret + two visual smokes)
- **Completed:** 2026-07-12
- **Tasks:** 2 (both human-gated checkpoints)
- **Files modified:** 0 production files (ops + verification only)

## Accomplishments

- **Task 1 — deploy + secret + restart (SC-5 precondition):**
  - Prod app identified via `fly status` (not hardcoded): `boardgame-rag-prod` (hostname `boardgame-rag-prod.fly.dev`, machines in `dfw` + `iad`).
  - Backend deployed to prod via `fly deploy` (repo-root Dockerfile) — new image `deployment-01KXBMPKHP...`; frontend deployed via `git push origin master:main` (Cloudflare rebuild) — confirmed `origin/main` == `master` (0 commits ahead).
  - `WEB_SEARCH_API_KEY` set as a Fly secret; `SYSTEM_PROMPT` secret unset (owner decision) so the shipped `config.py` `system_prompt` default (D-01 steer + D-02 citation format + D-03 error-ack) governs prod.
  - Restart confirmed: machines advanced version and restarted **after** the secret change (checks passing), so `get_settings()` (`@lru_cache`, config.py:191/199) re-read and `web_search_enabled` is true in the running process.
- **Task 2 — live prod smoke (SC-1/SC-3/SC-4/SC-5, spot-check SC-2):**
  - **Success smoke (SC-1 / SC-3 / SC-5):** a current-info board-game query the KB can't answer (the suggested Catan current-price / latest-expansion prompt) invoked `web_search` — the **Web Search tool card appeared and completed (gray)**, and the answer was **web-grounded with inline `[text](url)` markdown-link citations plus a trailing "Sources:" list** (D-02). Owner-confirmed against the Task 2 acceptance criteria.
  - **Failure smoke (SC-4):** with a temporary invalid `WEB_SEARCH_API_KEY`, a web-needing query showed the **red failed-state tool card** (plan 16-03), the agent **briefly acknowledged it couldn't reach the web and answered best-effort** — **no turn crash**. The valid key was then restored.
  - **Fail-closed (SC-2):** unit-verified in plan 16-01 (`test_gating_fail_closed`); with no key the `web_search` tool is cleanly absent and chat still completes. No prod action taken (avoided unsetting the prod key mid-verification).

## Task Commits

This is a verification/ops plan — no production code commits. The only commit is this SUMMARY + tracking (STATE.md / ROADMAP.md / REQUIREMENTS.md).

## Files Created/Modified

- Created: `.planning/phases/16-web-search-restoration/16-04-SUMMARY.md` (this file).
- No production source files modified (Task `files_modified: []`).

## Verification

- **SC-5 precondition:** `fly secrets list --app boardgame-rag-prod` → `WEB_SEARCH_API_KEY` present and **Deployed** (digest `feca87ad`), `SYSTEM_PROMPT` absent; `fly status` → both machines VERSION 36 `started`, 1/1 checks passing, restarted after the secret change.
- **SC-1 / SC-3 / SC-5:** owner-confirmed live — visible completed Web Search tool card + web-grounded answer with inline-link citations and a "Sources:" list.
- **SC-4:** owner-confirmed live — red failed-state card + agent acknowledgement + best-effort answer, no crash; valid key restored (confirmed Deployed on v36 before closing).
- **SC-2:** unit-verified (plan 16-01).
- Backend suite green (288 passed, plan 16-02) and frontend build green (plan 16-03) **before** deploy — no live verification against unbuilt code.

## Decisions Made

- **Unset the prod `SYSTEM_PROMPT` secret** (owner-selected) instead of editing it — the D-01/D-02/D-03 guidance ships inside `config.py` `system_prompt` (lines 95–108), and the prod secret was shadowing it. Unsetting lets the shipped default reach the running app, which is what SC-3 needs.
- **Batched secret set (`--stage`) + unset into one restart** to minimize prod restarts.
- **Failure smoke on prod, then restore** — accepted a brief invalid-key window (personal app, test users only), with the real key restored and confirmed Deployed (v36) afterward.

## Deviations from Plan

None. Both checkpoint gates executed as written. One planning caveat was surfaced and resolved live rather than deferred: the prod `SYSTEM_PROMPT` Fly secret (flagged in plan 16-02's SUMMARY as an ops risk) would have shadowed the shipped citation guidance — unset during Task 1 so SC-3 could pass.

## User Setup Required

Ongoing prod ops state (now in place):
- `WEB_SEARCH_API_KEY` Fly secret set on `boardgame-rag-prod` (owner's Tavily key) — required for the tool to activate.
- `SYSTEM_PROMPT` Fly secret unset on prod — required for the shipped citation/steer/error-ack guidance to apply. If a custom prod system prompt is ever re-added, it must include the D-02 citation instructions or SC-3 formatting will regress.
- Optional: `WEB_SEARCH_DEPTH=advanced` Fly secret for deeper Tavily search (defaults to `basic`).

## Known Stubs

None.

## Issues Encountered

- **Transient `Staged`/`Partial` secret state during the failure-smoke restore.** Immediately after the restore `fly secrets set`, `WEB_SEARCH_API_KEY` briefly showed `Staged`/`Partial` while v36 rolled out across the two machines. Resolved on its own within ~30 s to `Deployed` on both (dfw + iad); the restored digest matched the original valid-key digest, confirming the same real key. No action needed beyond waiting for the rollout to complete — verified before closing the phase.

## Threat Surface

- **T-16-12 (raw key disclosure):** mitigated — the `tvly-` key was set only via `fly secrets set` (value hidden in `fly secrets list`), never echoed into chat, a logged command, or this SUMMARY; `scrub_secrets` (plan 16-02) redacts `tvly-` as a log backstop.
- **T-16-13 (failure smoke leaves prod on an invalid key):** mitigated — the valid key was restored and confirmed **Deployed** (digest `feca87ad`, v36, both machines) before the phase was closed.
- **T-16-14 (wrong environment targeted):** mitigated — app name discovered via `fly status` (not hardcoded); prod distinguished from dev via `.env.prod` and the `boardgame-rag-prod` app name; owner approved each command.

## Next Phase Readiness

- Phase 16 (Web Search Restoration) is complete and prod-verified. `web_search` is live: cited web-grounded answers on success, red failed-state card + graceful degradation on failure, fail-closed when unkeyed.
- No blockers. Milestone v1.3 (Web Search & Agent Personas) can proceed to its next phase.

## Self-Check: PASSED

---
*Phase: 16-web-search-restoration*
*Completed: 2026-07-12*
