"""Regression tests for Module 3: Record Manager.

Tests duplicate detection, incremental updates, and fresh uploads
against the live Supabase backend. Requires .env with valid credentials.

Usage: cd backend && python -m tests.test_record_manager
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from config import get_settings
from database import get_supabase
from services.record_manager import hash_content, hash_chunk, check_duplicate, find_previous_version, diff_chunks

settings = get_settings()

# --- Unit tests (no DB) ---

def test_hash_deterministic():
    h1 = hash_content(b"hello world")
    h2 = hash_content(b"hello world")
    assert h1 == h2, "hash_content not deterministic"
    assert len(h1) == 64, f"Expected SHA-256 hex (64 chars), got {len(h1)}"
    print("  PASS hash_content is deterministic")

def test_hash_chunk_deterministic():
    h1 = hash_chunk("hello world")
    h2 = hash_chunk("hello world")
    assert h1 == h2, "hash_chunk not deterministic"
    print("  PASS hash_chunk is deterministic")

def test_different_content_different_hash():
    h1 = hash_content(b"hello")
    h2 = hash_content(b"world")
    assert h1 != h2, "Different content should produce different hashes"
    print("  PASS different content -> different hash")

def test_diff_chunks_new_and_stale():
    old = {"abc": "id1", "def": "id2"}
    new = ["abc", "xyz"]
    new_indices, stale_ids = diff_chunks(old, new)
    assert new_indices == [1], f"Expected [1], got {new_indices}"
    assert stale_ids == ["id2"], f"Expected ['id2'], got {stale_ids}"
    print("  PASS diff_chunks identifies new and stale correctly")

def test_diff_chunks_no_changes():
    old = {"abc": "id1", "def": "id2"}
    new = ["abc", "def"]
    new_indices, stale_ids = diff_chunks(old, new)
    assert new_indices == [], f"Expected [], got {new_indices}"
    assert stale_ids == [], f"Expected [], got {stale_ids}"
    print("  PASS diff_chunks with no changes")

def test_diff_chunks_all_new():
    old = {"abc": "id1"}
    new = ["xyz", "uvw"]
    new_indices, stale_ids = diff_chunks(old, new)
    assert new_indices == [0, 1], f"Expected [0, 1], got {new_indices}"
    assert stale_ids == ["id1"], f"Expected ['id1'], got {stale_ids}"
    print("  PASS diff_chunks all new content")


# --- Integration tests (hit DB) ---

def get_test_user_id():
    """Sign in with test credentials and return user_id."""
    from supabase import create_client
    client = create_client(settings.supabase_url_resolved, settings.vite_supabase_anon_key)
    auth = client.auth.sign_in_with_password({"email": "ragtest1@gmail.com", "password": "testpass123"})
    return auth.user.id

def cleanup_test_docs(user_id: str, filename: str):
    """Delete all documents with given filename for the test user."""
    db = get_supabase()
    docs = db.table("documents").select("id, storage_path").eq("user_id", user_id).eq("filename", filename).execute()
    for doc in docs.data:
        try:
            db.storage.from_("documents").remove([doc["storage_path"]])
        except Exception:
            pass
        db.table("documents").delete().eq("id", doc["id"]).execute()

def test_check_duplicate_integration(user_id: str):
    """Test that check_duplicate finds a completed doc with matching hash."""
    db = get_supabase()
    import uuid
    doc_id = str(uuid.uuid4())
    content = b"test_duplicate_detection_content_12345"
    ch = hash_content(content)

    # Clean up first
    cleanup_test_docs(user_id, "__test_dup.txt")

    # Insert a completed document with content_hash
    db.table("documents").insert({
        "id": doc_id,
        "user_id": user_id,
        "filename": "__test_dup.txt",
        "storage_path": f"{user_id}/{doc_id}/__test_dup.txt",
        "file_size": len(content),
        "mime_type": "text/plain",
        "status": "completed",
        "content_hash": ch,
    }).execute()

    # check_duplicate should find it
    found = check_duplicate(user_id, ch)
    assert found is not None, "check_duplicate should find the completed doc"
    assert found["id"] == doc_id, f"Expected doc {doc_id}, got {found['id']}"
    print("  PASS check_duplicate finds completed doc with matching hash")

    # check_duplicate with different hash should NOT find it
    found2 = check_duplicate(user_id, "nonexistent_hash")
    assert found2 is None, "check_duplicate should return None for non-matching hash"
    print("  PASS check_duplicate returns None for non-matching hash")

    # Cleanup
    db.table("documents").delete().eq("id", doc_id).execute()

def test_find_previous_version_integration(user_id: str):
    """Test that find_previous_version works even with multiple docs of same name."""
    db = get_supabase()
    import uuid

    cleanup_test_docs(user_id, "__test_prev.txt")

    # Insert two completed docs with same filename
    doc1_id = str(uuid.uuid4())
    doc2_id = str(uuid.uuid4())
    for did in [doc1_id, doc2_id]:
        db.table("documents").insert({
            "id": did,
            "user_id": user_id,
            "filename": "__test_prev.txt",
            "storage_path": f"{user_id}/{did}/__test_prev.txt",
            "file_size": 10,
            "mime_type": "text/plain",
            "status": "completed",
            "content_hash": hash_content(did.encode()),
        }).execute()

    # Should NOT crash (was using maybe_single before)
    found = find_previous_version(user_id, "__test_prev.txt")
    assert found is not None, "find_previous_version should find a doc"
    print("  PASS find_previous_version handles multiple same-name docs without crashing")

    # Cleanup
    for did in [doc1_id, doc2_id]:
        db.table("documents").delete().eq("id", did).execute()


if __name__ == "__main__":
    print("\n=== Unit Tests ===")
    test_hash_deterministic()
    test_hash_chunk_deterministic()
    test_different_content_different_hash()
    test_diff_chunks_new_and_stale()
    test_diff_chunks_no_changes()
    test_diff_chunks_all_new()

    print("\n=== Integration Tests ===")
    uid = get_test_user_id()
    print(f"  Test user: {uid}")
    test_check_duplicate_integration(uid)
    test_find_previous_version_integration(uid)

    print("\nOK: All tests passed!")
