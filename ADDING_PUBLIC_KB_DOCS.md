# Adding Public KB Documents

How to expand the default (public) knowledge base — the pre-seeded board games every user sees, owned by the system user with `visibility: public`.

Private user uploads go through the Documents UI. **Public docs do not** — they are added by dropping a markdown file and running the seed script. This guide covers the public path.

---

## How it works

The public KB is built from three pieces:

| Piece | Location | Role |
|---|---|---|
| Markdown source files | `data/default-kb/*.md` | The actual document content |
| `GAMES` registry | `backend/scripts/seed_default_kb.py` | Maps `filename → display name` |
| Seed script | `backend/scripts/seed_default_kb.py` | Uploads, chunks, embeds each file |

The script is **idempotent**: it hashes each file's content and skips anything already ingested (`check_duplicate`). Re-running is safe — only new files get processed.

Every seeded doc is:
- Owned by the **system user** (`00000000-0000-0000-0000-000000000000`)
- Marked `visibility: public` (visible to all users via RLS)
- Placed in a per-game subfolder under the **Board Games** root folder (`a0000000-0000-0000-0000-000000000001`)

---

## Add a new document

### 1. Write the markdown

Drop a new `.md` file in `data/default-kb/`. Use kebab-case filename.

```
data/default-kb/gloomhaven.md
```

Match the existing structure — look at `data/default-kb/catan.md` for the template. Recommended sections:

```markdown
# Gloomhaven

## Overview
...

## Setup
...

## Turn Structure
...

## Win Conditions
...

## Components
...
```

Clean headers help chunking. One game per file.

### 2. Register it in the seed script

Add an entry to the `GAMES` dict in `backend/scripts/seed_default_kb.py`:

```python
GAMES = {
    "catan.md": "Catan",
    "ticket-to-ride.md": "Ticket to Ride",
    # ...
    "gloomhaven.md": "Gloomhaven",   # <-- add this
}
```

Key = filename in `data/default-kb/`. Value = display name (becomes the subfolder name).

### 3. Run the seed

**Local / dev** (from `backend/`, venv active):

```bash
cd backend
python scripts/seed_default_kb.py
```

Existing games print `Skipping ... (already seeded)`; new ones print `Seeded ...`.

**Production** (loads prod creds from `.env.prod`):

```bash
cd backend
ENV_FILE=.env.prod python -m scripts.seed_default_kb
```

### 4. Verify

- Log in, open chat, ask about the new game — the agent should find it via KB tools.
- Or check the Documents / folder view: new subfolder under **Board Games**.

---

## Notes & gotchas

- **Editing an existing file changes its content hash.** Since the script dedups by content hash, an edited file is *not* skipped — it re-ingests. To avoid a stale duplicate, delete the old public doc first (or confirm the filename-based incremental re-parent in `record_manager` handles it). Cleanest path: add *new* files rather than mutate seeded ones.
- **Board Games namespace is assumed.** The script parents every game under the Board Games root and derives folder UUIDs from `boardgame.<label>`. A different top-level category needs script changes (new root folder + parent ID), not just a new `GAMES` entry.
- **Supabase-only storage.** Files upload to the `documents` storage bucket + `documents`/`document_chunks` tables. Nothing runs off the local filesystem at query time — the local `.md` is only the ingestion source.
- **Markdown only via this path.** The seed script hardcodes `text/markdown`. For PDF/DOCX public docs you'd extend the script to route through Docling (as the normal ingestion pipeline does).

---

## Quick reference

```bash
# 1. add file
data/default-kb/<name>.md

# 2. register
# backend/scripts/seed_default_kb.py  ->  GAMES["<name>.md"] = "<Display Name>"

# 3. seed (dev)
cd backend && python scripts/seed_default_kb.py

# 3. seed (prod)
cd backend && ENV_FILE=.env.prod python -m scripts.seed_default_kb
```
