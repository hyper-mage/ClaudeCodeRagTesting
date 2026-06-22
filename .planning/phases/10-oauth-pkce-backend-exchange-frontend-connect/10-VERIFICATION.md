---
phase: 10-oauth-pkce-backend-exchange-frontend-connect
verified: 2026-06-22T00:40:00Z
status: passed
score: 4/4 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: none
  note: "Initial verification — no prior VERIFICATION.md existed"
---

# Phase 10: OAuth PKCE — Backend Exchange + Frontend Connect Verification Report

**Phase Goal:** A user can connect their OpenRouter account through a secure OAuth (PKCE) round-trip with no manual key paste, see their connection status, and disconnect/reconnect — with the key landing encrypted server-side and never crossing the wire to the browser.
**Verified:** 2026-06-22T00:40:00Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
| - | ----- | ------ | -------- |
| 1 | Connect → backend `POST /api/keys/openrouter/exchange` does code→key exchange via httpx, encrypts, upserts; key never returned to FE | ✓ VERIFIED | `backend/services/openrouter_service.py:18-38` — `exchange_code` does a real `httpx.post` to `openrouter.ai/api/v1/auth/keys` with S256, returns `resp.json()["key"]`. `backend/routers/keys.py:38-73` — exchange handler calls `encrypt_key(key)` (real import from `crypto_service`, `def encrypt_key` exists at `crypto_service.py:35`), `.upsert` into `user_api_keys` with explicit `connected_at`, and `return {"connected": True}` — the key is never in any response body. 6 keys tests + lockdown GREEN (12 passed). |
| 2 | Forged/mismatched callback rejected — SPA generates+verifies own CSRF `state` alongside Web Crypto `code_verifier` in sessionStorage; hard-refresh exchange still works | ✓ VERIFIED | `frontend/src/lib/pkce.ts:34-45` — `startOpenRouterConnect` generates `verifier=randomString(64)` + `state=randomString(32)` via `crypto.getRandomValues`/`crypto.subtle.digest('SHA-256')`, stores BOTH in `sessionStorage`, redirects with `&state=`. `OAuthCallbackPage.tsx:33-39` reads verifier+state from `sessionStorage` (NOT React state), and `if (!code || !verifier || returnedState !== storedState) throw 'csrf'` before the exchange POST. sessionStorage survives same-tab hard refresh (D-07) and the effect re-runs from sessionStorage, not component state. Human-verified live: forged `?state=WRONG` rejected (step 6), hard-refresh succeeds (step 5). |
| 3 | Accurate key-connection indicator (connected vs not, masked label only) via `GET /api/keys/status`; disconnect via `DELETE /api/keys` then reconnect | ✓ VERIFIED | `keys.py:76-93` — `/status` selects ONLY `key_label, connected_at` (never `encrypted_key`), returns `{connected, masked_label, connected_at}`. `keys.py:96-99` — `DELETE ""` deletes the user's row (204). Reconnect re-runs the exchange `.upsert` (PK=user_id, one key per user, re-stamps `connected_at`). FE: `SettingsPage.tsx` shows masked tail + "Connected since" + Disconnect (ConfirmDialog → `DELETE /api/keys` → `notifyKeyStatusChanged()`). Dot-sync defect (stale persistent dots on in-SPA disconnect) found at human-verify step 7 and fixed in `cf7d749` (`useKeyStatus` window-event broadcast) — confirmed live in code. |
| 4 | Full round-trip on prod Cloudflare Pages origin — `callback_url` from `window.location.origin`, callback served by SPA fallback; frontend Sentry scrubber redacts `sk-or-v1-…` from events, breadcrumbs, callback URL | ✓ VERIFIED | `pkce.ts:40` — `callback = \`${window.location.origin}/settings/openrouter/callback\`` (origin-derived, not hardcoded localhost). `frontend/public/_redirects` = `/* /index.html 200` (SPA fallback serves the callback path → no 404 in prod). `frontend/src/lib/sentry.ts:31-33,58-101` — `OR_KEY = /sk-or-v1-[A-Za-z0-9_-]+/g` scrub applied in `beforeSend` (message, each exception value, `request.url` incl. callback URL) AND `beforeBreadcrumb` (message + stringy data); existing Authorization/`sb-…-auth-token` rules intact. Human-verified 8/8 on `boardgame-rag-prod.pages.dev` 2026-06-22, incl. no `sk-or-v1-…` in console/network/Sentry (step 8). |

**Score:** 4/4 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `backend/services/openrouter_service.py` | `exchange_code` via httpx | ✓ VERIFIED | Real `httpx.post` to OpenRouter token endpoint, S256, propagates `HTTPStatusError`, zero body logging. Wired: imported+called in `keys.py:33,47`. |
| `backend/routers/keys.py` | exchange/status/disconnect | ✓ VERIFIED | All 3 handlers substantive, `Depends(get_user_id)` binds key to JWT sub; exchange leak-guard (generic 502, no `resp.text`/`exc_info`). Wired: registered `main.py:9,69`. |
| `backend/models/schemas.py` | ExchangeRequest + KeyStatusResponse | ✓ VERIFIED | `class ExchangeRequest` (line 65, code+code_verifier body-only) + `class KeyStatusResponse` (line 75) present; imported in `keys.py:31`. |
| `backend/main.py` | keys.router registration | ✓ VERIFIED | `from routers import ..., keys` (line 9) + `app.include_router(keys.router)` (line 69). |
| `supabase/migrations/20240301000028_*.sql` | additive connected_at column | ✓ VERIFIED | `ALTER TABLE user_api_keys ADD COLUMN IF NOT EXISTS connected_at TIMESTAMPTZ` — additive-only, no GRANT/RLS/allowlist edit. Applied dev (10-01) + prod (deploy step). |
| `frontend/src/lib/pkce.ts` | Web Crypto verifier+S256+state | ✓ VERIFIED | `randomString`, `challengeFromVerifier`, `startOpenRouterConnect`; sessionStorage; origin-derived callback. Imported by SettingsPage + OAuthCallbackPage. |
| `frontend/src/lib/sentry.ts` | sk-or scrub | ✓ VERIFIED | Scrub in both `beforeSend` + `beforeBreadcrumb`; existing rules preserved. |
| `frontend/src/hooks/useKeyStatus.ts` | shared status fetch + refresh | ✓ VERIFIED | Session-gated fetch into state, `refresh()`, `notifyKeyStatusChanged()` window-event broadcast (cf7d749). Consumed by SettingsPage, IconSidebar, MobileTopBar. |
| `frontend/src/pages/SettingsPage.tsx` | connect/status/disconnect stub | ✓ VERIFIED | "Connect OpenRouter" CTA → `startOpenRouterConnect`; connected state (masked tail + connected-since); Disconnect via ConfirmDialog → DELETE → broadcast. |
| `frontend/src/pages/OAuthCallbackPage.tsx` | callback state machine | ✓ VERIFIED | One-shot `ranRef`-guarded effect, CSRF check, exchange POST, success toast+redirect / locked generic failure (no error interpolation). |
| `frontend/src/App.tsx` | /settings + callback routes | ✓ VERIFIED | `/settings` (Protected+AuthenticatedLayout) line 49; `/settings/openrouter/callback` (Protected, bare — no layout) line 59. Pages imported lines 8-9. |
| `frontend/src/components/IconSidebar.tsx` | Settings gear + desktop dot | ✓ VERIFIED | Gear in rail (`navigate('/settings')` line 34) + IconNavRow (`handleNavigate('/settings')` line 104); desktop dot beside DemoPill (lines 41-45, role=status, aria-label, green/gray via `useKeyStatus`). |
| `frontend/src/components/MobileTopBar.tsx` | mobile dot | ✓ VERIFIED | Dot left of DemoPill (lines 36-38, role=status, aria-label, green/gray via `useKeyStatus`). |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | -- | --- | ------ | ------- |
| keys.py | openrouter_service.py | `exchange_code` import+call | ✓ WIRED | imported line 33, called line 47 |
| keys.py | crypto_service.py | `encrypt_key` before upsert | ✓ WIRED | imported line 32, called line 64 (`encrypt_key(key)`) |
| main.py | keys.router | `include_router` | ✓ WIRED | line 69 |
| SettingsPage.tsx | openrouter.ai/auth | `startOpenRouterConnect` | ✓ WIRED | imported, called in `handleConnect` |
| OAuthCallbackPage.tsx | /api/keys/openrouter/exchange | `apiFetch` POST | ✓ WIRED | lines 40-43, inside post-CSRF-check branch |
| App.tsx | SettingsPage + OAuthCallbackPage | `<Route>` elements | ✓ WIRED | both routes registered; callback bare (no AuthenticatedLayout) |
| IconSidebar/MobileTopBar | useKeyStatus | hook consumption | ✓ WIRED | both consume `useKeyStatus()` for the dot |
| SettingsPage disconnect | persistent dots | `notifyKeyStatusChanged()` broadcast | ✓ WIRED | cf7d749 — fixes the stale-dot defect found at human-verify step 7 |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| -------- | ------------- | ------ | ------------------ | ------ |
| SettingsPage.tsx | `status` (connected/masked_label/connected_at) | `useKeyStatus` → `apiFetch('/api/keys/status')` → `keys.py` `.select("key_label, connected_at").eq("user_id",...)` real DB query | Yes (real `user_api_keys` select) | ✓ FLOWING |
| IconSidebar / MobileTopBar dot | `status?.connected` | same `useKeyStatus` fetch | Yes | ✓ FLOWING |
| keys.py exchange | `key` → `encrypt_key(key)` → upsert | live `httpx` OpenRouter exchange | Yes (real outbound exchange + encrypt) | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| Keys exchange/status/delete + SQL lockdown tests | `pytest tests/test_keys_exchange.py tests/test_keys_status.py tests/test_keys_delete.py tests/test_sql_keys_lockdown.py -q` | 12 passed | ✓ PASS |
| Full backend regression | `pytest -q` | 156 passed, 2 errors (pre-existing `test_record_manager.py` user_id fixture — documented, orthogonal) | ✓ PASS (no P10 regression) |
| Frontend strict typecheck | `npx tsc -b --noEmit` | exit 0 | ✓ PASS |

### Probe Execution

No conventional `scripts/*/tests/probe-*.sh` probes declared for this phase. The phase's verification contract is the TDD test suite (run above, 12 passed) + the prod human-verify checkpoint (8/8, recorded in 10-04-SUMMARY). N/A.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| ----------- | ----------- | ----------- | ------ | -------- |
| KEY-01 | 10-02, 10-03 | Connect OpenRouter via OAuth PKCE without pasting a key | ✓ SATISFIED | Backend exchange path + FE PKCE round-trip; human-verified connect (steps 1-3) |
| KEY-03 | 10-01, 10-02, 10-03, 10-04 | See connection status (connected vs not, masked label only) | ✓ SATISFIED | `/status` masked-only; SettingsPage masked tail + connected-since; chat-route dot |
| KEY-04 | 10-01, 10-02, 10-03 | Disconnect and reconnect | ✓ SATISFIED | `DELETE /api/keys` + ConfirmDialog; reconnect upserts/re-stamps; dot-sync fix verified |

No orphaned requirements — REQUIREMENTS.md maps exactly KEY-01/KEY-03/KEY-04 to Phase 10, all claimed by plans.

### Non-Regression Checks (Phase 9 SEC-02 lockdown)

| Check | Status | Evidence |
| ----- | ------ | -------- |
| `ALLOWED_SQL_TABLES` still excludes `user_api_keys` | ✓ INTACT | `sql_service.py:17` = `frozenset({"threads","messages","documents","document_chunks"})` — no `user_api_keys` |
| Migrations 025/026/027 unedited | ✓ INTACT | `git log -1` per file → last touched in Phase 9 commits (`ed5126d`, `7e5bd01`, `91425fe`), NOT any Phase 10 commit |
| Migration 028 additive-only | ✓ INTACT | Only `ADD COLUMN IF NOT EXISTS connected_at`; no GRANT/RLS/allowlist change |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| (none) | — | No TBD/FIXME/XXX/TODO/HACK/PLACEHOLDER in any of the 10 Phase 10 files | — | Clean |

No debt markers, no stub returns, no empty handlers, no hardcoded-empty rendered data in the phase's modified files.

### Human Verification Required

None outstanding. The only items that intrinsically required human testing (prod browser OAuth round-trip, no-key-leak inspection in console/network/Sentry) were already executed and recorded as **8/8 PASS** on the prod Cloudflare Pages origin (`boardgame-rag-prod.pages.dev`) on 2026-06-22 — see `10-04-SUMMARY.md` "Task 3 — VERIFIED 8/8". A stale-dot defect surfaced at step 7 was fixed (`cf7d749`) and re-verified live; the fix is present and correct in the current code (`useKeyStatus.notifyKeyStatusChanged` + listener).

### Gaps Summary

No gaps. All 4 ROADMAP success criteria are observably true in the live codebase, all 13 required artifacts exist / are substantive / are wired / have real data flowing, all key links are connected, all 3 requirements (KEY-01/KEY-03/KEY-04) are satisfied, the Phase 9 SEC-02 SQL-tool lockdown is provably un-regressed, and the prod round-trip was human-verified 8/8. The documented out-of-scope items (backend log/SSE scrub + LangSmith gate → Phase 11; per-request key resolution / model picker / settings page → Phases 11-15; pre-existing ChatPage lint + test_record_manager fixture errors) are correctly deferred and orthogonal — none are Phase 10 failures.

---
_Verified: 2026-06-22T00:40:00Z_
_Verifier: Claude (gsd-verifier)_
