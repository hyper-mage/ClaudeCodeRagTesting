# Roadmap — Board Game Knowledge Base RAG

## Milestones

- ✅ **v1.0 KB Navigation & Agentic RAG** — 7 phases (shipped 2026-04-23) — see `milestones/v1.0-ROADMAP.md`
- ✅ **v1.1 Portfolio Deployment** — 9 phases (shipped 2026-05-20) — see `milestones/v1.1-ROADMAP.md`

## Phases

<details>
<summary>✅ v1.1 Portfolio Deployment (Phases 1-8 + 6.1) — SHIPPED 2026-05-20</summary>

- [x] Phase 1: Secrets & Repo Hygiene (2/2 plans)
- [x] Phase 2: Dockerize Backend (1/1 plans)
- [x] Phase 3: Prod Supabase Project (2/2 plans)
- [x] Phase 4: Deploy Backend to Fly.io (2/2 plans)
- [x] Phase 5: Deploy Frontend to Cloudflare Pages (1/1 plans)
- [x] Phase 6: Prod Wiring — Auth, CORS, Rate Limiting, Cost Caps (5/5 plans)
- [x] Phase 6.1: Mobile-Responsive Chat Layout (2/2 plans) — inserted after Phase 6
- [x] Phase 7: Observability Baseline (5/5 plans)
- [x] Phase 8: Portfolio Polish (8/8 plans)

Full phase detail archived in `milestones/v1.1-ROADMAP.md`. Audit: passed, 23/23 requirements (`milestones/v1.1-MILESTONE-AUDIT.md`).

</details>

## Backlog

### Phase 999.1: Chat empty-state UX (BACKLOG)

**Goal:** When no threads exist, sending a chat message silently does nothing. Either block the input until "+ New Chat" is clicked OR auto-create an initial thread on first message send. Caught during Phase 3 UAT.
**Requirements:** TBD
**Plans:** 1/1 plans complete

Plans:
- [ ] TBD (promote with /gsd:review-backlog when ready)

### Phase 999.2: Cost guardrail burn script (BACKLOG)

**Goal:** Programmatic test to trip the OpenRouter $0.10 cost guardrail. Mint N parallel chat requests against the paid model (`openai/gpt-4o-mini` ~$0.005/call → ~20 reqs) from a script in `backend/scripts/`. Watch credits page for $0.10 delta + inbox for delivery email. Captured during 06-04 friend-testing reached only $0.0105 (10.5% of trip) before benching. Verifies whether OpenRouter Guardrail trip emits email-on-trip OR just blocks calls — current behavior unknown. Surface during v1.2 BYO-key + multi-model picker phase planning.
**Requirements:** TBD
**Plans:** 0 plans

Plans:
- [ ] TBD (promote with /gsd:review-backlog when ready)
