---
phase: 13-preferences-per-thread-model
verified: 2026-06-25T11:25:00Z
status: passed
score: 4/4 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: none
  note: "Initial verification — no prior VERIFICATION.md existed."
---

# Phase 13: Preferences + Per-Thread Model Verification Report

**Phase Goal:** A user's default model, per-thread model selection, and theme preference are persisted server-side and resolve correctly into the chat path and UI.
**Verified:** 2026-06-25T11:25:00Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria — the contract)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | User can set a default model and it persists (`user_preferences.default_model` via `GET`/`PUT /api/preferences`), feeding the three-tier resolution as the middle tier | ✓ VERIFIED | `backend/routers/preferences.py` GET (lines 34-55) + PUT partial-upsert keyed on user_id (lines 58-89). Three-tier resolver reads `_safe_user_default_model` as middle tier in `chat.py:175`. FE `DefaultModelSelector.tsx` self-PUTs `{default_model}`; `ChatPage.tsx:78` hydrates from GET. Migration creates `user_preferences.default_model` (nullable). Tests `test_put_then_get_default_model`, `test_get_defaults_for_new_user` pass. |
| 2 | User can select a model per chat thread and it persists on `threads.model` (`PATCH /api/threads/{id}`), surviving thread switches and reloads | ✓ VERIFIED | `backend/routers/threads.py:58-89` — PATCH with ownership re-check (`.eq id + user_id` → 404), explicit `update({"model": body.model})` so null clears. Migration `20240301000032` line 62 adds `threads.model TEXT` nullable. `ThreadResponse.model` exposed (schemas.py:33). FE `ChatContainer.tsx:78` per-thread `ModelSelector` → `onThreadModelChange` → `ChatPage.tsx:102` PATCH. Tests `test_patch_sets_model`, `test_patch_null_clears`, 404 case, `test_thread_model_wins_when_set` pass. |
| 3 | User can toggle light/dark theme and it persists per user (`user_preferences.theme`), mirrored to `localStorage` for flash-free first paint | ✓ VERIFIED | Migration line 25-26: `theme NOT NULL DEFAULT 'dark' CHECK (theme IN ('light','dark'))`. PUT `/api/preferences {theme}` (Pydantic `Literal` 422 backstop). `ThemeToggle.tsx` writes `localStorage.theme` + `applyStoredTheme()` + fire-and-forget PUT. `index.html` inline FOUC script (`matchMedia` + classList.toggle before module). `index.css:10` `@custom-variant dark (&:where(...))` + core-surface tokens. `ChatPage.tsx:80-86` server-wins reconcile. Tests `test_theme_persist_and_validate`, themeBootstrap + ThemeToggle suites pass. Human-verify APPROVED 2026-06-25. |
| 4 | A thread pinned to a deprecated model falls back to default at send time with a user-visible notice, rather than crashing | ✓ VERIFIED | `chat.py:807-852` — reads `thread.model`, cache-non-empty guard (Assumption A2), inserts `role:"notice"` row with locked copy, overrides `model = default_model`, wrapped in try/except (T-13-CRASH, never crashes). History filter `chat.py:747-751` excludes 'notice' from LLM context. FE `DeprecationNotice.tsx` renders escaped text (not a bubble, not red); `ChatContainer.tsx:119-120` 'notice' branch; `useChat.ts:29` role union includes 'notice'. Tests `test_inserts_notice_and_falls_back`, `test_notice_excluded_from_history` pass. |

**Score:** 4/4 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `supabase/migrations/20240301000032_*.sql` | user_preferences + RLS, threads.model, messages role 'notice' | ✓ VERIFIED | All three additive statements present: CREATE TABLE user_preferences w/ PK + theme CHECK, 4 own-row policies (no REVOKE SELECT), ADD COLUMN threads.model, DROP+ADD messages_role_check incl 'notice'. Applied LIVE to dev (`ntkkmljbariflblldmha`) per 13-02-SUMMARY (clean `db push`, transactional). |
| `backend/models/schemas.py` | PreferencesResponse/Update, ThreadModelUpdate, ThreadResponse.model | ✓ VERIFIED | All four present (lines 33, 42, 53, 66). PreferencesUpdate.theme is `Literal['light','dark']`. |
| `backend/routers/preferences.py` | GET + PUT /api/preferences (upsert on user_id) | ✓ VERIFIED | 90 lines, substantive. JWT-bound user_id, exclude_unset partial upsert, maybe_single new-user guard. WIRED into main.py:71. |
| `backend/routers/threads.py` (PATCH) | set/clear per-thread model | ✓ VERIFIED | `update_thread_model` (line 58) — ownership re-check, explicit-null write. |
| `backend/routers/chat.py` (deprecation) | notice insert + override + history filter | ✓ VERIFIED | Lines 747-751 (filter) + 807-852 (deprecation block). Resolver `_resolve_key_and_model` unchanged; override in caller. |
| `frontend/src/components/ModelSelector.tsx` | accessible listbox dropdown over GET /api/models | ✓ VERIFIED | 330 lines. aria-haspopup/expanded, role listbox/option, no shadcn, no dangerouslySetInnerHTML. |
| `frontend/src/components/ThemeToggle.tsx` | class flip + localStorage + fire-and-forget PUT | ✓ VERIFIED | 64 lines. Neutral styling, aria-pressed, LOCKED labels. |
| `frontend/src/components/DeprecationNotice.tsx` | persisted inline system line | ✓ VERIFIED | 34 lines. Escaped text, Info icon, not a bubble, not red. |
| `frontend/src/components/DefaultModelSelector.tsx` | default-model control PUTting preferences | ✓ VERIFIED | 51 lines. Self-PUTs {default_model}, LOCKED heading/helper. |
| `frontend/src/lib/themeBootstrap.ts` | testable applyStoredTheme() | ✓ VERIFIED | 74 lines, exports applyStoredTheme, jsdom-safe. |
| `frontend/src/index.css` | @custom-variant dark + core-surface tokens | ✓ VERIFIED | Line 10 custom-variant w/ :where(); 6 surface tokens under :root + .dark. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| preferences.py | user_preferences | upsert(on_conflict=user_id) + maybe_single | ✓ WIRED | `upsert(patch, on_conflict="user_id")` line 75; maybe_single read lines 42-49, 77-83. |
| threads.py PATCH | threads.model | update({'model': body.model}) scoped by id+user_id | ✓ WIRED | Line 83 explicit update, .eq id + user_id (IDOR defense). |
| chat.py event_generator | model_cache | select model_id → deprecated detection | ✓ WIRED | Lines 820-828 cache read + absent-detection + empty-guard. |
| chat.py history map | stream_chat_completion | filter role in (user, assistant) | ✓ WIRED | Lines 747-751 comprehension excludes 'notice'. |
| ChatContainer per-thread selector | /api/threads/{id} | onSelect → PATCH | ✓ WIRED | ChatContainer:78-80 → ChatPage:102-103 PATCH. |
| DefaultModelSelector | /api/preferences | apiFetch PUT {default_model} | ✓ WIRED | DefaultModelSelector.tsx:36-39. |
| ThemeToggle | /api/preferences | apiFetch PUT {theme} | ✓ WIRED | ThemeToggle.tsx:41-44. |
| index.html inline script | document.documentElement dark class | localStorage read before module | ✓ WIRED | index.html:20 matchMedia + classList.toggle. |
| useChat | DeprecationNotice | role 'notice' mapped + rendered | ✓ WIRED | useChat.ts:29 union; ChatContainer:119-120 render branch. |
| main.py | preferences.router | include_router | ✓ WIRED | main.py:9 import + :71 include_router. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| DefaultModelSelector | `value` (default_model) | ChatPage GET /api/preferences → `defaultModel` state | Yes — live fetch hydrates (ChatPage:78) | ✓ FLOWING |
| ChatContainer per-thread selector | `threadModel` | `activeThread?.model` from threads[] (loaded from API) | Yes — PATCH echo authoritative on reload | ✓ FLOWING |
| ThemeToggle / bootstrap | `theme` class | localStorage + GET /api/preferences reconcile | Yes — server-wins reconcile (ChatPage:80-86) | ✓ FLOWING |
| DeprecationNotice | `content` | message row role='notice' from chat.py insert | Yes — server-composed notice persisted to messages | ✓ FLOWING |
| ModelSelector rows | `models` | GET /api/models (Phase 12 catalog) or lazy fetch on open | Yes — catalog threaded from ChatPage or self-fetch | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Phase 13 backend tests pass | `pytest test_preferences_api test_thread_model_patch test_deprecated_model_fallback test_key_model_resolution -q` | 15 passed | ✓ PASS |
| 8 named Wave-0 cases present | `pytest --collect-only` grep 8 names | 8 found | ✓ PASS |
| Full backend suite (no regression) | `pytest -q` | 203 passed, 2 pre-existing record_manager errors (documented out-of-scope) | ✓ PASS |
| Phase 13 frontend component tests | `vitest run` (5 P13 test files) | 28 passed | ✓ PASS |
| Full frontend suite (no regression) | `vitest run` | 56 passed (9 files) | ✓ PASS |
| TypeScript strict build | `tsc -b` | exit 0 | ✓ PASS |

### Probe Execution

| Probe | Command | Result | Status |
|-------|---------|--------|--------|
| (none) | — | No probe-*.sh declared or conventional for this phase; verification uses pytest/vitest suites + tsc | ? SKIP |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| MODEL-05 | 13-01/03/05/06 | User can set a default model | ✓ SATISFIED | GET/PUT /api/preferences + DefaultModelSelector + resolver middle tier (SC#1). REQUIREMENTS.md marks Complete/Phase 13. |
| MODEL-06 | 13-01/03/04/05/06 | User can select a model per chat thread, persisted on the thread | ✓ SATISFIED | PATCH /api/threads/{id} + threads.model + per-thread header selector + deprecation fallback (SC#2/SC#4). REQUIREMENTS.md Complete/Phase 13. |
| PREF-02 | 13-01/03/05/06 | User can toggle light/dark theme, persisted per user | ✓ SATISFIED | user_preferences.theme + ThemeToggle + FOUC bootstrap + reconcile (SC#3). REQUIREMENTS.md Complete/Phase 13. |

**Orphaned requirements:** None. REQUIREMENTS.md maps exactly MODEL-05, MODEL-06, PREF-02 to Phase 13 — all three claimed in plan frontmatter. PREF-01 (settings page) correctly maps to Phase 14, not in scope here.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| (none) | — | No TBD/FIXME/XXX debt markers in any P13 source file | — | No unauditable debt |
| ModelSelector.tsx / DefaultModelSelector.tsx | various | `placeholder` (React prop) | ℹ️ Info | Legitimate UI prop for trigger label, not a stub/placeholder code marker |

No blocker or warning anti-patterns. DeprecationNotice and ModelSelector contain no `dangerouslySetInnerHTML` (XSS-safe). No empty-return stubs, no console.log-only handlers.

### Deferred / Out-of-Scope Items (informational — not gaps)

| Item | Disposition | Evidence |
|------|-------------|----------|
| Live LLM round-trip on a chosen `:free` model | Deferred D-999.1-LLM-A — out of phase scope | Provider error orthogonal to PATCH/PUT wiring; verification context explicitly instructs not to fail the phase on it. The resolution/PATCH/PUT wiring is verified. |
| `/settings` page (PREF-01) | Phase 14 | REQUIREMENTS.md maps PREF-01 → Phase 14 (Pending). Not a Phase 13 must-have. |
| `test_record_manager.py` integration cases (2 errors) | Pre-existing fixture debt | Documented in deferred-items.md (D-13-03-B) + STATE.md Pending Todos; missing `user_id` fixture pre-dates Phase 13. Not a regression. |
| `react-hooks/set-state-in-effect` lint on ChatPage mount effect | Pre-existing false positive | deferred-items.md D-13-06-A; pre-exists Plan 13-06 (confirmed via git stash); not authored by this phase. |

### Human Verification Required

None outstanding. The Phase 13 human-verify checkpoint (13-06 Task 4 — light-mode visual coherence on four core surfaces, FOUC-free hard reload, live PATCH/PUT wiring) was **APPROVED by the user on 2026-06-25**. Three issues found during verification were fixed inline before approval (dropdown flip-up `a8dcf9b`, light-mode extension `77bcf1a`, silent-empty dropdown `3eed48a`), with +2 regression tests (full FE suite re-confirmed green at 56).

### Gaps Summary

No gaps. All four ROADMAP success criteria are observably achieved in the codebase, not merely claimed in SUMMARY:

- **Backend** — migration is correct and applied LIVE to dev; preferences router (GET/PUT), threads PATCH, and chat.py deprecation fallback are all substantive, wired, and covered by passing tests (203 backend pass; 8 named Wave-0 cases green).
- **Resolution** — the three-tier resolver reads `user_preferences.default_model` as the middle tier (SC#1) and `threads.model` above it (SC#2), with the deprecation override living in the caller and the history filter excluding 'notice' rows (SC#4).
- **Frontend** — ModelSelector, ThemeToggle, DefaultModelSelector, DeprecationNotice, and themeBootstrap exist, are substantive, and are wired into ChatContainer / ChatPage / ThreadSidebar / MobileDrawer / useChat with real data flowing (56 FE tests pass; tsc clean).
- **Visual/FOUC** — the jsdom-unobservable behaviors were human-verified and APPROVED.

The two record_manager errors and the live-`:free`-model round-trip are documented out-of-scope deferrals and do not bear on the Phase 13 goal.

---

_Verified: 2026-06-25T11:25:00Z_
_Verifier: Claude (gsd-verifier)_
