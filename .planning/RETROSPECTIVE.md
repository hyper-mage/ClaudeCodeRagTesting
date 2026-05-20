# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

## Milestone: v1.0 — KB Navigation & Agentic RAG

**Shipped:** 2026-04-23
**Phases:** 7 (01, 02, 03, 03.1, 04, 05, 06) | **Plans:** 21 | **Tasks:** 40
**Timeline:** 2026-01-21 → 2026-04-22 (~3 months)

### What Was Built
- ltree-based folder hierarchy with mixed-visibility RLS (public default KB + private user docs, single table)
- 5 Claude Code-inspired KB navigation tools (kb_ls, kb_tree, kb_read, kb_grep, kb_glob) via Supabase RPCs
- 10-game default KB seeded via idempotent content-hash script
- Image OCR + XLSX ingestion via Docling
- File manager UI with tree sidebar, drag-drop, context menus, bulk operations
- Explorer sub-agent (run_exploration generator) with find_similar/recommendation modes + nested sub_event SSE
- TokenBudget, source routing, scope parsing, colored scope badge in ToolCallCard
- analyze_document contract aligned with run_exploration (unified sub_event path)
- Retroactive 03-VERIFICATION.md + v1.0 audit closure via decimal gap phase 03.1

### What Worked
- **Decimal gap phases (03.1)** — closing verification debt without rework or re-planning. Fast, scoped, auditable.
- **Phase-per-capability breakdown** — each phase shipped a testable chunk; integration checker found zero orphans across 39 REQ-IDs.
- **Belt-and-suspenders RLS** — DB policy + explicit `.or_()` filters in kb_tools_service. Caught nothing (policies correct) but cheap insurance.
- **Unified SSE contract** — tool_start/tool_result/sub_event with call_id correlation made Phase 05 (sub-agent) and Phase 06 (analyze_document retrofit) trivial to wire.

### What Was Inefficient
- **Phase 3 shipped without VERIFICATION.md** — required Phase 03.1 to retroactively close. If verifier had run per-phase from the start, 03.1 unnecessary.
- **Nyquist validation partial** — 5/7 phases have VALIDATION.md with `nyquist_compliant: false`. Tech debt for future validate-phase passes.
- **Executor rate-limit mid-plan** — Phase 03.1 Plan 01 execution split across limit boundary. Orchestrator finalized inline. Cost: minor context re-load.
- **Phase 03 `kb_read` None-folder crash** — caught in UAT late, fixed in Plan 05; better plan-level validation could have caught earlier.

### Patterns Established
- **Doc-only gap-closure phase** (03.1): decimal number, gap_closure=true frontmatter, cites file:line evidence from parent phase code, no app changes
- **Audit Dry-Run Cross-Check table**: explicit mapping of audit gaps → closing artifacts → CLOSED status
- **Sub-agent as generator + queue bridge**: Iterator[dict] contract, asyncio.to_thread + queue.Queue, parent_call_id correlation — reused for analyze_document in Phase 06
- **Scope/source hint injection**: parse_scope_hint → stream_chat_completion params → system prompt blocks → args_preview prefix → UI badge

### Key Lessons
1. Run `/gsd:verify-work` at phase boundary every time. Retroactive VERIFICATION.md works but costs a phase.
2. Early SSE protocol design (tool_start/tool_result/sub_event + call_id) paid compound dividends — Phases 03/05/06 all reused it without contract changes.
3. Doc-only gap phases are cheap and auditable. Don't skip them to "save a phase."
4. Nyquist validation as retroactive cleanup is fine — don't block shipping on it.

### Cost Observations
- Model mix: primarily Opus (gsd agents inherit)
- Sessions: ~20-30 across 3 months
- Notable: executor rate limit hit during 03.1 execution (orchestrator recovery worked; no work lost)

---

## Milestone: v1.1 — Portfolio Deployment

**Shipped:** 2026-05-20
**Phases:** 9 (01, 02, 03, 04, 05, 06, 06.1, 07, 08) | **Plans:** 28 | **Tasks:** 53
**Timeline:** 2026-04-22 → 2026-05-20 (~4 weeks) | **Commits:** 179

### What Was Built
- Repo-root single-stage Docker image — FastAPI + Docling + native deps, non-root, CPU torch, preloaded models — with an end-to-end build/boot/ingest smoke script
- Dedicated prod Supabase project — migrations, pgvector, RLS, Storage, default KB seeded (10 docs / 11 folders / 62 chunks)
- Public deploy — backend on Fly.io (free-tier suspend), Vite SPA on Cloudflare Pages with SPA deep-link routing
- Production hardening — env CORS allowlist, per-user chat rate limit, tool-loop max-iterations cap, anon-JWT auth, secrets in host env stores
- Mobile-responsive chat shell (Phase 6.1, inserted) — hamburger drawer + reusable mobile primitives
- Observability baseline — Sentry (source maps + PII scrub), prod LangSmith project, 2 UptimeRobot monitors, DB-probing `/api/health`
- Portfolio polish — Try-demo anon onboarding, graceful error/retry UX, architecture diagram + screenshots + hero GIF, portfolio README, shields.io badges

### What Worked
- **Interactive resume for user-driven work** — Phase 8 had 5 dashboard/deploy/capture actions only the human could do; one-action-at-a-time resume with paste-ready instructions kept it unambiguous.
- **UAT caught real prod bugs** — the Phase 8 deployed UAT surfaced two genuine deploy bugs (Docker missing `data/` bundle; useChat silently swallowing SSE `event: error`) that unit tests + code-only verification missed.
- **Gap-fix during UAT, not after** — both bugs were root-caused, patched, committed, and re-tested inside the UAT loop (3 runs) rather than deferred.
- **Milestone audit caught stale bookkeeping** — re-audit cross-referenced VERIFICATION + SUMMARY frontmatter + traceability; surfaced 2 phases missing verification artifacts + a traceability table frozen at planning time.

### What Was Inefficient
- **Verification artifacts inconsistent** — Phases 03 and 07 reached milestone audit with no phase-level VERIFICATION.md; closed retroactively via `/gsd:verify-work`. Phase 06's 4 SUMMARYs all had empty `requirements-completed` frontmatter.
- **REQUIREMENTS.md traceability went stale** — Status column + checkboxes were never updated during execution; all 23 rows had to be refreshed at milestone close.
- **UAT env-var mismatch** — Phase 8 UAT spec said break `OPENROUTER_API_KEY`, but the backend reads `LLM_API_KEY` (resolved-key chain) — a false-negative test run before the spec was corrected.
- **Wrong-Supabase-project round-trip** — a verification REST call sourced from `.env` (dev project) instead of `.env.prod`, hit the wrong project. Now captured as a project memory.

### Patterns Established
- **Two-env Supabase split** — `.env` = dev project, `.env.prod` = prod; verify prod work against `.env.prod`
- **Two-candidate path resolution** — `SAMPLE_DOC_PATH` resolves both repo-root (dev/test) and `/app` (container) layouts via an existence-checked candidate list
- **ffmpeg two-pass palette GIF** — speed-ramped MP4 → palettegen → paletteuse for sub-5 MB hero GIFs
- **Decimal phase insertion mid-milestone** (06.1) — same pattern as v1.0's 03.1, used here for an urgent mobile fix

### Key Lessons
1. Run `/gsd:verify-work` at every phase boundary — same lesson as v1.0, and v1.1 repeated the mistake on Phases 03 + 07. The retroactive close works but the milestone audit pays for it.
2. Deployed UAT is non-negotiable for deploy phases — code-only verification passed both Phase 8 bugs; only a live browser test caught them.
3. Keep `requirements-completed` frontmatter populated as plans land — empty frontmatter forced a manual 3-source cross-reference at milestone close.
4. UAT instructions that name env vars / secrets must be checked against the actual config resolution chain before the run.

### Cost Observations
- Model mix: primarily Opus (gsd agents inherit; agents not installed → workflows ran inline in the orchestrator)
- Sessions: ~15-25 across 4 weeks
- Notable: 179 commits, +34.5k LOC; free-tier LLM during Phase 8 made the hero-GIF capture slow (114 s raw → 6.4× sped to 18 s)

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Plans | Phases | Key Change |
|-----------|-------|--------|------------|
| v1.0 | 21 | 7 (incl. 03.1) | Baseline — gsd workflow + decimal gap closure |
| v1.1 | 28 | 9 (incl. 06.1) | Deploy milestone — interactive resume for human-driven work; UAT-driven gap-fix loop |

### Cumulative Quality

| Milestone | REQ Coverage | Integration | Nyquist |
|-----------|--------------|-------------|---------|
| v1.0 | 39/39 (100%) | 0 orphans, 0 broken | 1/7 compliant |
| v1.1 | 23/23 (100%) | 0 orphans, 0 broken (live E2E) | 0/9 compliant — tech debt |

### Top Lessons (Verified Across Milestones)

1. **Run `/gsd:verify-work` at every phase boundary.** Verified across v1.0 (Phase 03 → 03.1) and v1.1 (Phases 03 + 07 retroactive). Skipping it always costs at milestone-audit time.
2. **Nyquist validation slips to tech debt every milestone** (v1.0: 1/7, v1.1: 0/9). Either enforce it per-phase or formally accept it as a recurring deferral — the current middle ground just accumulates.
3. **A well-designed SSE / contract layer compounds** — v1.0's tool_start/tool_result/sub_event protocol carried into v1.1's error-event handling (the one gap was the frontend not handling `event: error`, fixed in Phase 8).
