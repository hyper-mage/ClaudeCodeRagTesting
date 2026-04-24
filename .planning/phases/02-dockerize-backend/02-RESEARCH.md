# Phase 2: Dockerize Backend — Research

**Researched:** 2026-04-24
**Domain:** Reproducible FastAPI + Docling backend container (python:3.11-slim-bookworm, CPU-only torch, apt native deps, local smoke test)
**Confidence:** HIGH

## Summary

Every consequential decision for this phase is already locked in `02-CONTEXT.md`. Research purpose here is to (a) verify those decisions against upstream Docling + Docker ecosystem sources, (b) surface one upstream pattern the planner should adopt literally (`docling-tools models download`), (c) document the apt-list discrepancy between Docling's official Dockerfile and ROADMAP's broader list, and (d) lock in a repeatable smoke-test recipe.

Findings:
- Docling's official upstream Dockerfile uses `libgl1 libglib2.0-0` — narrower than ROADMAP's list. ROADMAP wins (D-03 apt list is authoritative; the extras catch real failure modes the minimal set misses).
- `docling-tools models download` is the **canonical** preload command — use it instead of a hand-rolled `python -c "..."` script (D-06 was directionally right; refine to the CLI form).
- CPU-only torch via `--extra-index-url https://download.pytorch.org/whl/cpu` is required because `docling-ibm-models` pulls `torch>=2.2.2` transitively; without it, pip resolves CUDA wheels (~3GB NVIDIA libs baked into image).
- Fly.io free tier has changed in 2026 — no meaningful free tier for new orgs; stopped-machine rootfs is now billed at $0.15/GB/month. Size discipline (D-03: <6GB target) still matters, but for cost control rather than a hard 8GB ceiling.
- `HEALTHCHECK` needs curl/wget in the image; slim-bookworm has neither by default. Planner should add a tiny inline Python check (`python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health').status == 200"`) rather than apt-install curl just for the HC — matches minimal-slim ethos.

**Primary recommendation:** Follow upstream Docling's Dockerfile pattern as the structural template, but apply our ROADMAP-locked apt list, our non-root `appuser`, our `WORKDIR /app + COPY backend/ ./` layout, and our default `~/.cache/docling` path. Use `docling-tools models download` for preload. Keep the smoke test as a committed bash script under `backend/scripts/docker_smoke.sh`.

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Build Strategy + Image Size**
- **D-01:** Single-stage Dockerfile at repo root, `FROM python:3.11-slim-bookworm`. Simpler to read + debug. Accept ~2–3GB image for Docling + torch + preloaded models.
- **D-02:** Escalation path — if `docker image inspect` reports size > 6GB target, refactor to multi-stage in a follow-up plan. Do not pre-optimize.
- **D-03:** Image size target: **< 6GB** (Fly free-tier rootfs historically 8GB). Smoke-test script WARNs between 6GB and 7.5GB, FAILs > 7.5GB.
- **D-04:** CPU-only torch installed via `pip install -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cpu`.
- **D-05:** Layer order is apt → requirements.txt → app code. `COPY backend/requirements.txt .` precedes `COPY backend/ ./`.

**Docling Model Preload**
- **D-06:** Preload Docling default models at build time (models bake into image).
- **D-07:** Use Docling's default cache path (`~/.cache/docling` under runtime user's HOME). No custom `DOCLING_CACHE_DIR` env var.

**Runtime User + Process**
- **D-08:** Run as non-root `appuser` UID 1000. `RUN useradd -m -u 1000 appuser` + `chown -R appuser:appuser /app` + `USER appuser` before CMD.
- **D-09:** Exec-form `CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]`. Port fixed at 8000.
- **D-10:** `WORKDIR /app` + `COPY backend/ ./` (NOT `./backend/`). App files at `/app` root so imports work as `from routers import ...`.

**Smoke Test**
- **D-11:** Commit `backend/scripts/docker_smoke.sh` (or `.py`): build → boot → poll `/api/health` → upload real PDF + DOCX → assert chunk count > 0 → `docker image inspect` with thresholds → teardown.
- **D-12:** Fixture strategy: scan `backend/tests/` for existing reusable PDF/DOCX fixtures first. If none, generate two minimal fixtures (1-page hello-world) ≤ 50KB committed under `backend/tests/fixtures/`.
- **D-13:** Smoke test authenticates with existing test creds from CLAUDE.md (`ragtest1@gmail.com` / `testpass123`) via Supabase auth endpoint, attaches `Authorization: Bearer <jwt>` to uploads. No dev-only bypass endpoint.
- **D-14:** Image size check uses `docker image inspect <tag> --format '{{.Size}}'` compared to D-03 thresholds.

### Claude's Discretion
- Exact Dockerfile comments + section structure
- Language of the smoke-test script (bash vs python). Recommendation below in §Smoke Test Architecture.
- Whether to add a `Makefile` target `make docker-smoke`. Recommendation below.
- Whether to add `ENV PYTHONUNBUFFERED=1` and `ENV OMP_NUM_THREADS=4`. Recommendation: **include both** — upstream Docling sets `OMP_NUM_THREADS=4`; `PYTHONUNBUFFERED=1` is standard for container logs.
- Exact failure messages / exit codes in the smoke-test script.

### Deferred Ideas (OUT OF SCOPE)
- Multi-stage Dockerfile refactor — only if D-02 escalation triggers
- Dev-only smoke endpoint bypassing auth — rejected; test creds used instead
- Multi-arch build (linux/arm64) — Fly VMs are x86_64
- Testcontainers + pytest docker integration marker — shell script is enough
- `pip-tools` / `requirements.lock` — still deferred from Phase 1
- `DOCLING_CACHE_DIR` env var with explicit cache path — use default
- `Makefile` wrapper — Claude's discretion
- Migration orchestration — Phase 3 handles via Supabase dashboard / `supabase db push`
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DEPLOY-01 | Developer can build a backend container image locally that boots FastAPI + Docling, passes `/api/health`, and handles PDF/DOCX ingest without missing native deps | Upstream Docling Dockerfile pattern (§Code Examples); apt list (§Native Deps Matrix); CPU-torch install pattern (§Standard Stack); smoke-test recipe (§Smoke Test Architecture); health-endpoint already present in `backend/main.py:27-29` |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- Python backend must use a `venv` virtual environment for local dev (container bypasses this — that's fine; container is the venv equivalent for prod-like runs).
- No LangChain / LangGraph — raw SDK only. (No impact on Dockerfile; docling + openai SDK already in `requirements.txt`.)
- Use Pydantic for structured LLM outputs — already in deps.
- All tables need RLS. (No impact on image build.)
- Stream chat via SSE — requires uvicorn without buffering. `PYTHONUNBUFFERED=1` recommended.
- Module 2+ uses stateless completions — means container is stateless, no special volume requirements beyond model cache (which we bake into image per D-06).
- Supabase-Only Storage — external dependency; container must reach Supabase via env-provided URL at runtime.
- Docling required for PDF/DOCX/XLSX — entire reason this phase exists.
- Test credentials `ragtest1@gmail.com` / `testpass123` — reused by smoke-test script per D-13.
- Planning files go under `.planning/` — excluded by `.dockerignore` (already set in Phase 1).

## Standard Stack

### Core (all pre-existing in `backend/requirements.txt` — pinned in Phase 1)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `docling` | 2.82.0 | PDF/DOCX/XLSX → searchable markdown | Project-mandated parser; hard requirement for Phase 2 success criterion 3 |
| `fastapi` | 0.115.12 | Web framework | Already app's entry |
| `uvicorn` | 0.34.2 | ASGI server | CMD process; `--host 0.0.0.0` mandatory in container |
| `torch` | transitive via `docling-ibm-models` (>=2.2.2) | ML runtime for Docling layout/OCR models | NOT in `requirements.txt` directly; resolved through docling's dep graph. MUST be CPU build. |

### Container Build Toolchain

| Tool | Version | Purpose | Why Standard |
|------|---------|---------|--------------|
| `python:3.11-slim-bookworm` (base image) | — | Container base | Exact base in upstream Docling Dockerfile. Bookworm has all required `libgl1`/`libglib2.0-0`/`poppler-utils`/`tesseract-ocr` apt packages. Slim avoids compiler toolchain bloat. |
| Docker | 26+ | Build engine | Any recent version; BuildKit enabled by default is fine |
| `pip` | bundled with base image | Python installer | Use `--no-cache-dir` to avoid wheel cache bloat in image layers |

### Native deps matrix (apt packages on `python:3.11-slim-bookworm`)

ROADMAP success criterion 1 is authoritative. Full list, with reason each one is needed:

| apt package | Needed by | Without it, symptom |
|-------------|-----------|----------------------|
| `poppler-utils` | Docling PDF backend (pdftoppm/pdftotext for some PDFs) | `pdftoppm: command not found` / empty text on certain PDFs |
| `tesseract-ocr` | Docling OCR path (scanned / image-only PDFs) | Falls back, or errors on OCR-required documents |
| `libglib2.0-0` | Transitive to several image libs (opencv/pillow variants, lxml on some wheels) | `ImportError: libglib-2.0.so.0: cannot open shared object file` |
| `fonts-dejavu-core` | PDF rendering / thumbnailing with a default fallback font | Missing glyphs or layout errors on PDFs that embed DejaVu or reference it as fallback |

**Upstream Docling's Dockerfile uses a narrower set** (`libgl1 libglib2.0-0 curl wget git procps`). Our ROADMAP list is broader and safer for the PDF/DOCX/XLSX ingest paths we actually exercise. The one thing **upstream ships that we don't** is `libgl1` (libGL.so.1) — worth watching in the smoke test. If Docling's image conversion path errors with `libGL.so.1`, add `libgl1` to the apt list.

### CPU torch flag

```bash
pip install --no-cache-dir -r requirements.txt \
    --extra-index-url https://download.pytorch.org/whl/cpu
```

- `--extra-index-url` (not `--index-url`): keeps PyPI as primary; only pulls torch/torchvision from pytorch.org CPU wheels.
- Order matters: `--extra-index-url` can follow `-r requirements.txt` on the same command line (pip evaluates all indices for every requirement).
- `--no-cache-dir`: prevents a `/root/.cache/pip` layer that carries all built wheels (can easily be 1–2GB).

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `python:3.11-slim-bookworm` | `python:3.11-alpine` | Rejected: Docling's torch + lxml have musl issues on Alpine — documented pitfall |
| `python:3.11-bookworm` (non-slim) | Non-slim base | Non-slim adds ~200MB of build tools we don't need at runtime (compilers land via slim→apt as needed). Slim + targeted apt is the right call. |
| Single-stage (our D-01) | Multi-stage build (builder + runtime) | Multi-stage would trim ~500MB–1GB by discarding pip wheel cache and any build artifacts. Deferred per D-02 unless image > 6GB. |
| `docling-tools models download` | `python -c "DocumentConverter().convert('dummy.pdf')"` | CLI form is explicit, doesn't need a dummy PDF, and is the documented preload entry point. **Prefer CLI.** |
| `HEALTHCHECK` via curl | `HEALTHCHECK` via python oneliner | curl requires apt-install. Python oneliner uses stdlib urllib — no extra deps. **Prefer python.** |

**Version verification** (run during planning/execution):

```bash
# Verify current versions against pinned / expected
npm view docker-cli version 2>/dev/null  # informational
pip index versions docling                # should list 2.82.0 still available
```

## Architecture Patterns

### Recommended Dockerfile structure (single-stage)

```
FROM python:3.11-slim-bookworm

# 1. ENV — set before apt/pip so all subsequent layers inherit
# 2. apt install  (invalidates rarely — top of Dockerfile)
# 3. Create non-root user
# 4. WORKDIR + COPY requirements.txt
# 5. pip install (cached until requirements.txt changes)
# 6. COPY app code  (invalidates on every code change — placed last)
# 7. chown + USER switch
# 8. docling-tools models download  (AFTER USER switch so cache lands in appuser HOME)
# 9. EXPOSE + HEALTHCHECK + CMD
```

Key insight: the **USER switch must happen BEFORE `docling-tools models download`** — otherwise models cache to `/root/.cache/docling`, which `appuser` cannot read at runtime. This is a gotcha called out in `02-CONTEXT.md` "Gotchas surfaced during scout".

### Layer caching

| Layer | Changes when… | Rebuild time |
|-------|---------------|--------------|
| FROM + apt install | Base or apt list changes | Slow (~60s) — rare |
| pip install | `requirements.txt` changes | Slow (~3–5 min including torch CPU + docling) — occasional |
| models download | docling version changes | Slow (~30–60s + model weights ~1–2GB) — rare |
| COPY backend/ | Any backend source edit | Fast (~5s) — frequent |

This is why D-05 mandates `COPY requirements.txt` BEFORE `COPY backend/`.

### Pattern: non-root user with correct HOME

```dockerfile
RUN useradd -m -u 1000 appuser \
    && mkdir -p /app \
    && chown -R appuser:appuser /app
WORKDIR /app
USER appuser
# now `~/.cache/docling` resolves to /home/appuser/.cache/docling
```

`useradd -m` creates HOME dir (`/home/appuser`) — without `-m`, HOME doesn't exist and cache writes fail.

### Pattern: HEALTHCHECK without curl

```dockerfile
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/api/health', timeout=3).status == 200 else 1)"
```

- `--start-period=30s`: Docling model load on first request can take seconds; start-period prevents false-negative unhealthy during boot. **If models were baked in (D-06), start-period can be short (~10–15s).**
- Python stdlib only — no apt-install needed.

### Anti-patterns to avoid

- **`COPY . .` at repo root**: pulls `.env`, `frontend/`, `.planning/`, `.git/` into image. Phase 1's `.dockerignore` already mitigates, but `COPY backend/ ./` is explicit belt-and-suspenders.
- **`pip install -r requirements.txt` without `--no-cache-dir`**: leaves ~1–2GB of wheel cache in the layer.
- **`apt-get install -y foo` without `--no-install-recommends` and without `rm -rf /var/lib/apt/lists/*`**: adds ~200MB of recommended-but-unused packages + apt index.
- **Shell-form `CMD uvicorn main:app ...`**: wraps in `/bin/sh -c`, breaks signal forwarding. D-09 correctly mandates exec form.
- **`EXPOSE $PORT` with `ENV PORT=8000`**: adds indirection with no benefit since D-09 fixed 8000.
- **Running `docling-tools models download` BEFORE `USER appuser`**: cache lands in `/root/.cache/docling`, unreadable at runtime.
- **Installing torch BEFORE adding `--extra-index-url`**: pulls CUDA wheels, ~3GB of NVIDIA libs.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Preload Docling models | Custom `python -c "DocumentConverter().convert(...)"` with a dummy PDF | `RUN docling-tools models download` | Official CLI; doesn't need dummy input; deterministic |
| Health check auth bypass | Custom dev-only `/api/health/internal` with token | Reuse existing `/api/health` at `backend/main.py:27` | Already unauthenticated, returns 200, suitable for Docker HC and UptimeRobot |
| Build a Python JWT exchange helper | Custom Supabase auth plumbing in smoke script | `curl -X POST <SUPABASE_URL>/auth/v1/token?grant_type=password` with anon key + creds | One HTTP call; returns JSON with `access_token` — jq one-liner to extract |
| File upload simulator | Python httpx wrapper | `curl -F "file=@path/to/fixture.pdf" -H "Authorization: Bearer $JWT"` against `/api/documents` | Shell-native; fewer moving parts in a smoke script |
| Image size check | Parse `docker images` output | `docker image inspect <tag> --format '{{.Size}}'` | Bytes as integer, machine-checkable |

**Key insight:** Stay as close as possible to upstream Docling's Dockerfile + Docker-native primitives. Every custom wrapper is a place the container diverges from "what everyone else runs."

## Runtime State Inventory

> N/A for this phase — greenfield build artifacts only. No renames, no stored data migrations, no OS-registered state, no pre-existing secrets bound to names that change.

**Categories explicitly checked (all empty):**
- Stored data: None — this phase writes nothing to Supabase or any datastore.
- Live service config: None — no Fly app created yet (Phase 4); no existing registry pushes.
- OS-registered state: None — no launchd/systemd/Task Scheduler entries involved.
- Secrets/env vars: `.env` is read by container at runtime via `--env-file`; no new secret names introduced in this phase.
- Build artifacts: No existing Docker image with this tag exists; first build is greenfield. (If a stale `<app>:dev` tag exists locally from earlier experimentation, smoke script should overwrite via `docker build -t` and that's it — no cleanup needed.)

## Common Pitfalls

### Pitfall 1: CUDA torch silently installed (image balloons past 8GB)

**What goes wrong:** Pip resolves `torch>=2.2.2` (transitive from `docling-ibm-models`) against PyPI's default index, which serves CUDA-enabled wheels with NVIDIA libs. Image grows ~3GB.

**Why:** `--extra-index-url` is omitted, typoed, or placed on the wrong `RUN` line.

**How to avoid:** `--extra-index-url https://download.pytorch.org/whl/cpu` on the same `RUN pip install` that installs `-r requirements.txt`. Verify post-build: `docker run --rm <image> python -c "import torch; print(torch.__version__, torch.cuda.is_available())"` — `cuda.is_available()` must be `False` AND the version string should end in `+cpu`.

**Warning signs:** Image size > 5GB; presence of `/usr/local/lib/python3.11/site-packages/nvidia/` or `libcudart.so` in the image.

### Pitfall 2: Docling models cached to `/root/.cache/docling`, unreadable at runtime

**What goes wrong:** Models preloaded as root land in `/root/.cache`; after `USER appuser`, the runtime process can't read them, so Docling re-downloads at first request (slow + fails offline).

**Why:** `RUN docling-tools models download` placed BEFORE `USER appuser`.

**How to avoid:** Put `USER appuser` BEFORE the preload step. Verify: `docker run --rm <image> ls -la /home/appuser/.cache/docling/models` should show model weights owned by `appuser`.

**Warning signs:** First request to `/api/documents` (PDF upload) takes 30+ seconds; container logs show `Downloading model from HuggingFace…`.

### Pitfall 3: `.env` baked into image despite `.dockerignore`

**What goes wrong:** `.env` gets into build context via an explicit `COPY .env .env` line or via `COPY . .` overriding the ignore.

**Why:** Forgetful `COPY . /app` instead of targeted `COPY backend/ ./`.

**How to avoid:** Only `COPY backend/requirements.txt .` and `COPY backend/ ./` in the Dockerfile. Never `COPY . .`. Post-build verify: `docker run --rm <image> sh -c 'ls -la / /app | grep -i env; env | grep -iE "KEY|SECRET|TOKEN" | grep -v PATH'` should produce nothing secret.

**Warning signs:** Image runs successfully WITHOUT `--env-file .env` passed — that's a smell; it means the env is baked in.

### Pitfall 4: `/api/health` returns 200 but Docling still not working

**What goes wrong:** Health check only validates FastAPI process, not the Docling stack. Container reports healthy but first PDF upload fails with a native-dep error.

**Why:** `/api/health` at `backend/main.py:28` returns `{"status":"ok"}` — no Docling import check.

**How to avoid:** Smoke script MUST go beyond `/api/health` and actually upload PDF + DOCX fixtures (D-11). This is the whole point of ROADMAP success criterion 3.

**Warning signs:** Health passes in CI/dev but document uploads fail only in prod.

### Pitfall 5: Frontend `backend/tests/` vs Dockerfile build context

**What goes wrong:** Smoke script expects `backend/tests/fixtures/*.pdf` to be available when `docker cp`ing INTO a running container; but `.dockerignore` excludes `backend/tests/` from the BUILD context. These are different operations — build context ≠ host filesystem access.

**Why it's a non-issue:** Smoke script runs on HOST, uploads via HTTP POST (not `docker cp`), reads fixtures from HOST filesystem. `.dockerignore` only affects what `docker build` sees, not what the host script can access.

**How to avoid confusion:** Comment in the Dockerfile noting that tests are deliberately excluded; comment in smoke script noting fixtures read from host `backend/tests/fixtures/`, not from inside the image.

**Warning signs:** Executor tries to add `COPY backend/tests/fixtures/` to Dockerfile thinking fixtures need to ship in the image — they don't.

### Pitfall 6: Supabase auth request in smoke script fails due to wrong anon key

**What goes wrong:** Script tries `grant_type=password` against `<SUPABASE_URL>/auth/v1/token` but uses service-role key or wrong URL. Returns 401 / 404.

**Why:** Anon key is public, goes in `VITE_SUPABASE_ANON_KEY`; service role is secret, in `SUPABASE_SERVICE_ROLE_KEY`. Password grants need anon key as `apikey` header.

**How to avoid:** Smoke script reads `VITE_SUPABASE_URL` + `VITE_SUPABASE_ANON_KEY` from `.env`. curl call:
```bash
curl -sS -X POST "$VITE_SUPABASE_URL/auth/v1/token?grant_type=password" \
  -H "apikey: $VITE_SUPABASE_ANON_KEY" \
  -H "Content-Type: application/json" \
  -d '{"email":"ragtest1@gmail.com","password":"testpass123"}'
```

**Warning signs:** Auth step returns 401 but `ragtest1` credentials are correct — you're using the wrong key or missing `apikey` header.

## Code Examples

### Reference Dockerfile (upstream Docling, quoted verbatim)

```dockerfile
# Source: https://github.com/docling-project/docling/blob/main/Dockerfile
FROM python:3.11-slim-bookworm

ENV GIT_SSH_COMMAND="ssh -o StrictHostKeyChecking=no"

RUN apt-get update \
&& apt-get install -y libgl1 libglib2.0-0 curl wget git procps \
&& rm -rf /var/lib/apt/lists/*

# This will install torch with *only* cpu support
RUN pip install --no-cache-dir docling --extra-index-url https://download.pytorch.org/whl/cpu

ENV HF_HOME=/tmp/
ENV TORCH_HOME=/tmp/

COPY docs/examples/minimal.py /root/minimal.py

RUN docling-tools models download

ENV OMP_NUM_THREADS=4
```

### Our Dockerfile (composed from upstream + locked decisions)

```dockerfile
# Source: adapted from upstream Docling Dockerfile + CONTEXT.md decisions
FROM python:3.11-slim-bookworm

# ENV — applied early so all layers inherit; PYTHONUNBUFFERED keeps logs flush
# on SSE / uvicorn; OMP_NUM_THREADS recommended by upstream Docling
ENV PYTHONUNBUFFERED=1 \
    OMP_NUM_THREADS=4 \
    PIP_NO_CACHE_DIR=1

# Native deps per ROADMAP success criterion 1
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        poppler-utils \
        tesseract-ocr \
        libglib2.0-0 \
        fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# Non-root user (UID 1000). `-m` creates HOME so ~/.cache resolves.
RUN useradd -m -u 1000 appuser \
    && mkdir -p /app \
    && chown -R appuser:appuser /app

WORKDIR /app

# Install Python deps first — cache-friendly layer
COPY --chown=appuser:appuser backend/requirements.txt .
RUN pip install -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cpu

# App code last so code edits don't bust the pip layer
COPY --chown=appuser:appuser backend/ ./

# Switch to non-root BEFORE model preload so cache lands in /home/appuser/.cache/docling
USER appuser

# Preload Docling default models (baked into image; cold-start-free at runtime)
RUN docling-tools models download

EXPOSE 8000

# Use python stdlib for HC — avoids apt-installing curl just for health
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/api/health', timeout=3).status == 200 else 1)"

# Exec form for PID 1 signal handling
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Smoke-test recipe (bash skeleton)

```bash
#!/usr/bin/env bash
# Source: backend/scripts/docker_smoke.sh (to be created this phase)
set -euo pipefail

IMAGE_TAG="boardgame-rag-backend:smoke"
CONTAINER_NAME="boardgame-rag-smoke"
FIXTURE_PDF="backend/tests/fixtures/hello.pdf"
FIXTURE_DOCX="backend/tests/fixtures/hello.docx"
WARN_BYTES=$((6 * 1024 * 1024 * 1024))    # 6GB
FAIL_BYTES=$((7 * 1024 * 1024 * 1024 + 512 * 1024 * 1024))  # 7.5GB

cleanup() { docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true; }
trap cleanup EXIT

# 1. Build
docker build -t "$IMAGE_TAG" .

# 2. Size check
SIZE_BYTES=$(docker image inspect "$IMAGE_TAG" --format '{{.Size}}')
echo "Image size: $SIZE_BYTES bytes"
if [ "$SIZE_BYTES" -gt "$FAIL_BYTES" ]; then
  echo "FAIL: image > 7.5GB" >&2; exit 1
elif [ "$SIZE_BYTES" -gt "$WARN_BYTES" ]; then
  echo "WARN: image > 6GB — consider multi-stage refactor (D-02)" >&2
fi

# 3. Boot
docker run -d --name "$CONTAINER_NAME" --env-file .env -p 8000:8000 "$IMAGE_TAG"

# 4. Poll health
for i in $(seq 1 30); do
  if curl -sSf http://localhost:8000/api/health >/dev/null 2>&1; then break; fi
  sleep 2
  if [ "$i" -eq 30 ]; then echo "FAIL: health never became 200" >&2; exit 1; fi
done

# 5. Auth — exchange creds for JWT
JWT=$(curl -sS -X POST "$VITE_SUPABASE_URL/auth/v1/token?grant_type=password" \
  -H "apikey: $VITE_SUPABASE_ANON_KEY" \
  -H "Content-Type: application/json" \
  -d '{"email":"ragtest1@gmail.com","password":"testpass123"}' \
  | jq -r '.access_token')
[ -n "$JWT" ] && [ "$JWT" != "null" ] || { echo "FAIL: auth" >&2; exit 1; }

# 6. Upload PDF + DOCX, assert chunks
for FIXTURE in "$FIXTURE_PDF" "$FIXTURE_DOCX"; do
  RESP=$(curl -sS -X POST "http://localhost:8000/api/documents" \
    -H "Authorization: Bearer $JWT" \
    -F "file=@$FIXTURE")
  CHUNKS=$(echo "$RESP" | jq -r '.chunk_count // 0')
  [ "$CHUNKS" -gt 0 ] || { echo "FAIL: $FIXTURE produced 0 chunks: $RESP" >&2; exit 1; }
  echo "OK: $FIXTURE → $CHUNKS chunks"
done

echo "SMOKE PASS"
```

**Language pick (Claude's discretion per CONTEXT.md):** Bash is sufficient and preferred — the whole flow is HTTP calls + JSON parsing with `jq`, no Python-specific features needed. Python would add a venv dependency just for the smoke test. **Recommend bash.**

**Makefile wrapper (Claude's discretion):** Optional. A single `make docker-smoke` target (one line: `@bash backend/scripts/docker_smoke.sh`) is ergonomic and costs ~5 lines. **Recommend include**, since Phase 4 will reuse this target pre-deploy.

### Minimal fixture generation (if no existing PDF/DOCX fixtures)

Scan confirmed `backend/tests/fixtures/` contains only `explorer_fixtures.py` — **no PDF or DOCX fixtures exist**. Executor will need to generate them:

```python
# One-off: backend/scripts/generate_smoke_fixtures.py (or inlined in docker_smoke.sh)
from reportlab.pdfgen import canvas
c = canvas.Canvas("backend/tests/fixtures/hello.pdf")
c.drawString(100, 750, "Hello from smoke test fixture.")
c.showPage(); c.save()

from docx import Document
d = Document()
d.add_paragraph("Hello from smoke test fixture.")
d.save("backend/tests/fixtures/hello.docx")
```

Requires `reportlab` + `python-docx` — NOT in `requirements.txt`, NOT shipped in image. Install only during fixture-gen step: `pip install reportlab python-docx` in a local venv, commit the generated files (< 50KB each), discard the install. Alternative: use a genuinely tiny hand-crafted PDF (7-line valid PDF that embeds "hello") and a stub DOCX (a DOCX is just a zip). Recommend reportlab/python-docx path — standard, well-understood.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `python:3.11` full base | `python:3.11-slim-bookworm` | Standard since ~2023 | ~300MB saved per layer stack |
| Bare `pip install docling` | `pip install docling --extra-index-url .../cpu` | Always — `docling-ibm-models` pulls torch | ~3GB saved vs CUDA default |
| Hand-rolled DocumentConverter preload script | `docling-tools models download` CLI | Added to Docling CLI circa 2.70+ | One-liner, no dummy PDF needed |
| `HEALTHCHECK` via curl | Python stdlib oneliner | Best practice for slim images | Avoids apt-install curl just for HC |
| Fly.io 3× free-tier shared machines | Fly.io 2026: no meaningful free tier, pay-as-you-go | Late 2024 / 2025 | Size discipline now for cost, not hard rootfs limit |

**Deprecated / outdated:**
- `FROM python:3.11` (non-slim): too large, unnecessary for FastAPI + Docling.
- `COPY . .` pattern: use explicit paths.
- `CMD "uvicorn main:app"` shell form: use exec form.
- Assuming Fly free tier will catch you — **2026: Fly is paid**, smoke test cost discipline matters pre-deploy.

## Open Questions

1. **Does `fonts-dejavu-core` + `poppler-utils` + `tesseract-ocr` + `libglib2.0-0` cover all Docling failure modes without `libgl1`?**
   - What we know: upstream Docling Dockerfile uses `libgl1`; ROADMAP omits it; project has been running Docling locally without explicit system `libgl1` on dev machines that happen to have it via other packages.
   - What's unclear: whether Docling's image-conversion code paths (used when OCR fallback kicks in for image-only pages) will error with `ImportError: libGL.so.1` on pure slim-bookworm with only our four apt packages.
   - Recommendation: smoke test with a real PDF that contains an embedded image / scanned page as one of the fixtures. If that errors with `libGL.so.1`, add `libgl1` to the apt list. If it passes, ROADMAP list is vindicated.

2. **Will `docling-tools models download` fetch the `EasyOcrModel` / vision models by default, or only layout?**
   - What we know: Docling's `DocumentConverter` default pipeline uses layout + tableformer + optional OCR. `docling-tools models download` (without flags) downloads "all default models" per upstream comment, but exact scope varies by docling version.
   - What's unclear: total on-disk size contribution (estimates range 500MB–2GB depending on which vision models are pulled).
   - Recommendation: after first successful build, inspect `/home/appuser/.cache/docling/models/` contents via `docker run --rm <image> du -sh /home/appuser/.cache/docling/models` and record in plan/summary. If unexpectedly large (> 2GB), consider `docling-tools models download --help` for subset flags (deferred optimization).

3. **Does `.env` in repo root include `VITE_SUPABASE_URL` + `VITE_SUPABASE_ANON_KEY` usable for JWT exchange?**
   - What we know: Phase 1 SUMMARY confirms CORS env wiring and VITE_API_BASE_URL centralization; `backend/config.py` reads `VITE_SUPABASE_URL` + `VITE_SUPABASE_ANON_KEY` as documented in PITFALLS.md.
   - What's unclear: whether all four env vars (supabase URL, anon key, email, password) are in the single `.env` or spread across multiple files.
   - Recommendation: plan includes a preflight check in the smoke script: fail fast with clear message if any required env var is missing.

## Environment Availability

Environment probes were blocked by sandbox during research. Planner should include an "environment probe" step in the first task that confirms:

| Dependency | Required By | Expected | Fallback |
|------------|-------------|----------|----------|
| Docker 24+ | Build + run container | Available on host | None — hard blocker; escalate to user |
| `bash` 4+ | Smoke script shell | Standard on Linux/macOS; Git Bash on Windows works | PowerShell port if Windows-native needed |
| `curl` | Smoke script HTTP | Standard | None |
| `jq` | Smoke script JSON parsing | Usually available; `winget install jqlang.jq` on Windows | Python oneliner fallback: `python -c "import sys,json; print(json.load(sys.stdin)['access_token'])"` |
| Python 3.10+ (host) | Fixture generation only (one-off) | Already present (dev venv) | — |
| `reportlab`, `python-docx` (host) | Fixture generation only | Install into local venv only, NOT in image | — |
| `.env` with populated VITE_* + SUPABASE_* | Smoke-test auth step | Present in Phase 1 | Smoke script fails fast with diagnostic |

**Missing dependencies with no fallback:** Docker is the only hard blocker. Planner should make the first smoke-script line `command -v docker >/dev/null || { echo "FAIL: docker not installed"; exit 1; }`.

**Missing dependencies with fallback:** `jq` can be swapped for a Python one-liner; Makefile target is optional.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.4.2 (existing; see `backend/requirements.txt:14`) — but NOT the primary validation vector for this phase |
| Config file | `backend/conftest.py` (exists) |
| Quick run command | `cd backend && pytest -x` |
| Full suite command | `cd backend && pytest` |
| **Primary validation** | `bash backend/scripts/docker_smoke.sh` — **this is the Nyquist sample for Phase 2** |

Rationale: Phase 2's four success criteria are all container-level behaviors (`docker build`, `docker run`, `curl /api/health`, PDF/DOCX ingest, image size). No unit-test equivalent exists for "an image built from this Dockerfile boots and ingests real documents." The smoke script IS the validation harness.

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DEPLOY-01.1 | `docker build .` produces image based on `python:3.11-slim-bookworm` with required apt + CPU-torch | build-smoke | `docker build -t boardgame-rag-backend:smoke .` (exit 0) | ❌ Wave 0 (Dockerfile to create) |
| DEPLOY-01.2 | `docker run` boots; `curl /api/health` returns 200 | container-smoke | boot + poll loop in `docker_smoke.sh` | ❌ Wave 0 (script to create) |
| DEPLOY-01.3 | Real PDF + DOCX ingest succeeds without native-dep errors | e2e-smoke | JWT-authenticated upload in `docker_smoke.sh`, assert `chunk_count > 0` | ❌ Wave 0 (script + fixtures to create) |
| DEPLOY-01.4 | Image size within Fly rootfs limits | metric-smoke | `docker image inspect` size compared to 6GB warn / 7.5GB fail thresholds | ❌ Wave 0 (script to create) |
| (regression) | CPU-only torch installed (not CUDA) | post-build-check | `docker run --rm <image> python -c "import torch; assert not torch.cuda.is_available() and '+cpu' in torch.__version__"` | ❌ Wave 0 (add to smoke script) |
| (regression) | Non-root `appuser` runtime | post-build-check | `docker run --rm <image> whoami` returns `appuser` | ❌ Wave 0 (add to smoke script) |
| (regression) | Model cache in appuser HOME | post-build-check | `docker run --rm <image> ls /home/appuser/.cache/docling/models` non-empty | ❌ Wave 0 (add to smoke script) |
| (regression) | No `.env` baked in | post-build-check | `docker run --rm <image> ls /app/.env 2>&1` returns "No such file" | ❌ Wave 0 (add to smoke script) |

### Sampling Rate

- **Per task commit:** run the relevant slice of the smoke script. E.g., after Dockerfile changes → `docker build` + size check. After smoke-script edits → run the full script.
- **Per wave merge:** full `bash backend/scripts/docker_smoke.sh` end-to-end against a clean build (`docker build --no-cache .`).
- **Phase gate:** full smoke script green AND the four regression post-build checks pass, before `/gsd:verify-work`.

### Wave 0 Gaps

- [ ] `Dockerfile` — covers DEPLOY-01.1
- [ ] `backend/scripts/docker_smoke.sh` — covers DEPLOY-01.2, DEPLOY-01.3, DEPLOY-01.4
- [ ] `backend/tests/fixtures/hello.pdf` — fixture for PDF ingest test (generate via reportlab if not present)
- [ ] `backend/tests/fixtures/hello.docx` — fixture for DOCX ingest test (generate via python-docx)
- [ ] `Makefile` target `docker-smoke` — optional; Claude's discretion per CONTEXT.md
- [ ] `.dockerignore` already exists (Phase 1) — verify `backend/tests/` exclusion still correct (it is; fixtures are accessed from host, not inside image)

*No existing test infrastructure covers container-level validation. Smoke script is net-new.*

## Sources

### Primary (HIGH confidence)
- Upstream Docling Dockerfile (verbatim): `https://github.com/docling-project/docling/blob/main/Dockerfile` — base image, apt list, torch CPU flag, `docling-tools models download`, `OMP_NUM_THREADS=4` all confirmed.
- Docling installation docs: `https://docling-project.github.io/docling/getting_started/installation/` — CPU torch flag, tesseract-ocr apt dependency, Python version matrix (3.10+).
- Docling PyPI 2.82.0: `https://pypi.org/project/docling/2.82.0/` — release date 2026-03-25, `Requires-Python: <4.0,>=3.10`, torch not in direct install_requires (pulled via `docling-ibm-models`).
- `.planning/research/STACK.md` §"Reference Dockerfile Pattern" — in-repo research artifact, authoritative for project.
- `.planning/research/PITFALLS.md` §Pitfall 3, §Pitfall 4 — in-repo authoritative.
- `backend/requirements.txt` — docling==2.82.0 pin confirmed.
- `backend/main.py:27-29` — `/api/health` endpoint confirmed present.
- `.dockerignore` — Phase 1 artifact; `backend/tests/` excluded confirmed.
- `.planning/phases/02-dockerize-backend/02-CONTEXT.md` — all locked decisions.

### Secondary (MEDIUM confidence — verified with at least one authoritative source)
- Fly.io pricing 2026: `https://fly.io/docs/about/pricing/` + SaaS Price Pulse — confirms no meaningful free tier; rootfs billed $0.15/GB/mo for stopped machines. Implication: 6GB/7.5GB thresholds from D-03 remain relevant as cost-control, not hard ceiling.
- Docling GitHub Issue #1634: `docling-ibm-models` pins torch>=2.2.2 — confirms why `--extra-index-url` is mandatory.
- Docker HEALTHCHECK best practices: multiple community guides (Better Stack, OneUptime, TestDriven.io 2026) — confirm interval/timeout/start-period/retries pattern, curl-or-stdlib approach.
- DeepWiki Docling docker-deployment page (`10.1-docker-deployment`): attempted; page returned testing framework content (misrouted), so upstream Dockerfile on GitHub was used instead.

### Tertiary (LOW confidence — flagged for validation)
- Exact on-disk size of `docling-tools models download` output — estimate 500MB–2GB; confirm empirically in Task 1 of execution.
- Whether `libgl1` is truly unnecessary for our PDF corpus — ROADMAP says yes; smoke test with an image-embedding PDF will settle it.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — direct verification against upstream Docling repo + docling 2.82.0 PyPI page + in-repo research artifacts.
- Architecture (layering, non-root user, preload ordering): HIGH — upstream pattern + D-series decisions locked in CONTEXT.md.
- Pitfalls: HIGH — mix of in-repo PITFALLS.md (project-authoritative) and upstream-documented gotchas (HF_HOME, USER ordering, torch CUDA default).
- Validation architecture: HIGH — smoke script design flows directly from the four ROADMAP success criteria plus the four regression post-build checks.
- Open Questions #1 (`libgl1` necessity): MEDIUM — will be resolved by smoke test itself.
- Open Question #2 (model size): LOW — will be measured during first build.

**Research date:** 2026-04-24
**Valid until:** ~2026-05-24 (30 days — docker/docling ecosystem moderately stable; Fly pricing could shift sooner).

## RESEARCH COMPLETE

**Phase:** 2 — Dockerize Backend
**Confidence:** HIGH

### Key Findings
- Upstream Docling's Dockerfile is the canonical template; our locked D-decisions diverge only on (a) apt list (broader per ROADMAP), (b) runtime user (non-root), (c) cache path (default `~/.cache/docling` not `/tmp/`), (d) app copy layout (`WORKDIR /app + COPY backend/ ./`).
- Use `docling-tools models download` (upstream CLI) for preload — refines D-06 from hand-rolled `python -c` to official entry point.
- `--extra-index-url https://download.pytorch.org/whl/cpu` is non-negotiable — `docling-ibm-models` transitively pins torch>=2.2.2 and default pip resolution picks CUDA wheels.
- `USER appuser` MUST precede `RUN docling-tools models download` — otherwise cache lands in `/root/.cache` and runtime can't read it.
- Fly.io 2026 has no meaningful free tier — size discipline (<6GB) now serves cost control rather than a hard 8GB rootfs ceiling. D-03 thresholds still correct but for different reason.
- Smoke-test script is the Nyquist sample for this phase — pytest is not the validation vector. Four ROADMAP criteria + four regression post-build checks covered by a single bash script.
- No PDF/DOCX fixtures exist in `backend/tests/fixtures/` — plan must include fixture generation via reportlab + python-docx (host-side, committed).

### File Created
`.planning/phases/02-dockerize-backend/02-RESEARCH.md`

### Confidence Assessment
| Area | Level | Reason |
|------|-------|--------|
| Standard Stack | HIGH | Upstream Docling Dockerfile + PyPI + in-repo STACK.md all agree |
| Architecture | HIGH | Locked D-decisions + upstream pattern alignment |
| Pitfalls | HIGH | Verified via upstream docs + in-repo PITFALLS.md + Docling GitHub issues |
| Validation | HIGH | Four ROADMAP criteria directly map to four smoke-script stages |

### Open Questions (for planner/executor to resolve)
1. Does our 4-package apt list handle image-embedding PDFs without `libgl1`? — settled by smoke test with an appropriate fixture.
2. What's the actual on-disk footprint of `docling-tools models download`? — measure during first build.
3. Are all four env vars (Supabase URL, anon key, test email, password) present in `.env`? — preflight check in smoke script.

### Ready for Planning
Research complete. Planner can now create PLAN.md file(s) for Phase 2. Expected plan structure: one plan is sufficient (Dockerfile + smoke script + fixtures are tightly coupled; no natural wave split).
