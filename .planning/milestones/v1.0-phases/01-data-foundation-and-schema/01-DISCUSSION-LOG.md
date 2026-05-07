# Phase 1: Data Foundation and Schema - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md -- this log preserves the alternatives considered.

**Date:** 2026-04-07
**Phase:** 01-data-foundation-and-schema
**Areas discussed:** Default KB ownership, Folder structure

---

## Default KB Ownership

### Question 1: How should default KB content be owned in the database?

| Option | Description | Selected |
|--------|-------------|----------|
| NULL user_id + visibility column | Default KB has user_id=NULL and visibility='public'. Requires making user_id nullable. | |
| System user account | Dedicated system user owns default content. user_id stays NOT NULL. | |
| Separate tables | Default KB in its own tables. Simpler RLS but duplicated schema. | |

**User's choice:** System user account + visibility column (hybrid of first two options)
**Notes:** User wanted both: system user to keep user_id NOT NULL, plus visibility column for flexible access control.

### Question 2: Visibility column values

| Option | Description | Selected |
|--------|-------------|----------|
| public/private | Simple binary. Covers current needs. | |
| public/private/shared | Adds 'shared' for future sharing feature. | |
| You decide | Claude picks. | ✓ |

**User's choice:** You decide
**Notes:** Claude has discretion on visibility values.

### Question 3: Root folder structure

| Option | Description | Selected |
|--------|-------------|----------|
| Flat start | Users start with no folders. Default KB appears as top-level folder. | |
| Pre-created | Each user gets 'My Documents' root on signup. Default KB is separate 'Board Games' root. | ✓ |
| You decide | Claude picks the best UX approach. | |

**User's choice:** Pre-created
**Notes:** Users get a "My Documents" root folder. Default KB appears as "Board Games" root.

---

## Folder Structure

### Question 1: ltree vs text paths

| Option | Description | Selected |
|--------|-------------|----------|
| ltree (Recommended) | Postgres extension with GiST indexes. Native ancestor/descendant queries. | ✓ |
| Text paths | Store paths as '/root/games/catan'. Simpler but needs LIKE patterns. | |
| You decide | Claude picks based on query patterns. | |

**User's choice:** ltree
**Notes:** Research recommended ltree. Supabase supports it.

### Question 2: How deep should folder nesting be allowed?

| Option | Description | Selected |
|--------|-------------|----------|
| Unlimited (Recommended) | No artificial limit. Materialized paths handle any depth. | ✓ |
| 3 levels max | Root > Category > Subcategory. Keeps it simple. | |
| 5 levels max | Enough for most use cases. | |

**User's choice:** Unlimited
**Notes:** No artificial nesting limits.

### Question 3: Document-to-folder relationship

| Option | Description | Selected |
|--------|-------------|----------|
| folder_id on documents (Recommended) | Add folder_id FK. One document = one folder. | ✓ |
| Junction table | Separate doc_folders table. Allows one doc in multiple folders. | |
| You decide | Claude picks simpler approach. | |

**User's choice:** folder_id on documents
**Notes:** Simple FK relationship. One document belongs to one folder.

---

## Claude's Discretion

- Visibility column value set
- Storage path design for folder hierarchy
- Migration numbering and ordering
- Whether to denormalize visibility to document_chunks
- Folder table constraints and indexes

## Deferred Ideas

None -- discussion stayed within phase scope
