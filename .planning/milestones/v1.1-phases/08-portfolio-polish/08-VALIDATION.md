---
phase: 8
slug: portfolio-polish
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-17
---

# Phase 8 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Source contracts derived from `08-RESEARCH.md` § Validation Architecture.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework (backend)** | pytest (existing — see `backend/tests/`) |
| **Framework (frontend)** | none yet (no unit test framework wired; manual UAT for UI surfaces) |
| **Config file (backend)** | `backend/pytest.ini` (if present) or pytest defaults |
| **Quick run command (backend)** | `cd backend && venv/Scripts/python -m pytest tests/test_demo_bootstrap.py tests/test_anon_cleanup.py tests/test_auth_anon.py -x -q` |
| **Full suite command (backend)** | `cd backend && venv/Scripts/python -m pytest -x` |
| **README structural checks** | `grep -F "## Live demo" README.md && grep -F "## Tech stack" README.md && grep -F "## Services" README.md && grep -F "Try demo" README.md && grep -F "docs/architecture" README.md && grep -F "shields.io" README.md` (5–8 grep assertions, sub-second) |
| **Frontend type check** | `cd frontend && npm run build` (tsc + Vite — catches type errors in new components/hooks) |
| **Estimated runtime** | backend ~15 s · frontend build ~30 s · README greps <1 s |

---

## Sampling Rate

- **After every task commit:** Run the quick backend command if the task touches `backend/`; run `cd frontend && npx tsc --noEmit` if the task touches `frontend/`; run README greps if the task touches `README.md` / `docs/`.
- **After every plan wave:** Full backend suite + full frontend build.
- **Before `/gsd-verify-work`:** Full suite green + manual UAT checklist passed against deployed CF Pages + Fly URLs.
- **Max feedback latency:** ≤30 s (frontend build is the long pole).

---

## Per-Task Verification Map

> Filled in by `/gsd-plan-phase` planner as it generates tasks. Each task gets one row.
> Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 08-00-01 | 00 | 0 | PORT-01 | — | Test fixtures + stub files for anon-auth + bootstrap + cleanup | scaffold | `cd backend && venv/Scripts/python -m pytest tests/test_demo_bootstrap.py --collect-only` | ❌ W0 | ⬜ pending |
| 08-01-XX | 01 | 1 | PORT-01 | T-08-01 (anon JWT misverification) | Anon JWT verified by `backend/auth.py`; RLS isolates anon `user_id` | unit + manual | `pytest tests/test_auth_anon.py -x` | ❌ W0 | ⬜ pending |
| 08-02-XX | 02 | 1 | PORT-01 | T-08-02 (cleanup orphans) | `/api/demo/bootstrap` deletes >7d anon users + cascades; ingests sample doc; seeds threads | unit + integration | `pytest tests/test_demo_bootstrap.py tests/test_anon_cleanup.py -x` | ❌ W0 | ⬜ pending |
| 08-03-XX | 03 | 2 | PORT-02 | T-08-03 (retry duplicate row) | Retry deletes prior failed assistant row, no duplicate insert | unit | `pytest tests/test_chat_retry.py -x` + manual chat-error UAT | ❌ W0 | ⬜ pending |
| 08-04-XX | 04 | 2 | PORT-02 | — | ErrorMessageBubble + Toast render error variant; retry button resends last user message | manual UAT + type check | `cd frontend && npm run build` + manual checklist | ❌ W0 | ⬜ pending |
| 08-05-XX | 05 | 3 | PORT-03 | — | README contains required sections; docs/MASTERCLASS.md exists; tech tables present | grep | `grep -F "## Live demo" README.md && grep -F "## Tech stack" README.md && test -f docs/MASTERCLASS.md` | ✅ | ⬜ pending |
| 08-06-XX | 06 | 3 | PORT-03 | — | Architecture diagram asset committed + linked | file + grep | `test -f docs/architecture.png && grep -F "docs/architecture" README.md` | ✅ | ⬜ pending |
| 08-07-XX | 07 | 3 | PORT-03 | — | ≥4 screenshots + 1 hero GIF committed + linked from README | file + grep | `ls docs/screenshots/*.png \| wc -l (≥4) && ls docs/hero.gif && grep -F "docs/hero" README.md` | ✅ | ⬜ pending |
| 08-08-XX | 08 | 3 | PORT-04 | — | UptimeRobot + last-deploy badges present in README | grep | `grep -F "shields.io" README.md && grep -F "uptime" README.md && grep -F "last-commit" README.md` | ✅ | ⬜ pending |

*Planner refines this table during step 8 as actual task IDs are issued.*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_auth_anon.py` — anon JWT verification + RLS isolation stubs (PORT-01 T-08-01)
- [ ] `backend/tests/test_demo_bootstrap.py` — `/api/demo/bootstrap` endpoint stubs: first-anon ingests sample doc + seeds 1–2 threads; idempotent on repeat call (PORT-01)
- [ ] `backend/tests/test_anon_cleanup.py` — cascade-delete >7d anon users; preserves recent anon users; deletes storage objects (PORT-01 T-08-02)
- [ ] `backend/tests/test_chat_retry.py` — retry deletes prior failed assistant row before inserting new placeholder (PORT-02 T-08-03)
- [ ] `backend/tests/conftest.py` — shared fixtures: `anon_jwt`, `permanent_jwt`, `seed_sample_doc`, `supabase_admin_client`
- [ ] `data/sample-private-docs/dnd5e-quickref.md` — hand-written CC-BY 4.0 5e SRD-derived quick reference (≤2 MB, Docling-ingestable)
- [ ] `docs/sample-credits.md` — attribution stub for D&D 5e SRD CC-BY 4.0

*Frontend has no test framework wired (CLAUDE.md confirms). Manual UAT covers React surfaces — see "Manual-Only Verifications".*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| "Try demo" CTA renders above email/password form on LoginPage and signs in anon user with one click | PORT-01 | Visual + interaction; no frontend unit tests | Load deployed CF Pages URL in fresh incognito window → click "Try the demo" → assert chat loads with seeded thread + sample D&D doc visible in Documents page |
| Inline error bubble + toast appear when LLM provider fails | PORT-02 | Requires forcing a real LLM failure (`OPENROUTER_API_KEY` to bogus value on Fly, or rate-limit burst) | `flyctl secrets set OPENROUTER_API_KEY=invalid` → send chat from prod UI → assert red bubble in thread + transient toast + Retry button; restore key after |
| Retry resends last user message and produces a successful answer | PORT-02 | Visual confirmation + DB inspection | After triggering error: click Retry → assert new assistant turn streams + no duplicate assistant row in `messages` table for that thread |
| Tool failure stays silent (rerank/web_search/subagent error in agent loop) | PORT-02 | Backend-side fault injection; UI must show NOTHING | Stub rerank service to raise → send chat needing rerank → assert assistant answer arrives normally + LangSmith trace shows tool error + UI shows no error indicator |
| Demo identity pill renders on IconSidebar / MobileTopBar / drawer when `user.is_anonymous` is true | PORT-01 + UI-SPEC | Conditional render, mobile + desktop | Anon-sign-in via Try demo → assert amber "Demo" pill visible desktop + mobile; permanent user sign-in → assert pill absent |
| Mobile parity: Try demo CTA, error bubble, toast, Demo pill all render correctly ≤768px | UI-SPEC (Phase 06.1 baseline) | Real-device or DevTools mobile emulation | Chrome DevTools 375×667 + 414×896 → walk every surface; verify touch targets ≥44px |
| Hero GIF + screenshots render correctly in README on GitHub | PORT-03 | GitHub markdown rendering varies from local preview | Push README → load repo on github.com → assert images render inline + alt text visible |
| Deploy-status + uptime badges render and link correctly | PORT-04 | Live shields.io / UR responses | Load README on github.com → click both badges → assert UR badge SVG returns + last-commit badge reflects current branch HEAD |
| Anon cleanup of >7d anon users runs on next signin without blocking signin UX | PORT-01 | Time-based behavior; requires seeded old anon user | SQL-insert an old anon user via service-role client (created_at = now() - interval '8 days') → trigger new anon signin → assert old user + cascaded rows + storage objects deleted; assert signin latency < 2 s |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify (frontend-only chains rely on `npm run build` type check as proxy)
- [ ] Wave 0 covers all MISSING references (5 new test files + 1 sample doc + credits stub)
- [ ] No watch-mode flags (all commands `-x -q` single-run)
- [ ] Feedback latency < 30 s
- [ ] `nyquist_compliant: true` set in frontmatter (after planner fills task IDs)
- [ ] Manual UAT checklist matches the 9 surfaces above + the 12-point Phase 06.1 pattern

**Approval:** pending
