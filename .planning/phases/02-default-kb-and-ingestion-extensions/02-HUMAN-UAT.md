---
status: partial
phase: 02-default-kb-and-ingestion-extensions
source: [02-VERIFICATION.md]
started: 2026-04-08T18:00:00Z
updated: 2026-04-08T18:00:00Z
---

## Current Test

[awaiting human testing]

## Tests

### 1. Run seed script and verify board games are queryable
expected: cd backend && python -m scripts.seed_default_kb outputs 'Seeded 10 games', and chatting with agent about Catan returns accurate rules
result: [pending]

### 2. Upload a JPG image and verify OCR extraction
expected: Upload a photo of a rule card via the UI, document processes to 'completed' status with extracted text chunks
result: [pending]

### 3. Upload an XLSX file and verify markdown extraction
expected: Upload a spreadsheet via the UI, document processes to 'completed' status with markdown content in chunks
result: [pending]

### 4. Verify folder association on upload
expected: Upload a file with a folder selected, verify the document record has the correct folder_id in Supabase
result: [pending]

## Summary

total: 4
passed: 0
issues: 0
pending: 4
skipped: 0
blocked: 0

## Gaps
