---
gsd_state_version: 1.0
milestone: v1.2
milestone_name: User Options & BYOK
status: executing
stopped_at: Phase 11 executed — 4/4 plans merged; verification human_needed (2 SEC-01 manual gates)
last_updated: "2026-06-23T02:44:50.374Z"
last_activity: 2026-06-22 -- Phase 11 execution started
progress:
  total_phases: 9
  completed_phases: 3
  total_plans: 11
  completed_plans: 11
  percent: 33
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-20 after v1.1 completion)

**Core value:** The agent can intelligently search and reason across a structured board game knowledge base -- finding rules, comparing mechanics, and recommending games -- using the right tool for the job, transparently.
**Current focus:** Phase 11 — per-request-key-model-resolution-chat-loop-seam

## Current Position

Phase: 11 (per-request-key-model-resolution-chat-loop-seam) — EXECUTING
Plan: 1 of 4
Status: Executing Phase 11
Progress: [█████████░] 86%
Last activity: 2026-06-22 -- Phase 11 execution started

## Performance Metrics

- Phases planned: 7 (Phases 9-15)
- Phases complete: 1/7 (Phase 9)
- Plans complete: 6 (Phase 9: 3/3; Phase 10: 3/4 — 10-01 migration 028 ~14 min; 10-02 backend exchange path ~4 min, 3 tasks, 7 files, 12 tests green; 10-03 FE connect core ~5 min, 3 tasks, 5 files, build green + new files lint-clean)
- Requirements mapped: 26/26 ✓

## Accumulated Context

### Roadmap Evolution

- v1.2 roadmap created 2026-06-18: 7 phases (9-15), continuing numbering from v1.1 (which ended at Phase 8 + inserted 6.1). Standard granularity. Phase shape follows the research-recommended dependency-ordered build sequence: crypto/storage → OAuth → per-request resolution (critical-path 9-10-11), model cache parallelizable (12), prefs/thread-model (13), usage-cost/settings (14), options-UI capstone + demo-fallback gating last (15).
- Phase 06.1 inserted after Phase 6 (v1.1): mobile-responsive-chat-layout — always-visible w-64 sidebar ate the mobile viewport; decimal phase kept numbering clean. Verified 2026-05-15.

### Decisions

Full decision log lives in PROJECT.md Key Decisions table. v1.1 decisions folded in at milestone close.

v1.2 roadmap-shaping decisions (to be promoted to PROJECT.md at phase transitions as they harden):

- Security findings treated as release blockers, front-loaded: SQL-tool lockdown + encryption hygiene in Phase 9; LangSmith/Sentry/SSE scrub + fail-closed resolution + cross-user isolation at the Phase 11 chat-loop seam.
- Demo-fallback flag enablement is deliberately LAST (Phase 15) and hard-gated on the SEC-06 cost guardrail (backlog 999.2) being trip-tested with a kill switch — the fail-closed *shape* lands earlier in Phase 11.
- Model-list refresh is lazy TTL refresh-if-stale + deploy seed (NOT an in-process scheduler — Fly free-tier suspend kills timers).
- BYOK is additive-by-reuse: Fernet (already-pinned `cryptography`), `httpx` for all OpenRouter calls, Web Crypto PKCE (no lib); only new frontend dep surface is shadcn/ui Combobox.
- [Phase ?]: Phase 9 BYOK encryption uses MultiFernet from day one (D-02): KEY_ENCRYPTION_SECRET is a comma-separated NEW-KEY-FIRST list; encrypt uses keys[0], decrypt tries all, rotate re-encrypts under keys[0].
- [Phase ?]: crypto_service reads KEY_ENCRYPTION_SECRET at call-time via get_settings() so @lru_cache is test-clearable; secret/plaintext/ciphertext never logged, traced, or returned (D-04, T-09-01).
- [Phase ?]: [Phase 9]: SQL-tool keys-table allowlist reconciled to {threads, messages, documents, document_chunks} (RESEARCH Open Question 1 closed) — matches QUERYABLE_SCHEMA; RESEARCH-era folders dropped.
- [Phase ?]: [Phase 9]: execute_readonly_query allowlist is positive default-deny; CTE self-referencing aliases are NOT tolerated (would otherwise let an attacker alias user_api_keys past the gate). Allowlist helper in sql_service.py is additive-only — the DB RPC remains the enforcing gate.
- [Phase ?]: [Phase 9]: Migrations 025/026 applied LIVE to dev (ntkkmljbariflblldmha) after a 001-024 migration-history repair; SEC-02 lockdown verified live — select * from user_api_keys rejected by the migration-026 allowlist (P0001 non-allowlisted table). Prod deferred to deploy (D-03).
- [Phase ?]: [Phase 9]: Pre-existing execute_readonly_query 42501 (SET LOCAL role inside SECURITY DEFINER, identical in migrations 015 and 026) logged to deferred-items.md D-09-A — out of scope for the verify plan, orthogonal to SEC-02; triage in Phase 11 or a dedicated RPC-fix plan.
- [Phase ?]: [Phase 10]: connected_at added as a dedicated nullable TIMESTAMPTZ column (migration 028); set explicitly in the exchange upsert (ON CONFLICT skips defaults); backs 'Connected since' (KEY-03) + reconnect (KEY-04).
- [Phase ?]: [Phase 10]: Migration 028 applied LIVE to dev (ntkkmljbariflblldmha), additive-only; SEC-02 lockdown verified intact (live P0001 RPC probe + unit test); prod deferred to deploy (D-03).
- [Phase ?]: [Phase 10]: BYOK exchange returns {connected:True} only — the sk-or-v1 key (plaintext OR ciphertext) is NEVER in any response; a 403 from OpenRouter surfaces a generic HTTPException(502) scrubbed of the body/key (T-10-03/T-10-04/SEC-01, Plan 10-02).
- [Phase ?]: [Phase 10]: keys.py exchange sets connected_at EXPLICITLY in the .upsert payload (PK=user_id, one key per user) so reconnect re-stamps; user_id bound to JWT sub; sql_service.py left untouched so the Phase 9 SEC-02 lockdown stays green (Plan 10-02).
- [Phase ?]: [Phase 10]: FE PKCE round-trip stores code_verifier + CSRF state in sessionStorage (NOT localStorage) so a same-tab hard-refresh on the callback is the SUCCESS path (D-07); the callback reads them from sessionStorage (not React state), validates returnedState !== storedState before the bearer'd exchange POST, and renders a LOCKED generic failure sentence that never interpolates the caught error / HTTP status / sk-or- fragment (D-06). Shared startOpenRouterConnect() helper in lib/pkce.ts powers both the Connect CTA and the callback Retry (Plan 10-03).
- [Phase ?]: [Phase 10]: SEC-01 frontend half landed — lib/sentry.ts scrubs /sk-or-v1-[A-Za-z0-9_-]+/g -> [redacted-key] in BOTH beforeSend (message/exception/request.url incl. callback URL) and beforeBreadcrumb (message/data), additive beside the existing Authorization/sb-…-auth-token rules (Plan 10-03).
- [Phase ?]: Plan 10-04 Tasks 1-2 shipped: /settings + callback routes, IconSidebar Settings gear (rail + drawer), display-only connection dot on chat route (MobileTopBar + IconSidebar desktop) via useKeyStatus, no polling. Task 3 prod round-trip is a blocking human-verify checkpoint, pending the real user.

### Pending Todos

- Pre-existing test debt: `backend/tests/test_record_manager.py::test_check_duplicate_integration` references a missing `user_id` fixture (conftest provides only `test_user_id` / `mock_user_id`). Pre-dates v1.1 — fix in a future plan-checker pass.
- shadcn `init` against Vite + Tailwind 4 is a Phase 15 prerequisite — project has not used shadcn before; verify `components.json` does not pre-exist before adding Combobox.

### Blockers/Concerns

- [Phase 15 hard dep]: SEC-03 / backlog 999.2 — OpenRouter cost-cap live trip-test not yet exercised. MUST be closed before enabling the demo-fallback flag in prod.
- [Phase 11 research flag]: LangSmith `wrap_openai` redaction of `api_key` + Sentry/SSE scrub + concurrent-key isolation are the highest-blast-radius work; validate the disable-wrapper approach against the prod LangSmith project during planning.
- [Phase 14 gap]: OpenRouter `/api/v1/key` exact balance field names are MEDIUM confidence — validate live against a real OAuth-provisioned key; tolerate null `limit_remaining` for pay-as-you-go.
- [v1.2+]: Supabase free-tier `pg_cron` availability affects any future scheduled model-refresh upgrade (lazy TTL is the v1.2 baseline; pg_cron is documented-optional).
- [tech debt]: Nyquist test-coverage validation incomplete for several v1.1 phases — run `/gsd:validate-phase N` when convenient.

## Session Continuity

Last session: 2026-06-23T02:44:50.366Z
Stopped at: Phase 11 executed — 4/4 plans merged; verification human_needed (2 SEC-01 manual gates)
Resume file: .planning/phases/11-per-request-key-model-resolution-chat-loop-seam/11-HUMAN-UAT.md
Next: Execute Plan 10-04 (wire routing in App.tsx + IconSidebar gear + chat-header connection dot).

## Operator Next Steps

- Plan the first phase: `/gsd:plan-phase 9` (Crypto + Encrypted Key Storage Foundation)
- Phase 12 (Model Cache) is parallelizable with 9-11 — can be planned/built alongside the key path
- Before Phase 15: close SEC-03 / backlog 999.2 (cost-guardrail trip-test) — hard dependency for the demo-fallback flag
- Optional: close Nyquist tech debt with `/gsd:validate-phase N` for v1.1 phases 1, 3, 6, 6.1, 7, 8
