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
- [x] **Phase 10: OAuth PKCE — Backend Exchange + Frontend Connect** - Connect/disconnect an OpenRouter account with no manual key paste (completed 2026-06-22)
- [x] **Phase 11: Per-Request Key + Model Resolution (chat-loop seam)** - Every chat runs on the right user's key + model, fail-closed, no cross-user bleed
 (completed 2026-06-23)
- [x] **Phase 12: Model Cache + Catalog** - Searchable, auto-refreshing model list with free/paid + popularity + price hints
 (completed 2026-06-23)
- [x] **Phase 13: Preferences + Per-Thread Model** - Default model, per-thread model selection, persisted theme storage (completed 2026-06-25)
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

**Plans**: 4 plans

Plans:

**Wave 1**

- [x] 11-01-PLAN.md — config (demo_fallback_enabled OFF + demo_fallback_model :free) + scrub_secrets helper + Wave 0 test scaffolds
- [x] 11-02-PLAN.md — [BLOCKING] migration 029 (additive nullable messages.usage) + apply to dev Supabase

**Wave 2** *(blocked on Wave 1)*

- [x] 11-03-PLAN.md — llm_service trace-gate + key/model params + usage drain; thread rerank/subagent/explorer + search_documents→rerank

**Wave 3** *(blocked on Waves 1-2)*

- [x] 11-04-PLAN.md — chat.py _resolve_key_and_model (fail-closed three-branch + three-tier) + budget fifth-read fix + SSE scrub/402/429 + usage persist + demo-mode signal

### Phase 12: Model Cache + Catalog

**Goal**: Users can browse a searchable, current catalog of OpenRouter models with free/paid tags, curated popularity marking, and context-length/price hints — served from a Supabase-backed cache that refreshes lazily and survives Fly suspend.
**Depends on**: Phase 8 (prod baseline) — parallelizable with Phases 9-11; joins the rest only at the picker UI (Phase 15)
**Requirements**: MODEL-01, MODEL-02, MODEL-03, MODEL-04, MODEL-07
**Success Criteria** (what must be TRUE):

  1. `GET /api/models` returns the full OpenRouter catalog from the `model_cache` table, seeded at deploy time and never empty on first request; the frontend reads only via the backend, never OpenRouter directly.
  2. Each model is correctly tagged free vs paid from defensively-parsed string pricing (`pricing.prompt == "0"` and `pricing.completion == "0"`, plus the `:free` id convention) — never `float()`'d blindly — and shows context-length + per-Mtok price hints.
  3. Popular models are marked from a curated config allowlist (there is no OpenRouter popularity field); the picker degrades gracefully (e.g. free-first / alphabetical) when popularity data is absent.
  4. A newly added OpenRouter model appears after the TTL lapses via lazy refresh-if-stale on read (no in-process scheduler — Fly suspend would kill it); the catalog persists across cold starts.

**Plans**: 4 plans

Plans:

**Wave 1**

- [x] 12-01-PLAN.md — config (POPULAR_MODELS + model_cache_ttl_seconds) + model_catalog_service pure functions (defensive free/paid + per-Mtok + popularity + refresh-if-stale) + Wave 0 unit tests + offline fixture
- [x] 12-02-PLAN.md — [BLOCKING] migration 030 (model_cache table + global-read/service-role-write RLS) + apply to dev Supabase

**Wave 2** *(blocked on Wave 1)*

- [x] 12-03-PLAN.md — ModelResponse schema + models.py router (GET /api/models refresh-if-stale + ?free_only) + main.py wiring + idempotent deploy seed + Wave 0 route tests

**Wave 3** *(gap closure — blocked on Waves 1-2)*

- [x] 12-04-PLAN.md — [GAP CR-01] coalesce name→model_id + corrective migration 031 (relax model_cache.name to nullable, RLS-preserved) + empty-catalog guard + honest fail-path warnings + seed try/except + bounded TTL + CR-01/WR-03/WR-05 regression tests (closes VERIFICATION truth #5 / never-empty-by-design)

### Phase 13: Preferences + Per-Thread Model

**Goal**: A user's default model, per-thread model selection, and theme preference are persisted server-side and resolve correctly into the chat path and UI.
**Depends on**: Phase 11 (model resolution consumes these); soft input to Phase 15
**Requirements**: MODEL-05, MODEL-06, PREF-02
**Success Criteria** (what must be TRUE):

  1. User can set a default model and it persists (`user_preferences.default_model` via `GET`/`PUT /api/preferences`), feeding the three-tier resolution as the middle tier.
  2. User can select a model per chat thread and it persists on the `threads.model` column (`PATCH /api/threads/{id}`), surviving thread switches and reloads.
  3. User can toggle light/dark theme and it persists per user (`user_preferences.theme`), mirrored to `localStorage` for flash-free first paint.
  4. A thread pinned to a model that is later deprecated falls back to the default at send time with a user-visible notice, rather than crashing the thread.

**Plans**: 6 plans
**UI hint**: yes

Plans:

**Wave 1**

- [x] 13-01-PLAN.md — combined additive migration (user_preferences + RLS, threads.model, messages.role 'notice') + Pydantic schemas + Wave 0 backend test scaffolds (RED)

**Wave 2** *(blocked on Wave 1)*

- [x] 13-02-PLAN.md — [BLOCKING] apply migration 20240301000032 to dev Supabase + live schema probes

**Wave 3** *(blocked on Waves 1-2)*

- [x] 13-03-PLAN.md — preferences router (GET/PUT /api/preferences upsert) + PATCH /api/threads/{id} set/clear model + main.py wiring
- [x] 13-04-PLAN.md — deprecation fallback in chat.py (notice insert + model override + history filter) — SC#4 / D-06

**Wave 4** *(blocked on Wave 3)*

- [x] 13-05-PLAN.md — frontend primitives: theme bootstrap (FOUC-free) + Tailwind dark variant + core-surface tokens + hand-rolled ModelSelector + ThemeToggle + Wave 0 fe tests

**Wave 5** *(blocked on Wave 4)*

- [x] 13-06-PLAN.md — wire per-thread selector header row + default-model selector + theme toggle + DeprecationNotice + theme reconcile + light-mode core surfaces + human-verify checkpoint

### Phase 14: Usage/Cost Display + Settings/Key-State UX

**Goal**: Users can see what each message and thread cost, view their OpenRouter balance, get warned when balance is low, and reach a settings/account page that always makes their key state and mode unambiguous — with mid-chat key failures recoverable.
**Depends on**: Phase 11 (resolved request path + captured usage), Phase 10 (connected key + balance source)
**Requirements**: COST-01, COST-02, COST-03, COST-04, PREF-01
**Success Criteria** (what must be TRUE):

  1. User sees the cost of each message taken from OpenRouter's inline `usage.cost`, summed across all tool-loop iterations of the turn — displayed as reported, never recomputed client-side.
  2. User sees their OpenRouter account balance via `GET /api/keys/balance` (proxying `GET /api/v1/key`), fetched on demand (settings open / after a turn), tolerating null `limit_remaining` for pay-as-you-go accounts.
  3. User is warned when their balance is low, and sees a running cost total per chat thread.
  4. User can open a settings/account page that always shows current key state ("Demo mode" vs "Your key: connected" vs "No key — connect to chat") with masked label + balance; a mid-chat 401/402/403 surfaces a recoverable action (reconnect / pick demo / add credits) instead of a dead-end.

**Plans**: 5 plans
**UI hint**: yes

Plans:

**Wave 1**

- [x] 14-01-PLAN.md — backend foundation: Wave 0 tests (RED) + MessageResponse.usage read-path fix + BalanceResponse + GET /api/keys/balance + low_balance_threshold_usd config + chat.py `forbidden` 403 branch

**Wave 2** *(blocked on Wave 1)*

- [x] 14-02-PLAN.md — FE hooks contract: useChat (Usage + usage/errorType on Message, done.usage capture, typed-error stamping, no-toast key path) + useKeyStatus (balance fetch + derived isLow + loading/error)

**Wave 3** *(blocked on Wave 2 — three parallel plans, disjoint files)*

- [ ] 14-03-PLAN.md — chat render surfaces: per-message cost caption (MessageBubble) + typed recovery bubble (ErrorMessageBubble) + Σ thread total + usage/type passthrough (ChatContainer)
- [ ] 14-04-PLAN.md — amber low-balance status dot (IconSidebar + MobileTopBar tri-state)
- [ ] 14-05-PLAN.md — settings consolidation: SettingsPage grow to 3 theme-aware sections (tri-state copy + balance/warning lines + relocated Default model + Theme) + ChatPage prefsControls removal

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

**Goal:** Make the first chat message "just work": auto-create a thread on send for any null-thread state (cold start AND after deleting the active thread), and replace the bland text-only empty-state with a welcoming headline + 2–3 tappable board-game example prompts. Frontend-only UX fix; the "block input until + New Chat" alternative was rejected (D-01). Caught during Phase 3 UAT.
**Requirements:** TBD (backlog phase — derived decisions D-01..D-04 from CONTEXT.md + the approved UI-SPEC)
**Plans:** 3/3 plans complete

Plans:

- [x] 999.1-01-PLAN.md — Wave 0 test runner (vitest+RTL+jsdom) + closure-proof sendMessage(threadId) + loadMessages clobber guard
- [x] 999.1-02-PLAN.md — Welcoming empty-state (headline + sub-line + board-game example chips) in ChatContainer
- [x] 999.1-03-PLAN.md — Auto-create-on-send wiring in ChatPage.handleSend (+ create-failure feedback) + live human-verify checkpoint

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
| 10. OAuth PKCE Connect | v1.2 | 4/4 | Complete   | 2026-06-22 |
| 11. Per-Request Key + Model Resolution | v1.2 | 4/4 | Complete   | 2026-06-23 |
| 12. Model Cache + Catalog | v1.2 | 4/4 | Complete    | 2026-06-23 |
| 13. Preferences + Per-Thread Model | v1.2 | 6/6 | Complete   | 2026-06-25 |
| 14. Usage/Cost + Settings/Key-State UX | v1.2 | 2/5 | In Progress|  |
| 15. Options UI Capstone + Demo Gating | v1.2 | 0/TBD | Not started | - |
