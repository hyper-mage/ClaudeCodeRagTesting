---
status: partial
phase: 02-dockerize-backend
source: [02-VERIFICATION.md]
started: 2026-04-26
updated: 2026-04-26
---

## Current Test

[awaiting human testing]

## Tests

### 1. Run end-to-end smoke script
expected: `bash backend/scripts/docker_smoke.sh` exits 0; output contains `SMOKE PASS`, `Health 200`, two `-> N chunks` lines (PDF + DOCX, N>0), and four `[ OK ]` regression lines (CPU torch, appuser, models, no .env)
result: [pending]

### 2. Confirm built image size <7.5GB (hard) and ideally <6GB
expected: `docker image inspect boardgame-rag-backend:smoke --format '{{.Size}}'` returns value < 8053063680 (7.5 GB). Smoke script auto-checks this and FAILs > 7.5 GB / WARNs 6-7.5 GB.
result: [pending]

## Summary

total: 2
passed: 0
issues: 0
pending: 2
skipped: 0
blocked: 0

## Gaps
