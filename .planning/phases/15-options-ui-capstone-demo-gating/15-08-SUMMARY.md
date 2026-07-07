---
phase: 15-options-ui-capstone-demo-gating
plan: 08
subsystem: infra
tags: [supabase, fly, cloudflare-pages, migrations, openrouter, demo-fallback, deploy]

# Dependency graph
requires:
  - phase: 15-options-ui-capstone-demo-gating (plans 01-07)
    provides: "Phase-15 code shipped in this deploy: prefs/favorites schema (033), free-guard + demo resolution branch, OAuth resume auto-apply, sectioned picker, key gate, demo banner + [Use demo] recovery"
  - phase: 999.2-cost-guardrail-burn-script
    provides: "SEC-03 PASS finding (guardrail 403 at $0.1026, both kill switches proven) that released this deploy's gate"
  - phase: 13-preferences-thread-model (plans 01-04)
    provides: "migrations 029-032 content (usage, model_cache, user_preferences, threads.model)"
provides:
  - "Prod Supabase (ybehhhduhynsdujmxdzx) migrated through 20240301000033 (029-033 applied this deploy)"
  - "Fly prod (boardgame-rag-prod) running Phase-15 backend with DEMO_FALLBACK_ENABLED=true (D-09 executed)"
  - "Cloudflare Pages serving the Phase-15 frontend (main fast-forwarded 8c0fcde..247503f)"
  - "DEMO-01 closed (flag ON in prod, env-driven only); SEC-03 closed (enabled atop the 999.2 PASS finding, deployment note satisfied)"
affects: [v1.2 milestone close, phase-15 verification, future demo-model slug maintenance]

# Tech tracking
tech-stack:
  added: []
  patterns: ["strict deploy ordering: migrations -> code deploy (flag OFF) -> flag flip -> frontend (Pitfall 10)", "prod DB ops via supabase --db-url from .env.prod DATABASE_URL (no relink of the dev-linked CLI)"]

key-files:
  created: [".planning/phases/15-options-ui-capstone-demo-gating/15-08-SUMMARY.md"]
  modified: [".planning/phases/15-options-ui-capstone-demo-gating/deferred-items.md"]

key-decisions:
  - "User approved 'proceed' at the Task-2 decision gate: prod schema push + cost-bearing DEMO_FALLBACK_ENABLED=true flip (D-09), cost bounded by D-03 free-guard / app flag / provider guardrail ~$0.10"
  - "Drift check + push ran via --db-url from .env.prod DATABASE_URL instead of relinking the CLI (dev link left untouched; read-only discipline)"
  - "No migration repair needed: prod history was clean through 028 (Open Q4 resolved: no)"

patterns-established:
  - "Secrets hygiene in deploy evidence: names + digests only, prefix checks via grep -c, log pipes scrubbed with sed s/sk-or-*/[redacted-key]/"

requirements-completed: [DEMO-01, SEC-03]

# Metrics
duration: ~50min active (wall clock 2026-07-07T03:53:18Z -> 19:40:26Z across two session windows with checkpoint pauses)
completed: 2026-07-07
---

# Phase 15 Plan 08: Human-Gated Capstone Deploy Summary

**Prod migrated 029-033, Phase-15 backend deployed to Fly with DEMO_FALLBACK_ENABLED=true, frontend shipped via master:main to Cloudflare Pages — live smoke approved-with-caveat (free-provider 429, environmental).**

## Performance

- **Duration:** ~50 min active execution (wall clock spans 2026-07-07T03:53:18Z → 2026-07-07T19:40:26Z including two blocking human checkpoints and a session-limit pause)
- **Started:** 2026-07-07T03:53:18Z
- **Completed:** 2026-07-07T19:40:26Z
- **Tasks:** 4/4 (2 auto, 2 human checkpoints)
- **Files modified:** 1 (deferred-items.md; the deploy itself touched zero repo files by design)

## Accomplishments

- **Prod schema current:** `supabase db push` (via `.env.prod` `DATABASE_URL`) applied exactly `20240301000029_add_usage_to_messages`, `030_create_model_cache`, `031_allow_null_model_cache_name`, `032_create_user_preferences_and_thread_model`, `033_add_favorite_models`; post-push `migration list` shows 001-033 local|remote in sync. No history repair was needed — remote history was clean through 028.
- **Strict flip ordering held (Pitfall 10 / T-15-29):** migrations → `flyctl deploy` with flag OFF (machine `80e35ef6015d48` healthy, `/api/health` 200) → `flyctl secrets set DEMO_FALLBACK_ENABLED=true` (rolling update succeeded, health 200 post-flip) → `git push origin master:main` (`8c0fcde..247503f`).
- **Frontend live:** Cloudflare Pages rebuilt from `main`; served bundle `/assets/index-BCWa5JJ7.js` at https://boardgame-rag-prod.pages.dev contains the Phase-15 demo-banner copy (probe-verified).
- **SEC-03 deployment note satisfied (T-15-31):** `LLM_API_KEY` confirmed present on Fly before the flip (names/digests only); `.env.prod` owner key confirmed `sk-or-` prefix via count-check. No secret value appeared in any output or log.
- **DEMO-01 + SEC-03 closed:** flag ON in prod, env-driven only (no admin UI); enabled atop the 999.2 PASS finding.

## Task Commits

1. **Task 1: Pre-flight go/no-go (read-only)** - `247503f` (docs: deferred-items D-15-08-A log; all four checks GO — suites, drift 029-033 pending/no repair, slug live with tools on Venice, LLM_API_KEY present + DEMO_FALLBACK_ENABLED absent)
2. **Task 2: Approve the prod flip (checkpoint:decision)** - no commit; user replied **"proceed"**
3. **Task 3: Ordered deploy sequence** - no commit (ops only, zero repo file changes per plan)
4. **Task 4: Live prod smoke (checkpoint:human-verify)** - no commit; outcome recorded below

**Plan metadata:** see final docs commit for this SUMMARY.

## Files Created/Modified

- `.planning/phases/15-options-ui-capstone-demo-gating/deferred-items.md` - added D-15-08-A (pre-existing env-coupled `test_config.py` failure)
- `.planning/phases/15-options-ui-capstone-demo-gating/15-08-SUMMARY.md` - this deploy record

## Checkpoint Outcomes

### Task 2 — checkpoint:decision

User replied **"proceed"** against the full go/no-go table (suites green modulo documented debt; drift exactly 029-033; slug `meta-llama/llama-3.3-70b-instruct:free` live with tools support on 1 endpoint (Venice); Fly secrets correct pre-flip).

### Task 4 — checkpoint:human-verify (live smoke)

**Outcome: APPROVED-WITH-CAVEAT.** User's verbatim response:

> "approved with caveat, everything works but before connecting an open router account the chat on the free model(s) does not work"

**Log diagnosis (read-only, `flyctl logs`, output scrubbed):** the failed keyless demo turns are **environmental free-provider rate-limiting, not a code defect** — the exact acceptable-caveat case pre-declared in this plan's Task 4 step 3 and the D-999.1-LLM-A precedent (single Venice endpoint, ~88% uptime):

- One error class in the whole log window: `openai.RateLimitError` **429** from OpenRouter — `'qwen/qwen3-coder:free is temporarily rate-limited upstream. Please retry shortly, or add your own key...'`, `provider_name: 'Venice'`, `Retry-After: 29`.
- **The demo resolution branch behaved correctly:** `is_byok: False` in the provider error metadata proves the turn was minted on the owner key (DEMO-01 branch taken for the keyless user); the `:free` slug passed the D-03 free-guard; the chat route logged "Chat rate-limited" and returned **200 with the error in-band** (the designed SSE error + recovery seam — `POST /api/threads/{id}/messages?retry=true` visible, i.e. the retry/[Use demo] path was exercised).
- No 403 guardrail trip, no auth errors, no 5xx, no backend exception beyond the upstream 429.
- The banner rendering implies `/api/keys/status` returned `demo_enabled=true` correctly (endpoint 200s in the log; user confirmed all non-chat checks work).
- **Post-connect path all green live:** `POST /api/keys/openrouter/exchange` 200 → `PATCH /api/threads/{id}` 200 → keys/status + balance 200 — matching the user's "everything works" after connecting (KEY/OAuth auto-apply resume verified live).

**Verdict:** functional deliverable verified; the caveat is provider-side availability of free models at smoke time. Per plan context: "do not retry-until-green against the live provider."

## Decisions Made

- Ran the prod drift check and push with `--db-url` from `.env.prod` `DATABASE_URL` rather than relinking the CLI (dev link `ntkkmljbariflblldmha` untouched).
- No `migration repair` executed — dry-run + `migration list` proved history clean through 028 (Open Q4: no repair needed).
- Kept the pinned demo slug `meta-llama/llama-3.3-70b-instruct:free` (probe: HTTP 200, tools supported) — no config default change rode the deploy.

## Deviations from Plan

None auto-fixed — the deploy sequence executed exactly as written. Out-of-scope discoveries were logged, not fixed (scope boundary):

- **D-15-08-A (new):** `backend/tests/test_config.py::test_key_encryption_secret_default` fails whenever the local `.env` carries `KEY_ENCRYPTION_SECRET` (test does not isolate the process env; code default at `backend/config.py:24` is correct). Pre-existing, zero deploy relevance. Fix is a one-line `monkeypatch.delenv` in a future test-debt pass. Secret-hygiene note: the pytest assertion diff echoes the local secret value in terminal output — value not reproduced in any artifact.
- **D-15-03-A (known):** 5 pre-existing full-repo lint errors, none in files this plan touches.

## Issues Encountered

- `main` was found sitting at the repo-initial commit ("create .gitkeep") before the frontend push — the `master:main` push fast-forwarded it to the full current tree (`8c0fcde..247503f`), so this CF build is the first from `main` carrying the complete history. Worth remembering if CF build history looks sparse.
- Fly deploy printed a transient "app not listening on 0.0.0.0:8000" warning mid-rolling-update (before uvicorn bound); subsequent smoke/machine/health checks and a direct `/api/health` 200 confirmed it was boot-timing noise.
- Residual (accepted): byte-equality between the Fly `LLM_API_KEY` and the `.env.prod` owner key cannot be proven without exposing values; presence + `sk-or-` prefix + the Phase-10 deploy record + the guardrail-lives-on-the-key property (999.2) cover T-15-31.

## Known Stubs

None — this plan created no code; the deploy shipped previously-verified Phase-15 code.

## Threat Flags

None — no new security surface beyond the planned threat model. The one public-surface change (keyless users minting owner-key free-model completions) is exactly T-15-28 with all three mitigations live: D-03 free-guard, app flag, provider guardrail (~$0.10).

## User Setup Required

None - all external configuration (Fly secret, prod migrations, CF build) was performed by this plan with user approval at the decision gate.

## Next Phase Readiness

- v1.2 capstone is live end-to-end: DEMO-01 and SEC-03 closed; DEMO-02 observable live.
- Note for the phase-completion state update (per plan verification): the stale STATE.md "shadcn init" pending todo is superseded by the UI-SPEC (Phase 15 shipped its picker without shadcn Combobox) — close it when the orchestrator updates tracking.
- Free-model availability remains environmental (single Venice endpoint on the pinned demo slug); if it degrades further, a config-default slug change is a one-line, low-risk follow-up.
- Prod migration debt from project memory ("029-032 unapplied") is now cleared through 033.

## Self-Check: PASSED

- FOUND: `.planning/phases/15-options-ui-capstone-demo-gating/15-08-SUMMARY.md`
- FOUND: commit `247503f` (Task 1)
- Verified live: prod `migration list` 001-033 in sync; Fly secrets list shows `DEMO_FALLBACK_ENABLED`; `/api/health` 200 post-flip; CF bundle `/assets/index-BCWa5JJ7.js` carries Phase-15 banner copy

---
*Phase: 15-options-ui-capstone-demo-gating*
*Completed: 2026-07-07*
