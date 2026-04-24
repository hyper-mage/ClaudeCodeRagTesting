# Phase 2: Dockerize Backend - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-23
**Phase:** 02-dockerize-backend
**Areas discussed:** Build strategy, Docling model preload, Runtime user + permissions, Local smoke-test approach

---

## Gray Area Selection

| Option | Description | Selected |
|--------|-------------|----------|
| Build strategy (single vs multi-stage) | Single-stage simpler; multi-stage can slim image | ✓ |
| Docling model preload | Preload at build vs lazy on first request | ✓ |
| Runtime user + permissions | Non-root vs root in container | ✓ |
| Local smoke-test approach | Script vs manual vs pytest integration | ✓ |

User selected all 4.

---

## Build Strategy

### Q1: Single-stage vs multi-stage Dockerfile?

| Option | Description | Selected |
|--------|-------------|----------|
| Single-stage | Simpler, accept ~2-3GB image, fits Fly 8GB rootfs | |
| Multi-stage | Builder + runtime, slims image, more complex | |
| Start single-stage, escalate if needed | Ship single-stage; refactor later if size exceeds budget | ✓ |

**User's choice:** Start single-stage, escalate if needed.

### Q2: Image size target?

| Option | Description | Selected |
|--------|-------------|----------|
| <4GB target, warn at 6GB | Half Fly rootfs; strict | |
| <6GB target, warn at 7.5GB | More tolerant; closer to Docling baseline | ✓ |
| No hard target, just under 8GB | Only hard cap is rootfs limit | |

**User's choice:** <6GB target, warn at 7.5GB.

### Q3: Torch CPU wheel install?

| Option | Description | Selected |
|--------|-------------|----------|
| `--extra-index-url` (Recommended) | Docling docs pattern | ✓ |
| Separate torch line with `--index-url` | Two RUN layers | |
| Pin torch CPU in requirements.txt | Explicit pin with extra-index at top | |

**User's choice:** `--extra-index-url`.

### Q4: Layer ordering?

| Option | Description | Selected |
|--------|-------------|----------|
| apt → requirements.txt → app code (Recommended) | Standard cache-friendly pattern | ✓ |
| Combined apt+pip+code | Simpler but bad for cache | |

**User's choice:** apt → requirements.txt → app code.

---

## Docling Model Preload

### Q1: Preload at build or lazy load?

| Option | Description | Selected |
|--------|-------------|----------|
| Preload at build (Recommended) | Models baked in; slow build, fast runtime | ✓ |
| Lazy load on first request | Smaller image; cold-start penalty | |
| Preload layout only; lazy OCR | Middle ground | |

**User's choice:** Preload at build.

### Q2: Which models to preload?

| Option | Description | Selected |
|--------|-------------|----------|
| Docling defaults (layout + OCR) (Recommended) | Matches prod runtime exactly | ✓ |
| Minimal: layout only | Save ~500MB; cold OCR on first image | |
| Everything Docling can cache | Max size; unclear usage | |

**User's choice:** Docling defaults.

### Q3: Model cache location?

| Option | Description | Selected |
|--------|-------------|----------|
| Default Docling path (~/.cache/docling) (Recommended) | Standard; upstream-assumed | ✓ |
| Explicit `/opt/docling-cache` via env var | More predictable for debugging | |

**User's choice:** Default path.

---

## Runtime User + Permissions

### Q1: Runtime user strategy?

| Option | Description | Selected |
|--------|-------------|----------|
| Non-root `appuser` UID 1000 (Recommended) | Standard sec; compatible with Fly | ✓ |
| Root | Simpler; anti-pattern for prod | |
| Non-root with explicit HOME + chown belt-and-suspenders | Extra safety | |

**User's choice:** Non-root `appuser` UID 1000.

### User clarification

> "is there any reason to rerun migrations after this build?"

Answer provided: No. Supabase hosts Postgres externally; migrations run from Supabase dashboard / `supabase db push` in Phase 3. Backend container never touches schema. Entrypoint script rationale ("run migrations") doesn't apply. Env validation already handled by pydantic-settings on import.

### Q2: CMD: direct uvicorn or entrypoint script? (reformulated)

| Option | Description | Selected |
|--------|-------------|----------|
| Direct uvicorn CMD (Recommended) | Exec-form, native signal handling, simplest | ✓ |
| Honor $PORT via shell-form CMD | Fly $PORT expansion; loses exec semantics | |
| Direct uvicorn + Fly internal_port override | Hardcoded 8000; Fly maps external | |

**User's choice:** Direct uvicorn CMD.

### Q3: WORKDIR and COPY layout?

| Option | Description | Selected |
|--------|-------------|----------|
| WORKDIR /app, COPY backend/ ./ (Recommended) | Imports match dev; `uvicorn main:app` | ✓ |
| WORKDIR /app, COPY backend/ ./backend/ | Preserves prefix; `uvicorn backend.main:app` | |

**User's choice:** WORKDIR /app, COPY backend/ ./.

---

## Local Smoke-Test Approach

### Q1: Verify PDF + DOCX ingest how?

| Option | Description | Selected |
|--------|-------------|----------|
| Dedicated script + fixtures (Recommended) | Committed, repeatable, reusable | ✓ |
| Manual curl commands in SUMMARY | Lightest; not repeatable | |
| Pytest + testcontainers | Heavier; nice for CI later | |

**User's choice:** Dedicated script + fixtures.

### Q2: Fixtures?

| Option | Description | Selected |
|--------|-------------|----------|
| Check existing fixtures first (Recommended) | Scan `backend/tests/`; reuse if present | ✓ |
| Generate minimal fixtures fresh | ReportLab PDF + python-docx DOCX | |
| Public sample (e.g., Catan excerpt) | Domain content; license care | |

**User's choice:** Check existing first, generate if absent.

### Q3: Smoke-test auth?

| Option | Description | Selected |
|--------|-------------|----------|
| Existing test creds (Recommended) | `ragtest1@gmail.com` / `testpass123`; exercises middleware | ✓ |
| Dev-only smoke endpoint with auth bypass | Faster; prod-risk endpoint | |
| Script assumes `SMOKE_TEST_JWT` env | Thinnest; caller handles creds | |

**User's choice:** Existing test creds.

### Q4: Image size verification?

| Option | Description | Selected |
|--------|-------------|----------|
| `docker image inspect` + threshold in script (Recommended) | Machine-checkable; matches success criterion 4 | ✓ |
| Manual visual check | Documented in SUMMARY; not enforced | |

**User's choice:** `docker image inspect` + threshold.

---

## Done Check

**User's choice:** Ready for context.

---

## Claude's Discretion

- Exact Dockerfile comments/section structure
- Bash vs Python for smoke-test script
- Whether to add a `Makefile` wrapper target
- Whether to include `ENV PYTHONUNBUFFERED=1` + `ENV OMP_NUM_THREADS=4`
- Exact exit codes + failure messages in smoke-test script

## Deferred Ideas

- Multi-stage refactor — only on escalation trigger (D-02)
- Testcontainers/pytest-docker integration
- Multi-arch build
- `pip-tools` / `requirements.lock`
- `DOCLING_CACHE_DIR` explicit path
- Makefile wrapper
- Dev-only auth-bypass smoke endpoint (rejected)
