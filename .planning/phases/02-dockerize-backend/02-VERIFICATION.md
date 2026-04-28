---
phase: 02-dockerize-backend
verified: 2026-04-28T00:00:00Z
status: passed
score: 10/10 must-haves verified (live Docker smoke run completed 2026-04-28)
re_verification:
  previous_status: none
  previous_score: n/a
  gaps_closed: []
  gaps_remaining: []
  regressions: []
human_verification:
  - test: "Run end-to-end smoke script"
    expected: "`bash backend/scripts/docker_smoke.sh` exits 0; output contains `SMOKE PASS`, `Health 200`, two `-> N chunks` lines (PDF + DOCX, N>0), and four `[ OK ]` regression lines (CPU torch, appuser, models, no .env)"
    why_human: "Docker daemon is not available in this verification sandbox. The full build + boot + ingest + regression cycle (truths 1-5, 7-10) can only be exercised on the developer's host. Static Dockerfile contract and smoke-script contract are both 100% green; the live run is the final unfaked confirmation."
  - test: "Confirm built image size <7.5GB (hard) and ideally <6GB"
    expected: "`docker image inspect boardgame-rag-backend:smoke --format '{{.Size}}'` returns value < 8053063680 (7.5 GB). Smoke script auto-checks this and FAILs > 7.5 GB / WARNs 6-7.5 GB."
    why_human: "Requires Docker build to have completed. Embedded in smoke script step 3 (size audit), so a clean smoke-script exit 0 (or only WARN) is sufficient evidence."
---

# Phase 02: Dockerize Backend Verification Report

**Phase Goal:** Build a reproducible backend image that boots FastAPI + Docling with all native deps, validated locally before any cloud deploy. (DEPLOY-01)
**Verified:** 2026-04-28 (live smoke run completed)
**Status:** passed
**Re-verification:** No - initial verification

## Live Smoke Run (2026-04-28)

```
[ OK ]  Image built: boardgame-rag-backend:smoke
[smoke] Image size: 2.78 GB (2988195874 bytes)
[ OK ]  Image size within target (< 6 GB)
[ OK ]  Health 200 after 3x2s
[ OK ]  JWT acquired
[ OK ]  backend/tests/fixtures/hello.pdf -> 1 chunks
[ OK ]  backend/tests/fixtures/hello.docx -> 1 chunks
[ OK ]  torch is CPU-only
[ OK ]  Runtime user is appuser
[ OK ]  Docling models baked into /home/appuser/.cache/docling/models
[ OK ]  .env not baked in
[ OK ]  SMOKE PASS (image 2.78 GB)
```

Truths 1-10 all confirmed live. Final image: 2.78 GB (well under 6 GB warn / 7.5 GB hard ceiling).

### Fixes applied during smoke debugging

| File | Change | Reason |
|---|---|---|
| `backend/requirements.txt` | Added `python-multipart==0.0.20` | FastAPI `UploadFile` runtime dep missing in container (present in dev venv as transitive) |
| `Dockerfile` | Added `libgl1` apt pkg | opencv (Docling transitive) needs `libGL.so.1` |
| `Dockerfile` | Added `tesseract-ocr-eng` apt pkg | English `traineddata` for Tesseract OCR engine |
| `backend/services/parsing_service.py` | `pdf_options.ocr_options = TesseractCliOcrOptions()` | Pin OCR engine; bypass docling/rapidocr 3.x version drift (`ch_PP-OCRv4_det_infer is not in arch_config.yaml`). See `docs/ocr-decision.md`. |
| `.env` (developer host, not committed) | Stripped inline comment from `EXPLORER_MAX_ITERATIONS=3` | pydantic-settings does not strip `# comment` after `=` |

## Goal Achievement

### Observable Truths

| #   | Truth                                                                                                                | Status            | Evidence                                                                                                                                                                                                                |
| --- | -------------------------------------------------------------------------------------------------------------------- | ----------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | `docker build .` at repo root succeeds without errors                                                                | ? NEEDS HUMAN     | Dockerfile contract fully verified statically (every required directive present, layer order correct). Live build requires Docker daemon (not available in this verification env).                                       |
| 2   | `docker run --env-file .env -p 8000:8000 <image>` boots the container                                                | ? NEEDS HUMAN     | CMD `["uvicorn","main:app","--host","0.0.0.0","--port","8000"]` confirmed (line 66). `main:app` matches `backend/main.py:11` (`app = FastAPI(...)`). Live boot requires Docker.                                          |
| 3   | `curl http://localhost:8000/api/health` returns 200                                                                  | ? NEEDS HUMAN     | `/api/health` endpoint confirmed at `backend/main.py:27`. Smoke script step 5 polls and asserts. Live runtime requires Docker.                                                                                            |
| 4   | PDF fixture upload to `/api/documents/upload` returns chunk_count > 0                                                | ? NEEDS HUMAN     | Smoke script step 7 sends `curl -F file=@backend/tests/fixtures/hello.pdf` to correct endpoint (path auto-fixed in commit `fc861cf` from plan-stated `/api/documents` to actual route at `documents.py:12,28`). Live ingest required. |
| 5   | DOCX fixture upload returns chunk_count > 0                                                                          | ? NEEDS HUMAN     | Same loop as PDF; same endpoint; live ingest required.                                                                                                                                                                  |
| 6   | Image size < 7.5GB (hard) and ideally < 6GB                                                                          | ? NEEDS HUMAN     | Smoke script enforces this in step 3 with `WARN_BYTES=6GB`, `FAIL_BYTES=7.5GB` (lines 26-27, 64-67). Static check confirmed; live image size requires build.                                                                |
| 7   | torch installed is the CPU wheel (`+cpu`, no CUDA)                                                                   | ✓ VERIFIED        | Dockerfile line 40: `pip install -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cpu`. Smoke script regression check (step 8a, lines 114-117) asserts `not torch.cuda.is_available() and '+cpu' in torch.__version__`. |
| 8   | Container runs as non-root `appuser` (UID 1000); Docling cache under `/home/appuser/.cache/docling/models`           | ✓ VERIFIED        | `useradd -m -u 1000 appuser` (line 30), `USER appuser` (line 51) precedes `RUN docling-tools models download` (line 55). Smoke script regression checks 8b + 8c assert `whoami=appuser` and cache dir non-empty.            |
| 9   | No `.env` file is baked into the image                                                                               | ✓ VERIFIED        | `.dockerignore` excludes `.env` and `.env.*` (lines 2-3). Dockerfile uses explicit `COPY backend/requirements.txt` + `COPY backend/ ./` (not `COPY . .`). Smoke regression check 8d (line 130) asserts `test ! -f /app/.env`. |
| 10  | `bash backend/scripts/docker_smoke.sh` exits 0 end-to-end                                                            | ? NEEDS HUMAN     | Script is executable, `set -euo pipefail`, all 9 phases (preflight -> teardown) present and correctly wired. Live execution requires Docker + dev `.env` populated.                                                       |

**Score:** 3/10 fully VERIFIED via static analysis; 7/10 require live Docker for behavioral confirmation.

Note: SUMMARY self-check states "live `docker build` + `bash backend/scripts/docker_smoke.sh` execution was performed by the developer prior to commit (commit ordering and the script-was-corrected-for-real-endpoint-path evidence both indicate at-least-one successful end-to-end run)". This is plausible (the auto-fix from `/api/documents` -> `/api/documents/upload` could only be discovered by running the script and seeing 404/405), but it is unverifiable from the static repo state.

### Required Artifacts

| Artifact                                       | Expected                                                                       | Status      | Details                                                                                                                                                                  |
| ---------------------------------------------- | ------------------------------------------------------------------------------ | ----------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `Dockerfile`                                   | Repo-root single-stage backend image                                           | ✓ VERIFIED  | 67 lines, all 13 required `contains:` patterns present (FROM, 4 apt pkgs, useradd, COPY requirements, COPY backend, --extra-index-url, USER appuser, docling-tools, HEALTHCHECK, CMD). |
| `backend/scripts/docker_smoke.sh`              | E2E smoke: build/size/boot/health/auth/ingest/regression/teardown              | ✓ VERIFIED  | 136 lines, mode `-rwxr-xr-x` (executable). Contains shebang, `set -euo pipefail`, IMAGE_TAG, FIXTURE paths, preflight tools, Supabase password grant with `apikey` (anon, not service role), 6GB warn / 7.5GB fail bytes, all four regression checks. |
| `backend/scripts/generate_smoke_fixtures.py`   | Reproducibility script (reportlab + python-docx)                               | ✓ VERIFIED  | 35 lines, imports both `reportlab.pdfgen.canvas` and `docx.Document`, writes both fixtures to `backend/tests/fixtures/`.                                                  |
| `backend/tests/fixtures/hello.pdf`             | 1-page PDF, ≤ 51200 bytes                                                      | ✓ VERIFIED  | 1442 bytes. `file` reports "PDF document, version 1.3, 1 page(s)".                                                                                                       |
| `backend/tests/fixtures/hello.docx`            | 1-page DOCX, ≤ 51200 bytes                                                     | ✓ VERIFIED  | 36646 bytes. `file` reports "Microsoft Word 2007+".                                                                                                                      |

All 5 artifacts pass Levels 1 (exists), 2 (substantive), 3 (wired). Level 4 (data flows) is N/A for infra/script artifacts.

### Key Link Verification

| From                              | To                                                | Via                                                                            | Status        | Details                                                                                                          |
| --------------------------------- | ------------------------------------------------- | ------------------------------------------------------------------------------ | ------------- | ---------------------------------------------------------------------------------------------------------------- |
| Dockerfile                        | `backend/requirements.txt`                        | `COPY backend/requirements.txt . && pip install --extra-index-url .../cpu`     | ✓ WIRED       | Line 39-40 match pattern verbatim.                                                                               |
| Dockerfile                        | `backend/main.py` (uvicorn entrypoint)            | `COPY backend/ ./ && CMD uvicorn main:app`                                     | ✓ WIRED       | Line 47 + 66. `main:app` (not `backend.main:app`) matches `WORKDIR /app` + flat copy of `backend/` contents.        |
| `backend/scripts/docker_smoke.sh` | `backend/tests/fixtures/hello.pdf`, `hello.docx`  | `curl -F file=@<fixture>` against running container                            | ✓ WIRED       | Lines 24-25, 98-102. Uses correct `/api/documents/upload` endpoint (verified against `routers/documents.py:12,28`). |
| `backend/scripts/docker_smoke.sh` | Supabase auth                                     | `curl grant_type=password` -> JWT -> `Authorization: Bearer`                   | ✓ WIRED       | Lines 88-94. Uses `apikey: $VITE_SUPABASE_ANON_KEY` (correctly NOT service role per Pitfall 6).                    |
| Dockerfile USER switch            | `docling-tools models download`                   | `USER appuser` MUST precede `RUN docling-tools models download`                | ✓ WIRED       | `USER appuser` at line 51, `RUN docling-tools models download` at line 55. Order correct (cache lands in /home/appuser/.cache/docling). |

All 5 key links WIRED.

### Data-Flow Trace (Level 4)

N/A — phase produces infrastructure (Dockerfile, shell script, fixtures), not dynamic-data-rendering artifacts.

### Behavioral Spot-Checks

| Behavior                                          | Command                                                                            | Result                                  | Status     |
| ------------------------------------------------- | ---------------------------------------------------------------------------------- | --------------------------------------- | ---------- |
| Dockerfile syntactic contract complete            | `grep -c <required pattern> Dockerfile` for all 13 patterns                        | All 13 present                          | ✓ PASS     |
| Smoke script syntactic contract complete          | `grep` for set -euo, fixtures, jq, anon key, thresholds, regression checks         | All present                             | ✓ PASS     |
| `.dockerignore` preserves Phase 1 contract        | grep `.env`, `venv/`, `__pycache__/`, `.git/`, `frontend/`, `.planning/`, `backend/tests/` | All 7 patterns present                  | ✓ PASS     |
| `reportlab`/`python-docx` NOT in image deps       | `grep -E '^(reportlab\|python-docx)' backend/requirements.txt`                     | 0 matches (good)                        | ✓ PASS     |
| `docling==2.82.0` pinned                          | `grep '^docling' backend/requirements.txt`                                          | `docling==2.82.0` (line 12)             | ✓ PASS     |
| `main.py` exposes `/api/health` and `app`         | grep `backend/main.py`                                                             | `app = FastAPI(...)` line 11; `@app.get("/api/health")` line 27 | ✓ PASS     |
| Smoke script ingest endpoint matches real router  | router `prefix="/api/documents"` + `@router.post("/upload")` vs script POSTs       | Script POSTs `/api/documents/upload` -- match | ✓ PASS     |
| Fixture file types valid                          | `file backend/tests/fixtures/hello.{pdf,docx}`                                     | PDF v1.3 / "Microsoft Word 2007+"       | ✓ PASS     |
| Fixture sizes ≤ 50KB                              | `wc -c`                                                                            | 1442 / 36646 bytes (both ≤ 51200)       | ✓ PASS     |
| Live `docker build` succeeds                      | `docker build -t boardgame-rag-backend:smoke .`                                    | Docker daemon unavailable in env        | ? SKIP     |
| Live smoke script exit 0                          | `bash backend/scripts/docker_smoke.sh`                                             | Docker daemon unavailable in env        | ? SKIP     |

### Requirements Coverage

| Requirement | Source Plan      | Description                                                                                                                                                              | Status          | Evidence                                                                                                                                              |
| ----------- | ---------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | --------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| DEPLOY-01   | 02-01-PLAN.md    | Developer can build a backend container image locally that boots FastAPI + Docling, passes /api/health, and handles PDF/DOCX ingest without missing native deps          | ? NEEDS HUMAN   | Static contract fully satisfied (Dockerfile + smoke script + fixtures all green). Behavioral confirmation requires Docker build + smoke run on developer host. SUMMARY claims developer ran the script; corroborating evidence is the `/api/documents/upload` auto-fix in commit `fc861cf` (only discoverable by running). |

No orphaned requirements. ROADMAP maps only DEPLOY-01 to Phase 2; the plan declares only DEPLOY-01 in `requirements:` frontmatter. 1:1 coverage, no gaps.

### Anti-Patterns Found

Scanned all 5 files modified in phase 02 + `.dockerignore`:

| File                                       | Line   | Pattern                          | Severity   | Impact                                                                                                                            |
| ------------------------------------------ | ------ | -------------------------------- | ---------- | --------------------------------------------------------------------------------------------------------------------------------- |
| (none)                                     | -      | -                                | -          | No TODO/FIXME/PLACEHOLDER, no empty returns, no `console.log`-only handlers, no hardcoded empty state in user-visible paths. Smoke script is fail-fast end-to-end. Dockerfile has zero placeholder layers. |

Comments in scripts/Dockerfile referencing PITFALLS.md and CONTEXT.md are documentation, not stubs.

### Human Verification Required

#### 1. Run end-to-end smoke script

**Test:** From repo root with Docker daemon running and `.env` populated with valid `VITE_SUPABASE_URL` + `VITE_SUPABASE_ANON_KEY`:
```bash
bash backend/scripts/docker_smoke.sh
```

**Expected:** Exits 0. Output contains:
- `[ OK ] Preflight passed`
- `[ OK ] Image built: boardgame-rag-backend:smoke`
- `[smoke] Image size: <N.NN> GB` followed by `[ OK ] Image size within target (< 6 GB)` or at most `[WARN] Image > 6 GB`
- `[ OK ] Health 200 after Nx2s`
- `[ OK ] JWT acquired`
- `[ OK ] backend/tests/fixtures/hello.pdf -> N chunks` (N > 0)
- `[ OK ] backend/tests/fixtures/hello.docx -> N chunks` (N > 0)
- `[ OK ] torch is CPU-only`
- `[ OK ] Runtime user is appuser`
- `[ OK ] Docling models baked into /home/appuser/.cache/docling/models`
- `[ OK ] .env not baked in`
- `[ OK ] SMOKE PASS (image <N.NN> GB)`

**Why human:** Docker daemon is not available in this verification sandbox. The full build + boot + ingest + regression cycle (truths 1-6, 10) can only be exercised on the developer's host. Static contracts are 100% green; the live run is the final unfaked confirmation.

#### 2. Confirm image-size headroom

**Test:** After build:
```bash
docker image inspect boardgame-rag-backend:smoke --format '{{.Size}}'
```

**Expected:** Value < 8053063680 (7.5 GB hard ceiling). Ideally < 6442450944 (6 GB warn ceiling). Smoke script step 3 already automates this comparison, so a clean smoke-script exit handles it implicitly.

**Why human:** Image size is a build-product property; cannot be measured without a successful build.

### Gaps Summary

There are no static-contract gaps. Every Dockerfile directive, smoke-script clause, fixture file, and key link in the plan's `must_haves` is present and correctly wired. The two outstanding items (live `docker build` + live smoke run) are not "gaps" in the planning sense — they are runtime confirmations of an already-correct contract that this verification environment cannot perform because Docker is not available.

The plan SUMMARY's self-check claims at-least-one successful end-to-end run was performed by the developer (corroborated by the `/api/documents/upload` auto-fix in commit `fc861cf`, which would only be discoverable by actually running the script and seeing the wrong path 404/405). This is plausible but unverifiable from the static repo state alone, hence `human_needed` (not `passed`).

**Recommendation:** Developer runs `bash backend/scripts/docker_smoke.sh` once on a clean Docker daemon and pastes the final 30 lines of output to confirm. If the script exits 0 with `SMOKE PASS` and chunk counts > 0 for both fixtures, status flips to `passed` with no plan changes needed.

---

_Verified: 2026-04-26_
_Verifier: Claude (gsd-verifier)_
