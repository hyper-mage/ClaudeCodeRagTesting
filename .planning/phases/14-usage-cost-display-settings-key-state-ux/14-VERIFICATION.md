---
phase: 14-usage-cost-display-settings-key-state-ux
verified: 2026-06-30T02:33:27Z
status: verified
human_verified: 2026-06-30  # all 6 UAT items approved by human; 4 follow-ups → 14-HUMAN-UAT.md Gaps
score: 6/6 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: null
  note: "Initial verification — no prior VERIFICATION.md existed"
human_verification:
  - test: "Live OpenRouter balance fetch (COST-02 / SC#2)"
    expected: "With a real OAuth-connected OpenRouter key, opening /settings shows a real balance line — 'Balance: $X' for a capped account or 'Pay-as-you-go — no limit set' for an uncapped one. The automated tests mock httpx.get, so the real proxy against GET /api/v1/key has not been exercised end-to-end."
    why_human: "External-service integration — requires a live OpenRouter account/key; cannot be exercised without real credentials."
  - test: "Amber low-balance indicator (COST-03, surface #1 + #2)"
    expected: "Set LOW_BALANCE_THRESHOLD_USD above a test account's remaining credit, connect that key: both the IconSidebar rail dot and the MobileTopBar dot turn amber (aria-label 'OpenRouter balance low'), and the /settings page shows the amber 'Balance low: $X — add credits' warning line. A null-limit (pay-as-you-go) key shows green / no warning; disconnect shows gray."
    why_human: "Requires a live OpenRouter key with a known balance + config override; visual amber-fill confirmation in light AND dark."
  - test: "Balance freshness after a chat turn (SC#2 'after a turn' trigger)"
    expected: "After a chat turn consumes credit, the always-visible header dot reflects an updated balance. NOTE: balance is currently fetched on hook mount + on the disconnect broadcast only — there is no post-turn re-fetch wired (notifyKeyStatusChanged is fired solely on disconnect). Confirm whether the as-shipped freshness (re-checks on settings open / navigation) is acceptable, or whether a post-turn refresh is desired (CONTEXT D-03 granted executor discretion on refresh-after-turn)."
    why_human: "Real-time/UX freshness judgment; the 'after a turn' example trigger in SC#2 is not explicitly wired and CONTEXT left the mechanism to executor discretion."
  - test: "Mid-chat 401/402/403 typed recovery bubble (PREF-01 / SC#4 / D-09)"
    expected: "A mid-stream OpenRouter 401 renders the in-thread bubble 'Connect your OpenRouter account to keep chatting.' + [Reconnect]; a 402 renders 'Your key is out of credit (402).' + [Add credits ⇗] (opens openrouter.ai/settings/credits in a new tab) + [Reconnect]; a 403 renders 'Your key was rejected (403).' + [Reconnect] alone (Use demo hidden). No error toast fires on these typed paths; a generic stream failure still shows the toast + Retry."
    why_human: "Real-time SSE behavior + visual; reproducing a live mid-stream 401/402/403 requires a revoked/out-of-credit key against the running stack."
  - test: "Cost surfaces + Σ total visual + reload persistence (COST-01 / COST-04)"
    expected: "A paid assistant turn shows a muted '$0.00XX · N tok' caption under the bubble (assistant only, never user); a free turn shows 'N tok' (no $, no ·); the thread header shows 'Σ $X.XXXX' when > 0; reloading the thread reconstructs the same per-message captions and Σ total from persisted usage. Light + dark both coherent."
    why_human: "Visual rendering + reload behavior against a live thread with persisted usage; not programmatically testable without a running app + data."
  - test: "Settings page light/dark coherence + D-06 relocation (PREF-01 / D-06)"
    expected: "/settings reads coherently in BOTH themes (no orphan dark panel in light mode) across all three sections (OpenRouter, Default model, Theme). The ChatPage sidebar/drawer no longer show the default-model/theme cluster and have NO empty footer box; the per-thread model selector still works in the chat header."
    why_human: "Visual theme coherence + layout/relocation confirmation; browser-observable only (no FE test framework per CLAUDE.md)."
---

# Phase 14: Usage/Cost Display + Settings/Key-State UX Verification Report

**Phase Goal:** Users can see what each message and thread cost (per-message cost from OpenRouter inline usage.cost summed across the tool loop; per-thread running total), view their OpenRouter account balance, get warned when balance is low, and reach a settings/account page that always makes their key state and mode unambiguous (Your key: connected / No key — connect to chat) — with mid-chat key failures (401/402/403) recoverable.
**Verified:** 2026-06-30T02:33:27Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| #   | Truth (ROADMAP SC / Requirement) | Status | Evidence |
| --- | --- | --- | --- |
| 1 | **SC#1 / COST-01:** Each message shows cost from OpenRouter `usage.cost`, summed across all tool-loop iterations, displayed as reported (never recomputed client-side) | ✓ VERIFIED | Backend: `_accumulate_usage` sums per-iteration usage (chat.py:106-119, accumulated :921), written to message (`"usage": turn_usage or None` :1173) + carried on `done` (:1188-1189); `MessageResponse.usage` declared so it survives `GET /api/threads/{id}` (schemas.py:92; test_thread_usage_exposed PASS). Frontend: `useChat` captures `parsed.usage ?? m.usage` on done (useChat.ts:256) + maps `m.usage` on reload (:78); `MessageBubble.CostLine` renders `$${usage.cost.toFixed(4)} · {tokens} tok`, assistant-only (MessageBubble.tsx:30-34,104) — display formatting only, no recomputation of cost |
| 2 | **SC#2 / COST-02:** Balance via `GET /api/keys/balance` proxying `GET /api/v1/key`, fetched on demand, tolerating null `limit_remaining` | ✓ VERIFIED | Backend: handler proxies OpenRouter, returns only `{connected, limit_remaining, is_low}`, null `limit_remaining` → `is_low=False`, secret-free (keys.py:101-147; 5/5 test_keys_balance PASS incl. null + scrub). Frontend: `useKeyStatus.refreshBalance` calls `apiFetch('/api/keys/balance')` on mount + broadcast, gated session+connected, no poll/Realtime (useKeyStatus.ts:68-107); `Balance.limit_remaining: number\|null` (:17). Settings-open trigger satisfied. NOTE: "after a turn" auto-refresh not wired (mount + disconnect-broadcast only) — see human-verification #3 |
| 3 | **SC#3a / COST-03:** User is warned when balance is low (non-intrusive: header dot + settings line) | ✓ VERIFIED | Surface #1: tri-state dot `connected && isLow → bg-amber-500` + `aria-label="OpenRouter balance low"` in IconSidebar.tsx:18-27,56 and MobileTopBar.tsx:22-31,51. Surface #2: SettingsPage warning gated on `balance?.is_low`, `AlertTriangle` + `Balance low: $X — add credits` in `amber-700 dark:amber-300` (SettingsPage.tsx:125-130). Both consume server-computed `is_low` only (no FE threshold) |
| 4 | **SC#3b / COST-04:** User sees a running cost total per chat thread, reload-stable | ✓ VERIFIED | `ChatContainer` `threadCost = messages.reduce((s,m)=>s+(m.usage?.cost??0),0)` (ChatContainer.tsx:55); `Σ ${threadCost.toFixed(4)}` in the existing h-12 header row via `ml-auto`, gated `threadCost > 0` (:78-82). Persisted-usage sum = reload-stable source of truth (depends on truth #1 read-path) |
| 5 | **SC#4a / PREF-01:** Settings page always shows unambiguous key state (Your key: connected / No key — connect to chat) + masked label + balance | ✓ VERIFIED | SettingsPage renders `Your key: connected` (green dot + theme-aware label) + masked label + `Connected since …` + 4-state balance line (SettingsPage.tsx:85-120), and `No key — connect to chat` + helper + Connect CTA (:140-155). Wired from `status.connected`. "Demo mode" 3rd state intentionally reserved for P15 (locked D-08 scope note) — correctly NOT built (no `mode === 'demo'` branch); not flagged per scope note |
| 6 | **SC#4b / PREF-01:** Mid-chat 401/402/403 surfaces a recoverable action instead of a dead-end | ✓ VERIFIED | Backend: distinct SSE codes `401→no_api_key`, `402→payment_required`, `403→forbidden`, before the `else→upstream_error`, with RateLimitError(429) caught first (chat.py:1196-1256; test_unauthorized_code_on_401 + test_forbidden_code_on_403 + test_429_402_distinct_codes PASS). Frontend: `useChat` stamps `errorType` + suppresses toast on typed path (useChat.ts:289-323); `ErrorMessageBubble` renders code-mapped locked copy + buttons ([Reconnect]→`startOpenRouterConnect`, [Add credits ⇗]→external anchor), Use-demo gated off (ErrorMessageBubble.tsx:20-127); ChatContainer passes `type={msg.errorType}` (:121) |

**Score:** 6/6 truths verified (at the code level)

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `backend/models/schemas.py` | `MessageResponse.usage` + `BalanceResponse` | ✓ VERIFIED | `usage: dict \| None` (:92); `BalanceResponse{connected, limit_remaining: float\|None, is_low}` (:134-146) |
| `backend/routers/keys.py` | `GET /api/keys/balance` proxy | ✓ VERIFIED | Decrypts in-memory, proxies OpenRouter, returns only derived non-secret fields, fixed-generic 502 on error, no exc_info on balance path (:101-147) |
| `backend/config.py` | `low_balance_threshold_usd` | ✓ VERIFIED | `low_balance_threshold_usd: float = 1.00` (:57), env-overridable |
| `backend/routers/chat.py` | 401/403 SSE branches | ✓ VERIFIED | `elif e.status_code == 401: no_api_key` (:1220), `elif == 403: forbidden` (:1234), before `else` |
| `frontend/src/hooks/useChat.ts` | Usage + usage/errorType + capture + typed stamping | ✓ VERIFIED | Exported `Usage` (:28); `Message.usage`/`errorType` (:43,46); done capture (:256); loadMessages map (:78); typed stamping + toast suppression (:289-323) |
| `frontend/src/hooks/useKeyStatus.ts` | balance fetch + isLow + loading/error | ✓ VERIFIED | `Balance` interface (:15); `refreshBalance` (:68); `isLow = balance?.is_low ?? false` (:112); `balanceLoading`/`balanceError`; no poll/Realtime |
| `frontend/src/components/MessageBubble.tsx` | per-message cost caption | ✓ VERIFIED | `CostLine` muted `text-gray-600 dark:text-gray-400`, assistant-only, null-cost-safe (:29-34,104) |
| `frontend/src/components/ErrorMessageBubble.tsx` | typed recovery variant | ✓ VERIFIED | Locked sentences, code-mapped buttons, light+dark tokens, demo gated, generic path preserved (:20-127) |
| `frontend/src/components/ChatContainer.tsx` | Σ total + passthrough | ✓ VERIFIED | `reduce` sum + `Σ` caption gated >0 ml-auto; `usage`/`type` passthrough (:55,78-82,121,132) |
| `frontend/src/components/IconSidebar.tsx` | tri-state dot | ✓ VERIFIED | `bg-amber-500`/green/gray + aria-labels, mb-2 kept, no animation (:18-27,56) |
| `frontend/src/components/MobileTopBar.tsx` | tri-state dot (no mb-2) | ✓ VERIFIED | Identical logic, inline placement, no mb-2 (:22-31,51) |
| `frontend/src/pages/SettingsPage.tsx` | 3-section theme-aware page | ✓ VERIFIED | Theme-aware surfaces, tri-state copy, 4-state balance, amber warning, Default model + Theme sections (whole file) |
| `frontend/src/pages/ChatPage.tsx` | prefsControls removed | ✓ VERIFIED | grep counts 0 for prefsControls/DefaultModelSelector/ThemeToggle/footer=/defaultModel; models + per-thread wiring retained |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | --- | --- | ------ | ------- |
| `keys.py /balance` | `decrypt_key` + `scrub_secrets` | in-memory decrypt + scrubbed 502 | ✓ WIRED | keys.py:126 decrypt, :136 `scrub_secrets(str(e))`, :137-140 generic 502 |
| `threads.py get_thread` | `MessageResponse.usage` | response_model serialization | ✓ WIRED | test_thread_usage_exposed PASS — usage present in `GET /api/threads/{id}` body |
| `useChat done branch` | `Message.usage` | `parsed.usage ?? m.usage` | ✓ WIRED | useChat.ts:256 |
| `useKeyStatus` | `GET /api/keys/balance` | apiFetch gated session+connected | ✓ WIRED | useKeyStatus.ts:77 |
| `ChatContainer map` | `MessageBubble usage` + `ErrorMessageBubble type` | `usage={msg.usage}`, `type={msg.errorType}` | ✓ WIRED | ChatContainer.tsx:121,132 |
| `ErrorMessageBubble [Reconnect]` | `startOpenRouterConnect()` | lib/pkce import | ✓ WIRED | ErrorMessageBubble.tsx:2,86 |
| `SettingsPage balance line` | `useKeyStatus balance/loading/error` | 4-state render + amber warning | ✓ WIRED | SettingsPage.tsx:26,106-130 |
| `ChatPage` | `ThreadSidebar/ThreadListContent` | footer prop removed entirely | ✓ WIRED | grep `footer=` == 0; no empty wrapper |
| `IconSidebar/MobileTopBar dot` | `useKeyStatus isLow` | connected+isLow → amber | ✓ WIRED | IconSidebar.tsx:11,20; MobileTopBar.tsx:19,24 |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| -------- | ------------- | ------ | ------------------ | ------ |
| `MessageBubble` cost caption | `usage` | `useChat.Message.usage` ← done.usage / loadMessages ← `messages.usage` JSONB (Phase 11 capture) | Yes (live SSE + persisted DB) | ✓ FLOWING |
| `ChatContainer` Σ total | `threadCost` | reduce over `messages[].usage.cost` (persisted) | Yes | ✓ FLOWING |
| `SettingsPage` balance line | `balance` | `useKeyStatus` ← `GET /api/keys/balance` ← OpenRouter `GET /api/v1/key` | Yes (real proxy; mocked in tests — see human verify #1) | ✓ FLOWING (live path needs human confirm) |
| Status dot | `isLow` | `balance?.is_low` (server-computed) | Yes | ✓ FLOWING |
| `ErrorMessageBubble` | `type` | `useChat.Message.errorType` ← SSE error code | Yes | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| Backend: balance + usage read-path + 401/403 codes | `pytest tests/test_keys_balance.py tests/test_thread_usage_exposed.py ::test_unauthorized_code_on_401 ::test_forbidden_code_on_403 ::test_429_402_distinct_codes -q` | `9 passed` | ✓ PASS |
| Frontend: full type contract + build | `cd frontend && npm run build` (tsc -b strict + vite) | exit 0, 2330 modules, build OK (chunk-size warning pre-existing, not an error) | ✓ PASS |
| ChatPage relocation cleanup | grep prefsControls/DefaultModelSelector/ThemeToggle/footer=/defaultModel | all = 0 | ✓ PASS |
| Debt-marker scan (12 modified files) | grep `TBD\|FIXME\|XXX\|PLACEHOLDER\|not yet implemented` | none | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan(s) | Description | Status | Evidence |
| ----------- | -------------- | ----------- | ------ | -------- |
| COST-01 | 01, 02, 03 | Per-message cost from `usage.cost` | ✓ SATISFIED | Truth #1 |
| COST-02 | 01, 02, 05 | OpenRouter balance via `GET /api/v1/key` | ✓ SATISFIED (live path → human verify #1) | Truth #2 |
| COST-03 | 01, 02, 04, 05 | Warned when balance low | ✓ SATISFIED (live amber → human verify #2) | Truth #3 |
| COST-04 | 01, 02, 03 | Running cost total per thread | ✓ SATISFIED | Truth #4 |
| PREF-01 | 01, 02, 03, 05 | Settings/account page + mid-chat recovery | ✓ SATISFIED | Truths #5, #6 |

No orphaned requirements: REQUIREMENTS.md maps exactly {COST-01, COST-02, COST-03, COST-04, PREF-01} to Phase 14; the union of all five plans' `requirements` fields covers all five. No requirement is unclaimed.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| (none) | — | — | — | No debt markers, no stub returns, no hardcoded-empty render data, no orphaned artifacts found in the 12 modified files |

### Human Verification Required

6 items (full detail in frontmatter `human_verification`). Summary:

1. **Live OpenRouter balance fetch (COST-02)** — needs a real connected key; automated tests mock `httpx.get`, so the real `GET /api/v1/key` proxy is unexercised end-to-end.
2. **Amber low-balance indicator (COST-03)** — set `LOW_BALANCE_THRESHOLD_USD` above a test balance; confirm both dots + settings line turn amber in light AND dark.
3. **Balance freshness "after a turn" (SC#2)** — currently fetched on mount + disconnect-broadcast only; confirm the as-shipped freshness is acceptable (CONTEXT D-03 granted executor discretion on refresh-after-turn).
4. **Mid-chat 401/402/403 recovery bubbles (PREF-01/SC#4)** — reproduce live mid-stream auth failures; confirm typed copy + buttons + no toast.
5. **Cost caption + Σ total visual + reload persistence (COST-01/COST-04)** — visual + reload confirmation against a live thread.
6. **Settings light/dark coherence + D-06 relocation (PREF-01)** — theme coherence + no dangling ChatPage footer; per-thread selector still works.

### Gaps Summary

No code-level gaps. All six observable truths are VERIFIED in the codebase: the backend read-path (`MessageResponse.usage`), the secret-safe balance proxy (null-tolerant, server-computed `is_low`), the distinct mid-stream 401/402/403 SSE codes, the FE hook contract (`useChat` usage/errorType, `useKeyStatus` balance/isLow), and every Wave-3 render surface (cost caption, Σ total, tri-state dot, typed recovery bubble, 3-section theme-aware settings page) are present, substantive, wired, and pass the data-flow trace. Backend tests (9/9) and the strict-tsc frontend build (exit 0) confirm the contracts hold.

The "Demo mode" third key-state is intentionally and correctly reserved for Phase 15 (locked decision D-08 scope note; `demo_fallback_enabled` OFF) — verified as NOT-built rather than dead-stubbed, and explicitly not flagged.

Status is **human_needed** (not passed) solely because the phase's user-visible payoff is inherently visual, real-time, and dependent on a live OpenRouter account: the live balance proxy, the amber low-balance behavior, the mid-chat recovery bubbles, and light/dark theme coherence require a human with real credentials to confirm. The single soft observation — balance is not auto-refreshed "after a turn" (only on mount + disconnect-broadcast) — falls within the discretion CONTEXT D-03 granted the executor and does not dead-end the user; it is surfaced for a human freshness judgment rather than treated as a blocker.

---

_Verified: 2026-06-30T02:33:27Z_
_Verifier: Claude (gsd-verifier)_
