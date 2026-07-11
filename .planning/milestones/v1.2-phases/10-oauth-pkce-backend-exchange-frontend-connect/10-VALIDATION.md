---
phase: 10
slug: oauth-pkce-backend-exchange-frontend-connect
status: approved
nyquist_compliant: true
wave_0_complete: false
created: 2026-06-19
---

# Phase 10 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Commands sourced from the four PLAN.md `<verify>` blocks + RESEARCH §Validation Architecture.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (backend, existing in `backend/tests/`); frontend has NO test framework — gated by `tsc + vite build` + ESLint |
| **Config file** | none — backend uses bare `pytest`; frontend uses `npm run build` (tsc strict) + `npm run lint` |
| **Quick run command** | `cd backend && venv/Scripts/python -m pytest tests/test_keys_exchange.py tests/test_keys_status.py tests/test_keys_delete.py tests/test_sql_keys_lockdown.py -x` |
| **Full suite command** | `cd backend && venv/Scripts/python -m pytest -q` |
| **Frontend gate** | `cd frontend && npm run build && npm run lint` |
| **Estimated runtime** | backend quick ~15s · backend full ~30s · frontend build+lint ~45s |

---

## Sampling Rate

- **After every backend task commit:** Run the **quick run command** (the four key tests + Phase 9 lockdown).
- **After every frontend task commit:** Run the **frontend gate** (`build && lint`).
- **After every plan wave:** Run the **full suite** (`pytest -q`) to catch any cross-cutting regression (esp. Phase 9 SQL-tool lockdown).
- **Before `/gsd-verify-work`:** Full backend suite green + frontend `build && lint` green.
- **Max feedback latency:** 60 seconds.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 10-01-01 | 01 | 1 | KEY-03 | T-10-04 (lockdown) | Migration 028 additive-only; no SELECT re-grant | source | `grep -c "ADD COLUMN IF NOT EXISTS connected_at" supabase/migrations/20240301000028_add_connected_at_to_user_api_keys.sql` | ✅ | ⬜ pending |
| 10-01-02 | 01 | 1 | KEY-03 / SEC-02 | T-10-03 (SQL exfil) | `user_api_keys` unreachable via Text-to-SQL after migration | unit | `cd backend && venv/Scripts/python -m pytest tests/test_sql_keys_lockdown.py -x` | ✅ | ⬜ pending |
| 10-02-01 | 02 | 2 | KEY-01/03/04 | — | Test stubs collect (Wave 0) | unit (collect) | `cd backend && venv/Scripts/python -m pytest tests/test_keys_exchange.py tests/test_keys_status.py tests/test_keys_delete.py --co -q` | ❌ W0 | ⬜ pending |
| 10-02-02 | 02 | 2 | KEY-01 | T-10-01 (key returned) | `exchange_code` httpx; key encrypted, never returned | import | `cd backend && venv/Scripts/python -c "from services.openrouter_service import exchange_code; from models.schemas import ExchangeRequest, KeyStatusResponse; print('ok')"` | ❌ W0 | ⬜ pending |
| 10-02-03 | 02 | 2 | KEY-01/03/04 | T-10-01/02 | `/status` masked-only; `/exchange` no key echo; `DELETE` + reconnect upsert; lockdown green | unit | `cd backend && venv/Scripts/python -m pytest tests/test_keys_exchange.py tests/test_keys_status.py tests/test_keys_delete.py tests/test_sql_keys_lockdown.py -x` | ❌ W0 | ⬜ pending |
| 10-03-01 | 03 | 3 | KEY-01 / SEC-01 | T-10-02 (Sentry leak) | `lib/pkce.ts` Web Crypto S256; Sentry `sk-or-v1` scrub in beforeSend + beforeBreadcrumb | build | `cd frontend && npm run build` | ✅ | ⬜ pending |
| 10-03-02 | 03 | 3 | KEY-03/04 | T-10-01 | `useKeyStatus` reads masked-only; disconnect ConfirmDialog → DELETE | build+lint | `cd frontend && npm run build && npm run lint` | ✅ | ⬜ pending |
| 10-03-03 | 03 | 3 | KEY-01 | T-10-05 (CSRF) | Callback validates `state` from sessionStorage; generic scrubbed error | build+lint | `cd frontend && npm run build && npm run lint` | ✅ | ⬜ pending |
| 10-04-01 | 04 | 4 | KEY-01/03 | T-10-12 (SPA 404) | `/settings` + callback routes; gear nav | build+lint | `cd frontend && npm run build && npm run lint` | ✅ | ⬜ pending |
| 10-04-02 | 04 | 4 | KEY-03 | — | Always-visible connection dot (mobile + IconSidebar), display-only, no poll | build+lint | `cd frontend && npm run build && npm run lint` | ✅ | ⬜ pending |
| 10-04-03 | 04 | 4 | KEY-01/03 | T-10-13/14 | Prod round-trip; forged-state rejected; no `sk-or-` leak | manual + full suite | `cd backend && venv/Scripts/python -m pytest -q` (+ manual prod steps) | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky · `❌ W0` = file created in Wave 0 (Plan 02 Task 1) before consumption.*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_keys_exchange.py` — stubs for KEY-01 (exchange → encrypt → upsert; key never returned)
- [ ] `backend/tests/test_keys_status.py` — stubs for KEY-03 (`/status` returns `{connected, masked_label, connected_at}`, never a `sk-or-` value)
- [ ] `backend/tests/test_keys_delete.py` — stubs for KEY-04 (DELETE removes row; reconnect upsert re-stamps `connected_at`)
- [ ] No framework install needed — `pytest` already present in `backend/tests/` (mirror `test_demo_bootstrap.py`: `TestClient(app)` + `app.dependency_overrides[get_user_id]` + `patch("routers.keys.…")`)
- [ ] No frontend test framework installed — frontend logic (PKCE derivation, Sentry regex) is thin and covered by `build && lint` + the manual prod round-trip (RESEARCH Q3 decision)

*`backend/tests/test_sql_keys_lockdown.py` already exists from Phase 9 — reused, not created.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Forged/mismatched CSRF `state` rejected | KEY-01 (ROADMAP #2) | Needs a live OAuth callback round-trip | 10-04 Task 3 step 6 — open `<prod>/settings/openrouter/callback?code=x&state=WRONG` → generic inline error + Retry/Back, rejected |
| Hard-refresh on callback = success path | KEY-01 (D-07) | Depends on real sessionStorage survival across full-page redirect | 10-04 Task 3 step 5 — hard-refresh mid-callback → exchange still succeeds |
| Full connect→disconnect→reconnect on prod Cloudflare origin | KEY-01/03/04 (ROADMAP #4) | Requires the deployed prod origin + real OpenRouter auth screen | 10-04 Task 3 steps 1-7 |
| No `sk-or-v1-…` in console / network bodies / Sentry | SEC-01 | Requires live exchange + browser/Sentry inspection | 10-04 Task 3 step 8 |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (the three new `test_keys_*.py` files, created in Plan 02 Task 1 before consumption)
- [x] No watch-mode flags
- [x] Feedback latency < 60s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-06-19
