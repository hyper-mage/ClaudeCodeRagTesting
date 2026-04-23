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

## Cross-Milestone Trends

### Process Evolution

| Milestone | Plans | Phases | Key Change |
|-----------|-------|--------|------------|
| v1.0 | 21 | 7 (incl. 03.1) | Baseline — gsd workflow + decimal gap closure |

### Cumulative Quality

| Milestone | REQ Coverage | Integration | Nyquist |
|-----------|--------------|-------------|---------|
| v1.0 | 39/39 (100%) | 0 orphans, 0 broken | 1/7 compliant |

### Top Lessons (Verified Across Milestones)

1. *(Needs v1.1+ to cross-validate)*
