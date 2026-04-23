# Phase 1: Secrets & Repo Hygiene - Context

**Gathered:** 2026-04-23
**Status:** Ready for planning

<domain>
## Phase Boundary

Land the code-level safety rails needed before any container build or public deploy: env-driven CORS allowlist (replacing the spec-invalid `["*"]` + `credentials=True` combo), a `.dockerignore` that keeps secrets and bloat out of the backend image, `docling` + other unpinned deps pinned to the currently-installed versions for reproducible builds, and a `VITE_API_BASE_URL` prefix applied uniformly so the same frontend code works with the Vite dev proxy locally and an absolute Fly URL in prod. A production Vite build grepped for backend secrets must return zero matches.

Out of scope for Phase 1 (deferred to later phases):
- Sentry DSN field in config (Phase 7)
- Rate-limit config fields (Phase 6)
- `environment` flag (Phase 4, when first needed to distinguish dev/prod)
- Any runtime changes that require Docker, Fly, or Supabase prod
- Max-iterations cap on chat tool loop (Phase 6)

</domain>

<decisions>
## Implementation Decisions

### CORS Allowlist
- **D-01:** `CORS_ALLOWED_ORIGINS` is a comma-separated string env var (e.g. `https://app.pages.dev,http://localhost:5173`). Parsed in `backend/config.py` via a pydantic-settings field plus a split-and-strip validator producing `list[str]`. Simpler than JSON and survives `flyctl secrets set` quoting cleanly.
- **D-02:** When `CORS_ALLOWED_ORIGINS` is unset (dev-local), `Settings` falls back to `["http://localhost:5173"]` so local workflow is unchanged and no `.env` edit is required to keep dev running.
- **D-03:** `backend/main.py` CORSMiddleware reads the parsed list from settings. `allow_credentials=True` stays; `allow_origins=["*"]` is removed. `allow_methods` and `allow_headers` can remain `["*"]` (they do not trigger the same spec issue).
- **D-04:** No `allow_origin_regex` for CF Pages previews in Phase 1. If preview-URL CORS is needed later, revisit in Phase 5 or 6 once the CF Pages project exists and the preview URL pattern is known.

### Frontend API Base URL
- **D-05:** Centralize all HTTP calls through `apiFetch()` in `frontend/src/lib/api.ts`. The 15+ direct `fetch('/api/...')` call sites across `useChat.ts`, `useDocuments.ts`, `useFolderTree.ts`, `ChatPage.tsx` migrate to `apiFetch`. Rationale: single place to apply the base URL prefix and token header.
- **D-06:** `apiFetch` gains a streaming-aware mode (or a companion `apiStream` helper) so `useChat.ts` — which reads the response body with `reader.read()` for SSE chunks — can share the base URL prefix without losing the raw `Response`. Current `apiFetch` always calls `.json()` which would break streaming; planner to decide exact shape (overload flag, second helper, or return `Response` for a specific option).
- **D-07:** `VITE_API_BASE_URL` defaults to empty string when unset. Prefixing `${VITE_API_BASE_URL ?? ''}` on a path like `/api/threads` resolves to same-origin in dev (Vite proxy kicks in at `vite.config.ts`) and to absolute Fly URL in prod. Zero dev workflow change.
- **D-08:** `VITE_API_BASE_URL`, when set for prod, is a full origin with no trailing slash (e.g. `https://boardgame-rag-api.fly.dev`). Paths keep the `/api/...` prefix they already have.

### .dockerignore Scope
- **D-09:** Aggressive `.dockerignore` at repo root. Minimum excludes: `.env`, `.env.*`, `!.env.example` (keep the example if one is added later), `venv/`, `backend/venv/`, `__pycache__/`, `**/__pycache__/`, `*.pyc`, `.git/`, `.gitignore`, `frontend/` (backend image does not need it), `.planning/`, `backend/tests/`, `docs/`, `*.md` (except README if the backend image needs it — it doesn't, so exclude), `.vscode/`, `.idea/`, `node_modules/`, `**/node_modules/`, `.pytest_cache/`, `.mypy_cache/`.
- **D-10:** Keep `.dockerignore` at repo root (not `backend/.dockerignore`) because the eventual Dockerfile will be at repo root with build context `.` — this keeps `COPY backend/ ...` possible while excluding the rest.

### Docling + Dep Pinning
- **D-11:** `docling` pinned to exact version `2.82.0` in `backend/requirements.txt` — matches the currently-installed version on the dev machine, so no surprise upgrades in Docker build.
- **D-12:** Audit all other unpinned deps in `backend/requirements.txt` and pin each to the currently-installed version via `pip freeze` reference. Commit as part of this phase. Includes any transitive deps that are already pinned loosely.
- **D-13:** No introduction of `pip-tools`, `pip-compile`, or a `requirements.lock` file in Phase 1. Flat pinned `requirements.txt` is enough for reproducibility here; lockfile tooling can be a future improvement if the plain list shows drift.

### Claude's Discretion
- Exact shape of the streaming-aware fetch helper (D-06) — planner picks between overload, companion function, or returning `Response` on a flag. Must preserve type safety and keep call-site readability.
- Specific set of currently-unpinned deps to pin (D-12) — planner/executor reads `backend/requirements.txt` + `pip show`/`pip freeze` output and produces the pinned list. Not every pin needs to be discussed individually.
- Exact wording of `.env.example` (or whether to add one at all) — not required for the phase's success criteria, but a nice-to-have documentation artifact if the planner finds it easy to slip in.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase contract
- `.planning/ROADMAP.md` §Phase 1 — Success criteria (5 items) that verification will check
- `.planning/REQUIREMENTS.md` — DEPLOY-02, DEPLOY-06, DEPLOY-08, SEC-02, SEC-07 definitions

### Research
- `.planning/research/SUMMARY.md` — Executive summary with phase rationale
- `.planning/research/ARCHITECTURE.md` — Integration points, especially CORS allowlist pattern and `VITE_API_BASE_URL` behavior
- `.planning/research/PITFALLS.md` — Pitfalls 1 (CORS spec-invalid), 2 (`.env` leak), 3 (Docling unpinned + apt list) that this phase addresses
- `.planning/research/STACK.md` — Docker base + CF Pages context (informs `.dockerignore` choices; actual Dockerfile is Phase 2)

### Source files to modify
- `backend/main.py` — Replace CORSMiddleware config with env-driven list
- `backend/config.py` — Add `cors_allowed_origins: str = ""` field + `@property` parser to list[str] with dev fallback
- `backend/requirements.txt` — Pin `docling==2.82.0` + audit and pin all other unpinned deps
- `frontend/src/lib/api.ts` — Add base URL prefix; extend for streaming support
- `frontend/src/lib/supabase.ts` — (Inspect to confirm no changes needed; anon key already reads from `VITE_` env)
- `frontend/src/hooks/useChat.ts` — Migrate `fetch('/api/...')` calls to `apiFetch` or `apiStream`
- `frontend/src/hooks/useDocuments.ts` — Migrate all `fetch('/api/...')` to `apiFetch`
- `frontend/src/hooks/useFolderTree.ts` — Migrate all `fetch('/api/...')` to `apiFetch`
- `frontend/src/pages/ChatPage.tsx` — Already uses `apiFetch`; verify coverage
- `frontend/vite.config.ts` — Verify existing proxy behavior remains intact with empty-string base URL default

### Source files to CREATE
- `.dockerignore` at repo root (see D-09 for scope)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `apiFetch` in `frontend/src/lib/api.ts` — existing helper; attaches Supabase bearer token; all non-streaming calls should migrate here
- `Settings` in `backend/config.py` — pydantic-settings BaseSettings; new fields land here as additional class attrs; existing `@property` pattern (e.g. `supabase_url_resolved`) is the model for the parsed CORS list
- Existing `/api/health` endpoint in `backend/main.py` — not modified this phase but referenced by Phase 4 + 7; confirms the `/api/` path convention

### Established Patterns
- pydantic-settings `BaseSettings` reads env vars automatically; new `cors_allowed_origins` field will Just Work without new dotenv plumbing
- Frontend env vars use `VITE_` prefix (seen on `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`); `VITE_API_BASE_URL` follows the same convention
- `backend/main.py` is the single CORS config site — no duplication across routers
- Vite config (not inspected but per CLAUDE.md) proxies `/api/*` → `localhost:8000` in dev; empty-string base URL leaves that flow untouched

### Integration Points
- `backend/config.py` → consumed by `get_settings()` everywhere in the backend; adding a field is additive and safe
- `backend/main.py` CORSMiddleware → the *only* change to runtime behavior in Phase 1
- `frontend/src/lib/api.ts` → `apiFetch` is imported by pages and hooks; changing its internal URL resolution propagates to all callers
- `frontend/src/hooks/useChat.ts` streaming → cannot use current `apiFetch` because `.json()` is eager; requires the streaming-aware variant decided in planning

### Gotchas surfaced during scout
- `backend/main.py:12-13` has the live CORS bug (spec-invalid combo) — do NOT leave `allow_credentials=True` paired with `allow_origins=["*"]`
- `backend/config.py:7` calls `load_dotenv()` unconditionally from repo root — harmless in container when `.env` does not exist, leave as-is for Phase 1 (revisit in Phase 4 if we want explicit prod/dev split)
- 15+ direct `fetch()` calls outside `apiFetch` — scope of the D-05 migration is larger than it first appeared

</code_context>

<specifics>
## Specific Ideas

- User confirmed the Phase 1 goal is pure code hygiene — no Docker, Fly, or Supabase prod work this phase; those are 2/3/4.
- User preferred recommended defaults on every gray area, suggesting low appetite for re-litigating downstream.
- User explicitly widened scope on Docling pinning: audit and pin *all* currently-unpinned deps, not only docling (D-12). This is a point of emphasis — planner must not narrow back to docling-only.

</specifics>

<deferred>
## Deferred Ideas

- `pip-tools` / `requirements.lock` — deferred indefinitely; flat pinned `requirements.txt` suffices for portfolio scope
- `allow_origin_regex` for CF Pages preview URLs — deferred to Phase 5 or 6 once CF Pages preview URL pattern is known
- `.env.example` file — optional, Claude's discretion; if skipped, not a phase failure
- `environment` flag (`dev`/`prod`) in `Settings` — deferred to Phase 4 when first needed for Fly secrets handling
- Sentry DSN field in `Settings` — deferred to Phase 7 (Observability)
- Rate-limit config fields — deferred to Phase 6 (Prod Wiring)

</deferred>

---

*Phase: 01-secrets-repo-hygiene*
*Context gathered: 2026-04-23*
