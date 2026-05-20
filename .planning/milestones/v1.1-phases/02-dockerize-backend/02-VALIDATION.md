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
| **Config file** | `backend/scripts/docker_smoke.sh` — Wave 0 creates |
| **Quick run command** | `bash backend/scripts/docker_smoke.sh` (full run — no sub-modes per D-11) |
| **Full suite command** | `bash backend/scripts/docker_smoke.sh` |
| **Estimated runtime** | ~180 seconds (build cached) / ~600 seconds (cold build + models) |

---

## Sampling Rate

- **After every task commit:** Run `bash backend/scripts/docker_smoke.sh` (full run — build + health + ingest + regression)
- **After every plan wave:** Run `bash backend/scripts/docker_smoke.sh` (same — no sub-modes)
- **Before `/gsd:verify-work`:** Full script must exit 0
- **Max feedback latency:** 600 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 02-01-01 | 01 | 1 | DEPLOY-01 | fixture | `test -f backend/tests/fixtures/hello.pdf && test -f backend/tests/fixtures/hello.docx` | ❌ W0 | ⬜ pending |
| 02-01-02 | 01 | 1 | DEPLOY-01 | build + regression | `docker build -t ragkb-backend:test .` + CPU-torch/non-root/model-cache/no-`.env`-baked probes | ❌ W0 | ⬜ pending |
| 02-01-03 | 01 | 1 | DEPLOY-01 | smoke e2e | `bash backend/scripts/docker_smoke.sh` (preflight → build → size audit → health → PDF + DOCX ingest → regression) | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/fixtures/hello.pdf` — reportlab-generated, ≤50KB, committed (D-12)
- [ ] `backend/tests/fixtures/hello.docx` — python-docx-generated, ≤50KB, committed (D-12)
- [ ] `backend/scripts/generate_smoke_fixtures.py` — throwaway generator, committed (D-12)
- [ ] `backend/scripts/docker_smoke.sh` — executable, full run only (D-11)
- [ ] `Dockerfile` at repo root — does not yet exist (D-10)
- [ ] `.dockerignore` — preserved from Phase 1

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Image runs on fresh host without cached layers | DEPLOY-01 | Cold-cache only reproducible by pruning local Docker cache | `docker builder prune -af && docker build -t ragkb-backend:cold .` then rerun smoke script |
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
