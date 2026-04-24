---
phase: 2
slug: dockerize-backend
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-24
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | bash smoke script (docker build + curl + in-container ingest) |
| **Config file** | `scripts/smoke-docker.sh` — Wave 0 creates |
| **Quick run command** | `bash scripts/smoke-docker.sh --quick` |
| **Full suite command** | `bash scripts/smoke-docker.sh` |
| **Estimated runtime** | ~180 seconds (build cached) / ~600 seconds (cold build + models) |

---

## Sampling Rate

- **After every task commit:** Run `bash scripts/smoke-docker.sh --quick` (build + health check only)
- **After every plan wave:** Run full smoke script (build + run + PDF + DOCX ingest + regression checks + size audit)
- **Before `/gsd:verify-work`:** Full script must exit 0
- **Max feedback latency:** 600 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 02-01-01 | 01 | 1 | DEPLOY-01 | fixture | `test -f backend/tests/fixtures/sample.pdf && test -f backend/tests/fixtures/sample.docx` | ❌ W0 | ⬜ pending |
| 02-01-02 | 01 | 1 | DEPLOY-01 | build | `docker build -t ragkb-backend:test -f backend/Dockerfile .` | ❌ W0 | ⬜ pending |
| 02-01-03 | 01 | 1 | DEPLOY-01 | smoke | `bash scripts/smoke-docker.sh --health` | ❌ W0 | ⬜ pending |
| 02-01-04 | 01 | 1 | DEPLOY-01 | integration | `bash scripts/smoke-docker.sh --ingest` | ❌ W0 | ⬜ pending |
| 02-01-05 | 01 | 1 | DEPLOY-01 | regression | `bash scripts/smoke-docker.sh --regression` (no-CUDA, non-root, cache path, no `.env` baked) | ❌ W0 | ⬜ pending |
| 02-01-06 | 01 | 1 | DEPLOY-01 | size | `docker image inspect ragkb-backend:test --format '{{.Size}}'` ≤ 7.5GB | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/fixtures/sample.pdf` — reportlab-generated, ≤50KB, committed
- [ ] `backend/tests/fixtures/sample.docx` — python-docx-generated, ≤50KB, committed
- [ ] `scripts/smoke-docker.sh` — executable, supports `--quick`, `--health`, `--ingest`, `--regression`, full run
- [ ] `backend/Dockerfile` — does not yet exist
- [ ] `backend/.dockerignore` — does not yet exist

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Image runs on fresh host without cached layers | DEPLOY-01 | Cold-cache only reproducible by pruning local Docker cache | `docker builder prune -af && docker build -t ragkb-backend:cold -f backend/Dockerfile .` then rerun smoke script |
| Docling model download completes inside build (offline runtime) | DEPLOY-01 | Validates `docling-tools models download` executed as `appuser`, weights under `/home/appuser/.cache/docling/models` | `docker run --rm ragkb-backend:test ls -la /home/appuser/.cache/docling/models` |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (fixtures + smoke script)
- [ ] No watch-mode flags
- [ ] Feedback latency < 600s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
