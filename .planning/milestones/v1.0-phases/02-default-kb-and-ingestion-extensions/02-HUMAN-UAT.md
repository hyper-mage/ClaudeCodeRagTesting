---
status: resolved
phase: 02-default-kb-and-ingestion-extensions
source: [02-VERIFICATION.md]
started: 2026-04-08T18:00:00Z
updated: 2026-04-08T18:30:00Z
---

## Current Test

[complete]

## Tests

### 1. Run seed script and verify board games are queryable
expected: cd backend && python -m scripts.seed_default_kb outputs 'Seeded 10 games', and chatting with agent about Catan returns accurate rules
result: passed

### 2. Upload a JPG image and verify OCR extraction
expected: Upload a photo of a rule card via the UI, document processes to 'completed' status with extracted text chunks
result: passed (required Windows symlink workaround in parsing_service.py)

### 3. Upload an XLSX file and verify markdown extraction
expected: Upload a spreadsheet via the UI, document processes to 'completed' status with markdown content in chunks
result: passed

### 4. Verify folder association on upload
expected: Upload a file with a folder selected, verify the document record has the correct folder_id in Supabase
result: skipped (folder picker UI is Phase 4 — backend parameter wired and unit tested)

## Summary

total: 4
passed: 3
issues: 0
pending: 0
skipped: 1
blocked: 0

## Gaps
