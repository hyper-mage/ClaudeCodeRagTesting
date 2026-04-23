# Phase 1: Secrets & Repo Hygiene - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-23
**Phase:** 01-secrets-repo-hygiene
**Areas discussed:** CORS allowlist format, API base URL migration, .dockerignore scope, Docling pin strategy

---

## CORS allowlist format

### Q1: Format and parsing

| Option | Description | Selected |
|--------|-------------|----------|
| Comma-separated string (Recommended) | `CORS_ALLOWED_ORIGINS=https://app.pages.dev,http://localhost:5173` — simple pydantic-settings native, easy to set via flyctl secrets | ✓ |
| JSON list | `CORS_ALLOWED_ORIGINS=["https://app.pages.dev","http://localhost:5173"]` — stricter but quoting is brittle in shell/flyctl | |
| Regex allowlist | Use FastAPI CORSMiddleware `allow_origin_regex` to also match CF Pages preview URLs | |

**User's choice:** Comma-separated string
**Notes:** Preserves shell-friendly quoting for flyctl secrets.

### Q2: Dev fallback

| Option | Description | Selected |
|--------|-------------|----------|
| Default to localhost:5173 (Recommended) | Fall back to `["http://localhost:5173"]` when env unset — keeps dev workflow identical | ✓ |
| Fail fast | Raise on boot if `CORS_ALLOWED_ORIGINS` missing — forces explicit config everywhere | |
| Empty list | Safest prod default but breaks local dev unless `.env` is set | |

**User's choice:** Default to localhost:5173
**Notes:** Dev ergonomics prioritized over strict prod-parity.

---

## API base URL migration

### Q1: Migration pattern

| Option | Description | Selected |
|--------|-------------|----------|
| Centralize via apiFetch (Recommended) | Migrate all hooks (useChat, useDocuments, useFolderTree) to use `apiFetch` helper. Single prefix point | ✓ |
| Shared API_BASE const imported everywhere | Export `API_BASE` from `lib/api.ts`, prefix each fetch call inline. Smaller diff | |
| Keep apiFetch for non-streaming, const for streaming | Split approach: apiFetch wraps JSON calls, API_BASE const for streaming | |

**User's choice:** Centralize via apiFetch
**Notes:** `useChat` streaming forces planner to design a streaming-aware variant (apiStream or mode flag) so `apiFetch` stays the single resolution point.

### Q2: Default value

| Option | Description | Selected |
|--------|-------------|----------|
| Empty string (Recommended) | Prefix becomes empty — fetch resolves same-origin, Vite proxy kicks in | ✓ |
| http://localhost:8000 explicit | Direct call, no proxy. Breaks existing Vite proxy setup | |

**User's choice:** Empty string
**Notes:** Zero dev workflow change.

---

## .dockerignore scope

### Q1: Scope

| Option | Description | Selected |
|--------|-------------|----------|
| Aggressive (Recommended) | Exclude .env*, venv/, __pycache__/, .git/, frontend/, .planning/, backend/tests/, *.md, docs/ | ✓ |
| Minimal | Only .env*, venv/, node_modules/, .git/ | |
| Custom list now | User specifies exact set | |

**User's choice:** Aggressive
**Notes:** Smallest image, zero secret risk prioritized.

---

## Docling pin strategy

### Q1: Pin scope for docling

| Option | Description | Selected |
|--------|-------------|----------|
| Pin to 2.82.0 exact (Recommended) | `docling==2.82.0` — matches what's already running locally | ✓ |
| Pin compatible (~=2.82.0) | Allows patch upgrades | |
| Latest stable + full lockfile | Upgrade + generate pip-compile lockfile | |

**User's choice:** Pin to 2.82.0 exact
**Notes:** Reproducibility over forward compatibility. Local env confirmed at 2.82.0 via `pip show docling`.

### Q2: Other unpinned deps

| Option | Description | Selected |
|--------|-------------|----------|
| Docling-only for this phase (Recommended) | Phase 1 pins docling; other unpinned deps stay as-is | |
| Audit + pin all unpinned | Full requirements.txt lockdown, pin everything to installed versions | ✓ |

**User's choice:** Audit + pin all unpinned
**Notes:** User widened scope beyond recommendation — planner must pin all currently-unpinned deps via `pip freeze` reference.

---

## Claude's Discretion

- Exact shape of streaming-aware fetch helper (overload flag, second helper, or Response-returning variant) — D-06
- Specific set of deps to pin in requirements.txt — D-12
- Whether to add an `.env.example` file — not required for success criteria

## Deferred Ideas

- `pip-tools` / `requirements.lock` — deferred indefinitely
- `allow_origin_regex` for CF Pages preview URLs — deferred to Phase 5/6
- `environment` flag in Settings — deferred to Phase 4
- Sentry DSN field in Settings — deferred to Phase 7
- Rate-limit config fields — deferred to Phase 6
