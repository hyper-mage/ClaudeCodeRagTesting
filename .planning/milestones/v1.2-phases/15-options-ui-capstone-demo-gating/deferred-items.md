# Phase 15 — Deferred Items

## D-15-03-A — pre-existing full-repo `npm run lint` failures (5 errors, none in plan-15-03 files)

- **Found during:** Plan 15-03 Task 2 (GREEN verify: `npm run build && npm run lint`).
- **Status:** `npm run lint` exits 1 with 5 pre-existing errors, ALL in files untouched by
  this plan/branch (branch diff = `OAuthCallbackPage.tsx` + `OAuthCallbackPage.test.tsx` only):
  - `src/components/FileUpload.tsx:5` — `@typescript-eslint/no-explicit-any`
  - `src/contexts/AuthContext.tsx:48` — `react-refresh/only-export-components`
  - `src/contexts/ToastContext.tsx:96` — `react-refresh/only-export-components`
  - `src/pages/ChatPage.tsx:49` — `react-hooks/set-state-in-effect` (already documented as
    D-13-06-A in Phase 13 deferred items — known false positive)
  - `src/test/themeBootstrap.test.ts:24` — `@typescript-eslint/no-unused-vars` (`_query`)
- **Plan files are clean:** `npx eslint src/pages/OAuthCallbackPage.tsx src/pages/OAuthCallbackPage.test.tsx`
  exits 0.
- **Out of scope (scope boundary):** none of the five files were authored or modified by
  Plan 15-03; fixing them here would be unrelated churn inside a parallel worktree wave.
- **Resolution:** a dedicated lint-cleanup pass (several are known debt: D-13-06-A, the
  react-refresh context exports pre-date v1.2). No new plan needed for 15-03.

## D-15-08-A — pre-existing env-coupled failure: `tests/test_config.py::test_key_encryption_secret_default`

- **Found during:** Plan 15-08 Task 1 (pre-flight full backend suite).
- **Status:** FAILED — the test asserts `Settings().key_encryption_secret == ""` (the code
  default, `backend/config.py:24`, which is correct), but `config.py` runs
  `load_dotenv(repo-root .env)` at import and the local `.env` now carries
  `KEY_ENCRYPTION_SECRET` (set during Phase 9/10 BYOK work), so pydantic-settings reads the
  real env value. Reproduces in isolation (`pytest tests/test_config.py -q` → 1 failed,
  13 passed) — not order-dependent.
- **Not a code defect:** `demo_fallback_enabled` default-False and all other config-default
  tests pass; the failure is the test not isolating the process environment
  (needs `monkeypatch.delenv("KEY_ENCRYPTION_SECRET", raising=False)`).
- **Out of scope (scope boundary):** pre-existing, in a file untouched by Plan 15-08
  (`files_modified: []`); zero prod/deploy relevance.
- **Secret-hygiene note:** the pytest assertion diff echoes the local `.env` secret value in
  terminal output — one more reason to fix the isolation. Value NOT reproduced in any
  planning artifact.
- **Resolution:** one-line `monkeypatch.delenv` fix in a future lint/test-debt cleanup pass.
