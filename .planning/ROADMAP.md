# Roadmap: Board Game Knowledge Base RAG

## Milestones

- ✅ **v1.0 KB Navigation & Agentic RAG** — Phases 1-7 (shipped 2026-04-23) — [archive](milestones/v1.0-ROADMAP.md)
- ✅ **v1.1 Portfolio Deployment** — Phases 1-8 + 6.1 (shipped 2026-05-20) — [archive](milestones/v1.1-ROADMAP.md)
- ✅ **v1.2 User Options & BYOK** — Phases 9-15 + 999.1/999.2 (shipped 2026-07-11) — [archive](milestones/v1.2-ROADMAP.md)
- 🚧 **v1.3 Web Search & Agent Personas** — Phases 16-17 (in progress)

## Phases

### 🚧 v1.3 Web Search & Agent Personas (In Progress)

**Milestone Goal:** Restore the agent's web search tool end-to-end (prod-verified) and let users switch the chat agent persona per-thread — board-game expert (default) ↔ general assistant — with a user-level default, all personas retaining full tool access.

- [ ] **Phase 16: Web Search Restoration** — Fix and prod-verify the `web_search` tool (current Tavily auth), with cited sources and graceful failure
- [ ] **Phase 17: Agent Personas** — Predefined per-thread persona pin + user-level default, applied per request with no cross-user/thread bleed

<details>
<summary>✅ v1.2 User Options & BYOK (Phases 9-15 + 999.1/999.2) — SHIPPED 2026-07-11</summary>

- [x] Phase 9: Crypto + Encrypted Key Storage Foundation (3/3 plans)
- [x] Phase 10: OAuth PKCE Backend Exchange + Frontend Connect (4/4 plans)
- [x] Phase 11: Per-Request Key + Model Resolution Chat-Loop Seam (6/6 plans) — completed 2026-07-11 (SEC-01 prod gates)
- [x] Phase 12: Model Cache + Catalog (4/4 plans) — completed 2026-06-23
- [x] Phase 13: Preferences + Per-Thread Model (6/6 plans)
- [x] Phase 14: Usage/Cost Display + Settings Key-State UX (5/5 plans)
- [x] Phase 15: Options UI Capstone + Demo Gating (10/10 plans) — completed 2026-07-09
- [x] Phase 999.1: Chat Empty-State UX (3/3 plans) (INSERTED from backlog)
- [x] Phase 999.2: Cost Guardrail Burn Script (2/2 plans) (INSERTED from backlog — SEC-03 gate for Phase 15)

Full phase details: [milestones/v1.2-ROADMAP.md](milestones/v1.2-ROADMAP.md)

</details>

<details>
<summary>✅ v1.1 Portfolio Deployment (Phases 1-8 + 6.1) — SHIPPED 2026-05-20</summary>

See [milestones/v1.1-ROADMAP.md](milestones/v1.1-ROADMAP.md)

</details>

<details>
<summary>✅ v1.0 KB Navigation & Agentic RAG (Phases 1-7) — SHIPPED 2026-04-23</summary>

See [milestones/v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md)

</details>

## Phase Details

### Phase 16: Web Search Restoration
**Goal**: The agent's `web_search` tool works end-to-end again — users get answers grounded in current web information, with cited sources — and it is verified live on prod.
**Depends on**: v1.2 (shipped) — `web_search` service + tool wiring + config seam already exist (`backend/services/web_search_service.py`, `WEB_SEARCH_TOOL` in `backend/routers/chat.py`, `web_search_*` settings in `backend/config.py`). This is a fix + prod-verify, not a greenfield build. Likely root cause: Tavily's current auth (Bearer header) vs the `api_key`-in-body the code still uses, and/or an unset `web_search_api_key`.
**Requirements**: WSRCH-01, WSRCH-02, WSRCH-03, WSRCH-04
**Success Criteria** (what must be TRUE):
  1. In a chat that needs current information, the agent invokes `web_search` and returns an answer grounded in live web results (the call is visible in the chat's tool card).
  2. The `web_search` tool is offered to the agent only when a search provider key is configured; with no key it is cleanly absent and chat turns still complete normally (fail-closed).
  3. The agent's response cites the source URLs returned by web search.
  4. A web-search provider error (invalid key, timeout, non-200) returns a graceful result to the agent without crashing the turn, and the failure is logged server-side.
  5. Web search is verified working against the production search-provider key on the live prod deployment.
**Plans**: 4 plans (4 waves — sequential: tests → backend → frontend → prod verify)
- [ ] 16-01-PLAN.md — Wave 0 test scaffold: test_web_search.py + test_config.py depth/scrub tests (RED)
- [ ] 16-02-PLAN.md — Backend restore: Bearer-auth transport + web_search_depth + D-01/D-02 prompts + is_error SSE flag + tvly- scrub
- [ ] 16-03-PLAN.md — Frontend failed-state card: ToolEvent 'error' status + red ToolCallCard branch (depends on 16-02 SSE flag)
- [ ] 16-04-PLAN.md — Live prod verify (SC-5): deploy + Fly secret + success/failure smokes (checkpoint, autonomous:false)

### Phase 17: Agent Personas
**Goal**: Users can switch the chat agent's persona per-thread and set a user-level default, choosing between the board-game expert (default) and a general assistant — both retaining full tool access — with the selected persona's system prompt resolved per request with no cross-user/thread bleed.
**Depends on**: Phase 16 (sequential). Reuses the shipped v1.2 model-pin infrastructure: the `user_preferences` per-user default row + `threads`-column per-thread pin pattern (migration `032`), the per-request key/model resolution seam in `chat.py` / `llm_service.stream_chat_completion` (system prompt is assembled there from `settings.system_prompt`), and the model-picker UI (`ModelSelector.tsx` chat picker + `DefaultModelSelector.tsx` settings default). Predefined personas only — no user-editable free-text prompts (deferred to PERS-F1). "General Assistant" is a vanilla persona that still retains full tool access; board-game-expert is the default.
**Requirements**: PERS-01, PERS-02, PERS-03, PERS-04, PERS-05, PERS-06
**Success Criteria** (what must be TRUE):
  1. User can select an agent persona for a thread from a predefined set via a chat-UI picker (mirrors the model picker), and the agent responds in the selected persona.
  2. A "General Assistant" persona behaves like a vanilla model while retaining full tool access; the board-game-expert persona remains the default persona.
  3. User can set a default persona on the settings/account page, and new threads start with that default.
  4. A thread's persona selection persists across sessions and is restored when the user reopens the thread.
  5. The selected persona's system prompt is resolved and applied per chat request with no cross-user or cross-thread bleed under concurrent BYOK turns.
**Plans**: TBD
**UI hint**: yes

## Progress

**Execution Order:**
Phases execute in numeric order: 16 → 17

| Phase | Milestone | Plans Complete | Status | Completed |
| ----- | --------- | -------------- | ------ | --------- |
| 9. Crypto + Key Storage | v1.2 | 3/3 | Complete | 2026-06 |
| 10. OAuth PKCE Connect | v1.2 | 4/4 | Complete | 2026-06 |
| 11. Per-Request Resolution Seam | v1.2 | 6/6 | Complete | 2026-07-11 |
| 12. Model Cache + Catalog | v1.2 | 4/4 | Complete | 2026-06-23 |
| 13. Preferences + Per-Thread Model | v1.2 | 6/6 | Complete | 2026-07 |
| 14. Usage/Cost + Settings UX | v1.2 | 5/5 | Complete | 2026-07 |
| 15. Options UI Capstone + Demo Gating | v1.2 | 10/10 | Complete | 2026-07-09 |
| 999.1 Chat Empty-State UX | v1.2 | 3/3 | Complete | 2026-06 |
| 999.2 Cost Guardrail Burn Script | v1.2 | 2/2 | Complete | 2026-07 |
| 16. Web Search Restoration | v1.3 | 0/4 | Not started | - |
| 17. Agent Personas | v1.3 | 0/TBD | Not started | - |
