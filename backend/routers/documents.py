import uuid
import logging
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from auth import get_user_id
from database import get_supabase
from services.ingestion_service import process_document, process_document_incremental
from services.record_manager import hash_content, check_duplicate, find_previous_version

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/documents", tags=["documents"])

mime_map = {
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".html": "text/html",
    ".htm": "text/html",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    folder_id: str | None = Form(None),
    user_id: str = Depends(get_user_id),
):
    db = get_supabase()
    doc_id = str(uuid.uuid4())

    # Determine mime type
    filename = file.filename or "unnamed"
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    mime_type = mime_map.get(ext)

    if not mime_type:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {ext}. Supported: .txt, .md, .pdf, .docx, .html, .jpg, .png, .xlsx"
        )

    # Read file content
    content = await file.read()
    content_hash = hash_content(content)
    file_size = len(content)
    logger.info(f"Upload '{filename}': content_hash={content_hash[:12]}..., size={file_size}")

    # Path A: Exact duplicate
    existing = check_duplicate(user_id, content_hash)
    if existing:
        logger.info(f"Duplicate detected for '{filename}': existing doc {existing['id']}")
        return {**existing, "duplicate": True, "message": "This file has already been uploaded"}

    # Path B: Check for same filename (incremental update candidate)
    previous = find_previous_version(user_id, filename)
    if previous:
        logger.info(f"Previous version found for '{filename}': doc {previous['id']}, has_hash={bool(previous.get('content_hash'))}")

    # Upload to Supabase Storage
    storage_path = f"{user_id}/{doc_id}/{filename}"
    db.storage.from_("documents").upload(
        path=storage_path,
        file=content,
        file_options={"content-type": mime_type},
    )

    # Create document record
    doc = db.table("documents").insert({
        "id": doc_id,
        "user_id": user_id,
        "filename": filename,
        "storage_path": storage_path,
        "file_size": file_size,
        "mime_type": mime_type,
        "status": "pending",
        "content_hash": content_hash,
        "folder_id": folder_id,
        "visibility": "private",
    }).execute()

    # Process document (synchronous for now)
    try:
        if previous and previous.get("content_hash"):
            logger.info(f"Incremental processing '{filename}' (old doc: {previous['id']})")
            process_document_incremental(doc_id, user_id, previous["id"])
        else:
            logger.info(f"Full processing '{filename}'")
            process_document(doc_id, user_id)
    except Exception as e:
        logger.error(f"Processing failed for '{filename}': {e}")

    # Return updated document
    result = db.table("documents").select("*").eq("id", doc_id).single().execute()
    return result.data


@router.get("")
def list_documents(user_id: str = Depends(get_user_id)):
    db = get_supabase()
    result = (
        db.table("documents")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )
    return result.data


@router.get("/{doc_id}")
def get_document(doc_id: str, user_id: str = Depends(get_user_id)):
    db = get_supabase()
    result = (
        db.table("documents")
        .select("*")
        .eq("id", doc_id)
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Document not found")
    return result.data


@router.delete("/{doc_id}", status_code=204)
def delete_document(doc_id: str, user_id: str = Depends(get_user_id)):
    db = get_supabase()

    # Get document
    doc = (
        db.table("documents")
        .select("*")
        .eq("id", doc_id)
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )
    if not doc.data:
        raise HTTPException(status_code=404, detail="Document not found")

    # Delete from storage
    try:
        db.storage.from_("documents").remove([doc.data["storage_path"]])
    except Exception:
        pass  # Storage file may already be gone

    # Delete document (chunks cascade-deleted)
    db.table("documents").delete().eq("id", doc_id).execute()


# ---------------------------------------------------------------------------
# Rename / Move / Bulk operations (Phase 04)
# ---------------------------------------------------------------------------


class DocumentRename(BaseModel):
    filename: str


class DocumentMove(BaseModel):
    folder_id: str | None = None


class BulkIds(BaseModel):
    ids: list[str]


class BulkMove(BaseModel):
    ids: list[str]
    folder_id: str | None = None


def _get_owned_private_document_or_403(db, doc_id: str, user_id: str) -> dict:
    """Fetch a document by id and enforce ownership + private visibility.

    Returns the document dict. Raises 404 if not found, 403 if public
    or not owned by user.
    """
    result = (
        db.table("documents")
        .select("*")
        .eq("id", doc_id)
        .maybe_single()
        .execute()
    )
    if not result or not result.data:
        raise HTTPException(status_code=404, detail="Document not found")
    data = result.data
    if data.get("visibility") == "public":
        raise HTTPException(
            status_code=403,
            detail="Cannot modify read-only (public) documents",
        )
    if data.get("user_id") != user_id:
        raise HTTPException(status_code=403, detail="Not allowed")
    return data


def _ensure_target_folder_writable(db, folder_id: str | None, user_id: str) -> None:
    """If folder_id is provided, verify target folder is private & owned."""
    if folder_id is None:
        return
    result = (
        db.table("folders")
        .select("*")
        .eq("id", folder_id)
        .maybe_single()
        .execute()
    )
    if not result or not result.data:
        raise HTTPException(status_code=404, detail="Target folder not found")
    target = result.data
    if target.get("visibility") == "public":
        raise HTTPException(
            status_code=403,
            detail="Cannot move items into read-only (public) folders",
        )
    if target.get("user_id") != user_id:
        raise HTTPException(status_code=403, detail="Not allowed")


@router.patch("/{doc_id}")
def rename_document(
    doc_id: str,
    body: DocumentRename,
    user_id: str = Depends(get_user_id),
):
    """Rename a private document. Public documents rejected with 403."""
    db = get_supabase()
    _get_owned_private_document_or_403(db, doc_id, user_id)
    db.table("documents").update({"filename": body.filename}).eq("id", doc_id).execute()
    result = (
        db.table("documents")
        .select("*")
        .eq("id", doc_id)
        .single()
        .execute()
    )
    return result.data


@router.patch("/{doc_id}/move")
def move_document(
    doc_id: str,
    body: DocumentMove,
    user_id: str = Depends(get_user_id),
):
    """Move a private document to a target private folder (or root)."""
    db = get_supabase()
    _get_owned_private_document_or_403(db, doc_id, user_id)
    _ensure_target_folder_writable(db, body.folder_id, user_id)
    db.table("documents").update({"folder_id": body.folder_id}).eq(
        "id", doc_id
    ).execute()
    result = (
        db.table("documents")
        .select("*")
        .eq("id", doc_id)
        .single()
        .execute()
    )
    return result.data


@router.post("/bulk-delete")
def bulk_delete_documents(
    body: BulkIds,
    user_id: str = Depends(get_user_id),
):
    """Bulk delete documents. Rejects entire batch (403) if ANY doc is
    not owned by the user or is public. Removes storage files first, then
    DB rows (chunks cascade)."""
    db = get_supabase()
    if not body.ids:
        return {"deleted": 0}

    # Validate every doc (ownership + private) before any mutation
    validated: list[dict] = []
    for doc_id in body.ids:
        validated.append(_get_owned_private_document_or_403(db, doc_id, user_id))

    storage_paths = [d["storage_path"] for d in validated if d.get("storage_path")]
    if storage_paths:
        try:
            db.storage.from_("documents").remove(storage_paths)
        except Exception as e:
            logger.warning(f"Bulk storage cleanup partial failure: {e}")

    db.table("documents").delete().in_("id", body.ids).execute()
    return {"deleted": len(body.ids)}


@router.post("/bulk-move")
def bulk_move_documents(
    body: BulkMove,
    user_id: str = Depends(get_user_id),
):
    """Bulk move documents into a target private folder (or root).
    Rejects entire batch (403) if target is public OR any doc is not
    owned / is public."""
    db = get_supabase()
    if not body.ids:
        return {"moved": 0}

    _ensure_target_folder_writable(db, body.folder_id, user_id)
    for doc_id in body.ids:
        _get_owned_private_document_or_403(db, doc_id, user_id)

    db.table("documents").update({"folder_id": body.folder_id}).in_(
        "id", body.ids
    ).execute()
    return {"moved": len(body.ids)}
