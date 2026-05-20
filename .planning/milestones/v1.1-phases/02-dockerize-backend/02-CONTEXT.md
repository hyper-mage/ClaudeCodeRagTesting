# Phase 2: Dockerize Backend - Context

**Gathered:** 2026-04-23
**Status:** Ready for planning

<domain>
## Phase Boundary

Produce a reproducible backend container image — repo-root `Dockerfile` based on `python:3.11-slim-bookworm` with required apt packages (`poppler-utils`, `tesseract-ocr`, `libglib2.0-0`, `fonts-dejavu-core`), CPU-only torch, pinned `backend/requirements.txt`, Docling model cache preloaded — that boots FastAPI, serves `/api/health`, and ingests real PDF + DOCX fixtures successfully when run locally via `docker run --env-file .env -p 8000:8000 <image>`. Plus a committed smoke-test script that builds the image, boots it, runs the end-to-end ingest check, and verifies image size against a 6GB target / 7.5GB warn threshold.

Out of scope for Phase 2 (deferred to later phases):
- `fly.toml`, any `flyctl` invocation, or actual Fly deploy (Phase 4)
- Prod Supabase project wiring — smoke test runs against dev Supabase (Phase 3)
- CORS origin allowlist entries for Cloudflare Pages preview URLs (Phase 5/6)
- Rate limiting, cost caps, observability (Phases 6/7)
- Multi-arch builds (no current target platform beyond x86_64 Fly VM)
- `pip-tools` / `requirements.lock` (deferred indefinitely in Phase 1)

</domain>

<decisions>
## Implementation Decisions

### Build Strategy + Image Size
- **D-01:** Single-stage Dockerfile at repo root, `FROM python:3.11-slim-bookworm`. Simpler to read + debug. Accept ~2-3GB image for Docling + torch + preloaded models.
- **D-02:** Escalation path — if `docker image inspect` reports size > 6GB target, refactor to multi-stage in a follow-up plan. Do not pre-optimize.
- **D-03:** Image size target: **< 6GB** (Fly free-tier rootfs is 8GB). Smoke-test script WARNs between 6GB and 7.5GB, FAILs > 7.5GB.
- **D-04:** CPU-only torch installed via `pip install -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cpu`. Matches Docling docs pattern. Keeps PyPI as primary index for every other dep.
- **D-05:** Layer order is apt → requirements.txt → app code, so code edits do not invalidate the pip install layer. `COPY backend/requirements.txt .` precedes `COPY backend/ ./`.

### Docling Model Preload
- **D-06:** Preload Docling default models (layout + OCR) at build time via a `RUN python -c "..."` step that instantiates `DocumentConverter` and converts a tiny dummy PDF. Models bake into image. Slower build; fast cold-start in prod; deterministic image size.
- **D-07:** Use Docling's default cache path (`~/.cache/docling` under the runtime user's HOME). No custom `DOCLING_CACHE_DIR` env var. Matches upstream docs.

### Runtime User + Process
- **D-08:** Run as non-root `appuser` UID 1000 (`RUN useradd -m -u 1000 appuser`). `chown -R appuser:appuser /app` after COPY. `USER appuser` before CMD. Docling cache lands in `/home/appuser/.cache/docling` automatically.
- **D-09:** Exec-form `CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]`. Native PID 1 signal handling. Port fixed at 8000; Fly's `[http_service] internal_port=8000` maps external to this in Phase 4 — no `$PORT` expansion needed.
- **D-10:** `WORKDIR /app` + `COPY backend/ ./` (NOT `./backend/`). App files land at `/app` root so imports work as `from routers import ...`, matching `backend/main.py`'s existing layout and dev-local `uvicorn main:app` invocation.

### Smoke Test
- **D-11:** Commit `backend/scripts/docker_smoke.sh` (or `.py`) that: builds the image, boots the container with `--env-file .env`, polls `/api/health` until 200, uploads a real PDF + DOCX from `backend/tests/fixtures/`, asserts HTTP 200 + chunk count > 0, runs `docker image inspect` with the 6GB/7.5GB thresholds, tears down container. Reusable in Phase 4 pre-deploy + regression testing.
- **D-12:** Fixture strategy: **first scan `backend/tests/` for existing reusable PDF/DOCX fixtures**. If any exist, use them. If none, planner/executor generates two minimal fixtures (1-page hello-world PDF via ReportLab or similar, 1-page DOCX via python-docx) ≤ 50KB each, committed under `backend/tests/fixtures/`.
- **D-13:** Smoke test authenticates with **existing test credentials** from CLAUDE.md (`ragtest1@gmail.com` / `testpass123`). Script exchanges creds for a Supabase JWT via the Supabase auth endpoint, attaches `Authorization: Bearer <jwt>` to the upload request. Exercises full auth middleware. No dev-only bypass endpoint.
- **D-14:** Image size check uses `docker image inspect <tag> --format '{{.Size}}'` and compares in script against D-03 thresholds. Machine-checkable, matches ROADMAP success criterion 4.

### Claude's Discretion
- Exact Dockerfile comments + section structure (D-01/D-05)
- Language of the smoke-test script (bash vs python) — bash is simpler if the auth/JWT exchange is short; python is better if Supabase client usage keeps it readable
- Whether to add a tiny wrapper `Makefile` target (e.g., `make docker-smoke`) alongside the script — nice-to-have, not required
- Whether to add `ENV PYTHONUNBUFFERED=1` and `ENV OMP_NUM_THREADS=4` (recommended by Docling docs for CPU inference) — planner may include unless it complicates layering
- Exact failure messages / exit codes in the smoke-test script

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase contract
- `.planning/ROADMAP.md` §Phase 2: Dockerize Backend — 4 success criteria (base image + apt deps, `docker run` + health 200, PDF/DOCX ingest without native-dep failures, image size within Fly rootfs limits)
- `.planning/REQUIREMENTS.md` — DEPLOY-01 ("Developer can build a backend container image locally that boots FastAPI + Docling, passes `/api/health`, and handles PDF/DOCX ingest without missing native deps")

### Research
- `.planning/research/STACK.md` §"Reference Dockerfile Pattern" — base image, apt deps, CPU torch extra-index-url, ENV vars (`PYTHONUNBUFFERED`, `OMP_NUM_THREADS`), WORKDIR /app, CMD pattern. **Note:** ROADMAP's apt list (poppler-utils, tesseract-ocr, libglib2.0-0, fonts-dejavu-core) is authoritative and broader than STACK.md's original (`libgl1 libglib2.0-0`) — planner must use ROADMAP list.
- `.planning/research/PITFALLS.md` — Pitfall 3 (Docling native deps on slim images) is the exact failure mode this phase exists to prevent

### Upstream docs
- https://deepwiki.com/docling-project/docling/10.1-docker-deployment — Docling's official Docker guidance
- https://docling-project.github.io/docling/getting_started/installation/ — Python version matrix + CPU torch flag

### Phase 1 dependencies (carried forward, do not re-plan)
- `.planning/phases/01-secrets-repo-hygiene/01-CONTEXT.md` §`.dockerignore Scope` (D-09/D-10) — `.dockerignore` already at repo root, excludes `.env*`, `venv/`, `__pycache__/`, `.git/`, `frontend/`, `.planning/`, `backend/tests/` (note: tests excluded — but smoke-test fixtures under `backend/tests/fixtures/` must still be available to the smoke script, which runs OUTSIDE the image; no conflict)
- `.planning/phases/01-secrets-repo-hygiene/01-01-SUMMARY.md` — confirms `requirements.txt` has `docling==2.82.0` + pins on every line
- `.planning/phases/01-secrets-repo-hygiene/01-02-SUMMARY.md` — confirms frontend `apiFetch`/`apiStream` centralization (relevant for Phase 4's `VITE_API_BASE_URL` wiring, not this phase)

### Source files to CREATE
- `Dockerfile` at repo root
- `backend/scripts/docker_smoke.sh` or `.py`
- `backend/tests/fixtures/*.pdf` + `*.docx` (only if existing fixtures absent after scan)

### Source files to REFERENCE (but NOT modify this phase)
- `backend/main.py` — boot target `main:app`; `/api/health` endpoint confirmed at line 28
- `backend/config.py` — pydantic-settings env var loading (validates config on import; no explicit container-side env validation needed)
- `backend/requirements.txt` — all deps pinned in Phase 1; torch is NOT in the file yet and will be resolved transitively from docling's dep graph via `--extra-index-url`
- `.dockerignore` — created in Phase 1; planner must verify `backend/tests/fixtures/` is reachable from the build context (the current rule excludes `backend/tests/` entirely — if fixtures need to ship in the image for in-container use, revise; but current plan keeps fixtures OUT of image and uses them FROM the host via docker cp or HTTP upload, so no change needed)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend/main.py:13-19` — FastAPI app already bound to `0.0.0.0:8000` convention; CORSMiddleware reads `settings.cors_origins_list` (Phase 1 env-driven). Container CMD targets this module directly.
- `backend/config.py` — `get_settings()` + pydantic-settings `Settings` class reads env vars on import. Container failure to boot when required envs missing is already surfaced by this (no custom entrypoint validation required).
- `backend/scripts/` — existing scripts directory (per root listing); natural home for `docker_smoke` script alongside any existing ops scripts.
- `backend/tests/` — pytest suite exists (`pytest==8.4.2` pinned). Fixtures directory may already exist — planner must scan first.

### Established Patterns
- Dev invocation: `uvicorn main:app` run from `backend/` cwd (per CLAUDE.md + current main.py imports like `from routers import ...`). Container mirrors this by setting `WORKDIR /app` and copying `backend/` contents INTO `/app` (not into `/app/backend`). Preserves import paths across dev and container.
- All backend env vars loaded by `pydantic-settings` — no manual `os.environ` scatter. Setting `--env-file .env` on `docker run` Just Works.
- Test creds in CLAUDE.md (`ragtest1@gmail.com` / `testpass123`) are the de-facto dev auth path — reused by smoke test.

### Integration Points
- `.dockerignore` at repo root (from Phase 1) defines build context filter. Current `backend/tests/` exclusion means test code + fixtures do NOT ship in image. Smoke script operates from the host side (uploads fixtures via HTTP), so this is fine. If future need arises to run pytest *inside* image, .dockerignore rule will need revision — not this phase.
- Phase 4 will consume this image unchanged and deploy to Fly. No Fly-specific config in the Dockerfile itself (CMD uses fixed port 8000; Fly `internal_port` mapping handles external ingress).

### Gotchas surfaced during scout
- ROADMAP success criterion 1 lists `poppler-utils`, `tesseract-ocr`, `libglib2.0-0`, `fonts-dejavu-core` — STACK.md Reference Dockerfile only had `libgl1 libglib2.0-0`. Follow ROADMAP — it's the broader, verified list.
- `docling==2.82.0` pulls `torch` as transitive dep. Without `--extra-index-url https://download.pytorch.org/whl/cpu`, pip resolves the default (CUDA) wheel — adds ~3GB of NVIDIA libs, will likely blow past 8GB Fly rootfs. Must use CPU wheel.
- `backend/tests/` is excluded by `.dockerignore`. Smoke-test fixtures placed under `backend/tests/fixtures/` are therefore NOT shipped in the image, and ARE available on the host-side smoke script. Both are correct for this plan; no `.dockerignore` edit needed.
- `/app` is owned by root before `chown`. Docling model preload step must run AFTER `USER appuser` so the cache writes to the non-root home dir — not to a `/root/.cache` orphan that root would own but appuser cannot read.

</code_context>

<specifics>
## Specific Ideas

- User picked the "start single-stage, escalate if needed" middle path over either extreme — wants simplicity first, measured optimization later if needed.
- User picked all recommended defaults on preload (Docling defaults, default cache path), user strategy (non-root), smoke-test (dedicated script, existing fixtures first, existing test creds, inspect+threshold). Low appetite for bespoke solutions; stay close to upstream Docling + Docker norms.
- User explicitly corrected scope: migrations NOT run from container (Supabase external). Confirms entrypoint script has no job to do — direct CMD is right.

</specifics>

<deferred>
## Deferred Ideas

- Multi-stage Dockerfile refactor — only if D-02 escalation triggers
- Dev-only smoke endpoint bypassing auth — rejected; test creds used instead
- Multi-arch build (linux/arm64) — no target need; Fly VMs are x86_64
- Testcontainers + pytest docker integration marker — deferred indefinitely; shell script is enough for a portfolio build
- `pip-tools` / `requirements.lock` — deferred from Phase 1, still deferred
- `DOCLING_CACHE_DIR` env var with explicit cache path — use default for now; revisit only if image-inspection requires predictable path
- `Makefile` wrapper (`make docker-smoke`) — Claude's discretion during planning
- Migration orchestration — explicitly out of scope; Phase 3 handles via Supabase dashboard / `supabase db push`

</deferred>

---

*Phase: 02-dockerize-backend*
*Context gathered: 2026-04-23*
