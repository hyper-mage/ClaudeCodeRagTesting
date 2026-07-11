---
phase: 15-options-ui-capstone-demo-gating
verified: 2026-07-09T21:23:41Z
status: passed
score: 32/32 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 29/32
  gaps_closed:
    - "Keyless flag-ON turn runs the picked model ONLY when is_free=True; else pinned demo fallback (15-02 #1 / truth 5) — CR-01"
    - "Dropdown shows Favorites → Popular → All sections; renders under late-catalog timing (15-04 #2 / truth 13) — CR-02"
    - "Connected user picks any model, both surfaces, applies immediately (15-05 #1 / truth 16) — CR-02"
  gaps_remaining: []
  regressions: []
accepted_caveats:
  - item: "Live keyless free-model streaming re-smoke in prod"
    caveat: "Free provider (Venice/:free slug) returned HTTP 429 rate-limit AFTER the model resolution correctly selected the :free fallback. Pre-authorized environmental caveat class D-999.1-LLM-A — the resolution/notice-row evidence is the pass signal, not the stream completion. Both the 15-08 smoke and the 15-09 live CR-01 check hit this; both proved correct resolution on the owner key."
    accepted_by: "operator (15-09 Task 2)"
    accepted_at: "2026-07-09"
---

# Phase 15: Options UI Capstone + Demo Gating — Verification Report (Gap-Closure Re-Verification)

**Phase Goal:** Close out v1.2: key-gated model selection (picking a model with no key triggers OAuth connect), favorite/pin models, demo-fallback flag decision + non-dismissible demo banner (gated on the 999.2 SEC-03 PASS finding), and the picker polish the audit flagged — render popular marking (B-1/MODEL-03) and add catalog search (W-1/MODEL-01).
**Verified:** 2026-07-09T21:23:41Z
**Status:** passed
**Re-verification:** Yes — after gap closure (15-09 CR-01, 15-10 CR-02). Prior pass was gaps_found at 29/32.

## Re-Verification Summary

The prior verification (2026-07-07) returned `gaps_found` at 29/32, with 3 truths failed from 2 root causes: CR-01 (backend security — the deprecated-pin override clobbered the free-guarded demo model with an unguarded paid default) and CR-02 (frontend — ModelSelector never transitioned to 'loaded' when the catalog prop arrived post-mount, leaving the Settings picker empty). Two gap-closure plans (15-09, 15-10) were executed. This pass confirms **both root causes are closed in real code, all three previously-failed truths now VERIFIED, and the other 29 truths did not regress**. No new gaps introduced.

## Goal Achievement

### Observable Truths (32 total)

Only the 3 previously-failed truths received full re-verification; the other 29 received a regression check (existence + suite-green sanity). All 32 now VERIFIED.

| #  | Truth (plan) | Status | Evidence |
|----|--------------|--------|----------|
| 1  | GET /api/keys/status returns demo_enabled in BOTH branches (15-01) | ✓ VERIFIED (regression) | Untouched by gap diffs; test_keys_status green in 33-test backend run |
| 2  | Preferences favorite_models roundtrip, no clobber (15-01) | ✓ VERIFIED (regression) | preferences.py untouched; test_preferences_api green |
| 3  | MessageCreate accepts optional use_demo (15-01) | ✓ VERIFIED (regression) | schemas.py untouched |
| 4  | favorite_models column live in dev DB (15-01) | ✓ VERIFIED (prior) | Prior live probe; column unchanged |
| 5  | Keyless flag-ON turn runs picked model only when is_free=True; else pinned fallback (15-02) | ✓ **VERIFIED (CR-01 CLOSED)** | `_deprecated_pin_default_model` (chat.py:179-199) re-applies `_demo_model_for` when mode=="demo"; wired at chat.py:900-902 so BOTH the notice (912) and the `model=default_model` override (916) use the guarded value; mode in scope (861), settings in scope (826). 3 regression tests green (18/18). Live-prod: keyless + bogus pin + paid `openai/gpt-4o` default → resolved `meta-llama/llama-3.3-70b-instruct:free` (notice-row proof), never the paid model |
| 6  | use_demo short-circuits BEFORE user-key branch only when flag ON (15-02) | ✓ VERIFIED (regression) | chat.py:235 single condition unchanged, still positioned before the user_api_keys read (245); inert-when-OFF tests green |
| 7  | SEC-03 killswitch trio pass unmodified (15-02) | ✓ VERIFIED (regression) | Killswitch trio present and green in the 18-test resolution run |
| 8  | Stash removed FIRST, apply, combined toast, allowlisted navigate (15-03) | ✓ VERIFIED (regression) | OAuthCallbackPage untouched; full FE suite green |
| 9  | Apply failure → warning toast + still navigates (15-03) | ✓ VERIFIED (regression) | Untouched; FE suite green |
| 10 | No/unparseable stash → legacy byte-identical (15-03) | ✓ VERIFIED (regression) | Untouched; FE suite green |
| 11 | Back-to-settings clears stash; Retry preserves (15-03) | ✓ VERIFIED (regression) | Untouched; FE suite green |
| 12 | Fuzzy search filters typo-tolerantly with locked ranking + no-match copy (15-04) | ✓ VERIFIED (regression) | fuzzy.ts untouched; ModelSelector 30/30 green |
| 13 | Dropdown shows Favorites → Popular → All sections per spec (15-04) | ✓ **VERIFIED (CR-02 CLOSED)** | `effectiveState = suppliedModels ? 'loaded' : state` (ModelSelector.tsx:150); 4 render gates key off effectiveState (421/425/435/443); empty-`[]` regression preserved (suppliedModels stays undefined at :122). Late-arrival test (line 241) reproduces SettingsPage timing (undefined mount → rerender with catalog) and asserts headers `['Favorites','Popular','All models']` + SECTIONED_COUNT+1 options + no lazy fetch. 30/30 green |
| 14 | Popular chip on every popularity_rank row in EVERY section instance (15-04) | ✓ VERIFIED (regression) | ModelHint chip logic untouched; 30/30 green |
| 15 | Combobox focus/keyboard a11y contract (15-04) | ✓ VERIFIED (regression) | a11y wiring untouched; 30/30 green |
| 16 | Connected pick applies immediately, no modal, both surfaces (15-05) | ✓ **VERIFIED (CR-02 CLOSED)** | Gate pass-through unchanged (useKeyGate green); chat surface prop-at-mount → effectiveState 'loaded'; settings surface late prop → effectiveState 'loaded'. SettingsPage(:32 undefined seed, :40 setModels) → DefaultModelSelector(:56) → ModelSelector wiring confirmed. Both surfaces now operable |
| 17 | Keyless decision table: demo-ON free / paid gates / demo-OFF gates all (15-05) | ✓ VERIFIED (regression) | useKeyGate untouched; useKeyGate.test green |
| 18 | [Connect] writes stash then launches PKCE; [Cancel] unchanged (15-05) | ✓ VERIFIED (regression) | useKeyGate untouched |
| 19 | Keyless settings pick fires no optimistic onChange/PUT (15-05) | ✓ VERIFIED (regression) | DefaultModelSelector gate wiring intact (:56) |
| 20 | Non-gate connect launchers clear stale stash (15-05) | ✓ VERIFIED (regression) | Untouched |
| 21 | Star on every catalog row, toggles without select/close (15-06) | ✓ VERIFIED (regression) | Star logic untouched; 30/30 green |
| 22 | Shift+Enter toggles favorite; Enter selects (15-06) | ✓ VERIFIED (regression) | Untouched; 30/30 green |
| 23 | Optimistic whole-array PUT, silent, no revert (15-06) | ✓ VERIFIED (regression) | Untouched; 30/30 green |
| 24 | Star → Favorites section same session; persists via mount GET (15-06) | ✓ VERIFIED (regression) | Favorites read/section intersection untouched; 30/30 green |
| 25 | Demo banner: locked copy, non-dismissible, first shrink-0 child, locked condition (15-07) | ✓ VERIFIED (regression) | ChatContainer.tsx:49 verbatim copy, :84 role="status", :78 first shrink-0 child, :70 condition — all intact |
| 26 | 403 bubble shows [Use demo]; click retries with use_demo:true (15-07) | ✓ VERIFIED (regression) | ChatContainer/useChat untouched; FE suite green |
| 27 | Normal sends carry NO use_demo key (15-07) | ✓ VERIFIED (regression) | useChat untouched; FE suite green |
| 28 | Status null → no banner flash (15-07) | ✓ VERIFIED (regression) | ChatContainer:70 condition intact |
| 29 | Prod DB migrated 029-033 (15-08) | ✓ VERIFIED (prior) | Prior deploy record; unchanged by backend code-only redeploy |
| 30 | Fly prod carries LLM_API_KEY (owner) + DEMO_FALLBACK_ENABLED=true (15-08) | ✓ VERIFIED (re-confirmed) | 15-09 Task 2 re-confirmed via GET /api/keys/status → demo_enabled:true, is_byok:false on the demo turn (owner key) after redeploy |
| 31 | Deployed prod carries Phase-15 code (15-08) | ✓ VERIFIED (re-confirmed) | 15-09 redeploy: image deployment-01KX3XR4TWXGT5M4CRGC31TZNE rolled to both machines; the live CR-01 test executing against the fixed binary proves the new code serves |
| 32 | Live prod smoke passes (15-08) | ✓ VERIFIED (with accepted caveat) | Resolution correctness proven live (notice-row); free-provider 429 is the pre-authorized environmental caveat class D-999.1-LLM-A. Same posture as the prior verified-with-caveat pass |

**Score:** 32/32 truths verified (3 previously-failed now CLOSED; 29 regression-checked clean)

### Required Artifacts

Only artifacts touched by the two gap-closure diffs received full re-verification; the rest are unchanged from the prior VERIFIED pass.

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/routers/chat.py` | Free-guarded deprecated-pin override via `_deprecated_pin_default_model` | ✓ VERIFIED | Helper at :179-199 (demo-only guard); called at :900-902; old inline `_safe_user_default_model(...) or settings.llm_model` gone from the block; guarded value flows to both notice (:912) and model override (:916) |
| `backend/tests/test_key_model_resolution.py` | Deprecated-pin + demo regression coverage; IN-03 cleanup | ✓ VERIFIED | 3 new tests (:557/:574/:590) assert demo+paid→fallback, demo+unknown→fallback, user-mode→paid unchanged; `_WAVE0` count 0; "Wave 0 stub" count 0; 18/18 green |
| `frontend/src/components/ModelSelector.tsx` | effectiveState render gating for late catalog | ✓ VERIFIED | `effectiveState: LoadState = suppliedModels ? 'loaded' : state` (:150); 4 panel gates retargeted (:421/:425/:435/:443); no bare `state ===` on those gates (the two remaining `state === 'idle'` at :227/:255 are the lazy-fetch triggers, intentionally untouched) |
| `frontend/src/components/ModelSelector.test.tsx` | Late-arrival render test | ✓ VERIFIED | Test at :241 renders models=undefined → rerender with catalog → open → asserts sections + option count + no `/api/models` fetch; 30/30 green |

### Key Link Verification

The two links marked BROKEN in the prior pass are now WIRED; the rest are unchanged-VERIFIED.

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| resolver demo output / deprecated-pin override | actual LLM call model | `_deprecated_pin_default_model` re-runs `_demo_model_for` in demo mode | ✓ **WIRED (was BROKEN — CR-01)** | chat.py:900→916; guarded value used for the override |
| deprecated-pin notice copy | guarded default_model | same helper return | ✓ WIRED | chat.py:912 interpolates the guarded slug — the notice now names the free fallback in demo mode |
| SettingsPage models prop (late setModels) | ModelSelector open-panel render | `effectiveState = suppliedModels ? 'loaded' : state` | ✓ **WIRED (was BROKEN — CR-02)** | SettingsPage:32/:40 → DefaultModelSelector:56 → ModelSelector:150 gates |
| threads.py PATCH (unvalidated pin) | resolution seam | free-guard at USE, not write (T-15-33 accept) | ✓ WIRED (by design) | Bogus pin now resolves to the free fallback regardless — proven live (bogus id `totally/bogus-deprecated-v9` → `:free`) |
| (all other prior-verified links) | — | — | ✓ WIRED (unchanged) | Not touched by the gap diffs |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|--------------|--------|--------------------|--------|
| ModelSelector (settings surface) | rows vs effectiveState | models prop arriving post-mount | Data arrives AND render now gated on effectiveState (follows the late prop) | ✓ **FLOWING (was HOLLOW — CR-02)** |
| ModelSelector (chat surface) | rows | models prop at mount / lazy GET | Yes | ✓ FLOWING (unchanged) |
| chat demo resolution (deprecated-pin) | model override | model_cache.is_free via `_demo_model_for` | Yes — non-free/unknown → pinned free fallback | ✓ FLOWING (CR-01) |
| Demo banner | status.demo_enabled | GET /api/keys/status → env flag | Yes | ✓ FLOWING (unchanged) |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Backend resolution suite (incl. 3 CR-01 tests) | `venv/Scripts/python.exe -m pytest tests/test_key_model_resolution.py -q` | 18 passed | ✓ PASS |
| Backend related suites (regression) | `pytest test_key_model_resolution + test_keys_status + test_preferences_api + test_deprecated_model_fallback -q` | 33 passed | ✓ PASS |
| Frontend ModelSelector suite (incl. late-arrival test) | `npx vitest run src/components/ModelSelector.test.tsx` | 30 passed | ✓ PASS |
| Frontend full suite (regression) | `npx vitest run` | 126 passed (12 files) | ✓ PASS |
| IN-03 scaffold cleanup | `grep -c _WAVE0 / "Wave 0 stub"` | 0 / 0 | ✓ PASS |

### Probe Execution

No `scripts/*/tests/probe-*.sh` probes exist or are declared by this phase — SKIPPED (no conventional probes). The pytest/vitest suites above are the phase's declared automated checks and were run in-process.

### Requirements Coverage

| Requirement | Source Plan(s) | Description | Status | Evidence |
|-------------|---------------|-------------|--------|----------|
| KEY-05 | 15-03, 15-05, 15-10 | Keyless model pick triggers OAuth connect | ✓ SATISFIED | Gate + resume complete; settings-surface picker now operable (CR-02 closed) so the gate is reachable on both surfaces |
| MODEL-08 | 15-01, 15-06, 15-10 | Favorite/pin models to top of picker | ✓ SATISFIED | Column live; star/toggle/PUT/sections verified; settings-surface starring unblocked (CR-02 closed) |
| DEMO-01 | 15-01, 15-02, 15-07, 15-08, 15-09 | Env-driven demo fallback flag (default OFF) | ✓ SATISFIED | config default OFF; ON in prod; is_byok:false live; **structural $0 owner-cost bound restored end-to-end** (CR-01 closed) |
| DEMO-02 | 15-07 | Non-dismissible demo-mode banner | ✓ SATISFIED | Locked copy verbatim, role="status", no interactive children, no-flash condition — intact. NOTE: REQUIREMENTS.md tracking still marks this `[ ]`/Pending (stale — code satisfies it; see Anti-Patterns) |
| SEC-03 | 15-02, 15-08, 15-09 | Owner-key cost bounded before demo ON in prod | ✓ SATISFIED (structural bound restored) | Literal 999.2 guardrail PASS + killswitch trio green PLUS the D-03 structural $0 bound is now enforced on the previously-breached deprecated-pin path (CR-01). Live-verified: keyless bogus-pin + paid default → free fallback |
| MODEL-03 (fold-in B-1) | 15-04, 15-10 | Popular marking rendered | ✓ SATISFIED | Chip renders in every section instance; now visible on the settings surface too (CR-02) |
| MODEL-01 (fold-in W-1) | 15-04, 15-10 | Catalog search | ✓ SATISFIED | Fuzzy search complete; settings-surface search unblocked (CR-02 closed) |

**All requirement IDs accounted for.** Phase-15-mapped set (REQUIREMENTS.md line 130): KEY-05, MODEL-08, DEMO-01, DEMO-02, SEC-03 — all claimed by plan frontmatter, all SATISFIED. Fold-ins MODEL-01/MODEL-03 (Phase-12 requirements, additive polish scope) SATISFIED. **Orphaned requirements: None.**

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| backend/routers/chat.py | 900-916 | (RESOLVED) Post-resolution override now free-guarded via `_deprecated_pin_default_model` | ✓ Fixed (was CR-01 Blocker) | Owner-key paid-spend path closed; verified live |
| frontend/src/components/ModelSelector.tsx | 150 | (RESOLVED) Render gated on derived effectiveState; late prop unlocks the panel | ✓ Fixed (was CR-02 Blocker) | Settings picker renders under real timing |
| .planning/REQUIREMENTS.md | 39, 109 | DEMO-02 tracking row still `[ ]`/Pending though the banner deliverable exists and is verified | ℹ️ Info (doc lag) | Tracking table lag only — no code gap; recommend flipping to Complete |
| backend/routers/preferences.py + schemas.py | 75-80 / :70 | Explicit `favorite_models: null` → NOT NULL 23502 → unhandled 500 (review WR-01) | ⚠️ Warning (pre-existing, out of scope) | Self-inflicted 500, no data corruption |
| frontend/src/hooks/useChat.ts | 268 | Demo-banner latch never clears on a subsequent non-demo turn in the same thread (review WR-02) | ⚠️ Warning (pre-existing, out of scope) | Stale "Demo mode" banner copy |
| backend/routers/chat.py | 747-763 | retry=true deletes newest assistant row even when not an orphan (review WR-03, pre-existing Phase 8) | ⚠️ Warning (pre-existing, out of scope) | Data loss on network-failed generic Retry; [Use demo] path itself safe |
| backend/models/schemas.py | 70 | favorite_models items unbounded strings; only count capped (review WR-04) | ⚠️ Warning (pre-existing, out of scope) | Row bloat risk |
| gap-closure files | — | No TBD/FIXME/XXX/HACK debt markers in any of the 4 files touched by 15-09/15-10 | ℹ️ Info | Clean |

The four ⚠️ warnings (WR-01..WR-04) are pre-existing, were already logged in the prior pass, and are outside the CR-01/CR-02 gap-closure scope. They did not block `passed` in the prior pass's truth accounting and do not now — they are carried forward as backlog items, not phase-goal blockers.

### Human Verification Required

None blocking. The two blocking human items from the prior pass are resolved:

1. **CR-01 live security check — PERFORMED and PASSED.** Operator executed the exact exploit path against flag-ON prod (keyless `ragtest1@gmail.com`, thread PATCHed to bogus id `totally/bogus-deprecated-v9`, paid `openai/gpt-4o` default, normal send). The DB notice row resolved to `meta-llama/llama-3.3-70b-instruct:free`, never the paid model. Operator verdict: `approved-with-caveat`. Recorded verbatim in 15-09-SUMMARY.
2. **CR-02 settings-picker check — closed by a deterministic fix + faithful reproduction test.** The prior human item existed because the bug was timing-dependent; the fix (`effectiveState = suppliedModels ? 'loaded' : state`) eliminates the timing dependency entirely — any defined catalog prop unlocks the panel on the next render, with no async gap. The late-arrival test reproduces the real SettingsPage sequence (undefined at mount → prop after mount-drain). No residual human check required.

**Accepted caveat (informational, non-blocking):** live keyless free-model streaming in prod remains subject to free-provider availability (HTTP 429 from the `:free` slug at both the 15-08 and 15-09 checks). This is pre-authorized caveat class D-999.1-LLM-A — the model-resolution correctness is the pass signal, and it was proven both times. Truth #32 carries this caveat as it did in the prior verified pass.

### Gaps Summary

No gaps. Both root causes from the prior `gaps_found` verification are closed in real code, backed by tests run in-process this pass and (for CR-01) a live-prod security check with operator sign-off:

- **CR-01 (backend/security) CLOSED:** `_deprecated_pin_default_model` (chat.py:179-199) re-applies the D-03 free-guard when `mode == "demo"`, and it is wired into the deprecated-pin block (chat.py:900-902) so both the notice copy and the `model` override use the guarded value. `mode` and `settings` are both in scope. Three regression tests assert demo+paid→fallback, demo+unknown→fallback, and the non-demo control keeps the paid default — all green (18/18). Live prod resolved a keyless bogus-pin + paid default to the `:free` fallback (notice-row proof). SEC-03's structural $0 owner-cost bound is restored end-to-end; DEMO-01 holds in prod.
- **CR-02 (frontend/functional) CLOSED:** ModelSelector render-gates off a derived `effectiveState`, so a catalog prop arriving after mount (the guaranteed Settings-page timing) immediately flips the panel to 'loaded'. The four panel gates key off `effectiveState`; the empty-`[]` lazy-fetch regression is preserved (suppliedModels stays undefined). The late-arrival test reproduces the SettingsPage sequence and passes (30/30 ModelSelector, 126/126 full FE suite). The settings surface is operable, re-enabling KEY-05 gating, MODEL-08 starring, MODEL-01 search, and MODEL-03 chips on that surface.

No regressions across the other 29 truths (33 backend + 126 frontend tests green; all non-gap files untouched by the two diffs). No new debt markers. All five gap-closure commits (`6804532`, `164bff9`, `7f7b080`, `2222950`, `8da66f6`) exist in history. One documentation lag noted (DEMO-02 tracking row stale) — informational, not a code gap.

---

_Verified: 2026-07-09T21:23:41Z_
_Verifier: Claude (gsd-verifier)_
