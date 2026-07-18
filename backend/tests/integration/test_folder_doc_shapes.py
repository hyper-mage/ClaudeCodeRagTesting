"""Real-DB shape tests for GET /api/folders/{id}/contents and GET /api/documents
(quick task 260718-o4c).

These hit the REAL dev Supabase — `get_supabase` is NOT patched. They guard the READ-path
row shapes against real PostgREST.

OUT OF SCOPE (intentional): heavier folder/document flows requiring a real Storage upload
(POST /api/documents/upload). Inserting rows directly is sufficient to guard the READ-path
shapes and avoids Storage-object scaffolding (per the design's "prefer to SKIP heavy
scaffolding" guidance). The thread trio remains the high-value core of this suite.
"""
import pytest

from tests.integration import requires_supabase, SENTINEL

pytestmark = [pytest.mark.integration, requires_supabase]


def test_folder_contents_shape(seeded_folder, client):
    fid = seeded_folder

    resp = client.get(f"/api/folders/{fid}/contents")
    assert resp.status_code == 200, resp.text

    body = resp.json()
    # This exercises the real `_get_folder_or_404` `maybe_single()` — the SAFE usage of
    # maybe_single WITHOUT resource embedding — plus the two real child selects.
    assert set(["folder", "subfolders", "documents"]).issubset(body.keys())
    assert body["folder"]["id"] == fid
    assert isinstance(body["subfolders"], list)  # empty for a fresh folder
    assert isinstance(body["documents"], list)


def test_documents_list_shape(seeded_document, client):
    did = seeded_document

    resp = client.get("/api/documents")
    assert resp.status_code == 200, resp.text

    body = resp.json()
    # list_documents has NO response_model → this guards the RAW PostgREST row shape directly.
    assert isinstance(body, list)
    row = next((d for d in body if d["id"] == did), None)
    assert row is not None
    assert row["filename"].startswith(SENTINEL)
    for key in (
        "id",
        "filename",
        "status",
        "file_size",
        "mime_type",
        "storage_path",
        "visibility",
        "created_at",
    ):
        assert key in row, f"missing raw DB-shape key: {key}"
