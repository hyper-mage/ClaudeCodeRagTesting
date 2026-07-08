# Requirements: Board Game KB RAG — v1.2 User Options & BYOK

**Defined:** 2026-06-18
**Core Value:** Users run LLMs of their choice from their own OpenRouter keys with near-zero-friction onboarding, while a gated owner-key demo fallback preserves the public demo.

## v1.2 Requirements

Requirements for this milestone. Each maps to a roadmap phase (continues numbering from v1.1, which ended at Phase 8).

### Key Management & BYOK (KEY)

- [x] **KEY-01**: User can connect their OpenRouter account via OAuth (PKCE) without manually pasting a key
- [x] **KEY-02**: User's OpenRouter key is stored encrypted at rest, RLS-scoped to the user, and never returned to the frontend
- [x] **KEY-03**: User can see their key connection status (connected vs not connected, masked label only)
- [x] **KEY-04**: User can disconnect and reconnect their OpenRouter key
- [x] **KEY-05**: Selecting a model with no connected key triggers the OAuth connect flow (key-gated)

### Model Selection (MODEL)

- [x] **MODEL-01**: User can browse a searchable list of available OpenRouter models
- [x] **MODEL-02**: Each model is tagged as free or paid
- [x] **MODEL-03**: Popular models are marked (curated) in the picker
- [x] **MODEL-04**: The model list auto-refreshes to pick up newly added models
- [x] **MODEL-05**: User can set a default model
- [x] **MODEL-06**: User can select a model per chat thread, persisted on the thread
- [x] **MODEL-07**: Picker shows context-length and per-Mtok price hints per model
- [x] **MODEL-08**: User can favorite/pin models to the top of the picker

### Usage & Cost (COST)

- [x] **COST-01**: User sees the cost of each message (from OpenRouter `usage.cost`)
- [x] **COST-02**: User sees their OpenRouter account balance (via `GET /api/v1/key`)
- [x] **COST-03**: User is warned when their balance is low
- [x] **COST-04**: User sees a running cost total per chat thread

### Demo Fallback (DEMO)

- [ ] **DEMO-01**: Owner can enable/disable an owner-key demo fallback via a global flag (default OFF)
- [ ] **DEMO-02**: When demo fallback is active for a user, a clear, non-dismissible "demo mode" banner is shown
- [ ] **DEMO-03**: When the user has no key and demo is off, chat refuses with a connect-key prompt (fail-closed)

### Preferences & UI (PREF)

- [x] **PREF-01**: User can access a settings/account page (key status, default model, theme, profile)
- [x] **PREF-02**: User can toggle light/dark theme, persisted per user

### Security Hardening (SEC)

Cross-cutting release blockers — secret custody is the milestone's defining risk.

- [ ] **SEC-01**: User OpenRouter keys never appear in LangSmith traces, Sentry events, logs, or SSE error payloads
- [x] **SEC-02**: The Text-to-SQL tool cannot read the user-keys table (secret column REVOKE'd from the `authenticated` role + RPC table allowlist)
- [ ] **SEC-03**: Owner-key cost exposure is bounded before demo fallback is enabled in prod (SEC-06 cost guardrail / backlog 999.2 verified with a real trip-test + kill switch)
- [ ] **SEC-04**: Concurrent requests from different users never share a key or model (per-request client, no cross-user bleed)

## Future Requirements

Deferred beyond v1.2. Tracked but not in this roadmap.

### Model UX (MODEL-future)

- **MODEL-F1**: "New" badge on recently-added models (beyond the curated popular list)
- **MODEL-F2**: Heavy picker keyboard navigation / drag-reordering

### Team (TEAM)

- **TEAM-01**: Org / shared-key team billing and seat management

## Out of Scope

Explicitly excluded. Anti-features from research documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Manual API key paste | OAuth-only posture; manual paste doubles the failure + security surface |
| Multi-provider native BYOK (OpenAI/Anthropic direct keys) | OpenRouter already aggregates 400+ models behind one key |
| Admin UI for allowlist / demo config | Project rule: no admin UI — env/flag-driven only |
| Real-time balance polling | Fetch balance on demand only; polling wastes quota |
| In-app billing / credit top-up | Handled on OpenRouter's own site |
| Background scheduler for model refresh | Fly.io free-tier suspend kills timers; use lazy TTL cache instead |
| Showing the full key back to the user | Security — only a masked label is ever surfaced |
| Browser / client-only key storage | Backend (FastAPI SSE) must read the key server-side |
| Per-message model switching mid-thread | Thread-level model selection only |

## Traceability

Each requirement maps to exactly one phase. Phases continue numbering from v1.1 (which ended at Phase 8); v1.2 spans Phases 9-15.

| Requirement | Phase | Status |
|-------------|-------|--------|
| KEY-01 | Phase 10 | Complete |
| KEY-02 | Phase 9 | Complete |
| KEY-03 | Phase 10 | Complete |
| KEY-04 | Phase 10 | Complete |
| KEY-05 | Phase 15 | Complete |
| MODEL-01 | Phase 12 | Complete |
| MODEL-02 | Phase 12 | Complete |
| MODEL-03 | Phase 12 | Complete |
| MODEL-04 | Phase 12 | Complete |
| MODEL-05 | Phase 13 | Complete |
| MODEL-06 | Phase 13 | Complete |
| MODEL-07 | Phase 12 | Complete |
| MODEL-08 | Phase 15 | Complete |
| COST-01 | Phase 14 | Complete |
| COST-02 | Phase 14 | Complete |
| COST-03 | Phase 14 | Complete |
| COST-04 | Phase 14 | Complete |
| DEMO-01 | Phase 15 | Pending |
| DEMO-02 | Phase 15 | Pending |
| DEMO-03 | Phase 11 | Pending |
| PREF-01 | Phase 14 | Complete |
| PREF-02 | Phase 13 | Complete |
| SEC-01 | Phase 11 | Pending |
| SEC-02 | Phase 9 | Complete |
| SEC-03 | Phase 15 | Pending |
| SEC-04 | Phase 11 | Pending |

**Coverage:**
- v1.2 requirements: 26 total
- Mapped to phases: 26 ✓
- Unmapped: 0 ✓

**Per-phase distribution:**
- Phase 9 (Crypto + Key Storage): KEY-02, SEC-02 (2)
- Phase 10 (OAuth PKCE Connect): KEY-01, KEY-03, KEY-04 (3)
- Phase 11 (Per-Request Resolution): SEC-04, SEC-01, DEMO-03 (3)
- Phase 12 (Model Cache + Catalog): MODEL-01, MODEL-02, MODEL-03, MODEL-04, MODEL-07 (5)
- Phase 13 (Preferences + Per-Thread Model): MODEL-05, MODEL-06, PREF-02 (3)
- Phase 14 (Usage/Cost + Settings UX): COST-01, COST-02, COST-03, COST-04, PREF-01 (5)
- Phase 15 (Options UI Capstone + Demo Gating): KEY-05, MODEL-08, DEMO-01, DEMO-02, SEC-03 (5)

**Cross-cutting SEC note:** Each SEC requirement is folded into the single phase where it is *enforced* (per the SUMMARY.md / PITFALLS.md pitfall-to-phase mapping), not stranded: SEC-02 (SQL-tool lockdown) ships with the storage migration in Phase 9; SEC-01 (no key in traces/logs/SSE) is enforced at the chat-loop seam in Phase 11 where the LangSmith `wrap_openai` gate lives, with the frontend Sentry `sk-or-` scrub landing alongside the OAuth callback in Phase 10 and the backend scrub alongside the resolution block in Phase 11; SEC-04 (no cross-user key bleed) is enforced by per-request key+model parameters in Phase 11; SEC-03 (owner-key cost bounded before demo) is the hard gate on enabling the demo-fallback flag in Phase 15, depending on backlog 999.2.

---
*Requirements defined: 2026-06-18*
*Last updated: 2026-06-18 after roadmap creation — traceability mapped (26/26 to Phases 9-15)*
