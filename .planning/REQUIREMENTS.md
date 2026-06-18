# Requirements: Board Game KB RAG — v1.2 User Options & BYOK

**Defined:** 2026-06-18
**Core Value:** Users run LLMs of their choice from their own OpenRouter keys with near-zero-friction onboarding, while a gated owner-key demo fallback preserves the public demo.

## v1.2 Requirements

Requirements for this milestone. Each maps to a roadmap phase (continues numbering from v1.1, which ended at Phase 8).

### Key Management & BYOK (KEY)

- [ ] **KEY-01**: User can connect their OpenRouter account via OAuth (PKCE) without manually pasting a key
- [ ] **KEY-02**: User's OpenRouter key is stored encrypted at rest, RLS-scoped to the user, and never returned to the frontend
- [ ] **KEY-03**: User can see their key connection status (connected vs not connected, masked label only)
- [ ] **KEY-04**: User can disconnect and reconnect their OpenRouter key
- [ ] **KEY-05**: Selecting a model with no connected key triggers the OAuth connect flow (key-gated)

### Model Selection (MODEL)

- [ ] **MODEL-01**: User can browse a searchable list of available OpenRouter models
- [ ] **MODEL-02**: Each model is tagged as free or paid
- [ ] **MODEL-03**: Popular models are marked (curated) in the picker
- [ ] **MODEL-04**: The model list auto-refreshes to pick up newly added models
- [ ] **MODEL-05**: User can set a default model
- [ ] **MODEL-06**: User can select a model per chat thread, persisted on the thread
- [ ] **MODEL-07**: Picker shows context-length and per-Mtok price hints per model
- [ ] **MODEL-08**: User can favorite/pin models to the top of the picker

### Usage & Cost (COST)

- [ ] **COST-01**: User sees the cost of each message (from OpenRouter `usage.cost`)
- [ ] **COST-02**: User sees their OpenRouter account balance (via `GET /api/v1/key`)
- [ ] **COST-03**: User is warned when their balance is low
- [ ] **COST-04**: User sees a running cost total per chat thread

### Demo Fallback (DEMO)

- [ ] **DEMO-01**: Owner can enable/disable an owner-key demo fallback via a global flag (default OFF)
- [ ] **DEMO-02**: When demo fallback is active for a user, a clear, non-dismissible "demo mode" banner is shown
- [ ] **DEMO-03**: When the user has no key and demo is off, chat refuses with a connect-key prompt (fail-closed)

### Preferences & UI (PREF)

- [ ] **PREF-01**: User can access a settings/account page (key status, default model, theme, profile)
- [ ] **PREF-02**: User can toggle light/dark theme, persisted per user

### Security Hardening (SEC)

Cross-cutting release blockers — secret custody is the milestone's defining risk.

- [ ] **SEC-01**: User OpenRouter keys never appear in LangSmith traces, Sentry events, logs, or SSE error payloads
- [ ] **SEC-02**: The Text-to-SQL tool cannot read the user-keys table (secret column REVOKE'd from the `authenticated` role + RPC table allowlist)
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

Populated by the roadmapper during roadmap creation. Each requirement maps to exactly one phase.

| Requirement | Phase | Status |
|-------------|-------|--------|
| KEY-01 | TBD | Pending |
| KEY-02 | TBD | Pending |
| KEY-03 | TBD | Pending |
| KEY-04 | TBD | Pending |
| KEY-05 | TBD | Pending |
| MODEL-01 | TBD | Pending |
| MODEL-02 | TBD | Pending |
| MODEL-03 | TBD | Pending |
| MODEL-04 | TBD | Pending |
| MODEL-05 | TBD | Pending |
| MODEL-06 | TBD | Pending |
| MODEL-07 | TBD | Pending |
| MODEL-08 | TBD | Pending |
| COST-01 | TBD | Pending |
| COST-02 | TBD | Pending |
| COST-03 | TBD | Pending |
| COST-04 | TBD | Pending |
| DEMO-01 | TBD | Pending |
| DEMO-02 | TBD | Pending |
| DEMO-03 | TBD | Pending |
| PREF-01 | TBD | Pending |
| PREF-02 | TBD | Pending |
| SEC-01 | TBD | Pending |
| SEC-02 | TBD | Pending |
| SEC-03 | TBD | Pending |
| SEC-04 | TBD | Pending |

**Coverage:**
- v1.2 requirements: 26 total
- Mapped to phases: 0 (pending roadmap)
- Unmapped: 26 ⚠️ (roadmapper to resolve)

---
*Requirements defined: 2026-06-18*
*Last updated: 2026-06-18 after initial definition*
