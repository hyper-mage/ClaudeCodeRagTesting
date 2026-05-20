---
phase: 04
slug: deploy-backend-to-fly-io
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-04
---

# Phase 04 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | bash assertions + flyctl CLI + curl + docker CLI (no unit-test framework — Phase 4 is deploy ops) |
| **Config file** | none — verification is command-based, not test-suite-based |
| **Quick run command** | `bash backend/scripts/fly_smoke.sh https://boardgame-rag-prod.fly.dev` |
| **Full suite command** | `flyctl status -a boardgame-rag-prod && flyctl secrets list -a boardgame-rag-prod && bash backend/scripts/fly_smoke.sh https://boardgame-rag-prod.fly.dev` |
| **Estimated runtime** | ~60s (health poll up to 60s + SSE chat ~10-20s) |

---

## Sampling Rate

- **After every task commit:** Verify the task's `<automated>` block (file exists / grep / `flyctl ... | grep`).
- **After every plan wave:** Run the full suite command above.
- **Before `/gsd:verify-work`:** `fly_smoke.sh` exits 0 against the live Fly URL; `flyctl secrets list` shows every key from CONTEXT.md D-05; `docker run --rm boardgame-rag-prod env | grep -E 'SUPABASE_SERVICE_ROLE_KEY|OPENROUTER_API_KEY'` returns empty.
- **Max feedback latency:** 90 seconds (deploy + smoke).

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 04-01-01 | 01 | 1 | DEPLOY-07 | artifact | `test -f fly.toml && grep -E 'shared-cpu-1x' fly.toml && grep 'internal_port = 8000' fly.toml && grep 'auto_stop_machines = "suspend"' fly.toml && grep -E '^# *min_machines_running' fly.toml` | ❌ W0 | ⬜ pending |
| 04-01-02 | 01 | 1 | SEC-03 | artifact | `bash backend/scripts/_lib/get_test_jwt.sh > /dev/null && grep 'get_test_jwt' backend/scripts/docker_smoke.sh` | ❌ W0 | ⬜ pending |
| 04-01-03 | 01 | 1 | DEPLOY-04 | artifact | `test -x backend/scripts/fly_smoke.sh && grep '/api/health' backend/scripts/fly_smoke.sh && grep 'text/event-stream' backend/scripts/fly_smoke.sh` | ❌ W0 | ⬜ pending |
| 04-01-04 | 01 | 2 | SEC-03 | runtime | `flyctl secrets list -a boardgame-rag-prod \| grep -E 'SUPABASE_URL\|SUPABASE_SERVICE_ROLE_KEY\|OPENROUTER_API_KEY\|LANGSMITH_API_KEY\|LANGSMITH_PROJECT\|LANGSMITH_TRACING\|TAVILY_API_KEY\|CORS_ALLOWED_ORIGINS' \| wc -l` returns 8 | ❌ W0 | ⬜ pending |
| 04-01-05 | 01 | 2 | DEPLOY-04 | runtime | `flyctl deploy -a boardgame-rag-prod && curl -fsS https://boardgame-rag-prod.fly.dev/api/health` returns 200 | ❌ W0 | ⬜ pending |
| 04-01-06 | 01 | 2 | DEPLOY-04 | runtime | `bash backend/scripts/fly_smoke.sh https://boardgame-rag-prod.fly.dev` exits 0 with ≥3 SSE chunks | ❌ W0 | ⬜ pending |
| 04-01-07 | 01 | 2 | SEC-03 | image-purity | `flyctl image show -a boardgame-rag-prod` then `docker pull <ref> && docker run --rm <ref> env \| grep -vE '^(PATH\|HOME\|HOSTNAME\|LANG\|PYTHON)' \| grep -E 'SUPABASE_SERVICE_ROLE_KEY=\|OPENROUTER_API_KEY='` returns empty | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

*Plan/task IDs are predicted — actual numbering finalized by gsd-planner. Adjust if planner produces a different breakdown.*

---

## Wave 0 Requirements

- [ ] `flyctl` installed locally and authenticated (`flyctl auth whoami` returns the developer's account) — preflight gate before any plan task runs.
- [ ] `.env.prod` exists at repo root with every key from CONTEXT.md D-05 (SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_ANON_KEY, OPENROUTER_API_KEY, LANGSMITH_API_KEY, LANGSMITH_PROJECT, LANGSMITH_TRACING, TAVILY_API_KEY, CORS_ALLOWED_ORIGINS).
- [ ] Prod Supabase project (Phase 3) reachable; prod test user `ragtest1@gmail.com` / `testpass123` exists OR plan task creates one via `supabase.auth.admin.create_user()` (per CONTEXT.md `<specifics>` open item — research flagged Phase 3 UAT log shows prod auth.users was empty).
- [ ] `backend/scripts/_lib/` directory created (per D-14, planner picks exact path).

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Fly app name globally unique | DEPLOY-04 | Cannot pre-check without attempting `flyctl apps create`; CONTEXT.md D-01 names `bgkb-rag-prod` as fallback if `boardgame-rag-prod` is taken | Run `flyctl apps create --name boardgame-rag-prod`. On collision, retry with fallback name and update `fly.toml` `app =` line + smoke-script default URL. |
| SSE first-chunk latency under load | DEPLOY-04 | Requires real-network curl, not a unit test | Smoke script asserts ≥3 chunks within 30s; manual sanity-check that first chunk arrives within ~5s on warm machine, ~30s on cold suspend-resume. |
| Keep-warm toggle works when uncommented | DEPLOY-07 | Toggle is OFF by default per D-12; verifying ON state would burn free-tier hours unnecessarily | Documented in fly.toml comment only. Manual verification deferred until v1.2+ if the toggle is ever needed. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (flyctl, .env.prod, prod test user, _lib/ dir)
- [ ] No watch-mode flags
- [ ] Feedback latency < 90s
- [ ] `nyquist_compliant: true` set in frontmatter (after planner finalizes task IDs and this map updates)

**Approval:** pending
