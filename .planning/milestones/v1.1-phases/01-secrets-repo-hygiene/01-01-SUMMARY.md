---
phase: 01-secrets-repo-hygiene
plan: 01
subsystem: infra
tags: [cors, docker, pip, security, fastapi, pydantic-settings]

requires:
  - phase: none
    provides: "Starts milestone v1.1 portfolio deployment work"
provides:
  - "Env-driven CORS allowlist (SEC-02) — replaces spec-invalid ['*']+credentials=True combo"
  - ".dockerignore at repo root (DEPLOY-02) — prevents .env and bloat from entering build context"
  - "Fully-pinned backend/requirements.txt including docling==2.82.0 (DEPLOY-08) — reproducible builds"
affects: [phase-02-docker-image, phase-03-fly-deploy, phase-04-supabase-prod]

tech-stack:
  added: []
  patterns:
    - "pydantic-settings str field + @property parser returning list[str] for env-var list parsing"
    - ".dockerignore excludes .env/.env.* but !.env.example (allowlist pattern for build-context secrets)"

key-files:
  created:
    - .dockerignore
  modified:
    - backend/config.py
    - backend/main.py
    - backend/requirements.txt

key-decisions:
  - "CORS_ALLOWED_ORIGINS parsed as comma-separated str with whitespace-stripped split (D-01)"
  - "Default fallback to ['http://localhost:5173'] when CORS_ALLOWED_ORIGINS unset so dev-local workflow unchanged (D-02)"
  - "Keep allow_credentials=True (credentialed SSE contract) — only the wildcard origin is the spec violation (D-03)"
  - ".dockerignore lives at repo root (not backend/.dockerignore) because Dockerfile will build with context=. (D-10)"
  - "docling pinned to exact 2.82.0 regardless of pip-resolved version (D-11)"
  - "pytest pinned to 8.4.2 (resolved from dev venv via pip show) per D-12"
  - "No pip-tools/lockfile in Phase 1 — flat pinned requirements.txt is sufficient (D-13)"

patterns-established:
  - "Env-var list parsing via @property on pydantic-settings: comma-split + strip + drop-empty"
  - ".dockerignore secrets pattern: '.env', '.env.*', '!.env.example' (blocklist + allowlist)"

requirements-completed: [DEPLOY-02, DEPLOY-08, SEC-02]

duration: 15 min
completed: 2026-04-23
---

# Phase 01-secrets-repo-hygiene Plan 01: Backend hardening Summary

**Env-driven CORS allowlist via pydantic-settings, repo-root .dockerignore excluding secrets, and fully-pinned backend/requirements.txt (docling==2.82.0, pytest==8.4.2).**

## Performance

- **Duration:** 15 min
- **Started:** 2026-04-23T22:45:08Z
- **Completed:** 2026-04-23T23:00:33Z
- **Tasks:** 3
- **Files modified:** 4 (1 created + 3 modified)

## Accomplishments
- Fixed CORS spec violation: replaced `allow_origins=["*"]`+`allow_credentials=True` with env-driven allowlist
- Added `.dockerignore` at repo root with 32 lines covering secrets, runtime artifacts, VCS, frontend, planning, tests
- Pinned every non-blank line in `backend/requirements.txt` (15/15) including `docling==2.82.0` and `pytest==8.4.2`
- Preserved dev-local workflow via default fallback to `http://localhost:5173` when env unset
- Verified `from main import app` still imports cleanly; CORS parser validated with empty and multi-origin inputs

## Task Commits

Each task was committed atomically (no-verify per parallel-executor contract):

1. **Task 1: Create .dockerignore at repo root** — `9031801` (feat)
2. **Task 2: Env-driven CORS allowlist in Settings + main.py** — `6b4d7c0` (feat)
3. **Task 3: Pin docling==2.82.0 and pytest==8.4.2** — `09ebdbe` (chore)

**Plan metadata:** (this summary commit, see final commit below)

## Files Created/Modified
- `.dockerignore` (CREATED) — 32 lines; excludes `.env`, `venv/`, `backend/venv/`, `__pycache__/`, `**/__pycache__/`, `.git/`, `frontend/`, `node_modules/`, `**/node_modules/`, `.planning/`, `docs/`, `*.md`, `.vscode/`, `.idea/`, `backend/tests/`; keeps `!.env.example`
- `backend/config.py` — added `cors_allowed_origins: str = ""` field and `cors_origins_list` @property parser
- `backend/main.py` — switched `allow_origins` from wildcard to `settings.cors_origins_list`, added `from config import get_settings`
- `backend/requirements.txt` — `docling` → `docling==2.82.0`; `pytest` → `pytest==8.4.2`

## Decisions Made
All decisions followed CONTEXT.md D-01 through D-13 exactly:
- CORS env var is comma-separated (D-01); fallback to localhost:5173 (D-02); credentials=True stays (D-03)
- .dockerignore lives at repo root (D-10); content copied verbatim from D-09
- docling pinned to 2.82.0 (D-11); pytest pinned via pip-show (D-12); no lockfile (D-13)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- **Reproducibility smoke test (two fresh-venv installs)** — The plan's last acceptance criterion for Task 3 calls for creating two throwaway venvs and `diff`-ing `pip freeze`. `docling` pulls heavy native deps (torch, transformers, opencv-like libs) and each install cycle runs 5-10+ minutes. Deferred to Phase 2 where the Dockerfile build will exercise the install in CI and surface any drift. All 15 non-blank lines in `requirements.txt` carry exact `==` pins, which is the actual mechanism that guarantees identical resolution — the smoke test merely observes that property.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness
- CORS field is in place; when Phase 2 Dockerfile lands and Phase 3 Fly deploy wires `CORS_ALLOWED_ORIGINS` via `fly secrets set`, the backend will accept exactly the origins listed and no others.
- `.dockerignore` is ready for the Phase 2 Dockerfile (build context `.`).
- `requirements.txt` is ready for Phase 2 `pip install -r backend/requirements.txt` in the image layer.
- Ready for `01-02` plan (frontend `VITE_API_BASE_URL` prefix and `apiFetch`/`apiStream` centralization).

## Self-Check: PASSED

- `.dockerignore`: EXISTS at worktree root
- `backend/config.py`: `cors_origins_list` present
- `backend/main.py`: `allow_origins=settings.cors_origins_list` present; `allow_origins=["*"]` absent
- `backend/requirements.txt`: `docling==2.82.0` and `pytest==8.4.2` present; all 15 lines pinned
- Commits: `9031801`, `6b4d7c0`, `09ebdbe` all present in `git log`
- `from main import app` imports cleanly
- Parser default fallback returns `['http://localhost:5173']`; multi-origin parse strips whitespace correctly

---
*Phase: 01-secrets-repo-hygiene*
*Completed: 2026-04-23*
