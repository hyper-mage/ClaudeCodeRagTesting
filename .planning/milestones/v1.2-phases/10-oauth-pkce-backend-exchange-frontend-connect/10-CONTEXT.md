# Phase 10: OAuth PKCE — Backend Exchange + Frontend Connect - Context

**Gathered:** 2026-06-19
**Status:** Ready for planning

<domain>
## Phase Boundary

A user can connect their OpenRouter account through a secure OAuth (PKCE) round-trip with **no manual key paste**, see their connection status, and disconnect/reconnect — with the exchanged key landing **encrypted server-side** and **never crossing the wire to the browser**.

**In scope (KEY-01, KEY-03, KEY-04):**
- Frontend PKCE init (Web Crypto `code_verifier` + S256 `code_challenge` + own CSRF `state`), redirect to OpenRouter `/auth`, callback route, `state` validation.
- Backend `POST /api/keys/openrouter/exchange` — code→key exchange via `httpx`, encrypt (Phase 9 `crypto_service`), upsert into `user_api_keys`; key never returned.
- `GET /api/keys/status` (connected + masked label only) and `DELETE /api/keys` (disconnect).
- Minimal `/settings` stub surface (connect/status/disconnect only) + IconSidebar entry + chat-header connection dot.
- Frontend Sentry `sk-or-v1-…` scrubber (events, breadcrumbs, callback URL) — the frontend half of SEC-01.
- Prod round-trip verification on the Cloudflare Pages origin (callback served by SPA fallback).

**Out of scope (later phases):**
- Per-request key+model resolution / chat-loop seam, demo-fallback, backend `sk-or` scrub, LangSmith gate — **Phase 11** (SEC-01 backend half, SEC-04, DEMO-03).
- Model catalog / picker — **Phase 12 / 15**.
- Full Settings/account page, balance display (`GET /api/keys/balance`), default model, theme — **Phase 13/14**.
- Key-gated model selection that launches OAuth inline — **Phase 15** (KEY-05).

</domain>

<decisions>
## Implementation Decisions

### Connect surface (KEY-01, KEY-03)
- **D-01:** Build a **minimal `/settings` route stub** this phase — connect / status / disconnect ONLY. Phase 14 grows it into the full Settings/account page (default model, theme, balance, profile). Real testable route, no throwaway UI, no scope creep into P14.
- **D-02:** Entry point = a **Settings/gear entry in the existing `IconSidebar`** → opens `/settings`, **PLUS a persistent "key connected / not connected" dot in the chat header** so key state is always visible at a glance. (Deliberately folds the easy, low-risk half of Pitfall 13's "always-visible mode signal" forward into P10; the full Demo-vs-your-key state machine + balance stays in P14.)

### Status indicator (KEY-03 — "masked label only")
- **D-03:** Connected state on `/settings` shows a **masked key tail (last 4 chars, e.g. `sk-or-v1-…wXyZ`) + a connected-since date**. The backend captures the masked hint at exchange time (plaintext is in memory then), stores it as a **small non-secret display label**, and never stores/returns more of the key. Lets a user confirm *which* key without exposing the secret.
- **D-04:** The chat-header indicator is just a **dot** (connected vs not), not the masked label — minimal footprint; the masked detail lives on `/settings`.
- ⚠ **Schema check for researcher/planner:** Phase 9's `user_api_keys` stores ciphertext + `key_version` + timestamps (exact columns were executor's discretion). Confirm whether a **masked-label column** and a **`connected_at`/`connected_since` column** exist; add them in a follow-on migration if absent. The masked label is non-secret (last-4 only) and must NOT be reachable by the Text-to-SQL tool (table already REVOKE'd + excluded from the FROM-allowlist in Phase 9 — no change needed, just don't undo it).

### Callback + return UX (KEY-01)
- **D-05:** Happy path — callback route (`/settings/openrouter/callback`) shows a **"Connecting your OpenRouter account…" spinner** during `state`-validate → `POST exchange`, then **auto-redirects to `/settings` (now Connected) + a success toast**. No extra click.
- **D-06:** Failure path (forged/mismatched CSRF `state`, exchange `403`, or network error) — **inline error on the callback page: "Couldn't connect your OpenRouter account — please try again" + a Retry / Back-to-settings action.** The surfaced failure reason MUST be scrubbed of `sk-or-…` before any log/Sentry/UI render. Recoverable, stays on the route.
- **D-07:** Hard-refresh on the callback page is the **SUCCESS path, not a failure** — `code_verifier` + `state` live in `sessionStorage` (survive same-tab refresh), so a refreshed exchange still works (ROADMAP success criterion #2).

### Disconnect / reconnect (KEY-04)
- **D-08:** Disconnect uses a **confirm dialog** ("Disconnect OpenRouter? You'll need to reconnect to chat with your own key.") → `DELETE /api/keys` → state flips to not-connected + Connect button. Guards an action that stops chat (demo-fallback is OFF by default, so no key = no chat).
- **D-09:** **Reconnect = re-run the Connect flow.** The exchange **upserts** (PK = `user_id`), so a new connect overwrites the prior row. No separate "switch key" affordance — one key per user (Phase 9 anti-feature lock).

### Locked by research / success criteria (do NOT re-litigate)
- **Backend-side exchange.** The SPA posts `{code, code_verifier}` to OUR backend under the Supabase bearer token; the backend calls OpenRouter `/api/v1/auth/keys`. The `sk-or-v1-…` key lands server-side, is encrypted, and is **never returned to the client** (not plaintext, not ciphertext — `/status` returns booleans + masked label only).
- **PKCE S256**, `code_challenge_method=S256` consistent across authorize + exchange.
- **Own CSRF `state`** generated by the SPA (OpenRouter omits it), carried via `callback_url`, validated on return — forged callback rejected (success criterion #2; Pitfall 5).
- **`callback_url` derives from `window.location.origin`** + fixed path (`/settings/openrouter/callback`) — no new FE env var; robust across localhost + Cloudflare Pages prod. Callback path must be served by the **SPA fallback** (Pitfall 6).
- **Exchange via `httpx`** (already used in the backend).
- **No Supabase auth-redirect / CORS change** needed — this is OpenRouter's flow; the exchange POST is same-origin to the API, already in the v1.1 CORS allowlist.

### Claude's Discretion
- Exact endpoint/handler signatures, `openrouter_service.exchange_code` shape, masked-label/`connected_at` column names + migration filename (next free number), `lib/pkce.ts` helper API, route guard (callback public vs protected), spinner/toast component choice, confirm-dialog component — planner/executor decide following existing conventions.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope & requirements
- `.planning/ROADMAP.md` — Phase 10 entry (goal, 4 success criteria, depends-on Phase 9)
- `.planning/REQUIREMENTS.md` — KEY-01, KEY-03, KEY-04 (definitions + traceability); SEC-01 note (frontend Sentry scrub lands in P10)

### Research (milestone-level, milestone-aware)
- `.planning/research/ARCHITECTURE.md` §"OAuth Callback Flow (PKCE)" + §"New API Endpoints & Frontend Routes/Components" + §"Suggested Build Order" steps 2–3 — the FE-callback/BE-exchange split, endpoint table, route/component list
- `.planning/research/PITFALLS.md` — Pitfall 2 (Sentry `sk-or` scrub), Pitfall 5 (PKCE verifier/`state`/CSRF), Pitfall 6 (callback URL mismatch dev/prod + SPA rewrite); Pitfall 13 (key-state UX — only the always-visible dot is in-scope here)
- `.planning/research/SUMMARY.md` — milestone synthesis / build order

### Phase 9 foundation (the storage + crypto this phase builds on)
- `.planning/phases/09-crypto-encrypted-key-storage-foundation/09-CONTEXT.md` — `crypto_service` API, `user_api_keys` table shape, SQL-tool lockdown (don't undo it)
- `crypto_service` (backend, from Phase 9) — `encrypt_key()` / `decrypt_key()` used by the exchange handler
- The Phase 9 `user_api_keys` migration (`supabase/migrations/202403010000XX_*`) — confirm columns; extend for masked label + connected_at if needed

### Code to modify / mirror
- `backend/config.py` — `Settings` + dual-env (`ENV_FILE`); any new OAuth-related config (likely none — `callback_url` is FE-derived)
- `backend/database.py` — service-role `get_supabase()` client (how the backend upserts/reads `user_api_keys`)
- `backend/main.py` — register the new `keys.py` router via `app.include_router(...)` (mirror `demo.router`)
- `backend/routers/demo.py` / `backend/routers/threads.py` — existing router + `Depends(get_user_id)` auth pattern to mirror for `keys.py`
- `frontend/src/App.tsx` — add `/settings` + `/settings/openrouter/callback` routes
- `frontend/src/lib/sentry.ts` — extend the scrubber with `/sk-or-v1-[A-Za-z0-9_-]+/g` in `beforeSend` + `beforeBreadcrumb` (currently only `Authorization` + Supabase JWT)
- `frontend/src/lib/api.ts` — `apiFetch` (auth'd calls to the exchange/status/delete endpoints)
- `frontend/src/components/IconSidebar.tsx` (or equivalent nav) — add Settings/gear entry
- `frontend/src/hooks/useChat.ts` / chat header component — add the connection-status dot

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`crypto_service` (Phase 9)** — `encrypt_key()` / `decrypt_key()`; the exchange handler encrypts the returned key before upsert. Stable, minimal API by design.
- **`user_api_keys` table (Phase 9, dev)** — PK `user_id`, ciphertext + `key_version`, RLS + REVOKE + FROM-allowlist exclusion already in place. This phase upserts into it.
- **`Depends(get_user_id)` + service-role `get_supabase()`** — every new `keys.py` endpoint reuses the existing auth + DB pattern; the exchange runs under the user's JWT so the key binds to `auth.uid()` server-side (Pitfall 5 mitigation).
- **`apiFetch` (`frontend/src/lib/api.ts`)** — sends the Supabase bearer token; reuse for exchange/status/delete calls.
- **v1.1 Sentry scrubber (`frontend/src/lib/sentry.ts`)** — extend, don't rewrite; new `sk-or-` regex rule alongside the existing JWT rule.
- **`httpx`** — already a direct backend dependency (embeddings, web search) → used for the exchange POST.
- **Cloudflare Pages SPA fallback (v1.1)** — already configured; the callback path must be covered by it (Pitfall 6).

### Established Patterns
- New routers registered in `main.py` exactly like `demo.router`; resource-named routers (`keys.py`).
- Backend always touches `user_api_keys` via the **service-role client** (bypasses RLS); the **frontend must never read this table directly**.
- Dual Supabase envs — dev (`.env`) for this phase's iteration; prod (`.env.prod`, Cloudflare Pages origin) verified at the deploy/verification step (mirrors Phase 9 D-03). See [[project_dual_supabase_envs]].
- `callback_url` derives from `window.location.origin` (self-locating) — parallels the env-driven CORS pattern from v1.1 Phases 1 & 6.

### Integration Points
- `keys.py` → `crypto_service` (encrypt at exchange), `keys.py` → `openrouter_service` (NEW; `exchange_code` via `httpx`), `keys.py` → service-role DB (upsert/read/delete `user_api_keys`).
- Frontend `OAuthCallback` route → `POST /api/keys/openrouter/exchange`; `/settings` stub → `GET /api/keys/status` + `DELETE /api/keys`.
- The decrypt path is NOT exercised this phase (no chat resolution yet) — that's the Phase 11 seam. This phase only writes (encrypt + upsert) and reads status booleans/label.

</code_context>

<specifics>
## Specific Ideas

- Masked label = last-4 of the key, rendered as `sk-or-v1-…wXyZ` — captured once at exchange time, stored as a non-secret display column, never reconstructed from ciphertext.
- Chat-header indicator is a **dot** only (color = connected/not); the masked label + connected-since date live on the `/settings` stub.
- Disconnect confirm copy: "Disconnect OpenRouter? You'll need to reconnect to chat with your own key."
- Reconnect is literally re-running Connect (upsert overwrites) — no dedicated switch-key UI.
- **Phase has a UI hint (ROADMAP "UI hint: yes")** — consider `/gsd:ui-phase 10` after planning to produce a UI-SPEC for the `/settings` stub + callback states + header dot.

</specifics>

<deferred>
## Deferred Ideas

- **Always-visible "Demo mode vs Your key (balance $X) vs No key" state machine** + mid-chat 401/402/403 recovery (Pitfall 13 full scope) — Phase 14. P10 only ships the connected/not dot.
- **`GET /api/keys/balance`** (OpenRouter balance proxy) — Phase 14 (COST-02).
- **Key-gated model selection launching OAuth inline + resume-on-return** — Phase 15 (KEY-05).
- **Backend `sk-or` log/SSE scrub + LangSmith `wrap_openai` gate** — Phase 11 (backend half of SEC-01).

None of the above were re-scoped into P10 — discussion stayed within the connect/disconnect/status boundary.

</deferred>

---

*Phase: 10-oauth-pkce-backend-exchange-frontend-connect*
*Context gathered: 2026-06-19*
