---
phase: 10-oauth-pkce-backend-exchange-frontend-connect
plan: 02
subsystem: backend
tags: [fastapi, openrouter, oauth, pkce, byok, httpx, crypto, sec-01, sec-02, tdd]

# Dependency graph
requires:
  - phase: 10-oauth-pkce-backend-exchange-frontend-connect
    plan: 01
    provides: "connected_at TIMESTAMPTZ column live on dev user_api_keys (backs the explicit reconnect re-stamp)"
  - phase: 09-crypto-encrypted-key-storage-foundation
    provides: "crypto_service.encrypt_key (MultiFernet) + SEC-02 SQL-tool lockdown (user_api_keys out of ALLOWED_SQL_TABLES)"
provides:
  - "POST /api/keys/openrouter/exchange — code->key exchange, encrypt, service-role upsert; returns {connected:True}, never the key"
  - "GET /api/keys/status — {connected, masked_label, connected_at} (masked-only, no encrypted_key)"
  - "DELETE /api/keys — disconnect (delete row, 204), reconnect upserts (one key per user)"
  - "openrouter_service.exchange_code(code, code_verifier) -> str (httpx POST, HTTPStatusError propagates)"
  - "schemas.ExchangeRequest + KeyStatusResponse Pydantic models"
affects: [10-03 (FE Connect/SettingsPage), 10-04 (FE OAuthCallbackPage consumes exchange), Phase 11 per-request key resolution reads the stored encrypted_key]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Outbound httpx POST that PROPAGATES HTTPStatusError (does NOT swallow into logger.warning+None like budget_service) so the router maps it to a generic 502"
    - "Exchange-error leak guard: catch httpx.HTTPStatusError -> generic HTTPException(502, fixed string); never resp.text / exc_info on the response (SEC-01)"
    - "Explicit connected_at in the upsert payload (datetime.now(timezone.utc).isoformat()) — ON CONFLICT DO UPDATE skips column defaults, so reconnect re-stamps"
    - "Masked tail computed in-memory ('sk-or-v1-…' + key[-4:]) and stored as key_label; the full key never crosses back to the client"

key-files:
  created:
    - backend/services/openrouter_service.py
    - backend/routers/keys.py
    - backend/tests/test_keys_exchange.py
    - backend/tests/test_keys_status.py
    - backend/tests/test_keys_delete.py
  modified:
    - backend/models/schemas.py
    - backend/main.py

key-decisions:
  - "Exchange returns {connected:True} only — the sk-or-v1 key (plaintext OR ciphertext) is NEVER in any response body (T-10-03); asserted via `sk-or-v1 not in resp.text`"
  - "httpx.HTTPStatusError from OpenRouter -> generic HTTPException(502, 'Couldn't complete the OpenRouter connection.') — fixed string, never the response body/key (T-10-04 / Pitfall 1)"
  - "connected_at set EXPLICITLY in the upsert payload (Pitfall 4) so reconnect re-stamps 'connected since'"
  - "Used .upsert (PK=user_id) — one key per user, reconnect overwrites; .insert is never used (asserted)"
  - "sql_service.py left byte-for-byte untouched — user_api_keys stays out of ALLOWED_SQL_TABLES (SEC-02 lockdown stays green)"

patterns-established:
  - "request-body-only secrets: code/code_verifier accepted ONLY via ExchangeRequest JSON body (never query params) — T-10-07"
  - "key bound to auth.uid() server-side: upsert user_id comes from Depends(get_user_id) (JWT sub), never from the request body or the OpenRouter response — T-10-05"

requirements-completed: [KEY-01, KEY-03, KEY-04]

# Metrics
duration: 4min
completed: 2026-06-19
---

# Phase 10 Plan 02: Backend OAuth Exchange Path Summary

**The security-critical BYOK exchange: `POST /api/keys/openrouter/exchange` swaps the OAuth code for an `sk-or-v1-…` key via httpx, encrypts it with the Phase 9 `crypto_service`, and service-role upserts it into `user_api_keys` with an explicit `connected_at` — the key NEVER crosses back to the client (plaintext or ciphertext), and a 403 from OpenRouter surfaces a generic 502 scrubbed of the body; paired with masked-only `GET /status` and a `DELETE` disconnect, all six TDD tests GREEN and the Phase 9 SQL-tool lockdown still green.**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-06-19T20:46Z
- **Completed:** 2026-06-19
- **Tasks:** 3 (all TDD: RED scaffolds -> service+models -> router GREEN)
- **Files:** 5 created, 2 modified

## Accomplishments

- **Task 1 (RED):** Wrote three TestClient scaffolds (`test_keys_exchange.py`, `test_keys_status.py`, `test_keys_delete.py`) mirroring `test_demo_bootstrap.py` verbatim (dependency_overrides[get_user_id] + `patch("routers.keys.*")` + `finally` clear). Six tests collectible; all RED on the missing `routers.keys` import.
- **Task 2 (service + models):** `openrouter_service.exchange_code` — synchronous httpx POST to `https://openrouter.ai/api/v1/auth/keys` with `code_challenge_method:"S256"`, `timeout=15`, `raise_for_status()`, returns `resp.json()["key"]`. Deliberately propagates `HTTPStatusError` (no swallow-into-warning) and logs nothing from the body. Added `ExchangeRequest` + `KeyStatusResponse` to `schemas.py`.
- **Task 3 (GREEN):** `routers/keys.py` with the three handlers (all `Depends(get_user_id)`); exchange catches `httpx.HTTPStatusError` -> generic `HTTPException(502)`, computes the in-memory masked tail, encrypts, upserts with explicit `connected_at`, returns `{connected:True}`; status returns masked-only; delete returns 204. Registered in `main.py`. All six Plan-02 tests + the Phase 9 lockdown GREEN (12 passed).

## Task Commits

1. **Task 1: Wave 0 RED test scaffolds** — `bae9690` (test)
2. **Task 2: exchange_code httpx service + Pydantic models** — `94c3e57` (feat)
3. **Task 3: keys.py router + main.py registration -> GREEN** — `7d98648` (feat)

**Plan metadata** (this SUMMARY + STATE/ROADMAP/REQUIREMENTS) committed separately.

## Files Created/Modified

- `backend/services/openrouter_service.py` (created) — `exchange_code(code, code_verifier) -> str`; httpx POST, `HTTPStatusError` propagates, no body logging.
- `backend/routers/keys.py` (created) — `APIRouter(prefix="/api/keys")` with exchange (POST), status (GET), disconnect (DELETE); exchange leak-guard + explicit `connected_at` upsert; never returns the key.
- `backend/models/schemas.py` (modified) — added `ExchangeRequest` (code, code_verifier) and `KeyStatusResponse` (connected, masked_label, connected_at).
- `backend/main.py` (modified) — `from routers import ..., keys`; `app.include_router(keys.router)`.
- `backend/tests/test_keys_exchange.py` (created) — upsert+hide-key, 403-generic-error, reconnect-upserts.
- `backend/tests/test_keys_status.py` (created) — masked-only status, not-connected.
- `backend/tests/test_keys_delete.py` (created) — disconnect 204.

## Verification Evidence

- **Six Plan-02 tests + Phase 9 lockdown:** `pytest tests/test_keys_exchange.py tests/test_keys_status.py tests/test_keys_delete.py tests/test_sql_keys_lockdown.py -x` -> **12 passed**.
- **Full backend suite:** `pytest -q` -> **156 passed, 2 errors** — the 2 errors are the PRE-EXISTING `user_id` fixture gap in `test_record_manager.py` (documented in STATE.md Pending Todos, pre-dates v1.1, out of scope per the SCOPE BOUNDARY rule). No regression introduced by this plan.
- **Route resolution:** `/api/keys` (DELETE), `/api/keys/openrouter/exchange` (POST), `/api/keys/status` (GET) all resolve in `app.routes`.
- **Leak-guard grep on `keys.py`:** no executable `resp.text` / `exc_info=True` / `.insert(` / `"key":`-in-response — the only `sk-or` literals are the masked-prefix display string (`"sk-or-v1-…" + key[-4:]`) and docstrings.
- **No-leak grep on `openrouter_service.py`:** zero `logger.` invocations (no logger even imported); the body is never logged.
- **SEC-02 untouched:** `git diff --stat backend/services/sql_service.py` is empty — `ALLOWED_SQL_TABLES` unchanged, no GRANT added.
- **TDD gate sequence (git log):** `test(...)` (RED, `bae9690`) -> `feat(...)` (GREEN, `94c3e57`, `7d98648`) — both gates present.

## Decisions Made

- **Exchange returns `{connected:True}` only** — the key (plaintext or ciphertext) is never in any response; the test asserts `sk-or-v1 not in resp.text` (T-10-03 / SEC-01).
- **Generic 502 on OpenRouter error** — `httpx.HTTPStatusError` is caught and re-raised as `HTTPException(502, "Couldn't complete the OpenRouter connection.")`, a fixed string; the response body (which can contain the key) is never echoed and `exc_info` is never set on it (T-10-04 / Pitfall 1).
- **Explicit `connected_at`** — set to `datetime.now(timezone.utc).isoformat()` in the upsert payload because `ON CONFLICT DO UPDATE` skips column defaults, so reconnect re-stamps (Pitfall 4 / KEY-04).
- **`.upsert` not `.insert`** — PK=user_id, one key per user; reconnect overwrites. The test asserts `.insert` is never called.
- **`status` row-None hardened** — guards `if not row or not row.data` (supabase-py `maybe_single` can return a falsy wrapper) -> `{connected:False}`.

## Deviations from Plan

None - plan executed exactly as written.

One minor robustness addition inside Task 3's prescribed handler (not a deviation in scope): the status guard checks `not row or not row.data` rather than `not row.data` alone — defends against a `maybe_single()` wrapper that is itself falsy, with no behavior change for the tested cases. Covered by `test_status_not_connected` (Rule 2 - defensive null check, within the planned file/handler).

## Threat Surface

No new security-relevant surface beyond the plan's `<threat_model>`. All five registered threats are mitigated and verified by tests:

- **T-10-03** (key returned to FE): exchange returns `{connected:True}`; status is masked-only; `encrypted_key` never selected. Verified by `test_exchange_upserts_and_hides_key` (`sk-or-v1 not in resp.text`) + `test_status_returns_masked_only` (`encrypted_key not in resp.text`).
- **T-10-04** (OpenRouter body echoed): generic 502, no `resp.text`/`exc_info`. Verified by `test_exchange_403_generic_error` (`sk-or` / leaky body absent from the error).
- **T-10-05** (key bound to wrong user): `user_id` from `Depends(get_user_id)`, never from body/response.
- **T-10-06** (SQL tool regains read): service-role client only; `sql_service.py` untouched; lockdown test green.
- **T-10-07** (code over querystring): `ExchangeRequest` is a POST JSON body model; no query params.

## Issues Encountered

- The full-suite `pytest -q` reports 2 pre-existing collection errors in `test_record_manager.py` (`fixture 'user_id' not found`). These pre-date v1.1 and are already logged in STATE.md Pending Todos — not touched (out of scope: not caused by this plan's changes).

## User Setup Required

None. No env var or external service config beyond what Phase 9 already established (`KEY_ENCRYPTION_SECRET` for `crypto_service`). The OpenRouter exchange endpoint is called outbound at request time; no key/secret is needed server-side to initiate the exchange (the code/verifier arrive from the FE in Plans 03/04).

## Next Phase Readiness

- The three `/api/keys/*` endpoints are live and tested — Plans 03 (SettingsPage Connect/disconnect) and 04 (OAuthCallbackPage exchange POST) can consume them directly.
- `connected_at` (Plan 01, live on dev) is now written explicitly on every connect/reconnect — the "Connected since {date}" read (KEY-03) has real data once a user connects.
- **Carry-forward for deploy:** migration 028 (Plan 01) must still be applied to PROD before this endpoint runs against the prod project (D-03).
- Phase 11 per-request key resolution will read the stored `encrypted_key` via `decrypt_key` — this plan establishes the only sanctioned write path.

## Self-Check: PASSED

- `backend/services/openrouter_service.py` — FOUND
- `backend/routers/keys.py` — FOUND
- `backend/tests/test_keys_exchange.py` / `test_keys_status.py` / `test_keys_delete.py` — FOUND
- `backend/models/schemas.py` + `backend/main.py` — MODIFIED (keys models + router registration present)
- Commit `bae9690` (test) — FOUND
- Commit `94c3e57` (feat: service+models) — FOUND
- Commit `7d98648` (feat: router+registration) — FOUND
- Six Plan-02 tests + Phase 9 lockdown — VERIFIED (12 passed)
- SEC-02 lockdown intact — VERIFIED (sql_service.py diff empty, lockdown test green)

---
*Phase: 10-oauth-pkce-backend-exchange-frontend-connect*
*Completed: 2026-06-19*
