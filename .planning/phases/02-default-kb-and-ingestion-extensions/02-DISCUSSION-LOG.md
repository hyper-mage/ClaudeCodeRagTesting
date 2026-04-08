# Phase 2: Default KB and Ingestion Extensions - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md -- this log preserves the alternatives considered.

**Date:** 2026-04-08
**Phase:** 02-default-kb-and-ingestion-extensions
**Areas discussed:** Game Selection & Content, Seeding Mechanism, OCR Approach, Folder Selection on Upload

---

## Game Selection & Content

### Content Depth

| Option | Description | Selected |
|--------|-------------|----------|
| Rules-focused | Rules overview, setup, turn structure, win conditions, components | Y |
| Comprehensive | Rules + strategy + FAQ + player counts + house rules | |
| Minimal seed | 1-2 page summary per game | |

**User's choice:** Rules-focused
**Notes:** None

### Game Selection

| Option | Description | Selected |
|--------|-------------|----------|
| Claude picks | 10 well-known classics | |
| I'll provide a list | User provides full list | |
| Mix | User names some, Claude fills rest | Y |

**User's choice:** Mix -- some picks + some classics
**Notes:** User will provide their picks during planning. Claude fills remaining slots with popular classics.

---

## Seeding Mechanism

### Loading Method

| Option | Description | Selected |
|--------|-------------|----------|
| Markdown files + seed script | Checked-in .md files, Python script ingests as system user | Y |
| SQL migration | Inline content in SQL INSERT statements | |
| Admin seed endpoint | Backend endpoint triggered on deploy | |

**User's choice:** Markdown files + seed script

### Folder Structure

| Option | Description | Selected |
|--------|-------------|----------|
| One subfolder per game | Board Games/Catan/, Board Games/Pandemic/, etc. | Y |
| Flat -- all docs in root | All 10 docs directly under Board Games/ | |

**User's choice:** One subfolder per game

---

## OCR Approach

| Option | Description | Selected |
|--------|-------------|----------|
| Docling's image pipeline | Uses EasyOCR under the hood, unified pipeline | Y |
| Tesseract (pytesseract) | Separate system dependency | |
| Cloud OCR API | Google Vision / AWS Textract / Azure | |

**User's choice:** Docling's image pipeline
**Notes:** Keeps parsing unified -- one library for all formats.

---

## Folder Selection on Upload

| Option | Description | Selected |
|--------|-------------|----------|
| Backend-only | Add folder_id to API, no frontend UI yet | Y |
| Simple dropdown | Basic folder picker in upload UI | |
| Auto-create My Documents | Backend-only + auto-create root folder per user | |

**User's choice:** Backend-only
**Notes:** Phase 4 adds the full file manager UI with folder selection.

---

## Claude's Discretion

- Seed script location, invocation, and idempotency strategy
- Docling image OCR configuration
- XLSX formatting decisions
- Chunk size tuning for game rules

## Deferred Ideas

None
