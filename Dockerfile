# Dockerfile -- Backend container for Board Game KB RAG (Phase 2)
# Single-stage (D-01), python:3.11-slim-bookworm base, non-root appuser (D-08),
# CPU-only torch (D-04), Docling models preloaded (D-06) under /home/appuser/.cache/docling.
# Locked decisions: see .planning/phases/02-dockerize-backend/02-CONTEXT.md D-01..D-10.
FROM python:3.11-slim-bookworm

# ENV applied early so all subsequent layers inherit.
# PYTHONUNBUFFERED=1 keeps uvicorn/SSE logs flushing in real time.
# OMP_NUM_THREADS=4 matches upstream Docling Dockerfile for CPU inference.
# PIP_NO_CACHE_DIR=1 prevents a /root/.cache/pip wheel cache layer (~1-2GB).
ENV PYTHONUNBUFFERED=1 \
    OMP_NUM_THREADS=4 \
    PIP_NO_CACHE_DIR=1

# Native deps per ROADMAP Phase 2 success criterion 1 (broader than upstream Docling's list).
# poppler-utils: Docling PDF backend (pdftoppm/pdftotext)
# tesseract-ocr: Docling OCR path for scanned/image-only PDFs
# libglib2.0-0:  transitive for opencv/pillow/lxml variants (prevents libglib-2.0.so.0 ImportError)
# fonts-dejavu-core: PDF rendering fallback font
# --no-install-recommends + rm apt lists keeps the layer minimal (~200MB saved vs defaults).
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        poppler-utils \
        tesseract-ocr \
        libglib2.0-0 \
        fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# Non-root user (D-08). `-m` creates HOME (/home/appuser) so ~/.cache/docling resolves.
RUN useradd -m -u 1000 appuser \
    && mkdir -p /app \
    && chown -R appuser:appuser /app

WORKDIR /app

# Python deps first (D-05 layer order) -- cache-friendly until requirements.txt changes.
# --extra-index-url is MANDATORY: docling-ibm-models pulls torch>=2.2.2 transitively,
# and without the CPU wheel index pip resolves CUDA wheels (~3GB NVIDIA libs). See PITFALLS.md #1.
COPY --chown=appuser:appuser backend/requirements.txt .
RUN pip install -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cpu

# App code last (D-05) so source edits don't bust the pip layer.
# Explicit `backend/ ./` (NOT `COPY . .`) -- belt-and-suspenders on top of .dockerignore,
# prevents .env/.git/frontend/.planning from entering the image (PITFALLS.md #3).
# NOTE: backend/tests/ is excluded by .dockerignore -- fixtures stay on host, consumed by
# backend/scripts/docker_smoke.sh via HTTP POST, not via in-image filesystem.
COPY --chown=appuser:appuser backend/ ./

# Switch to non-root BEFORE model preload so cache lands in /home/appuser/.cache/docling
# (not /root/.cache/docling which appuser cannot read). See PITFALLS.md #2.
USER appuser

# Preload Docling default models (D-06). Bakes weights into the image; cold-start-free at runtime.
# Uses official CLI (not hand-rolled `python -c`) per RESEARCH.md recommendation.
RUN docling-tools models download

EXPOSE 8000

# HEALTHCHECK uses Python stdlib (urllib) to avoid apt-installing curl just for the probe.
# start-period=15s: Docling models are preloaded so boot is fast; no long warm-up needed.
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/api/health', timeout=3).status == 200 else 1)"

# Exec form (D-09) for native PID 1 signal handling. Target is `main:app` because
# COPY backend/ ./ lands main.py at /app/main.py -- NOT `backend.main:app`.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
