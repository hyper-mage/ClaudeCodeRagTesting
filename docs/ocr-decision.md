# OCR Engine Decision: Tesseract over RapidOCR/EasyOCR

**Date:** 2026-04-27
**Phase:** 02 — dockerize-backend (smoke-test debugging)
**Decision:** Pin Docling's PDF OCR engine to **Tesseract** via explicit `TesseractOcrOptions()` in `backend/services/parsing_service.py`.

---

## Context

Phase 02 added a containerized backend (`Dockerfile` + `backend/scripts/docker_smoke.sh`) that boots FastAPI + Docling and ingests PDF/DOCX fixtures. First successful boot reproducibly failed at PDF ingest with:

```
{"status":"failed","error_message":"architecture ch_PP-OCRv4_det_infer is not in arch_config.yaml","chunk_count":0}
```

## Root cause

Inside the container:

| Package           | Version |
|-------------------|---------|
| `docling`         | 2.82.0  |
| `docling-core`    | 2.74.0  |
| `docling-ibm-models` | 3.13.2 |
| `docling-parse`   | 5.10.1  |
| `rapidocr`        | 3.8.1   |

Docling 2.82's default OCR engine is RapidOCR. `docling-tools models download` (run during image build) fetches PP-OCRv4 ONNX weights into `~/.cache/docling/models/RapidOcr/`. RapidOCR 3.x changed its model architecture registry (`arch_config.yaml`); the model files Docling 2.82 fetches no longer match the architecture names RapidOCR 3.8.1 expects.

This is a transitive version-drift bug between Docling's downloader CLI and the RapidOCR runtime — not something we caused, and not something a single pin in `requirements.txt` cleanly fixes (Docling pulls `rapidocr` unpinned).

## Options considered

| Option | Cost | Long-term fit |
|--------|------|---------------|
| **A. Disable OCR** (`pdf_options.do_ocr = False`) | Zero — fixtures are text-layer PDFs | **Bad.** Board game PDFs (BGG, archive.org, scanned manuals) are frequently image-heavy. Silent regression mode: "X uploaded but no chunks." |
| **B. Pin RapidOCR / pre-3.x** | Medium — chase upstream pins, retest each Docling bump | Brittle. Couples our build to two third-party version curves. |
| **C. Switch to EasyOCR** (`EasyOcrOptions`) | Adds ~500MB model weights to image, requires `docling-tools models download` to fetch matching weights | Works, but inherits the same downloader-vs-runtime drift class of bug, just shifted to a different engine. |
| **D. Switch to Tesseract** (`TesseractOcrOptions`) | Zero new Python deps; +~50MB apt for `tesseract-ocr-eng`; requires `tesseract-ocr` already in apt list (it is) | **Chosen.** |

## Why Tesseract (D)

1. **OS-managed.** `tesseract-ocr` + `tesseract-ocr-eng` are Debian apt packages. Docling shells out to the binary. Zero Python-side model registry; zero ONNX runtime; zero version drift between "downloader" and "runtime" because there is no downloader.
2. **Already in image.** `tesseract-ocr` was on the apt list since Phase 02-01 commit. Adding `tesseract-ocr-eng` is a one-line addition (English `traineddata`).
3. **Battle-tested.** 30+ year history. Deterministic output across versions for identical input. Predictable failure modes.
4. **Smaller.** ~50MB lang pack vs ~500MB EasyOCR weights or ~300MB RapidOCR weights.
5. **Extensible.** Adding more languages (e.g. German for Catan rules, French for older Asmodee titles) is `apt-get install tesseract-ocr-deu tesseract-ocr-fra` — a one-line Dockerfile change, no Python code, no model downloads.
6. **No CUDA coupling.** EasyOCR/RapidOCR ship `onnxruntime` which can drag CUDA wheels into the resolver. Tesseract has zero ML/Python ecosystem footprint.

## Tradeoffs accepted

- **OCR quality.** Tesseract is generally lower-quality than EasyOCR/PaddleOCR on cluttered, low-DPI, or non-Latin scripts. Mitigation: most board game manuals are clean print PDFs ≥300 DPI; quality gap is acceptable for v1. If a real corpus reveals systematic OCR misses, revisit per Phase 04+.
- **Speed.** Tesseract is single-threaded per page in Docling's wrapper. Our PDFs are short rulebooks (typically <50 pages); no concern at current scale.
- **Layout-aware OCR.** Tesseract has weaker layout heuristics than PaddleOCR for multi-column / mixed-image text. Docling's own layout model handles most layout reasoning before OCR is invoked, so the impact is minor.

## What changed

### `backend/services/parsing_service.py`
```python
from docling.datamodel.pipeline_options import PdfPipelineOptions, TesseractCliOcrOptions
...
pdf_options = PdfPipelineOptions()
pdf_options.ocr_options = TesseractCliOcrOptions()  # CLI subprocess to apt tesseract
```

**Important:** Docling exposes two Tesseract backends. `TesseractOcrOptions` uses
the `tesserocr` Python C-bindings (must `pip install tesserocr` and often compile
against the host libtesseract). `TesseractCliOcrOptions` shells out to the apt
`tesseract` binary via subprocess — zero Python deps, just the apt packages.
We use the CLI variant.

### `Dockerfile`
Added `tesseract-ocr-eng` to the apt install list. Comment block expanded to document why each native dep is present.

## Earlier fixes from same smoke run (logged for completeness)

| Fix | File | Why |
|-----|------|-----|
| Add `python-multipart==0.0.20` | `backend/requirements.txt` | FastAPI `UploadFile` needs it; missing in container, present in dev venv via transitive of something else |
| Add `libgl1` apt package | `Dockerfile` | opencv (Docling transitive) needs `libGL.so.1` at runtime |
| `EXPLORER_MAX_ITERATIONS=3 # default is 5` → `EXPLORER_MAX_ITERATIONS=3` | `.env` (developer host) | pydantic-settings does not strip inline comments after `=` |

## Re-evaluation triggers

Revisit this decision if any of:

- Real board game corpus shows >5% OCR-quality regressions vs human-readable ground truth.
- Docling pins RapidOCR ≤2.x in a future release (drift risk eliminated).
- Multi-language support requires fonts/scripts Tesseract handles poorly (e.g. CJK board games).
- A future phase adds image-only ingest (board photos, prototype scans) where Tesseract's image OCR proves insufficient.
