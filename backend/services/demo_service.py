"""Demo seed + anon-user cleanup helpers (Plan 08-02, PORT-01).

Two public functions + one private helper:

- `seed_anon_user_content(user_id)` — first-call sample-doc + welcome-thread seed
  for a newly-minted anon user. Idempotent (skips if user already has any
  document).
- `purge_stale_anon_users(retention_days=7)` — background-task cleanup that
  cascade-deletes anon users older than the retention threshold. Bounded to
  one page (≤100 users) per call so a Fly.io machine suspend never strands
  a half-finished sweep (RESEARCH §Pitfall 9).
- `_cascade_delete_user_data(db, user_id)` — child-first FK-safe delete of
  all rows owned by a user across storage + 5 tables. Order matters
  (RESEARCH §Pitfall 2/6); enforced by `test_cascade_order`.

Strict project rules respected: NO LangChain, NO LLM call in the bootstrap
path (welcome assistant message is a hard-coded string), service-role DB
client throughout (bypasses RLS).
"""
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone

from database import get_supabase
from services.ingestion_service import process_document
from services.record_manager import check_duplicate, hash_content

logger = logging.getLogger(__name__)

# Resolved relative to this file so the path is stable across cwd changes
# (worktrees, pytest invocations from repo root, uvicorn from backend/).
# Two layouts supported:
#   - dev/test:   backend/services/demo_service.py -> ../../data/... (repo root)
#   - container:  /app/services/demo_service.py    -> ../data/...    (/app/data)
# Dockerfile copies data/sample-private-docs/ to /app/data/sample-private-docs/.
_SAMPLE_DOC_CANDIDATES = (
    os.path.join(os.path.dirname(__file__), "..", "..", "data", "sample-private-docs", "dnd5e-quickref.md"),
    os.path.join(os.path.dirname(__file__), "..", "data", "sample-private-docs", "dnd5e-quickref.md"),
)
SAMPLE_DOC_PATH = next(
    (p for p in _SAMPLE_DOC_CANDIDATES if os.path.exists(p)),
    _SAMPLE_DOC_CANDIDATES[0],
)

# Locked welcome copy (CONTEXT D-02 + PATTERNS.md). NEVER route through an LLM —
# RESEARCH §Anti-Patterns forbids it (cost + latency on the cold-start path).
_WELCOME_THREAD_TITLE = "Welcome to the demo"
_WELCOME_USER_MESSAGE = (
    "What 2-player strategy games do you have in the library?"
)
_WELCOME_ASSISTANT_MESSAGE = (
    "Welcome to the board-game RAG demo! I can search across the default "
    "library of popular board games (Catan, Ticket to Ride, Pandemic, and more) "
    "as well as the D&D 5e quick-reference document I've already attached to "
    "your private collection. Try asking about game rules, mechanics, or "
    "recommendations — I'll use tools like search, list, and read to find the "
    "right answer and show my work."
)


def seed_anon_user_content(user_id: str) -> bool:
    """Seed sample doc + welcome thread for a fresh anon user.

    Returns True if seeding ran; False if idempotency hit (user already has
    a document or the sample content hash already exists for them).

    Steps:
    1. Idempotency check (skip if user has any document).
    2. Read sample doc bytes + content hash.
    3. Duplicate check via record_manager.
    4. Upload to storage at `{user_id}/{doc_id}/dnd5e-quickref.md`.
    5. Insert documents row (visibility='private', status='pending').
    6. Call process_document(doc_id, user_id) inline (sync — must complete
       before frontend navigates so the chat sees a ready document).
    7. Insert sample thread + 2 hard-coded messages.
    """
    db = get_supabase()

    # Idempotency guard — any prior document for this user blocks re-seed.
    existing = (
        db.table("documents")
        .select("id")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    if existing.data:
        logger.info(f"seed_anon_user_content: skip — user {user_id} already has documents")
        return False

    with open(SAMPLE_DOC_PATH, "rb") as f:
        file_bytes = f.read()

    content_hash = hash_content(file_bytes)
    if check_duplicate(user_id, content_hash):
        logger.info(f"seed_anon_user_content: skip — duplicate content hash for user {user_id}")
        return False

    doc_id = str(uuid.uuid4())
    filename = "dnd5e-quickref.md"
    storage_path = f"{user_id}/{doc_id}/{filename}"

    db.storage.from_("documents").upload(
        path=storage_path,
        file=file_bytes,
        file_options={"content-type": "text/markdown"},
    )

    db.table("documents").insert({
        "id": doc_id,
        "user_id": user_id,
        "filename": filename,
        "storage_path": storage_path,
        "file_size": len(file_bytes),
        "mime_type": "text/markdown",
        "status": "pending",
        "content_hash": content_hash,
        "folder_id": None,
        "visibility": "private",
    }).execute()

    # Inline ingestion: chunk + embed + insert document_chunks.
    process_document(doc_id, user_id)

    # Sample welcome thread — single user/assistant pair, no tool calls,
    # hard-coded copy (NO LLM call per RESEARCH §Anti-Patterns).
    thread_insert = (
        db.table("threads")
        .insert({"user_id": user_id, "title": _WELCOME_THREAD_TITLE})
        .execute()
    )
    thread_id = thread_insert.data[0]["id"]

    db.table("messages").insert([
        {
            "thread_id": thread_id,
            "user_id": user_id,
            "role": "user",
            "content": _WELCOME_USER_MESSAGE,
        },
        {
            "thread_id": thread_id,
            "user_id": user_id,
            "role": "assistant",
            "content": _WELCOME_ASSISTANT_MESSAGE,
        },
    ]).execute()

    logger.info(f"seed_anon_user_content: seeded doc {doc_id} + welcome thread for user {user_id}")
    return True


def purge_stale_anon_users(retention_days: int = 7) -> int:
    """Cascade-delete anon users older than `retention_days`.

    Bounded to a single 100-user page per call (RESEARCH §Pitfall 9 — Fly.io
    machine suspend safety: never start work that cannot finish before the
    machine sleeps). Per-user errors are logged and swallowed so one bad row
    does not abort the rest of the sweep.

    Returns the count of users successfully deleted.
    """
    db = get_supabase()
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    deleted = 0

    users = db.auth.admin.list_users(page=1, per_page=100)

    for u in users:
        if not (getattr(u, "is_anonymous", False) and u.created_at < cutoff):
            continue
        try:
            _cascade_delete_user_data(db, u.id)
            db.auth.admin.delete_user(u.id)
            deleted += 1
        except Exception as e:
            logger.warning(f"purge_stale_anon_users: failed to purge {u.id}: {e}")

    logger.info(f"purge_stale_anon_users: deleted {deleted} anon users (cutoff={cutoff.isoformat()})")
    return deleted


def _cascade_delete_user_data(db, user_id: str) -> None:
    """Delete all rows + storage objects owned by `user_id`.

    Order is load-bearing (RESEARCH §Pitfall 2/6 — FK constraints + storage
    parent path). Storage objects deleted FIRST so a partial DB-delete failure
    never leaves orphaned files. DB deletes child-first to satisfy FK order.

    Raises on DB delete failure (caller wraps in try/except per `purge_stale_anon_users`).
    """
    # Storage first — mirror documents.py:148-152 (swallow storage errors;
    # objects may already be gone or the prefix may not exist).
    try:
        objs = db.storage.from_("documents").list(f"{user_id}/")
        if objs:
            paths = [f"{user_id}/{o['name']}" for o in objs]
            db.storage.from_("documents").remove(paths)
    except Exception as e:
        logger.warning(f"_cascade_delete_user_data: storage remove failed for {user_id}: {e}")

    # DB deletes — child-first FK-safe order. NO try/except: let exceptions
    # bubble to the caller's per-user guard so failures are logged + counted.
    db.table("document_chunks").delete().eq("user_id", user_id).execute()
    db.table("documents").delete().eq("user_id", user_id).execute()
    db.table("folders").delete().eq("user_id", user_id).execute()
    db.table("messages").delete().eq("user_id", user_id).execute()
    db.table("threads").delete().eq("user_id", user_id).execute()
