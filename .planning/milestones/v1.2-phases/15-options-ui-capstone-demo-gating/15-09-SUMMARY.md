---
phase: 15-options-ui-capstone-demo-gating
plan: 09
subsystem: api
tags: [fastapi, openrouter, demo-fallback, fly, security, chat-resolution]

# Dependency graph
requires:
  - phase: 15-02
    provides: "_demo_model_for D-03 server-side free-guard + _resolve_key_and_model (mode in scope at the caller)"
  - phase: 15-08
    provides: "prod backend on Fly (boardgame-rag-prod) with DEMO_FALLBACK_ENABLED=true already ON"
  - phase: 13-04
    provides: "at-send deprecated-pin fallback block (notice row + model override) in send_message"
provides:
  - "_deprecated_pin_default_model(db, user_id, mode, settings) — free-guards the deprecated-pin model override on the demo path"
  - "CR-01 closed: keyless demo turns can never mint a paid completion on the owner key via a thread pin + paid user default"
  - "SEC-03 structural $0 owner-cost bound restored end-to-end (verified live in prod)"
  - "IN-03 test-scaffold debt cleaned (dead _WAVE0 + stale Wave-0 docstring removed)"
affects: [chat-resolution, demo-gating, owner-key-cost, prod-deploy]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Free-guard re-applied at the model-USE seam (deprecated-pin override), not the write seam (threads.py PATCH stays unvalidated by design, T-15-33 accept)"
    - "Testable module-level resolver helper mirroring _demo_model_for / _safe_user_default_model (mode threaded in, no new plumbing)"

key-files:
  created: []
  modified:
    - backend/routers/chat.py
    - backend/tests/test_key_model_resolution.py

key-decisions:
  - "The free-guard is deliberately demo-only: mode != 'demo' returns the user default unchanged so a connected user still pays with their own key (control test pins this)"
  - "unknown != free — a user default absent from model_cache falls back to demo_fallback_model, matching _demo_model_for's own defensive posture"
  - "Fix lives at the resolution/override seam, not threads.py PATCH — a bogus pin now resolves safely regardless of the unvalidated write (T-15-33)"

patterns-established:
  - "Pattern: any caller-side model override on the demo path must re-run _demo_model_for; the resolver's free-guard is not sufficient once the caller can clobber the resolved model"

requirements-completed: [SEC-03, DEMO-01]

# Metrics
duration: ~8 min active (Task 1); Task 2 operator-gated
completed: 2026-07-09
---

# Phase 15 Plan 09: CR-01 Deprecated-Pin Demo Free-Guard Summary

**`_deprecated_pin_default_model` re-applies the D-03 free-guard on the deprecated-pin override in demo mode, closing the owner-key paid-spend path — verified live in prod where a keyless bogus-pin + paid `openai/gpt-4o` default resolved to the `:free` fallback, never the paid model.**

## Performance

- **Duration:** ~8 min active code work (Task 1); Task 2 operator-gated (prod deploy + live security check, spanning a Fly host incident and a free-provider 429)
- **Started:** 2026-07-08T14:33:41Z
- **Tasks:** 2 (Task 1 code fix + regression tests; Task 2 blocking human-gated prod redeploy + live verification)
- **Files modified:** 2

## Accomplishments

- Extracted a testable module-level helper `_deprecated_pin_default_model(db, user_id, mode, settings)` beside `_demo_model_for` / `_safe_user_default_model`. It computes `base = _safe_user_default_model(db, user_id) or settings.llm_model`, then in demo mode returns `_demo_model_for(db, base, settings)` (the D-03 free-guard re-application); off the demo path it returns `base` unchanged.
- Wired it into `send_message`'s deprecated-pin block so BOTH the persisted `notice` copy ("using {default_model} instead") AND the `model = default_model` override use the guarded value. In demo mode the notice now correctly names the free fallback.
- Added 3 regression tests (previously zero coverage for the demo + deprecated-pin interaction): demo + paid default (`cache_is_free=False`) → fallback; demo + unknown default (`cache_is_free=None`) → fallback; non-demo control → paid default unchanged.
- Cleaned IN-03 test-scaffold debt: removed the dead `_WAVE0` constant and rewrote the stale "Wave 0 stub" module docstring to describe the now-live suite.
- Redeployed the fixed backend to Fly prod and verified the exploit path is closed against the live flag-ON binary.

## Task Commits

Each task was committed atomically:

1. **Task 1 (RED): failing deprecated-pin demo free-guard regression tests + IN-03 cleanup** - `6804532` (test)
2. **Task 1 (GREEN): free-guard the deprecated-pin override in demo mode** - `164bff9` (feat)
3. **Checkpoint pause: record Task 1 done + pause at Task 2** - `7f7b080` (docs)
4. **Task 2 (ops): prod backend redeploy + live security verification** - no repo file changes (ops-only, evidence recorded here)

**Plan metadata:** (this SUMMARY + STATE + ROADMAP + REQUIREMENTS) — final docs commit.

_TDD task: test (RED) → feat (GREEN); no refactor commit (code was clean)._

## Files Created/Modified

- `backend/routers/chat.py` - Added `_deprecated_pin_default_model` helper (line 179); replaced the inline unguarded `_safe_user_default_model(db, user_id) or settings.llm_model` in the deprecated-pin block (line 900) with the guarded helper call.
- `backend/tests/test_key_model_resolution.py` - 3 new CR-01 regression tests; removed dead `_WAVE0`; rewrote module docstring.

## Verification

**Task 1 (local, `backend/` + real venv):**
- `venv/Scripts/python.exe -m pytest tests/test_key_model_resolution.py -q` → **18 passed** (15 prior + 3 new).
- `tests/test_deprecated_model_fallback.py` (same block) → **2 passed**, no regression.
- Acceptance greps: helper defined + called; old inline default gone from the block; `_demo_model_for(db, base, settings)` applied only when `mode == "demo"`; `_WAVE0` and "Wave 0 stub" both count 0.

**Task 2 (prod deploy — approved-with-caveat by operator):**
- Backend redeployed to Fly prod `boardgame-rag-prod` (code-only, no migration, no secret flip). Image `registry.fly.io/boardgame-rag-prod:deployment-01KX3XR4TWXGT5M4CRGC31TZNE` (2.9 GB), rolled to both machines (dfw `2872d26c105948`, iad `80e35ef6015d48`).
- **Environmental note:** a Fly host incident hit `iad` during rollout — machine `80e35ef6015d48` transiently failed to bind `0.0.0.0:8000` (only hallpass/SSH listening), with earlier depot-builder "context deadline exceeded" cleanup warnings (non-fatal). Operator mitigated by adding a `dfw` machine and confirmed the new release is live/healthy and serving. The live security test below executing successfully against the fixed binary independently proves the new code is serving in prod.
- Secret posture confirmed via `GET /api/keys/status` → `demo_enabled: true` (`DEMO_FALLBACK_ENABLED` still ON); owner `LLM_API_KEY` in use (demo turn ran on owner key, `is_byok` false). Names/status only — no secret value printed.

**Live security check (CR-01 exploit path) — PASS:**
- Account `ragtest1@gmail.com` (sub `c3c3f974-bc9f-430c-b052-5931198f2d3f`): `GET /api/keys/status` → `{"connected":false,"masked_label":null,"connected_at":null,"demo_enabled":true}` (keyless + flag ON).
- Thread `b1faffae-5ec5-4bb1-add3-be23b5bfaf10`: `PATCH /api/threads/{id}` accepted a bogus id `totally/bogus-deprecated-v9` with NO model_cache validation (confirms the widened attack surface in threads.py, T-15-33 accept).
- `PUT /api/preferences` set paid `default_model: "openai/gpt-4o"` (theme/favorites preserved, no clobber).
- Normal send `POST /api/threads/{id}/messages {"content":"hi"}` (no `use_demo`).
- **RESULT** — DB `notice` row (id `9612d3b9-bf48-422b-9563-ddc5d48a4a3a`), verbatim:
  `Model "totally/bogus-deprecated-v9" is no longer available — using meta-llama/llama-3.3-70b-instruct:free instead.`
  → resolved model is the `:free` `demo_fallback_model`, **NEVER** the paid `openai/gpt-4o`. The `_deprecated_pin_default_model` free-guard held on the keyless demo path. D-03 $0 structural bound restored end-to-end in prod.
- The send then hit an environmental free-provider 429 (SSE `event: error {"error":"rate_limit",...}`; assistant row `[Response interrupted]`). Pre-authorized caveat class D-999.1-LLM-A — the notice/resolution evidence is the pass signal; not retried-until-green.

**Operator verdict:** `approved-with-caveat: free-provider 429 (Venice/free-slug rate limit); resolution correctly yielded meta-llama/llama-3.3-70b-instruct:free. CR-01 fixed and verified live in prod.`

## Decisions Made

- **Guard is demo-only.** `mode != "demo"` returns the base user default unchanged — a connected user pays with their own key as before. The non-demo control test (`cache_is_free=False`, `mode="user"` → paid default unchanged) pins that the free-guard is not consulted off the demo path.
- **unknown != free.** A user default absent from `model_cache` (`.data is None`) falls back to `demo_fallback_model`, mirroring `_demo_model_for`'s own defensive posture (never trust the FE, never infer freeness from the `:free` suffix).
- **Fix at the USE seam, not the write.** `threads.py` PATCH stays unvalidated by design (T-15-33 accept); the enforcing boundary is the resolution-seam free-guard, so a bogus pin resolves to the free fallback regardless of what was written.

## Deviations from Plan

None - plan executed exactly as written. TDD flow (RED test → GREEN feat) followed; the IN-03 scaffold cleanup was folded into the RED commit as specified.

## Issues Encountered

- **Fly host incident during rollout (Task 2, environmental):** the `iad` machine transiently failed to bind `0.0.0.0:8000` during the release, with non-fatal depot-builder cleanup warnings. Operator mitigated by adding a `dfw` machine; the live security test passing against the fixed binary independently confirms the new code is serving. Not a code defect.
- **Free-provider 429 on the live send (environmental):** the `:free` fallback slug hit a provider rate limit after the resolution correctly selected it. Pre-authorized caveat class D-999.1-LLM-A — the resolution/notice evidence is the pass signal, so the turn was not retried-until-green.

## User Setup Required

None - no external service configuration required (the demo flag was already ON in prod from 15-08; this was a code-only redeploy).

## Next Phase Readiness

- CR-01 closed: 15-02 #1 holds end-to-end — demo turns never mint a paid completion on the owner key. SEC-03 structural $0 bound (D-03) restored on the keyless path; DEMO-01 holds in prod.
- Phase 15 gap closure: CR-01 (15-09) and CR-02 (15-10) are both now closed. Remaining v1.2 close-out items (per project memory `project_v12_outstanding_gaps`): the 2 SEC-01 manual UAT gates, prod migrations 029-032 status, and a v1.2 audit — tracked outside this plan.

## Self-Check: PASSED

- Files verified present: `15-09-SUMMARY.md`, `backend/routers/chat.py`, `backend/tests/test_key_model_resolution.py`
- Commits verified in history: `6804532` (test/RED), `164bff9` (feat/GREEN), `7f7b080` (docs/pause)

---
*Phase: 15-options-ui-capstone-demo-gating*
*Completed: 2026-07-09*
