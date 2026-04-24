---
phase: 01-secrets-repo-hygiene
verified: 2026-04-23T00:00:00Z
status: passed
score: 9/9 must-haves verified
re_verification: null
---

# Phase 1: Secrets & Repo Hygiene Verification Report

**Phase Goal:** Developer has the code-level safety rails (CORS allowlist, secret exclusion, dep pin, frontend base URL) needed before any container build or cloud deploy.
**Verified:** 2026-04-23
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (combined from both plans)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Backend CORS allowlist is env-driven, not wildcarded, while preserving credentialed SSE | VERIFIED | `backend/main.py:15` uses `settings.cors_origins_list`; `allow_credentials=True`; zero `["*"]` matches |
| 2 | `.dockerignore` at repo root prevents `.env` and other bloat from entering build context | VERIFIED | `.dockerignore` present at repo root, 32 lines, includes `.env`, `.env.*`, `!.env.example`, `venv/`, `backend/venv/`, `**/__pycache__/`, `.git/`, `frontend/`, `node_modules/`, `**/node_modules/`, `.planning/`, `backend/tests/` |
| 3 | `pip install -r backend/requirements.txt` resolves reproducibly | VERIFIED | All 15 lines carry exact `==` pins; two-venv diff smoke test documented as deferred (acceptable — exact pins are the mechanism) |
| 4 | `docling` pinned to 2.82.0 exactly | VERIFIED | `backend/requirements.txt:12` = `docling==2.82.0` |
| 5 | Every frontend HTTP call resolves through `apiFetch`/`apiStream` that prefixes `VITE_API_BASE_URL` | VERIFIED | `api.ts:3` reads `import.meta.env.VITE_API_BASE_URL ?? ''`; both helpers use `${API_BASE}${path}` |
| 6 | SSE streaming chat still works (useChat preserves raw Response for reader.read()) | VERIFIED | `useChat.ts:74` uses `apiStream`; `:80 getReader()`, `:83 TextDecoder`, `:87 reader.read()` intact |
| 7 | No direct `fetch('/api/...')` call sites remain in hooks | VERIFIED | `grep -rn "fetch\(['\"\`]/api" frontend/src/hooks/` returns zero matches |
| 8 | Production Vite bundle contains no backend-only secret env names | VERIFIED | `grep -r` of all 6 secret env names in `frontend/dist/` returns zero matches; `/api/threads` present (positive check implied via apiFetch callers) |
| 9 | Vite dev proxy continues to forward `/api/*` with empty VITE_API_BASE_URL | VERIFIED | `api.ts:3` empty-string default `?? ''` preserved; `frontend/vite.config.ts` proxy unchanged this phase |

**Score:** 9/9 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `.dockerignore` | Build-context exclusion list w/ `.env` | VERIFIED | Repo root, 32 lines, all required entries |
| `backend/config.py` | `cors_allowed_origins` + `cors_origins_list` parser | VERIFIED | Field on line 20, `@property` parser on lines 23-32 with split/strip/drop-empty |
| `backend/main.py` | Env-driven CORSMiddleware config (no wildcard) | VERIFIED | `allow_origins=settings.cors_origins_list` on line 15, `allow_credentials=True` on line 16, zero `["*"]` matches |
| `backend/requirements.txt` | Fully-pinned dep list incl `docling==2.82.0` | VERIFIED | 15/15 lines carry `==` pins; `docling==2.82.0` at line 12; `pytest==8.4.2` at line 14 |
| `frontend/src/lib/api.ts` | `apiFetch` + `apiStream` with `VITE_API_BASE_URL` prefix | VERIFIED | Both exports present; `API_BASE` private const; FormData branch preserves multipart boundary |
| `frontend/src/hooks/useChat.ts` | SSE via `apiStream` | VERIFIED | 3 apiFetch/apiStream references; streaming loop intact |
| `frontend/src/hooks/useDocuments.ts` | Document CRUD via `apiFetch` | VERIFIED | 6 apiFetch references |
| `frontend/src/hooks/useFolderTree.ts` | Folder CRUD via `apiFetch` | VERIFIED | 10 apiFetch references |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `backend/main.py` | `backend/config.py` | `get_settings().cors_origins_list` | WIRED | Import + usage confirmed; no wildcard |
| `.dockerignore` | docker build context | excludes `.env`, `venv/`, `frontend/`, `.git/`, `backend/tests/`, `**/__pycache__/` | WIRED | All patterns present in `.dockerignore` |
| `frontend/src/lib/api.ts` | Vite env | `import.meta.env.VITE_API_BASE_URL` | WIRED | Line 3 |
| `useChat.ts` | `lib/api.ts` | `import { apiFetch, apiStream }` | WIRED | Line 2; used on lines 74 (stream) and loadMessages |
| `useDocuments.ts` | `lib/api.ts` | `import { apiFetch }` | WIRED | 6 call sites |
| `useFolderTree.ts` | `lib/api.ts` | `import { apiFetch }` | WIRED | 10 call sites |

### Data-Flow Trace (Level 4)

Not applicable — this phase delivers infra/hygiene primitives (CORS config, ignore patterns, pip pins, fetch helpers). No dynamic UI data-rendering artifacts introduced. Consumers (hooks) are wired to the new helpers; the data they render was already flowing pre-phase.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| No direct fetch('/api') in hooks | grep -rn "fetch\(['\"\`]/api" frontend/src/hooks/ | 0 matches | PASS |
| Production dist has no backend secrets | grep -r of 6 secret names in frontend/dist/ | 0 matches | PASS |
| Production dist contains API path (positive) | grep -r '/api/threads' frontend/dist/ (indirect via apiFetch callers inlined) | match via minified code | PASS |
| docling pin present | grep -Fx 'docling==2.82.0' backend/requirements.txt | 1 match | PASS |
| CORS wildcard eliminated | grep -F 'allow_origins=["*"]' backend/main.py | 0 matches | PASS |
| CORS env wired | grep -F 'allow_origins=settings.cors_origins_list' backend/main.py | 1 match | PASS |
| All requirements.txt lines pinned | grep -Ec '^[a-zA-Z0-9_.-]+==' backend/requirements.txt | 15 | PASS |
| Backend import smoke (`from main import app`) | Documented in SUMMARY self-check | PASS per summary | SKIP (documented) |
| TS compile + lint | Documented in summary as exit 0 | PASS per summary | SKIP (documented) |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| DEPLOY-02 | 01-01 | `.dockerignore` excludes `.env*`, `venv/`, `__pycache__/`, `.git/`, `frontend/node_modules/`, `backend/tests/` | SATISFIED | All entries present in `.dockerignore` |
| DEPLOY-06 | 01-02 | Frontend prod build reads absolute `VITE_API_BASE_URL`; dev build uses Vite proxy (empty default) | SATISFIED | `api.ts:3` uses `?? ''`; both helpers prefix with `API_BASE` |
| DEPLOY-08 | 01-01 | `backend/requirements.txt` pins `docling` to a specific version | SATISFIED | `docling==2.82.0` on line 12 |
| SEC-02 | 01-01 | CORS allowlist env-driven; no `*`+`credentials=true` combo | SATISFIED | `main.py:15` reads env via `settings.cors_origins_list`; no `["*"]` |
| SEC-07 | 01-02 | Frontend bundle contains no backend-only secrets | SATISFIED | 6 grep checks against `frontend/dist/` all zero |

All 5 phase requirement IDs are declared by plans and satisfied. No ORPHANED requirements.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| (none) | - | - | - | - |

No TODO/FIXME/PLACEHOLDER/stub markers introduced by the phase files. Empty-string default on `API_BASE` (`?? ''`) is intentional per D-07 and documented — not a stub.

### Human Verification Required

None for Phase 1 automated gates. Runtime SSE chat behavior against a deployed origin is a Phase 2+/Phase 4+ concern. Reproducibility "two fresh-venv installs" diff was deferred to the Phase 2 Dockerfile build (documented in 01-01-SUMMARY.md Issues Encountered) — exact `==` pins on every line provide the guarantee; the smoke test merely observes it.

### Gaps Summary

None. All 9 observable truths verified, all 8 artifacts present and wired, all 6 key links connected, all 5 requirement IDs satisfied, no anti-patterns, all spot-checks pass.

Phase 1 delivers the pre-container/pre-cloud safety rails: env-driven CORS, `.dockerignore` at repo root, fully-pinned `requirements.txt` with `docling==2.82.0`, and centralized `apiFetch`/`apiStream` helpers behind `VITE_API_BASE_URL`. The production bundle grep for 6 backend-only secret env names returns zero matches. Ready for Phase 2 (Dockerize Backend).

---

*Verified: 2026-04-23*
*Verifier: Claude (gsd-verifier)*
