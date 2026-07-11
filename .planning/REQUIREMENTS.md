# Requirements: Board Game Knowledge Base RAG

**Defined:** 2026-07-11
**Milestone:** v1.3 Web Search & Agent Personas
**Core Value:** The agent can intelligently search and reason across a structured board game knowledge base — finding rules, comparing mechanics, and recommending games — using the right tool for the job, transparently.

## v1.3 Requirements

Requirements for the v1.3 milestone. Each maps to a roadmap phase.

### Web Search (WSRCH)

- [ ] **WSRCH-01**: User gets answers grounded in current web information via the agent's `web_search` tool (restored end-to-end)
- [ ] **WSRCH-02**: The `web_search` tool is exposed to the agent when a search provider is configured, and is cleanly absent / fail-closed when it is not
- [ ] **WSRCH-03**: The agent cites source URLs from web search results in its response
- [ ] **WSRCH-04**: Web search failures return a graceful error to the agent (no turn crash) and are logged

### Agent Personas (PERS)

- [ ] **PERS-01**: User can select an agent persona for a thread from a predefined set via a chat-UI picker (mirrors the model picker)
- [ ] **PERS-02**: A "General Assistant" persona is available that behaves as a vanilla model while retaining full tool access
- [ ] **PERS-03**: The board-game-expert persona is preserved as the default persona
- [ ] **PERS-04**: User can set their default persona (applied to new threads) on the settings/account page
- [ ] **PERS-05**: A thread's persona selection persists across sessions and is restored on return
- [ ] **PERS-06**: The selected persona's system prompt is resolved and applied per chat request (no cross-user/thread bleed)

## Future Requirements

Deferred to a future milestone. Tracked but not in the current roadmap.

### Web Search (WSRCH)

- **WSRCH-F1**: Multiple/switchable web search providers beyond Tavily (e.g. Brave, SearXNG)
- **WSRCH-F2**: User-facing per-thread toggle to force-enable/disable web search

### Agent Personas (PERS)

- **PERS-F1**: User-editable custom persona prompts (CRUD, storage, injection review)
- **PERS-F2**: Per-persona tool allowlists (restrict which tools a persona may call)

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| User-authored free-text system prompts | Predefined personas chosen for v1.3 — avoids prompt-injection review surface (deferred to PERS-F1) |
| Per-persona tool restrictions | All personas retain full tool access in v1.3 — allowlisting deferred (PERS-F2) |
| Additional web search providers | Tavily restore only for v1.3 — multi-provider deferred (WSRCH-F1) |
| BYOK web-search keys (per-user) | Web search stays an owner-configured server tool — no per-user search keys |
| Model switching | Already shipped in v1.2 (per-thread model pin + default model) — not re-scoped here |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| WSRCH-01 | Phase 16 | Pending |
| WSRCH-02 | Phase 16 | Pending |
| WSRCH-03 | Phase 16 | Pending |
| WSRCH-04 | Phase 16 | Pending |
| PERS-01 | Phase 17 | Pending |
| PERS-02 | Phase 17 | Pending |
| PERS-03 | Phase 17 | Pending |
| PERS-04 | Phase 17 | Pending |
| PERS-05 | Phase 17 | Pending |
| PERS-06 | Phase 17 | Pending |

**Coverage:**
- v1.3 requirements: 10 total
- Mapped to phases: 10
- Unmapped: 0 ✓

---
*Requirements defined: 2026-07-11*
*Last updated: 2026-07-11 after initial definition*
