# Roadmap — Board Game Knowledge Base RAG

## Milestones

- ✅ **v1.0 KB Navigation & Agentic RAG** — 7 phases (shipped 2026-04-23) — see `milestones/v1.0-ROADMAP.md`
- ✅ **v1.1 Portfolio Deployment** — 9 phases (shipped 2026-05-20) — see `milestones/v1.1-ROADMAP.md`
- 🚧 **v1.2 User Options & BYOK** — Phases 9-15 (in progress)

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

### 🚧 v1.2 User Options & BYOK (Phases 9-15)

**Milestone Goal:** Users run LLMs of their choice from their own OpenRouter keys with near-zero-friction onboarding (OAuth PKCE, no manual key paste), while a gated owner-key demo fallback preserves the public demo. Secret custody is the milestone's defining risk — security findings are release blockers, front-loaded into the storage and chat-loop phases, with demo-fallback enablement deliberately last and gated on the SEC-06 cost guardrail.

- [x] **Phase 9: Crypto + Encrypted Key Storage Foundation** - Fernet encryption, `user_api_keys` table with RLS, SQL-tool lockdown (completed 2026-06-19)
- [ ] **Phase 10: OAuth PKCE — Backend Exchange + Frontend Connect** - Connect/disconnect an OpenRouter account with no manual key paste
- [ ] **Phase 11: Per-Request Key + Model Resolution (chat-loop seam)** - Every chat runs on the right user's key + model, fail-closed, no cross-user bleed
- [ ] **Phase 12: Model Cache + Catalog** - Searchable, auto-refreshing model list with free/paid + popularity + price hints
- [ ] **Phase 13: Preferences + Per-Thread Model** - Default model, per-thread model selection, persisted theme storage
- [ ] **Phase 14: Usage/Cost Display + Settings/Key-State UX** - Per-message cost, balance, low-balance warning, per-thread totals, settings page
- [ ] **Phase 15: Options UI Capstone + Demo-Fallback Gating** - Model picker, favorites, key-gated selection, demo banner, demo-fallback flag (gated on SEC-03)

## Phase Details

### Phase 9: Crypto + Encrypted Key Storage Foundation

**Goal**: A user's OpenRouter key can be safely persisted server-side — encrypted at rest, RLS-scoped, and provably unreachable by the Text-to-SQL tool — before any provisioning or chat path depends on it.
**Depends on**: Phase 8 (v1.1 prod baseline)
**Requirements**: KEY-02, SEC-02
**Success Criteria** (what must be TRUE):

  1. A plaintext key encrypts and decrypts round-trip via `crypto_service` (Fernet) using a dedicated `KEY_ENCRYPTION_SECRET` held only in Fly/`.env`/`.env.prod` secrets — verified across dev and prod.
  2. The `user_api_keys` migration (table + per-user RLS + `key_version` column) applies cleanly to both the dev and prod Supabase projects, storing ciphertext only — a raw DB dump leaks nothing usable.
  3. A prompt-injected `select * from user_api_keys` through the chat's Text-to-SQL tool returns nothing — the secret column is `REVOKE`'d from the `authenticated` role and the RPC enforces a FROM-table allowlist.
  4. A second master key can decrypt and lazily re-encrypt a stored row, proving the rotation path works; the rotation runbook is documented.

**Plans**: 3 plans

Plans:
**Wave 1**

- [x] 09-01-PLAN.md — crypto_service (MultiFernet encrypt/decrypt/rotate) + KEY_ENCRYPTION_SECRET config + round-trip/rotation tests + rotation runbook
- [x] 09-02-PLAN.md — user_api_keys migration (table + RLS + REVOKE) + execute_readonly_query FROM-table allowlist + SEC-02 lockdown unit test

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 09-03-PLAN.md — [BLOCKING] apply migrations 025/026 to dev Supabase + live REVOKE/allowlist probe (dev only per D-03)

### Phase 10: OAuth PKCE — Backend Exchange + Frontend Connect

**Goal**: A user can connect their OpenRouter account through a secure OAuth (PKCE) round-trip with no manual key paste, see their connection status, and disconnect/reconnect — with the key landing encrypted server-side and never crossing the wire to the browser.
**Depends on**: Phase 9 (somewhere safe to store the exchanged key)
**Requirements**: KEY-01, KEY-03, KEY-04
**Success Criteria** (what must be TRUE):

  1. User clicks "Connect OpenRouter", completes the OpenRouter auth screen, and returns connected — the backend (`POST /api/keys/openrouter/exchange`) does the code→key exchange via `httpx`, encrypts the result, and upserts it; the key is never returned to the frontend.
  2. A forged/mismatched callback is rejected — the SPA generates and verifies its own CSRF `state` (OpenRouter omits it) alongside the Web Crypto `code_verifier` in `sessionStorage`, and a hard-refresh exchange still works.
  3. User sees an accurate key-connection indicator (connected vs not connected, masked label only) via `GET /api/keys/status`, and can disconnect (`DELETE /api/keys`) then reconnect.
  4. The full connect round-trip succeeds on the prod Cloudflare Pages origin (not just localhost) — `callback_url` derives from `window.location.origin` and the callback path is served by the SPA fallback; the frontend Sentry scrubber redacts `sk-or-v1-…` from events, breadcrumbs, and the callback URL.

**Plans**: TBD
**UI hint**: yes

Plans:

- [ ] TBD (refined during /gsd:plan-phase 10)

### Phase 11: Per-Request Key + Model Resolution (chat-loop seam)

**Goal**: Every chat turn resolves the correct key and model per request — the user's own key when connected, a gated owner-key fallback only when explicitly enabled, and a clean fail-closed refusal otherwise — with no cross-user key bleed and no secret leaking into observability.
**Depends on**: Phase 9 (decrypt path), Phase 10 (a connected key to resolve)
**Requirements**: SEC-04, SEC-01, DEMO-03
**Success Criteria** (what must be TRUE):

  1. Two concurrent requests from different users with different keys never cross — key + model are explicit per-request parameters threaded `send_message` → `stream_chat_completion` → `get_llm_client`; every `settings.resolved_llm_api_key`/`settings.llm_model` read (including the budget context-length lookup in `chat.py`) is converted to the resolved per-request value.
  2. A keyless user with the demo flag OFF gets a structured `no_api_key` SSE error ("connect your OpenRouter account") and is never silently billed to the owner — resolution is fail-closed (`if user_has_key … elif demo_flag_on and eligible … else refuse`), never `user_key or owner_key`.
  3. No `sk-or-v1-…` value or BYOK prompt appears in LangSmith, Sentry, logs, or SSE error payloads — `wrap_openai` is gated off for per-user-key calls and a `sk-or-` regex scrub runs before any log/SSE-error in the backend.
  4. Model resolves three-tier (`thread.model` → `user_preferences.default_model` → owner default) and OpenRouter 429 vs 402 errors are surfaced distinctly (rate-limit vs payment), not folded into a generic error; the trailing `usage` object is captured on the terminal non-tool-call turn.

**Plans**: TBD

Plans:

- [ ] TBD (refined during /gsd:plan-phase 11)

### Phase 12: Model Cache + Catalog

**Goal**: Users can browse a searchable, current catalog of OpenRouter models with free/paid tags, curated popularity marking, and context-length/price hints — served from a Supabase-backed cache that refreshes lazily and survives Fly suspend.
**Depends on**: Phase 8 (prod baseline) — parallelizable with Phases 9-11; joins the rest only at the picker UI (Phase 15)
**Requirements**: MODEL-01, MODEL-02, MODEL-03, MODEL-04, MODEL-07
**Success Criteria** (what must be TRUE):

  1. `GET /api/models` returns the full OpenRouter catalog from the `model_cache` table, seeded at deploy time and never empty on first request; the frontend reads only via the backend, never OpenRouter directly.
  2. Each model is correctly tagged free vs paid from defensively-parsed string pricing (`pricing.prompt == "0"` and `pricing.completion == "0"`, plus the `:free` id convention) — never `float()`'d blindly — and shows context-length + per-Mtok price hints.
  3. Popular models are marked from a curated config allowlist (there is no OpenRouter popularity field); the picker degrades gracefully (e.g. free-first / alphabetical) when popularity data is absent.
  4. A newly added OpenRouter model appears after the TTL lapses via lazy refresh-if-stale on read (no in-process scheduler — Fly suspend would kill it); the catalog persists across cold starts.

**Plans**: TBD

Plans:

- [ ] TBD (refined during /gsd:plan-phase 12)

### Phase 13: Preferences + Per-Thread Model

**Goal**: A user's default model, per-thread model selection, and theme preference are persisted server-side and resolve correctly into the chat path and UI.
**Depends on**: Phase 11 (model resolution consumes these); soft input to Phase 15
**Requirements**: MODEL-05, MODEL-06, PREF-02
**Success Criteria** (what must be TRUE):

  1. User can set a default model and it persists (`user_preferences.default_model` via `GET`/`PUT /api/preferences`), feeding the three-tier resolution as the middle tier.
  2. User can select a model per chat thread and it persists on the `threads.model` column (`PATCH /api/threads/{id}`), surviving thread switches and reloads.
  3. User can toggle light/dark theme and it persists per user (`user_preferences.theme`), mirrored to `localStorage` for flash-free first paint.
  4. A thread pinned to a model that is later deprecated falls back to the default at send time with a user-visible notice, rather than crashing the thread.

**Plans**: TBD
**UI hint**: yes

Plans:

- [ ] TBD (refined during /gsd:plan-phase 13)

### Phase 14: Usage/Cost Display + Settings/Key-State UX

**Goal**: Users can see what each message and thread cost, view their OpenRouter balance, get warned when balance is low, and reach a settings/account page that always makes their key state and mode unambiguous — with mid-chat key failures recoverable.
**Depends on**: Phase 11 (resolved request path + captured usage), Phase 10 (connected key + balance source)
**Requirements**: COST-01, COST-02, COST-03, COST-04, PREF-01
**Success Criteria** (what must be TRUE):

  1. User sees the cost of each message taken from OpenRouter's inline `usage.cost`, summed across all tool-loop iterations of the turn — displayed as reported, never recomputed client-side.
  2. User sees their OpenRouter account balance via `GET /api/keys/balance` (proxying `GET /api/v1/key`), fetched on demand (settings open / after a turn), tolerating null `limit_remaining` for pay-as-you-go accounts.
  3. User is warned when their balance is low, and sees a running cost total per chat thread.
  4. User can open a settings/account page that always shows current key state ("Demo mode" vs "Your key: connected" vs "No key — connect to chat") with masked label + balance; a mid-chat 401/402/403 surfaces a recoverable action (reconnect / pick demo / add credits) instead of a dead-end.

**Plans**: TBD
**UI hint**: yes

Plans:

- [ ] TBD (refined during /gsd:plan-phase 14)

### Phase 15: Options UI Capstone + Demo-Fallback Gating

**Goal**: The full options surface comes together — searchable model picker with favorites, key-gated selection that launches OAuth inline, and the owner-key demo fallback — with the demo flag enabled in prod ONLY after the SEC-06 cost guardrail is proven.
**Depends on**: Phase 10 (connect flow), Phase 12 (catalog), Phase 13 (prefs + thread model), Phase 14 (settings + key state)
**Requirements**: KEY-05, MODEL-08, DEMO-01, DEMO-02, SEC-03
**Success Criteria** (what must be TRUE):

  1. User browses and picks a model in the shadcn/ui Combobox picker (free/paid badges, curated popularity, price hints) and can favorite/pin models to the top.
  2. Selecting a model with no connected key launches the OAuth connect flow inline (key-gated) and resumes the action on return — no silent no-op.
  3. The owner can enable/disable the owner-key demo fallback via a global flag (default OFF); when active for a user, a clear, non-dismissible "demo mode" banner is shown.
  4. The demo-fallback flag is enabled in prod ONLY after the SEC-06 cost guardrail / backlog 999.2 is verified with a real fire-before-blowout trip-test plus a working kill switch — owner-key cost exposure is bounded before the door opens.

**Plans**: TBD
**UI hint**: yes

Plans:

- [ ] TBD (refined during /gsd:plan-phase 15)

## Backlog

### Phase 999.1: Chat empty-state UX (BACKLOG)

**Goal:** When no threads exist, sending a chat message silently does nothing. Either block the input until "+ New Chat" is clicked OR auto-create an initial thread on first message send. Caught during Phase 3 UAT.
**Requirements:** TBD
**Plans:** 1/1 plans complete

Plans:

- [ ] TBD (promote with /gsd:review-backlog when ready)

### Phase 999.2: Cost guardrail burn script (BACKLOG)

**Goal:** Programmatic test to trip the OpenRouter $0.10 cost guardrail. Mint N parallel chat requests against the paid model (`openai/gpt-4o-mini` ~$0.005/call → ~20 reqs) from a script in `backend/scripts/`. Watch credits page for $0.10 delta + inbox for delivery email. Captured during 06-04 friend-testing reached only $0.0105 (10.5% of trip) before benching. Verifies whether OpenRouter Guardrail trip emits email-on-trip OR just blocks calls — current behavior unknown. **Hard dependency for SEC-03 / Phase 15** — must be closed before enabling the demo-fallback flag in prod.
**Requirements:** SEC-03 (dependency)
**Plans:** 0 plans

Plans:

- [ ] TBD (promote with /gsd:review-backlog when ready)

## Progress

**Execution Order:**
Phases execute in numeric order: 9 → 10 → 11 → 12 → 13 → 14 → 15 (Phase 12 may run in parallel with 9-11; it has no dependency on the key path).

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 9. Crypto + Encrypted Key Storage | v1.2 | 3/3 | Complete   | 2026-06-19 |
| 10. OAuth PKCE Connect | v1.2 | 0/TBD | Not started | - |
| 11. Per-Request Key + Model Resolution | v1.2 | 0/TBD | Not started | - |
| 12. Model Cache + Catalog | v1.2 | 0/TBD | Not started | - |
| 13. Preferences + Per-Thread Model | v1.2 | 0/TBD | Not started | - |
| 14. Usage/Cost + Settings/Key-State UX | v1.2 | 0/TBD | Not started | - |
| 15. Options UI Capstone + Demo Gating | v1.2 | 0/TBD | Not started | - |
