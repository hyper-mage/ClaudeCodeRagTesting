---
phase: 15
slug: options-ui-capstone-demo-gating
status: approved
nyquist_compliant: true
wave_0_complete: true
created: 2026-07-02
updated: 2026-07-03
---

# Phase 15 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Populated from 15-RESEARCH.md §Validation Architecture and the 8 phase plans (revision 1).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework (FE)** | vitest 4.1.9 + @testing-library/react 16.3.2 + jsdom (config `frontend/vitest.config.ts`, setup `src/test/setup.ts`, harness `src/test/utils.tsx`) |
| **Framework (BE)** | pytest via `backend/venv` (conftest at `backend/tests/conftest.py`) |
| **Quick run command (FE)** | `cd frontend && npx vitest run <file>` (per-file) |
| **Quick run command (BE)** | `cd backend && venv/Scripts/python.exe -m pytest <file> -x -q` |
| **Full suite command (FE)** | `cd frontend && npm run test` (= `vitest run`) |
| **Full suite command (BE)** | `cd backend && venv/Scripts/python.exe -m pytest tests/ -q` — 2 pre-existing `test_record_manager.py` fixture errors are documented debt, tolerated, do not fix here |
| **Static gates** | `cd frontend && npm run build` (tsc -b + vite) and `npm run lint` |
| **Estimated runtime** | per-file runs < 15s; FE full ~60s; BE full ~30s |

---

## Sampling Rate

- **After every task commit:** the focused per-file command for the seam touched (FE per-file vitest run or BE per-file pytest) + `npm run lint` for FE tasks
- **After every plan wave:** both full suites (`npm run test`; `pytest tests/ -q`) + `npm run build` — run at the wave MERGE only, never inside parallel same-wave plans (waves 1–3 share one working tree)
- **Before `/gsd-verify-work`:** full suites green (modulo the 2 documented record_manager errors) + build + lint
- **Max feedback latency:** ~60 seconds (full FE suite); focused runs < 15s

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 15-01-01 | 01 | 1 | MODEL-08 | T-15-03 | `favorite_models` bounded with `max_length=200` (Open Q3) | unit (inline asserts) | `venv python -c` schema-default asserts (see plan) | ✅ inline | ⬜ pending |
| 15-01-02 | 01 | 1 | MODEL-08, DEMO-01 | T-15-01 / T-15-02 | `demo_enabled` in BOTH status branches; `user_id` JWT-bound in upsert | unit (BE, TDD) | `pytest tests/test_keys_status.py tests/test_preferences_api.py -x -q` | ✅ extend | ⬜ pending |
| 15-01-03 | 01 | 1 | MODEL-08 | — | live-schema probe (column real, not just authored) | integration | `supabase migration list` grep 033 + live column probe | ✅ inline | ⬜ pending |
| 15-02-01 | 02 | 1 | DEMO-01, SEC-03 | T-15-05 / T-15-06 | killswitch trio pinned green while new tests RED | unit (BE, TDD RED) | trio `-k` run `&& !` new-tests `-k` run (trio-green AND new-red) | ✅ extend | ⬜ pending |
| 15-02-02 | 02 | 1 | DEMO-01, SEC-03 | T-15-05..T-15-09 | free-guard `is_free is True`; `use_demo` inert when flag OFF; fail-closed no_key tail intact | unit (BE) | `pytest tests/test_key_model_resolution.py -x -q` | ✅ extend | ⬜ pending |
| 15-03-01 | 03 | 1 | KEY-05 | T-15-10 / T-15-11 | returnTo allowlist + one-shot remove-first asserted in tests | component (TDD RED) | `! npx vitest run src/pages/OAuthCallbackPage.test.tsx` (RED) | ❌ W0 — created by this task | ⬜ pending |
| 15-03-02 | 03 | 1 | KEY-05 | T-15-10..T-15-13 | remove-first one-shot; allowlisted `navigate()`; locked toast strings only | component | `npx vitest run src/pages/OAuthCallbackPage.test.tsx` + build + lint | ✅ after 15-03-01 | ⬜ pending |
| 15-04-01 | 04 | 2 | MODEL-01 | — | N/A (pure ranking spec) | unit | `npx vitest run src/lib/fuzzy.test.ts` | ❌ W0 — created by this task | ⬜ pending |
| 15-04-02 | 04 | 2 | MODEL-03 | T-15-14 | `is_free`/`popularity_rank` rendered verbatim, never recomputed client-side | component | `npx vitest run src/components/ModelSelector.test.tsx` + lint | ✅ extend | ⬜ pending |
| 15-04-03 | 04 | 2 | MODEL-01 | T-15-15 / T-15-16 | 150ms debounce; query stays local, never sent to any API | component | `npx vitest run src/components/ModelSelector.test.tsx` + build + lint | ✅ extend | ⬜ pending |
| 15-05-01 | 05 | 2 | KEY-05 | — | dark danger dialog output byte-identical (no visual regression) | static gate | `npm run build && npm run lint` (+ grep acceptance checks) | n/a (type gate) | ⬜ pending |
| 15-05-02 | 05 | 2 | KEY-05 | T-15-17..T-15-20 | full gate decision table; stash carries zero secret material | component (hook, TDD) | `npx vitest run src/hooks/useKeyGate.test.tsx` + lint | ❌ W0 — created by this task | ⬜ pending |
| 15-05-03 | 05 | 2 | KEY-05 | T-15-18 | stale-stash clears at all non-gate launchers; no half-apply before gate | component | `npx vitest run src/pages/ChatPage.test.tsx src/components/DefaultModelSelector.test.tsx` + build + lint | ✅ extend | ⬜ pending |
| 15-06-01 | 06 | 3 | MODEL-08 | T-15-21 / T-15-22 | PUT body exactly `{favorite_models}`; server binds user_id (15-01) | component (TDD) | `npx vitest run src/components/ModelSelector.test.tsx` + lint | ✅ extend | ⬜ pending |
| 15-06-02 | 06 | 3 | MODEL-08 | T-15-23 | silent failure path renders nothing sensitive (no toast, no revert) | component | `npx vitest run src/components/ModelSelector.test.tsx` + build + lint | ✅ extend | ⬜ pending |
| 15-07-01 | 07 | 3 | DEMO-02, DEMO-01 | T-15-24 | normal sends carry NO `use_demo` key; override only via demo retry | component (hook, TDD) | `npx vitest run src/hooks/useChat.test.tsx` + lint | ✅ extend | ⬜ pending |
| 15-07-02 | 07 | 3 | DEMO-02 | T-15-25..T-15-27 | LOCKED banner copy verbatim; role="status"; no interactive children | component | `npx vitest run src/components/ChatContainer.test.tsx src/pages/ChatPage.test.tsx` + build + lint | ✅ extend | ⬜ pending |
| 15-08-01 | 08 | 4 | DEMO-01, SEC-03 | T-15-30 | secrets listed by NAME/digest only; zero writes | integration (read-only pre-flight) | both full suites + FE build (single-plan wave — safe) | ✅ | ⬜ pending |
| 15-08-02 | 08 | 4 | SEC-03 | T-15-28 | cost-bearing flip requires explicit user approval (D-09) | manual — checkpoint:decision | — (resume signal recorded in SUMMARY) | n/a | ⬜ pending |
| 15-08-03 | 08 | 4 | DEMO-01, SEC-03 | T-15-29 / T-15-31 | strict order: migrations → code deploy → flag flip; abort on failure | integration (ops) | `supabase migration list` grep-count + `flyctl secrets list` grep DEMO_FALLBACK_ENABLED | n/a (ops) | ⬜ pending |
| 15-08-04 | 08 | 4 | DEMO-01, DEMO-02, KEY-05 | T-15-28 | live smoke on signed-in keyless account (Open Q5 resolution) | manual — checkpoint:human-verify | — (live OAuth + provider round-trip is the test) | n/a | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

**Wave-merge gates (full-suite regression, run once per wave after ALL wave plans complete — never inside parallel same-wave plans):**

| Gate | Command | Green Criteria |
|------|---------|----------------|
| Wave 1 merge | `pytest tests/ -q` + `npm run test` + `npm run build` | 0 new failures (2 record_manager errors tolerated) |
| Wave 2 merge | `npm run test` + `npm run build` + `npm run lint` | all exit 0 |
| Wave 3 merge | `npm run test` + `pytest tests/ -q` + `npm run build` + `npm run lint` | 0 new failures |
| Phase gate | both full suites + build + lint before `/gsd-verify-work` | green; 15-08 live smoke is the final human gate |

---

## Wave 0 Requirements

No separate Wave 0 execution is needed — every MISSING test file from the RESEARCH gap list is created by a RED-first (TDD) task inside its owning plan, ordered before the implementation task:

- [x] `frontend/src/lib/fuzzy.test.ts` — created by 15-04 Task 1 (MODEL-01 locked ranking spec)
- [x] `frontend/src/hooks/useKeyGate.test.tsx` — created by 15-05 Task 2 (KEY-05 decision table + stash contract)
- [x] `frontend/src/pages/OAuthCallbackPage.test.tsx` — created by 15-03 Task 1 (KEY-05 resume lifecycle, RED before GREEN)
- [x] Framework install: none — both harnesses fully operational (vitest + pytest scaffolding verified live in RESEARCH)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Prod flip approval (go/no-go on migrations 029-033 + `DEMO_FALLBACK_ENABLED=true`) | SEC-03 / DEMO-01 | cost-bearing prod mutation requires explicit user decision (D-09) | 15-08 Task 2 checkpoint:decision — reply `proceed` or `abort` against the Task-1 go/no-go table |
| Live prod smoke: banner, free-pick stream, paid-pick gate → OAuth → auto-apply, favorites persistence | DEMO-01 / DEMO-02 / KEY-05 | live OpenRouter OAuth + provider round-trip requires the real user account | 15-08 Task 4 six-step checklist — SIGNED-IN keyless account, NOT the anon path (Open Q5 resolution; anon bootstrap pre-broken D-999.1-DEMO-A) |
| Dark-mode disconnect dialog visually unchanged after ConfirmDialog variant work | KEY-05 | pixel-identity spot check (byte-identical class output asserted by grep, visual parity by eye) | open Settings in dark mode after 15-05, open the disconnect dialog, compare against pre-phase appearance |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies — the only two MISSING markers are the 15-08 human checkpoints (checkpoint:decision / checkpoint:human-verify), which are the tests themselves
- [x] Sampling continuity: no 3 consecutive tasks without automated verify (every auto task carries a focused command)
- [x] Wave 0 covers all MISSING references (embedded as RED-first tasks in 15-03/15-04/15-05, each ordered before its implementation task)
- [x] No watch-mode flags (all vitest invocations use `vitest run`; pytest uses `-q`/`-x`)
- [x] Feedback latency < 60s (focused per-file runs < 15s; full suites reserved for wave merges)
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved — revision 1, 2026-07-03 (populated from 15-RESEARCH.md §Validation Architecture + plans 15-01..15-08)
