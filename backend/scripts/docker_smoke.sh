#!/usr/bin/env bash
# backend/scripts/docker_smoke.sh
# Phase 2 end-to-end smoke test for the backend container.
# Locked by: .planning/phases/02-dockerize-backend/02-CONTEXT.md D-11..D-14
#
# Flow:
#   1. preflight   -- docker + jq + curl installed; .env has required VITE_* keys; fixtures exist
#   2. build       -- docker build -t boardgame-rag-backend:smoke .
#   3. size audit  -- docker image inspect; WARN > 6GB, FAIL > 7.5GB (D-03, D-14)
#   4. boot        -- docker run -d --env-file .env -p 8000:8000
#   5. health poll -- curl /api/health until 200 (timeout ~60s)
#   6. auth        -- Supabase password grant -> JWT (RESEARCH.md Pitfall 6)
#   7. ingest      -- upload hello.pdf + hello.docx to /api/documents/upload; assert chunks > 0
#   8. regression  -- CPU torch / non-root / model cache / no .env baked in
#   9. teardown    -- docker rm -f container
#
# Exits 0 on full pass. Non-zero with clear message on any failure.
# Reusable in Phase 4 pre-deploy gate.

set -euo pipefail

IMAGE_TAG="boardgame-rag-backend:smoke"
CONTAINER_NAME="boardgame-rag-smoke"
FIXTURE_PDF="backend/tests/fixtures/hello.pdf"
FIXTURE_DOCX="backend/tests/fixtures/hello.docx"
WARN_BYTES=$((6 * 1024 * 1024 * 1024))                    # 6 GB
FAIL_BYTES=$((7 * 1024 * 1024 * 1024 + 512 * 1024 * 1024)) # 7.5 GB

log()  { printf '\033[1;34m[smoke]\033[0m %s\n' "$*"; }
fail() { printf '\033[1;31m[FAIL]\033[0m  %s\n' "$*" >&2; exit 1; }
warn() { printf '\033[1;33m[WARN]\033[0m  %s\n' "$*" >&2; }
ok()   { printf '\033[1;32m[ OK ]\033[0m  %s\n' "$*"; }

cleanup() {
  docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true
}
trap cleanup EXIT

# --- 1. Preflight --------------------------------------------------------
log "Preflight: checking host tools + .env + fixtures"
command -v docker >/dev/null || fail "docker not installed -- hard blocker"
command -v curl   >/dev/null || fail "curl not installed"
command -v jq     >/dev/null || fail "jq not installed (winget install jqlang.jq on Windows)"

[ -f .env ] || fail ".env not found at repo root"
# shellcheck disable=SC1091
set -a; source .env; set +a
[ -n "${VITE_SUPABASE_URL:-}" ]      || fail "VITE_SUPABASE_URL missing in .env"
[ -n "${VITE_SUPABASE_ANON_KEY:-}" ] || fail "VITE_SUPABASE_ANON_KEY missing in .env"

[ -f "$FIXTURE_PDF" ]  || fail "Missing $FIXTURE_PDF (run backend/scripts/generate_smoke_fixtures.py)"
[ -f "$FIXTURE_DOCX" ] || fail "Missing $FIXTURE_DOCX (run backend/scripts/generate_smoke_fixtures.py)"
ok "Preflight passed"

# --- 2. Build ------------------------------------------------------------
log "Build: docker build -t $IMAGE_TAG ."
docker build -t "$IMAGE_TAG" . || fail "docker build failed"
ok "Image built: $IMAGE_TAG"

# --- 3. Size audit (D-03 / D-14) -----------------------------------------
SIZE_BYTES=$(docker image inspect "$IMAGE_TAG" --format '{{.Size}}')
SIZE_GB=$(awk "BEGIN {printf \"%.2f\", $SIZE_BYTES/1024/1024/1024}")
log "Image size: ${SIZE_GB} GB ($SIZE_BYTES bytes)"
if   [ "$SIZE_BYTES" -gt "$FAIL_BYTES" ]; then fail "Image > 7.5 GB -- unusable on Fly rootfs"
elif [ "$SIZE_BYTES" -gt "$WARN_BYTES" ]; then warn "Image > 6 GB -- consider multi-stage refactor (D-02)"
else ok "Image size within target (< 6 GB)"
fi

# --- 4. Boot -------------------------------------------------------------
cleanup
log "Boot: docker run --env-file .env -p 8000:8000 $IMAGE_TAG"
docker run -d --name "$CONTAINER_NAME" --env-file .env -p 8000:8000 "$IMAGE_TAG" >/dev/null \
  || fail "docker run failed"

# --- 5. Health poll ------------------------------------------------------
log "Health: polling http://localhost:8000/api/health (up to 60s)"
for i in $(seq 1 30); do
  if curl -sSf http://localhost:8000/api/health >/dev/null 2>&1; then ok "Health 200 after ${i}x2s"; break; fi
  if [ "$i" -eq 30 ]; then
    docker logs "$CONTAINER_NAME" 2>&1 | tail -50 >&2
    fail "/api/health never returned 200 within 60s"
  fi
  sleep 2
done

# --- 6. Auth (Supabase password grant -- shared helper, Phase 4 D-14) ----
log "Auth: exchanging ragtest1 creds for JWT (via _lib/get_test_jwt.sh)"
# shellcheck source=_lib/get_test_jwt.sh
source "$(dirname "$0")/_lib/get_test_jwt.sh"
get_test_jwt || fail "Auth failed (see stderr above)"
ok "JWT acquired"

# --- 7. Ingest PDF + DOCX ------------------------------------------------
# NOTE: endpoint is /api/documents/upload (router prefix /api/documents + POST /upload)
for FIXTURE in "$FIXTURE_PDF" "$FIXTURE_DOCX"; do
  log "Ingest: POST /api/documents/upload file=@$FIXTURE"
  RESP=$(curl -sS -X POST "http://localhost:8000/api/documents/upload" \
    -H "Authorization: Bearer $JWT" \
    -F "file=@$FIXTURE")
  # Prefer .chunk_count; fall back to (.chunks | length) if the field name differs.
  CHUNKS=$(echo "$RESP" | jq -r '.chunk_count // (.chunks | length) // 0' 2>/dev/null || echo 0)
  if [ "$CHUNKS" -gt 0 ] 2>/dev/null; then
    ok "$FIXTURE -> $CHUNKS chunks"
  else
    echo "$RESP" | head -c 2000 >&2
    fail "$FIXTURE produced 0 chunks (check Docling native deps -- libgl/libglib/poppler/tesseract)"
  fi
done

# --- 8. Regression checks (PITFALLS.md #1/#2/#3) -------------------------
log "Regression: CPU-only torch"
docker run --rm "$IMAGE_TAG" python -c "import torch,sys; sys.exit(0 if (not torch.cuda.is_available() and '+cpu' in torch.__version__) else 1)" \
  || fail "torch is not CPU-only (CUDA wheel slipped in -- check --extra-index-url)"
ok "torch is CPU-only"

log "Regression: non-root runtime user"
USER_IN_IMG=$(docker run --rm "$IMAGE_TAG" whoami)
[ "$USER_IN_IMG" = "appuser" ] || fail "Runtime user is '$USER_IN_IMG', expected 'appuser' (D-08)"
ok "Runtime user is appuser"

log "Regression: Docling models in appuser HOME"
docker run --rm "$IMAGE_TAG" sh -c 'ls /home/appuser/.cache/docling/models >/dev/null 2>&1' \
  || fail "Model cache missing at /home/appuser/.cache/docling/models (USER switch too late -- PITFALLS.md #2)"
ok "Docling models baked into /home/appuser/.cache/docling/models"

log "Regression: .env NOT baked into image"
docker run --rm "$IMAGE_TAG" sh -c 'test ! -f /app/.env' \
  || fail ".env was baked into /app -- PITFALLS.md #3"
ok ".env not baked in"

# --- 9. Teardown (via trap) ----------------------------------------------
ok "SMOKE PASS (image ${SIZE_GB} GB)"
