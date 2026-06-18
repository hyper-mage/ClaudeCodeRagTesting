---
gsd_state_version: 1.0
milestone: v1.2
milestone_name: User Options & BYOK
status: executing
stopped_at: Phase 9 context gathered
last_updated: "2026-06-18T23:25:08.516Z"
last_activity: 2026-06-18
progress:
  total_phases: 9
  completed_phases: 0
  total_plans: 3
  completed_plans: 1
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-20 after v1.1 completion)

**Core value:** The agent can intelligently search and reason across a structured board game knowledge base -- finding rules, comparing mechanics, and recommending games -- using the right tool for the job, transparently.
**Current focus:** Phase 09 — crypto-encrypted-key-storage-foundation

## Current Position

Phase: 09 (crypto-encrypted-key-storage-foundation) — EXECUTING
Plan: 2 of 3
Status: Ready to execute
Progress: [███░░░░░░░] 33%
Last activity: 2026-06-18

## Performance Metrics

- Phases planned: 7 (Phases 9-15)
- Phases complete: 0/7
- Plans complete: 0/0 (plan counts TBD per phase)
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

Last session: 2026-06-18T23:24:57.250Z
Stopped at: Phase 9 context gathered
Resume file: None
Next: Plan the first phase with `/gsd:plan-phase 9`.

## Operator Next Steps

- Plan the first phase: `/gsd:plan-phase 9` (Crypto + Encrypted Key Storage Foundation)
- Phase 12 (Model Cache) is parallelizable with 9-11 — can be planned/built alongside the key path
- Before Phase 15: close SEC-03 / backlog 999.2 (cost-guardrail trip-test) — hard dependency for the demo-fallback flag
- Optional: close Nyquist tech debt with `/gsd:validate-phase N` for v1.1 phases 1, 3, 6, 6.1, 7, 8
