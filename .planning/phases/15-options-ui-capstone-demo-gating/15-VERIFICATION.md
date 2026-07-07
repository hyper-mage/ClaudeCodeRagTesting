---
phase: 15-options-ui-capstone-demo-gating
verified: 2026-07-07T20:08:42Z
status: gaps_found
score: 29/32 must-haves verified
overrides_applied: 0
gaps:
  - truth: "A keyless turn with the flag ON runs the picked model ONLY when model_cache marks it is_free=True; paid, unknown, or cache-error outcomes fall back to the pinned demo_fallback_model (15-02 #1)"
    status: failed
    reason: "CR-01 confirmed in code: the deprecated-pin fallback in send_message (chat.py:871-890) runs AFTER _resolve_key_and_model and overrides the already-free-guarded demo model with _safe_user_default_model(db, user_id) or settings.llm_model — no mode=='demo' check, no free-guard re-application. Exploitability verified beyond the review: PATCH /api/threads/{id} (threads.py:58-89) writes body.model with NO validation against model_cache, and default_model is user-settable via PUT /api/preferences. Any authenticated keyless user can pin a bogus model id + set a paid default, then send — the demo turn mints a PAID completion on the OWNER key. The D-03 structural $0 bound is breached; only the ~$0.10 provider guardrail (999.2) remains. No test covers the deprecated-pin + demo interaction. This defect is LIVE IN PROD (DEMO_FALLBACK_ENABLED=true deployed by 15-08)."
    artifacts:
      - path: "backend/routers/chat.py"
        issue: "Deprecated-pin override (~lines 871-890) replaces the free-guarded demo model unconditionally: `model = default_model` with no mode check"
      - path: "backend/tests/test_key_model_resolution.py"
        issue: "15 tests, zero coverage of deprecated-pin + demo interaction (grep 'deprecat' = 0 matches)"
    missing:
      - "In the deprecated-pin block: when mode == 'demo', re-apply the free-guard — default_model = _demo_model_for(db, default_model, settings) — before `model = default_model`"
      - "Regression test: demo mode + deprecated thread pin + paid user default → model resolves to settings.demo_fallback_model, never the paid default"
      - "Redeploy backend to prod after fix (flag is currently ON against the vulnerable code)"
  - truth: "The open dropdown shows Favorites → Popular → All models sections with non-interactive headers; Favorites hidden when empty; Popular preserves popularity_rank order; All is the complete catalog alphabetical (15-04 #2)"
    status: partial
    reason: "CR-02 confirmed in code (same root cause as next gap): ModelSelector seeds `state` ONCE at mount (line 126: useState(suppliedModels ? 'loaded' : 'idle')); loadModels early-returns when suppliedModels is defined (line 202); NO effect ever flips state to 'loaded' when the models prop arrives after mount; every panel block below the search row is gated on `state` (lines 414/418/428/436). Reachability verified: SettingsPage seeds models=undefined (SettingsPage.tsx:32) and mounts DefaultModelSelector immediately while /api/models is in flight — when the fetch resolves post-mount (the normal timing), state stays 'idle' forever and the open panel shows ONLY the search input: no sections, no options, no loading/error/empty state. Sections/search/star are all fine when the prop is present at mount (chat surface, all tests) — no test covers the late-arrival path."
    artifacts:
      - path: "frontend/src/components/ModelSelector.tsx"
        issue: "state seeded once at mount (line 126); loadModels early-return (line 202); no state transition on late suppliedModels arrival"
      - path: "frontend/src/components/ModelSelector.test.tsx"
        issue: "All tests pass models at mount or omit it entirely; no rerender-with-late-catalog test"
    missing:
      - "Derive effective state at render (e.g. `const effectiveState = suppliedModels ? 'loaded' : state`) or add an effect setting state='loaded' when suppliedModels becomes defined"
      - "Test: render with models=undefined, rerender with a non-empty catalog, open, assert option rows render"
  - truth: "Connected user picks any model: applies immediately, no modal, on both surfaces (15-05 #1)"
    status: partial
    reason: "Same root cause as the previous gap (CR-02). The gate logic itself is fully verified (useKeyGate decision table, tests green) and the chat surface works, but on the Settings surface the picker panel renders permanently empty under the common fetch timing — the user cannot pick ANY model there, so the truth fails on one of the two surfaces. This also degrades MODEL-08 (starring) and MODEL-01 (search) on the settings surface."
    artifacts:
      - path: "frontend/src/components/ModelSelector.tsx"
        issue: "Same late-prop state bug as above; DefaultModelSelector/SettingsPage wiring is correct"
    missing:
      - "Fixed by the same ModelSelector change as the previous gap — one fix closes both truths"
human_verification:
  - test: "After CR-01 fix + redeploy: keyless account, PATCH a thread to a bogus model id, set a paid default_model, send a message — confirm the turn runs the pinned free demo model (check logs: model == demo_fallback_model)"
    expected: "Demo turn never runs the paid default; notice line shows the free fallback"
    why_human: "Requires a live authenticated session against a running backend with the flag ON"
  - test: "After CR-02 fix: open Settings fresh (hard reload), immediately-to-eventually open the Default model picker"
    expected: "Catalog sections render (Favorites/Popular/All); search filters; stars toggle"
    why_human: "Timing-dependent render path; the automated tests mock the fetch timing"
  - test: "Re-smoke keyless free-model streaming in prod when the free provider recovers (429 at 15-08 smoke was environmental — Venice endpoint rate-limited)"
    expected: "Keyless turn streams on the picked free model with the demo banner visible"
    why_human: "Live provider availability; pre-authorized approved-with-caveat per D-999.1-LLM-A precedent"
---

# Phase 15: Options UI Capstone + Demo Gating — Verification Report

**Phase Goal:** Close out v1.2: key-gated model selection (picking a model with no key triggers OAuth connect), favorite/pin models, demo-fallback flag decision + non-dismissible demo banner (gated on the 999.2 SEC-03 PASS finding), and the picker polish the audit flagged — render popular marking (B-1/MODEL-03) and add catalog search (W-1/MODEL-01).
**Verified:** 2026-07-07T20:08:42Z
**Status:** gaps_found
**Re-verification:** No — initial verification

## Goal Achievement

Must-haves merged from the 8 plan frontmatters (ROADMAP has no success_criteria array; the goal text is the contract). 32 truths total.

### Observable Truths

| #  | Truth (plan) | Status | Evidence |
|----|--------------|--------|----------|
| 1  | GET /api/keys/status returns demo_enabled in BOTH branches (15-01) | ✓ VERIFIED | keys.py:91 computes once; :101 keyless return, :106 connected return; test_keys_status.py green |
| 2  | Preferences favorite_models roundtrip, no clobber (15-01) | ✓ VERIFIED | preferences.py:48,54,59,84,90,95 (all 4+ touch points); bidirectional no-clobber tests in 28-test green run |
| 3  | MessageCreate accepts optional use_demo (15-01) | ✓ VERIFIED | schemas.py:88 `use_demo: bool = False` |
| 4  | favorite_models column live in dev DB (15-01) | ✓ VERIFIED | Live probe executed this verification: select succeeded, printed "column live" |
| 5  | Keyless flag-ON turn runs picked model only when is_free=True; else pinned fallback (15-02) | ✗ FAILED | CR-01: resolver free-guard holds (chat.py:152-176, 237-247) but the deprecated-pin block (chat.py:871-890) overrides the demo model with an unguarded, user-influenceable default. Thread PATCH accepts arbitrary model ids (threads.py:81-87, no cache validation) |
| 6  | use_demo short-circuits BEFORE user-key branch only when flag ON (15-02) | ✓ VERIFIED | chat.py:212 single condition `getattr(body, "use_demo", False) and settings.demo_fallback_enabled`, positioned before the user_api_keys read; inert-when-OFF tests green |
| 7  | SEC-03 killswitch trio pass unmodified (15-02) | ✓ VERIFIED | test_sec03_killswitch_no_owner_spend_when_flag_off, test_no_key_flag_off_refuses, test_fail_closed_no_or_fallback present and passing (28/28) |
| 8  | Stash removed FIRST, apply, combined toast, allowlisted navigate (15-03) | ✓ VERIFIED | OAuthCallbackPage.tsx:79 removeItem before apply (:92-105); locked toasts :98,:104; allowlist :22,:111-114 |
| 9  | Apply failure → warning toast + still navigates, never failure screen (15-03) | ✓ VERIFIED | catch around apply only (:106-110), navigate follows (:114) |
| 10 | No/unparseable stash → legacy byte-identical (15-03) | ✓ VERIFIED | :119-121 legacy toast + /settings; parsePendingSelection returns null on bad JSON (:24-32) |
| 11 | Back-to-settings clears stash; Retry preserves (15-03) | ✓ VERIFIED | :160 removeItem in Back handler; Retry (:150) calls startOpenRouterConnect only |
| 12 | Fuzzy search filters typo-tolerantly with locked ranking + no-match copy (15-04) | ✓ VERIFIED | fuzzy.ts exports fuzzyScore/matchModel; ModelSelector :181-187 score-desc flat list; noMatch copy :430; fuzzy.test.ts + ModelSelector.test.tsx green |
| 13 | Dropdown shows Favorites → Popular → All sections per spec (15-04) | ✗ FAILED (partial) | CR-02: sections implemented (:188-198) and correct when catalog present at mount, but permanently empty panel when models prop arrives post-mount — the ALWAYS timing on SettingsPage (models seeded undefined, SettingsPage.tsx:32) |
| 14 | Popular chip on every popularity_rank row in EVERY section instance (15-04, B-1/MODEL-03) | ✓ VERIFIED | ModelHint :544-548 renders the chip section-agnostically, Free-tag class mirror |
| 15 | Combobox focus/keyboard a11y contract (15-04, W-1/MODEL-01) | ✓ VERIFIED | Input focus on open (:300-302), aria-activedescendant (:409), header-skipping nav (:342-361), Esc-to-trigger, Tab trap; 95 FE tests green |
| 16 | Connected pick applies immediately, no modal, both surfaces (15-05) | ✗ FAILED (partial) | Gate pass-through verified (useKeyGate.tsx:76-78) and chat surface works; settings surface inoperable under CR-02 (cannot pick from an empty panel) |
| 17 | Keyless decision table: demo-ON free fast-path / paid gates / demo-OFF gates all (15-05) | ✓ VERIFIED | useKeyGate.tsx:80-92 exact locked table incl. unknown≠free; useKeyGate.test.tsx green |
| 18 | [Connect] writes stash then launches PKCE; [Cancel] leaves selection unchanged (15-05) | ✓ VERIFIED | :100-109 setItem before startOpenRouterConnect; onCancel only clears pending (:121) |
| 19 | Keyless settings pick fires no optimistic onChange/PUT (15-05) | ✓ VERIFIED | DefaultModelSelector.tsx:34-48 — PUT/onChange live only inside gate onApply |
| 20 | Non-gate connect launchers clear stale stash (15-05) | ✓ VERIFIED | SettingsPage.tsx:62, ErrorMessageBubble.tsx:123 |
| 21 | Star on every catalog row, toggles without select/close (15-06) | ✓ VERIFIED | ModelSelector :488-515 — stopPropagation, extraOption excluded (`model &&` guard) |
| 22 | Shift+Enter toggles favorite; Enter selects (15-06) | ✓ VERIFIED | :350-361 shiftKey branch before select |
| 23 | Optimistic whole-array PUT, silent, no revert (15-06) | ✓ VERIFIED | :315-322 — body is exactly {favorite_models: next} |
| 24 | Star → Favorites section same session; persists via mount GET (15-06) | ✓ VERIFIED | favorites state → section intersection (:189,196); mount GET (:231-242) |
| 25 | Demo banner: locked copy, non-dismissible, first shrink-0 child, locked condition (15-07) | ✓ VERIFIED | ChatContainer.tsx:49 verbatim locked sentence; :82-90 role="status", no interactive children, first child; :70 condition |
| 26 | 403 bubble shows [Use demo] when demo_enabled; click retries with use_demo:true (15-07) | ✓ VERIFIED | ChatContainer :155-156 live wiring (demoEligible={false} gone); ErrorMessageBubble :156-158; useChat retryWithDemo :381 |
| 27 | Normal sends carry NO use_demo key (15-07) | ✓ VERIFIED | useChat.ts:164 conditional spread; test asserts key absent |
| 28 | Status null → no banner flash (15-07) | ✓ VERIFIED | :70 both terms false while status null |
| 29 | Prod DB migrated 029-033 (15-08) | ✓ VERIFIED | 15-08 SUMMARY records migration list 001-033 in sync post-push; behavioral corroboration: prod favorites/preferences features functioned in live smoke |
| 30 | Fly prod carries LLM_API_KEY (owner) + DEMO_FALLBACK_ENABLED=true (15-08) | ✓ VERIFIED | Live-system evidence: prod logs show `is_byok: False` on the keyless demo turn (owner key used); banner rendered live proves demo_enabled=true over /api/keys/status; Fly secrets list recorded (names/digests) |
| 31 | Deployed prod carries Phase-15 code (15-08) | ✓ VERIFIED | Independent probe THIS verification: CF bundle index-BCWa5JJ7.js contains the locked banner copy (grep=1); Fly /api/health = 200 |
| 32 | Live prod smoke passes (15-08) | ✓ VERIFIED (with caveat) | Human checkpoint: "approved-with-caveat" — keyless free turn hit an upstream 429 (environmental, Venice rate-limit; pre-authorized caveat class per plan Task 4 + D-999.1-LLM-A). Logs prove correct demo resolution; post-connect flow all green (exchange 200 → PATCH 200 → auto-apply toast) |

**Score:** 29/32 truths verified (3 failed from 2 root causes: CR-01, CR-02)

### Required Artifacts

All plan-declared artifacts pass Levels 1-3 via `gsd-sdk query verify.artifacts` (19/19 across 8 plans) plus manual substantive checks:

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `supabase/migrations/20240301000033_add_favorite_models.sql` | Single additive TEXT[] DDL, no policies | ✓ VERIFIED | Exactly one ALTER; header rationale; column live in dev (probe) and prod (deploy record) |
| `backend/models/schemas.py` | 4 additive fields | ✓ VERIFIED | :53, :70 (max_length=200), :88, :145 |
| `backend/routers/keys.py` | demo_enabled both branches | ✓ VERIFIED | :91, :101, :106 |
| `backend/routers/preferences.py` | favorite_models 4 touch points | ✓ VERIFIED | :48, :54, :59, :84, :90, :95 |
| `backend/routers/chat.py` | _demo_model_for + gated use_demo override | ⚠️ VERIFIED-WITH-BLOCKER | Both present and correct in isolation; downstream deprecated-pin block (:871-890) bypasses the guard (CR-01) |
| `backend/tests/test_key_model_resolution.py` | 7 new + killswitch trio | ✓ VERIFIED | 15 tests, all green; deprecated-pin+demo gap untested |
| `frontend/src/pages/OAuthCallbackPage.tsx(.test)` | One-shot resume | ✓ VERIFIED | Full lifecycle implemented + tested |
| `frontend/src/lib/fuzzy.ts(.test)` | fuzzyScore/matchModel, zero deps | ✓ VERIFIED | Named exports :19, :45; no new packages |
| `frontend/src/components/ModelSelector.tsx(.test)` | Sections/search/chip/star | ⚠️ HOLLOW on late-prop path | Substantive and wired, but CR-02 makes the settings-surface panel render empty (data present, render gated on stale state) |
| `frontend/src/hooks/useKeyGate.tsx(.test)` | Locked decision table + stash | ✓ VERIFIED | Full table :69-93; stash contract :100-108 |
| `frontend/src/components/ConfirmDialog.tsx` | primary variant + light shell | ✓ VERIFIED | variant prop :15,:25; KeyRound/blue-600 :44-45,:63-65; danger path intact |
| `frontend/src/hooks/useChat.ts` | lastTurnWasDemo + retryWithDemo | ✓ VERIFIED | :58, :164, :268, :381, :398-399 |
| `frontend/src/components/ChatContainer.tsx` | Banner + live demoEligible/onUseDemo | ✓ VERIFIED | :49, :70, :82-90, :155-156 |
| `.planning/.../15-08-SUMMARY.md` | Deploy record | ✓ VERIFIED | Migration list, secrets (names only), smoke verbatim, log diagnosis |

### Key Link Verification

(SDK link checker could not parse descriptive `from` fields — all links verified manually.)

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| keys.py status() | config demo_fallback_enabled | computed once, both returns | ✓ WIRED | keys.py:91,101,106 |
| preferences.py | user_preferences.favorite_models | select + exclude_unset upsert | ✓ WIRED | 6 touch points |
| chat.py _resolve_key_and_model | model_cache.is_free | _demo_model_for one-row read | ✓ WIRED | `is_free is True` guard chat.py:170 |
| use_demo override | settings.demo_fallback_enabled | same condition, pre-user-key | ✓ WIRED | chat.py:212 |
| resolver demo output | actual LLM call model | send_message caller | ✗ BROKEN (CR-01) | Deprecated-pin block overrides model post-resolution with no guard |
| sessionStorage or_pending_selection | PATCH threads / PUT preferences | removeItem FIRST then apply | ✓ WIRED | OAuthCallbackPage :79→:92-105 |
| pending.returnTo | navigate() | allowlist ['/','/settings'] | ✓ WIRED | :22, :111-114 |
| ModelSelector mount | GET /api/preferences | favorites seed | ✓ WIRED | :231-242 |
| search input | listbox rows | aria-activedescendant section-scoped ids | ✓ WIRED | :376, :409 |
| SettingsPage models prop | ModelSelector rendered options | suppliedModels → state gate | ✗ BROKEN (CR-02) | rows derived correctly but render gated on never-updating `state` |
| useKeyGate [Connect] | stash + startOpenRouterConnect | setItem before launch | ✓ WIRED | useKeyGate :100-109 |
| DefaultModelSelector | useKeyGate.guardedSelect | gate before onChange/PUT | ✓ WIRED | DefaultModelSelector :34-48, :56 |
| useChat done event | parsed.mode === 'demo' | setLastTurnWasDemo | ✓ WIRED | useChat :268 |
| ChatPage | ChatContainer | lastTurnWasDemo + onUseDemo props | ✓ WIRED | ChatPage :215-216 |
| ErrorMessageBubble call site | useKeyStatus.demo_enabled | demoEligible={Boolean(status?.demo_enabled)} | ✓ WIRED | ChatContainer :155 |
| Fly DEMO_FALLBACK_ENABLED | config.py demo_fallback_enabled | pydantic-settings env read | ✓ WIRED | config.py:37 default False; live behavior proves ON in prod |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|--------------|--------|--------------------|--------|
| ModelSelector (chat surface) | rows | models prop at mount / lazy GET /api/models | Yes | ✓ FLOWING |
| ModelSelector (settings surface) | rows vs `state` | models prop arriving post-mount | Data arrives but render gated on stale state | ⚠️ HOLLOW (CR-02) |
| ModelSelector favorites | favorites | mount GET /api/preferences | Yes (favorite_models column live) | ✓ FLOWING |
| Demo banner | status.demo_enabled | useKeyStatus → GET /api/keys/status → env flag | Yes (both branches) | ✓ FLOWING |
| Demo banner latch | lastTurnWasDemo | SSE done event mode:"demo" | Yes (Phase-11 emitter) | ✓ FLOWING |
| Gate modal | models[].is_free | server-computed catalog, rendered verbatim | Yes | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Backend phase tests | `pytest test_key_model_resolution.py test_keys_status.py test_preferences_api.py -q` | 28 passed | ✓ PASS |
| Frontend phase tests | `vitest run` on the 6 phase test files | 95 passed (6 files) | ✓ PASS |
| Dev DB column live | supabase-py select favorite_models limit 1 | "column live" | ✓ PASS |
| Prod frontend carries Phase-15 code | curl CF bundle, grep locked banner copy | 1 match | ✓ PASS |
| Prod backend health | curl fly.dev /api/health | 200 | ✓ PASS |

### Probe Execution

No `scripts/*/tests/probe-*.sh` probes exist or are declared by this phase — SKIPPED (no conventional probes; the dev-DB column probe above substitutes for 15-01's plan-declared probe and passed).

### Requirements Coverage

| Requirement | Source Plan(s) | Description | Status | Evidence |
|-------------|---------------|-------------|--------|----------|
| KEY-05 | 15-03, 15-05 | Keyless model pick triggers OAuth connect | ⚠️ SATISFIED-WITH-WARNING | Gate + resume complete, tested, live-verified on chat surface (smoke: modal → OAuth → auto-apply PATCH 200). Settings surface impaired by CR-02 |
| MODEL-08 | 15-01, 15-06 | Favorite/pin models to top of picker | ⚠️ SATISFIED-WITH-WARNING | Column live dev+prod; star/toggle/PUT/sections verified. Settings-surface starring blocked by CR-02 |
| DEMO-01 | 15-01, 15-02, 15-07, 15-08 | Env-driven demo fallback flag (default OFF) | ✓ SATISFIED | config.py:37 default False; flag surfaced read-only; ON in prod; is_byok:false proven live |
| DEMO-02 | 15-07 | Non-dismissible demo-mode banner | ✓ SATISFIED | Locked copy verbatim, role="status", no interactive children, no-flash condition; seen live |
| SEC-03 | 15-02, 15-08 | Owner-key cost bounded before demo ON in prod | ⚠️ SATISFIED (literal) / AT-RISK (structural) | The literal bound (999.2 guardrail trip-test PASS at $0.1026 + kill switch tests green) holds and the flag was flipped atop it. But CR-01 breaches the D-03 structural $0 bound — worst-case owner spend is now the ~$0.10 provider ceiling, not $0, on a user-reachable path |
| MODEL-03 (fold-in B-1) | 15-04 | Popular marking rendered | ✓ SATISFIED | Chip renders in every section instance |
| MODEL-01 (fold-in W-1) | 15-04 | Catalog search | ⚠️ SATISFIED-WITH-WARNING | Fuzzy search complete on chat surface; settings surface impaired by CR-02 |

**Orphaned requirements:** None — REQUIREMENTS.md maps exactly KEY-05, MODEL-08, DEMO-01, DEMO-02, SEC-03 to Phase 15; all five are claimed by plan frontmatter. MODEL-01/MODEL-03 fold-ins are additive scope over their Phase-12 completions.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| backend/routers/chat.py | 871-890 | Post-resolution model override without guard re-application (CR-01) | 🛑 Blocker | Paid model on owner key in demo mode; live in prod |
| frontend/src/components/ModelSelector.tsx | 122-126, 201-212 | Mount-time state seed never updated on late prop (CR-02) | 🛑 Blocker | Settings picker permanently empty panel |
| backend/routers/preferences.py + schemas.py | 75-80 / :70 | Explicit `favorite_models: null` (or `theme: null`) → NOT NULL 23502 → unhandled 500 (review WR-01) | ⚠️ Warning | Self-inflicted 500, no data corruption |
| frontend/src/hooks/useChat.ts | 268 | Latch never clears on subsequent non-demo turn in same thread (review WR-02) | ⚠️ Warning | Stale "Demo mode" banner while billing user's own key; copy factually wrong |
| backend/routers/chat.py | 747-763 | retry=true deletes newest assistant row even when not an orphan (review WR-03, pre-existing Phase 8) | ⚠️ Warning | Data loss on network-failed generic Retry; [Use demo] path itself safe (403s post-placeholder) |
| backend/models/schemas.py | 70 | favorite_models items unbounded strings; only count capped (review WR-04) | ⚠️ Warning | Row bloat via 200 multi-MB strings |
| — | — | No TBD/FIXME/XXX debt markers in any phase-modified file | ℹ️ Info | Clean |
| backend/tests/test_key_model_resolution.py | 1-22 | Stale "Wave 0 stub" docstring + dead `_WAVE0` (review IN-03) | ℹ️ Info | Cosmetic |

### Human Verification Required

Superseded by gaps for status purposes (gaps_found takes priority). Recorded for the re-verification pass:

### 1. CR-01 fix live-check
**Test:** Keyless account, pin a thread to a model id absent from model_cache, set a paid default_model, send a message.
**Expected:** Turn runs settings.demo_fallback_model (log-verifiable), never the paid default.
**Why human:** Requires live authenticated session with the flag ON.

### 2. CR-02 fix settings-picker check
**Test:** Hard-reload /settings, open the Default model picker after the catalog fetch resolves.
**Expected:** Sections render; search and stars work.
**Why human:** Real fetch timing; automated tests control the mock timing.

### 3. Keyless free-model streaming re-smoke
**Test:** Keyless prod account, pick a free model, send.
**Expected:** Turn streams with the banner (the 15-08 smoke hit an environmental 429).
**Why human:** Live provider availability; pre-authorized caveat class (D-999.1-LLM-A).

### Gaps Summary

The phase delivered nearly everything it promised, and the SUMMARYs are accurate about what was built — 29/32 truths verified against real code, all 123 focused tests green, prod deploy independently corroborated (CF bundle carries the locked banner copy; Fly health 200; live logs prove the demo branch resolved on the owner key with the free-guard engaged). The two code-review criticals are both CONFIRMED in the codebase and both break must-have truths:

1. **CR-01 (backend, security):** `_demo_model_for` is correct, but the pre-existing deprecated-pin fallback in `send_message` overrides its output with an unguarded default AFTER resolution. Verification found it worse than reviewed: thread PATCH performs no model-id validation and `default_model` is user-settable, so the paid-model-on-owner-key path is deliberately reachable by any authenticated keyless user, not just an edge-case deprecation race. The 15-02 must-have "paid/unknown/error outcomes fall back to the pinned demo_fallback_model" is false end-to-end, and the vulnerable code is live in prod with the flag ON. Owner exposure is bounded only by the ~$0.10 provider guardrail. Fix is a 3-line guard re-application + one regression test + backend redeploy.

2. **CR-02 (frontend, functional):** the rebuilt ModelSelector never transitions to 'loaded' when the catalog prop arrives after mount — the guaranteed timing on the Settings page. The settings picker opens to a permanently empty panel, failing the 15-04 sections truth and the 15-05 "both surfaces" truth, and collaterally blocking settings-surface search (MODEL-01), starring (MODEL-08), and gating (KEY-05). Chat surface unaffected (catalog resolves before the header selector mounts), which is why the prod smoke passed. Fix is a one-line effective-state derivation + one late-arrival test.

Both gaps are single-root-cause, small-diff fixes. Everything else — OAuth resume, gate decision table, stash hygiene, banner, [Use demo] recovery, favorites persistence, fuzzy search, Popular chip, killswitch posture, deploy ordering — is verified in code, not just claimed.

---

_Verified: 2026-07-07T20:08:42Z_
_Verifier: Claude (gsd-verifier)_
