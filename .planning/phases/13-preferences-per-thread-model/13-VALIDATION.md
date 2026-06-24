---
phase: 13
slug: preferences-per-thread-model
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-24
---

# Phase 13 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `13-RESEARCH.md` § Validation Architecture. Task IDs are
> provisional — the planner assigns final `{N}-{plan}-{task}` IDs; this map
> is keyed by requirement/behavior until then.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Backend: pytest (in `backend/venv`, shared fixtures `backend/tests/conftest.py`). Frontend: vitest 4.1.9 + @testing-library/react 16.3.2 + jsdom 29.1.1 |
| **Config file** | Frontend: `frontend/vitest.config.ts` (jsdom, globals, `./src/test/setup.ts`). Backend: none (run via `python -m pytest` from `backend/`) |
| **Quick run command** | Backend: `cd backend && ./venv/Scripts/python -m pytest tests/<file> -x` · Frontend: `cd frontend && npx vitest run src/components/<File>.test.tsx` |
| **Full suite command** | `cd backend && ./venv/Scripts/python -m pytest -q` AND `cd frontend && npm test` |
| **Estimated runtime** | ~30–60 seconds (both suites) |

---

## Sampling Rate

- **After every task commit:** the single relevant quick command (e.g. `pytest tests/test_preferences_api.py -x` or `vitest run <file>`).
- **After every plan wave:** `cd backend && ./venv/Scripts/python -m pytest -q` AND `cd frontend && npm test`.
- **Before `/gsd-verify-work`:** both full suites green.
- **Max feedback latency:** ~60 seconds.

---

## Per-Task Verification Map

| Task (provisional) | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|--------------------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| prefs-api: PUT/GET default_model | — | MODEL-05 | T-IDOR / own-row RLS | user_id from JWT, never body | integration (be) | `pytest tests/test_preferences_api.py::test_put_then_get_default_model -x` | ❌ W0 | ⬜ |
| prefs-api: new-user defaults | — | MODEL-05 | maybe_single guard | brand-new user GET → `{default_model:null, theme:"dark"}` | integration (be) | `pytest tests/test_preferences_api.py::test_get_defaults_for_new_user -x` | ❌ W0 | ⬜ |
| default-model selector PUTs | — | MODEL-05 | — | selector PUTs on select | component (fe) | `vitest run src/components/DefaultModelSelector.test.tsx` | ❌ W0 | ⬜ |
| PATCH threads.model set | — | MODEL-06 | IDOR ownership re-check | `.eq("id",tid).eq("user_id",uid)` before update | integration (be) | `pytest tests/test_thread_model_patch.py::test_patch_sets_model -x` | ❌ W0 | ⬜ |
| PATCH model:null clears pin | — | MODEL-06 | — | clears back to default | integration (be) | `pytest tests/test_thread_model_patch.py::test_patch_null_clears -x` | ❌ W0 | ⬜ |
| resolution reads real thread.model | — | MODEL-06 | — | thread.model wins when set; no regression on absent-schema fallback | unit (be) | `pytest tests/test_key_model_resolution.py::test_thread_model_wins_when_set -x` (+ existing fallthrough) | ✅ file / ❌ new case | ⬜ |
| per-thread selector default sub-state | — | MODEL-06 | — | shows `Default model` when null; PATCHes on select | component (fe) | `vitest run src/components/ChatContainer.test.tsx` (extend) | ✅ file / ❌ cases | ⬜ |
| theme persist + CHECK | — | PREF-02 | invalid-theme poisoning | DB CHECK `theme IN ('light','dark')` + Pydantic Literal | integration (be) | `pytest tests/test_preferences_api.py::test_theme_persist_and_validate -x` | ❌ W0 | ⬜ |
| theme toggle wiring | — | PREF-02 | — | flips `<html>` class + writes localStorage + fires PUT | component (fe) | `vitest run src/components/ThemeToggle.test.tsx` | ❌ W0 | ⬜ |
| FOUC bootstrap | — | PREF-02 | — | html.dark set from localStorage before mount | unit (fe/jsdom) | `vitest run src/test/themeBootstrap.test.ts` | ❌ W0 | ⬜ |
| deprecation fallback + notice | — | SC#4 (D-06) | stored XSS / prompt-confusion | notice React-escaped text; fallback used; no crash | integration (be) | `pytest tests/test_deprecated_model_fallback.py::test_inserts_notice_and_falls_back -x` | ❌ W0 | ⬜ |
| notice excluded from LLM history | — | SC#4 (D-06) | notice-row prompt injection | history map filters role∈(user,assistant) | unit (be) | `pytest tests/test_deprecated_model_fallback.py::test_notice_excluded_from_history -x` | ❌ W0 | ⬜ |
| DeprecationNotice renders as system line | — | SC#4 (D-06) | — | system line, not bubble, not red | component (fe) | `vitest run src/components/DeprecationNotice.test.tsx` | ❌ W0 | ⬜ |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_preferences_api.py` — MODEL-05, PREF-02 (GET/PUT, new-user defaults, theme CHECK). Mirror `test_models_api.py` patching (`app.dependency_overrides[get_user_id]`, `patch("routers.preferences.get_supabase")`).
- [ ] `backend/tests/test_thread_model_patch.py` — MODEL-06 PATCH set/clear + 404 on non-owned thread.
- [ ] `backend/tests/test_deprecated_model_fallback.py` — SC#4: notice insert, fallback override, history exclusion. Reuse `mock_stream_chat_completion` (conftest.py:74) + `_db_with_key_row` mock from `test_key_model_resolution.py`.
- [ ] `backend/tests/test_key_model_resolution.py` — ADD `test_thread_model_wins_when_set` (extends existing file).
- [ ] `frontend/src/components/ModelSelector.test.tsx` — a11y contract (listbox roles, keyboard, ≥44px, selected indicator).
- [ ] `frontend/src/components/ThemeToggle.test.tsx` — class toggle + localStorage write + PUT fired.
- [ ] `frontend/src/components/DefaultModelSelector.test.tsx` + `DeprecationNotice.test.tsx`.
- [ ] `frontend/src/test/themeBootstrap.test.ts` — extract inline-script logic into a tiny importable function for jsdom unit test.
- [ ] No framework install needed — vitest + RTL + jsdom (frontend) and pytest + conftest (backend) already present.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Light palette visually correct on core surfaces (chat/sidebar/login/composer) | PREF-02 | Visual judgment under a real browser; jsdom can't assert rendered color/contrast | Toggle to light, inspect chat/sidebar/login/composer for contrast + no dark-only leftovers |
| No theme flash (FOUC) on hard reload | PREF-02 | Real paint timing — not observable in jsdom | Set light, hard-refresh, confirm no dark flash before first paint |
| Live per-thread model actually used by a real chat turn | MODEL-06 | Requires running backend + a live model round-trip | Pick a model in thread header, send, confirm the chosen model resolves (when the separate live-LLM provider error is resolved) |

*(All other phase behaviors have automated verification per the map above.)*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags (`vitest run` / `pytest`, never `--watch`)
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending (planner assigns final task IDs; reconciled at `/gsd:validate-phase 13`)
