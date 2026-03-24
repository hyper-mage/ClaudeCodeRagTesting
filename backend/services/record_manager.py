import hashlib
from database import get_supabase


def hash_content(content: bytes) -> str:
    """SHA-256 hash of raw file bytes for file-level duplicate detection."""
    return hashlib.sha256(content).hexdigest()


def hash_chunk(text: str) -> str:
    """SHA-256 hash of chunk text for chunk-level change detection."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def check_duplicate(user_id: str, content_hash: str) -> dict | None:
    """Check if user already has a completed document with this content hash.
    Returns existing document record or None."""
    db = get_supabase()
    result = (
        db.table("documents")
        .select("*")
        .eq("user_id", user_id)
        .eq("content_hash", content_hash)
        .eq("status", "completed")
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None


def find_previous_version(user_id: str, filename: str) -> dict | None:
    """Find the most recent completed document with the same filename (for incremental update)."""
    db = get_supabase()
    result = (
        db.table("documents")
        .select("*")
        .eq("user_id", user_id)
        .eq("filename", filename)
        .eq("status", "completed")
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None


def get_existing_chunk_hashes(document_id: str) -> dict[str, str]:
    """Get all chunk hashes for a document. Returns {content_hash: chunk_id}."""
    db = get_supabase()
    result = (
        db.table("document_chunks")
        .select("id, content_hash")
        .eq("document_id", document_id)
        .execute()
    )
    return {row["content_hash"]: row["id"] for row in result.data if row["content_hash"]}


def diff_chunks(
    old_hashes: dict[str, str],   # {content_hash: chunk_id}
    new_hashes: list[str],         # content_hashes of new chunks in order
) -> tuple[list[int], list[str]]:
    """Compare old and new chunk hashes.
    Returns (new_chunk_indices, stale_chunk_ids)."""
    old_set = set(old_hashes.keys())
    new_set = set(new_hashes)
    new_indices = [i for i, h in enumerate(new_hashes) if h not in old_set]
    stale_ids = [cid for h, cid in old_hashes.items() if h not in new_set]
    return new_indices, stale_ids
